"""트랙/실패 작업/체크포인트 관리를 담당하는 DB 모듈."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from filelock import FileLock

logger = logging.getLogger(__name__)


class TrackDB:
    """tracks.json, failed_tasks.json, checkpoint.json을 관리하는 헬퍼."""

    def __init__(
        self,
        db_path: str = "./db/tracks.json",
        failed_tasks_path: str = "./db/failed_tasks.json",
        checkpoint_path: str = "./db/checkpoint.json",
    ) -> None:
        self.db_path = Path(db_path)
        self.failed_tasks_path = Path(failed_tasks_path)
        self.checkpoint_path = Path(checkpoint_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.failed_tasks_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        self.lock = FileLock(str(self.db_path.with_suffix(self.db_path.suffix + ".lock")))
        self.failed_lock = FileLock(
            str(self.failed_tasks_path.with_suffix(self.failed_tasks_path.suffix + ".lock"))
        )
        self.checkpoint_lock = FileLock(
            str(self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".lock"))
        )

        self.data: Dict[str, Any] = {}
        self.failed_tasks: Dict[str, Any] = {}
        self.load()
        self._load_failed_tasks()

    # ─────────────────────────────────────
    # 기본 DB 로드/저장
    # ─────────────────────────────────────
    def load(self) -> Dict[str, Any]:
        """DB 로드, 없으면 기본 구조 생성."""
        with self.lock:
            if not self.db_path.exists():
                self.data = self._default_db()
                self._save_locked()
            else:
                with self.db_path.open("r", encoding="utf-8") as f:
                    self.data = json.load(f)

        return self.data

    def save(self) -> bool:
        """DB 저장 (자동 백업 포함)."""
        with self.lock:
            self._update_metadata()
            self._backup_file(self.db_path)
            self._save_locked()
            return True

    def _save_locked(self) -> None:
        with self.db_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _backup_file(self, path: Path) -> None:
        if path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            path.replace(backup_path)

    def _default_db(self) -> Dict[str, Any]:
        return {
            "tracks": {},
            "metadata": {
                "total_tracks": 0,
                "last_updated": self._now(),
                "version": "1.0",
            },
        }

    # ─────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────
    def get_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        return self.data.get("tracks", {}).get(track_id)

    def get_all_tracks(self) -> List[Dict[str, Any]]:
        return list(self.data.get("tracks", {}).values())

    def add_track(self, track_id: str, initial_data: Optional[Dict[str, Any]] = None) -> bool:
        if track_id in self.data.get("tracks", {}):
            logger.debug("Track %s already exists; skipping add.", track_id)
            return False

        track_data = self._default_track(track_id)
        if initial_data:
            self._deep_update(track_data, initial_data)

        self.data.setdefault("tracks", {})[track_id] = track_data
        self._update_metadata()
        return self.save()

    def update_track(self, track_id: str, updates: Dict[str, Any]) -> bool:
        track = self.get_track(track_id)
        if track is None:
            logger.warning("Track %s not found for update.", track_id)
            return False

        self._deep_update(track, updates)
        track["updated_at"] = self._now()
        return self.save()

    def update_status(self, track_id: str, stage: str, status: str) -> bool:
        track = self.get_track(track_id)
        if track is None:
            logger.warning("Track %s not found for status update.", track_id)
            return False

        stage_section = track.get(stage, {})
        stage_section["status"] = status
        stage_section.setdefault("updated_at", self._now())
        track[stage] = stage_section
        track["updated_at"] = self._now()
        return self.save()

    def delete_track(self, track_id: str) -> bool:
        if track_id not in self.data.get("tracks", {}):
            logger.debug("Track %s does not exist; skipping delete.", track_id)
            return False

        del self.data["tracks"][track_id]
        self._update_metadata()
        return self.save()

    def get_tracks_by_status(self, stage: str, status: str) -> List[Dict[str, Any]]:
        return [
            track
            for track in self.data.get("tracks", {}).values()
            if track.get(stage, {}).get("status") == status
        ]

    # ─────────────────────────────────────
    # 에러 로그
    # ─────────────────────────────────────
    def add_error_log(self, track_id: str, stage: str, error_message: str) -> bool:
        track = self.get_track(track_id)
        if track is None:
            logger.warning("Track %s not found for error logging.", track_id)
            return False

        entry = {
            "timestamp": self._now(),
            "stage": stage,
            "message": error_message,
        }
        error_log = track.setdefault("error_log", [])
        error_log.append(entry)
        track["error_log"] = error_log[-10:]
        return self.save()

    def get_error_log(self, track_id: str) -> List[Dict[str, Any]]:
        track = self.get_track(track_id)
        if track is None:
            return []
        return track.get("error_log", [])

    def clear_error_log(self, track_id: str) -> bool:
        track = self.get_track(track_id)
        if track is None:
            return False
        track["error_log"] = []
        return self.save()

    # ─────────────────────────────────────
    # 실패 작업 관리
    # ─────────────────────────────────────
    def _load_failed_tasks(self) -> Dict[str, Any]:
        with self.failed_lock:
            if not self.failed_tasks_path.exists():
                self.failed_tasks = {"failed_tasks": [], "last_updated": self._now()}
                self._save_failed_locked()
            else:
                with self.failed_tasks_path.open("r", encoding="utf-8") as f:
                    self.failed_tasks = json.load(f)
        return self.failed_tasks

    def _save_failed_locked(self) -> None:
        with self.failed_tasks_path.open("w", encoding="utf-8") as f:
            json.dump(self.failed_tasks, f, indent=2, ensure_ascii=False)

    def add_failed_task(self, track_id: str, stage: str, error: str) -> bool:
        with self.failed_lock:
            self._load_failed_tasks()
            failed_entry = {
                "track_id": track_id,
                "stage": stage,
                "failed_at": self._now(),
                "error_message": error,
                "retry_count": 0,
            }
            self.failed_tasks.setdefault("failed_tasks", []).append(failed_entry)
            self.failed_tasks["last_updated"] = self._now()
            self._save_failed_locked()
        return True

    def get_failed_tasks(self) -> List[Dict[str, Any]]:
        self._load_failed_tasks()
        return self.failed_tasks.get("failed_tasks", [])

    def remove_failed_task(self, track_id: str, stage: str) -> bool:
        with self.failed_lock:
            self._load_failed_tasks()
            tasks = self.failed_tasks.get("failed_tasks", [])
            filtered = [t for t in tasks if not (t.get("track_id") == track_id and t.get("stage") == stage)]
            self.failed_tasks["failed_tasks"] = filtered
            self.failed_tasks["last_updated"] = self._now()
            self._save_failed_locked()
        return True

    def retry_all_failed(self) -> Dict[str, Any]:
        """실패 작업 목록을 반환하고 목록을 초기화한다."""
        with self.failed_lock:
            self._load_failed_tasks()
            tasks = self.failed_tasks.get("failed_tasks", [])
            result = {"retried": tasks, "count": len(tasks)}
            self.failed_tasks = {"failed_tasks": [], "last_updated": self._now()}
            self._save_failed_locked()
        return result

    # ─────────────────────────────────────
    # 체크포인트 관리
    # ─────────────────────────────────────
    def save_checkpoint(self, stage: str, track_id: str, completed: List[str], pending: List[str]) -> bool:
        checkpoint = {
            "is_running": True,
            "started_at": self._now(),
            "current_stage": stage,
            "current_track_id": track_id,
            "completed_tracks": completed,
            "pending_tracks": pending,
            "last_updated": self._now(),
        }
        with self.checkpoint_lock:
            self._backup_file(self.checkpoint_path)
            with self.checkpoint_path.open("w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2, ensure_ascii=False)
        return True

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        if not self.checkpoint_path.exists():
            return None
        with self.checkpoint_lock:
            with self.checkpoint_path.open("r", encoding="utf-8") as f:
                return json.load(f)

    def clear_checkpoint(self) -> bool:
        with self.checkpoint_lock:
            if self.checkpoint_path.exists():
                self.checkpoint_path.unlink()
        return True

    def has_checkpoint(self) -> bool:
        return self.checkpoint_path.exists()

    # ─────────────────────────────────────
    # 통계
    # ─────────────────────────────────────
    def get_statistics(self) -> Dict[str, Any]:
        tracks = self.data.get("tracks", {})
        stats = {
            "total_tracks": len(tracks),
            "music": {"completed": 0, "pending": 0, "failed": 0},
            "image": {"completed": 0, "pending": 0, "failed": 0},
            "video": {"completed": 0, "pending": 0, "failed": 0},
            "fully_completed": 0,
        }

        for track in tracks.values():
            for stage in ("music", "image", "video"):
                status = track.get(stage, {}).get("status")
                if status in stats[stage]:
                    stats[stage][status] += 1

            if all(track.get(stage, {}).get("status") == "completed" for stage in ("music", "image", "video")):
                stats["fully_completed"] += 1

        return stats

    # ─────────────────────────────────────
    # 유틸
    # ─────────────────────────────────────
    def _update_metadata(self) -> None:
        metadata = self.data.setdefault("metadata", {})
        metadata["total_tracks"] = len(self.data.get("tracks", {}))
        metadata["last_updated"] = self._now()
        metadata.setdefault("version", "1.0")

    def _default_track(self, track_id: str) -> Dict[str, Any]:
        return {
            "track_id": track_id,
            "created_at": self._now(),
            "updated_at": self._now(),
            "music": {
                "status": "pending",
                "file_path": None,
                "suno_task_id": None,
                "suno_prompt": None,
                "duration_seconds": None,
                "generated_at": None,
            },
            "image": {
                "status": "pending",
                "file_path": None,
                "prompt_used": None,
                "style": None,
                "resolution": None,
                "format": None,
                "generated_at": None,
            },
            "video": {
                "status": "pending",
                "file_path": None,
                "resolution": None,
                "generated_at": None,
            },
            "thumbnail": {
                "status": "pending",
                "file_path": None,
            },
            "error_log": [],
            "retry_count": 0,
        }

    def _deep_update(self, target: Dict[str, Any], updates: Dict[str, Any]) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    db = TrackDB()
    db.add_track("track_001")
    db.update_status("track_001", "music", "completed")
    print(db.get_statistics())
