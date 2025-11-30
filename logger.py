"""
로깅 설정 모듈
콘솔 + 파일 동시 로깅, 컬러 출력, 파일 로테이션 지원
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


def setup_logger(
    name: str,
    level: str = "INFO",
    log_folder: str = "./logs",
    file_enabled: bool = True,
    console_enabled: bool = True,
    max_file_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    로거 설정 및 반환
    
    Args:
        name: 로거 이름
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_folder: 로그 파일 저장 폴더
        file_enabled: 파일 로깅 활성화 여부
        console_enabled: 콘솔 로깅 활성화 여부
        max_file_size_mb: 최대 파일 크기 (MB)
        backup_count: 백업 파일 개수
    
    Returns:
        설정된 로거 인스턴스
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 기존 핸들러 제거 (중복 방지)
    logger.handlers.clear()
    
    # 포맷터 설정
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    if HAS_COLORLOG:
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s%(reset)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # 파일 핸들러
    if file_enabled:
        log_folder_path = Path(log_folder)
        log_folder_path.mkdir(parents=True, exist_ok=True)
        
        # 일반 로그 파일
        log_file = log_folder_path / "pipeline.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # 에러 로그 파일
        error_file = log_folder_path / "error.log"
        error_handler = RotatingFileHandler(
            error_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)
    
    # 콘솔 핸들러
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def log_info(message: str, logger: Optional[logging.Logger] = None):
    """
    INFO 레벨 로그 기록
    
    Args:
        message: 로그 메시지
        logger: 로거 인스턴스 (None이면 기본 로거 사용)
    """
    if logger is None:
        logger = logging.getLogger("default")
    logger.info(message)


def log_error(message: str, exc_info: bool = False, logger: Optional[logging.Logger] = None):
    """
    ERROR 레벨 로그 기록
    
    Args:
        message: 로그 메시지
        exc_info: 예외 정보 포함 여부
        logger: 로거 인스턴스 (None이면 기본 로거 사용)
    """
    if logger is None:
        logger = logging.getLogger("default")
    logger.error(message, exc_info=exc_info)


def log_debug(message: str, logger: Optional[logging.Logger] = None):
    """
    DEBUG 레벨 로그 기록
    
    Args:
        message: 로그 메시지
        logger: 로거 인스턴스 (None이면 기본 로거 사용)
    """
    if logger is None:
        logger = logging.getLogger("default")
    logger.debug(message)


def log_warning(message: str, logger: Optional[logging.Logger] = None):
    """
    WARNING 레벨 로그 기록
    
    Args:
        message: 로그 메시지
        logger: 로거 인스턴스 (None이면 기본 로거 사용)
    """
    if logger is None:
        logger = logging.getLogger("default")
    logger.warning(message)


if __name__ == "__main__":
    # 테스트
    test_logger = setup_logger("test", level="DEBUG")
    
    log_info("정보 로그 테스트", test_logger)
    log_warning("경고 로그 테스트", test_logger)
    log_error("에러 로그 테스트", test_logger)
    log_debug("디버그 로그 테스트", test_logger)
    
    try:
        raise ValueError("테스트 예외")
    except Exception as e:
        log_error(f"예외 발생: {e}", exc_info=True, logger=test_logger)


