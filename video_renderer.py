"""
FFmpeg 영상 렌더링 모듈
이미지 + 음악 → 영상 생성
"""

import os
import subprocess
import shutil
import time
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable, Tuple
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

from config_manager import load_config, get_path
from db_manager import TrackDB
from metadata import get_audio_duration, seconds_to_ffmpeg_time, seconds_to_mmss
from logger import setup_logger


class FFmpegError(Exception):
    """FFmpeg 관련 예외"""
    pass


# 해상도 프리셋
RESOLUTION_PRESETS = {
    "youtube_hd": (1920, 1080),
    "youtube_4k": (3840, 2160),
    "shorts": (1080, 1920),
    "instagram_square": (1080, 1080),
    "instagram_portrait": (1080, 1350),
}

# 품질 프리셋
QUALITY_PRESETS = {
    "fast": {"crf": 28, "preset": "ultrafast"},
    "normal": {"crf": 23, "preset": "medium"},
    "high": {"crf": 18, "preset": "slow"},
}


class FFmpegRenderer:
    """FFmpeg 영상 렌더러"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        FFmpegRenderer 초기화
        
        Args:
            config: 설정 딕셔너리 (None이면 자동 로드)
        """
        if config is None:
            config = load_config()
        
        self.config = config
        video_config = config.get("video", {})
        
        self.ffmpeg_path = video_config.get("ffmpeg_path", "ffmpeg")
        self.codec_video = video_config.get("codec_video", "libx264")
        self.codec_audio = video_config.get("codec_audio", "aac")
        self.audio_bitrate = video_config.get("audio_bitrate", "192k")
        self.default_resolution = video_config.get("default_resolution", "1920x1080")
        self.vertical_resolution = video_config.get("vertical_resolution", "1080x1920")
        self.thumbnail_enabled = video_config.get("thumbnail_enabled", True)
        self.thumbnail_time = video_config.get("thumbnail_time", "00:00:05")
        
        # 품질 설정
        self.quality_preset = "normal"
        self.crf = QUALITY_PRESETS["normal"]["crf"]
        self.preset = QUALITY_PRESETS["normal"]["preset"]
        self.two_pass = video_config.get("two_pass_enabled", False)  # 2-pass 인코딩 옵션
        
        # 경로 설정
        self.video_folder = Path(get_path('video_folder', config))
        self.video_folder.mkdir(parents=True, exist_ok=True)
        
        self.thumbnail_folder = Path(get_path('thumbnail_folder', config))
        self.thumbnail_folder.mkdir(parents=True, exist_ok=True)
        
        self.logger = setup_logger("video_renderer")
    
    def check_ffmpeg_installed(self) -> bool:
        """
        FFmpeg 설치 확인
        
        Returns:
            설치 여부
        """
        return shutil.which(self.ffmpeg_path) is not None
    
    def get_ffmpeg_version(self) -> Optional[str]:
        """
        FFmpeg 버전 반환
        
        Returns:
            버전 문자열 또는 None
        """
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # 첫 번째 줄에서 버전 추출
                first_line = result.stdout.split('\n')[0]
                # "ffmpeg version 6.0" 형식에서 버전 추출
                if "version" in first_line:
                    parts = first_line.split("version")
                    if len(parts) > 1:
                        version = parts[1].strip().split()[0]
                        return version
            return None
        except Exception as e:
            self.logger.error(f"FFmpeg 버전 확인 실패: {e}")
            return None
    
    def check_codec_support(self, codec: str) -> bool:
        """
        특정 코덱 지원 여부 확인
        
        Args:
            codec: 코덱 이름 (예: "libx264", "aac")
        
        Returns:
            지원 여부
        """
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-codecs"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return codec in result.stdout
            return False
        except Exception as e:
            self.logger.error(f"코덱 확인 실패: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        전체 환경 체크
        
        Returns:
            {
                "installed": True,
                "version": "6.0",
                "libx264": True,
                "aac": True,
                "ready": True
            }
        """
        installed = self.check_ffmpeg_installed()
        version = self.get_ffmpeg_version() if installed else None
        libx264_support = self.check_codec_support("libx264") if installed else False
        aac_support = self.check_codec_support("aac") if installed else False
        
        ready = installed and libx264_support and aac_support
        
        return {
            "installed": installed,
            "version": version,
            "libx264": libx264_support,
            "aac": aac_support,
            "ready": ready
        }
    
    def _build_ffmpeg_command(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        duration: Optional[float] = None,
        resolution: Optional[Tuple[int, int]] = None,
        scale_filter: Optional[str] = None,
        video_filter: Optional[str] = None,
        two_pass: bool = False,
        pass_number: Optional[int] = None,
        pass_logfile: Optional[str] = None,
        **kwargs
    ) -> List[str]:
        """
        FFmpeg 명령어 리스트 생성
        
        Args:
            image_path: 이미지 파일 경로
            audio_path: 음악 파일 경로
            output_path: 출력 영상 경로
            duration: 영상 길이(초)
            resolution: 해상도 (width, height)
            scale_filter: 스케일 필터 문자열
            video_filter: 비디오 필터 문자열
            two_pass: 2-pass 인코딩 여부
            pass_number: 패스 번호 (1 또는 2, two_pass=True일 때만 사용)
            pass_logfile: 패스 로그 파일 경로 (two_pass=True일 때만 사용)
        
        Returns:
            FFmpeg 명령어 리스트
        """
        cmd = [self.ffmpeg_path]
        
        # 입력 파일
        cmd.extend(["-loop", "1", "-i", image_path])
        cmd.extend(["-i", audio_path])
        
        # 비디오 코덱 및 설정
        cmd.extend(["-c:v", self.codec_video])
        cmd.extend(["-tune", "stillimage"])
        
        # 2-pass 인코딩 설정
        if two_pass and pass_number is not None:
            if pass_number == 1:
                # 첫 번째 패스: 비트레이트 분석만 수행
                cmd.extend(["-b:v", "0"])  # 비트레이트는 두 번째 패스에서 결정
                cmd.extend(["-pass", "1"])
                cmd.extend(["-passlogfile", pass_logfile])
                cmd.extend(["-f", "null"])  # 첫 번째 패스는 출력 없음
            elif pass_number == 2:
                # 두 번째 패스: 실제 인코딩
                cmd.extend(["-crf", str(self.crf)])
                cmd.extend(["-preset", self.preset])
                cmd.extend(["-pass", "2"])
                cmd.extend(["-passlogfile", pass_logfile])
        else:
            # 일반 인코딩 (1-pass)
            cmd.extend(["-crf", str(self.crf)])
            cmd.extend(["-preset", self.preset])
        
        # 해상도 설정
        if resolution:
            width, height = resolution
            cmd.extend(["-s", f"{width}x{height}"])
        
        # 필터 설정
        filters = []
        if scale_filter:
            filters.append(scale_filter)
        if video_filter:
            filters.append(video_filter)
        
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        
        # 오디오 코덱 및 설정
        cmd.extend(["-c:a", self.codec_audio])
        cmd.extend(["-b:a", self.audio_bitrate])
        
        # 길이 설정
        if duration:
            cmd.extend(["-t", str(duration)])
        
        # 출력 설정
        cmd.extend(["-shortest"])  # 오디오 길이에 맞춤
        cmd.extend(["-pix_fmt", "yuv420p"])  # 호환성
        
        # 첫 번째 패스가 아니면 출력 파일 지정
        if not (two_pass and pass_number == 1):
            cmd.extend(["-y"])  # 덮어쓰기
            cmd.append(output_path)
        else:
            # 첫 번째 패스는 /dev/null 또는 NUL로 출력
            if os.name == 'nt':  # Windows
                cmd.append("NUL")
            else:  # Unix/Linux
                cmd.append("/dev/null")
        
        return cmd
    
    def _execute_ffmpeg(self, command: List[str], suppress_output: bool = False) -> Tuple[bool, str]:
        """
        FFmpeg 실행
        
        Args:
            command: FFmpeg 명령어 리스트
            suppress_output: 첫 번째 패스 등 출력을 숨길지 여부
        
        Returns:
            (성공여부, 에러메시지 또는 빈 문자열)
        """
        try:
            self.logger.debug(f"FFmpeg 명령 실행: {' '.join(command)}")
            
            # 첫 번째 패스는 출력을 숨김
            stdout_target = subprocess.DEVNULL if suppress_output else subprocess.PIPE
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                stdout=stdout_target,
                stderr=subprocess.PIPE,
                timeout=600  # 10분 타임아웃
            )
            
            if result.returncode == 0:
                return True, ""
            else:
                error_msg = result.stderr or result.stdout or "알 수 없는 오류"
                return False, error_msg
        
        except subprocess.TimeoutExpired:
            return False, "FFmpeg 실행 시간 초과 (10분)"
        except FileNotFoundError:
            return False, f"FFmpeg를 찾을 수 없습니다: {self.ffmpeg_path}"
        except Exception as e:
            return False, f"FFmpeg 실행 실패: {str(e)}"
    
    def render_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        duration: Optional[float] = None,
        use_two_pass: bool = None
    ) -> bool:
        """
        기본 영상 렌더링
        
        Args:
            image_path: 이미지 파일 경로
            audio_path: 음악 파일 경로
            output_path: 출력 영상 경로
            duration: 영상 길이(초), None이면 음악 길이 사용
            use_two_pass: 2-pass 인코딩 사용 여부 (None이면 self.two_pass 사용)
        
        Returns:
            성공 여부
        """
        if not os.path.exists(image_path):
            raise FFmpegError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        if not os.path.exists(audio_path):
            raise FFmpegError(f"음악 파일을 찾을 수 없습니다: {audio_path}")
        
        # 길이 확인
        if duration is None:
            try:
                duration = get_audio_duration(audio_path)
            except Exception as e:
                raise FFmpegError(f"음악 길이 분석 실패: {e}")
        
        # 출력 폴더 생성
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # 2-pass 인코딩 여부 결정
        if use_two_pass is None:
            use_two_pass = self.two_pass
        
        if use_two_pass:
            # 2-pass 인코딩
            pass_logfile = str(output_path_obj.with_suffix('.log'))
            
            # 첫 번째 패스: 비트레이트 분석
            self.logger.info(f"2-pass 인코딩: 첫 번째 패스 시작...")
            command_pass1 = self._build_ffmpeg_command(
                image_path,
                audio_path,
                output_path,
                duration=duration,
                two_pass=True,
                pass_number=1,
                pass_logfile=pass_logfile
            )
            
            success, error_msg = self._execute_ffmpeg(command_pass1, suppress_output=True)
            if not success:
                # 로그 파일 정리
                if os.path.exists(pass_logfile):
                    try:
                        os.remove(pass_logfile)
                    except:
                        pass
                raise FFmpegError(f"2-pass 첫 번째 패스 실패: {error_msg}")
            
            # 두 번째 패스: 실제 인코딩
            self.logger.info(f"2-pass 인코딩: 두 번째 패스 시작...")
            command_pass2 = self._build_ffmpeg_command(
                image_path,
                audio_path,
                output_path,
                duration=duration,
                two_pass=True,
                pass_number=2,
                pass_logfile=pass_logfile
            )
            
            success, error_msg = self._execute_ffmpeg(command_pass2)
            if not success:
                raise FFmpegError(f"2-pass 두 번째 패스 실패: {error_msg}")
            
            # 로그 파일 정리
            if os.path.exists(pass_logfile):
                try:
                    os.remove(pass_logfile)
                except:
                    pass
            
            self.logger.info(f"2-pass 영상 렌더링 완료: {output_path}")
        else:
            # 1-pass 인코딩
            command = self._build_ffmpeg_command(
                image_path,
                audio_path,
                output_path,
                duration=duration
            )
            
            success, error_msg = self._execute_ffmpeg(command)
            
            if not success:
                raise FFmpegError(f"영상 렌더링 실패: {error_msg}")
            
            self.logger.info(f"영상 렌더링 완료: {output_path}")
        
        return True
    
    def _get_scale_filter(
        self,
        input_size: Tuple[int, int],
        output_size: Tuple[int, int],
        mode: str = "fit"
    ) -> str:
        """
        FFmpeg scale 필터 문자열 생성
        
        Args:
            input_size: 입력 이미지 크기 (width, height)
            output_size: 출력 영상 크기 (width, height)
            mode: "fit" | "fill" | "stretch"
        
        Returns:
            필터 문자열
        """
        iw, ih = input_size
        ow, oh = output_size
        
        if mode == "stretch":
            # 비율 무시, 늘리기
            return f"scale={ow}:{oh}"
        
        elif mode == "fill":
            # 비율 유지, 크롭
            return f"scale={ow}:{oh}:force_original_aspect_ratio=increase,crop={ow}:{oh}"
        
        else:  # fit (기본값)
            # 비율 유지, 패딩 추가
            return f"scale={ow}:{oh}:force_original_aspect_ratio=decrease,pad={ow}:{oh}:(ow-iw)/2:(oh-ih)/2:color=black"
    
    def render_with_resolution(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        resolution: Tuple[int, int] = (1920, 1080),
        scale_mode: str = "fit"
    ) -> bool:
        """
        해상도 지정 렌더링
        
        Args:
            image_path: 이미지 파일 경로
            audio_path: 음악 파일 경로
            output_path: 출력 영상 경로
            resolution: (width, height)
            scale_mode: "fit" | "fill" | "stretch"
        
        Returns:
            성공 여부
        """
        if not os.path.exists(image_path):
            raise FFmpegError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        if not os.path.exists(audio_path):
            raise FFmpegError(f"음악 파일을 찾을 수 없습니다: {audio_path}")
        
        # 이미지 크기 확인
        try:
            with Image.open(image_path) as img:
                input_size = img.size
        except Exception as e:
            raise FFmpegError(f"이미지 크기 확인 실패: {e}")
        
        # 길이 확인
        try:
            duration = get_audio_duration(audio_path)
        except Exception as e:
            raise FFmpegError(f"음악 길이 분석 실패: {e}")
        
        # 스케일 필터 생성
        scale_filter = self._get_scale_filter(input_size, resolution, scale_mode)
        
        # 출력 폴더 생성
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg 명령 생성 및 실행
        command = self._build_ffmpeg_command(
            image_path,
            audio_path,
            output_path,
            duration=duration,
            resolution=resolution,
            scale_filter=scale_filter
        )
        
        success, error_msg = self._execute_ffmpeg(command)
        
        if not success:
            raise FFmpegError(f"영상 렌더링 실패: {error_msg}")
        
        self.logger.info(f"영상 렌더링 완료: {output_path} (해상도: {resolution[0]}x{resolution[1]})")
        return True
    
    def _get_ken_burns_filter(
        self,
        duration: float,
        effect_type: str,
        zoom_start: float,
        zoom_end: float,
        resolution: Tuple[int, int] = (1920, 1080)
    ) -> str:
        """
        Ken Burns FFmpeg 필터 생성
        
        Args:
            duration: 영상 길이(초)
            effect_type: "zoom_in" | "zoom_out" | "pan_left" | "pan_right"
            zoom_start: 시작 줌 레벨
            zoom_end: 끝 줌 레벨
            resolution: 해상도 (width, height)
        
        Returns:
            필터 문자열
        """
        width, height = resolution
        frames = int(duration * 30)  # 30fps 가정
        
        if effect_type == "zoom_in":
            # 줌 인: zoom_start → zoom_end
            zoom_rate = (zoom_end - zoom_start) / frames
            return f"zoompan=z='min(zoom+{zoom_rate:.6f},{zoom_end})':d={frames}:s={width}x{height}"
        
        elif effect_type == "zoom_out":
            # 줌 아웃: zoom_end → zoom_start
            zoom_rate = (zoom_start - zoom_end) / frames
            return f"zoompan=z='max(zoom+{zoom_rate:.6f},{zoom_start})':d={frames}:s={width}x{height}"
        
        elif effect_type == "pan_left":
            # 왼쪽으로 팬 (줌 인과 함께)
            zoom_rate = (zoom_end - zoom_start) / frames
            x_rate = -width * 0.1 / frames  # 왼쪽으로 이동
            return f"zoompan=z='min(zoom+{zoom_rate:.6f},{zoom_end})':x='if(lte(zoom,{zoom_start}),iw/2,iw/2-iw*(zoom-{zoom_start})*{x_rate})':y='ih/2':d={frames}:s={width}x{height}"
        
        elif effect_type == "pan_right":
            # 오른쪽으로 팬 (줌 인과 함께)
            zoom_rate = (zoom_end - zoom_start) / frames
            x_rate = width * 0.1 / frames  # 오른쪽으로 이동
            return f"zoompan=z='min(zoom+{zoom_rate:.6f},{zoom_end})':x='if(lte(zoom,{zoom_start}),iw/2,iw/2+iw*(zoom-{zoom_start})*{x_rate})':y='ih/2':d={frames}:s={width}x{height}"
        
        else:
            # 기본: 줌 인
            zoom_rate = (zoom_end - zoom_start) / frames
            return f"zoompan=z='min(zoom+{zoom_rate:.6f},{zoom_end})':d={frames}:s={width}x{height}"
    
    def render_with_ken_burns(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        effect_type: str = "zoom_in",
        zoom_start: float = 1.0,
        zoom_end: float = 1.2,
        resolution: Tuple[int, int] = (1920, 1080)
    ) -> bool:
        """
        Ken Burns 효과 적용 렌더링
        
        Args:
            image_path: 이미지 파일 경로
            audio_path: 음악 파일 경로
            output_path: 출력 영상 경로
            effect_type: "zoom_in" | "zoom_out" | "pan_left" | "pan_right"
            zoom_start: 시작 줌 레벨 (1.0 = 원본)
            zoom_end: 끝 줌 레벨
            resolution: 해상도 (width, height)
        
        Returns:
            성공 여부
        """
        if not os.path.exists(image_path):
            raise FFmpegError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        if not os.path.exists(audio_path):
            raise FFmpegError(f"음악 파일을 찾을 수 없습니다: {audio_path}")
        
        # 길이 확인
        try:
            duration = get_audio_duration(audio_path)
        except Exception as e:
            raise FFmpegError(f"음악 길이 분석 실패: {e}")
        
        # Ken Burns 필터 생성
        ken_burns_filter = self._get_ken_burns_filter(
            duration,
            effect_type,
            zoom_start,
            zoom_end,
            resolution
        )
        
        # 출력 폴더 생성
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg 명령 생성 및 실행
        command = self._build_ffmpeg_command(
            image_path,
            audio_path,
            output_path,
            duration=duration,
            resolution=resolution,
            video_filter=ken_burns_filter
        )
        
        success, error_msg = self._execute_ffmpeg(command)
        
        if not success:
            raise FFmpegError(f"Ken Burns 렌더링 실패: {error_msg}")
        
        self.logger.info(f"Ken Burns 렌더링 완료: {output_path}")
        return True
    
    def _get_drawtext_filter(
        self,
        text: str,
        position: str,
        font_size: int,
        font_color: str,
        duration: float,
        fade_in: float,
        fade_out: float,
        resolution: Tuple[int, int] = (1920, 1080)
    ) -> str:
        """
        FFmpeg drawtext 필터 생성
        
        Args:
            text: 표시할 텍스트
            position: "top" | "bottom" | "center"
            font_size: 폰트 크기
            font_color: 색상 (white, black, #RRGGBB)
            duration: 영상 길이(초)
            fade_in: 페이드 인 시간(초)
            fade_out: 페이드 아웃 시간(초)
            resolution: 해상도 (width, height)
        
        Returns:
            필터 문자열
        """
        width, height = resolution
        
        # 위치 계산
        if position == "top":
            x = "(w-text_w)/2"
            y = f"{font_size + 20}"
        elif position == "bottom":
            x = "(w-text_w)/2"
            y = f"h-{font_size + 20}"
        else:  # center
            x = "(w-text_w)/2"
            y = "(h-text_h)/2"
        
        # 색상 처리
        if font_color.startswith("#"):
            color = font_color
        elif font_color.lower() == "white":
            color = "white"
        elif font_color.lower() == "black":
            color = "black"
        else:
            color = "white"
        
        # 텍스트 이스케이프
        text_escaped = text.replace("'", "\\'").replace(":", "\\:")
        
        # 페이드 효과
        fade_in_frames = int(fade_in * 30)
        fade_out_start = duration - fade_out
        fade_out_frames = int(fade_out * 30)
        
        if fade_in > 0 or fade_out > 0:
            alpha_expr = f"if(lt(t,{fade_in}),t/{fade_in},if(gt(t,{fade_out_start}),1-(t-{fade_out_start})/{fade_out},1))"
            return f"drawtext=text='{text_escaped}':fontsize={font_size}:fontcolor={color}:x={x}:y={y}:alpha='{alpha_expr}'"
        else:
            return f"drawtext=text='{text_escaped}':fontsize={font_size}:fontcolor={color}:x={x}:y={y}"
    
    def render_with_text(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        text: str,
        position: str = "bottom",
        font_size: int = 48,
        font_color: str = "white",
        fade_in: float = 1.0,
        fade_out: float = 1.0,
        resolution: Tuple[int, int] = (1920, 1080)
    ) -> bool:
        """
        텍스트 오버레이 렌더링
        
        Args:
            image_path: 이미지 파일 경로
            audio_path: 음악 파일 경로
            output_path: 출력 영상 경로
            text: 표시할 텍스트
            position: "top" | "bottom" | "center"
            font_size: 폰트 크기
            font_color: 색상 (white, black, #RRGGBB)
            fade_in: 페이드 인 시간(초)
            fade_out: 페이드 아웃 시간(초)
            resolution: 해상도 (width, height)
        
        Returns:
            성공 여부
        """
        if not os.path.exists(image_path):
            raise FFmpegError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        if not os.path.exists(audio_path):
            raise FFmpegError(f"음악 파일을 찾을 수 없습니다: {audio_path}")
        
        # 길이 확인
        try:
            duration = get_audio_duration(audio_path)
        except Exception as e:
            raise FFmpegError(f"음악 길이 분석 실패: {e}")
        
        # 텍스트 필터 생성
        text_filter = self._get_drawtext_filter(
            text,
            position,
            font_size,
            font_color,
            duration,
            fade_in,
            fade_out,
            resolution
        )
        
        # 출력 폴더 생성
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg 명령 생성 및 실행
        command = self._build_ffmpeg_command(
            image_path,
            audio_path,
            output_path,
            duration=duration,
            resolution=resolution,
            video_filter=text_filter
        )
        
        success, error_msg = self._execute_ffmpeg(command)
        
        if not success:
            raise FFmpegError(f"텍스트 오버레이 렌더링 실패: {error_msg}")
        
        self.logger.info(f"텍스트 오버레이 렌더링 완료: {output_path}")
        return True
    
    def generate_thumbnail(
        self,
        video_path: str,
        output_path: str,
        timestamp: str = "00:00:05",
        size: Tuple[int, int] = (1280, 720)
    ) -> bool:
        """
        영상에서 썸네일 추출
        
        Args:
            video_path: 영상 경로
            output_path: 썸네일 저장 경로
            timestamp: 추출 시점 (HH:MM:SS)
            size: 썸네일 크기
        
        Returns:
            성공 여부
        """
        if not os.path.exists(video_path):
            raise FFmpegError(f"영상 파일을 찾을 수 없습니다: {video_path}")
        
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        width, height = size
        
        cmd = [
            self.ffmpeg_path,
            "-i", video_path,
            "-ss", timestamp,
            "-vframes", "1",
            "-vf", f"scale={width}:{height}",
            "-y",
            output_path
        ]
        
        success, error_msg = self._execute_ffmpeg(cmd)
        
        if not success:
            raise FFmpegError(f"썸네일 추출 실패: {error_msg}")
        
        self.logger.info(f"썸네일 추출 완료: {output_path}")
        return True
    
    def generate_thumbnail_from_image(
        self,
        image_path: str,
        output_path: str,
        size: Tuple[int, int] = (1280, 720),
        add_play_button: bool = False
    ) -> bool:
        """
        원본 이미지에서 썸네일 생성
        
        Args:
            image_path: 이미지 파일 경로
            output_path: 썸네일 저장 경로
            size: 썸네일 크기
            add_play_button: 재생 버튼 오버레이 추가 여부
        
        Returns:
            성공 여부
        """
        if not os.path.exists(image_path):
            raise FFmpegError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        
        try:
            with Image.open(image_path) as img:
                # 리사이즈
                img_resized = img.resize(size, Image.Resampling.LANCZOS)
                
                # 재생 버튼 추가 (선택)
                if add_play_button:
                    draw = ImageDraw.Draw(img_resized)
                    # 중앙에 원형 재생 버튼 그리기
                    center_x, center_y = size[0] // 2, size[1] // 2
                    button_radius = min(size) // 8
                    
                    # 반투명 원
                    draw.ellipse(
                        [center_x - button_radius, center_y - button_radius,
                         center_x + button_radius, center_y + button_radius],
                        fill=(255, 255, 255, 200),
                        outline=(255, 255, 255, 255),
                        width=3
                    )
                    
                    # 삼각형 재생 아이콘
                    triangle_size = button_radius // 2
                    triangle_points = [
                        (center_x - triangle_size // 2, center_y - triangle_size),
                        (center_x - triangle_size // 2, center_y + triangle_size),
                        (center_x + triangle_size, center_y)
                    ]
                    draw.polygon(triangle_points, fill=(0, 0, 0, 255))
                
                # 저장
                output_path_obj = Path(output_path)
                output_path_obj.parent.mkdir(parents=True, exist_ok=True)
                
                if output_path_obj.suffix.lower() in ['.jpg', '.jpeg']:
                    img_resized.save(output_path_obj, "JPEG", quality=95)
                else:
                    img_resized.save(output_path_obj, "PNG")
            
            self.logger.info(f"썸네일 생성 완료: {output_path}")
            return True
        
        except Exception as e:
            raise FFmpegError(f"썸네일 생성 실패: {e}")
    
    def set_quality_preset(self, preset: str, enable_two_pass: bool = False) -> None:
        """
        품질 프리셋 설정
        
        Args:
            preset: "fast" | "normal" | "high"
            enable_two_pass: 2-pass 인코딩 활성화 여부
        """
        if preset not in QUALITY_PRESETS:
            raise ValueError(f"지원하지 않는 프리셋: {preset}")
        
        self.quality_preset = preset
        self.crf = QUALITY_PRESETS[preset]["crf"]
        self.preset = QUALITY_PRESETS[preset]["preset"]
        self.two_pass = enable_two_pass
        
        self.logger.info(f"품질 프리셋 변경: {preset} (CRF: {self.crf}, Preset: {self.preset}, 2-pass: {enable_two_pass})")
    
    def render_for_track(
        self,
        track_id: str,
        db: TrackDB,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        단일 트랙 영상 생성
        
        Args:
            track_id: 트랙 ID
            db: TrackDB 인스턴스
            options: {
                "resolution": (1920, 1080),
                "ken_burns": True,
                "ken_burns_type": "zoom_in",
                "text_overlay": "Track Title",
                "text_position": "bottom",
                "generate_thumbnail": True,
                "force": False
            }
        
        Returns:
            {
                "success": True,
                "track_id": "track_001",
                "video_path": "./videos/track_001.mp4",
                "thumbnail_path": "./thumbnails/track_001.jpg",
                "duration": 185.5,
                "file_size_mb": 45.2,
                "skipped": False,
                "error": None
            }
        """
        if options is None:
            options = {}
        
        try:
            # 1. 이미지/음악 파일 존재 확인
            track = db.get_track(track_id)
            if not track:
                raise FFmpegError(f"트랙을 찾을 수 없습니다: {track_id}")
            
            music_info = track.get("music", {})
            image_info = track.get("image", {})
            
            music_path = music_info.get("file_path")
            image_path = image_info.get("file_path")
            
            if not music_path or not os.path.exists(music_path):
                raise FFmpegError(f"음악 파일을 찾을 수 없습니다: {track_id}")
            if not image_path or not os.path.exists(image_path):
                raise FFmpegError(f"이미지 파일을 찾을 수 없습니다: {track_id}")
            
            # 2. 이미 영상 있으면 스킵 (force 아닌 경우)
            video_info = track.get("video", {})
            video_path = self.video_folder / f"{track_id}.mp4"
            
            if not options.get("force", False) and video_path.exists():
                self.logger.info(f"이미 영상이 존재합니다: {video_path} (스킵)")
                return {
                    "success": True,
                    "track_id": track_id,
                    "video_path": str(video_path),
                    "thumbnail_path": None,
                    "duration": music_info.get("duration_seconds"),
                    "file_size_mb": video_path.stat().st_size / (1024 * 1024) if video_path.exists() else 0,
                    "skipped": True,
                    "error": None
                }
            
            # 3. 옵션에 따라 렌더링 실행
            resolution = options.get("resolution")
            if resolution:
                if isinstance(resolution, str):
                    # 문자열인 경우 프리셋에서 찾기
                    resolution = RESOLUTION_PRESETS.get(resolution, (1920, 1080))
            else:
                # 기본 해상도
                resolution = tuple(map(int, self.default_resolution.split("x")))
            
            # 품질 프리셋 설정
            quality = options.get("quality", "normal")
            if quality in QUALITY_PRESETS:
                self.set_quality_preset(quality)
            
            # 렌더링 실행
            if options.get("ken_burns"):
                effect_type = options.get("ken_burns_type", "zoom_in")
                self.render_with_ken_burns(
                    image_path,
                    music_path,
                    str(video_path),
                    effect_type=effect_type,
                    resolution=resolution
                )
            elif options.get("text_overlay"):
                text = options.get("text_overlay", "")
                text_position = options.get("text_position", "bottom")
                self.render_with_text(
                    image_path,
                    music_path,
                    str(video_path),
                    text=text,
                    position=text_position,
                    resolution=resolution
                )
            else:
                # 기본 렌더링
                self.render_with_resolution(
                    image_path,
                    music_path,
                    str(video_path),
                    resolution=resolution
                )
            
            # 파일 크기 확인
            file_size_mb = video_path.stat().st_size / (1024 * 1024) if video_path.exists() else 0
            
            # 4. 썸네일 생성 (옵션)
            thumbnail_path = None
            if options.get("generate_thumbnail", self.thumbnail_enabled):
                thumbnail_path_obj = self.thumbnail_folder / f"{track_id}_thumb.jpg"
                
                try:
                    self.generate_thumbnail(
                        str(video_path),
                        str(thumbnail_path_obj),
                        timestamp=self.thumbnail_time,
                        size=(1280, 720)
                    )
                    thumbnail_path = str(thumbnail_path_obj)
                except Exception as e:
                    self.logger.warning(f"썸네일 생성 실패 ({track_id}): {e}")
            
            # 5. DB 업데이트
            duration = music_info.get("duration_seconds")
            if not duration:
                try:
                    duration = get_audio_duration(music_path)
                except Exception:
                    duration = None
            
            db.update_track(track_id, {
                "video": {
                    "status": "completed",
                    "file_path": str(video_path),
                    "resolution": f"{resolution[0]}x{resolution[1]}",
                    "duration": duration,
                    "file_size_mb": round(file_size_mb, 2),
                    "generated_at": datetime.now().isoformat()
                },
                "thumbnail": {
                    "status": "completed" if thumbnail_path else "pending",
                    "file_path": thumbnail_path
                }
            })
            
            self.logger.info(f"영상 생성 완료: {track_id}")
            
            return {
                "success": True,
                "track_id": track_id,
                "video_path": str(video_path),
                "thumbnail_path": thumbnail_path,
                "duration": duration,
                "file_size_mb": round(file_size_mb, 2),
                "skipped": False,
                "error": None
            }
        
        except Exception as e:
            self.logger.error(f"영상 생성 실패 ({track_id}): {e}")
            
            # DB에 에러 기록
            if db:
                db.add_error_log(track_id, "video", str(e))
                db.update_status(track_id, "video", "failed")
            
            return {
                "success": False,
                "track_id": track_id,
                "video_path": None,
                "thumbnail_path": None,
                "duration": None,
                "file_size_mb": 0,
                "skipped": False,
                "error": str(e)
            }
    
    def render_batch(
        self,
        track_ids: List[str],
        db: TrackDB,
        options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        배치 영상 렌더링
        
        Args:
            track_ids: 처리할 트랙 ID 목록
            db: 트랙 DB
            options: 렌더링 옵션
            progress_callback: (current, total, track_id, status, eta_seconds)
        
        Returns:
            {
                "total": 10,
                "successful": 8,
                "failed": 1,
                "skipped": 1,
                "total_duration_seconds": 1850.5,
                "total_size_mb": 425.8,
                "results": [...]
            }
        """
        if options is None:
            options = {}
        
        total = len(track_ids)
        successful = 0
        failed = 0
        skipped = 0
        results = []
        total_duration = 0.0
        total_size = 0.0
        
        start_time = time.time()
        
        for i, track_id in enumerate(track_ids, 1):
            try:
                result = self.render_for_track(track_id, db, options)
                results.append(result)
                
                if result.get("skipped"):
                    skipped += 1
                    status = "skipped"
                elif result.get("success"):
                    successful += 1
                    status = "success"
                    if result.get("duration"):
                        total_duration += result["duration"]
                    if result.get("file_size_mb"):
                        total_size += result["file_size_mb"]
                else:
                    failed += 1
                    status = "failed"
                
                # ETA 계산
                elapsed = time.time() - start_time
                if i > 0:
                    avg_time_per_track = elapsed / i
                    remaining_tracks = total - i
                    eta_seconds = avg_time_per_track * remaining_tracks
                else:
                    eta_seconds = 0
                
                if progress_callback:
                    progress_callback(i, total, track_id, status, eta_seconds)
            
            except Exception as e:
                failed += 1
                self.logger.error(f"배치 렌더링 실패 ({track_id}): {e}")
                results.append({
                    "success": False,
                    "track_id": track_id,
                    "error": str(e)
                })
                
                if progress_callback:
                    progress_callback(i, total, track_id, "failed", 0)
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "total_duration_seconds": round(total_duration, 2),
            "total_size_mb": round(total_size, 2),
            "results": results
        }
    
    def render_all_pending(self, db: TrackDB, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        영상 없는 모든 트랙 처리
        
        Args:
            db: 트랙 DB
            options: 렌더링 옵션
        
        Returns:
            배치 렌더링 결과
        """
        all_tracks = db.get_all_tracks()
        pending_track_ids = []
        
        for track in all_tracks:
            track_id = track.get("track_id")
            video_status = track.get("video", {}).get("status", "pending")
            
            if video_status in ("pending", "failed"):
                # 실제 파일도 확인
                video_path = self.video_folder / f"{track_id}.mp4"
                if not video_path.exists():
                    pending_track_ids.append(track_id)
        
        self.logger.info(f"영상 렌더링 대기 트랙: {len(pending_track_ids)}개")
        
        return self.render_batch(pending_track_ids, db, options=options)
    
    def estimate_render_time(self, track_ids: List[str], db: TrackDB) -> float:
        """
        예상 렌더링 시간(초) 계산
        
        Args:
            track_ids: 트랙 ID 목록
            db: 트랙 DB
        
        Returns:
            예상 시간(초)
        """
        total_duration = 0.0
        
        for track_id in track_ids:
            track = db.get_track(track_id)
            if track:
                duration = track.get("music", {}).get("duration_seconds")
                if duration:
                    total_duration += duration
        
        # 경험적 수치: 음악 1분당 렌더링 약 10초
        estimated_time = (total_duration / 60.0) * 10.0
        
        return estimated_time


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="영상 렌더러")
    parser.add_argument("--track", type=str, help="트랙 ID")
    parser.add_argument("--all-pending", action="store_true", help="모든 pending 트랙 처리")
    parser.add_argument("--resolution", type=str, help="해상도 (1920x1080 또는 프리셋 이름)")
    parser.add_argument("--ken-burns", action="store_true", help="Ken Burns 효과 적용")
    parser.add_argument("--ken-burns-type", type=str, default="zoom_in", help="Ken Burns 타입 (zoom_in, zoom_out, pan_left, pan_right)")
    parser.add_argument("--text", type=str, help="텍스트 오버레이")
    parser.add_argument("--text-position", type=str, default="bottom", help="텍스트 위치 (top, bottom, center)")
    parser.add_argument("--quality", type=str, default="normal", help="품질 프리셋 (fast, normal, high)")
    parser.add_argument("--thumbnail", type=str, help="썸네일만 생성 (트랙 ID)")
    parser.add_argument("--check", action="store_true", help="FFmpeg 환경 체크")
    
    args = parser.parse_args()
    
    renderer = FFmpegRenderer()
    
    if args.check:
        # FFmpeg 환경 체크
        health = renderer.health_check()
        print("\n🔍 FFmpeg 환경 체크")
        print("=" * 60)
        print(f"설치 여부: {'✅ 설치됨' if health['installed'] else '❌ 미설치'}")
        if health['installed']:
            print(f"버전: {health['version'] or '확인 불가'}")
            print(f"libx264 지원: {'✅' if health['libx264'] else '❌'}")
            print(f"aac 지원: {'✅' if health['aac'] else '❌'}")
            print(f"준비 상태: {'✅ 준비됨' if health['ready'] else '❌ 준비 안 됨'}")
        else:
            print("\n⚠️ FFmpeg가 설치되지 않았습니다.")
            print("   설치 방법: https://ffmpeg.org/download.html")
    
    elif args.thumbnail:
        # 썸네일만 생성
        track_id = args.thumbnail
        db = TrackDB()
        track = db.get_track(track_id)
        
        if not track:
            print(f"❌ 트랙을 찾을 수 없습니다: {track_id}")
        else:
            video_info = track.get("video", {})
            video_path = video_info.get("file_path")
            
            if video_path and os.path.exists(video_path):
                thumbnail_path = renderer.thumbnail_folder / f"{track_id}_thumb.jpg"
                try:
                    renderer.generate_thumbnail(
                        video_path,
                        str(thumbnail_path),
                        timestamp=renderer.thumbnail_time
                    )
                    print(f"✅ 썸네일 생성 완료: {thumbnail_path}")
                except Exception as e:
                    print(f"❌ 썸네일 생성 실패: {e}")
            else:
                print(f"❌ 영상 파일을 찾을 수 없습니다: {track_id}")
    
    elif args.track:
        # 단일 트랙 렌더링
        track_id = args.track
        db = TrackDB()
        
        options = {
            "quality": args.quality,
            "generate_thumbnail": True
        }
        
        # 해상도 설정
        if args.resolution:
            if args.resolution in RESOLUTION_PRESETS:
                options["resolution"] = RESOLUTION_PRESETS[args.resolution]
            else:
                try:
                    width, height = map(int, args.resolution.split("x"))
                    options["resolution"] = (width, height)
                except ValueError:
                    print(f"⚠️ 잘못된 해상도 형식: {args.resolution}")
        
        # Ken Burns 효과
        if args.ken_burns:
            options["ken_burns"] = True
            options["ken_burns_type"] = args.ken_burns_type
        
        # 텍스트 오버레이
        if args.text:
            options["text_overlay"] = args.text
            options["text_position"] = args.text_position
        
        result = renderer.render_for_track(track_id, db, options)
        
        if result["success"]:
            if result.get("skipped"):
                print(f"\n⏭️ 스킵됨: {result['video_path']}")
            else:
                print(f"\n✅ 영상 생성 완료!")
                print(f"  - Track ID: {result['track_id']}")
                print(f"  - 파일 경로: {result['video_path']}")
                print(f"  - 길이: {seconds_to_mmss(result['duration']) if result['duration'] else 'N/A'}")
                print(f"  - 파일 크기: {result['file_size_mb']:.2f} MB")
                if result.get('thumbnail_path'):
                    print(f"  - 썸네일: {result['thumbnail_path']}")
        else:
            print(f"\n❌ 생성 실패: {result.get('error', '알 수 없는 오류')}")
    
    elif args.all_pending:
        # 모든 pending 트랙 처리
        print(f"\n배치 영상 렌더링 시작...")
        
        db = TrackDB()
        options = {
            "quality": args.quality,
            "generate_thumbnail": True
        }
        
        if args.resolution:
            if args.resolution in RESOLUTION_PRESETS:
                options["resolution"] = RESOLUTION_PRESETS[args.resolution]
            else:
                try:
                    width, height = map(int, args.resolution.split("x"))
                    options["resolution"] = (width, height)
                except ValueError:
                    print(f"⚠️ 잘못된 해상도 형식: {args.resolution}")
        
        if args.ken_burns:
            options["ken_burns"] = True
            options["ken_burns_type"] = args.ken_burns_type
        
        result = renderer.render_all_pending(db, options=options)
        
        print(f"\n✅ 배치 렌더링 완료!")
        print(f"  - 전체: {result['total']}개")
        print(f"  - 성공: {result['successful']}개")
        print(f"  - 실패: {result['failed']}개")
        print(f"  - 스킵: {result['skipped']}개")
        print(f"  - 총 길이: {seconds_to_mmss(result['total_duration_seconds'])}")
        print(f"  - 총 크기: {result['total_size_mb']:.2f} MB")
    
    else:
        parser.print_help()

