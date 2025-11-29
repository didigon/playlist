"""
설정 관리 모듈
config.json 로드/저장 및 .env 환경변수 관리
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


def load_config(config_path: str = "./config.json") -> Dict[str, Any]:
    """
    config.json 로드, .env로 API 키 오버라이드
    
    Args:
        config_path: config.json 파일 경로
    
    Returns:
        설정 딕셔너리
    
    Raises:
        FileNotFoundError: config.json 파일이 없을 때
        json.JSONDecodeError: JSON 파싱 오류
    """
    config_file = Path(config_path)
    
    # config.json이 없으면 기본 템플릿 생성
    if not config_file.exists():
        create_default_config(config_path)
    
    # config.json 로드
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # .env 파일 로드 (존재하는 경우)
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        
        # .env의 API 키로 오버라이드
        if os.getenv("SUNO_API_KEY"):
            config["suno"]["api_key"] = os.getenv("SUNO_API_KEY")
        
        if os.getenv("OPENAI_API_KEY"):
            config["image"]["api_key"] = os.getenv("OPENAI_API_KEY")
        
        if os.getenv("YOUTUBE_API_KEY"):
            # YouTube API 키는 config에 없을 수 있으므로 안전하게 처리
            if "youtube" not in config:
                config["youtube"] = {}
            config["youtube"]["api_key"] = os.getenv("YOUTUBE_API_KEY")
    
    return config


def save_config(config: Dict[str, Any], config_path: str = "./config.json") -> bool:
    """
    config.json 저장
    
    Args:
        config: 저장할 설정 딕셔너리
        config_path: 저장할 파일 경로
    
    Returns:
        성공 여부
    """
    try:
        config_file = Path(config_path)
        
        # 백업 생성 (기존 파일이 있는 경우)
        if config_file.exists():
            backup_path = config_file.with_suffix('.json.bak')
            config_file.rename(backup_path)
        
        # 설정 저장
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"설정 저장 실패: {e}")
        return False


def create_default_config(config_path: str = "./config.json") -> None:
    """
    기본 config.json 템플릿 생성
    
    Args:
        config_path: 생성할 파일 경로
    """
    default_config = {
        "_comment": "Suno Video Factory 설정 파일",
        "suno": {
            "api_key": "YOUR_SUNO_API_KEY",
            "api_base_url": "https://api.suno.ai",
            "model": "v3.5",
            "daily_limit": 60,
            "timeout_seconds": 300
        },
        "image": {
            "provider": "openai",
            "api_key": "YOUR_OPENAI_API_KEY",
            "model": "dall-e-3",
            "default_size": "1792x1024",
            "quality": "hd",
            "format": "png",
            "fallback_format": "jpg"
        },
        "video": {
            "ffmpeg_path": "ffmpeg",
            "codec_video": "libx264",
            "codec_audio": "aac",
            "audio_bitrate": "192k",
            "default_resolution": "1920x1080",
            "vertical_resolution": "1080x1920",
            "thumbnail_enabled": True,
            "thumbnail_time": "00:00:05"
        },
        "paths": {
            "music_folder": "./music",
            "image_folder": "./images",
            "video_folder": "./videos",
            "thumbnail_folder": "./thumbnails",
            "prompt_folder": "./prompts",
            "log_folder": "./logs",
            "db_folder": "./db"
        },
        "pipeline": {
            "auto_retry_count": 3,
            "retry_delay_seconds": 2,
            "retry_backoff_multiplier": 2,
            "rate_limit_wait_seconds": 60,
            "checkpoint_enabled": True,
            "parallel_enabled": False,
            "max_parallel_tasks": 3
        },
        "logging": {
            "level": "INFO",
            "file_enabled": True,
            "console_enabled": True,
            "max_file_size_mb": 10,
            "backup_count": 5
        }
    }
    
    save_config(default_config, config_path)
    print(f"기본 설정 파일 생성: {config_path}")


def get_path(key: str, config: Optional[Dict[str, Any]] = None) -> str:
    """
    경로 설정값 반환
    
    Args:
        key: 경로 키 (예: 'music_folder')
        config: 설정 딕셔너리 (None이면 자동 로드)
    
    Returns:
        경로 문자열
    """
    if config is None:
        config = load_config()
    
    return config.get("paths", {}).get(key, "")


def get_api_key(service: str, config: Optional[Dict[str, Any]] = None) -> str:
    """
    API 키 반환
    
    Args:
        service: 서비스 이름 ('suno', 'openai', 'youtube')
        config: 설정 딕셔너리 (None이면 자동 로드)
    
    Returns:
        API 키 문자열
    """
    if config is None:
        config = load_config()
    
    service_map = {
        "suno": ("suno", "api_key"),
        "openai": ("image", "api_key"),
        "youtube": ("youtube", "api_key")
    }
    
    if service not in service_map:
        return ""
    
    section, key = service_map[service]
    return config.get(section, {}).get(key, "")


if __name__ == "__main__":
    # 테스트
    print("설정 로드 테스트...")
    config = load_config()
    print(f"음악 폴더: {get_path('music_folder', config)}")
    print(f"Suno API 키: {get_api_key('suno', config)[:20]}...")


