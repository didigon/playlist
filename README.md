# Suno Auto Music → Image → Video Factory

AI 기반 자동 음악 제작 · 이미지 제작 · 영상 합성 통합 시스템

## 프로젝트 개요

이 프로그램은 **음악 제작 → 이미지 생성 → 영상 렌더링**이라는 콘텐츠 제작의 전체 과정을 완전히 자동화하기 위해 설계된 AI 기반 생산 시스템입니다.

### 주요 기능

- 🎵 **Suno API**를 활용한 음악 자동 생성
- 🖼️ 음악과 어울리는 배경 이미지 AI 자동 생성
- 🎬 FFmpeg를 이용한 자동 영상 제작
- 📊 Streamlit 기반 사용자 친화적 UI
- 🔄 자동 재시도 및 에러 복구 기능
- 📈 하루 60곡 이상 자동 생산 목표

## 설치 방법

### 1. 저장소 클론

```bash
git clone <repository-url>
cd playlist
```

### 2. Python 가상 환경 생성 (권장)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 설정

#### 폴더 구조 생성

```bash
python setup.py
```

#### 설정 파일 구성

1. `.env.example` 파일을 `.env`로 복사
2. `.env` 파일에 실제 API 키 입력:

```env
SUNO_API_KEY=your_actual_suno_api_key
OPENAI_API_KEY=your_actual_openai_api_key
```

또는 `config.json` 파일에서 직접 수정할 수 있습니다.

## 실행 방법

### CLI 모드

#### 전체 파이프라인 실행

```bash
python main.py
```

#### 특정 단계만 실행

```bash
# 이미지 생성만
python main.py --only-images --style celtic

# 영상 렌더링만
python main.py --only-videos
```

### UI 모드 (Streamlit)

```bash
streamlit run ui_app.py
```

브라우저에서 `http://localhost:8501`로 접속하여 웹 인터페이스를 사용할 수 있습니다.

## 폴더 구조

```
playlist/
├── music/              # Suno 자동 생성 음악
├── images/             # 이미지 자동 생성 결과
├── videos/             # 최종 생성된 영상
├── thumbnails/         # 썸네일 이미지
├── prompts/            # 이미지 생성 프롬프트 템플릿
├── logs/               # 실행 로그
├── db/                 # 상태 관리 DB
├── config.json         # 설정 파일
├── .env                # 환경변수 (API 키)
└── requirements.txt    # 의존성 패키지
```

## 설정 방법

### config.json

주요 설정 항목:

- `suno`: Suno API 설정
- `image`: 이미지 생성 API 설정
- `video`: FFmpeg 영상 렌더링 설정
- `paths`: 각종 폴더 경로 설정
- `pipeline`: 파이프라인 실행 옵션
- `logging`: 로깅 설정

### .env

API 키는 `.env` 파일에서 관리하는 것을 권장합니다. `.env` 파일의 값이 `config.json`보다 우선 적용됩니다.

## 사용 예시

### 1. 음악 생성

```bash
python suno_client.py --generate "upbeat celtic folk music" --style celtic
```

### 2. 이미지 생성

```bash
python image_generator.py --all-pending --style default
```

### 3. 영상 렌더링

```bash
python video_renderer.py --all-pending
```

## 요구사항

- Python 3.10 이상
- FFmpeg (영상 렌더링용)
- Suno API 키
- OpenAI API 키 (이미지 생성용)

## 라이선스

[라이선스 정보를 여기에 추가하세요]

## 기여

[기여 가이드라인을 여기에 추가하세요]

## 문의

[문의 방법을 여기에 추가하세요]


