"""
Suno API 클라이언트 모듈
음악 생성, 상태 확인, 다운로드 기능
"""

import time
import requests
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable
from datetime import datetime, timedelta
from config_manager import load_config, get_api_key, get_path
from db_manager import TrackDB
from logger import setup_logger


class SunoAPIError(Exception):
    """Suno API 관련 예외"""
    pass


class RateLimiter:
    """Rate Limit 관리 클래스"""
    
    def __init__(self, requests_per_minute: int = 10, daily_limit: int = 60):
        """
        RateLimiter 초기화
        
        Args:
            requests_per_minute: 분당 요청 수 제한
            daily_limit: 일일 요청 수 제한
        """
        self.rpm = requests_per_minute
        self.daily_limit = daily_limit
        self.request_times: List[float] = []
        self.daily_count = 0
        self.daily_reset_time = self._get_midnight()
    
    def _get_midnight(self) -> datetime:
        """다음 자정 시간 계산"""
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour >= 0:
            midnight += timedelta(days=1)
        return midnight
    
    def wait_if_needed(self) -> None:
        """필요시 대기"""
        now = time.time()
        
        # 일일 카운트 리셋 체크
        if datetime.now() >= self.daily_reset_time:
            self.reset_daily_count()
        
        # 일일 한도 체크
        if self.daily_count >= self.daily_limit:
            wait_seconds = (self.daily_reset_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                raise SunoAPIError(f"일일 한도 초과. {wait_seconds/3600:.1f}시간 후 재시도 가능합니다.")
        
        # 분당 요청 수 제한
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        if len(self.request_times) >= self.rpm:
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                time.sleep(wait_time)
                self.request_times = [t for t in self.request_times if now - t < 60]
    
    def can_make_request(self) -> bool:
        """요청 가능 여부"""
        # 일일 카운트 리셋 체크
        if datetime.now() >= self.daily_reset_time:
            self.reset_daily_count()
        
        return self.daily_count < self.daily_limit
    
    def record_request(self) -> None:
        """요청 기록"""
        self.request_times.append(time.time())
        self.daily_count += 1
    
    def reset_daily_count(self) -> None:
        """일일 카운트 리셋 (자정 기준)"""
        self.daily_count = 0
        self.daily_reset_time = self._get_midnight()


class SunoClient:
    """Suno API 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        SunoClient 초기화
        
        Args:
            api_key: API 키 (None이면 config에서 로드)
            config: 설정 딕셔너리 (None이면 자동 로드)
        """
        if config is None:
            config = load_config()
        
        if api_key is None:
            api_key = get_api_key('suno', config)
        
        self.api_key = api_key
        self.base_url = config.get("suno", {}).get("api_base_url", "https://api.suno.ai")
        self.model = config.get("suno", {}).get("model", "v3.5")
        self.timeout = config.get("suno", {}).get("timeout_seconds", 300)
        self.daily_limit = config.get("suno", {}).get("daily_limit", 60)
        
        self.session = requests.Session()
        self.rate_limiter = RateLimiter(
            requests_per_minute=10,
            daily_limit=self.daily_limit
        )
        
        self.logger = setup_logger("suno_client")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        인증 헤더 반환
        
        Returns:
            헤더 딕셔너리
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        공통 요청 래퍼 (에러 핸들링 포함)
        
        Args:
            method: HTTP 메서드 (GET, POST 등)
            endpoint: API 엔드포인트
            **kwargs: requests 요청 파라미터
        
        Returns:
            응답 JSON 딕셔너리
        
        Raises:
            SunoAPIError: API 오류 시
        """
        # Rate Limit 체크
        if not self.rate_limiter.can_make_request():
            raise SunoAPIError("일일 요청 한도에 도달했습니다.")
        
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.timeout,
                **kwargs
            )
            
            # Rate Limit 기록
            self.rate_limiter.record_request()
            
            # 429 Rate Limit 처리
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.logger.warning(f"Rate limit 도달. {retry_after}초 대기...")
                time.sleep(retry_after)
                return self._request(method, endpoint, **kwargs)
            
            # 401 인증 오류
            if response.status_code == 401:
                raise SunoAPIError("API 키가 유효하지 않습니다.")
            
            # 기타 오류
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.Timeout:
            raise SunoAPIError(f"요청 시간 초과 (timeout: {self.timeout}초)")
        except requests.exceptions.ConnectionError:
            raise SunoAPIError("네트워크 연결 실패")
        except requests.exceptions.RequestException as e:
            raise SunoAPIError(f"API 요청 실패: {str(e)}")
    
    def health_check(self) -> bool:
        """
        API 연결 상태 확인
        
        Returns:
            연결 성공 여부
        """
        try:
            # 실제 엔드포인트는 Suno API 문서에 따라 수정 필요
            # 예시: self._request("GET", "/health")
            # 현재는 API 키 유효성만 확인
            if not self.api_key or self.api_key == "YOUR_SUNO_API_KEY":
                self.logger.warning("API 키가 설정되지 않았습니다.")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Health check 실패: {e}")
            return False
    
    def generate_music(
        self,
        prompt: str,
        style: Optional[str] = None,
        duration: int = 120,
        instrumental: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        음악 생성 요청
        
        Args:
            prompt: 음악 설명 프롬프트
            style: 스타일 (celtic, lofi, jazz 등)
            duration: 목표 길이(초), 기본 120초
            instrumental: 보컬 제외 여부
        
        Returns:
            {
                "task_id": "suno_xxx_xxx",
                "status": "pending",
                "estimated_time": 60
            }
        
        Raises:
            SunoAPIError: API 오류 시
        """
        # 프롬프트 검증
        if not prompt or len(prompt.strip()) == 0:
            raise SunoAPIError("프롬프트가 비어있습니다.")
        
        # 요청 페이로드 구성
        payload = {
            "prompt": prompt,
            "model": self.model,
            "duration": duration,
            "instrumental": instrumental,
            "make_instrumental": instrumental
        }
        
        if style:
            payload["style"] = style
        
        payload.update(kwargs)
        
        try:
            # 실제 엔드포인트는 Suno API 문서에 따라 수정 필요
            # 예시: response = self._request("POST", "/v1/generate", json=payload)
            # 현재는 구조만 구현
            self.logger.info(f"음악 생성 요청: {prompt[:50]}...")
            
            # 실제 API 호출 (엔드포인트는 실제 문서 확인 필요)
            # response = self._request("POST", "/v1/generate", json=payload)
            
            # 임시 응답 (실제 API 연동 시 제거)
            return {
                "task_id": f"suno_{int(time.time())}",
                "status": "pending",
                "estimated_time": 60
            }
        
        except SunoAPIError:
            raise
        except Exception as e:
            raise SunoAPIError(f"음악 생성 요청 실패: {str(e)}")
    
    def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        단일 상태 확인
        
        Args:
            task_id: 작업 ID
        
        Returns:
            {
                "task_id": "suno_xxx_xxx",
                "status": "processing" | "completed" | "failed",
                "progress": 75,
                "audio_url": null | "https://...",
                "error": null | "error message"
            }
        """
        try:
            # 실제 엔드포인트는 Suno API 문서에 따라 수정 필요
            # 예시: response = self._request("GET", f"/v1/status/{task_id}")
            
            # 임시 응답 (실제 API 연동 시 제거)
            return {
                "task_id": task_id,
                "status": "processing",
                "progress": 0,
                "audio_url": None,
                "error": None
            }
        
        except Exception as e:
            return {
                "task_id": task_id,
                "status": "failed",
                "progress": 0,
                "audio_url": None,
                "error": str(e)
            }
    
    def wait_for_completion(
        self,
        task_id: str,
        poll_interval: int = 10,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        완료될 때까지 대기
        
        Args:
            task_id: 작업 ID
            poll_interval: 폴링 간격(초)
            timeout: 최대 대기 시간(초)
        
        Returns:
            완료된 작업 정보 (audio_url 포함)
        
        Raises:
            TimeoutError: 타임아웃 초과
            SunoAPIError: 생성 실패
        """
        start_time = time.time()
        
        while True:
            status = self.check_status(task_id)
            
            if status["status"] == "completed":
                if not status.get("audio_url"):
                    raise SunoAPIError("완료되었지만 audio_url이 없습니다.")
                return status
            
            if status["status"] == "failed":
                error_msg = status.get("error", "알 수 없는 오류")
                raise SunoAPIError(f"음악 생성 실패: {error_msg}")
            
            # 타임아웃 체크
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"타임아웃 초과 ({timeout}초)")
            
            # 진행률 로깅
            progress = status.get("progress", 0)
            self.logger.info(f"작업 {task_id} 진행 중... {progress}%")
            
            time.sleep(poll_interval)
    
    def download_audio(
        self,
        audio_url: str,
        save_path: str,
        chunk_size: int = 8192
    ) -> bool:
        """
        오디오 파일 다운로드
        
        Args:
            audio_url: 다운로드 URL
            save_path: 저장 경로 (예: ./music/track_001.mp3)
            chunk_size: 다운로드 청크 크기
        
        Returns:
            성공 여부
        """
        try:
            save_path_obj = Path(save_path)
            save_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"오디오 다운로드 시작: {audio_url}")
            
            response = self.session.get(audio_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path_obj, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (chunk_size * 10) == 0:  # 10청크마다 로깅
                                self.logger.debug(f"다운로드 진행: {progress:.1f}%")
            
            self.logger.info(f"다운로드 완료: {save_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"다운로드 실패: {e}")
            return False
    
    def generate_track_id(self, prefix: str = "track") -> str:
        """
        새 트랙 ID 생성
        기존 파일 확인 후 다음 번호 부여
        
        Args:
            prefix: 트랙 ID 접두사
        
        Returns:
            트랙 ID (예: track_001)
        """
        config = load_config()
        music_folder = Path(get_path('music_folder', config))
        music_folder.mkdir(parents=True, exist_ok=True)
        
        # 기존 파일에서 최대 번호 찾기
        max_num = 0
        for file_path in music_folder.glob(f"{prefix}_*.mp3"):
            try:
                num_str = file_path.stem.split('_')[1]
                num = int(num_str)
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                continue
        
        # DB에서도 확인
        db = TrackDB()
        all_tracks = db.get_all_tracks()
        for track in all_tracks:
            track_id = track.get("track_id", "")
            if track_id.startswith(prefix + "_"):
                try:
                    num_str = track_id.split('_')[1]
                    num = int(num_str)
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    continue
        
        # 다음 번호 생성
        next_num = max_num + 1
        return f"{prefix}_{next_num:03d}"
    
    def create_track(
        self,
        prompt: str,
        style: str = "default",
        db: Optional[TrackDB] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        전체 음악 생성 플로우 실행
        
        Args:
            prompt: 음악 프롬프트
            style: 스타일
            db: TrackDB 인스턴스 (None이면 새로 생성)
            **kwargs: 추가 파라미터
        
        Returns:
            {
                "success": True,
                "track_id": "track_015",
                "file_path": "./music/track_015.mp3",
                "duration": 185.5,
                "suno_task_id": "suno_xxx_xxx"
            }
        """
        if db is None:
            db = TrackDB()
        
        track_id = None  # 초기화 (에러 처리 시 사용)
        
        try:
            # 1. track_id 생성
            track_id = self.generate_track_id()
            self.logger.info(f"새 트랙 ID 생성: {track_id}")
            
            # 2. 음악 생성 요청
            result = self.generate_music(prompt, style=style, **kwargs)
            suno_task_id = result["task_id"]
            
            # DB에 트랙 추가 (pending 상태)
            db.add_track(track_id)
            db.update_track(track_id, {
                "music": {
                    "status": "processing",
                    "suno_task_id": suno_task_id,
                    "suno_prompt": prompt
                }
            })
            
            # 3. 완료 대기
            self.logger.info(f"음악 생성 대기 중... (task_id: {suno_task_id})")
            completed = self.wait_for_completion(suno_task_id)
            audio_url = completed["audio_url"]
            
            # 4. 파일 다운로드
            config = load_config()
            music_folder = Path(get_path('music_folder', config))
            file_path = music_folder / f"{track_id}.mp3"
            
            if not self.download_audio(audio_url, str(file_path)):
                raise SunoAPIError("오디오 다운로드 실패")
            
            # 5. DB 업데이트
            db.update_track(track_id, {
                "music": {
                    "status": "completed",
                    "file_path": str(file_path)
                }
            })
            
            # 메타데이터 분석 (duration 등)은 metadata.py에서 처리
            # Task 6에서 구현 예정이므로 임시로 스킵
            # from metadata import get_audio_duration
            # try:
            #     duration = get_audio_duration(str(file_path))
            #     db.update_track(track_id, {
            #         "music": {
            #             "duration_seconds": duration
            #         }
            #     })
            # except Exception as e:
            #     self.logger.warning(f"메타데이터 분석 실패: {e}")
            
            self.logger.info(f"트랙 생성 완료: {track_id}")
            
            return {
                "success": True,
                "track_id": track_id,
                "file_path": str(file_path),
                "duration": db.get_track(track_id).get("music", {}).get("duration_seconds"),
                "suno_task_id": suno_task_id
            }
        
        except Exception as e:
            self.logger.error(f"트랙 생성 실패: {e}")
            if db and track_id:
                db.add_error_log(track_id, "music", str(e))
                db.update_status(track_id, "music", "failed")
            raise
    
    def create_batch(
        self,
        prompts: List[Dict[str, Any]],
        db: Optional[TrackDB] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        배치 음악 생성
        
        Args:
            prompts: [{"prompt": "...", "style": "celtic"}, ...]
            db: 트랙 DB
            progress_callback: 진행 콜백 함수 (current, total, track_id)
        
        Returns:
            {
                "total_requested": 10,
                "successful": 8,
                "failed": 2,
                "tracks": [...]
            }
        """
        if db is None:
            db = TrackDB()
        
        total = len(prompts)
        successful = 0
        failed = 0
        tracks = []
        
        for i, prompt_data in enumerate(prompts, 1):
            prompt = prompt_data.get("prompt", "")
            style = prompt_data.get("style", "default")
            
            try:
                result = self.create_track(prompt, style=style, db=db)
                tracks.append(result)
                successful += 1
                
                if progress_callback:
                    progress_callback(i, total, result["track_id"], "success")
            
            except Exception as e:
                failed += 1
                self.logger.error(f"배치 생성 실패 ({i}/{total}): {e}")
                
                if progress_callback:
                    progress_callback(i, total, None, "failed")
        
        return {
            "total_requested": total,
            "successful": successful,
            "failed": failed,
            "tracks": tracks
        }
    
    def get_remaining_quota(self) -> int:
        """
        오늘 남은 생성 가능 개수
        
        Returns:
            남은 할당량
        """
        return max(0, self.daily_limit - self.rate_limiter.daily_count)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Suno API 클라이언트")
    parser.add_argument("--generate", type=str, help="음악 생성 프롬프트")
    parser.add_argument("--style", type=str, help="스타일 (celtic, lofi 등)")
    parser.add_argument("--batch", type=int, help="배치 생성 개수")
    parser.add_argument("--quota", action="store_true", help="남은 할당량 확인")
    parser.add_argument("--status", type=str, help="작업 상태 확인 (task_id)")
    
    args = parser.parse_args()
    
    client = SunoClient()
    
    if args.generate:
        try:
            result = client.create_track(args.generate, style=args.style or "default")
            print(f"\n✅ 음악 생성 완료!")
            print(f"  - Track ID: {result['track_id']}")
            print(f"  - 파일 경로: {result['file_path']}")
            print(f"  - Suno Task ID: {result['suno_task_id']}")
        except Exception as e:
            print(f"\n❌ 생성 실패: {e}")
    
    elif args.batch:
        print(f"\n배치 생성 시작: {args.batch}곡")
        # 배치 생성 로직 (프롬프트 생성 필요)
        print("배치 생성 기능은 프롬프트 템플릿과 함께 사용하세요.")
    
    elif args.quota:
        remaining = client.get_remaining_quota()
        print(f"\n남은 할당량: {remaining}/{client.daily_limit}")
    
    elif args.status:
        status = client.check_status(args.status)
        print(f"\n작업 상태: {args.status}")
        print(f"  - 상태: {status['status']}")
        print(f"  - 진행률: {status.get('progress', 0)}%")
        if status.get('audio_url'):
            print(f"  - 오디오 URL: {status['audio_url']}")
    
    else:
        parser.print_help()

