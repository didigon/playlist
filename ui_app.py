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
    handle_render_combined_video,
    handle_check_ffmpeg,
    handle_load_settings,
    handle_save_settings,
    handle_get_failed_tasks,
    handle_retry_failed_task,
    handle_retry_all_failed,
    handle_remove_failed_task,
    mask_api_key,
    handle_get_suno_credits,
    handle_estimate_suno_cost,
    handle_generate_music,
    handle_get_available_styles,
    handle_auto_build_prompt
)
from mantine_theme import (
    init_theme,
    apply_theme
)


# 페이지 설정
st.set_page_config(
    page_title="Suno Video Factory",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Mantine 테마 초기화 및 적용
init_theme()
apply_theme()


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
    """대시보드 페이지 렌더링 (Mantine 스타일)"""
    # 페이지 제목
    st.markdown('<h1 class="m-title-h1 m-fade-in" style="overflow: visible !important; white-space: normal !important; word-break: keep-all !important; color: #212529 !important;">대시보드</h1>', unsafe_allow_html=True)
    
    handlers = get_handlers()
    
    # 통계 조회
    result = handle_get_statistics(handlers["db"])
    
    if not result["success"]:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        st.info(f"안내: {error['action']}")
        return
    
    stats = result["data"]
    
    # 통계 카드 그리드 (CSS Grid)
    total = stats.get("total_tracks", 0)
    music_completed = stats.get("music", {}).get("completed", 0)
    music_total = stats.get("music", {}).get("completed", 0) + stats.get("music", {}).get("pending", 0)
    image_completed = stats.get("image", {}).get("completed", 0)
    image_total = stats.get("image", {}).get("completed", 0) + stats.get("image", {}).get("pending", 0)
    fully_completed = stats.get("fully_completed", 0)

    metric_cards = [
        {"value": total, "label": "전체 트랙"},
        {"value": f"{music_completed}/{music_total}", "label": "이미지"},
        {"value": f"{image_completed}/{image_total}", "label": "영상"},
        {"value": fully_completed, "label": "완료"},
    ]

    cards_html = "".join(
        f'<div class="m-card m-metric-card"><div class="m-metric"><div class="m-metric-value">{card["value"]}</div><div class="m-metric-label">{card["label"]}</div></div></div>'
        for card in metric_cards
    )

    metrics_html = f'<div class="m-section m-slide-up"><div class="metrics-grid">{cards_html}</div></div>'
    st.markdown(metrics_html, unsafe_allow_html=True)
    st.markdown('<hr class="m-divider">', unsafe_allow_html=True)
    
    # 파이프라인 실행 섹션
    st.markdown('<div class="m-section">', unsafe_allow_html=True)
    st.markdown('<h2 class="m-title-h2" style="overflow: visible !important; white-space: normal !important; word-break: keep-all !important; color: #212529 !important;">파이프라인 실행</h2>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("전체 실행", type="primary", use_container_width=True):
            run_pipeline_with_progress({})
    
    with col2:
        if st.button("이미지만", use_container_width=True):
            run_pipeline_with_progress({"skip_music": True, "skip_videos": True})
    
    with col3:
        if st.button("영상만", use_container_width=True):
            run_pipeline_with_progress({"skip_music": True, "skip_images": True})
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="m-divider">', unsafe_allow_html=True)
    
    # 실패 작업 표시
    render_failed_tasks_section(handlers)
    
    # 상태 요약 섹션
    st.markdown('<div class="m-section">', unsafe_allow_html=True)
    st.markdown('<h2 class="m-title-h2" style="overflow: visible !important; white-space: normal !important; word-break: keep-all !important; color: #212529 !important;">상태 요약</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="m-card" style="overflow: visible !important; width: 100% !important; color: #212529 !important;">', unsafe_allow_html=True)
        st.markdown('<h3 class="m-title-h3" style="overflow: visible !important; white-space: normal !important; word-break: keep-all !important; color: #212529 !important;">음악 상태</h3>', unsafe_allow_html=True)
        music_stats = stats.get("music", {})
        st.write(f"- 완료: **{music_stats.get('completed', 0)}**")
        st.write(f"- 대기: **{music_stats.get('pending', 0)}**")
        st.write(f"- 실패: **{music_stats.get('failed', 0)}**")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="m-card" style="overflow: visible !important; width: 100% !important; color: #212529 !important;">', unsafe_allow_html=True)
        st.markdown('<h3 class="m-title-h3" style="overflow: visible !important; white-space: normal !important; word-break: keep-all !important; color: #212529 !important;">이미지 상태</h3>', unsafe_allow_html=True)
        image_stats = stats.get("image", {})
        st.write(f"- 완료: **{image_stats.get('completed', 0)}**")
        st.write(f"- 대기: **{image_stats.get('pending', 0)}**")
        st.write(f"- 실패: **{image_stats.get('failed', 0)}**")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)


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
            cancel_button = st.button("취소", key="cancel_pipeline")
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
                st.success("파이프라인 실행 완료!")
                display_result_summary(result["data"])
            else:
                error = result["error"]
                st.error(f"{error['type']}: {error['message']}")
                st.info(f"안내: {error['action']}")
        
        except KeyboardInterrupt:
            st.warning("사용자에 의해 취소되었습니다.")
            st.session_state.pipeline_cancelled = False
        except Exception as e:
            st.error(f"오류 발생: {str(e)}")
            st.session_state.pipeline_cancelled = False


def display_result_summary(result: Dict[str, Any]):
    """실행 결과 요약 표시"""
    with st.expander("실행 결과 상세"):
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

def render_music_generation():
    """음악 생성 페이지 렌더링"""
    st.header("Suno 음악 생성")
    
    handlers = get_handlers()
    
    # 크레딧 정보 표시
    credits_result = handle_get_suno_credits()
    if credits_result["success"]:
        credits = credits_result["data"]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("잔여 크레딧", f"{credits['remaining']:,}")
        with col2:
            st.metric("생성 가능", f"{credits['max_songs']}곡")
        with col3:
            cost_per_song = credits['cost_per_song'] * 0.005
            st.metric("곡당 비용", f"${cost_per_song:.3f}")
    else:
        # 크레딧 조회 실패해도 음악 생성은 가능하도록 경고만 표시
        st.warning(f"크레딧 조회 실패: {credits_result['error']['message']}")
        st.info(f"{credits_result['error']['action']}")
        st.info("크레딧 조회는 실패했지만, 음악 생성은 시도할 수 있습니다.")
        # return 제거하여 계속 진행 가능하도록 함
    
    st.divider()
    
    # 한 줄 입력 (자동 프롬프트 생성)
    user_input = st.text_input(
        "음악 설명 (한 줄 입력)",
        placeholder="예: 평화로운 아침의 켈틱 풍 음악",
        help="간단히 입력하면 자동으로 프롬프트를 생성합니다. 예: '편안한 로파이 음악', '에너지 넘치는 일렉트로닉' 등",
        key="music_user_input"
    )
    
    # 자동 프롬프트 생성 여부
    auto_build = st.checkbox(
        "자동 프롬프트 생성 (권장)",
        value=True,
        help="입력한 내용을 기반으로 자동으로 최적화된 프롬프트를 생성합니다",
        key="music_auto_build"
    )
    
    # 생성된 프롬프트 미리보기
    generated_prompt = None
    detected_style = None
    
    if user_input and auto_build:
        # 실시간 프롬프트 생성 (폼 제출 전 미리보기)
        preview_result = handle_auto_build_prompt(user_input)
        if preview_result["success"]:
            preview_data = preview_result["data"]
            generated_prompt = preview_data["prompt"]
            detected_style = preview_data["detected_style"]
            
            with st.expander("📝 생성된 프롬프트 미리보기", expanded=True):
                st.text_area(
                    "프롬프트",
                    value=generated_prompt,
                    height=100,
                    disabled=True,
                    label_visibility="collapsed",
                    key="preview_prompt"
                )
                if detected_style:
                    st.caption(f"🎵 감지된 스타일: **{detected_style}**")
                else:
                    st.caption("🎵 스타일: 자동 (감지되지 않음)")
    
    # 입력 폼
    with st.form("music_generation_form"):
        # 수동 프롬프트 입력 (고급 사용자용)
        manual_prompt = None
        if not auto_build:
            manual_prompt = st.text_area(
                "음악 프롬프트 (수동 입력)",
                placeholder="예: 평화로운 아침의 켈틱 풍 음악, 부드러운 하프와 플루트 선율",
                height=100,
                help="자동 프롬프트 생성을 사용하지 않을 경우 직접 입력하세요"
            )
        
        # 최종 프롬프트 결정 (세션 상태에 저장)
        if auto_build and generated_prompt:
            prompt = generated_prompt
            st.session_state['final_prompt'] = generated_prompt
            st.session_state['final_style'] = detected_style
        elif manual_prompt:
            prompt = manual_prompt
            st.session_state['final_prompt'] = manual_prompt
            st.session_state['final_style'] = None
        else:
            prompt = user_input if user_input else None
            st.session_state['final_prompt'] = prompt
            st.session_state['final_style'] = detected_style
        
        # 옵션 컬럼
        col1, col2 = st.columns(2)
        
        with col1:
            song_count = st.slider(
                "생성할 곡 수",
                min_value=1,
                max_value=30,
                value=2,
                help="1을 선택해도 Suno는 2곡을 생성합니다"
            )
            
            # 실제 생성될 곡 수 표시
            estimate = handle_estimate_suno_cost(song_count)
            if estimate["success"]:
                est = estimate["data"]
                st.caption(
                    f"→ API 요청 {est['requests']}회, "
                    f"실제 {est['actual_songs']}곡 생성, "
                    f"{est['credits']} 크레딧 (${est['cost_usd']:.2f})"
                )
        
        with col2:
            # 스타일 선택
            styles_result = handle_get_available_styles()
            styles = styles_result["data"] if styles_result["success"] else []
            
            # 자동 감지된 스타일이 있으면 기본값으로 설정
            default_style_idx = 0
            if detected_style and detected_style in styles:
                default_style_idx = styles.index(detected_style) + 1
            
            style = st.selectbox(
                "음악 스타일",
                options=["(자동 감지)"] + styles,
                index=default_style_idx,
                help="자동 프롬프트 생성 시 입력 내용에서 스타일을 자동으로 감지합니다"
            )
            if style == "(자동 감지)":
                style = detected_style  # 자동 감지된 스타일 사용
        
        # 고급 옵션
        with st.expander("고급 옵션"):
            col1, col2 = st.columns(2)
            
            with col1:
                model = st.selectbox(
                    "AI 모델",
                    options=["V4_5ALL", "V5", "V4_5PLUS", "V4_5", "V4", "V3_5"],
                    index=0
                )
                
                instrumental = st.checkbox("인스트루멘탈 (보컬 없음)", value=True)
            
            with col2:
                negative_tags = st.text_input(
                    "제외할 스타일",
                    placeholder="예: Heavy Metal, Aggressive"
                )
                if not negative_tags:
                    negative_tags = None
        
        # 생성 버튼
        submitted = st.form_submit_button("음악 생성 시작", type="primary")
    
    # 생성 실행
    if submitted:
        # 세션 상태에서 최종 프롬프트 가져오기
        final_prompt = st.session_state.get('final_prompt')
        final_style = st.session_state.get('final_style')
        
        # 프롬프트 최종 확인 및 생성
        if not final_prompt:
            if not user_input:
                st.error("음악 설명을 입력해주세요.")
                return
            else:
                # 자동 프롬프트 생성 시도
                if auto_build:
                    auto_result = handle_auto_build_prompt(user_input, style=style if style else None)
                    if auto_result["success"]:
                        final_prompt = auto_result["data"]["prompt"]
                        if not style:
                            final_style = auto_result["data"]["detected_style"]
                            style = final_style
                    else:
                        final_prompt = user_input  # 실패 시 원본 사용
                else:
                    st.error("프롬프트를 입력해주세요.")
                    return
        
        # 프롬프트가 생성되었는지 확인
        if not final_prompt or final_prompt.strip() == "":
            st.error("유효한 프롬프트를 생성할 수 없습니다. 다시 입력해주세요.")
            return
        
        # 스타일이 자동 감지된 경우 사용
        if not style and final_style:
            style = final_style
        
        prompt = final_prompt  # 최종 프롬프트 사용
        
        # 진행률 표시
        progress_container = st.container()
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            detail_text = st.empty()
        
        def update_progress(p):
            """진행률 콜백"""
            try:
                from suno_music_generator import GenerationProgress
                if isinstance(p, GenerationProgress):
                    if p.total_songs > 0:
                        progress = p.current_song / p.total_songs
                        progress_bar.progress(progress)
                    
                    status_text.text(f"[{p.stage}] {p.message}")
                    
                    if p.eta_seconds:
                        eta_min = int(p.eta_seconds // 60)
                        eta_sec = int(p.eta_seconds % 60)
                        detail_text.caption(f"예상 남은 시간: {eta_min}분 {eta_sec}초")
            except Exception as e:
                # GenerationProgress가 없어도 동작하도록
                status_text.text(f"진행 중...")
        
        # 생성 실행
        with st.spinner("음악 생성 중..."):
            result = handle_generate_music(
                prompt=prompt,
                song_count=song_count,
                model=model,
                instrumental=instrumental,
                style=style,
                negative_tags=negative_tags,
                progress_callback=update_progress
            )
        
        # 결과 표시
        if result["success"]:
            data = result["data"]
            
            st.success(f"완료! {data['successful_songs']}곡 생성됨")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("성공", f"{data['successful_songs']}곡")
            with col2:
                st.metric("실패", f"{data['failed_songs']}곡")
            with col3:
                st.metric("사용 크레딧", f"{data['credits_used']}")
            
            # 생성된 파일 목록
            if data["saved_files"]:
                st.subheader("생성된 파일")
                for file_path in data["saved_files"]:
                    st.text(f"• {Path(file_path).name}")
            
            # 에러 표시
            if data["errors"]:
                with st.expander("에러 목록"):
                    for error in data["errors"]:
                        st.warning(error)
        else:
            error = result["error"]
            st.error(f"{error['type']}: {error['message']}")
            st.info(f"안내: {error['action']}")


def render_music_list():
    """음악 목록 페이지 렌더링"""
    st.title("음악 목록")
    
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
        
        with st.expander(f"{track_id} - {format_duration(duration)}"):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                music_status = "완료" if music_info.get("status") == "completed" else "대기"
                image_status = "완료" if image_info.get("status") == "completed" else "대기"
                video_status = "완료" if video_info.get("status") == "completed" else "대기"
                
                st.write(f"**상태:** 음악 {music_status} | 이미지 {image_status} | 영상 {video_status}")
                
                if music_info.get("suno_prompt"):
                    st.caption(f"프롬프트: {music_info['suno_prompt'][:100]}...")
            
            with col2:
                if image_info.get("status") != "completed":
                    if st.button("이미지 생성", key=f"img_{track_id}"):
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
                    if st.button("영상 생성", key=f"vid_{track_id}"):
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
    st.title("이미지 생성")
    
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
        
        if st.button("선택 항목 생성", type="primary", disabled=len(selected) == 0):
            if selected:
                run_image_batch(selected, style, handlers, force)
    
    with col2:
        if st.button("전체 생성"):
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
        st.success(f"완료! 성공: {data.get('successful', 0)}, 실패: {data.get('failed', 0)}, 스킵: {data.get('skipped', 0)}")
        st.rerun()
    else:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        st.info(f"안내: {error['action']}")


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
    st.title("영상 렌더링")
    
    handlers = get_handlers()
    
    # FFmpeg 체크
    ffmpeg_result = handle_check_ffmpeg(handlers["video_renderer"])
    if ffmpeg_result["success"]:
        ffmpeg_info = ffmpeg_result["data"]
        if not ffmpeg_info.get("ready", False):
            st.error("FFmpeg가 설치되지 않았거나 준비되지 않았습니다.")
            st.info("FFmpeg를 설치하고 설정 페이지에서 경로를 확인해주세요.")
            return
        else:
            st.success(f"FFmpeg 준비됨 (버전: {ffmpeg_info.get('version', 'Unknown')})")
    
    st.divider()
    
    # 탭으로 개별/통합 영상 생성 구분
    tab1, tab2 = st.tabs(["개별 영상 생성", "통합 영상 생성"])
    
    with tab1:
        render_individual_videos(handlers)
    
    with tab2:
        render_combined_video(handlers)


def render_individual_videos(handlers: Dict):
    """개별 영상 생성 섹션"""
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
            }[x],
            key="individual_resolution"
        )
        
        # 해상도를 튜플로 변환
        resolution_map = {
            "1920x1080": (1920, 1080),
            "1080x1920": (1080, 1920),
            "1080x1080": (1080, 1080)
        }
        resolution = resolution_map[resolution_option]
    
    with col2:
        quality = st.selectbox("품질", ["fast", "normal", "high"], key="individual_quality")
    
    with col3:
        ken_burns = st.checkbox("Ken Burns 효과", key="individual_ken_burns")
        generate_thumbnail = st.checkbox("썸네일 생성", value=True, key="individual_thumbnail")
    
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
    if st.button("렌더링 시작", type="primary"):
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


def render_combined_video(handlers: Dict):
    """통합 영상 생성 섹션 (여러 곡을 하나의 영상으로 합치기)"""
    st.subheader("통합 영상 생성")
    st.info("여러 곡을 하나의 영상으로 합칩니다. 곡이 바뀔 때 이미지도 자동으로 전환됩니다.")
    
    # 렌더링 옵션
    st.markdown("**렌더링 옵션**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        resolution_option = st.selectbox(
            "해상도",
            ["1920x1080", "1080x1920", "1080x1080"],
            format_func=lambda x: {
                "1920x1080": "1920x1080 (YouTube HD)",
                "1080x1920": "1080x1920 (Shorts)",
                "1080x1080": "1080x1080 (Instagram)"
            }[x],
            key="combined_resolution"
        )
        
        # 해상도를 튜플로 변환
        resolution_map = {
            "1920x1080": (1920, 1080),
            "1080x1920": (1080, 1920),
            "1080x1080": (1080, 1080)
        }
        resolution = resolution_map[resolution_option]
    
    with col2:
        quality = st.selectbox("품질", ["fast", "normal", "high"], key="combined_quality")
    
    with col3:
        ken_burns = st.checkbox("Ken Burns 효과", key="combined_ken_burns")
    
    st.divider()
    
    # 완료된 트랙 목록 가져오기 (이미지와 음악이 모두 있는 트랙)
    result = handle_get_track_list(handlers["db"], "completed")
    if not result["success"]:
        st.error("트랙 목록을 불러올 수 없습니다.")
        return
    
    all_tracks = result["data"]
    # 이미지와 음악이 모두 있는 트랙만 필터링
    available_tracks = [
        t for t in all_tracks
        if t.get("image", {}).get("status") == "completed" and
           t.get("music", {}).get("file_path") and
           Path(t.get("music", {}).get("file_path")).exists() and
           t.get("image", {}).get("file_path") and
           Path(t.get("image", {}).get("file_path")).exists()
    ]
    
    if len(available_tracks) < 2:
        st.warning("통합 영상을 만들려면 최소 2개 이상의 완료된 트랙이 필요합니다.")
        return
    
    st.write(f"**사용 가능한 트랙: {len(available_tracks)}개**")
    
    # 트랙 선택 (멀티셀렉트)
    track_options = {f"{t['track_id']} ({t.get('music', {}).get('title', '제목 없음')})": t['track_id'] 
                     for t in available_tracks}
    
    selected_track_labels = st.multiselect(
        "통합 영상에 포함할 트랙 선택 (순서대로)",
        options=list(track_options.keys()),
        help="여러 트랙을 선택하면 순서대로 하나의 영상으로 합쳐집니다. 곡이 바뀔 때 이미지도 자동으로 전환됩니다."
    )
    
    if len(selected_track_labels) < 2:
        st.info("최소 2개 이상의 트랙을 선택해주세요.")
        return
    
    # 선택된 트랙 ID 목록
    selected_track_ids = [track_options[label] for label in selected_track_labels]
    
    # 선택된 트랙 정보 표시
    st.write("**선택된 트랙 순서:**")
    total_duration = 0
    for idx, track_id in enumerate(selected_track_ids, 1):
        track = handlers["db"].get_track(track_id)
        if track:
            music_info = track.get("music", {})
            image_info = track.get("image", {})
            duration = music_info.get("duration_seconds", 0)
            total_duration += duration
            
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"{idx}. {track_id}")
            with col2:
                st.caption(f"제목: {music_info.get('title', '제목 없음')}")
            with col3:
                st.caption(f"길이: {seconds_to_mmss(duration)}")
    
    st.write(f"**총 영상 길이: {seconds_to_mmss(total_duration)}**")
    
    # 출력 파일명
    output_filename = st.text_input(
        "출력 파일명 (선택사항)",
        placeholder="예: my_playlist_20250115",
        help="입력하지 않으면 자동으로 생성됩니다 (combined_YYYYMMDD_HHMMSS.mp4)",
        key="combined_output_filename"
    )
    if not output_filename:
        output_filename = None
    elif not output_filename.endswith('.mp4'):
        output_filename = f"{output_filename}.mp4"
    
    # 생성 버튼
    if st.button("통합 영상 생성 시작", type="primary"):
        options = {
            "resolution": resolution,
            "quality": quality,
            "ken_burns": ken_burns,
            "ken_burns_type": "zoom_in" if ken_burns else None,
            "transition": "cut"  # 곡 전환 방식
        }
        
        run_combined_video(selected_track_ids, output_filename, options, handlers)


def run_combined_video(track_ids: List[str], output_filename: Optional[str], options: Dict, handlers: Dict):
    """통합 영상 생성 실행"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    detail_text = st.empty()
    
    def progress_callback(stage, current, total, track_id, message):
        if total > 0:
            progress = current / total
            progress_bar.progress(progress)
        status_text.text(f"[{stage}] {message}")
        if track_id:
            detail_text.caption(f"처리 중: {track_id}")
    
    result = handle_render_combined_video(
        track_ids=track_ids,
        output_filename=output_filename,
        options=options,
        renderer=handlers["video_renderer"],
        db=handlers["db"],
        progress_callback=progress_callback
    )
    
    if result["success"]:
        data = result["data"]
        st.success("통합 영상 생성 완료!")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("출력 파일", Path(data["output_path"]).name)
        with col2:
            st.metric("총 길이", seconds_to_mmss(data["total_duration"]))
        with col3:
            st.metric("파일 크기", f"{data['file_size_mb']:.1f} MB")
        with col4:
            st.metric("트랙 수", f"{data['tracks_count']}개")
        
        st.write(f"**파일 경로:** `{data['output_path']}`")
        
        # 파일 다운로드 버튼 (선택사항)
        if Path(data["output_path"]).exists():
            with open(data["output_path"], "rb") as f:
                st.download_button(
                    "영상 다운로드",
                    f.read(),
                    file_name=Path(data["output_path"]).name,
                    mime="video/mp4"
                )
    else:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        st.info(f"안내: {error['action']}")


def seconds_to_mmss(seconds: float) -> str:
    """초를 MM:SS 형식으로 변환"""
    if seconds is None:
        return "00:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


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
        st.success(f"완료! 성공: {data.get('successful', 0)}, 실패: {data.get('failed', 0)}, 스킵: {data.get('skipped', 0)}")
        st.rerun()
    else:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        st.info(f"안내: {error['action']}")


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
                    st.success("파일 존재")
                else:
                    st.warning("파일 없음")


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
    
    st.subheader("실패한 작업")
    st.warning(f"{len(failed_tasks)}개의 실패한 작업이 있습니다.")
    
    # 전체 재시도 버튼
    if st.button("전체 재시도", key="retry_all_failed"):
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
        
        with st.expander(f"{track_id} - {stage}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**실패 시간:** {failed_at}")
                st.write(f"**에러 메시지:** {error_message}")
                st.write(f"**재시도 횟수:** {retry_count}")
            
            with col2:
                col_retry, col_ignore = st.columns(2)
                
                with col_retry:
                    if st.button("재시도", key=f"retry_{track_id}_{stage}"):
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
                    if st.button("무시", key=f"ignore_{track_id}_{stage}"):
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
    st.title("설정")
    
    # 설정 로드
    result = handle_load_settings()
    if not result["success"]:
        error = result["error"]
        st.error(f"{error['type']}: {error['message']}")
        return
    
    config = result["data"]
    
    # API 키 설정
    st.subheader("API 키")
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
    st.subheader("폴더 경로")
    
    paths = config.get("paths", {})
    
    # 현재 작업 디렉토리 표시 및 하위 폴더 목록
    import os
    import platform
    current_dir = os.getcwd()
    st.info(f"현재 작업 디렉토리: `{current_dir}`")
    
    # 프로젝트 루트 경로 (웹 호스팅 환경에 맞게)
    project_root = Path(current_dir).absolute()
    
    # 경로 탐색 함수들
    def get_directories(path_str: str):
        """지정된 경로의 상위/하위 디렉토리 목록 반환"""
        try:
            path = Path(path_str)
            
            # 상대 경로를 절대 경로로 변환
            if not path.is_absolute():
                path = (Path(current_dir) / path).resolve()
            
            # 경로가 존재하지 않으면 상위 경로 확인
            if not path.exists():
                path = path.parent
            
            result = {
                'current': str(path.absolute()),
                'parent': str(path.parent.absolute()) if path.parent != path else None,
                'children': []
            }
            
            # 하위 디렉토리 목록
            try:
                for item in path.iterdir():
                    if item.is_dir():
                        result['children'].append(str(item.absolute()))
                result['children'] = sorted(result['children'])
            except (PermissionError, OSError):
                pass
            
            return result
        except Exception:
            # 오류 발생 시 현재 경로를 절대 경로로 변환 시도
            try:
                abs_path = Path(path_str)
                if not abs_path.is_absolute():
                    abs_path = (Path(current_dir) / abs_path).resolve()
                return {'current': str(abs_path), 'parent': None, 'children': []}
            except:
                return {'current': path_str, 'parent': None, 'children': []}
    
    def render_folder_browser(folder_type: str, current_path: str):
        """폴더 탐색 UI 렌더링"""
        # 현재 경로 기준으로 디렉토리 정보 가져오기
        path_info = get_directories(current_path)
        
        # 경로 탐색 UI
        with st.expander("🔍 폴더 찾기", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # 현재 경로 표시
                st.caption(f"현재 경로: `{path_info['current']}`")
            
            with col2:
                # 상위 폴더로 이동 버튼
                if path_info['parent'] and path_info['parent'] != path_info['current']:
                    if st.button("⬆️ 상위 폴더", key=f"{folder_type}_parent", use_container_width=True):
                        st.session_state[f"{folder_type}_input"] = path_info['parent']
                        st.rerun()
            
            # 하위 폴더 목록
            if path_info['children']:
                st.markdown("**하위 폴더:**")
                cols = st.columns(min(3, len(path_info['children'])))
                for idx, child_path in enumerate(path_info['children'][:9]):  # 최대 9개만 표시
                    col_idx = idx % 3
                    with cols[col_idx]:
                        folder_name = Path(child_path).name
                        if st.button(f"📁 {folder_name}", key=f"{folder_type}_child_{idx}", use_container_width=True):
                            st.session_state[f"{folder_type}_input"] = child_path
                            st.rerun()
                
                if len(path_info['children']) > 9:
                    st.caption(f"... 외 {len(path_info['children']) - 9}개 폴더 더 있음")
            else:
                st.info("하위 폴더가 없습니다.")
            
            # 프로젝트 루트로 빠르게 이동
            st.markdown("**빠른 이동:**")
            quick_cols = st.columns(2)
            
            with quick_cols[0]:
                if st.button("📂 프로젝트 루트", key=f"{folder_type}_quick_root", use_container_width=True):
                    st.session_state[f"{folder_type}_input"] = str(project_root)
                    st.rerun()
            
            with quick_cols[1]:
                # 현재 폴더 타입에 맞는 기본 폴더로 이동
                if folder_type == 'music':
                    default_folder = str(project_root / 'music')
                elif folder_type == 'image':
                    default_folder = str(project_root / 'images')
                else:  # video
                    default_folder = str(project_root / 'videos')
                
                if st.button("📁 기본 폴더", key=f"{folder_type}_quick_default", use_container_width=True):
                    st.session_state[f"{folder_type}_input"] = default_folder
                    st.rerun()
    
    # 현재 디렉토리의 하위 폴더 목록 가져오기 (기존 기능 유지)
    def get_subdirectories(path):
        """지정된 경로의 하위 디렉토리 목록 반환"""
        try:
            items = []
            for item in Path(path).iterdir():
                if item.is_dir():
                    items.append(str(item))
            return sorted(items)
        except Exception:
            return []
    
    subdirs = get_subdirectories(current_dir)
    
    # 빠른 경로 선택 함수
    def render_quick_path_buttons(folder_type: str, current_value: str):
        """빠른 경로 선택 버튼 렌더링 (웹 호스팅 환경용)"""
        col1, col2 = st.columns(2)
        
        with col1:
            # 프로젝트 루트의 기본 폴더
            if folder_type == 'music':
                default_path = str(project_root / 'music')
            elif folder_type == 'image':
                default_path = str(project_root / 'images')
            else:  # video
                default_path = str(project_root / 'videos')
            
            if st.button(f"📂 기본 폴더", key=f"{folder_type}_default", use_container_width=True):
                st.session_state[f"{folder_type}_input"] = default_path
        
        with col2:
            # 프로젝트 루트
            if st.button(f"📁 프로젝트 루트", key=f"{folder_type}_root", use_container_width=True):
                st.session_state[f"{folder_type}_input"] = str(project_root)
    
    # 음악 폴더
    st.markdown("**음악 폴더**")
    
    # 빠른 경로 선택 버튼
    render_quick_path_buttons('music', paths.get("music_folder", "./music"))
    
    # 세션 상태 초기화
    if 'music_input' not in st.session_state:
        st.session_state['music_input'] = paths.get("music_folder", "./music")
    
    # 경로 입력 필드
    music_folder = st.text_input(
        "경로 입력",
        value=st.session_state.get('music_input', paths.get("music_folder", "./music")),
        help="절대 경로 또는 상대 경로를 입력하거나, 아래 '폴더 찾기'를 사용하여 탐색하세요.",
        key="music_input",
        label_visibility="visible"
    )
    
    # 폴더 탐색 UI
    render_folder_browser('music', music_folder)
    
    # 경로 검증 및 표시
    if music_folder:
        music_path = Path(music_folder)
        if not music_path.is_absolute():
            music_path = Path(current_dir) / music_folder
        if music_path.exists():
            if music_path.is_dir():
                st.success(f"✓ 폴더 존재: `{music_path}`")
            else:
                st.warning(f"⚠️ 경로가 폴더가 아닙니다: `{music_path}`")
        else:
            st.info(f"ℹ️ 폴더가 존재하지 않습니다. 저장 시 자동으로 생성됩니다: `{music_path}`")
    
    # 이미지 폴더
    st.markdown("**이미지 폴더**")
    
    # 빠른 경로 선택 버튼
    render_quick_path_buttons('image', paths.get("image_folder", "./images"))
    
    # 세션 상태 초기화
    if 'image_input' not in st.session_state:
        st.session_state['image_input'] = paths.get("image_folder", "./images")
    
    # 경로 입력 필드
    image_folder = st.text_input(
        "경로 입력",
        value=st.session_state.get('image_input', paths.get("image_folder", "./images")),
        help="절대 경로 또는 상대 경로를 입력하거나, 아래 '폴더 찾기'를 사용하여 탐색하세요.",
        key="image_input",
        label_visibility="visible"
    )
    
    # 폴더 탐색 UI
    render_folder_browser('image', image_folder)
    
    # 경로 검증 및 표시
    if image_folder:
        image_path = Path(image_folder)
        if not image_path.is_absolute():
            image_path = Path(current_dir) / image_folder
        if image_path.exists():
            if image_path.is_dir():
                st.success(f"✓ 폴더 존재: `{image_path}`")
            else:
                st.warning(f"⚠️ 경로가 폴더가 아닙니다: `{image_path}`")
        else:
            st.info(f"ℹ️ 폴더가 존재하지 않습니다. 저장 시 자동으로 생성됩니다: `{image_path}`")
    
    # 영상 폴더
    st.markdown("**영상 폴더**")
    
    # 빠른 경로 선택 버튼
    render_quick_path_buttons('video', paths.get("video_folder", "./videos"))
    
    # 세션 상태 초기화
    if 'video_input' not in st.session_state:
        st.session_state['video_input'] = paths.get("video_folder", "./videos")
    
    # 경로 입력 필드
    video_folder = st.text_input(
        "경로 입력",
        value=st.session_state.get('video_input', paths.get("video_folder", "./videos")),
        help="절대 경로 또는 상대 경로를 입력하거나, 아래 '폴더 찾기'를 사용하여 탐색하세요.",
        key="video_input",
        label_visibility="visible"
    )
    
    # 폴더 탐색 UI
    render_folder_browser('video', video_folder)
    
    # 경로 검증 및 표시
    if video_folder:
        video_path = Path(video_folder)
        if not video_path.is_absolute():
            video_path = Path(current_dir) / video_folder
        if video_path.exists():
            if video_path.is_dir():
                st.success(f"✓ 폴더 존재: `{video_path}`")
            else:
                st.warning(f"⚠️ 경로가 폴더가 아닙니다: `{video_path}`")
        else:
            st.info(f"ℹ️ 폴더가 존재하지 않습니다. 저장 시 자동으로 생성됩니다: `{video_path}`")
    
    # 경로 입력 가이드
    with st.expander("💡 경로 입력 가이드"):
        st.markdown(f"""
        **방법 1: 빠른 경로 선택 버튼 사용**
        - **📂 기본 폴더**: 프로젝트 루트의 기본 폴더 (music/images/videos)
        - **📁 프로젝트 루트**: 프로젝트의 루트 디렉토리
        
        **방법 2: 폴더 찾기 사용 (추천)**
        - 경로 입력 필드 아래의 "🔍 폴더 찾기"를 클릭하여 폴더를 탐색할 수 있습니다.
        - 상위 폴더로 이동하거나 하위 폴더를 선택할 수 있습니다.
        - 프로젝트 루트나 기본 폴더로 빠르게 이동할 수 있습니다.
        
        **방법 3: 직접 경로 입력**
        - **절대 경로:** 서버의 절대 경로 (예: `/var/www/playlist/music` 또는 `C:\\inetpub\\playlist\\music`)
        - **상대 경로:** 프로젝트 루트 기준 상대 경로 (예: `./music`, `../storage/music`)
        
        **팁:**
        - 웹 호스팅 환경에서는 서버의 파일 시스템 경로를 사용합니다.
        - 폴더가 존재하지 않으면 저장 시 자동으로 생성됩니다.
        - 폴더 찾기를 사용하면 경로를 직접 타이핑하지 않고도 원하는 폴더를 찾을 수 있습니다.
        - 프로젝트 루트: `{project_root}`
        """)
    
    st.divider()
    
    # 파이프라인 설정
    st.subheader("파이프라인")
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
    if st.button("설정 저장", type="primary"):
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
            st.success("설정이 저장되었습니다.")
            st.info("참고: API 키는 .env 파일에 별도로 저장해야 합니다.")
        else:
            error = save_result["error"]
            st.error(f"{error['type']}: {error['message']}")


# ─────────────────────────────────────────
# 메인 함수
# ─────────────────────────────────────────

def main():
    """메인 함수"""
    # 테마 스위처 제거 (Light Theme만 사용)
    
    # 사이드바 네비게이션 (버튼 형태)
    # 현재 페이지 확인
    if "current_page" not in st.session_state:
        st.session_state.current_page = "대시보드"
    
    # 메뉴 버튼들
    pages = ["대시보드", "음악 생성", "음악 목록", "이미지 생성", "영상 렌더링", "설정"]
    
    for page_name in pages:
        is_selected = st.session_state.current_page == page_name
        button_type = "primary" if is_selected else "secondary"
        
        if st.sidebar.button(
            page_name,
            use_container_width=True,
            type=button_type,
            key=f"menu_{page_name}"
        ):
            st.session_state.current_page = page_name
            st.rerun()
    
    # 페이지 렌더링
    page = st.session_state.current_page
    
    if page == "대시보드":
        render_dashboard()
    elif page == "음악 생성":
        render_music_generation()
    elif page == "음악 목록":
        render_music_list()
    elif page == "이미지 생성":
        render_image_generator()
    elif page == "영상 렌더링":
        render_video_page()
    elif page == "설정":
        render_settings()


if __name__ == "__main__":
    main()

