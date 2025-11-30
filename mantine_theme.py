"""
Mantine 테마 관리 모듈
Streamlit에서 Light Theme만 사용 (Pretendard 폰트 적용)
"""

import streamlit as st
from pathlib import Path


def load_theme_css() -> str:
    """
    Light 테마 CSS 파일 로드
    
    Returns:
        CSS 문자열
    """
    themes_dir = Path(__file__).parent / "themes"
    
    # 기본 테마 CSS
    base_css_path = themes_dir / "st_mantine_theme.css"
    
    # Light 테마 CSS
    theme_css_path = themes_dir / "st_mantine_light.css"
    
    css_content = ""
    
    # 기본 CSS 로드
    if base_css_path.exists():
        with open(base_css_path, "r", encoding="utf-8") as f:
            css_content += f.read() + "\n\n"
    
    # Light 테마 CSS 로드
    if theme_css_path.exists():
        with open(theme_css_path, "r", encoding="utf-8") as f:
            css_content += f.read() + "\n\n"
    
    return css_content


def apply_theme() -> None:
    """
    Streamlit에 Light 테마 적용
    """
    # CSS 로드 및 적용
    css = load_theme_css()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    
    # 크롬에서 텍스트 잘림 방지를 위한 JavaScript 추가
    chrome_fix_js = """
    <script>
    (function() {
        // 크롬에서 텍스트 잘림 방지 - 강화 버전
        function fixChromeTextOverflow() {
            // 모든 컬럼 요소 찾기
            const columns = document.querySelectorAll('[data-testid="column"]');
            columns.forEach(column => {
                column.style.setProperty('overflow', 'visible', 'important');
                column.style.setProperty('overflow-x', 'visible', 'important');
                column.style.setProperty('overflow-y', 'visible', 'important');
                column.style.setProperty('min-width', '0', 'important');
                column.style.setProperty('max-width', 'none', 'important');
                column.style.setProperty('width', 'auto', 'important');
                column.style.setProperty('flex-basis', 'auto', 'important');
                
                // 컬럼 내부의 모든 요소 수정
                const allElements = column.querySelectorAll('*');
                allElements.forEach(el => {
                    el.style.setProperty('overflow', 'visible', 'important');
                    el.style.setProperty('overflow-x', 'visible', 'important');
                    el.style.setProperty('overflow-y', 'visible', 'important');
                    el.style.setProperty('text-overflow', 'clip', 'important');
                    el.style.setProperty('white-space', 'normal', 'important');
                });
            });
            
            // 모든 카드 요소 찾기
            const cards = document.querySelectorAll('.m-card');
            cards.forEach(card => {
                card.style.setProperty('overflow', 'visible', 'important');
                card.style.setProperty('overflow-x', 'visible', 'important');
                card.style.setProperty('overflow-y', 'visible', 'important');
                card.style.setProperty('text-overflow', 'clip', 'important');
                card.style.setProperty('white-space', 'normal', 'important');
                card.style.setProperty('width', '100%', 'important');
                card.style.setProperty('max-width', '100%', 'important');
                card.style.setProperty('min-width', '0', 'important');
                
                // 모든 자식 요소에도 적용
                const children = card.querySelectorAll('*');
                children.forEach(child => {
                    child.style.setProperty('overflow', 'visible', 'important');
                    child.style.setProperty('overflow-x', 'visible', 'important');
                    child.style.setProperty('overflow-y', 'visible', 'important');
                    child.style.setProperty('text-overflow', 'clip', 'important');
                    child.style.setProperty('white-space', 'normal', 'important');
                    child.style.setProperty('word-break', 'keep-all', 'important');
                });
            });
            
            // 모든 메트릭 요소 찾기
            const metrics = document.querySelectorAll('.m-metric-value, .m-metric-label');
            metrics.forEach(metric => {
                metric.style.setProperty('overflow', 'visible', 'important');
                metric.style.setProperty('overflow-x', 'visible', 'important');
                metric.style.setProperty('overflow-y', 'visible', 'important');
                metric.style.setProperty('text-overflow', 'clip', 'important');
                metric.style.setProperty('white-space', 'normal', 'important');
                metric.style.setProperty('word-break', 'keep-all', 'important');
                metric.style.setProperty('overflow-wrap', 'break-word', 'important');
                metric.style.setProperty('word-wrap', 'break-word', 'important');
                metric.style.setProperty('width', '100%', 'important');
                metric.style.setProperty('max-width', '100%', 'important');
                metric.style.setProperty('min-width', '0', 'important');
                metric.style.setProperty('display', 'block', 'important');
            });
            
            // flex 컨테이너 수정
            const flexContainers = document.querySelectorAll('[data-testid="stHorizontalBlock"]');
            flexContainers.forEach(container => {
                container.style.setProperty('overflow', 'visible', 'important');
                container.style.setProperty('display', 'flex', 'important');
                
                const flexItems = container.querySelectorAll('> div');
                flexItems.forEach(item => {
                    item.style.setProperty('overflow', 'visible', 'important');
                    item.style.setProperty('min-width', '0', 'important');
                    item.style.setProperty('max-width', 'none', 'important');
                    item.style.setProperty('flex-basis', 'auto', 'important');
                });
            });
            
            // 드롭다운 메뉴 (오버레이/포털) 강제 라이트 테마 적용
            const dropdownSelectors = [
                '[role="listbox"]',
                '[data-baseweb="popover"]',
                '[data-baseweb="menu"]',
                '[data-baseweb="select"]',
                'div[role="listbox"]',
                'ul[role="listbox"]'
            ];
            
            dropdownSelectors.forEach(selector => {
                const dropdowns = document.querySelectorAll(selector);
                dropdowns.forEach(dropdown => {
                    // 드롭다운 컨테이너 스타일
                    dropdown.style.setProperty('background-color', '#ffffff', 'important');
                    dropdown.style.setProperty('background', '#ffffff', 'important');
                    dropdown.style.setProperty('color', '#212529', 'important');
                    dropdown.style.setProperty('border', '1px solid rgba(0, 0, 0, 0.1)', 'important');
                    dropdown.style.setProperty('box-shadow', '0 4px 6px rgba(0, 0, 0, 0.1)', 'important');
                    
                    // 드롭다운 내부 모든 요소
                    const allChildren = dropdown.querySelectorAll('*');
                    allChildren.forEach(child => {
                        // 옵션 아이템인 경우
                        if (child.getAttribute('role') === 'option' || 
                            child.tagName === 'LI' || 
                            child.tagName === 'DIV') {
                            const bgColor = child.getAttribute('aria-selected') === 'true' 
                                ? '#e6f2ff' 
                                : '#ffffff';
                            child.style.setProperty('background-color', bgColor, 'important');
                            child.style.setProperty('background', bgColor, 'important');
                            child.style.setProperty('color', '#212529', 'important');
                        } else {
                            child.style.setProperty('background-color', 'transparent', 'important');
                            child.style.setProperty('color', '#212529', 'important');
                        }
                    });
                });
            });
            
            // 옵션 아이템 직접 선택
            const options = document.querySelectorAll('[role="option"], li[role="option"], div[role="option"]');
            options.forEach(option => {
                const bgColor = option.getAttribute('aria-selected') === 'true' 
                    ? '#e6f2ff' 
                    : '#ffffff';
                option.style.setProperty('background-color', bgColor, 'important');
                option.style.setProperty('background', bgColor, 'important');
                option.style.setProperty('color', '#212529', 'important');
            });
            
            // 사이드바 버튼 배경 제거
            const sidebarButtons = document.querySelectorAll('[data-testid="stSidebar"] .stButton > button');
            sidebarButtons.forEach(button => {
                const isPrimary = button.getAttribute('kind') === 'primary';
                if (!isPrimary) {
                    // 선택되지 않은 버튼은 배경 투명
                    button.style.setProperty('background', 'transparent', 'important');
                    button.style.setProperty('background-color', 'transparent', 'important');
                    button.style.setProperty('border', 'none', 'important');
                    button.style.setProperty('box-shadow', 'none', 'important');
                    
                    // 버튼 내부 모든 요소도 배경 제거
                    const buttonChildren = button.querySelectorAll('*');
                    buttonChildren.forEach(child => {
                        child.style.setProperty('background', 'transparent', 'important');
                        child.style.setProperty('background-color', 'transparent', 'important');
                    });
                } else {
                    // 선택된 버튼은 파란색 배경 유지
                    button.style.setProperty('background', '#1f7aff', 'important');
                    button.style.setProperty('background-color', '#1f7aff', 'important');
                }
            });
            
            // 사이드바 버튼 컨테이너도 배경 제거
            const sidebarButtonContainers = document.querySelectorAll('[data-testid="stSidebar"] .stButton');
            sidebarButtonContainers.forEach(container => {
                container.style.setProperty('background', 'transparent', 'important');
                container.style.setProperty('background-color', 'transparent', 'important');
                container.style.setProperty('border', 'none', 'important');
                container.style.setProperty('box-shadow', 'none', 'important');
            });
        }
        
        // 즉시 실행
        fixChromeTextOverflow();
        
        // 페이지 로드 시 실행
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fixChromeTextOverflow);
        } else {
            fixChromeTextOverflow();
        }
        
        // Streamlit이 동적으로 콘텐츠를 추가할 때를 대비
        const observer = new MutationObserver(function(mutations) {
            let shouldFix = false;
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0) {
                    shouldFix = true;
                }
            });
            if (shouldFix) {
                setTimeout(fixChromeTextOverflow, 100);
            }
        });
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // 주기적으로도 체크 (Streamlit의 동적 렌더링 대응, 드롭다운 메뉴 포함)
        setInterval(fixChromeTextOverflow, 100);
        
        // window load 이벤트에서도 실행
        window.addEventListener('load', fixChromeTextOverflow);
    })();
    </script>
    """
    st.markdown(chrome_fix_js, unsafe_allow_html=True)


def init_theme() -> None:
    """
    앱 시작 시 Light 테마 초기화 및 적용
    """
    # 테마 적용 (항상 Light)
    apply_theme()


def get_color_palette() -> dict:
    """
    Mantine 컬러 팔레트 로드
    
    Returns:
        컬러 팔레트 딕셔너리
    """
    import json
    
    colors_path = Path(__file__).parent / "themes" / "mantine_colors.json"
    
    if colors_path.exists():
        with open(colors_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {}


def get_color(color_name: str, shade: str = "500") -> str:
    """
    특정 컬러의 특정 shade 값 가져오기
    
    Args:
        color_name: 컬러 이름 (예: "indigo", "blue")
        shade: shade 값 (50~900, 기본값: "500")
    
    Returns:
        HEX 컬러 코드
    """
    palette = get_color_palette()
    
    if color_name in palette and shade in palette[color_name]:
        return palette[color_name][shade]
    
    # 기본값 반환
    return "#6366f1"  # indigo-500


# 테마 스위처 컴포넌트 (제거됨 - Light Theme만 사용)
def render_theme_switcher_button() -> None:
    """
    테마 스위처 버튼 렌더링 (현재는 사용하지 않음 - Light Theme만 사용)
    """
    # Light Theme만 사용하므로 스위처 제거
    pass

