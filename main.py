"""
전체 파이프라인 오케스트레이션 모듈
음악 생성 → 이미지 생성 → 영상 렌더링 전체 플로우 관리
"""

import os
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from config_manager import load_config
from db_manager import TrackDB, FailedTasksDB, CheckpointDB
from music_scanner import MusicScanner
from suno_client import SunoClient
from image_generator import ImageGenerator
from video_renderer import FFmpegRenderer
from metadata import update_all_metadata
from logger import setup_logger


class Pipeline:
    """전체 파이프라인 오케스트레이터"""
    
    def __init__(self, config_path: str = "./config.json"):
        """
        Pipeline 초기화
        
        Args:
            config_path: 설정 파일 경로
        """
        self.config = load_config(config_path)
        self.logger = setup_logger("pipeline")
        
        # 모듈 초기화
        self.db = TrackDB()
        self.failed_db = FailedTasksDB()
        self.checkpoint_db = CheckpointDB()
        self.scanner = MusicScanner(db=self.db)
        self.suno = SunoClient(config=self.config)
        self.image_gen = ImageGenerator(config=self.config)
        self.video_renderer = FFmpegRenderer(config=self.config)
        
        # 진행 콜백
        self.progress_callback: Optional[Callable] = None
        
        # 환경 체크
        self._check_environment()
    
    def _check_environment(self) -> None:
        """환경 체크 (FFmpeg 등)"""
        # FFmpeg 체크
        health = self.video_renderer.health_check()
        if not health["ready"]:
            self.logger.warning(f"FFmpeg 환경 체크 실패: {health}")
        else:
            self.logger.info(f"FFmpeg 환경 체크 통과: 버전 {health.get('version', 'N/A')}")
    
    def set_progress_callback(self, callback: Callable) -> None:
        """
        진행 콜백 설정
        
        Args:
            callback: 콜백 함수 (stage, current, total, track_id, eta_seconds, message)
        """
        self.progress_callback = callback
    
    def _report_progress(
        self,
        stage: str,
        current: int,
        total: int,
        track_id: Optional[str] = None,
        message: Optional[str] = None
    ) -> None:
        """
        진행 상황 리포트
        
        Args:
            stage: 단계 이름
            current: 현재 진행 수
            total: 전체 수
            track_id: 현재 처리 중인 트랙 ID
            message: 추가 메시지
        """
        if self.progress_callback:
            elapsed = time.time() - getattr(self, '_start_time', time.time())
            eta = self._calculate_eta(current, total, elapsed)
            self.progress_callback(stage, current, total, track_id, eta, message)
        
        # 콘솔 출력
        progress_pct = (current / total * 100) if total > 0 else 0
        status_msg = f"[{stage}] {current}/{total} ({progress_pct:.1f}%)"
        if track_id:
            status_msg += f" - {track_id}"
        if message:
            status_msg += f" - {message}"
        self.logger.info(status_msg)
    
    def _calculate_eta(self, current: int, total: int, elapsed: float) -> float:
        """
        예상 남은 시간 계산
        
        Args:
            current: 현재 진행 수
            total: 전체 수
            elapsed: 경과 시간(초)
        
        Returns:
            예상 남은 시간(초)
        """
        if current == 0:
            return 0.0
        
        avg_time_per_item = elapsed / current
        remaining = total - current
        return avg_time_per_item * remaining
    
    def _save_checkpoint(self, stage: str, track_id: str, completed: List[str], pending: List[str]) -> None:
        """현재 진행 상태 저장"""
        self.checkpoint_db.save_checkpoint(stage, track_id, completed, pending)
    
    def _load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """저장된 checkpoint 로드"""
        return self.checkpoint_db.load()
    
    def _clear_checkpoint(self) -> None:
        """정상 완료 시 checkpoint 삭제"""
        self.checkpoint_db.clear_checkpoint()
    
    def has_incomplete_run(self) -> bool:
        """미완료 실행이 있는지 확인"""
        return self.checkpoint_db.has_checkpoint()
    
    def _handle_track_error(
        self,
        track_id: str,
        stage: str,
        error: Exception
    ) -> None:
        """
        트랙 에러 처리
        
        Args:
            track_id: 트랙 ID
            stage: 단계 (music/image/video)
            error: 발생한 예외
        """
        error_msg = str(error)
        self.logger.error(f"[{stage}] 트랙 {track_id} 처리 실패: {error_msg}", exc_info=True)
        
        # DB에 에러 기록
        self.db.add_error_log(track_id, stage, error_msg)
        self.db.update_status(track_id, stage, "failed")
        
        # 실패 작업 DB에 추가
        track = self.db.get_track(track_id)
        retry_count = track.get("retry_count", 0) if track else 0
        self.failed_db.add_failed_task(track_id, stage, error_msg, retry_count)
    
    def run(
        self,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        전체 파이프라인 실행
        
        Args:
            options: {
                "skip_music": False,      # Suno 생성 스킵
                "skip_images": False,     # 이미지 생성 스킵
                "skip_videos": False,     # 영상 렌더링 스킵
                "force": False,           # 기존 결과물 무시
                "limit": None,            # 처리 개수 제한
                "style": "default",       # 이미지 스타일
                "auto_resume": False      # 자동 재개 (CLI용)
            }
        
        Returns:
            실행 결과 딕셔너리
        """
        if options is None:
            options = {}
        
        self._start_time = time.time()
        started_at = datetime.now().isoformat()
        
        # 미완료 작업 확인
        if self.has_incomplete_run() and not options.get("auto_resume", False):
            checkpoint = self._load_checkpoint()
            if checkpoint:
                self.logger.warning(f"미완료 작업 발견: {checkpoint.get('current_stage')} 단계")
                # CLI에서는 자동 재개, UI에서는 확인 필요
                if not options.get("auto_resume", False):
                    self.logger.info("--resume 옵션으로 재개할 수 있습니다.")
                    return {
                        "success": False,
                        "error": "미완료 작업이 있습니다. --resume 옵션을 사용하세요.",
                        "checkpoint": checkpoint
                    }
        
        # 재개 모드
        if options.get("auto_resume", False) or options.get("resume", False):
            return self.resume_from_checkpoint(options)
        
        # 새로 시작
        stages_result = {}
        
        try:
            # 1. 스캔 단계
            self.logger.info("=" * 60)
            self.logger.info("1. 스캔 단계 시작")
            self.logger.info("=" * 60)
            
            scan_result = self.scanner.full_scan_and_sync()
            stages_result["scan"] = {
                "tracks_found": scan_result["total_music_files"],
                "new_registered": scan_result["new_tracks_registered"],
                "missing_files": scan_result["missing_files_found"]
            }
            
            # 메타데이터 업데이트
            self.logger.info("메타데이터 업데이트 중...")
            metadata_result = update_all_metadata(self.db)
            stages_result["scan"]["metadata_updated"] = metadata_result.get("updated", 0)
            
            # 스캔 완료 checkpoint 저장
            all_tracks = self.db.get_all_tracks()
            track_ids = [t["track_id"] for t in all_tracks]
            self._save_checkpoint("scan", "", track_ids, [])
            
            # 2. 음악 생성 단계 (옵션)
            if not options.get("skip_music", False):
                self.logger.info("=" * 60)
                self.logger.info("2. 음악 생성 단계 시작")
                self.logger.info("=" * 60)
                
                # TODO: Suno API로 음악 생성 (현재는 스킵)
                stages_result["music"] = {
                    "generated": 0,
                    "skipped": scan_result["total_music_files"],
                    "failed": 0
                }
                self.logger.info("음악 생성 단계 스킵 (Suno API 연동 필요)")
            else:
                stages_result["music"] = {"generated": 0, "skipped": 0, "failed": 0}
            
            # 3. 이미지 생성 단계
            if not options.get("skip_images", False):
                self.logger.info("=" * 60)
                self.logger.info("3. 이미지 생성 단계 시작")
                self.logger.info("=" * 60)
                
                style = options.get("style", "default")
                force = options.get("force", False)
                
                # 이미지가 필요한 트랙 필터
                tracks_needing_image = self.scanner.get_tracks_needing_image()
                track_ids = [t["track_id"] for t in tracks_needing_image]
                
                # 개수 제한
                if options.get("limit"):
                    track_ids = track_ids[:options["limit"]]
                
                if track_ids:
                    # 진행 콜백 래퍼 (checkpoint 저장 포함)
                    completed_tracks = []
                    
                    def image_progress(current, total, track_id, status):
                        self._report_progress("images", current, total, track_id, status)
                        # Checkpoint 저장 (주기적)
                        if status == "success":
                            completed_tracks.append(track_id)
                        pending_tracks = [tid for tid in track_ids if tid not in completed_tracks]
                        if current % 5 == 0 or current == total:  # 5개마다 또는 완료 시
                            self._save_checkpoint("images", track_id or "", completed_tracks, pending_tracks)
                    
                    result = self.image_gen.generate_batch(
                        track_ids,
                        self.db,
                        style=style,
                        progress_callback=image_progress
                    )
                    
                    # 실패한 트랙에 대해 에러 처리
                    if result.get("results"):
                        for r in result["results"]:
                            if not r.get("success") and not r.get("skipped"):
                                try:
                                    self._handle_track_error(
                                        r.get("track_id", "unknown"),
                                        "image",
                                        Exception(r.get("error", "Unknown error"))
                                    )
                                except Exception as e:
                                    self.logger.warning(f"에러 처리 실패: {e}")
                    
                    stages_result["images"] = {
                        "generated": result["successful"],
                        "skipped": result["skipped"],
                        "failed": result["failed"]
                    }
                else:
                    stages_result["images"] = {"generated": 0, "skipped": 0, "failed": 0}
                    self.logger.info("이미지 생성 대기 트랙 없음")
            else:
                stages_result["images"] = {"generated": 0, "skipped": 0, "failed": 0}
            
            # 4. 영상 렌더링 단계
            if not options.get("skip_videos", False):
                self.logger.info("=" * 60)
                self.logger.info("4. 영상 렌더링 단계 시작")
                self.logger.info("=" * 60)
                
                # 영상이 필요한 트랙 필터
                tracks_needing_video = self.scanner.get_tracks_needing_video()
                track_ids = [t["track_id"] for t in tracks_needing_video]
                
                # 개수 제한
                if options.get("limit"):
                    track_ids = track_ids[:options["limit"]]
                
                if track_ids:
                    render_options = {
                        "quality": options.get("quality", "normal"),
                        "generate_thumbnail": True
                    }
                    
                    if options.get("force"):
                        render_options["force"] = True
                    
                    # 진행 콜백 래퍼 (checkpoint 저장 포함)
                    completed_tracks = []
                    
                    def video_progress(current, total, track_id, status, eta):
                        self._report_progress("videos", current, total, track_id, f"{status} (ETA: {int(eta)}초)")
                        # Checkpoint 저장 (주기적)
                        if status == "success":
                            completed_tracks.append(track_id)
                        pending_tracks = [tid for tid in track_ids if tid not in completed_tracks]
                        if current % 5 == 0 or current == total:  # 5개마다 또는 완료 시
                            self._save_checkpoint("videos", track_id or "", completed_tracks, pending_tracks)
                    
                    result = self.video_renderer.render_batch(
                        track_ids,
                        self.db,
                        options=render_options,
                        progress_callback=video_progress
                    )
                    
                    # 실패한 트랙에 대해 에러 처리
                    if result.get("results"):
                        for r in result["results"]:
                            if not r.get("success") and not r.get("skipped"):
                                try:
                                    self._handle_track_error(
                                        r.get("track_id", "unknown"),
                                        "video",
                                        Exception(r.get("error", "Unknown error"))
                                    )
                                except Exception as e:
                                    self.logger.warning(f"에러 처리 실패: {e}")
                    
                    stages_result["videos"] = {
                        "rendered": result["successful"],
                        "skipped": result["skipped"],
                        "failed": result["failed"]
                    }
                else:
                    stages_result["videos"] = {"rendered": 0, "skipped": 0, "failed": 0}
                    self.logger.info("영상 렌더링 대기 트랙 없음")
            else:
                stages_result["videos"] = {"rendered": 0, "skipped": 0, "failed": 0}
            
            # 5. 완료 및 리포트
            finished_at = datetime.now().isoformat()
            duration_seconds = time.time() - self._start_time
            
            # 최종 요약
            stats = self.db.get_statistics()
            summary = {
                "fully_completed": stats["fully_completed"],
                "pending": stats["total_tracks"] - stats["fully_completed"],
                "failed": len(self.failed_db.get_failed_tasks())
            }
            
            result = {
                "success": True,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": duration_seconds,
                "stages": stages_result,
                "summary": summary
            }
            
            # 리포트 생성 및 출력
            report = self._generate_report(result)
            self._print_report(report)
            self._save_report(report)
            
            # Checkpoint 정리
            self._clear_checkpoint()
            
            return result
        
        except KeyboardInterrupt:
            self.logger.warning("사용자에 의해 중단됨")
            # 현재 상태를 checkpoint로 저장
            try:
                # 현재 처리 중인 단계와 트랙 정보 추출
                current_stage = "unknown"
                current_track_id = ""
                completed_tracks = []
                pending_tracks = []
                
                # stages_result에서 완료된 트랙 추출
                if "images" in stages_result:
                    current_stage = "images"
                    # 이미지 생성 중이었다면 track_ids에서 추출
                elif "videos" in stages_result:
                    current_stage = "videos"
                
                # Checkpoint 저장
                self._save_checkpoint(current_stage, current_track_id, completed_tracks, pending_tracks)
                self.logger.info(f"중단 상태를 checkpoint로 저장했습니다. --resume 옵션으로 재개할 수 있습니다.")
            except Exception as e:
                self.logger.error(f"Checkpoint 저장 실패: {e}")
            
            return {
                "success": False,
                "error": "사용자 중단",
                "interrupted": True
            }
        except Exception as e:
            self.logger.error(f"파이프라인 실행 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "stages": stages_result
            }
    
    def resume_from_checkpoint(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        checkpoint에서 재개
        
        Args:
            options: 실행 옵션
        
        Returns:
            실행 결과
        """
        checkpoint = self._load_checkpoint()
        if not checkpoint:
            return {
                "success": False,
                "error": "재개할 checkpoint가 없습니다."
            }
        
        self.logger.info(f"Checkpoint에서 재개: {checkpoint.get('current_stage')} 단계")
        
        # checkpoint 정보 출력
        self.logger.info(f"시작 시간: {checkpoint.get('started_at')}")
        self.logger.info(f"완료된 트랙: {len(checkpoint.get('completed_tracks', []))}개")
        self.logger.info(f"대기 중인 트랙: {len(checkpoint.get('pending_tracks', []))}개")
        
        # 재개 옵션 설정
        if options is None:
            options = {}
        
        resume_stage = checkpoint.get("current_stage")
        completed_tracks = set(checkpoint.get("completed_tracks", []))
        pending_tracks = checkpoint.get("pending_tracks", [])
        
        self._start_time = time.time()
        started_at = datetime.now().isoformat()
        stages_result = {}
        
        try:
            # checkpoint의 단계부터 재개
            if resume_stage == "scan":
                # 스캔 단계부터 재개 (전체 재실행)
                self.logger.info("스캔 단계부터 재개 (전체 재실행)")
                self._clear_checkpoint()
                return self.run(options)
            
            elif resume_stage == "images":
                # 이미지 생성 단계부터 재개
                self.logger.info("=" * 60)
                self.logger.info("3. 이미지 생성 단계 재개")
                self.logger.info("=" * 60)
                
                # 완료된 트랙 제외하고 재개
                remaining_tracks = [tid for tid in pending_tracks if tid not in completed_tracks]
                
                if remaining_tracks:
                    style = options.get("style", "default")
                    completed_list = list(completed_tracks)
                    
                    def image_progress(current, total, track_id, status):
                        self._report_progress("images", current, total, track_id, status)
                        if status == "success":
                            completed_list.append(track_id)
                        pending_list = [tid for tid in remaining_tracks if tid not in completed_list]
                        if current % 5 == 0 or current == total:
                            self._save_checkpoint("images", track_id or "", completed_list, pending_list)
                    
                    result = self.image_gen.generate_batch(
                        remaining_tracks,
                        self.db,
                        style=style,
                        progress_callback=image_progress
                    )
                    
                    # 실패한 트랙에 대해 에러 처리
                    if result.get("results"):
                        for r in result["results"]:
                            if not r.get("success") and not r.get("skipped"):
                                try:
                                    self._handle_track_error(
                                        r.get("track_id", "unknown"),
                                        "image",
                                        Exception(r.get("error", "Unknown error"))
                                    )
                                except Exception as e:
                                    self.logger.warning(f"에러 처리 실패: {e}")
                    
                    stages_result["images"] = {
                        "generated": result["successful"],
                        "skipped": result["skipped"],
                        "failed": result["failed"]
                    }
                else:
                    stages_result["images"] = {"generated": 0, "skipped": 0, "failed": 0}
                    self.logger.info("재개할 이미지 생성 트랙 없음")
                
                # 영상 렌더링 단계도 계속 진행
                if not options.get("skip_videos", False):
                    self.logger.info("=" * 60)
                    self.logger.info("4. 영상 렌더링 단계 시작")
                    self.logger.info("=" * 60)
                    
                    tracks_needing_video = self.scanner.get_tracks_needing_video()
                    video_track_ids = [t["track_id"] for t in tracks_needing_video]
                    
                    if video_track_ids:
                        render_options = {
                            "quality": options.get("quality", "normal"),
                            "generate_thumbnail": True
                        }
                        
                        completed_video = []
                        
                        def video_progress(current, total, track_id, status, eta):
                            self._report_progress("videos", current, total, track_id, f"{status} (ETA: {int(eta)}초)")
                            if status == "success":
                                completed_video.append(track_id)
                            pending_video = [tid for tid in video_track_ids if tid not in completed_video]
                            if current % 5 == 0 or current == total:
                                self._save_checkpoint("videos", track_id or "", completed_video, pending_video)
                        
                        result = self.video_renderer.render_batch(
                            video_track_ids,
                            self.db,
                            options=render_options,
                            progress_callback=video_progress
                        )
                        
                        if result.get("results"):
                            for r in result["results"]:
                                if not r.get("success") and not r.get("skipped"):
                                    try:
                                        self._handle_track_error(
                                            r.get("track_id", "unknown"),
                                            "video",
                                            Exception(r.get("error", "Unknown error"))
                                        )
                                    except Exception as e:
                                        self.logger.warning(f"에러 처리 실패: {e}")
                        
                        stages_result["videos"] = {
                            "rendered": result["successful"],
                            "skipped": result["skipped"],
                            "failed": result["failed"]
                        }
                    else:
                        stages_result["videos"] = {"rendered": 0, "skipped": 0, "failed": 0}
                
                # 스캔 단계 결과 추가 (재개이므로 스킵)
                stages_result["scan"] = {"tracks_found": 0, "new_registered": 0, "missing_files": 0, "metadata_updated": 0}
                stages_result["music"] = {"generated": 0, "skipped": 0, "failed": 0}
            
            elif resume_stage == "videos":
                # 영상 렌더링 단계부터 재개
                self.logger.info("=" * 60)
                self.logger.info("4. 영상 렌더링 단계 재개")
                self.logger.info("=" * 60)
                
                remaining_tracks = [tid for tid in pending_tracks if tid not in completed_tracks]
                
                if remaining_tracks:
                    render_options = {
                        "quality": options.get("quality", "normal"),
                        "generate_thumbnail": True
                    }
                    
                    completed_list = list(completed_tracks)
                    
                    def video_progress(current, total, track_id, status, eta):
                        self._report_progress("videos", current, total, track_id, f"{status} (ETA: {int(eta)}초)")
                        if status == "success":
                            completed_list.append(track_id)
                        pending_list = [tid for tid in remaining_tracks if tid not in completed_list]
                        if current % 5 == 0 or current == total:
                            self._save_checkpoint("videos", track_id or "", completed_list, pending_list)
                    
                    result = self.video_renderer.render_batch(
                        remaining_tracks,
                        self.db,
                        options=render_options,
                        progress_callback=video_progress
                    )
                    
                    if result.get("results"):
                        for r in result["results"]:
                            if not r.get("success") and not r.get("skipped"):
                                try:
                                    self._handle_track_error(
                                        r.get("track_id", "unknown"),
                                        "video",
                                        Exception(r.get("error", "Unknown error"))
                                    )
                                except Exception as e:
                                    self.logger.warning(f"에러 처리 실패: {e}")
                    
                    stages_result["videos"] = {
                        "rendered": result["successful"],
                        "skipped": result["skipped"],
                        "failed": result["failed"]
                    }
                else:
                    stages_result["videos"] = {"rendered": 0, "skipped": 0, "failed": 0}
                
                # 이전 단계 결과 추가 (재개이므로 스킵)
                stages_result["scan"] = {"tracks_found": 0, "new_registered": 0, "missing_files": 0, "metadata_updated": 0}
                stages_result["music"] = {"generated": 0, "skipped": 0, "failed": 0}
                stages_result["images"] = {"generated": 0, "skipped": 0, "failed": 0}
            
            # 완료 및 리포트
            finished_at = datetime.now().isoformat()
            duration_seconds = time.time() - self._start_time
            
            stats = self.db.get_statistics()
            summary = {
                "fully_completed": stats["fully_completed"],
                "pending": stats["total_tracks"] - stats["fully_completed"],
                "failed": len(self.failed_db.get_failed_tasks())
            }
            
            result = {
                "success": True,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": duration_seconds,
                "stages": stages_result,
                "summary": summary,
                "resumed": True
            }
            
            report = self._generate_report(result)
            self._print_report(report)
            self._save_report(report)
            
            # Checkpoint 정리
            self._clear_checkpoint()
            
            return result
        
        except Exception as e:
            self.logger.error(f"재개 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "stages": stages_result
            }
    
    def run_stage(self, stage: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        특정 단계만 실행
        
        Args:
            stage: "scan" | "music" | "images" | "videos"
            options: 해당 단계 옵션
        
        Returns:
            실행 결과
        """
        if options is None:
            options = {}
        
        self._start_time = time.time()
        started_at = datetime.now().isoformat()
        
        try:
            if stage == "scan":
                return self.run_scan_only()
            elif stage == "music":
                return self.run_music_only(options)
            elif stage == "images":
                style = options.get("style", "default")
                return self.run_images_only(style, options)
            elif stage == "videos":
                return self.run_videos_only(options)
            else:
                return {
                    "success": False,
                    "error": f"알 수 없는 단계: {stage}"
                }
        except Exception as e:
            self.logger.error(f"단계 실행 실패 ({stage}): {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "stage": stage
            }
    
    def run_scan_only(self) -> Dict[str, Any]:
        """스캔만 실행"""
        self.logger.info("스캔 단계만 실행")
        
        result = self.scanner.full_scan_and_sync()
        metadata_result = update_all_metadata(self.db)
        
        return {
            "success": True,
            "stage": "scan",
            "tracks_found": result["total_music_files"],
            "new_registered": result["new_tracks_registered"],
            "metadata_updated": metadata_result.get("updated", 0)
        }
    
    def run_images_only(self, style: str = "default", options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """이미지 생성만 실행"""
        if options is None:
            options = {}
        
        self.logger.info(f"이미지 생성 단계만 실행 (스타일: {style})")
        
        result = self.image_gen.generate_all_pending(self.db, style=style)
        
        return {
            "success": True,
            "stage": "images",
            "total": result["total"],
            "successful": result["successful"],
            "failed": result["failed"],
            "skipped": result["skipped"]
        }
    
    def run_videos_only(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """영상 렌더링만 실행"""
        if options is None:
            options = {}
        
        self.logger.info("영상 렌더링 단계만 실행")
        
        render_options = {
            "quality": options.get("quality", "normal"),
            "generate_thumbnail": True
        }
        
        result = self.video_renderer.render_all_pending(self.db, options=render_options)
        
        return {
            "success": True,
            "stage": "videos",
            "total": result["total"],
            "successful": result["successful"],
            "failed": result["failed"],
            "skipped": result["skipped"]
        }
    
    def run_music_only(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """음악 생성만 실행 (현재는 스킵)"""
        self.logger.info("음악 생성 단계 (현재 구현되지 않음)")
        return {
            "success": True,
            "stage": "music",
            "generated": 0,
            "skipped": 0,
            "failed": 0,
            "message": "Suno API 연동 필요"
        }
    
    def retry_failed_tasks(self, stage: Optional[str] = None) -> Dict[str, Any]:
        """
        실패한 작업 재시도
        
        Args:
            stage: 특정 단계만 재시도, None이면 전체
        
        Returns:
            재시도 결과
        """
        failed_tasks = self.failed_db.get_failed_tasks()
        
        if stage:
            failed_tasks = [t for t in failed_tasks if t.get("stage") == stage]
        
        if not failed_tasks:
            return {
                "success": True,
                "total": 0,
                "retried": 0,
                "message": "재시도할 실패 작업이 없습니다."
            }
        
        self.logger.info(f"실패 작업 재시도 시작: {len(failed_tasks)}개")
        
        retried = 0
        results = []
        
        for task in failed_tasks:
            track_id = task["track_id"]
            task_stage = task["stage"]
            
            try:
                # stage 이름 정규화 (image/images 일관성)
                normalized_stage = "image" if task_stage in ("image", "images") else task_stage
                
                if normalized_stage == "image":
                    result = self.image_gen.generate_for_track(track_id, self.db, style="default", force=True)
                    if result["success"]:
                        self.failed_db.remove_failed_task(track_id, task_stage)
                        retried += 1
                elif normalized_stage == "video":
                    result = self.video_renderer.render_for_track(track_id, self.db, options={"force": True})
                    if result["success"]:
                        self.failed_db.remove_failed_task(track_id, task_stage)
                        retried += 1
                
                results.append({
                    "track_id": track_id,
                    "stage": task_stage,
                    "success": result.get("success", False)
                })
            except Exception as e:
                self.logger.error(f"재시도 실패 ({track_id}, {task_stage}): {e}")
                results.append({
                    "track_id": track_id,
                    "stage": task_stage,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "total": len(failed_tasks),
            "retried": retried,
            "results": results
        }
    
    def get_failed_summary(self) -> Dict[str, Any]:
        """실패 작업 요약"""
        failed_tasks = self.failed_db.get_failed_tasks()
        
        summary = {
            "total": len(failed_tasks),
            "by_stage": {}
        }
        
        for task in failed_tasks:
            stage = task.get("stage", "unknown")
            if stage not in summary["by_stage"]:
                summary["by_stage"][stage] = 0
            summary["by_stage"][stage] += 1
        
        return summary
    
    def _generate_report(self, result: Dict[str, Any]) -> str:
        """
        실행 리포트 생성
        
        Args:
            result: 실행 결과 딕셔너리
        
        Returns:
            포맷된 리포트 문자열
        """
        lines = []
        lines.append("=" * 60)
        lines.append("  SUNO VIDEO FACTORY - 실행 리포트")
        lines.append("=" * 60)
        
        # 실행 시간
        started = result.get("started_at", "")
        finished = result.get("finished_at", "")
        duration = result.get("duration_seconds", 0)
        duration_str = f"{int(duration // 3600)}시간 {int((duration % 3600) // 60)}분 {int(duration % 60)}초"
        
        lines.append(f"  실행 시간: {started} ~ {finished} ({duration_str})")
        lines.append("=" * 60)
        lines.append("")
        
        # 스캔 결과
        stages = result.get("stages", {})
        scan = stages.get("scan", {})
        lines.append("📁 스캔 결과")
        lines.append(f"   - 음악 파일: {scan.get('tracks_found', 0)}개")
        lines.append(f"   - 신규 등록: {scan.get('new_registered', 0)}개")
        lines.append(f"   - 메타데이터 업데이트: {scan.get('metadata_updated', 0)}개")
        lines.append("")
        
        # 음악 생성
        music = stages.get("music", {})
        lines.append("🎵 음악 생성")
        lines.append(f"   - 생성: {music.get('generated', 0)}개")
        lines.append(f"   - 스킵: {music.get('skipped', 0)}개")
        lines.append(f"   - 실패: {music.get('failed', 0)}개")
        lines.append("")
        
        # 이미지 생성
        images = stages.get("images", {})
        lines.append("🖼️ 이미지 생성")
        lines.append(f"   - 성공: {images.get('generated', 0)}개")
        lines.append(f"   - 스킵: {images.get('skipped', 0)}개")
        lines.append(f"   - 실패: {images.get('failed', 0)}개")
        lines.append("")
        
        # 영상 렌더링
        videos = stages.get("videos", {})
        lines.append("🎬 영상 렌더링")
        lines.append(f"   - 성공: {videos.get('rendered', 0)}개")
        lines.append(f"   - 스킵: {videos.get('skipped', 0)}개")
        lines.append(f"   - 실패: {videos.get('failed', 0)}개")
        lines.append("")
        
        # 최종 요약
        summary = result.get("summary", {})
        lines.append("=" * 60)
        lines.append("📊 최종 요약")
        lines.append(f"   - 완전 완료: {summary.get('fully_completed', 0)}개")
        lines.append(f"   - 진행 중: {summary.get('pending', 0)}개")
        lines.append(f"   - 실패: {summary.get('failed', 0)}개")
        lines.append("")
        
        # 실패 목록
        failed_tasks = self.failed_db.get_failed_tasks()
        if failed_tasks:
            lines.append("⚠️ 실패 목록")
            for task in failed_tasks[:10]:  # 최대 10개만 표시
                lines.append(f"   - {task['track_id']}: {task['stage']} 실패 ({task.get('error_message', 'N/A')[:50]})")
            if len(failed_tasks) > 10:
                lines.append(f"   ... 외 {len(failed_tasks) - 10}개")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _print_report(self, report: str) -> None:
        """콘솔에 리포트 출력"""
        print("\n" + report + "\n")
    
    def _save_report(self, report: str, filename: Optional[str] = None) -> str:
        """
        리포트 파일 저장
        
        Args:
            report: 리포트 문자열
            filename: 파일명 (None이면 자동 생성)
        
        Returns:
            저장된 파일 경로
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pipeline_report_{timestamp}.txt"
        
        log_folder = Path(self.config.get("paths", {}).get("log_folder", "./logs"))
        log_folder.mkdir(parents=True, exist_ok=True)
        
        report_path = log_folder / filename
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            self.logger.info(f"리포트 저장 완료: {report_path}")
            return str(report_path)
        except Exception as e:
            self.logger.error(f"리포트 저장 실패: {e}")
            return ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Suno Video Factory 파이프라인")
    
    # 실행 옵션
    parser.add_argument("--only-images", action="store_true", help="이미지 생성만 실행")
    parser.add_argument("--only-videos", action="store_true", help="영상 렌더링만 실행")
    parser.add_argument("--only-scan", action="store_true", help="스캔만 실행")
    parser.add_argument("--style", type=str, default="default", help="이미지 스타일")
    parser.add_argument("--force", action="store_true", help="기존 결과물 무시하고 재생성")
    parser.add_argument("--limit", type=int, help="처리 개수 제한")
    parser.add_argument("--quality", type=str, default="normal", help="영상 품질 (fast/normal/high)")
    
    # 재시도 및 상태
    parser.add_argument("--retry-failed", action="store_true", help="실패 작업 재시도")
    parser.add_argument("--status", action="store_true", help="현재 상태 확인")
    parser.add_argument("--resume", action="store_true", help="미완료 작업 재개")
    parser.add_argument("--dry-run", action="store_true", help="실제 실행 안 함 (미리보기)")
    
    args = parser.parse_args()
    
    pipeline = Pipeline()
    
    if args.status:
        # 상태 확인
        stats = pipeline.db.get_statistics()
        failed_summary = pipeline.get_failed_summary()
        
        print("\n📊 현재 상태")
        print("=" * 60)
        print(f"전체 트랙: {stats['total_tracks']}개")
        print(f"  - 음악 완료: {stats['music']['completed']}개")
        print(f"  - 이미지 완료: {stats['image']['completed']}개")
        print(f"  - 영상 완료: {stats['video']['completed']}개")
        print(f"  - 전체 완료: {stats['fully_completed']}개")
        print(f"\n실패 작업: {failed_summary['total']}개")
        if failed_summary['by_stage']:
            for stage, count in failed_summary['by_stage'].items():
                print(f"  - {stage}: {count}개")
        
        if pipeline.has_incomplete_run():
            checkpoint = pipeline._load_checkpoint()
            print(f"\n⚠️ 미완료 작업 발견: {checkpoint.get('current_stage')} 단계")
            print("   --resume 옵션으로 재개할 수 있습니다.")
        print("=" * 60)
    
    elif args.retry_failed:
        # 실패 작업 재시도
        print("\n🔄 실패 작업 재시도 시작...")
        result = pipeline.retry_failed_tasks()
        print(f"\n✅ 재시도 완료!")
        print(f"  - 전체: {result['total']}개")
        print(f"  - 성공: {result['retried']}개")
    
    elif args.only_scan:
        # 스캔만 실행
        result = pipeline.run_scan_only()
        if result["success"]:
            print(f"\n✅ 스캔 완료!")
            print(f"  - 음악 파일: {result['tracks_found']}개")
            print(f"  - 신규 등록: {result['new_registered']}개")
    
    elif args.only_images:
        # 이미지 생성만
        options = {"style": args.style}
        if args.force:
            options["force"] = True
        if args.limit:
            options["limit"] = args.limit
        
        result = pipeline.run_images_only(args.style, options)
        if result["success"]:
            print(f"\n✅ 이미지 생성 완료!")
            print(f"  - 전체: {result['total']}개")
            print(f"  - 성공: {result['successful']}개")
            print(f"  - 실패: {result['failed']}개")
            print(f"  - 스킵: {result['skipped']}개")
    
    elif args.only_videos:
        # 영상 렌더링만
        options = {"quality": args.quality}
        if args.force:
            options["force"] = True
        if args.limit:
            options["limit"] = args.limit
        
        result = pipeline.run_videos_only(options)
        if result["success"]:
            print(f"\n✅ 영상 렌더링 완료!")
            print(f"  - 전체: {result['total']}개")
            print(f"  - 성공: {result['successful']}개")
            print(f"  - 실패: {result['failed']}개")
            print(f"  - 스킵: {result['skipped']}개")
    
    elif args.dry_run:
        # Dry run
        print("\n🔍 Dry Run 모드 (실제 실행 안 함)")
        stats = pipeline.db.get_statistics()
        scanner = pipeline.scanner
        
        tracks_needing_image = scanner.get_tracks_needing_image()
        tracks_needing_video = scanner.get_tracks_needing_video()
        
        print(f"\n처리 예정:")
        print(f"  - 이미지 생성: {len(tracks_needing_image)}개")
        print(f"  - 영상 렌더링: {len(tracks_needing_video)}개")
        
        if args.limit:
            print(f"\n⚠️ 제한 적용: 최대 {args.limit}개만 처리")
    
    elif args.resume:
        # 재개
        options = {
            "auto_resume": True,
            "style": args.style,
            "quality": args.quality
        }
        if args.force:
            options["force"] = True
        if args.limit:
            options["limit"] = args.limit
        
        result = pipeline.run(options)
        if not result.get("success"):
            print(f"\n❌ 재개 실패: {result.get('error')}")
    
    else:
        # 전체 파이프라인 실행
        options = {
            "style": args.style,
            "quality": args.quality
        }
        if args.force:
            options["force"] = True
        if args.limit:
            options["limit"] = args.limit
        
        result = pipeline.run(options)
        
        if not result.get("success"):
            print(f"\n❌ 파이프라인 실행 실패: {result.get('error')}")

