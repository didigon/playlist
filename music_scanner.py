"""
음악 파일 스캐너 모듈
/music 폴더 스캔 및 DB 동기화
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from db_manager import TrackDB
from config_manager import load_config, get_path


class MusicScanner:
    """음악 파일 스캐너 클래스"""
    
    SUPPORTED_FORMATS = ['.mp3', '.wav', '.flac']
    
    def __init__(self, music_folder: Optional[str] = None, db: Optional[TrackDB] = None):
        """
        MusicScanner 초기화
        
        Args:
            music_folder: 음악 폴더 경로 (None이면 config에서 로드)
            db: TrackDB 인스턴스 (None이면 새로 생성)
        """
        if music_folder is None:
            config = load_config()
            music_folder = get_path('music_folder', config)
        
        self.music_folder = Path(music_folder)
        self.music_folder.mkdir(parents=True, exist_ok=True)
        
        if db is None:
            self.db = TrackDB()
        else:
            self.db = db
        
        # 이미지/영상 폴더 경로 (config에서 로드)
        config = load_config()
        self.image_folder = Path(get_path('image_folder', config))
        self.video_folder = Path(get_path('video_folder', config))
        self.image_folder.mkdir(parents=True, exist_ok=True)
        self.video_folder.mkdir(parents=True, exist_ok=True)
    
    def scan(self) -> List[Dict[str, Any]]:
        """
        폴더 스캔 후 트랙 목록 반환
        
        Returns:
            트랙 정보 리스트
        """
        tracks = []
        
        if not self.music_folder.exists():
            return tracks
        
        # 지원 포맷 파일 스캔
        for ext in self.SUPPORTED_FORMATS:
            for file_path in self.music_folder.glob(f"*{ext}"):
                # 숨김 파일 제외
                if file_path.name.startswith('.'):
                    continue
                
                track_id = self.get_track_id(file_path.name)
                tracks.append({
                    "track_id": track_id,
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "extension": ext,
                    "size_bytes": file_path.stat().st_size if file_path.exists() else 0
                })
        
        # track_id 기준으로 정렬
        tracks.sort(key=lambda x: x["track_id"])
        return tracks
    
    def get_track_id(self, filename: str) -> str:
        """
        파일명에서 track_id 추출
        
        Args:
            filename: 파일명 (예: "track_001.mp3")
        
        Returns:
            track_id (예: "track_001")
        """
        # 확장자 제거
        name_without_ext = Path(filename).stem
        return name_without_ext
    
    def is_supported_format(self, filename: str) -> bool:
        """
        지원 포맷 확인
        
        Args:
            filename: 파일명
        
        Returns:
            지원 여부
        """
        ext = Path(filename).suffix.lower()
        return ext in self.SUPPORTED_FORMATS
    
    def check_file_status(self, track_id: str) -> Dict[str, Any]:
        """
        파일 존재 여부 확인
        
        Args:
            track_id: 트랙 ID
        
        Returns:
            파일 상태 딕셔너리
        """
        status = {
            "track_id": track_id,
            "music_exists": False,
            "music_path": None,
            "image_exists": False,
            "image_path": None,
            "video_exists": False,
            "video_path": None
        }
        
        # 음악 파일 확인 (여러 확장자 체크)
        for ext in self.SUPPORTED_FORMATS:
            music_path = self.music_folder / f"{track_id}{ext}"
            if music_path.exists():
                status["music_exists"] = True
                status["music_path"] = str(music_path)
                break
        
        # 이미지 파일 확인 (png, jpg 둘 다 체크)
        for ext in ['.png', '.jpg', '.jpeg']:
            image_path = self.image_folder / f"{track_id}{ext}"
            if image_path.exists():
                status["image_exists"] = True
                status["image_path"] = str(image_path)
                break
        
        # 영상 파일 확인
        video_path = self.video_folder / f"{track_id}.mp4"
        if video_path.exists():
            status["video_exists"] = True
            status["video_path"] = str(video_path)
        
        return status
    
    def sync_with_db(self, track_id: str, status: Dict[str, Any]) -> bool:
        """
        파일 상태를 DB에 동기화
        
        Args:
            track_id: 트랙 ID
            status: 파일 상태 딕셔너리
        
        Returns:
            성공 여부
        """
        track = self.db.get_track(track_id)
        if track is None:
            return False
        
        updates = {}
        
        # 음악 상태 동기화
        if status["music_exists"]:
            if track.get("music", {}).get("status") != "completed":
                updates.setdefault("music", {})["status"] = "completed"
            if track.get("music", {}).get("file_path") != status["music_path"]:
                updates.setdefault("music", {})["file_path"] = status["music_path"]
        else:
            if track.get("music", {}).get("status") == "completed":
                updates.setdefault("music", {})["status"] = "pending"
        
        # 이미지 상태 동기화
        if status["image_exists"]:
            if track.get("image", {}).get("status") != "completed":
                updates.setdefault("image", {})["status"] = "completed"
            if track.get("image", {}).get("file_path") != status["image_path"]:
                updates.setdefault("image", {})["file_path"] = status["image_path"]
        else:
            if track.get("image", {}).get("status") == "completed":
                updates.setdefault("image", {})["status"] = "pending"
        
        # 영상 상태 동기화
        if status["video_exists"]:
            if track.get("video", {}).get("status") != "completed":
                updates.setdefault("video", {})["status"] = "completed"
            if track.get("video", {}).get("file_path") != status["video_path"]:
                updates.setdefault("video", {})["file_path"] = status["video_path"]
        else:
            if track.get("video", {}).get("status") == "completed":
                updates.setdefault("video", {})["status"] = "pending"
        
        if updates:
            return self.db.update_track(track_id, updates)
        
        return True
    
    def detect_new_tracks(self) -> List[str]:
        """
        DB에 없는 새 트랙 ID 목록
        
        Returns:
            새 트랙 ID 리스트
        """
        scanned_tracks = self.scan()
        db_tracks = self.db.get_all_tracks()
        db_track_ids = {track.get("track_id") for track in db_tracks}
        
        new_track_ids = [
            track["track_id"] for track in scanned_tracks
            if track["track_id"] not in db_track_ids
        ]
        
        return new_track_ids
    
    def register_new_track(self, track_id: str, music_path: Optional[str] = None) -> bool:
        """
        새 트랙을 DB에 등록
        
        Args:
            track_id: 트랙 ID
            music_path: 음악 파일 경로 (None이면 자동 검색)
        
        Returns:
            성공 여부
        """
        # 이미 존재하면 등록하지 않음
        if self.db.get_track(track_id) is not None:
            return False
        
        # 음악 파일 경로 찾기
        if music_path is None:
            for ext in self.SUPPORTED_FORMATS:
                path = self.music_folder / f"{track_id}{ext}"
                if path.exists():
                    music_path = str(path)
                    break
        
        if music_path is None:
            return False
        
        # 트랙 추가 (music 상태는 completed로 설정)
        initial_data = {
            "track_id": track_id,
            "music": {
                "status": "completed",
                "file_path": music_path
            }
        }
        
        return self.db.add_track(track_id, initial_data)
    
    def register_all_new(self) -> int:
        """
        모든 신규 트랙 일괄 등록
        
        Returns:
            등록된 트랙 개수
        """
        new_track_ids = self.detect_new_tracks()
        registered_count = 0
        
        for track_id in new_track_ids:
            if self.register_new_track(track_id):
                registered_count += 1
        
        return registered_count
    
    def detect_missing_files(self) -> List[str]:
        """
        파일은 없고 DB에만 있는 트랙 ID
        
        Returns:
            누락된 트랙 ID 리스트
        """
        db_tracks = self.db.get_all_tracks()
        missing_track_ids = []
        
        for track in db_tracks:
            track_id = track.get("track_id")
            music_path = track.get("music", {}).get("file_path")
            
            # 음악 파일이 없으면 누락으로 간주
            if music_path and not Path(music_path).exists():
                missing_track_ids.append(track_id)
            elif not music_path:
                # DB에 경로가 없으면 스캔해서 확인
                status = self.check_file_status(track_id)
                if not status["music_exists"]:
                    missing_track_ids.append(track_id)
        
        return missing_track_ids
    
    def handle_missing(self, track_id: str, action: str = "warn") -> bool:
        """
        누락 파일 처리
        
        Args:
            track_id: 트랙 ID
            action: 처리 방법 ("warn" | "remove" | "mark_missing")
        
        Returns:
            성공 여부
        """
        if action == "warn":
            # 경고만 (로그에 기록)
            print(f"경고: {track_id}의 음악 파일이 없습니다.")
            return True
        
        elif action == "remove":
            # DB에서 제거
            return self.db.delete_track(track_id)
        
        elif action == "mark_missing":
            # 상태를 'missing'으로 변경
            return self.db.update_status(track_id, "music", "missing")
        
        return False
    
    def full_scan_and_sync(self) -> Dict[str, Any]:
        """
        전체 스캔 수행, 결과 요약 반환
        
        Returns:
            스캔 결과 요약
        """
        # 스캔
        scanned_tracks = self.scan()
        total_music_files = len(scanned_tracks)
        
        # 신규 트랙 등록
        new_tracks_registered = self.register_all_new()
        
        # 누락 파일 감지
        missing_files_found = len(self.detect_missing_files())
        
        # DB 동기화 (모든 트랙의 파일 상태 확인 및 업데이트)
        db_tracks = self.db.get_all_tracks()
        synced_count = 0
        
        for track in db_tracks:
            track_id = track.get("track_id")
            status = self.check_file_status(track_id)
            if self.sync_with_db(track_id, status):
                synced_count += 1
        
        return {
            "total_music_files": total_music_files,
            "new_tracks_registered": new_tracks_registered,
            "missing_files_found": missing_files_found,
            "db_synced": synced_count == len(db_tracks),
            "synced_tracks": synced_count
        }
    
    def get_tracks_needing_image(self) -> List[Dict[str, Any]]:
        """
        이미지가 필요한 트랙 목록
        
        Returns:
            트랙 리스트
        """
        all_tracks = self.db.get_all_tracks()
        return [
            track for track in all_tracks
            if track.get("image", {}).get("status") in ["pending", "failed"]
        ]
    
    def get_tracks_needing_video(self) -> List[Dict[str, Any]]:
        """
        영상이 필요한 트랙 목록
        
        Returns:
            트랙 리스트
        """
        all_tracks = self.db.get_all_tracks()
        return [
            track for track in all_tracks
            if track.get("video", {}).get("status") in ["pending", "failed"]
            and track.get("image", {}).get("status") == "completed"
        ]
    
    def get_tracks_fully_completed(self) -> List[Dict[str, Any]]:
        """
        모든 단계 완료된 트랙
        
        Returns:
            트랙 리스트
        """
        all_tracks = self.db.get_all_tracks()
        return [
            track for track in all_tracks
            if (track.get("music", {}).get("status") == "completed" and
                track.get("image", {}).get("status") == "completed" and
                track.get("video", {}).get("status") == "completed")
        ]
    
    def get_tracks_by_style(self, style: str) -> List[Dict[str, Any]]:
        """
        특정 스타일의 트랙
        
        Args:
            style: 스타일 이름
        
        Returns:
            트랙 리스트
        """
        all_tracks = self.db.get_all_tracks()
        return [
            track for track in all_tracks
            if track.get("image", {}).get("style") == style
        ]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="음악 파일 스캐너")
    parser.add_argument("--scan", action="store_true", help="전체 스캔")
    parser.add_argument("--status", action="store_true", help="상태 요약 출력")
    parser.add_argument("--check", type=str, help="특정 트랙 상태 확인")
    parser.add_argument("--register-new", action="store_true", help="신규 트랙만 등록")
    
    args = parser.parse_args()
    
    scanner = MusicScanner()
    db = TrackDB()
    
    if args.scan:
        print("전체 스캔 중...")
        result = scanner.full_scan_and_sync()
        print(f"\n스캔 결과:")
        print(f"  - 음악 파일: {result['total_music_files']}개")
        print(f"  - 신규 등록: {result['new_tracks_registered']}개")
        print(f"  - 누락 파일: {result['missing_files_found']}개")
        print(f"  - DB 동기화: {'완료' if result['db_synced'] else '부분 완료'}")
    
    elif args.status:
        stats = db.get_statistics()
        print(f"\n상태 요약:")
        print(f"  - 전체 트랙: {stats['total_tracks']}개")
        print(f"  - 음악 완료: {stats['music']['completed']}개")
        print(f"  - 이미지 완료: {stats['image']['completed']}개")
        print(f"  - 영상 완료: {stats['video']['completed']}개")
        print(f"  - 전체 완료: {stats['fully_completed']}개")
    
    elif args.check:
        status = scanner.check_file_status(args.check)
        print(f"\n트랙 상태: {args.check}")
        print(f"  - 음악: {'✓' if status['music_exists'] else '✗'} {status['music_path'] or '없음'}")
        print(f"  - 이미지: {'✓' if status['image_exists'] else '✗'} {status['image_path'] or '없음'}")
        print(f"  - 영상: {'✓' if status['video_exists'] else '✗'} {status['video_path'] or '없음'}")
    
    elif args.register_new:
        count = scanner.register_all_new()
        print(f"신규 트랙 {count}개 등록 완료")
    
    else:
        parser.print_help()




