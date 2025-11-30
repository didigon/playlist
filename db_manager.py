"""
메타데이터 DB 관리 모듈
tracks.json, failed_tasks.json, checkpoint.json 관리
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from filelock import FileLock, Timeout


class TrackDB:
    """트랙 메타데이터 DB 관리 클래스"""
    
    def __init__(self, db_path: str = "./db/tracks.json"):
        """
        TrackDB 초기화
        
        Args:
            db_path: tracks.json 파일 경로
        """
        self.db_path = Path(db_path)
        self.lock_path = Path(str(db_path) + ".lock")
        self._data: Optional[Dict[str, Any]] = None
        
        # DB 폴더 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """
        DB 로드, 없으면 빈 구조 생성
        
        Returns:
            DB 데이터 딕셔너리
        """
        if self._data is not None:
            return self._data
        
        if not self.db_path.exists():
            # 빈 구조 생성
            self._data = {
                "tracks": {},
                "metadata": {
                    "total_tracks": 0,
                    "last_updated": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
            self.save()
            return self._data
        
        try:
            with FileLock(self.lock_path, timeout=5):
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
        except Timeout:
            raise RuntimeError("DB 파일이 다른 프로세스에서 사용 중입니다.")
        except json.JSONDecodeError:
            # 백업 생성 후 빈 구조로 초기화
            self._backup_file()
            self._data = {
                "tracks": {},
                "metadata": {
                    "total_tracks": 0,
                    "last_updated": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
            self.save()
        
        return self._data
    
    def save(self) -> bool:
        """
        DB 저장 (자동 백업 포함)
        
        Returns:
            성공 여부
        """
        if self._data is None:
            self.load()
        
        try:
            # 백업 생성
            if self.db_path.exists():
                self._backup_file()
            
            # 메타데이터 업데이트
            self._data["metadata"]["last_updated"] = datetime.now().isoformat()
            self._data["metadata"]["total_tracks"] = len(self._data.get("tracks", {}))
            
            # 파일 저장
            with FileLock(self.lock_path, timeout=5):
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"DB 저장 실패: {e}")
            return False
    
    def _backup_file(self) -> None:
        """DB 파일 백업"""
        if not self.db_path.exists():
            return
        
        backup_path = self.db_path.with_suffix('.json.bak')
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
        except Exception as e:
            print(f"백업 생성 실패: {e}")
    
    def get_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        단일 트랙 조회
        
        Args:
            track_id: 트랙 ID
        
        Returns:
            트랙 데이터 또는 None
        """
        data = self.load()
        return data.get("tracks", {}).get(track_id)
    
    def get_all_tracks(self) -> List[Dict[str, Any]]:
        """
        전체 트랙 목록
        
        Returns:
            트랙 리스트
        """
        data = self.load()
        tracks = data.get("tracks", {})
        return [track for track in tracks.values()]
    
    def add_track(self, track_id: str, initial_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        새 트랙 추가
        
        Args:
            track_id: 트랙 ID
            initial_data: 초기 데이터 (None이면 기본 구조 생성)
        
        Returns:
            성공 여부
        """
        data = self.load()
        
        # 이미 존재하면 추가하지 않음
        if track_id in data.get("tracks", {}):
            return False
        
        # 기본 트랙 구조
        if initial_data is None:
            initial_data = {
                "track_id": track_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "music": {
                    "status": "pending",
                    "file_path": None,
                    "suno_task_id": None,
                    "suno_prompt": None,
                    "duration_seconds": None,
                    "generated_at": None
                },
                "image": {
                    "status": "pending",
                    "file_path": None,
                    "prompt_used": None,
                    "style": None,
                    "resolution": None,
                    "format": None,
                    "generated_at": None
                },
                "video": {
                    "status": "pending",
                    "file_path": None,
                    "resolution": None,
                    "generated_at": None
                },
                "thumbnail": {
                    "status": "pending",
                    "file_path": None
                },
                "error_log": [],
                "retry_count": 0
            }
        
        data.setdefault("tracks", {})[track_id] = initial_data
        self._data = data
        return self.save()
    
    def update_track(self, track_id: str, updates: Dict[str, Any]) -> bool:
        """
        트랙 정보 업데이트
        
        Args:
            track_id: 트랙 ID
            updates: 업데이트할 데이터 (중첩 딕셔너리 지원)
        
        Returns:
            성공 여부
        """
        data = self.load()
        
        if track_id not in data.get("tracks", {}):
            return False
        
        track = data["tracks"][track_id]
        
        # 중첩 딕셔너리 업데이트
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(track.get(key), dict):
                track[key].update(value)
            else:
                track[key] = value
        
        track["updated_at"] = datetime.now().isoformat()
        self._data = data
        return self.save()
    
    def update_status(self, track_id: str, stage: str, status: str) -> bool:
        """
        상태만 빠르게 업데이트 (stage: music/image/video)
        
        Args:
            track_id: 트랙 ID
            stage: 단계 (music/image/video/thumbnail)
            status: 상태 (pending/processing/completed/failed/skipped)
        
        Returns:
            성공 여부
        """
        data = self.load()
        
        if track_id not in data.get("tracks", {}):
            return False
        
        track = data["tracks"][track_id]
        
        if stage not in track:
            return False
        
        track[stage]["status"] = status
        track["updated_at"] = datetime.now().isoformat()
        self._data = data
        return self.save()
    
    def delete_track(self, track_id: str) -> bool:
        """
        트랙 삭제
        
        Args:
            track_id: 트랙 ID
        
        Returns:
            성공 여부
        """
        data = self.load()
        
        if track_id not in data.get("tracks", {}):
            return False
        
        del data["tracks"][track_id]
        self._data = data
        return self.save()
    
    def get_tracks_by_status(self, stage: str, status: str) -> List[Dict[str, Any]]:
        """
        특정 상태의 트랙들 조회
        
        Args:
            stage: 단계 (music/image/video/thumbnail)
            status: 상태 (pending/processing/completed/failed/skipped)
        
        Returns:
            해당 상태의 트랙 리스트
        """
        all_tracks = self.get_all_tracks()
        return [
            track for track in all_tracks
            if track.get(stage, {}).get("status") == status
        ]
    
    def add_error_log(self, track_id: str, stage: str, error_message: str) -> bool:
        """
        에러 로그 추가
        
        Args:
            track_id: 트랙 ID
            stage: 단계 (music/image/video)
            error_message: 에러 메시지
        
        Returns:
            성공 여부
        """
        data = self.load()
        
        if track_id not in data.get("tracks", {}):
            return False
        
        track = data["tracks"][track_id]
        error_log = track.get("error_log", [])
        
        # 새 에러 로그 추가
        error_log.append({
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "message": error_message
        })
        
        # 최대 10개까지 보관 (오래된 것 삭제)
        if len(error_log) > 10:
            error_log = error_log[-10:]
        
        track["error_log"] = error_log
        self._data = data
        return self.save()
    
    def get_error_log(self, track_id: str) -> List[Dict[str, Any]]:
        """
        에러 로그 조회
        
        Args:
            track_id: 트랙 ID
        
        Returns:
            에러 로그 리스트
        """
        track = self.get_track(track_id)
        if track is None:
            return []
        return track.get("error_log", [])
    
    def clear_error_log(self, track_id: str) -> bool:
        """
        에러 로그 초기화
        
        Args:
            track_id: 트랙 ID
        
        Returns:
            성공 여부
        """
        return self.update_track(track_id, {"error_log": []})
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        대시보드용 통계 데이터 제공
        
        Returns:
            통계 딕셔너리
        """
        all_tracks = self.get_all_tracks()
        total_tracks = len(all_tracks)
        
        stats = {
            "total_tracks": total_tracks,
            "music": {"completed": 0, "pending": 0, "failed": 0, "processing": 0, "skipped": 0},
            "image": {"completed": 0, "pending": 0, "failed": 0, "processing": 0, "skipped": 0},
            "video": {"completed": 0, "pending": 0, "failed": 0, "processing": 0, "skipped": 0},
            "fully_completed": 0
        }
        
        for track in all_tracks:
            # 각 단계별 상태 카운트
            for stage in ["music", "image", "video"]:
                status = track.get(stage, {}).get("status", "pending")
                if status in stats[stage]:
                    stats[stage][status] += 1
            
            # 완전히 완료된 트랙 카운트
            if (track.get("music", {}).get("status") == "completed" and
                track.get("image", {}).get("status") == "completed" and
                track.get("video", {}).get("status") == "completed"):
                stats["fully_completed"] += 1
        
        return stats


class FailedTasksDB:
    """실패 작업 관리 클래스"""
    
    def __init__(self, db_path: str = "./db/failed_tasks.json"):
        """
        FailedTasksDB 초기화
        
        Args:
            db_path: failed_tasks.json 파일 경로
        """
        self.db_path = Path(db_path)
        self.lock_path = Path(str(db_path) + ".lock")
        self._data: Optional[Dict[str, Any]] = None
        
        # DB 폴더 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        """DB 로드"""
        if self._data is not None:
            return self._data
        
        if not self.db_path.exists():
            self._data = {
                "failed_tasks": [],
                "last_updated": datetime.now().isoformat()
            }
            self.save()
            return self._data
        
        try:
            with FileLock(self.lock_path, timeout=5):
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
        except Exception as e:
            print(f"Failed tasks DB 로드 실패: {e}")
            self._data = {
                "failed_tasks": [],
                "last_updated": datetime.now().isoformat()
            }
        
        return self._data
    
    def save(self) -> bool:
        """DB 저장"""
        if self._data is None:
            self.load()
        
        try:
            self._data["last_updated"] = datetime.now().isoformat()
            
            with FileLock(self.lock_path, timeout=5):
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed tasks DB 저장 실패: {e}")
            return False
    
    def add_failed_task(self, track_id: str, stage: str, error: str, retry_count: int = 0) -> bool:
        """
        실패 작업 추가
        
        Args:
            track_id: 트랙 ID
            stage: 단계 (music/image/video)
            error: 에러 메시지
            retry_count: 재시도 횟수
        
        Returns:
            성공 여부
        """
        data = self.load()
        
        # 중복 체크 (같은 track_id + stage 조합이 이미 있으면 업데이트)
        failed_tasks = data.get("failed_tasks", [])
        for task in failed_tasks:
            if task.get("track_id") == track_id and task.get("stage") == stage:
                task["failed_at"] = datetime.now().isoformat()
                task["error_message"] = error
                task["retry_count"] = retry_count
                self._data = data
                return self.save()
        
        # 새 실패 작업 추가
        failed_tasks.append({
            "track_id": track_id,
            "stage": stage,
            "failed_at": datetime.now().isoformat(),
            "error_message": error,
            "retry_count": retry_count
        })
        
        data["failed_tasks"] = failed_tasks
        self._data = data
        return self.save()
    
    def get_failed_tasks(self) -> List[Dict[str, Any]]:
        """
        실패 작업 목록 조회
        
        Returns:
            실패 작업 리스트
        """
        data = self.load()
        return data.get("failed_tasks", [])
    
    def remove_failed_task(self, track_id: str, stage: str) -> bool:
        """
        실패 작업 제거 (재시도 성공 시)
        
        Args:
            track_id: 트랙 ID
            stage: 단계
        
        Returns:
            성공 여부
        """
        data = self.load()
        failed_tasks = data.get("failed_tasks", [])
        
        # 해당 작업 제거
        data["failed_tasks"] = [
            task for task in failed_tasks
            if not (task.get("track_id") == track_id and task.get("stage") == stage)
        ]
        
        self._data = data
        return self.save()
    
    def retry_all_failed(self) -> Dict[str, Any]:
        """
        모든 실패 작업 재시도 (인터페이스만 제공, 실제 재시도는 파이프라인에서 처리)
        
        Returns:
            {
                "total": 총 실패 작업 수,
                "tasks": 실패 작업 리스트
            }
        """
        failed_tasks = self.get_failed_tasks()
        return {
            "total": len(failed_tasks),
            "tasks": failed_tasks
        }


class CheckpointDB:
    """체크포인트 관리 클래스"""
    
    def __init__(self, db_path: str = "./db/checkpoint.json"):
        """
        CheckpointDB 초기화
        
        Args:
            db_path: checkpoint.json 파일 경로
        """
        self.db_path = Path(db_path)
        self.lock_path = Path(str(db_path) + ".lock")
        self._data: Optional[Dict[str, Any]] = None
        
        # DB 폴더 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Optional[Dict[str, Any]]:
        """체크포인트 로드"""
        if self._data is not None:
            return self._data if self._data.get("is_running") else None
        
        if not self.db_path.exists():
            return None
        
        try:
            with FileLock(self.lock_path, timeout=5):
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            
            # is_running이 False면 None 반환
            if not self._data.get("is_running", False):
                return None
            
            return self._data
        except Exception:
            return None
    
    def save_checkpoint(
        self,
        stage: str,
        track_id: str,
        completed: List[str],
        pending: List[str]
    ) -> bool:
        """
        체크포인트 저장
        
        Args:
            stage: 현재 단계
            track_id: 현재 처리 중인 트랙 ID
            completed: 완료된 트랙 ID 리스트
            pending: 대기 중인 트랙 ID 리스트
        
        Returns:
            성공 여부
        """
        self._data = {
            "is_running": True,
            "started_at": datetime.now().isoformat(),
            "current_stage": stage,
            "current_track_id": track_id,
            "completed_tracks": completed,
            "pending_tracks": pending,
            "last_updated": datetime.now().isoformat()
        }
        
        try:
            with FileLock(self.lock_path, timeout=5):
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Checkpoint 저장 실패: {e}")
            return False
    
    def clear_checkpoint(self) -> bool:
        """
        체크포인트 삭제 (정상 완료 시)
        
        Returns:
            성공 여부
        """
        if not self.db_path.exists():
            return True
        
        try:
            # is_running을 False로 설정
            if self._data is None:
                with FileLock(self.lock_path, timeout=5):
                    with open(self.db_path, 'r', encoding='utf-8') as f:
                        self._data = json.load(f)
            
            self._data["is_running"] = False
            self._data["last_updated"] = datetime.now().isoformat()
            
            with FileLock(self.lock_path, timeout=5):
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Checkpoint 삭제 실패: {e}")
            return False
    
    def has_checkpoint(self) -> bool:
        """
        중단된 작업 있는지 확인
        
        Returns:
            체크포인트 존재 여부
        """
        checkpoint = self.load()
        return checkpoint is not None


if __name__ == "__main__":
    # 테스트
    print("TrackDB 테스트...")
    db = TrackDB()
    
    # 트랙 추가
    db.add_track("track_001")
    print("트랙 추가 완료")
    
    # 트랙 조회
    track = db.get_track("track_001")
    print(f"트랙 조회: {track['track_id']}")
    
    # 상태 업데이트
    db.update_status("track_001", "music", "completed")
    print("상태 업데이트 완료")
    
    # 통계 조회
    stats = db.get_statistics()
    print(f"통계: {stats}")
    
    print("\n모든 테스트 완료!")
