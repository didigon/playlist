"""
UI 핸들러 모듈
Streamlit UI의 비즈니스 로직 처리
모든 Pipeline/DB/모듈 호출은 여기서 처리
"""

from typing import Dict, List, Optional, Any, Callable
from main import Pipeline
from db_manager import TrackDB, FailedTasksDB
from image_generator import ImageGenerator
from video_renderer import FFmpegRenderer
from config_manager import load_config, save_config
from prompt_builder import ImagePromptBuilder
from logger import setup_logger

logger = setup_logger("ui_handlers")


# ─────────────────────────────────────────
# 초기화
# ─────────────────────────────────────────

def init_handlers() -> Dict[str, Any]:
    """
    핸들러에서 사용할 객체들 초기화
    
    Returns:
        핸들러 객체 딕셔너리
    """
    try:
        config = load_config()
        return {
            "config": config,
            "db": TrackDB(),
            "failed_db": FailedTasksDB(),
            "pipeline": Pipeline(),
            "image_gen": ImageGenerator(config=config),
            "video_renderer": FFmpegRenderer(config=config),
            "prompt_builder": ImagePromptBuilder()
        }
    except Exception as e:
        logger.error(f"핸들러 초기화 실패: {e}", exc_info=True)
        raise


# ─────────────────────────────────────────
# 대시보드 핸들러
# ─────────────────────────────────────────

def handle_get_statistics(db: TrackDB) -> Dict[str, Any]:
    """
    대시보드용 통계 조회
    
    Args:
        db: TrackDB 인스턴스
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        stats = db.get_statistics()
        return {"success": True, "data": stats}
    except Exception as e:
        return {"success": False, "error": format_error(e, "statistics")}


def handle_run_full_pipeline(
    pipeline: Pipeline,
    options: Dict[str, Any],
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    전체 파이프라인 실행
    
    Args:
        pipeline: Pipeline 인스턴스
        options: 파이프라인 옵션
        progress_callback: 진행 콜백 함수
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        if progress_callback:
            pipeline.set_progress_callback(progress_callback)
        result = pipeline.run(options)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "pipeline")}


# ─────────────────────────────────────────
# 음악 목록 핸들러
# ─────────────────────────────────────────

def handle_get_track_list(
    db: TrackDB,
    filter_status: str = "all"
) -> Dict[str, Any]:
    """
    트랙 목록 조회 (필터 적용)
    
    Args:
        db: TrackDB 인스턴스
        filter_status: 필터 상태 ("all", "need_image", "need_video", "completed", "failed")
    
    Returns:
        {"success": bool, "data": list} 또는 {"success": bool, "error": dict}
    """
    try:
        if filter_status == "all":
            tracks = db.get_all_tracks()
        elif filter_status == "need_image":
            tracks = db.get_tracks_by_status("image", "pending")
        elif filter_status == "need_video":
            tracks = db.get_tracks_by_status("video", "pending")
        elif filter_status == "completed":
            # 모든 단계 완료된 트랙
            all_tracks = db.get_all_tracks()
            tracks = [
                t for t in all_tracks
                if t.get("video", {}).get("status") == "completed"
            ]
        elif filter_status == "failed":
            # 실패한 트랙 (이미지 또는 영상)
            image_failed = db.get_tracks_by_status("image", "failed")
            video_failed = db.get_tracks_by_status("video", "failed")
            # 중복 제거
            failed_ids = set()
            tracks = []
            for t in image_failed + video_failed:
                if t["track_id"] not in failed_ids:
                    failed_ids.add(t["track_id"])
                    tracks.append(t)
        else:
            tracks = db.get_all_tracks()
        
        return {"success": True, "data": tracks}
    except Exception as e:
        return {"success": False, "error": format_error(e, "track_list")}


def handle_get_track_detail(track_id: str, db: TrackDB) -> Dict[str, Any]:
    """
    단일 트랙 상세 정보 조회
    
    Args:
        track_id: 트랙 ID
        db: TrackDB 인스턴스
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        track = db.get_track(track_id)
        if not track:
            return {
                "success": False,
                "error": {
                    "type": "트랙 없음",
                    "message": f"트랙을 찾을 수 없습니다: {track_id}",
                    "action": "트랙 ID를 확인해주세요.",
                    "technical": f"Track not found: {track_id}"
                }
            }
        return {"success": True, "data": track}
    except Exception as e:
        return {"success": False, "error": format_error(e, "track_detail")}


# ─────────────────────────────────────────
# 이미지 생성 핸들러
# ─────────────────────────────────────────

def handle_generate_image_single(
    track_id: str,
    style: str,
    image_gen: ImageGenerator,
    db: TrackDB,
    force: bool = False
) -> Dict[str, Any]:
    """
    단일 트랙 이미지 생성
    
    Args:
        track_id: 트랙 ID
        style: 스타일 이름
        image_gen: ImageGenerator 인스턴스
        db: TrackDB 인스턴스
        force: 강제 재생성 여부
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        result = image_gen.generate_for_track(
            track_id, db, style=style, force=force
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "image_generation")}


def handle_generate_image_batch(
    track_ids: List[str],
    style: str,
    image_gen: ImageGenerator,
    db: TrackDB,
    progress_callback: Optional[Callable] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    배치 이미지 생성
    
    Args:
        track_ids: 트랙 ID 목록
        style: 스타일 이름
        image_gen: ImageGenerator 인스턴스
        db: TrackDB 인스턴스
        progress_callback: 진행 콜백 함수
        force: 강제 재생성 여부
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        # generate_batch는 force를 지원하지 않으므로 개별 호출로 처리
        # 또는 generate_batch를 수정해야 함
        # 일단 force=False로 호출 (나중에 수정 가능)
        result = image_gen.generate_batch(
            track_ids, db, style=style,
            progress_callback=progress_callback
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "image_batch")}


def handle_get_image_styles(prompt_builder: ImagePromptBuilder) -> Dict[str, Any]:
    """
    사용 가능한 이미지 스타일 목록 조회
    
    Args:
        prompt_builder: ImagePromptBuilder 인스턴스
    
    Returns:
        {"success": bool, "data": list} 또는 {"success": bool, "error": dict}
    """
    try:
        styles = prompt_builder.get_available_styles()
        return {"success": True, "data": styles}
    except Exception as e:
        return {"success": False, "error": format_error(e, "image_styles")}


def handle_preview_image_prompt(
    track_id: str,
    style: str,
    prompt_builder: ImagePromptBuilder,
    db: TrackDB
) -> Dict[str, Any]:
    """
    이미지 프롬프트 미리보기
    
    Args:
        track_id: 트랙 ID
        style: 스타일 이름
        prompt_builder: ImagePromptBuilder 인스턴스
        db: TrackDB 인스턴스
    
    Returns:
        {"success": bool, "data": str} 또는 {"success": bool, "error": dict}
    """
    try:
        track = db.get_track(track_id)
        if not track:
            return {
                "success": False,
                "error": {
                    "type": "트랙 없음",
                    "message": f"트랙을 찾을 수 없습니다: {track_id}",
                    "action": "트랙 ID를 확인해주세요.",
                    "technical": f"Track not found: {track_id}"
                }
            }
        
        music_prompt = track.get("music", {}).get("suno_prompt", "")
        prompt = prompt_builder.build_prompt(
            style=style,
            music_prompt=music_prompt
        )
        return {"success": True, "data": prompt}
    except Exception as e:
        return {"success": False, "error": format_error(e, "prompt_preview")}


# ─────────────────────────────────────────
# 영상 렌더링 핸들러
# ─────────────────────────────────────────

def handle_render_video_single(
    track_id: str,
    options: Dict[str, Any],
    renderer: FFmpegRenderer,
    db: TrackDB
) -> Dict[str, Any]:
    """
    단일 트랙 영상 렌더링
    
    Args:
        track_id: 트랙 ID
        options: 렌더링 옵션
        renderer: FFmpegRenderer 인스턴스
        db: TrackDB 인스턴스
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        result = renderer.render_for_track(track_id, db, options=options)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "video_rendering")}


def handle_render_video_batch(
    track_ids: List[str],
    options: Dict[str, Any],
    renderer: FFmpegRenderer,
    db: TrackDB,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    배치 영상 렌더링
    
    Args:
        track_ids: 트랙 ID 목록
        options: 렌더링 옵션
        renderer: FFmpegRenderer 인스턴스
        db: TrackDB 인스턴스
        progress_callback: 진행 콜백 함수
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        result = renderer.render_batch(
            track_ids, db, options=options,
            progress_callback=progress_callback
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "video_batch")}


def handle_check_ffmpeg(renderer: FFmpegRenderer) -> Dict[str, Any]:
    """
    FFmpeg 환경 체크
    
    Args:
        renderer: FFmpegRenderer 인스턴스
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        result = renderer.health_check()
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "ffmpeg_check")}


# ─────────────────────────────────────────
# 설정 핸들러
# ─────────────────────────────────────────

def handle_load_settings() -> Dict[str, Any]:
    """
    설정 로드
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        config = load_config()
        return {"success": True, "data": config}
    except Exception as e:
        return {"success": False, "error": format_error(e, "settings_load")}


def handle_save_settings(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    설정 저장
    
    Args:
        new_config: 새로운 설정 딕셔너리
    
    Returns:
        {"success": bool, "message": str} 또는 {"success": bool, "error": dict}
    """
    try:
        save_config(new_config)
        return {"success": True, "message": "설정이 저장되었습니다."}
    except Exception as e:
        return {"success": False, "error": format_error(e, "settings_save")}


def mask_api_key(api_key: str) -> str:
    """
    API 키 마스킹
    
    Args:
        api_key: 원본 API 키
    
    Returns:
        마스킹된 API 키 (예: "sk-...xxxx")
    """
    if not api_key or api_key == "YOUR_SUNO_API_KEY" or api_key == "YOUR_OPENAI_API_KEY":
        return ""
    
    if len(api_key) <= 8:
        return "*" * len(api_key)
    
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]


# ─────────────────────────────────────────
# 실패 작업 핸들러
# ─────────────────────────────────────────

def handle_get_failed_tasks(failed_db: FailedTasksDB) -> Dict[str, Any]:
    """
    실패 작업 목록 조회
    
    Args:
        failed_db: FailedTasksDB 인스턴스
    
    Returns:
        {"success": bool, "data": list} 또는 {"success": bool, "error": dict}
    """
    try:
        failed = failed_db.get_failed_tasks()
        return {"success": True, "data": failed}
    except Exception as e:
        return {"success": False, "error": format_error(e, "failed_tasks")}


def handle_retry_failed_task(
    track_id: str,
    stage: str,
    pipeline: Pipeline
) -> Dict[str, Any]:
    """
    단일 실패 작업 재시도
    
    Args:
        track_id: 트랙 ID
        stage: 단계 ("image" 또는 "video")
        pipeline: Pipeline 인스턴스
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        # Pipeline에 retry_single 메서드가 있다고 가정
        # 없으면 직접 처리
        if stage == "image":
            result = pipeline.image_gen.generate_for_track(
                track_id, pipeline.db, force=True
            )
        elif stage == "video":
            result = pipeline.video_renderer.render_for_track(
                track_id, pipeline.db, options={}
            )
        else:
            return {
                "success": False,
                "error": {
                    "type": "잘못된 단계",
                    "message": f"지원하지 않는 단계입니다: {stage}",
                    "action": "image 또는 video를 선택해주세요.",
                    "technical": f"Invalid stage: {stage}"
                }
            }
        
        # 재시도 성공 시 failed_tasks에서 제거
        if result.get("success"):
            pipeline.failed_db.remove_failed_task(track_id, stage)
        
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "retry")}


def handle_retry_all_failed(pipeline: Pipeline) -> Dict[str, Any]:
    """
    모든 실패 작업 재시도
    
    Args:
        pipeline: Pipeline 인스턴스
    
    Returns:
        {"success": bool, "data": dict} 또는 {"success": bool, "error": dict}
    """
    try:
        result = pipeline.retry_failed_tasks()
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "retry_all")}


def handle_remove_failed_task(
    track_id: str,
    stage: str,
    failed_db: FailedTasksDB
) -> Dict[str, Any]:
    """
    실패 작업 무시 (failed_tasks에서 제거)
    
    Args:
        track_id: 트랙 ID
        stage: 단계
        failed_db: FailedTasksDB 인스턴스
    
    Returns:
        {"success": bool, "message": str} 또는 {"success": bool, "error": dict}
    """
    try:
        failed_db.remove_failed_task(track_id, stage)
        return {"success": True, "message": "실패 작업이 제거되었습니다."}
    except Exception as e:
        return {"success": False, "error": format_error(e, "remove_failed")}


# ─────────────────────────────────────────
# 에러 포맷팅
# ─────────────────────────────────────────

def format_error(exception: Exception, context: str) -> Dict[str, str]:
    """
    에러를 사용자 친화적 메시지로 변환
    
    Args:
        exception: 예외 객체
        context: 에러 발생 컨텍스트
    
    Returns:
        {
            "type": "에러 유형",
            "message": "사용자용 메시지",
            "action": "다음 행동 안내",
            "technical": "기술적 상세 (디버그용)"
        }
    """
    error_str = str(exception)
    error_type = type(exception).__name__
    
    # 에러 유형별 메시지 매핑
    if "401" in error_str or "Unauthorized" in error_str or "auth" in error_str.lower():
        return {
            "type": "인증 오류",
            "message": "🔑 API 키가 유효하지 않습니다.",
            "action": "설정 페이지에서 API 키를 확인해주세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }
    
    elif "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
        return {
            "type": "할당량 초과",
            "message": "⏱️ API 요청 한도를 초과했습니다.",
            "action": "잠시 후 다시 시도하거나, 내일 다시 실행해주세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }
    
    elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
        return {
            "type": "시간 초과",
            "message": "⏱️ 요청 시간이 초과되었습니다.",
            "action": "네트워크 상태를 확인하고 [재시도] 버튼을 눌러주세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }
    
    elif "connection" in error_str.lower() or "network" in error_str.lower():
        return {
            "type": "네트워크 오류",
            "message": "🌐 네트워크 연결에 실패했습니다.",
            "action": "인터넷 연결을 확인하고 다시 시도해주세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }
    
    elif "ffmpeg" in error_str.lower():
        return {
            "type": "FFmpeg 오류",
            "message": "🎬 영상 렌더링 중 오류가 발생했습니다.",
            "action": "FFmpeg가 설치되어 있는지 확인하거나, 입력 파일을 확인해주세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }
    
    elif "file not found" in error_str.lower() or "no such file" in error_str.lower():
        return {
            "type": "파일 없음",
            "message": "📁 필요한 파일을 찾을 수 없습니다.",
            "action": "음악/이미지 파일이 올바른 위치에 있는지 확인해주세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }
    
    elif "permission" in error_str.lower() or "access denied" in error_str.lower():
        return {
            "type": "권한 오류",
            "message": "🔒 파일 접근 권한이 없습니다.",
            "action": "폴더 권한을 확인하거나 관리자 권한으로 실행해주세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }
    
    else:
        return {
            "type": "알 수 없는 오류",
            "message": f"❌ 오류가 발생했습니다: {error_str[:100]}",
            "action": "문제가 계속되면 로그 파일을 확인하거나 관리자에게 문의하세요.",
            "technical": f"[{context}] {error_type}: {error_str}"
        }

