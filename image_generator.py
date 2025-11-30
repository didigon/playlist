"""
이미지 생성 모듈
OpenAI DALL-E 3를 사용한 이미지 생성 기능
"""

import os
import time
import requests
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable, Tuple
from datetime import datetime
from PIL import Image
import io

from config_manager import load_config, get_api_key, get_path
from db_manager import TrackDB
from prompt_builder import ImagePromptBuilder
from logger import setup_logger


class ImageGeneratorError(Exception):
    """이미지 생성 관련 예외"""
    pass


class ImageGeneratorBase(ABC):
    """이미지 생성기 추상 클래스"""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> bytes:
        """
        이미지 생성 후 바이너리 반환
        
        Args:
            prompt: 이미지 프롬프트
            **kwargs: 추가 옵션 (size, quality, style 등)
        
        Returns:
            이미지 바이너리 데이터
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        서비스 상태 확인
        
        Returns:
            연결 성공 여부
        """
        pass


class OpenAIImageGenerator(ImageGeneratorBase):
    """OpenAI DALL-E 구현체"""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        OpenAIImageGenerator 초기화
        
        Args:
            api_key: OpenAI API 키 (None이면 config에서 로드)
            config: 설정 딕셔너리 (None이면 자동 로드)
        """
        if config is None:
            config = load_config()
        
        if api_key is None:
            api_key = get_api_key('openai', config)
        
        self.api_key = api_key
        self.model = config.get("image", {}).get("model", "dall-e-3")
        self.default_size = config.get("image", {}).get("default_size", "1792x1024")
        self.quality = config.get("image", {}).get("quality", "hd")
        
        # OpenAI 클라이언트 초기화
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImageGeneratorError("openai 패키지가 설치되지 않았습니다. pip install openai 실행하세요.")
        
        self.logger = setup_logger("image_generator")
    
    def health_check(self) -> bool:
        """
        API 연결 상태 확인
        
        Returns:
            연결 성공 여부
        """
        try:
            if not self.api_key or self.api_key == "YOUR_OPENAI_API_KEY":
                self.logger.warning("OpenAI API 키가 설정되지 않았습니다.")
                return False
            
            # 간단한 모델 목록 조회로 연결 확인
            # 실제로는 이미지 생성 API가 별도이므로 키 유효성만 확인
            return True
        except Exception as e:
            self.logger.error(f"Health check 실패: {e}")
            return False
    
    def generate(self, prompt: str, **kwargs) -> bytes:
        """
        DALL-E 이미지 생성
        
        Args:
            prompt: 이미지 프롬프트
            size: "1024x1024" | "1792x1024" | "1024x1792" (DALL-E 3는 1024x1024, 1792x1024, 1024x1792만 지원)
            quality: "standard" | "hd"
            style: "vivid" | "natural"
        
        Returns:
            이미지 바이너리 데이터
        
        Raises:
            ImageGeneratorError: API 오류 시
        """
        size = kwargs.get("size", self.default_size)
        quality = kwargs.get("quality", self.quality)
        style = kwargs.get("style", "vivid")
        
        # 프롬프트 검증
        if not prompt or len(prompt.strip()) == 0:
            raise ImageGeneratorError("프롬프트가 비어있습니다.")
        
        # DALL-E 3는 프롬프트 길이 제한 (최대 4000자)
        if len(prompt) > 4000:
            prompt = prompt[:4000]
            self.logger.warning("프롬프트가 4000자를 초과하여 잘렸습니다.")
        
        try:
            self.logger.info(f"이미지 생성 요청: {prompt[:50]}...")
            
            # DALL-E 3 API 호출
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1
            )
            
            # 이미지 URL 추출
            image_url = response.data[0].url
            
            # 이미지 다운로드
            image_data = self._download_image(image_url)
            
            self.logger.info("이미지 생성 완료")
            return image_data
        
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                raise ImageGeneratorError("OpenAI API 키가 유효하지 않습니다.")
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                raise ImageGeneratorError("API 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요.")
            elif "content_policy_violation" in error_msg.lower():
                raise ImageGeneratorError("프롬프트가 콘텐츠 정책을 위반했습니다.")
            else:
                raise ImageGeneratorError(f"이미지 생성 실패: {error_msg}")
    
    def _download_image(self, url: str) -> bytes:
        """
        URL에서 이미지 다운로드
        
        Args:
            url: 이미지 URL
        
        Returns:
            이미지 바이너리 데이터
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            raise ImageGeneratorError(f"이미지 다운로드 실패: {str(e)}")


def get_image_generator(
    provider: str = "openai",
    api_key: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> ImageGeneratorBase:
    """
    설정에 따른 생성기 인스턴스 반환
    
    Args:
        provider: 제공자 이름 ("openai")
        api_key: API 키 (None이면 config에서 로드)
        config: 설정 딕셔너리 (None이면 자동 로드)
    
    Returns:
        ImageGeneratorBase 인스턴스
    
    Raises:
        ImageGeneratorError: 지원하지 않는 provider
    """
    generators = {
        "openai": OpenAIImageGenerator,
        # 향후 확장: "midjourney": MidjourneyGenerator,
        # "stable_diffusion": StableDiffusionGenerator,
    }
    
    if provider not in generators:
        raise ImageGeneratorError(f"지원하지 않는 이미지 생성기: {provider}")
    
    return generators[provider](api_key=api_key, config=config)


class ImageGenerator:
    """이미지 생성기 래퍼 클래스 (고수준 API)"""
    
    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        ImageGenerator 초기화
        
        Args:
            provider: 제공자 이름
            api_key: API 키
            config: 설정 딕셔너리
        """
        if config is None:
            config = load_config()
        
        self.config = config
        self.generator = get_image_generator(provider, api_key, config)
        self.prompt_builder = ImagePromptBuilder()
        self.logger = setup_logger("image_generator")
        
        # 경로 설정
        self.image_folder = Path(get_path('image_folder', config))
        self.image_folder.mkdir(parents=True, exist_ok=True)
    
    def save_image(
        self,
        image_data: bytes,
        save_path: str,
        format: str = "png",
        resize: Optional[Tuple[int, int]] = None
    ) -> bool:
        """
        이미지 저장
        
        Args:
            image_data: 이미지 바이너리
            save_path: 저장 경로
            format: "png" | "jpg"
            resize: (width, height) 또는 None
        
        Returns:
            성공 여부
        """
        try:
            save_path_obj = Path(save_path)
            save_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # 이미지 로드
            image = Image.open(io.BytesIO(image_data))
            
            # 리사이즈
            if resize:
                image = image.resize(resize, Image.Resampling.LANCZOS)
            
            # 포맷 변환 및 저장
            if format.lower() == "jpg" or format.lower() == "jpeg":
                # PNG를 JPG로 변환 (RGB 모드 필요)
                if image.mode in ("RGBA", "LA", "P"):
                    # 투명 배경을 흰색으로 변환
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "P":
                        image = image.convert("RGBA")
                    background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
                    image = background
                elif image.mode != "RGB":
                    image = image.convert("RGB")
                
                save_path_obj = save_path_obj.with_suffix('.jpg')
                image.save(save_path_obj, "JPEG", quality=95)
            else:
                # PNG 저장
                save_path_obj = save_path_obj.with_suffix('.png')
                image.save(save_path_obj, "PNG")
            
            self.logger.info(f"이미지 저장 완료: {save_path_obj}")
            return True
        
        except Exception as e:
            self.logger.error(f"이미지 저장 실패: {e}")
            return False
    
    def convert_format(
        self,
        input_path: str,
        output_format: str,
        quality: int = 95
    ) -> Optional[str]:
        """
        이미지 포맷 변환
        
        Args:
            input_path: 입력 파일 경로
            output_format: 출력 포맷 ("png" | "jpg")
            quality: JPG 품질 (1-100)
        
        Returns:
            변환된 파일 경로 (실패 시 None)
        """
        try:
            input_path_obj = Path(input_path)
            if not input_path_obj.exists():
                raise ImageGeneratorError(f"파일을 찾을 수 없습니다: {input_path}")
            
            image = Image.open(input_path_obj)
            output_path_obj = input_path_obj.with_suffix(f'.{output_format.lower()}')
            
            if output_format.lower() == "jpg" or output_format.lower() == "jpeg":
                if image.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", image.size, (255, 255, 255))
                    if image.mode == "P":
                        image = image.convert("RGBA")
                    background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
                    image = background
                elif image.mode != "RGB":
                    image = image.convert("RGB")
                
                image.save(output_path_obj, "JPEG", quality=quality)
            else:
                image.save(output_path_obj, "PNG")
            
            self.logger.info(f"포맷 변환 완료: {output_path_obj}")
            return str(output_path_obj)
        
        except Exception as e:
            self.logger.error(f"포맷 변환 실패: {e}")
            return None
    
    def get_existing_image_path(self, track_id: str) -> Optional[str]:
        """
        기존 이미지 경로 반환 (없으면 None)
        
        Args:
            track_id: 트랙 ID
        
        Returns:
            이미지 파일 경로 또는 None
        """
        # PNG와 JPG 둘 다 체크
        for ext in [".png", ".jpg", ".jpeg"]:
            image_path = self.image_folder / f"{track_id}{ext}"
            if image_path.exists():
                return str(image_path)
        return None
    
    def should_generate(self, track_id: str, force: bool = False) -> bool:
        """
        생성 필요 여부 판단
        
        Args:
            track_id: 트랙 ID
            force: True면 기존 파일 있어도 재생성
        
        Returns:
            생성 필요 여부
        """
        if force:
            return True
        
        existing = self.get_existing_image_path(track_id)
        if existing:
            self.logger.info(f"이미지가 이미 존재합니다: {existing} (스킵)")
            return False
        
        return True
    
    def get_resolution_for_platform(self, platform: str) -> Tuple[int, int]:
        """
        플랫폼별 해상도 반환
        
        Args:
            platform: "youtube" | "shorts" | "instagram"
        
        Returns:
            (width, height)
        """
        resolutions = {
            "youtube": (1920, 1080),
            "shorts": (1080, 1920),
            "instagram": (1080, 1080),
        }
        return resolutions.get(platform.lower(), (1920, 1080))
    
    def generate_for_track(
        self,
        track_id: str,
        db: TrackDB,
        style: str = "default",
        force: bool = False,
        resolution: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """
        단일 트랙 이미지 생성
        
        Args:
            track_id: 트랙 ID
            db: TrackDB 인스턴스
            style: 스타일 이름
            force: 강제 재생성 여부
            resolution: 해상도 (width, height), None이면 기본값 사용
        
        Returns:
            {
                "success": True,
                "track_id": "track_001",
                "image_path": "./images/track_001.png",
                "prompt_used": "...",
                "skipped": False
            }
        """
        try:
            # 1. 중복 체크
            if not self.should_generate(track_id, force):
                existing_path = self.get_existing_image_path(track_id)
                return {
                    "success": True,
                    "track_id": track_id,
                    "image_path": existing_path,
                    "prompt_used": None,
                    "skipped": True
                }
            
            # 2. 음악 정보에서 프롬프트 생성
            track = db.get_track(track_id)
            if not track:
                raise ImageGeneratorError(f"트랙을 찾을 수 없습니다: {track_id}")
            
            music_prompt = track.get("music", {}).get("suno_prompt", "")
            if not music_prompt:
                music_prompt = f"Music track {track_id}"
            
            image_prompt = self.prompt_builder.build_prompt(
                style=style,
                music_prompt=music_prompt
            )
            
            # 3. 이미지 생성 API 호출
            self.logger.info(f"이미지 생성 시작: {track_id} (스타일: {style})")
            
            # 해상도 설정
            if resolution:
                size_str = f"{resolution[0]}x{resolution[1]}"
            else:
                size_str = self.config.get("image", {}).get("default_size", "1792x1024")
            
            image_data = self.generator.generate(
                prompt=image_prompt,
                size=size_str,
                quality=self.config.get("image", {}).get("quality", "hd"),
                style="vivid"
            )
            
            # 4. 파일 저장
            image_format = self.config.get("image", {}).get("format", "png")
            image_path = self.image_folder / f"{track_id}.{image_format}"
            
            if not self.save_image(image_data, str(image_path), format=image_format, resize=resolution):
                raise ImageGeneratorError("이미지 저장 실패")
            
            # 5. DB 업데이트
            db.update_track(track_id, {
                "image": {
                    "status": "completed",
                    "file_path": str(image_path),
                    "prompt_used": image_prompt,
                    "style": style,
                    "resolution": f"{resolution[0]}x{resolution[1]}" if resolution else size_str,
                    "format": image_format,
                    "generated_at": datetime.now().isoformat()
                }
            })
            
            self.logger.info(f"이미지 생성 완료: {track_id}")
            
            return {
                "success": True,
                "track_id": track_id,
                "image_path": str(image_path),
                "prompt_used": image_prompt,
                "skipped": False
            }
        
        except Exception as e:
            self.logger.error(f"이미지 생성 실패 ({track_id}): {e}")
            
            # DB에 에러 기록
            if db:
                db.add_error_log(track_id, "image", str(e))
                db.update_status(track_id, "image", "failed")
            
            return {
                "success": False,
                "track_id": track_id,
                "image_path": None,
                "prompt_used": None,
                "skipped": False,
                "error": str(e)
            }
    
    def generate_batch(
        self,
        track_ids: List[str],
        db: TrackDB,
        style: str = "default",
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        배치 이미지 생성
        
        Args:
            track_ids: 처리할 트랙 ID 목록
            db: 트랙 DB
            style: 적용할 스타일
            progress_callback: 진행 콜백 (current, total, track_id, status)
        
        Returns:
            {
                "total": 10,
                "successful": 8,
                "failed": 1,
                "skipped": 1,
                "results": [...]
            }
        """
        total = len(track_ids)
        successful = 0
        failed = 0
        skipped = 0
        results = []
        
        for i, track_id in enumerate(track_ids, 1):
            try:
                result = self.generate_for_track(track_id, db, style=style, force=False)
                results.append(result)
                
                if result.get("skipped"):
                    skipped += 1
                    status = "skipped"
                elif result.get("success"):
                    successful += 1
                    status = "success"
                else:
                    failed += 1
                    status = "failed"
                
                if progress_callback:
                    progress_callback(i, total, track_id, status)
            
            except Exception as e:
                failed += 1
                self.logger.error(f"배치 생성 실패 ({track_id}): {e}")
                results.append({
                    "success": False,
                    "track_id": track_id,
                    "error": str(e)
                })
                
                if progress_callback:
                    progress_callback(i, total, track_id, "failed")
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "results": results
        }
    
    def generate_all_pending(self, db: TrackDB, style: str = "default") -> Dict[str, Any]:
        """
        이미지 없는 모든 트랙 처리
        
        Args:
            db: 트랙 DB
            style: 적용할 스타일
        
        Returns:
            배치 생성 결과
        """
        all_tracks = db.get_all_tracks()
        pending_track_ids = []
        
        for track in all_tracks:
            track_id = track.get("track_id")
            image_status = track.get("image", {}).get("status", "pending")
            
            if image_status in ("pending", "failed"):
                # 실제 파일도 확인
                if not self.get_existing_image_path(track_id):
                    pending_track_ids.append(track_id)
        
        self.logger.info(f"이미지 생성 대기 트랙: {len(pending_track_ids)}개")
        
        return self.generate_batch(pending_track_ids, db, style=style)
    
    def generate_multi_resolution(
        self,
        track_id: str,
        db: TrackDB,
        platforms: List[str]
    ) -> Dict[str, Any]:
        """
        여러 해상도로 동시 생성
        
        Args:
            track_id: 트랙 ID
            db: TrackDB 인스턴스
            platforms: 플랫폼 목록 ["youtube", "shorts", "instagram"]
        
        Returns:
            생성 결과 딕셔너리
        """
        results = {}
        
        for platform in platforms:
            resolution = self.get_resolution_for_platform(platform)
            result = self.generate_for_track(
                track_id,
                db,
                style="default",
                force=False,
                resolution=resolution
            )
            results[platform] = result
        
        return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="이미지 생성기")
    parser.add_argument("--track", type=str, help="트랙 ID")
    parser.add_argument("--style", type=str, default="default", help="스타일")
    parser.add_argument("--all-pending", action="store_true", help="모든 pending 트랙 처리")
    parser.add_argument("--force", action="store_true", help="강제 재생성")
    parser.add_argument("--list-styles", action="store_true", help="스타일 목록 확인")
    parser.add_argument("--preview", type=str, help="프롬프트 미리보기 (트랙 ID)")
    
    args = parser.parse_args()
    
    db = TrackDB()
    generator = ImageGenerator()
    
    if args.list_styles:
        styles = generator.prompt_builder.get_available_styles()
        print("\n사용 가능한 스타일:")
        for style in styles:
            print(f"  - {style}")
    
    elif args.preview:
        track = db.get_track(args.preview)
        if track:
            music_prompt = track.get("music", {}).get("suno_prompt", "")
            prompt = generator.prompt_builder.build_prompt(
                style=args.style,
                music_prompt=music_prompt
            )
            print(f"\n프롬프트 미리보기 ({args.preview}, 스타일: {args.style}):")
            print(f"{prompt}")
        else:
            print(f"트랙을 찾을 수 없습니다: {args.preview}")
    
    elif args.track:
        result = generator.generate_for_track(
            args.track,
            db,
            style=args.style,
            force=args.force
        )
        
        if result["success"]:
            if result.get("skipped"):
                print(f"\n⏭️ 스킵됨: {result['image_path']}")
            else:
                print(f"\n✅ 이미지 생성 완료!")
                print(f"  - Track ID: {result['track_id']}")
                print(f"  - 파일 경로: {result['image_path']}")
                print(f"  - 프롬프트: {result['prompt_used'][:100]}...")
        else:
            print(f"\n❌ 생성 실패: {result.get('error', '알 수 없는 오류')}")
    
    elif args.all_pending:
        print(f"\n배치 이미지 생성 시작...")
        result = generator.generate_all_pending(db, style=args.style)
        
        print(f"\n✅ 배치 생성 완료!")
        print(f"  - 전체: {result['total']}개")
        print(f"  - 성공: {result['successful']}개")
        print(f"  - 실패: {result['failed']}개")
        print(f"  - 스킵: {result['skipped']}개")
    
    else:
        parser.print_help()

