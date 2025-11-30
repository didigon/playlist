"""
프롬프트 빌더 모듈
음악 및 이미지 프롬프트 템플릿 관리
"""

import json
import random
from pathlib import Path
from typing import Optional, List, Dict, Any
from config_manager import load_config, get_path


def load_music_template(style: str) -> str:
    """
    스타일별 음악 템플릿 로드
    
    Args:
        style: 스타일 이름 (celtic, lofi, jazz, ambient)
    
    Returns:
        템플릿 문자열
    """
    config = load_config()
    prompt_folder = Path(get_path('prompt_folder', config))
    music_folder = prompt_folder / "music"
    
    template_file = music_folder / f"{style}.txt"
    
    if not template_file.exists():
        # 기본 템플릿 반환
        return f"Music in {style} style, {style} atmosphere."
    
    with open(template_file, 'r', encoding='utf-8') as f:
        return f.read().strip()


def build_music_prompt(style: str, randomize: bool = True) -> str:
    """
    최종 음악 프롬프트 생성
    
    Args:
        style: 스타일 이름
        randomize: True면 변수 부분을 랜덤 선택
    
    Returns:
        조합된 프롬프트 문자열
    """
    template = load_music_template(style)
    
    if not randomize:
        # 변수 제거 (간단한 처리)
        prompt = template.replace("{instrument}", "").replace("{mood}", "").replace("{tempo}", "")
        prompt = prompt.replace("  ", " ").strip()
        return prompt
    
    # 랜덤 요소 로드
    config = load_config()
    prompt_folder = Path(get_path('prompt_folder', config))
    music_folder = prompt_folder / "music"
    elements_file = music_folder / "random_elements.json"
    
    elements = {}
    if elements_file.exists():
        with open(elements_file, 'r', encoding='utf-8') as f:
            elements = json.load(f)
    
    # 변수 치환
    prompt = template
    
    if "{instrument}" in prompt:
        instruments = elements.get("instrument", ["piano", "guitar"])
        prompt = prompt.replace("{instrument}", random.choice(instruments))
    
    if "{mood}" in prompt:
        moods = elements.get("mood", ["peaceful", "energetic"])
        prompt = prompt.replace("{mood}", random.choice(moods))
    
    if "{tempo}" in prompt:
        tempos = elements.get("tempo", ["moderate", "upbeat"])
        prompt = prompt.replace("{tempo}", random.choice(tempos))
    
    return prompt.strip()


def get_available_styles() -> List[str]:
    """
    사용 가능한 음악 스타일 목록
    
    Returns:
        스타일 이름 리스트
    """
    config = load_config()
    prompt_folder = Path(get_path('prompt_folder', config))
    music_folder = prompt_folder / "music"
    
    if not music_folder.exists():
        return []
    
    styles = []
    for file_path in music_folder.glob("*.txt"):
        if file_path.name != "random_elements.json":
            styles.append(file_path.stem)
    
    return sorted(styles)


class ImagePromptBuilder:
    """이미지 프롬프트 빌더 클래스"""
    
    MUSIC_TO_VISUAL_KEYWORDS = {
        "celtic": ["rolling green hills", "ancient stone circles", "misty forest", "moonlight"],
        "lofi": ["cozy room", "rainy window", "warm lighting", "coffee cup", "plants"],
        "jazz": ["smoky bar", "city night", "neon lights", "piano keys"],
        "ambient": ["vast landscape", "starry sky", "ocean waves", "aurora"],
        "classical": ["grand concert hall", "elegant chandelier", "velvet curtains"],
    }
    
    def __init__(self, prompt_folder: Optional[str] = None):
        """
        ImagePromptBuilder 초기화
        
        Args:
            prompt_folder: 프롬프트 폴더 경로 (None이면 config에서 로드)
        """
        if prompt_folder is None:
            config = load_config()
            prompt_folder = get_path('prompt_folder', config)
        
        self.prompt_folder = Path(prompt_folder)
        self.quality_suffix = (
            "High quality, 4K resolution, cinematic lighting, "
            "professional photography, no text, no watermark."
        )
    
    def load_style_template(self, style: str) -> str:
        """
        스타일 템플릿 로드
        
        Args:
            style: 스타일 이름
        
        Returns:
            템플릿 문자열
        """
        template_file = self.prompt_folder / f"style_{style}.txt"
        
        if not template_file.exists():
            # 기본 템플릿 반환
            return "A beautiful, atmospheric background image for music visualization."
        
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def extract_keywords_from_music(self, music_prompt: str) -> List[str]:
        """
        음악 프롬프트에서 시각적 키워드 추출
        
        Args:
            music_prompt: 음악 프롬프트
        
        Returns:
            키워드 리스트
        """
        keywords = []
        music_lower = music_prompt.lower()
        
        # 스타일 매칭
        for style, visual_keywords in self.MUSIC_TO_VISUAL_KEYWORDS.items():
            if style in music_lower:
                keywords.extend(visual_keywords)
                break
        
        # 일반 키워드 추출
        if "folk" in music_lower or "traditional" in music_lower:
            keywords.extend(["traditional", "heritage", "cultural"])
        if "electronic" in music_lower or "synth" in music_lower:
            keywords.extend(["futuristic", "digital", "neon"])
        if "acoustic" in music_lower:
            keywords.extend(["natural", "organic", "warm"])
        
        return keywords[:5]  # 최대 5개
    
    def build_prompt(
        self,
        style: str = "default",
        music_prompt: Optional[str] = None,
        custom_keywords: Optional[List[str]] = None
    ) -> str:
        """
        최종 이미지 프롬프트 생성
        
        Args:
            style: 스타일 이름
            music_prompt: 음악 프롬프트 (키워드 추출용)
            custom_keywords: 사용자 지정 키워드
        
        Returns:
            조합된 프롬프트 문자열
        """
        # 스타일 템플릿 로드
        template = self.load_style_template(style)
        
        # 키워드 수집
        keywords = []
        
        if music_prompt:
            keywords.extend(self.extract_keywords_from_music(music_prompt))
        
        if custom_keywords:
            keywords.extend(custom_keywords)
        
        # 프롬프트 조합
        parts = [template]
        
        if keywords:
            parts.append(", ".join(keywords[:3]))  # 최대 3개 키워드
        
        parts.append(self.quality_suffix)
        
        return ", ".join(parts)
    
    def get_available_styles(self) -> List[str]:
        """
        사용 가능한 이미지 스타일 목록
        
        Returns:
            스타일 이름 리스트
        """
        styles = []
        for file_path in self.prompt_folder.glob("style_*.txt"):
            style_name = file_path.stem.replace("style_", "")
            styles.append(style_name)
        
        return sorted(styles) if styles else ["default"]


if __name__ == "__main__":
    # 테스트
    print("음악 프롬프트 빌더 테스트...")
    print(f"사용 가능한 스타일: {get_available_styles()}")
    
    for style in ["celtic", "lofi", "jazz", "ambient"]:
        prompt = build_music_prompt(style, randomize=True)
        print(f"\n{style}: {prompt}")
    
    print("\n이미지 프롬프트 빌더 테스트...")
    builder = ImagePromptBuilder()
    print(f"사용 가능한 스타일: {builder.get_available_styles()}")
    
    for style in ["default", "celtic", "lofi"]:
        prompt = builder.build_prompt(style, music_prompt="Celtic folk music with violin")
        print(f"\n{style}: {prompt[:100]}...")




