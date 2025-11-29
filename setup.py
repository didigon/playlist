#!/usr/bin/env python3
"""Suno Video Factory - 환경 설정 스크립트
필요한 폴더 구조를 자동으로 생성합니다."""

import os
from pathlib import Path

REQUIRED_FOLDERS = [
    "music",
    "images",
    "videos",
    "thumbnails",
    "prompts",
    "logs",
    "db"
]


def create_folders(base_path: str = ".") -> list[str]:
    """
    필요한 폴더들을 생성합니다.
    
    Args:
        base_path: 기본 경로 (기본값: 현재 디렉토리)
    
    Returns:
        생성된 폴더 경로 리스트
    """
    base = Path(base_path)
    created_folders = []
    
    for folder_name in REQUIRED_FOLDERS:
        folder_path = base / folder_name
        
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            created_folders.append(str(folder_path))
            print(f"[OK] {folder_path} 생성 완료")
        except Exception as e:
            print(f"[FAIL] {folder_path} 생성 실패: {e}")
    
    return created_folders


def main():
    """메인 함수"""
    print("=" * 50)
    print("Suno Video Factory - 환경 설정")
    print("=" * 50)
    print()
    
    created = create_folders()
    
    print()
    print("=" * 50)
    print(f"총 {len(created)}개 폴더 생성 완료")
    print("=" * 50)


if __name__ == "__main__":
    main()

