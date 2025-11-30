"""
Streamlit UI 애플리케이션
음악 → 이미지 → 영상 파이프라인 관리 인터페이스
"""

import streamlit as st
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from ui_handlers import (
    init_handlers,
    handle_get_statistics,
    handle_run_full_pipeline,
    handle_get_track_list,
    handle_get_track_detail,
    handle_generate_image_single,
    handle_generate_image_batch,
    handle_get_image_styles,
    handle_preview_image_prompt,
    handle_render_video_single,
    handle_render_video_batch,
    handle_check_ffmpeg,
    handle_load_settings,
    handle_save_settings,
    handle_get_failed_tasks,
    handle_retry_failed_task,
    handle_retry_all_failed,
    handle_remove_failed_task,
    mask_api_key
)


# 페이지 설정
st.set_page_config(
    page_title="Suno Video Factory",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ─────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────

@st.cache_resource
def get_handlers():
    """핸들러 객체 캐시"""
    return init_handlers()


def format_duration(seconds: float) -> str:
    """초를 MM:SS 형식으로 변환"""
    if seconds is None:
        return "00:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def format_file_size(size_bytes: float) -> str:
    """바이트를 MB 형식으로 변환"""
    if size_bytes is None:
        return "0 MB"
    size_mb = size_bytes / (1024 * 1024)
    return f"{size_mb:.1f} MB"


def format_eta(eta_seconds: float) -> str:
    """ETA를 읽기 쉬운 형식으로 변환"""
    if eta_seconds is None or eta_seconds < 0:
        return "계산 중..."
    
    if eta_seconds < 60:
        return f"{int(eta_seconds)}초"
    elif eta_seconds < 3600:
        minutes = int(eta_seconds // 60)
        seconds = int(eta_seconds % 60)
        return f"{minutes}분 {seconds}초"
    else:
        hours = int(eta_seconds // 3600)
        minutes = int((eta_seconds % 3600) // 60)
        return f"{hours}시간 {minutes}분"


# ─────────────────────────────────────────
# 대시보드 페이지
# ─────────────────────────────────────────

def render_dashboard():
    """대시보드 페이지 렌더링"""
    st.title("📊 대시보드")
    
    handlers = get_handlers()
    
    # 통계 조회
    result = handle_get_statistics(handlers["db"])
    
    if not result["success"]:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        st.info(f"💡 {error['action']}")
        return
    
    stats = result["data"]
    
    # 통계 카드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total = stats.get("total_tracks", 0)
        st.metric("🎵 전체 트랙", total)
    
    with col2:
        music_completed = stats.get("music", {}).get("completed", 0)
        music_total = stats.get("music", {}).get("completed", 0) + stats.get("music", {}).get("pending", 0)
        st.metric("🖼️ 이미지", f"{music_completed}/{music_total}")
    
    with col3:
        image_completed = stats.get("image", {}).get("completed", 0)
        image_total = stats.get("image", {}).get("completed", 0) + stats.get("image", {}).get("pending", 0)
        st.metric("🎬 영상", f"{image_completed}/{image_total}")
    
    with col4:
        fully_completed = stats.get("fully_completed", 0)
        st.metric("✅ 완료", fully_completed)
    
    st.divider()
    
    # 파이프라인 실행 버튼
    st.subheader("🚀 파이프라인 실행")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ 전체 실행", type="primary", use_container_width=True):
            run_pipeline_with_progress({})
    
    with col2:
        if st.button("🖼️ 이미지만", use_container_width=True):
            run_pipeline_with_progress({"skip_music": True, "skip_videos": True})
    
    with col3:
        if st.button("🎬 영상만", use_container_width=True):
            run_pipeline_with_progress({"skip_music": True, "skip_images": True})
    
    st.divider()
    
    # 실패 작업 표시
    render_failed_tasks_section(handlers)
    
    # 최근 활동 (간단한 요약)
    st.subheader("📜 상태 요약")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**음악 상태**")
        music_stats = stats.get("music", {})
        st.write(f"- 완료: {music_stats.get('completed', 0)}")
        st.write(f"- 대기: {music_stats.get('pending', 0)}")
        st.write(f"- 실패: {music_stats.get('failed', 0)}")
    
    with col2:
        st.write("**이미지 상태**")
        image_stats = stats.get("image", {})
        st.write(f"- 완료: {image_stats.get('completed', 0)}")
        st.write(f"- 대기: {image_stats.get('pending', 0)}")
        st.write(f"- 실패: {image_stats.get('failed', 0)}")


def run_pipeline_with_progress(options: Dict[str, Any]):
    """진행 상황을 표시하며 파이프라인 실행"""
    handlers = get_handlers()
    
    # 세션 상태로 취소 플래그 관리
    if "pipeline_cancelled" not in st.session_state:
        st.session_state.pipeline_cancelled = False
    
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        eta_text = st.empty()
        
        col1, col2 = st.columns([3, 1])
        with col2:
            cancel_button = st.button("❌ 취소", key="cancel_pipeline")
            if cancel_button:
                st.session_state.pipeline_cancelled = True
        
        def progress_callback(stage, current, total, track_id=None, eta=None, message=None):
            # 취소 확인
            if st.session_state.get("pipeline_cancelled", False):
                raise KeyboardInterrupt("사용자 취소")
            
            progress = current / total if total > 0 else 0
            progress_bar.progress(progress)
            
            status_msg = f"[{stage}] "
            if track_id:
                status_msg += f"{track_id} 처리 중... "
            status_msg += f"({current}/{total})"
            if message:
                status_msg += f" - {message}"
            
            status_text.text(status_msg)
            
            if eta is not None:
                eta_text.text(f"예상 남은 시간: {format_eta(eta)}")
        
        try:
            st.session_state.pipeline_cancelled = False
            result = handle_run_full_pipeline(
                handlers["pipeline"],
                options,
                progress_callback=progress_callback
            )
            
            if result["success"]:
                st.success("✅ 파이프라인 실행 완료!")
                display_result_summary(result["data"])
            else:
                error = result["error"]
                st.error(f"{error['type']}: {error['message']}")
                st.info(f"💡 {error['action']}")
        
        except KeyboardInterrupt:
            st.warning("⚠️ 사용자에 의해 취소되었습니다.")
            st.session_state.pipeline_cancelled = False
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
            st.session_state.pipeline_cancelled = False


def display_result_summary(result: Dict[str, Any]):
    """실행 결과 요약 표시"""
    with st.expander("📊 실행 결과 상세"):
        stages = result.get("stages", {})
        
        st.write("**스캔 결과**")
        scan = stages.get("scan", {})
        st.write(f"- 발견된 트랙: {scan.get('tracks_found', 0)}")
        st.write(f"- 신규 등록: {scan.get('new_registered', 0)}")
        
        st.write("**이미지 생성**")
        images = stages.get("images", {})
        st.write(f"- 생성: {images.get('generated', 0)}")
        st.write(f"- 스킵: {images.get('skipped', 0)}")
        st.write(f"- 실패: {images.get('failed', 0)}")
        
        st.write("**영상 렌더링**")
        videos = stages.get("videos", {})
        st.write(f"- 렌더링: {videos.get('rendered', 0)}")
        st.write(f"- 스킵: {videos.get('skipped', 0)}")
        st.write(f"- 실패: {videos.get('failed', 0)}")


# ─────────────────────────────────────────
# 음악 목록 페이지
# ─────────────────────────────────────────

def render_music_list():
    """음악 목록 페이지 렌더링"""
    st.title("🎵 음악 목록")
    
    handlers = get_handlers()
    
    # 필터
    col1, col2 = st.columns([1, 3])
    with col1:
        filter_status = st.selectbox(
            "상태 필터",
            ["all", "need_image", "need_video", "completed", "failed"],
            format_func=lambda x: {
                "all": "전체",
                "need_image": "이미지 필요",
                "need_video": "영상 필요",
                "completed": "완료",
                "failed": "실패"
            }[x]
        )
    
    # 트랙 목록 조회
    result = handle_get_track_list(handlers["db"], filter_status)
    
    if not result["success"]:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        return
    
    tracks = result["data"]
    
    if not tracks:
        st.info("트랙이 없습니다.")
        return
    
    st.write(f"**총 {len(tracks)}개 트랙**")
    
    # 트랙 목록 표시
    for track in tracks:
        track_id = track["track_id"]
        music_info = track.get("music", {})
        image_info = track.get("image", {})
        video_info = track.get("video", {})
        
        duration = music_info.get("duration_seconds", 0)
        
        with st.expander(f"🎵 {track_id} - {format_duration(duration)}"):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                music_status = "✅" if music_info.get("status") == "completed" else "❌"
                image_status = "✅" if image_info.get("status") == "completed" else "❌"
                video_status = "✅" if video_info.get("status") == "completed" else "❌"
                
                st.write(f"**상태:** 음악 {music_status} | 이미지 {image_status} | 영상 {video_status}")
                
                if music_info.get("suno_prompt"):
                    st.caption(f"프롬프트: {music_info['suno_prompt'][:100]}...")
            
            with col2:
                if image_info.get("status") != "completed":
                    if st.button("🖼️ 이미지 생성", key=f"img_{track_id}"):
                        with st.spinner("이미지 생성 중..."):
                            style_result = handle_get_image_styles()
                            if style_result["success"]:
                                styles = style_result["data"]
                                if styles:
                                    result = handle_generate_image_single(
                                        track_id, styles[0], handlers["image_gen"], handlers["db"]
                                    )
                                    if result["success"]:
                                        st.success("이미지 생성 완료!")
                                        st.rerun()
                                    else:
                                        error = result["error"]
                                        st.error(f"{error['message']}")
            
            with col3:
                if image_info.get("status") == "completed" and video_info.get("status") != "completed":
                    if st.button("🎬 영상 생성", key=f"vid_{track_id}"):
                        with st.spinner("영상 렌더링 중..."):
                            result = handle_render_video_single(
                                track_id, {}, handlers["video_renderer"], handlers["db"]
                            )
                            if result["success"]:
                                st.success("영상 생성 완료!")
                                st.rerun()
                            else:
                                error = result["error"]
                                st.error(f"{error['message']}")


# ─────────────────────────────────────────
# 이미지 생성 페이지
# ─────────────────────────────────────────

def render_image_generator():
    """이미지 생성 페이지 렌더링"""
    st.title("🖼️ 이미지 생성")
    
    handlers = get_handlers()
    
    # 스타일 선택
    col1, col2 = st.columns([1, 2])
    
    with col1:
        style_result = handle_get_image_styles(handlers["prompt_builder"])
        if not style_result["success"]:
            st.error("스타일 목록을 불러올 수 없습니다.")
            return
        
        styles = style_result["data"]
        if not styles:
            st.warning("사용 가능한 스타일이 없습니다.")
            return
        
        style = st.selectbox("스타일 선택", styles)
    
    with col2:
        st.info(f"선택된 스타일: **{style}**")
        
        # 프롬프트 미리보기 (예시 트랙)
        preview_track = st.selectbox(
            "프롬프트 미리보기 (트랙 선택)",
            ["없음"] + [t["track_id"] for t in handle_get_track_list(handlers["db"], "all")["data"][:10]]
        )
        
        if preview_track != "없음":
            preview_result = handle_preview_image_prompt(
                preview_track, style, handlers["prompt_builder"], handlers["db"]
            )
            if preview_result["success"]:
                st.text_area("프롬프트 미리보기", preview_result["data"], height=100, disabled=True)
    
    st.divider()
    
    # 대상 트랙 선택
    st.subheader("대상 트랙 선택")
    
    pending_result = handle_get_track_list(handlers["db"], "need_image")
    if not pending_result["success"]:
        st.error("트랙 목록을 불러올 수 없습니다.")
        return
    
    pending_tracks = pending_result["data"]
    
    if not pending_tracks:
        st.info("이미지가 필요한 트랙이 없습니다.")
        return
    
    st.write(f"**{len(pending_tracks)}개 트랙이 이미지를 필요로 합니다.**")
    
    # 체크박스로 선택
    selected = []
    cols = st.columns(5)
    for i, track in enumerate(pending_tracks[:50]):  # 최대 50개만 표시
        with cols[i % 5]:
            if st.checkbox(track["track_id"], key=f"sel_{track['track_id']}"):
                selected.append(track["track_id"])
    
    st.divider()
    
    # 실행 버튼
    col1, col2 = st.columns([1, 3])
    
    with col1:
        force = st.checkbox("강제 재생성", value=False)
        
        if st.button("🖼️ 선택 항목 생성", type="primary", disabled=len(selected) == 0):
            if selected:
                run_image_batch(selected, style, handlers, force)
    
    with col2:
        if st.button("🖼️ 전체 생성"):
            all_ids = [t["track_id"] for t in pending_tracks]
            run_image_batch(all_ids, style, handlers, force)
    
    st.divider()
    
    # 생성된 이미지 갤러리
    st.subheader("생성된 이미지")
    display_image_gallery(handlers["db"])


def run_image_batch(track_ids: List[str], style: str, handlers: Dict, force: bool):
    """배치 이미지 생성 실행"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def progress_callback(current, total, track_id, status):
        progress = current / total if total > 0 else 0
        progress_bar.progress(progress)
        status_text.text(f"처리 중: {track_id} ({current}/{total}) - {status}")
    
    result = handle_generate_image_batch(
        track_ids, style, handlers["image_gen"], handlers["db"],
        progress_callback=progress_callback, force=force
    )
    
    if result["success"]:
        data = result["data"]
        st.success(f"✅ 완료! 성공: {data.get('successful', 0)}, 실패: {data.get('failed', 0)}, 스킵: {data.get('skipped', 0)}")
        st.rerun()
    else:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        st.info(f"💡 {error['action']}")


def display_image_gallery(db):
    """이미지 갤러리 표시"""
    result = handle_get_track_list(db, "all")
    if not result["success"]:
        return
    
    tracks = result["data"]
    image_tracks = [t for t in tracks if t.get("image", {}).get("status") == "completed"]
    
    if not image_tracks:
        st.info("생성된 이미지가 없습니다.")
        return
    
    # 그리드 레이아웃으로 표시
    cols = st.columns(4)
    for i, track in enumerate(image_tracks[:20]):  # 최대 20개만 표시
        with cols[i % 4]:
            image_path = track.get("image", {}).get("file_path")
            if image_path and Path(image_path).exists():
                st.image(image_path, caption=track["track_id"], use_container_width=True)


# ─────────────────────────────────────────
# 영상 렌더링 페이지
# ─────────────────────────────────────────

def render_video_page():
    """영상 렌더링 페이지 렌더링"""
    st.title("🎬 영상 렌더링")
    
    handlers = get_handlers()
    
    # FFmpeg 체크
    ffmpeg_result = handle_check_ffmpeg(handlers["video_renderer"])
    if ffmpeg_result["success"]:
        ffmpeg_info = ffmpeg_result["data"]
        if not ffmpeg_info.get("ready", False):
            st.error("⚠️ FFmpeg가 설치되지 않았거나 준비되지 않았습니다.")
            st.info("FFmpeg를 설치하고 설정 페이지에서 경로를 확인해주세요.")
            return
        else:
            st.success(f"✅ FFmpeg 준비됨 (버전: {ffmpeg_info.get('version', 'Unknown')})")
    
    st.divider()
    
    # 옵션 설정
    st.subheader("렌더링 옵션")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        resolution_option = st.selectbox(
            "해상도",
            ["1920x1080", "1080x1920", "1080x1080"],
            format_func=lambda x: {
                "1920x1080": "1920x1080 (YouTube HD)",
                "1080x1920": "1080x1920 (Shorts)",
                "1080x1080": "1080x1080 (Instagram)"
            }[x]
        )
        
        # 해상도를 튜플로 변환
        resolution_map = {
            "1920x1080": (1920, 1080),
            "1080x1920": (1080, 1920),
            "1080x1080": (1080, 1080)
        }
        resolution = resolution_map[resolution_option]
    
    with col2:
        quality = st.selectbox("품질", ["fast", "normal", "high"])
    
    with col3:
        ken_burns = st.checkbox("Ken Burns 효과")
        generate_thumbnail = st.checkbox("썸네일 생성", value=True)
    
    st.divider()
    
    # 대상 트랙
    st.subheader("렌더링 대상")
    
    pending_result = handle_get_track_list(handlers["db"], "need_video")
    if not pending_result["success"]:
        st.error("트랙 목록을 불러올 수 없습니다.")
        return
    
    pending_tracks = pending_result["data"]
    
    if not pending_tracks:
        st.info("영상이 필요한 트랙이 없습니다.")
        return
    
    st.write(f"**렌더링 대기: {len(pending_tracks)}개**")
    
    # 실행 버튼
    if st.button("🎬 렌더링 시작", type="primary"):
        options = {
            "resolution": resolution,
            "quality": quality,
            "ken_burns": ken_burns,
            "ken_burns_type": "zoom_in" if ken_burns else None,
            "generate_thumbnail": generate_thumbnail
        }
        
        run_video_batch(pending_tracks, options, handlers)
    
    st.divider()
    
    # 완료된 영상 목록
    st.subheader("완료된 영상")
    display_completed_videos(handlers["db"])


def run_video_batch(tracks: List[Dict], options: Dict, handlers: Dict):
    """배치 영상 렌더링 실행"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    track_ids = [t["track_id"] for t in tracks]
    
    def progress_callback(current, total, track_id, status, eta=None):
        progress = current / total if total > 0 else 0
        progress_bar.progress(progress)
        status_text.text(f"처리 중: {track_id} ({current}/{total}) - {status}")
    
    result = handle_render_video_batch(
        track_ids, options, handlers["video_renderer"], handlers["db"],
        progress_callback=progress_callback
    )
    
    if result["success"]:
        data = result["data"]
        st.success(f"✅ 완료! 성공: {data.get('successful', 0)}, 실패: {data.get('failed', 0)}, 스킵: {data.get('skipped', 0)}")
        st.rerun()
    else:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        st.info(f"💡 {error['action']}")


def display_completed_videos(db):
    """완료된 영상 목록 표시"""
    result = handle_get_track_list(db, "completed")
    if not result["success"]:
        return
    
    tracks = result["data"]
    
    if not tracks:
        st.info("완료된 영상이 없습니다.")
        return
    
    st.write(f"**완료된 영상: {len(tracks)}개**")
    
    for track in tracks[:20]:  # 최대 20개만 표시
        video_info = track.get("video", {})
        video_path = video_info.get("file_path")
        
        if video_path:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{track['track_id']}**")
                st.caption(f"경로: {video_path}")
            with col2:
                if Path(video_path).exists():
                    st.success("✅ 파일 존재")
                else:
                    st.warning("⚠️ 파일 없음")


# ─────────────────────────────────────────
# 실패 작업 관리 UI
# ─────────────────────────────────────────

def render_failed_tasks_section(handlers: Dict[str, Any]):
    """실패 작업 섹션 렌더링"""
    failed_result = handle_get_failed_tasks(handlers["failed_db"])
    
    if not failed_result["success"]:
        error = failed_result["error"]
        st.error(f"{error['type']}: {error['message']}")
        return
    
    failed_tasks = failed_result["data"]
    
    if not failed_tasks:
        return
    
    st.subheader("⚠️ 실패한 작업")
    st.warning(f"{len(failed_tasks)}개의 실패한 작업이 있습니다.")
    
    # 전체 재시도 버튼
    if st.button("🔄 전체 재시도", key="retry_all_failed"):
        retry_result = handle_retry_all_failed(handlers["pipeline"])
        if retry_result["success"]:
            st.success("재시도가 시작되었습니다.")
            st.rerun()
        else:
            error = retry_result["error"]
            st.error(f"{error['type']}: {error['message']}")
    
    st.divider()
    
    # 실패 목록 상세 표시
    for task in failed_tasks:
        track_id = task.get("track_id", "unknown")
        stage = task.get("stage", "unknown")
        failed_at = task.get("failed_at", "Unknown")
        error_message = task.get("error_message", "Unknown error")
        retry_count = task.get("retry_count", 0)
        
        with st.expander(f"❌ {track_id} - {stage}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**실패 시간:** {failed_at}")
                st.write(f"**에러 메시지:** {error_message}")
                st.write(f"**재시도 횟수:** {retry_count}")
            
            with col2:
                col_retry, col_ignore = st.columns(2)
                
                with col_retry:
                    if st.button("🔄 재시도", key=f"retry_{track_id}_{stage}"):
                        retry_result = handle_retry_failed_task(
                            track_id, stage, handlers["pipeline"]
                        )
                        if retry_result["success"]:
                            st.success("재시도가 시작되었습니다.")
                            st.rerun()
                        else:
                            error = retry_result["error"]
                            st.error(f"{error['message']}")
                
                with col_ignore:
                    if st.button("🗑️ 무시", key=f"ignore_{track_id}_{stage}"):
                        remove_result = handle_remove_failed_task(
                            track_id, stage, handlers["failed_db"]
                        )
                        if remove_result["success"]:
                            st.success("실패 작업이 제거되었습니다.")
                            st.rerun()
                        else:
                            error = remove_result["error"]
                            st.error(f"{error['message']}")


# ─────────────────────────────────────────
# 설정 페이지
# ─────────────────────────────────────────

def render_settings():
    """설정 페이지 렌더링"""
    st.title("⚙️ 설정")
    
    # 설정 로드
    result = handle_load_settings()
    if not result["success"]:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        return
    
    config = result["data"]
    
    # API 키 설정
    st.subheader("🔑 API 키")
    col1, col2 = st.columns(2)
    
    with col1:
        suno_key = st.text_input(
            "Suno API Key",
            value=mask_api_key(config.get("suno", {}).get("api_key", "")),
            type="password",
            help="Suno API 키를 입력하세요. .env 파일에 저장됩니다."
        )
    
    with col2:
        openai_key = st.text_input(
            "OpenAI API Key",
            value=mask_api_key(config.get("image", {}).get("api_key", "")),
            type="password",
            help="OpenAI API 키를 입력하세요. .env 파일에 저장됩니다."
        )
    
    st.divider()
    
    # 경로 설정
    st.subheader("📁 폴더 경로")
    paths = config.get("paths", {})
    
    music_folder = st.text_input("음악 폴더", paths.get("music_folder", "./music"))
    image_folder = st.text_input("이미지 폴더", paths.get("image_folder", "./images"))
    video_folder = st.text_input("영상 폴더", paths.get("video_folder", "./videos"))
    
    st.divider()
    
    # 파이프라인 설정
    st.subheader("⚡ 파이프라인")
    pipeline_config = config.get("pipeline", {})
    
    retry_count = st.slider(
        "재시도 횟수",
        1, 5,
        pipeline_config.get("auto_retry_count", 3)
    )
    
    retry_delay = st.number_input(
        "재시도 대기 시간 (초)",
        1, 60,
        pipeline_config.get("retry_delay_seconds", 2)
    )
    
    st.divider()
    
    # 저장 버튼
    if st.button("💾 설정 저장", type="primary"):
        # 설정 업데이트 (API 키는 .env에 저장해야 하지만 여기서는 config만 업데이트)
        updated_config = config.copy()
        
        if suno_key and not suno_key.startswith("*"):
            updated_config["suno"]["api_key"] = suno_key
        
        if openai_key and not openai_key.startswith("*"):
            updated_config["image"]["api_key"] = openai_key
        
        updated_config["paths"]["music_folder"] = music_folder
        updated_config["paths"]["image_folder"] = image_folder
        updated_config["paths"]["video_folder"] = video_folder
        
        updated_config["pipeline"]["auto_retry_count"] = retry_count
        updated_config["pipeline"]["retry_delay_seconds"] = retry_delay
        
        save_result = handle_save_settings(updated_config)
        
        if save_result["success"]:
            st.success("✅ 설정이 저장되었습니다.")
            st.info("⚠️ API 키는 .env 파일에 별도로 저장해야 합니다.")
        else:
            error = save_result["error"]
            st.error(f"{error['type']}: {error['message']}")


# ─────────────────────────────────────────
# 메인 함수
# ─────────────────────────────────────────

def main():
    """메인 함수"""
    # 사이드바 네비게이션
    page = st.sidebar.radio(
        "메뉴",
        ["📊 대시보드", "🎵 음악 목록", "🖼️ 이미지 생성", "🎬 영상 렌더링", "⚙️ 설정"],
        label_visibility="collapsed"
    )
    
    # 페이지 렌더링
    if page == "📊 대시보드":
        render_dashboard()
    elif page == "🎵 음악 목록":
        render_music_list()
    elif page == "🖼️ 이미지 생성":
        render_image_generator()
    elif page == "🎬 영상 렌더링":
        render_video_page()
    elif page == "⚙️ 설정":
        render_settings()


if __name__ == "__main__":
    main()

