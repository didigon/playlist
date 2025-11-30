# 프로젝트명: Suno Auto Music → Image → Video Factory
### (AI 기반 자동 음악 제작 · 이미지 제작 · 영상 합성 통합 시스템)

---

# 📌 0. 프로젝트 목적(Purpose)

이 프로그램은 **음악 제작 → 이미지 생성 → 영상 렌더링**이라는 콘텐츠 제작의 전체 과정을  
**완전히 자동화하기 위해 설계된 AI 기반 생산 시스템**이다.

## 0-1. 핵심 목표

1. **Suno API**를 활용해 음악을 대량 자동 생성한다.
2. 음악 파일과 어울리는 **배경 이미지를 AI로 자동 생성**한다.
3. 음악 + 이미지 조합을 이용해 **FFmpeg로 자동 영상 제작**을 한다.
4. 최종적으로 YouTube, 플레이리스트 채널 등에 업로드 가능한 **대량 영상 콘텐츠를 자동으로 생산**하는 "음악·영상 공장"을 만든다.
5. 이 시스템은 **하루 60곡(=60 이미지=60 영상) 이상 자동 생산**을 목표로 한다.
6. UI는 Streamlit을 통해 **비개발자도 쉽게 조작**할 수 있도록 제작한다.

## 0-2. 핵심 원칙

> **"사람이 제작 과정에 개입하지 않아도 콘텐츠가 계속 생산되는 자동 제작 시스템"**

- 자동화율 100%를 목표로 한다.
- 에러 발생 시 자동 재시도 및 복구가 되어야 한다.
- 중단된 작업은 재개 가능해야 한다.
- 부분 실패가 전체 파이프라인을 중단시키지 않아야 한다.

---

# 📌 0-3. 전체 시스템 아키텍처

## 파이프라인 흐름

```
[Suno API] → /music/*.mp3
     ↓
[Image AI API] → /images/*.png
     ↓
[FFmpeg] → /videos/*.mp4
     ↓
[YouTube API] → 자동 업로드 (확장)
```

## 모듈 의존성 다이어그램

```
main.py (오케스트레이션)
  │
  ├── config_manager.py     # 설정 로드/저장
  │
  ├── db_manager.py         # tracks.json 상태 관리
  │     └── tracks.json
  │
  ├── suno_client.py        # Suno API 연동
  │     └── [외부] Suno API
  │
  ├── music_scanner.py      # /music 폴더 스캔
  │     └── metadata.py     # mp3 길이 분석
  │
  ├── image_generator.py    # 이미지 생성
  │     ├── prompt_builder.py   # 프롬프트 조합
  │     └── [외부] GPT Image API
  │
  └── video_renderer.py     # FFmpeg 영상 생성
        └── [외부] FFmpeg CLI

ui_app.py (Streamlit UI - 화면만)
  └── ui_handlers.py (UI 핸들러)
        └── main.py (Pipeline)
              └── 각 모듈들...
```

## Task 의존성 매트릭스

```
Task 1 (환경 구성)     → 선행 없음
Task 2 (메타데이터 DB) → Task 1 완료 필요
Task 3 (스캐너)        → Task 1, 2 완료 필요
Task 4 (Suno 연동)     → Task 1, 2 완료 필요
Task 5 (이미지 생성)   → Task 2, 3 완료 필요
Task 6 (mp3 분석)      → Task 1 완료 필요
Task 7 (영상 렌더링)   → Task 5, 6 완료 필요
Task 8 (파이프라인)    → Task 3~7 모두 완료 필요
Task 9 (UI)            → Task 8 완료 필요
Task 10 (확장)         → Task 9 완료 필요
```

---

# 📌 0-4. 폴더 구조

```bash
/suno_video_factory
│
├─ /music/              # Suno 자동 생성 음악
│     track_001.mp3
│     track_002.mp3
│
├─ /images/             # 이미지 자동 생성 결과
│     track_001.png
│     track_002.png
│
├─ /videos/             # 최종 생성된 영상
│     track_001.mp4
│     track_002.mp4
│
├─ /thumbnails/         # 썸네일 이미지 (선택)
│     track_001_thumb.jpg
│
├─ /prompts/            # 이미지 생성 프롬프트 템플릿
│     style_default.txt
│     style_celtic.txt
│     style_lofi.txt
│
├─ /logs/               # 실행 로그
│     pipeline.log
│     error.log
│
├─ /db/                 # 상태 관리 DB
│     tracks.json
│     failed_tasks.json
│     checkpoint.json
│
├─ config_manager.py    # 설정 관리
├─ db_manager.py        # DB 관리
├─ suno_client.py       # Suno API 연동
├─ music_scanner.py     # 음악 스캐너
├─ metadata.py          # mp3 메타데이터 분석
├─ prompt_builder.py    # 프롬프트 생성
├─ image_generator.py   # 이미지 생성 모듈
├─ video_renderer.py    # 영상 렌더링 모듈
├─ main.py              # 전체 파이프라인 실행
├─ ui_app.py            # Streamlit UI (화면 렌더링만)
├─ ui_handlers.py       # UI 이벤트 핸들러 (로직 처리)
├─ config.json          # API 키 및 옵션
├─ requirements.txt     # 의존성 패키지
├─ .env                 # 환경변수 (API 키)
├─ README.md            # 사용법
└─ tasks.md             # 현재 문서
```

---

# 📌 1. Task 1: 환경 구성 & 기본 폴더 생성

## 1-1. 폴더 자동 생성 스크립트

### 요구사항
- 위 폴더 구조를 자동으로 생성하는 `setup.py` 작성
- 이미 존재하는 폴더는 스킵
- 생성 결과를 터미널에 출력

### 구현 세부
```python
# setup.py
REQUIRED_FOLDERS = [
    "music", "images", "videos", "thumbnails",
    "prompts", "logs", "db"
]
```

### 완료 조건
- [O] `python setup.py` 실행 시 모든 폴더 생성됨
- [O] 이미 존재하는 폴더는 에러 없이 스킵
- [O] 생성된 폴더 목록 출력

---

## 1-2. config.json 템플릿 생성

### 요구사항
- 모든 설정값을 담은 `config.json` 템플릿 생성
- API 키는 placeholder로 작성
- 주석 대신 `_comment` 필드로 설명 추가 (JSON은 주석 미지원)

### config.json 구조

```json
{
  "_comment": "Suno Video Factory 설정 파일",
  
  "suno": {
    "api_key": "YOUR_SUNO_API_KEY",
    "api_base_url": "https://api.suno.ai",
    "model": "v3.5",
    "daily_limit": 60,
    "timeout_seconds": 300
  },
  
  "image": {
    "provider": "openai",
    "api_key": "YOUR_OPENAI_API_KEY",
    "model": "dall-e-3",
    "default_size": "1792x1024",
    "quality": "hd",
    "format": "png",
    "fallback_format": "jpg"
  },
  
  "video": {
    "ffmpeg_path": "ffmpeg",
    "codec_video": "libx264",
    "codec_audio": "aac",
    "audio_bitrate": "192k",
    "default_resolution": "1920x1080",
    "vertical_resolution": "1080x1920",
    "thumbnail_enabled": true,
    "thumbnail_time": "00:00:05"
  },
  
  "paths": {
    "music_folder": "./music",
    "image_folder": "./images",
    "video_folder": "./videos",
    "thumbnail_folder": "./thumbnails",
    "prompt_folder": "./prompts",
    "log_folder": "./logs",
    "db_folder": "./db"
  },
  
  "pipeline": {
    "auto_retry_count": 3,
    "retry_delay_seconds": 2,
    "retry_backoff_multiplier": 2,
    "rate_limit_wait_seconds": 60,
    "checkpoint_enabled": true,
    "parallel_enabled": false,
    "max_parallel_tasks": 3
  },
  
  "logging": {
    "level": "INFO",
    "file_enabled": true,
    "console_enabled": true,
    "max_file_size_mb": 10,
    "backup_count": 5
  }
}
```

### 완료 조건
- [O] `config.json` 파일 생성됨
- [O] 모든 필드에 기본값 또는 placeholder 존재
- [O] JSON 문법 오류 없음

---

## 1-3. .env 환경변수 파일 생성

### 요구사항
- API 키는 `.env` 파일로 분리 관리
- `python-dotenv`로 로드
- `.gitignore`에 `.env` 추가

### .env 템플릿

```env
# Suno API
SUNO_API_KEY=your_suno_api_key_here

# OpenAI (이미지 생성용)
OPENAI_API_KEY=your_openai_api_key_here

# YouTube API (확장용)
YOUTUBE_API_KEY=your_youtube_api_key_here
```

### 완료 조건
- [O] `.env.example` 파일 생성 (실제 키 없이)
- [O] `.gitignore`에 `.env` 추가
- [O] config_manager.py에서 .env 로드 로직 포함

---

## 1-4. config_manager.py 구현

### 요구사항
- `config.json` 로드/저장 기능
- `.env` 환경변수 로드 (API 키 우선)
- 설정값 접근 헬퍼 함수 제공

### 핵심 함수

```python
# config_manager.py

def load_config() -> dict:
    """config.json 로드, .env로 API 키 오버라이드"""
    pass

def save_config(config: dict) -> bool:
    """config.json 저장"""
    pass

def get_path(key: str) -> str:
    """경로 설정값 반환 (예: get_path('music_folder'))"""
    pass

def get_api_key(service: str) -> str:
    """API 키 반환 (예: get_api_key('suno'))"""
    pass
```

### 완료 조건
- [O] config.json 정상 로드
- [O] .env 값이 config.json보다 우선 적용
- [O] 파일 없을 시 기본 템플릿 자동 생성
- [O] 타입 힌트, docstring 포함

---

## 1-5. requirements.txt 생성

### 패키지 목록

```txt
# Core
python-dotenv>=1.0.0
requests>=2.31.0

# Audio Processing
pydub>=0.25.1
mutagen>=1.47.0

# Image Processing
Pillow>=10.0.0
openai>=1.0.0

# UI
streamlit>=1.30.0

# Utilities
tqdm>=4.66.0

# Logging
colorlog>=6.8.0

# Testing (optional)
pytest>=8.0.0
```

### 완료 조건
- [O] requirements.txt 생성
- [O] `pip install -r requirements.txt` 정상 설치
- [O] Python 3.10+ 호환 확인

---

## 1-6. README.md 작성

### 포함 내용
- 프로젝트 개요 (1~2문장)
- 설치 방법
- 설정 방법 (config.json, .env)
- 실행 방법 (CLI, UI)
- 폴더 구조 간략 설명

### 완료 조건
- [O] README.md 생성
- [O] 비개발자도 따라할 수 있는 수준의 설명

---

## 1-7. 기본 프롬프트 템플릿 생성

### 요구사항
- `/prompts/` 폴더에 기본 스타일 템플릿 생성
- 최소 3개 스타일 제공

### 파일 목록

**style_default.txt**
```
A beautiful, atmospheric background image for music visualization.
High quality, 4K resolution, cinematic lighting.
No text, no people, abstract or landscape.
```

**style_celtic.txt**
```
Mystical Celtic landscape, ancient stone circles, misty green hills.
Moonlight through clouds, ethereal atmosphere.
Fantasy art style, no text, no people.
```

**style_lofi.txt**
```
Cozy lo-fi aesthetic, warm indoor scene, soft lighting.
Rainy window, plants, coffee cup, vintage vibes.
Anime illustration style, peaceful mood, no text.
```

### 완료 조건
- [O] 3개 이상의 스타일 템플릿 생성
- [O] 각 파일은 이미지 생성 AI에 바로 전달 가능한 형태

---

## 1-8. 로깅 설정 모듈 구현

### 요구사항
- 콘솔 + 파일 동시 로깅
- 로그 레벨: DEBUG, INFO, WARNING, ERROR
- 파일 로테이션 (10MB, 5개 백업)
- 컬러 출력 (콘솔)

### 핵심 함수

```python
# logger.py

def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """로거 설정 및 반환"""
    pass

def log_info(message: str):
    pass

def log_error(message: str, exc_info: bool = False):
    pass

def log_debug(message: str):
    pass
```

### 완료 조건
- [O] 로그 파일 `/logs/pipeline.log`에 기록
- [O] 에러는 `/logs/error.log`에 별도 기록
- [O] 콘솔 출력 시 컬러 적용
- [O] 타임스탬프 포함

---

# 📌 2. Task 2: 메타데이터 DB 설계 (`db_manager.py`)

## 2-1. tracks.json 스키마 설계

### 요구사항
- 각 트랙의 전체 상태를 추적하는 JSON 구조
- 생성 일시, 프롬프트, 상태, 에러 로그 포함

### 스키마 구조

```json
{
  "tracks": {
    "track_001": {
      "track_id": "track_001",
      "created_at": "2025-01-15T10:30:00",
      "updated_at": "2025-01-15T11:45:00",
      
      "music": {
        "status": "completed",
        "file_path": "./music/track_001.mp3",
        "suno_task_id": "suno_xxx_xxx",
        "suno_prompt": "upbeat celtic folk with violin and flute",
        "duration_seconds": 238.5,
        "generated_at": "2025-01-15T10:30:00"
      },
      
      "image": {
        "status": "completed",
        "file_path": "./images/track_001.png",
        "prompt_used": "Mystical Celtic landscape...",
        "style": "celtic",
        "resolution": "1792x1024",
        "format": "png",
        "generated_at": "2025-01-15T10:35:00"
      },
      
      "video": {
        "status": "pending",
        "file_path": null,
        "resolution": "1920x1080",
        "generated_at": null
      },
      
      "thumbnail": {
        "status": "pending",
        "file_path": null
      },
      
      "error_log": [],
      "retry_count": 0
    }
  },
  
  "metadata": {
    "total_tracks": 1,
    "last_updated": "2025-01-15T11:45:00",
    "version": "1.0"
  }
}
```

### status 값 정의
- `pending`: 아직 시작 안 함
- `processing`: 처리 중
- `completed`: 완료
- `failed`: 실패 (재시도 필요)
- `skipped`: 의도적 스킵

### 완료 조건
- [O] 스키마 문서화
- [O] 모든 필드에 기본값 정의

---

## 2-2. db_manager.py 기본 구조

### 요구사항
- CRUD 기능 제공 (Create, Read, Update, Delete)
- 파일 잠금으로 동시 접근 방지
- 자동 백업 (수정 전)

### 클래스 구조

```python
# db_manager.py

class TrackDB:
    def __init__(self, db_path: str = "./db/tracks.json"):
        pass
    
    def load(self) -> dict:
        """DB 로드, 없으면 빈 구조 생성"""
        pass
    
    def save(self) -> bool:
        """DB 저장 (자동 백업 포함)"""
        pass
    
    def get_track(self, track_id: str) -> dict | None:
        """단일 트랙 조회"""
        pass
    
    def get_all_tracks(self) -> list[dict]:
        """전체 트랙 목록"""
        pass
    
    def add_track(self, track_id: str, initial_data: dict) -> bool:
        """새 트랙 추가"""
        pass
    
    def update_track(self, track_id: str, updates: dict) -> bool:
        """트랙 정보 업데이트"""
        pass
    
    def update_status(self, track_id: str, stage: str, status: str) -> bool:
        """상태만 빠르게 업데이트 (stage: music/image/video)"""
        pass
    
    def delete_track(self, track_id: str) -> bool:
        """트랙 삭제"""
        pass
    
    def get_tracks_by_status(self, stage: str, status: str) -> list[dict]:
        """특정 상태의 트랙들 조회"""
        pass
```

### 완료 조건
- [O] 모든 CRUD 함수 구현
- [O] 파일 없을 시 자동 생성
- [O] 타입 힌트, docstring 포함

---

## 2-3. 에러 로그 기록 기능

### 요구사항
- 각 트랙별로 발생한 에러 기록
- 타임스탬프, 단계, 에러 메시지 포함
- 최대 10개까지 보관 (오래된 것 삭제)

### 함수

```python
def add_error_log(self, track_id: str, stage: str, error_message: str) -> bool:
    """에러 로그 추가"""
    # error_log 배열에 추가
    # {
    #   "timestamp": "2025-01-15T10:35:00",
    #   "stage": "image",
    #   "message": "API rate limit exceeded"
    # }
    pass

def get_error_log(self, track_id: str) -> list[dict]:
    """에러 로그 조회"""
    pass

def clear_error_log(self, track_id: str) -> bool:
    """에러 로그 초기화"""
    pass
```

### 완료 조건
- [O] 에러 발생 시 자동 기록
- [O] 최대 10개 제한 동작
- [O] UI에서 조회 가능

---

## 2-4. failed_tasks.json 관리

### 요구사항
- 최종 실패한 작업들만 별도 파일로 관리
- 재시도 큐 역할
- UI에서 재시도 버튼으로 처리

### 구조

```json
{
  "failed_tasks": [
    {
      "track_id": "track_005",
      "stage": "image",
      "failed_at": "2025-01-15T12:00:00",
      "error_message": "API timeout after 3 retries",
      "retry_count": 3
    }
  ],
  "last_updated": "2025-01-15T12:00:00"
}
```

### 함수

```python
def add_failed_task(self, track_id: str, stage: str, error: str) -> bool:
    pass

def get_failed_tasks(self) -> list[dict]:
    pass

def remove_failed_task(self, track_id: str, stage: str) -> bool:
    """재시도 성공 시 제거"""
    pass

def retry_all_failed(self) -> dict:
    """모든 실패 작업 재시도, 결과 반환"""
    pass
```

### 완료 조건
- [O] 실패 작업 별도 관리
- [O] 재시도 성공 시 자동 제거
- [O] UI에서 목록 확인 가능

---

## 2-5. checkpoint.json 구현 (중단/재개)

### 요구사항
- 파이프라인 실행 중 현재 진행 상태 저장
- 비정상 종료 후 재실행 시 이어서 처리
- 정상 완료 시 checkpoint 초기화

### 구조

```json
{
  "is_running": true,
  "started_at": "2025-01-15T10:00:00",
  "current_stage": "image",
  "current_track_id": "track_023",
  "completed_tracks": ["track_001", "track_002", "..."],
  "pending_tracks": ["track_023", "track_024", "..."],
  "last_updated": "2025-01-15T10:45:00"
}
```

### 함수

```python
def save_checkpoint(self, stage: str, track_id: str, 
                    completed: list, pending: list) -> bool:
    pass

def load_checkpoint(self) -> dict | None:
    """checkpoint 있으면 반환, 없으면 None"""
    pass

def clear_checkpoint(self) -> bool:
    """정상 완료 시 호출"""
    pass

def has_checkpoint(self) -> bool:
    """중단된 작업 있는지 확인"""
    pass
```

### 완료 조건
- [O] 파이프라인 실행 중 주기적 저장
- [O] 재실행 시 checkpoint 감지 및 복구 옵션 제공
- [O] 정상 완료 시 자동 삭제

---

## 2-6. DB 통계 조회 기능

### 요구사항
- 대시보드용 통계 데이터 제공
- 각 단계별 완료/대기/실패 개수

### 함수

```python
def get_statistics(self) -> dict:
    """
    반환 예시:
    {
        "total_tracks": 60,
        "music": {"completed": 60, "pending": 0, "failed": 0},
        "image": {"completed": 45, "pending": 12, "failed": 3},
        "video": {"completed": 30, "pending": 27, "failed": 3},
        "fully_completed": 30
    }
    """
    pass
```

### 완료 조건
- [O] 통계 함수 구현
- [O] UI 대시보드에서 사용 가능

---

# 📌 3. Task 3: 음악 파일 스캐너 (`music_scanner.py`)

## 3-1. 기본 스캐너 구조

### 요구사항
- `/music` 폴더 내 mp3 파일 목록 스캔
- 지원 확장자: `.mp3`, `.wav`, `.flac` (mp3 우선)
- 파일명에서 track_id 추출

### 클래스 구조

```python
# music_scanner.py

class MusicScanner:
    def __init__(self, music_folder: str, db: TrackDB):
        self.music_folder = music_folder
        self.db = db
    
    def scan(self) -> list[dict]:
        """폴더 스캔 후 트랙 목록 반환"""
        pass
    
    def get_track_id(self, filename: str) -> str:
        """파일명에서 track_id 추출"""
        # track_001.mp3 → track_001
        pass
    
    def is_supported_format(self, filename: str) -> bool:
        """지원 포맷 확인"""
        pass
```

### 완료 조건
- [O] mp3 파일 목록 정상 스캔
- [O] 빈 폴더 시 빈 리스트 반환 (에러 아님)
- [O] 숨김 파일(.) 제외

---

## 3-2. 파일 상태 체크 기능

### 요구사항
- 각 트랙에 대해 이미지/영상 존재 여부 확인
- DB 상태와 실제 파일 동기화

### 함수

```python
def check_file_status(self, track_id: str) -> dict:
    """
    반환:
    {
        "track_id": "track_001",
        "music_exists": True,
        "music_path": "./music/track_001.mp3",
        "image_exists": True,
        "image_path": "./images/track_001.png",
        "video_exists": False,
        "video_path": None
    }
    """
    pass

def sync_with_db(self, track_id: str, status: dict) -> bool:
    """파일 상태를 DB에 동기화"""
    pass
```

### 완료 조건
- [O] 파일 존재 여부 정확히 체크
- [O] DB 상태와 불일치 시 DB 업데이트
- [O] png, jpg 둘 다 체크 (이미지)

---

## 3-3. 신규 트랙 감지 및 DB 등록

### 요구사항
- DB에 없는 새 음악 파일 감지
- 자동으로 DB에 등록 (초기 상태: music=completed, 나머지=pending)

### 함수

```python
def detect_new_tracks(self) -> list[str]:
    """DB에 없는 새 트랙 ID 목록"""
    pass

def register_new_track(self, track_id: str, music_path: str) -> bool:
    """새 트랙을 DB에 등록"""
    pass

def register_all_new(self) -> int:
    """모든 신규 트랙 일괄 등록, 등록 개수 반환"""
    pass
```

### 완료 조건
- [O] 새 파일 자동 감지
- [O] DB 등록 시 기본 필드 모두 초기화
- [O] 중복 등록 방지

---

## 3-4. 삭제된 파일 처리

### 요구사항
- DB에는 있지만 실제 파일이 없는 경우 처리
- 옵션: 경고만 / DB에서 제거 / 상태를 'missing'으로 변경

### 함수

```python
def detect_missing_files(self) -> list[str]:
    """파일은 없고 DB에만 있는 트랙 ID"""
    pass

def handle_missing(self, track_id: str, action: str = "warn") -> bool:
    """
    action: "warn" | "remove" | "mark_missing"
    """
    pass
```

### 완료 조건
- [O] 누락 파일 감지
- [O] 설정에 따른 처리 옵션 제공
- [O] 로그에 경고 기록

---

## 3-5. 전체 스캔 및 동기화

### 요구사항
- 위 기능들을 조합한 전체 동기화 함수
- 파이프라인 실행 전 항상 호출

### 함수

```python
def full_scan_and_sync(self) -> dict:
    """
    전체 스캔 수행, 결과 요약 반환:
    {
        "total_music_files": 60,
        "new_tracks_registered": 5,
        "missing_files_found": 2,
        "db_synced": True
    }
    """
    pass
```

### 완료 조건
- [O] 한 번 호출로 전체 동기화 완료
- [O] 결과 요약 반환
- [O] main.py에서 파이프라인 시작 전 호출

---

## 3-6. 필터링 기능

### 요구사항
- 특정 조건의 트랙만 필터링
- 파이프라인에서 "이미지 없는 것만", "영상 없는 것만" 처리 시 사용

### 함수

```python
def get_tracks_needing_image(self) -> list[dict]:
    """이미지가 필요한 트랙 목록"""
    pass

def get_tracks_needing_video(self) -> list[dict]:
    """영상이 필요한 트랙 목록"""
    pass

def get_tracks_fully_completed(self) -> list[dict]:
    """모든 단계 완료된 트랙"""
    pass

def get_tracks_by_style(self, style: str) -> list[dict]:
    """특정 스타일의 트랙"""
    pass
```

### 완료 조건
- [O] 각 필터 함수 구현
- [O] 빈 결과 시 빈 리스트 반환
- [O] UI 필터 기능과 연동

---

## 3-7. 스캐너 CLI 인터페이스

### 요구사항
- 독립 실행 가능한 CLI 모드
- 디버깅 및 수동 확인용

### 사용 예시

```bash
# 전체 스캔
python music_scanner.py --scan

# 상태 요약만 출력
python music_scanner.py --status

# 특정 트랙 상태 확인
python music_scanner.py --check track_001

# 신규 트랙만 등록
python music_scanner.py --register-new
```

### 완료 조건
- [O] argparse로 CLI 구현
- [O] 각 명령어 동작 확인
- [O] 결과를 보기 좋게 출력 (테이블 형태)

---

# 📌 공통: 에러 핸들링 정책

이 정책은 모든 모듈에 공통 적용된다.

## 재시도 전략

| 에러 유형 | 재시도 횟수 | 대기 시간 | 비고 |
|-----------|-------------|-----------|------|
| 네트워크 에러 | 3회 | 즉시 → 2초 → 4초 | exponential backoff |
| API 타임아웃 | 3회 | 5초 → 10초 → 20초 | |
| Rate Limit (429) | 5회 | 60초 고정 | 최대 5분 대기 |
| 인증 에러 (401) | 0회 | - | 즉시 실패, 사용자 알림 |
| 서버 에러 (5xx) | 3회 | 10초 → 20초 → 40초 | |
| 파일 I/O 에러 | 2회 | 1초 | |

## 실패 처리 흐름

```
에러 발생
    ↓
재시도 횟수 초과?
    ├─ No → 대기 후 재시도
    └─ Yes → 실패 처리
              ├─ DB에 status='failed' 기록
              ├─ error_log에 상세 기록
              ├─ failed_tasks.json에 추가
              └─ 다음 트랙으로 계속 진행 (중단 안 함)
```

## 공통 재시도 유틸리티

```python
# utils/retry.py

import time
from functools import wraps

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= backoff_multiplier
            
            raise last_exception
        return wrapper
    return decorator
```

---

# 📌 공통: 테스트 체크리스트

## Task 1 테스트

- [ ] `python setup.py` 실행 → 폴더 구조 생성 확인
- [ ] config.json 로드/저장 동작
- [ ] .env 파일 API 키 우선 적용
- [ ] 로그 파일 정상 생성

## Task 2 테스트

- [ ] tracks.json 생성 및 CRUD 동작
- [ ] 동시 접근 시 파일 잠금 동작
- [ ] 에러 로그 10개 제한 동작
- [ ] checkpoint 저장/복구 동작

## Task 3 테스트

- [ ] 빈 music 폴더 스캔 → 에러 없이 빈 리스트
- [ ] mp3 1개 추가 후 스캔 → 감지됨
- [ ] 이미 DB에 있는 트랙 → 중복 등록 안 됨
- [ ] 파일 삭제 후 스캔 → missing 감지

# 📌 4. Task 4: Suno API 연동 (`suno_client.py`)

## 4-1. Suno API 클라이언트 기본 구조

### 요구사항
- Suno API 인증 및 세션 관리
- 비동기 작업 특성 고려 (생성 요청 → 완료 대기 → 다운로드)
- Rate Limit 준수

### 클래스 구조

```python
# suno_client.py

class SunoClient:
    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.base_url = config.get("api_base_url", "https://api.suno.ai")
        self.model = config.get("model", "v3.5")
        self.timeout = config.get("timeout_seconds", 300)
        self.daily_limit = config.get("daily_limit", 60)
        self.session = None
    
    def _get_headers(self) -> dict:
        """인증 헤더 반환"""
        pass
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """공통 요청 래퍼 (에러 핸들링 포함)"""
        pass
    
    def health_check(self) -> bool:
        """API 연결 상태 확인"""
        pass
```

### 완료 조건
- [O] 클래스 초기화 시 설정값 로드
- [O] 인증 헤더 정상 생성
- [O] health_check로 연결 테스트 가능

---

## 4-2. 음악 생성 요청 기능

### 요구사항
- 프롬프트 기반 음악 생성 요청
- 요청 후 task_id 반환
- 스타일, 장르, 분위기 등 파라미터 지원

### 함수

```python
def generate_music(
    self,
    prompt: str,
    style: str = None,
    duration: int = 120,
    instrumental: bool = False,
    **kwargs
) -> dict:
    """
    음악 생성 요청
    
    Args:
        prompt: 음악 설명 프롬프트
        style: 스타일 (celtic, lofi, jazz 등)
        duration: 목표 길이(초), 기본 120초
        instrumental: 보컬 제외 여부
    
    Returns:
        {
            "task_id": "suno_xxx_xxx",
            "status": "pending",
            "estimated_time": 60
        }
    """
    pass
```

### 요청 페이로드 예시

```json
{
  "prompt": "upbeat celtic folk music with violin and flute, energetic and joyful",
  "model": "v3.5",
  "style": "celtic",
  "duration": 120,
  "instrumental": true,
  "make_instrumental": true
}
```

### 완료 조건
- [O] 프롬프트 전송 및 task_id 수신
- [O] 잘못된 프롬프트 시 명확한 에러 반환
- [O] instrumental 옵션 동작

---

## 4-3. 생성 상태 폴링 기능

### 요구사항
- task_id로 생성 진행 상태 확인
- 완료될 때까지 주기적 폴링
- 타임아웃 처리

### 함수

```python
def check_status(self, task_id: str) -> dict:
    """
    단일 상태 확인
    
    Returns:
        {
            "task_id": "suno_xxx_xxx",
            "status": "processing" | "completed" | "failed",
            "progress": 75,
            "audio_url": null | "https://...",
            "error": null | "error message"
        }
    """
    pass

def wait_for_completion(
    self, 
    task_id: str, 
    poll_interval: int = 10,
    timeout: int = 300
) -> dict:
    """
    완료될 때까지 대기
    
    Args:
        task_id: 작업 ID
        poll_interval: 폴링 간격(초)
        timeout: 최대 대기 시간(초)
    
    Returns:
        완료된 작업 정보 (audio_url 포함)
    
    Raises:
        TimeoutError: 타임아웃 초과
        SunoAPIError: 생성 실패
    """
    pass
```

### 완료 조건
- [O] 상태 조회 정상 동작
- [O] 완료 시 audio_url 반환
- [O] 타임아웃 시 명확한 예외 발생

---

## 4-4. 음악 파일 다운로드 기능

### 요구사항
- audio_url에서 mp3 다운로드
- `/music/` 폴더에 저장
- 파일명 규칙 적용

### 함수

```python
def download_audio(
    self, 
    audio_url: str, 
    save_path: str,
    chunk_size: int = 8192
) -> bool:
    """
    오디오 파일 다운로드
    
    Args:
        audio_url: 다운로드 URL
        save_path: 저장 경로 (예: ./music/track_001.mp3)
        chunk_size: 다운로드 청크 크기
    
    Returns:
        성공 여부
    """
    pass

def generate_track_id(self, prefix: str = "track") -> str:
    """
    새 트랙 ID 생성
    기존 파일 확인 후 다음 번호 부여
    예: track_001, track_002, ...
    """
    pass
```

### 완료 조건
- [O] mp3 파일 정상 다운로드
- [O] 중복 파일명 자동 회피
- [O] 다운로드 진행률 로깅

---

## 4-5. 전체 생성 플로우 통합

### 요구사항
- 프롬프트 → 생성요청 → 대기 → 다운로드 → DB등록 일괄 처리
- 한 번의 함수 호출로 전체 플로우 실행

### 함수

```python
def create_track(
    self,
    prompt: str,
    style: str = "default",
    db: TrackDB = None,
    **kwargs
) -> dict:
    """
    전체 음악 생성 플로우 실행
    
    Returns:
        {
            "success": True,
            "track_id": "track_015",
            "file_path": "./music/track_015.mp3",
            "duration": 185.5,
            "suno_task_id": "suno_xxx_xxx"
        }
    """
    # 1. track_id 생성
    # 2. 음악 생성 요청
    # 3. 완료 대기
    # 4. 파일 다운로드
    # 5. DB 등록
    # 6. 결과 반환
    pass
```

### 완료 조건
- [O] 전체 플로우 한 번에 실행
- [O] 중간 실패 시 적절한 에러 반환
- [O] DB 자동 등록

---

## 4-6. 배치 생성 기능

### 요구사항
- 여러 곡 연속 생성
- 일일 한도(daily_limit) 체크
- 진행 상황 콜백 지원

### 함수

```python
def create_batch(
    self,
    prompts: list[dict],
    db: TrackDB = None,
    progress_callback: callable = None
) -> dict:
    """
    배치 음악 생성
    
    Args:
        prompts: [{"prompt": "...", "style": "celtic"}, ...]
        db: 트랙 DB
        progress_callback: 진행 콜백 함수 (current, total, track_id)
    
    Returns:
        {
            "total_requested": 10,
            "successful": 8,
            "failed": 2,
            "tracks": [...]
        }
    """
    pass

def get_remaining_quota(self) -> int:
    """오늘 남은 생성 가능 개수"""
    pass
```

### 완료 조건
- [O] 연속 생성 동작
- [O] 일일 한도 초과 시 중단 및 알림
- [O] 진행 콜백 정상 호출

---

## 4-7. Rate Limit 처리

### 요구사항
- 429 응답 시 자동 대기 후 재시도
- 요청 간 최소 간격 유지
- 일일 한도 로컬 추적

### 구현

```python
class RateLimiter:
    def __init__(self, requests_per_minute: int = 10, daily_limit: int = 60):
        self.rpm = requests_per_minute
        self.daily_limit = daily_limit
        self.request_times = []
        self.daily_count = 0
        self.daily_reset_time = None
    
    def wait_if_needed(self) -> None:
        """필요시 대기"""
        pass
    
    def can_make_request(self) -> bool:
        """요청 가능 여부"""
        pass
    
    def record_request(self) -> None:
        """요청 기록"""
        pass
    
    def reset_daily_count(self) -> None:
        """일일 카운트 리셋 (자정 기준)"""
        pass
```

### 완료 조건
- [O] 분당 요청 수 제한 동작
- [O] 일일 한도 추적 동작
- [O] 자정에 자동 리셋

---

## 4-8. Suno 프롬프트 템플릿 관리

### 요구사항
- 스타일별 음악 프롬프트 템플릿
- 랜덤 변형 옵션
- `/prompts/music/` 폴더에 저장

### 파일 구조

```
/prompts/music/
  ├── celtic.txt
  ├── lofi.txt
  ├── jazz.txt
  ├── ambient.txt
  └── random_elements.json
```

**celtic.txt 예시**
```
Celtic folk music with {instrument}, {mood} atmosphere.
Traditional Irish melody, {tempo} tempo.
```

**random_elements.json 예시**
```json
{
  "instrument": ["violin", "flute", "harp", "tin whistle", "bodhrán"],
  "mood": ["mystical", "energetic", "melancholic", "joyful", "peaceful"],
  "tempo": ["slow", "moderate", "upbeat", "lively"]
}
```

### 함수

```python
# prompt_builder.py (음악용)

def load_music_template(style: str) -> str:
    """스타일별 템플릿 로드"""
    pass

def build_music_prompt(style: str, randomize: bool = True) -> str:
    """
    최종 프롬프트 생성
    randomize=True면 변수 부분을 랜덤 선택
    """
    pass

def get_available_styles() -> list[str]:
    """사용 가능한 스타일 목록"""
    pass
```

### 완료 조건
- [O] 템플릿 로드 동작
- [O] 랜덤 변형 동작
- [O] 최소 4개 스타일 템플릿 제공

---

## 4-9. Suno 클라이언트 CLI

### 요구사항
- 독립 실행 가능한 CLI
- 테스트 및 수동 생성용

### 사용 예시

```bash
# 단일 곡 생성
python suno_client.py --generate "upbeat celtic folk music"

# 스타일 지정 생성
python suno_client.py --generate --style celtic

# 배치 생성 (10곡)
python suno_client.py --batch 10 --style lofi

# 남은 할당량 확인
python suno_client.py --quota

# 상태 확인
python suno_client.py --status suno_xxx_xxx
```

### 완료 조건
- [O] 각 CLI 명령 동작
- [O] 결과 보기 좋게 출력
- [O] 에러 시 명확한 메시지

---

# 📌 5. Task 5: 이미지 생성 모듈 (`image_generator.py`)

## 5-1. 이미지 생성기 기본 구조

### 요구사항
- 추상 인터페이스로 설계 (여러 AI 서비스 교체 가능)
- 기본 구현체: OpenAI DALL-E 3
- 설정 기반 provider 선택

### 클래스 구조

```python
# image_generator.py

from abc import ABC, abstractmethod

class ImageGeneratorBase(ABC):
    """이미지 생성기 추상 클래스"""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> bytes:
        """이미지 생성 후 바이너리 반환"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """서비스 상태 확인"""
        pass


class OpenAIImageGenerator(ImageGeneratorBase):
    """OpenAI DALL-E 구현체"""
    
    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.model = config.get("model", "dall-e-3")
        self.default_size = config.get("default_size", "1792x1024")
        self.quality = config.get("quality", "hd")
    
    def generate(self, prompt: str, **kwargs) -> bytes:
        pass
    
    def health_check(self) -> bool:
        pass


def get_image_generator(provider: str, config: dict) -> ImageGeneratorBase:
    """설정에 따른 생성기 인스턴스 반환"""
    generators = {
        "openai": OpenAIImageGenerator,
        # 향후 확장: "midjourney": MidjourneyGenerator,
        # "stable_diffusion": StableDiffusionGenerator,
    }
    return generators[provider](config)
```

### 완료 조건
- [ ] 추상 클래스 정의
- [ ] OpenAI 구현체 작성
- [ ] 팩토리 함수로 인스턴스 생성

---

## 5-2. OpenAI DALL-E API 연동

### 요구사항
- DALL-E 3 API 호출
- 이미지 크기, 품질 옵션 지원
- 응답에서 이미지 URL 또는 base64 추출

### 함수

```python
def generate(self, prompt: str, **kwargs) -> bytes:
    """
    DALL-E 이미지 생성
    
    Args:
        prompt: 이미지 프롬프트
        size: "1024x1024" | "1792x1024" | "1024x1792"
        quality: "standard" | "hd"
        style: "vivid" | "natural"
    
    Returns:
        이미지 바이너리 데이터
    """
    pass

def _download_image(self, url: str) -> bytes:
    """URL에서 이미지 다운로드"""
    pass
```

### API 호출 예시

```python
from openai import OpenAI

client = OpenAI(api_key=self.api_key)
response = client.images.generate(
    model="dall-e-3",
    prompt=prompt,
    size="1792x1024",
    quality="hd",
    n=1
)
image_url = response.data[0].url
```

### 완료 조건
- [ ] API 호출 정상 동작
- [ ] 이미지 바이너리 반환
- [ ] 에러 시 명확한 예외

---

## 5-3. 이미지 프롬프트 빌더

### 요구사항
- 음악 정보 기반 이미지 프롬프트 생성
- 스타일 템플릿 적용
- 품질 향상 suffix 자동 추가

### 프롬프트 생성 전략

```
[스타일 템플릿] + [음악 기반 키워드] + [품질 suffix]
```

### 함수

```python
# prompt_builder.py

class ImagePromptBuilder:
    def __init__(self, prompt_folder: str = "./prompts"):
        self.prompt_folder = prompt_folder
        self.quality_suffix = (
            "High quality, 4K resolution, cinematic lighting, "
            "professional photography, no text, no watermark."
        )
    
    def load_style_template(self, style: str) -> str:
        """스타일 템플릿 로드"""
        pass
    
    def extract_keywords_from_music(self, music_prompt: str) -> list[str]:
        """음악 프롬프트에서 시각적 키워드 추출"""
        # 예: "celtic folk" → ["mystical", "green hills", "ancient"]
        pass
    
    def build_prompt(
        self, 
        style: str = "default",
        music_prompt: str = None,
        custom_keywords: list[str] = None
    ) -> str:
        """
        최종 이미지 프롬프트 생성
        
        Returns:
            조합된 프롬프트 문자열
        """
        pass
    
    def get_available_styles(self) -> list[str]:
        """사용 가능한 스타일 목록"""
        pass
```

### 키워드 매핑 테이블

```python
MUSIC_TO_VISUAL_KEYWORDS = {
    "celtic": ["rolling green hills", "ancient stone circles", "misty forest", "moonlight"],
    "lofi": ["cozy room", "rainy window", "warm lighting", "coffee cup", "plants"],
    "jazz": ["smoky bar", "city night", "neon lights", "piano keys"],
    "ambient": ["vast landscape", "starry sky", "ocean waves", "aurora"],
    "classical": ["grand concert hall", "elegant chandelier", "velvet curtains"],
}
```

### 완료 조건
- [ ] 스타일 템플릿 로드
- [ ] 음악→시각 키워드 변환
- [ ] 최종 프롬프트 조합

---

## 5-4. 이미지 저장 및 포맷 처리

### 요구사항
- PNG 기본, JPG 옵션 지원
- 파일명 = track_id와 동일
- 이미지 리사이즈 옵션

### 함수

```python
def save_image(
    self,
    image_data: bytes,
    save_path: str,
    format: str = "png",
    resize: tuple = None
) -> bool:
    """
    이미지 저장
    
    Args:
        image_data: 이미지 바이너리
        save_path: 저장 경로
        format: "png" | "jpg"
        resize: (width, height) 또는 None
    
    Returns:
        성공 여부
    """
    pass

def convert_format(
    self,
    input_path: str,
    output_format: str,
    quality: int = 95
) -> str:
    """
    이미지 포맷 변환
    
    Returns:
        변환된 파일 경로
    """
    pass
```

### 완료 조건
- [ ] PNG 저장 동작
- [ ] JPG 변환 동작 (용량 절감)
- [ ] 리사이즈 옵션 동작

---

## 5-5. 중복 체크 및 스킵 로직

### 요구사항
- 이미 이미지가 있는 트랙은 스킵
- 강제 재생성 옵션 지원
- 스킵 시 로그 기록

### 함수

```python
def should_generate(self, track_id: str, force: bool = False) -> bool:
    """
    생성 필요 여부 판단
    
    Args:
        track_id: 트랙 ID
        force: True면 기존 파일 있어도 재생성
    
    Returns:
        생성 필요 여부
    """
    pass

def get_existing_image_path(self, track_id: str) -> str | None:
    """기존 이미지 경로 반환 (없으면 None)"""
    # png, jpg 둘 다 체크
    pass
```

### 완료 조건
- [ ] 중복 체크 동작
- [ ] force 옵션으로 재생성 가능
- [ ] 스킵 시 로그 출력

---

## 5-6. 단일 트랙 이미지 생성 플로우

### 요구사항
- track_id → 프롬프트 생성 → API 호출 → 저장 → DB 업데이트
- 전체 플로우 한 번에 실행

### 함수

```python
def generate_for_track(
    self,
    track_id: str,
    db: TrackDB,
    style: str = "default",
    force: bool = False
) -> dict:
    """
    단일 트랙 이미지 생성
    
    Returns:
        {
            "success": True,
            "track_id": "track_001",
            "image_path": "./images/track_001.png",
            "prompt_used": "...",
            "skipped": False
        }
    """
    # 1. 중복 체크
    # 2. 음악 정보에서 프롬프트 생성
    # 3. 이미지 생성 API 호출
    # 4. 파일 저장
    # 5. DB 업데이트
    # 6. 결과 반환
    pass
```

### 완료 조건
- [ ] 전체 플로우 동작
- [ ] DB 자동 업데이트
- [ ] 실패 시 에러 로그 기록

---

## 5-7. 배치 이미지 생성

### 요구사항
- 여러 트랙 연속 처리
- 진행 상황 콜백 지원
- 부분 실패 허용

### 함수

```python
def generate_batch(
    self,
    track_ids: list[str],
    db: TrackDB,
    style: str = "default",
    progress_callback: callable = None
) -> dict:
    """
    배치 이미지 생성
    
    Args:
        track_ids: 처리할 트랙 ID 목록
        db: 트랙 DB
        style: 적용할 스타일
        progress_callback: 진행 콜백 (current, total, track_id, status)
    
    Returns:
        {
            "total": 10,
            "successful": 8,
            "failed": 1,
            "skipped": 1,
            "results": [...]
        }
    """
    pass

def generate_all_pending(self, db: TrackDB, style: str = "default") -> dict:
    """이미지 없는 모든 트랙 처리"""
    pass
```

### 완료 조건
- [ ] 배치 처리 동작
- [ ] 1개 실패해도 나머지 계속
- [ ] 진행 콜백 정상 호출

---

## 5-8. 이미지 해상도 옵션

### 요구사항
- 가로형 (1920x1080) - 일반 유튜브
- 세로형 (1080x1920) - 쇼츠/릴스
- 정사각형 (1080x1080) - 인스타그램

### 함수

```python
def get_resolution_for_platform(self, platform: str) -> tuple:
    """
    플랫폼별 해상도 반환
    
    Args:
        platform: "youtube" | "shorts" | "instagram"
    
    Returns:
        (width, height)
    """
    resolutions = {
        "youtube": (1920, 1080),
        "shorts": (1080, 1920),
        "instagram": (1080, 1080),
    }
    return resolutions.get(platform, (1920, 1080))

def generate_multi_resolution(
    self,
    track_id: str,
    db: TrackDB,
    platforms: list[str]
) -> dict:
    """여러 해상도로 동시 생성"""
    pass
```

### 완료 조건
- [ ] 3가지 해상도 지원
- [ ] 멀티 해상도 생성 옵션

---

## 5-9. 이미지 생성기 CLI

### 사용 예시

```bash
# 단일 트랙 이미지 생성
python image_generator.py --track track_001 --style celtic

# 모든 pending 트랙 처리
python image_generator.py --all-pending --style default

# 강제 재생성
python image_generator.py --track track_001 --force

# 스타일 목록 확인
python image_generator.py --list-styles

# 프롬프트 미리보기 (생성 안 함)
python image_generator.py --preview track_001 --style lofi
```

### 완료 조건
- [ ] 각 CLI 명령 동작
- [ ] --preview로 프롬프트만 확인 가능
- [ ] 결과 보기 좋게 출력

---

# 📌 6. Task 6: 메타데이터 분석 (`metadata.py`)

## 6-1. MP3 길이 분석 기본 기능

### 요구사항
- mp3 파일의 duration(길이) 추출
- 초 단위(float)로 반환
- pydub 또는 mutagen 사용

### 함수

```python
# metadata.py

from mutagen.mp3 import MP3
from pydub import AudioSegment

def get_audio_duration(path: str, method: str = "mutagen") -> float:
    """
    오디오 파일 길이 반환 (초 단위)
    
    Args:
        path: 파일 경로
        method: "mutagen" | "pydub"
    
    Returns:
        길이(초), 소수점 포함
    
    Raises:
        FileNotFoundError: 파일 없음
        AudioFormatError: 지원하지 않는 포맷
    """
    pass

def get_duration_mutagen(path: str) -> float:
    """mutagen 라이브러리 사용"""
    audio = MP3(path)
    return audio.info.length

def get_duration_pydub(path: str) -> float:
    """pydub 라이브러리 사용"""
    audio = AudioSegment.from_mp3(path)
    return len(audio) / 1000.0  # milliseconds to seconds
```

### 완료 조건
- [ ] mp3 길이 정확히 반환
- [ ] 파일 없을 시 명확한 예외
- [ ] 두 가지 방법 모두 지원

---

## 6-2. 포맷된 시간 문자열 변환

### 요구사항
- 초 → "MM:SS" 또는 "HH:MM:SS" 변환
- FFmpeg 타임스탬프 포맷 지원

### 함수

```python
def seconds_to_mmss(seconds: float) -> str:
    """
    초를 MM:SS 형식으로 변환
    예: 185.5 → "03:05"
    """
    pass

def seconds_to_hhmmss(seconds: float) -> str:
    """
    초를 HH:MM:SS 형식으로 변환
    예: 3725.5 → "01:02:05"
    """
    pass

def seconds_to_ffmpeg_time(seconds: float) -> str:
    """
    FFmpeg 타임스탬프 형식
    예: 185.5 → "00:03:05.500"
    """
    pass

def parse_time_string(time_str: str) -> float:
    """
    시간 문자열을 초로 변환
    "03:05" → 185.0
    "01:02:05" → 3725.0
    """
    pass
```

### 완료 조건
- [ ] 양방향 변환 동작
- [ ] FFmpeg 포맷 지원
- [ ] 엣지 케이스 처리 (0초, 매우 긴 시간)

---

## 6-3. MP3 태그 정보 추출

### 요구사항
- ID3 태그에서 메타데이터 추출
- title, artist, album, genre 등
- Suno 생성 음악은 태그가 없을 수 있음 → 기본값 처리

### 함수

```python
def get_mp3_tags(path: str) -> dict:
    """
    MP3 태그 정보 추출
    
    Returns:
        {
            "title": "Track Title" | None,
            "artist": "Artist Name" | None,
            "album": "Album Name" | None,
            "genre": "Genre" | None,
            "year": 2025 | None,
            "duration": 185.5
        }
    """
    pass

def set_mp3_tags(path: str, tags: dict) -> bool:
    """
    MP3 태그 설정 (Suno 생성 후 메타데이터 추가용)
    """
    pass
```

### 완료 조건
- [ ] 태그 읽기 동작
- [ ] 태그 없을 시 None 반환 (에러 아님)
- [ ] 태그 쓰기 동작

---

## 6-4. 배치 메타데이터 분석

### 요구사항
- 폴더 내 모든 mp3 분석
- 결과를 dict 또는 DataFrame으로 반환

### 함수

```python
def analyze_folder(folder_path: str) -> list[dict]:
    """
    폴더 내 모든 mp3 분석
    
    Returns:
        [
            {
                "file_name": "track_001.mp3",
                "file_path": "./music/track_001.mp3",
                "track_id": "track_001",
                "duration": 185.5,
                "duration_formatted": "03:05",
                "file_size_mb": 4.2,
                "tags": {...}
            },
            ...
        ]
    """
    pass

def get_total_duration(folder_path: str) -> float:
    """폴더 내 모든 음악 총 길이 (초)"""
    pass

def get_folder_statistics(folder_path: str) -> dict:
    """
    폴더 통계
    
    Returns:
        {
            "total_files": 60,
            "total_duration_seconds": 12500.5,
            "total_duration_formatted": "03:28:20",
            "average_duration": 208.3,
            "total_size_mb": 245.8
        }
    """
    pass
```

### 완료 조건
- [ ] 폴더 전체 분석 동작
- [ ] 통계 정보 정확히 계산
- [ ] 빈 폴더 시 에러 없이 빈 결과

---

## 6-5. DB 연동 메타데이터 업데이트

### 요구사항
- 분석 결과를 DB에 자동 반영
- 신규 트랙의 duration 필드 채우기

### 함수

```python
def update_track_metadata(track_id: str, db: TrackDB) -> bool:
    """
    단일 트랙 메타데이터 DB 업데이트
    """
    pass

def update_all_metadata(db: TrackDB) -> dict:
    """
    모든 트랙 메타데이터 일괄 업데이트
    
    Returns:
        {
            "updated": 45,
            "skipped": 15,  # 이미 있는 경우
            "failed": 0
        }
    """
    pass
```

### 완료 조건
- [ ] DB 업데이트 동작
- [ ] 이미 값 있으면 스킵 옵션
- [ ] 실패 건 로깅

---

## 6-6. 오디오 파형 분석 (선택)

### 요구사항
- 음악의 파형 데이터 추출
- 썸네일 또는 시각화용
- 후순위 기능

### 함수

```python
def get_waveform_data(path: str, samples: int = 100) -> list[float]:
    """
    파형 데이터 추출 (정규화된 진폭)
    
    Args:
        path: 파일 경로
        samples: 샘플 개수
    
    Returns:
        [0.0 ~ 1.0] 범위의 진폭 리스트
    """
    pass

def detect_bpm(path: str) -> float:
    """BPM 감지 (선택)"""
    pass
```

### 완료 조건
- [ ] 파형 데이터 추출 (선택)
- [ ] BPM 감지 (선택)

---

## 6-7. 메타데이터 CLI

### 사용 예시

```bash
# 단일 파일 분석
python metadata.py --analyze ./music/track_001.mp3

# 폴더 전체 분석
python metadata.py --folder ./music

# 통계만 출력
python metadata.py --stats ./music

# DB 업데이트
python metadata.py --update-db

# 태그 설정
python metadata.py --set-tags track_001 --title "My Song" --artist "AI"
```

### 완료 조건
- [ ] 각 CLI 명령 동작
- [ ] 분석 결과 테이블 형태 출력
- [ ] 통계 보기 좋게 출력

---

# 📌 2차 테스트 체크리스트

## Task 4 (Suno) 테스트

- [ ] API 키 없을 때 명확한 에러
- [ ] health_check 동작
- [ ] 단일 곡 생성 → 다운로드 → 저장 전체 플로우
- [ ] 타임아웃 발생 시 적절한 예외
- [ ] Rate Limit 대기 동작
- [ ] 일일 한도 체크 동작

## Task 5 (이미지) 테스트

- [ ] API 키 없을 때 명확한 에러
- [ ] 단일 트랙 이미지 생성 전체 플로우
- [ ] 이미 이미지 있는 트랙 → 스킵됨
- [ ] --force로 재생성 동작
- [ ] 스타일 변경 시 프롬프트 달라짐
- [ ] PNG/JPG 저장 모두 동작

## Task 6 (메타데이터) 테스트

- [ ] mp3 길이 정확히 반환
- [ ] 시간 포맷 변환 정확
- [ ] 폴더 통계 계산 정확
- [ ] 존재하지 않는 파일 → 명확한 에러
- [ ] 태그 읽기/쓰기 동작

# 📌 7. Task 7: FFmpeg 영상 렌더링 (`video_renderer.py`)

## 7-1. FFmpeg 환경 체크

### 요구사항
- FFmpeg 설치 여부 확인
- 버전 정보 추출
- 필수 코덱(libx264, aac) 지원 확인

### 함수

```python
# video_renderer.py

import subprocess
import shutil

class FFmpegRenderer:
    def __init__(self, config: dict):
        self.ffmpeg_path = config.get("ffmpeg_path", "ffmpeg")
        self.codec_video = config.get("codec_video", "libx264")
        self.codec_audio = config.get("codec_audio", "aac")
        self.audio_bitrate = config.get("audio_bitrate", "192k")
    
    def check_ffmpeg_installed(self) -> bool:
        """FFmpeg 설치 확인"""
        return shutil.which(self.ffmpeg_path) is not None
    
    def get_ffmpeg_version(self) -> str:
        """FFmpeg 버전 반환"""
        pass
    
    def check_codec_support(self, codec: str) -> bool:
        """특정 코덱 지원 여부"""
        pass
    
    def health_check(self) -> dict:
        """
        전체 환경 체크
        
        Returns:
            {
                "installed": True,
                "version": "6.0",
                "libx264": True,
                "aac": True,
                "ready": True
            }
        """
        pass
```

### 완료 조건
- [ ] FFmpeg 설치 확인 동작
- [ ] 미설치 시 명확한 에러 메시지
- [ ] 코덱 지원 여부 확인

---

## 7-2. 기본 영상 렌더링

### 요구사항
- 이미지 + 음악 → mp4 영상 생성
- 음악 길이에 맞춰 영상 길이 자동 조절
- 기본 FFmpeg 명령 실행

### 기본 명령어

```bash
ffmpeg -loop 1 -i image.png -i music.mp3 \
  -c:v libx264 -tune stillimage \
  -c:a aac -b:a 192k \
  -shortest -pix_fmt yuv420p \
  output.mp4
```

### 함수

```python
def render_video(
    self,
    image_path: str,
    audio_path: str,
    output_path: str,
    duration: float = None
) -> bool:
    """
    기본 영상 렌더링
    
    Args:
        image_path: 이미지 파일 경로
        audio_path: 음악 파일 경로
        output_path: 출력 영상 경로
        duration: 영상 길이(초), None이면 음악 길이 사용
    
    Returns:
        성공 여부
    """
    pass

def _build_ffmpeg_command(
    self,
    image_path: str,
    audio_path: str,
    output_path: str,
    **kwargs
) -> list[str]:
    """FFmpeg 명령어 리스트 생성"""
    pass

def _execute_ffmpeg(self, command: list[str]) -> tuple[bool, str]:
    """
    FFmpeg 실행
    
    Returns:
        (성공여부, 에러메시지 또는 빈 문자열)
    """
    pass
```

### 완료 조건
- [ ] 기본 렌더링 동작
- [ ] 음악 길이만큼 영상 생성
- [ ] 에러 시 상세 메시지 반환

---

## 7-3. 해상도 및 스케일 처리

### 요구사항
- 입력 이미지와 출력 해상도가 다를 경우 스케일 조정
- 가로/세로 비율 유지 옵션
- 패딩(letterbox/pillarbox) 옵션

### 함수

```python
def render_with_resolution(
    self,
    image_path: str,
    audio_path: str,
    output_path: str,
    resolution: tuple = (1920, 1080),
    scale_mode: str = "fit"
) -> bool:
    """
    해상도 지정 렌더링
    
    Args:
        resolution: (width, height)
        scale_mode: 
            "fit" - 비율 유지, 패딩 추가
            "fill" - 비율 유지, 크롭
            "stretch" - 비율 무시, 늘리기
    """
    pass

def _get_scale_filter(
    self,
    input_size: tuple,
    output_size: tuple,
    mode: str
) -> str:
    """FFmpeg scale 필터 문자열 생성"""
    # 예: "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    pass
```

### 해상도 프리셋

```python
RESOLUTION_PRESETS = {
    "youtube_hd": (1920, 1080),
    "youtube_4k": (3840, 2160),
    "shorts": (1080, 1920),
    "instagram_square": (1080, 1080),
    "instagram_portrait": (1080, 1350),
}
```

### 완료 조건
- [ ] 해상도 변경 동작
- [ ] 3가지 스케일 모드 동작
- [ ] 프리셋 사용 가능

---

## 7-4. Ken Burns 효과 (줌 인/아웃)

### 요구사항
- 정적 이미지에 서서히 줌 인/아웃 효과
- 시작/끝 줌 레벨 지정
- 팬(이동) 효과 옵션

### 함수

```python
def render_with_ken_burns(
    self,
    image_path: str,
    audio_path: str,
    output_path: str,
    effect_type: str = "zoom_in",
    zoom_start: float = 1.0,
    zoom_end: float = 1.2
) -> bool:
    """
    Ken Burns 효과 적용 렌더링
    
    Args:
        effect_type: "zoom_in" | "zoom_out" | "pan_left" | "pan_right"
        zoom_start: 시작 줌 레벨 (1.0 = 원본)
        zoom_end: 끝 줌 레벨
    """
    pass

def _get_ken_burns_filter(
    self,
    duration: float,
    effect_type: str,
    zoom_start: float,
    zoom_end: float
) -> str:
    """
    Ken Burns FFmpeg 필터 생성
    
    예: zoompan=z='min(zoom+0.0015,1.5)':d=125:s=1920x1080
    """
    pass
```

### 완료 조건
- [ ] 줌 인 효과 동작
- [ ] 줌 아웃 효과 동작
- [ ] 팬 효과 동작 (선택)

---

## 7-5. 워터마크/텍스트 오버레이

### 요구사항
- 곡 제목, 아티스트명 등 텍스트 삽입
- 위치, 폰트, 크기, 색상 설정
- 페이드 인/아웃 옵션

### 함수

```python
def render_with_text(
    self,
    image_path: str,
    audio_path: str,
    output_path: str,
    text: str,
    position: str = "bottom",
    font_size: int = 48,
    font_color: str = "white",
    fade_in: float = 1.0,
    fade_out: float = 1.0
) -> bool:
    """
    텍스트 오버레이 렌더링
    
    Args:
        text: 표시할 텍스트
        position: "top" | "bottom" | "center"
        font_size: 폰트 크기
        font_color: 색상 (white, black, #RRGGBB)
        fade_in: 페이드 인 시간(초)
        fade_out: 페이드 아웃 시간(초)
    """
    pass

def _get_drawtext_filter(
    self,
    text: str,
    position: str,
    font_size: int,
    font_color: str,
    duration: float,
    fade_in: float,
    fade_out: float
) -> str:
    """FFmpeg drawtext 필터 생성"""
    pass
```

### 완료 조건
- [ ] 텍스트 오버레이 동작
- [ ] 위치 옵션 동작
- [ ] 페이드 효과 동작

---

## 7-6. 썸네일 자동 생성

### 요구사항
- 영상에서 특정 시점 프레임 추출
- 썸네일 해상도 지정
- `/thumbnails/` 폴더에 저장

### 함수

```python
def generate_thumbnail(
    self,
    video_path: str,
    output_path: str,
    timestamp: str = "00:00:05",
    size: tuple = (1280, 720)
) -> bool:
    """
    영상에서 썸네일 추출
    
    Args:
        video_path: 영상 경로
        output_path: 썸네일 저장 경로
        timestamp: 추출 시점 (HH:MM:SS)
        size: 썸네일 크기
    """
    pass

def generate_thumbnail_from_image(
    self,
    image_path: str,
    output_path: str,
    size: tuple = (1280, 720),
    add_play_button: bool = False
) -> bool:
    """
    원본 이미지에서 썸네일 생성
    (영상 렌더링 전에도 사용 가능)
    """
    pass
```

### 완료 조건
- [ ] 영상에서 썸네일 추출
- [ ] 이미지에서 썸네일 생성
- [ ] 재생 버튼 오버레이 (선택)

---

## 7-7. 단일 트랙 영상 생성 플로우

### 요구사항
- track_id → 이미지/음악 확인 → 렌더링 → 썸네일 → DB 업데이트
- 전체 플로우 한 번에 실행

### 함수

```python
def render_for_track(
    self,
    track_id: str,
    db: TrackDB,
    options: dict = None
) -> dict:
    """
    단일 트랙 영상 생성
    
    Args:
        track_id: 트랙 ID
        db: 트랙 DB
        options: {
            "resolution": (1920, 1080),
            "ken_burns": True,
            "text_overlay": "Track Title",
            "generate_thumbnail": True
        }
    
    Returns:
        {
            "success": True,
            "track_id": "track_001",
            "video_path": "./videos/track_001.mp4",
            "thumbnail_path": "./thumbnails/track_001.jpg",
            "duration": 185.5,
            "file_size_mb": 45.2,
            "skipped": False,
            "error": None
        }
    """
    # 1. 이미지/음악 파일 존재 확인
    # 2. 이미 영상 있으면 스킵 (force 아닌 경우)
    # 3. 옵션에 따라 렌더링 실행
    # 4. 썸네일 생성 (옵션)
    # 5. DB 업데이트
    # 6. 결과 반환
    pass
```

### 완료 조건
- [ ] 전체 플로우 동작
- [ ] 이미지/음악 없으면 명확한 에러
- [ ] DB 자동 업데이트

---

## 7-8. 배치 영상 렌더링

### 요구사항
- 여러 트랙 연속 처리
- 진행 상황 콜백
- 예상 시간 계산

### 함수

```python
def render_batch(
    self,
    track_ids: list[str],
    db: TrackDB,
    options: dict = None,
    progress_callback: callable = None
) -> dict:
    """
    배치 영상 렌더링
    
    Args:
        track_ids: 처리할 트랙 ID 목록
        db: 트랙 DB
        options: 렌더링 옵션
        progress_callback: (current, total, track_id, status, eta_seconds)
    
    Returns:
        {
            "total": 10,
            "successful": 8,
            "failed": 1,
            "skipped": 1,
            "total_duration_seconds": 1850.5,
            "total_size_mb": 425.8,
            "results": [...]
        }
    """
    pass

def render_all_pending(self, db: TrackDB, options: dict = None) -> dict:
    """영상 없는 모든 트랙 처리"""
    pass

def estimate_render_time(self, track_ids: list[str], db: TrackDB) -> float:
    """예상 렌더링 시간(초) 계산"""
    # 경험적 수치: 음악 1분당 렌더링 약 10초
    pass
```

### 완료 조건
- [ ] 배치 처리 동작
- [ ] 진행 콜백 정상 호출
- [ ] 예상 시간 계산

---

## 7-9. 렌더링 품질 옵션

### 요구사항
- 품질 프리셋 (fast, normal, high)
- CRF(품질) 값 조정
- 2-pass 인코딩 옵션

### 함수

```python
def set_quality_preset(self, preset: str) -> None:
    """
    품질 프리셋 설정
    
    preset:
        "fast" - CRF 28, preset ultrafast (빠르지만 큰 파일)
        "normal" - CRF 23, preset medium (균형)
        "high" - CRF 18, preset slow (느리지만 고품질)
    """
    pass

QUALITY_PRESETS = {
    "fast": {"crf": 28, "preset": "ultrafast"},
    "normal": {"crf": 23, "preset": "medium"},
    "high": {"crf": 18, "preset": "slow"},
}
```

### 완료 조건
- [ ] 프리셋 변경 동작
- [ ] 파일 크기/품질 차이 확인

---

## 7-10. 영상 렌더러 CLI

### 사용 예시

```bash
# 단일 트랙 렌더링
python video_renderer.py --track track_001

# 모든 pending 트랙 처리
python video_renderer.py --all-pending

# 옵션 지정
python video_renderer.py --track track_001 --resolution 1080x1920 --ken-burns

# 품질 프리셋
python video_renderer.py --track track_001 --quality high

# 텍스트 오버레이
python video_renderer.py --track track_001 --text "My Song"

# 썸네일만 생성
python video_renderer.py --thumbnail track_001

# FFmpeg 환경 체크
python video_renderer.py --check
```

### 완료 조건
- [ ] 각 CLI 명령 동작
- [ ] 진행률 표시
- [ ] 결과 요약 출력

---

# 📌 8. Task 8: 전체 파이프라인 (`main.py`)

## 8-1. 파이프라인 기본 구조

### 요구사항
- 모든 모듈을 조합한 오케스트레이션
- 설정 기반 실행
- 단계별 실행 옵션

### 클래스 구조

```python
# main.py

class Pipeline:
    def __init__(self, config_path: str = "./config.json"):
        self.config = load_config(config_path)
        self.db = TrackDB()
        self.scanner = MusicScanner(self.config, self.db)
        self.suno = SunoClient(self.config)
        self.image_gen = get_image_generator(self.config)
        self.video_renderer = FFmpegRenderer(self.config)
        self.logger = setup_logger("pipeline")
    
    def run(self, options: dict = None) -> dict:
        """전체 파이프라인 실행"""
        pass
    
    def run_stage(self, stage: str, options: dict = None) -> dict:
        """특정 단계만 실행"""
        pass
```

### 완료 조건
- [ ] 모든 모듈 초기화
- [ ] 설정 로드 동작
- [ ] 로거 설정

---

## 8-2. 전체 파이프라인 실행 흐름

### 요구사항
- music → images → videos 순서 실행
- 각 단계 결과 집계
- 전체 소요 시간 측정

### 함수

```python
def run(self, options: dict = None) -> dict:
    """
    전체 파이프라인 실행
    
    Args:
        options: {
            "skip_music": False,      # Suno 생성 스킵
            "skip_images": False,     # 이미지 생성 스킵
            "skip_videos": False,     # 영상 렌더링 스킵
            "force": False,           # 기존 결과물 무시
            "limit": None,            # 처리 개수 제한
            "style": "default"        # 이미지 스타일
        }
    
    Returns:
        {
            "success": True,
            "started_at": "2025-01-15T10:00:00",
            "finished_at": "2025-01-15T11:30:00",
            "duration_seconds": 5400,
            "stages": {
                "scan": {"tracks_found": 60, "new_registered": 5},
                "music": {"generated": 0, "skipped": 60},
                "images": {"generated": 15, "skipped": 42, "failed": 3},
                "videos": {"rendered": 15, "skipped": 42, "failed": 3}
            },
            "summary": {
                "fully_completed": 42,
                "pending": 15,
                "failed": 3
            }
        }
    """
    pass
```

### 실행 순서

```
1. 초기화 및 환경 체크
   ├── config 로드
   ├── DB 로드
   └── FFmpeg 체크

2. 스캔 단계
   ├── /music 폴더 스캔
   ├── 신규 트랙 DB 등록
   └── 메타데이터 업데이트

3. 음악 생성 단계 (옵션)
   ├── Suno API로 음악 생성
   └── /music 폴더에 저장

4. 이미지 생성 단계
   ├── 이미지 없는 트랙 필터
   ├── 프롬프트 생성
   ├── 이미지 API 호출
   └── /images 폴더에 저장

5. 영상 렌더링 단계
   ├── 영상 없는 트랙 필터
   ├── FFmpeg 렌더링
   ├── 썸네일 생성
   └── /videos 폴더에 저장

6. 완료 및 리포트
   ├── 결과 집계
   ├── 로그 기록
   └── checkpoint 정리
```

### 완료 조건
- [ ] 전체 플로우 정상 동작
- [ ] 각 단계 결과 정확히 집계
- [ ] 소요 시간 측정

---

## 8-3. 단계별 실행 옵션

### 요구사항
- 특정 단계만 실행 가능
- CLI 옵션으로 제어

### 함수

```python
def run_stage(self, stage: str, options: dict = None) -> dict:
    """
    특정 단계만 실행
    
    Args:
        stage: "scan" | "music" | "images" | "videos"
        options: 해당 단계 옵션
    """
    pass

def run_scan_only(self) -> dict:
    """스캔만 실행"""
    pass

def run_images_only(self, style: str = "default") -> dict:
    """이미지 생성만 실행"""
    pass

def run_videos_only(self) -> dict:
    """영상 렌더링만 실행"""
    pass
```

### 완료 조건
- [ ] 각 단계 독립 실행 가능
- [ ] --only-images, --only-videos 옵션 동작

---

## 8-4. Checkpoint 기반 재개 기능

### 요구사항
- 실행 중 진행 상태 주기적 저장
- 비정상 종료 후 이어서 실행
- 재개 여부 사용자 확인

### 함수

```python
def _save_checkpoint(self, stage: str, track_id: str) -> None:
    """현재 진행 상태 저장"""
    pass

def _load_checkpoint(self) -> dict | None:
    """저장된 checkpoint 로드"""
    pass

def _clear_checkpoint(self) -> None:
    """정상 완료 시 checkpoint 삭제"""
    pass

def resume_from_checkpoint(self) -> dict:
    """checkpoint에서 재개"""
    pass

def has_incomplete_run(self) -> bool:
    """미완료 실행이 있는지 확인"""
    pass
```

### 재개 로직

```python
def run(self, options: dict = None) -> dict:
    # 미완료 작업 확인
    if self.has_incomplete_run():
        checkpoint = self._load_checkpoint()
        if self._confirm_resume():  # UI에서 확인
            return self.resume_from_checkpoint()
        else:
            self._clear_checkpoint()
    
    # 새로 시작
    ...
```

### 완료 조건
- [ ] checkpoint 저장/로드 동작
- [ ] 재개 시 이미 완료된 항목 스킵
- [ ] 정상 완료 시 checkpoint 삭제

---

## 8-5. 진행 상황 리포팅

### 요구사항
- 실시간 진행률 출력
- 예상 완료 시간 표시
- UI 콜백 지원

### 함수

```python
def set_progress_callback(self, callback: callable) -> None:
    """
    진행 콜백 설정
    
    callback(stage, current, total, track_id, eta_seconds, message)
    """
    self.progress_callback = callback

def _report_progress(
    self,
    stage: str,
    current: int,
    total: int,
    track_id: str = None,
    message: str = None
) -> None:
    """진행 상황 리포트"""
    pass

def _calculate_eta(self, current: int, total: int, elapsed: float) -> float:
    """예상 남은 시간 계산"""
    pass
```

### 완료 조건
- [ ] 진행률 실시간 출력
- [ ] ETA 계산 동작
- [ ] UI 콜백 정상 호출

---

## 8-6. 에러 처리 및 복구

### 요구사항
- 개별 트랙 실패 시 전체 중단 안 함
- 실패 목록 별도 관리
- 실패 항목 재시도 기능

### 함수

```python
def _handle_track_error(
    self,
    track_id: str,
    stage: str,
    error: Exception
) -> None:
    """트랙 에러 처리"""
    # 1. 에러 로깅
    # 2. DB에 status='failed' 기록
    # 3. failed_tasks.json에 추가
    # 4. 다음 트랙으로 계속
    pass

def retry_failed_tasks(self, stage: str = None) -> dict:
    """
    실패한 작업 재시도
    
    Args:
        stage: 특정 단계만 재시도, None이면 전체
    
    Returns:
        재시도 결과
    """
    pass

def get_failed_summary(self) -> dict:
    """실패 작업 요약"""
    pass
```

### 완료 조건
- [ ] 개별 실패 시 계속 진행
- [ ] 실패 목록 관리
- [ ] 재시도 기능 동작

---

## 8-7. 실행 리포트 생성

### 요구사항
- 실행 완료 후 상세 리포트 생성
- 콘솔 출력 + 로그 파일 저장
- 통계 및 에러 요약

### 함수

```python
def _generate_report(self, result: dict) -> str:
    """
    실행 리포트 생성
    
    Returns:
        포맷된 리포트 문자열
    """
    pass

def _print_report(self, report: str) -> None:
    """콘솔에 리포트 출력"""
    pass

def _save_report(self, report: str, filename: str = None) -> str:
    """
    리포트 파일 저장
    
    Returns:
        저장된 파일 경로
    """
    pass
```

### 리포트 예시

```
═══════════════════════════════════════════════════════
  SUNO VIDEO FACTORY - 실행 리포트
═══════════════════════════════════════════════════════
  실행 시간: 2025-01-15 10:00:00 ~ 11:30:00 (1시간 30분)
═══════════════════════════════════════════════════════

📁 스캔 결과
   - 음악 파일: 60개
   - 신규 등록: 5개

🎵 음악 생성
   - 생성: 0개 (스킵)

🖼️ 이미지 생성
   - 성공: 15개
   - 스킵: 42개 (이미 존재)
   - 실패: 3개

🎬 영상 렌더링
   - 성공: 15개
   - 스킵: 42개 (이미 존재)
   - 실패: 3개

═══════════════════════════════════════════════════════
📊 최종 요약
   - 완전 완료: 42개
   - 진행 중: 15개
   - 실패: 3개

⚠️ 실패 목록
   - track_045: 이미지 생성 실패 (API timeout)
   - track_052: 이미지 생성 실패 (Rate limit)
   - track_058: 영상 렌더링 실패 (FFmpeg error)
═══════════════════════════════════════════════════════
```

### 완료 조건
- [ ] 리포트 생성 동작
- [ ] 콘솔 출력 보기 좋음
- [ ] 로그 파일 저장

---

## 8-8. 파이프라인 CLI

### 사용 예시

```bash
# 전체 파이프라인 실행
python main.py

# 이미지 생성만
python main.py --only-images --style celtic

# 영상 렌더링만
python main.py --only-videos

# 강제 재생성
python main.py --force

# 개수 제한
python main.py --limit 10

# 실패 작업 재시도
python main.py --retry-failed

# 상태 확인만
python main.py --status

# 미완료 작업 재개
python main.py --resume

# Dry run (실제 실행 안 함)
python main.py --dry-run
```

### 완료 조건
- [ ] 각 CLI 옵션 동작
- [ ] --dry-run으로 미리보기
- [ ] --status로 현재 상태 확인

---

# 📌 9. Task 9: Streamlit UI (`ui_app.py`)

## 9-0. UI 핸들러 분리 (`ui_handlers.py`)

### 요구사항
- UI(ui_app.py)에는 화면 렌더링 코드만 존재
- 모든 비즈니스 로직은 ui_handlers.py로 분리
- 버튼 클릭 → 핸들러 호출 → Pipeline/모듈 실행 → 결과 반환 구조

### 분리 기준

| ui_app.py (화면) | ui_handlers.py (로직) |
|------------------|----------------------|
| st.button() 배치 | 버튼 클릭 시 실행할 함수 |
| st.progress() 표시 | 진행률 계산 |
| st.error() 표시 | 에러 메시지 생성 |
| st.dataframe() 표시 | 데이터 조회 및 가공 |
| 레이아웃 구성 | 실제 API/DB 호출 |

### 핸들러 함수 구조

```python
# ui_handlers.py

from main import Pipeline
from db_manager import TrackDB
from image_generator import get_image_generator
from video_renderer import FFmpegRenderer
from config_manager import load_config
from typing import Callable

# ─────────────────────────────────────────
# 초기화
# ─────────────────────────────────────────

def init_handlers() -> dict:
    """핸들러에서 사용할 객체들 초기화"""
    config = load_config()
    return {
        "config": config,
        "db": TrackDB(),
        "pipeline": Pipeline(),
        "image_gen": get_image_generator(config),
        "video_renderer": FFmpegRenderer(config)
    }

# ─────────────────────────────────────────
# 대시보드 핸들러
# ─────────────────────────────────────────

def handle_get_statistics(db: TrackDB) -> dict:
    """대시보드용 통계 조회"""
    try:
        stats = db.get_statistics()
        return {"success": True, "data": stats}
    except Exception as e:
        return {"success": False, "error": format_error(e, "statistics")}

def handle_run_full_pipeline(
    pipeline: Pipeline,
    options: dict,
    progress_callback: Callable = None
) -> dict:
    """전체 파이프라인 실행"""
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

def handle_get_track_list(db: TrackDB, filter_status: str = "all") -> dict:
    """트랙 목록 조회 (필터 적용)"""
    try:
        if filter_status == "all":
            tracks = db.get_all_tracks()
        elif filter_status == "need_image":
            tracks = db.get_tracks_by_status("image", "pending")
        elif filter_status == "need_video":
            tracks = db.get_tracks_by_status("video", "pending")
        elif filter_status == "completed":
            tracks = [t for t in db.get_all_tracks() 
                      if t.get("video", {}).get("status") == "completed"]
        elif filter_status == "failed":
            tracks = db.get_tracks_by_status("image", "failed") + \
                     db.get_tracks_by_status("video", "failed")
        else:
            tracks = db.get_all_tracks()
        
        return {"success": True, "data": tracks}
    except Exception as e:
        return {"success": False, "error": format_error(e, "track_list")}

# ─────────────────────────────────────────
# 이미지 생성 핸들러
# ─────────────────────────────────────────

def handle_generate_image_single(
    track_id: str,
    style: str,
    image_gen,
    db: TrackDB
) -> dict:
    """단일 트랙 이미지 생성"""
    try:
        result = image_gen.generate_for_track(track_id, db, style=style)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "image_generation")}

def handle_generate_image_batch(
    track_ids: list[str],
    style: str,
    image_gen,
    db: TrackDB,
    progress_callback: Callable = None
) -> dict:
    """배치 이미지 생성"""
    try:
        result = image_gen.generate_batch(
            track_ids, db, style=style, 
            progress_callback=progress_callback
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "image_batch")}

# ─────────────────────────────────────────
# 영상 렌더링 핸들러
# ─────────────────────────────────────────

def handle_render_video_single(
    track_id: str,
    options: dict,
    renderer: FFmpegRenderer,
    db: TrackDB
) -> dict:
    """단일 트랙 영상 렌더링"""
    try:
        result = renderer.render_for_track(track_id, db, options=options)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "video_rendering")}

def handle_render_video_batch(
    track_ids: list[str],
    options: dict,
    renderer: FFmpegRenderer,
    db: TrackDB,
    progress_callback: Callable = None
) -> dict:
    """배치 영상 렌더링"""
    try:
        result = renderer.render_batch(
            track_ids, db, options=options,
            progress_callback=progress_callback
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "video_batch")}

# ─────────────────────────────────────────
# 설정 핸들러
# ─────────────────────────────────────────

def handle_save_settings(new_config: dict) -> dict:
    """설정 저장"""
    try:
        from config_manager import save_config
        save_config(new_config)
        return {"success": True, "message": "설정이 저장되었습니다."}
    except Exception as e:
        return {"success": False, "error": format_error(e, "settings")}

# ─────────────────────────────────────────
# 실패 작업 핸들러
# ─────────────────────────────────────────

def handle_get_failed_tasks(db: TrackDB) -> dict:
    """실패 작업 목록 조회"""
    try:
        failed = db.get_failed_tasks()
        return {"success": True, "data": failed}
    except Exception as e:
        return {"success": False, "error": format_error(e, "failed_tasks")}

def handle_retry_failed_task(
    track_id: str,
    stage: str,
    pipeline: Pipeline
) -> dict:
    """단일 실패 작업 재시도"""
    try:
        result = pipeline.retry_single(track_id, stage)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "retry")}

def handle_retry_all_failed(pipeline: Pipeline) -> dict:
    """모든 실패 작업 재시도"""
    try:
        result = pipeline.retry_all_failed()
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": format_error(e, "retry_all")}

# ─────────────────────────────────────────
# 에러 포맷팅 (에러 메시지 가이드라인 적용)
# ─────────────────────────────────────────

def format_error(exception: Exception, context: str) -> dict:
    """
    에러를 사용자 친화적 메시지로 변환
    
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
```

### ui_app.py에서 핸들러 사용 예시

```python
# ui_app.py

import streamlit as st
from ui_handlers import (
    init_handlers,
    handle_get_statistics,
    handle_run_full_pipeline,
    handle_generate_image_single,
)

# 핸들러 초기화 (캐시)
@st.cache_resource
def get_handlers():
    return init_handlers()

def render_dashboard():
    handlers = get_handlers()
    
    # 통계 조회
    result = handle_get_statistics(handlers["db"])
    
    if result["success"]:
        stats = result["data"]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎵 음악", stats["total_music"])
        # ...
    else:
        error = result["error"]
        st.error(f"{error['message']}")
        st.caption(f"💡 {error['action']}")
    
    # 파이프라인 실행 버튼
    if st.button("▶️ 전체 실행", type="primary"):
        progress_bar = st.progress(0)
        
        def update_progress(stage, current, total, track_id, eta):
            progress_bar.progress(current / total if total > 0 else 0)
        
        result = handle_run_full_pipeline(
            handlers["pipeline"],
            options={},
            progress_callback=update_progress
        )
        
        if result["success"]:
            st.success("✅ 완료!")
        else:
            error = result["error"]
            st.error(f"{error['type']}: {error['message']}")
            st.info(f"💡 {error['action']}")
```

### 완료 조건

- [ ] ui_handlers.py 파일 생성
- [ ] 모든 UI 액션에 대한 핸들러 함수 존재
- [ ] ui_app.py에서 직접 Pipeline/DB 호출 없음
- [ ] 모든 핸들러가 `{"success": bool, "data"|"error": ...}` 형태 반환
- [ ] format_error() 함수로 일관된 에러 메시지 생성
- [ ] 타입 힌트, docstring 포함

---

---

## 9-1. UI 기본 구조 및 레이아웃

### 요구사항
- 사이드바 네비게이션
- 5개 메인 페이지
- 한글 UI

### 기본 구조

```python
# ui_app.py

import streamlit as st
from main import Pipeline

def main():
    st.set_page_config(
        page_title="Suno Video Factory",
        page_icon="🎵",
        layout="wide"
    )
    
    # 사이드바 네비게이션
    page = st.sidebar.radio(
        "메뉴",
        ["📊 대시보드", "🎵 음악 목록", "🖼️ 이미지 생성", 
         "🎬 영상 렌더링", "⚙️ 설정"]
    )
    
    if page == "📊 대시보드":
        render_dashboard()
    elif page == "🎵 음악 목록":
        render_music_list()
    # ...

if __name__ == "__main__":
    main()
```

### 완료 조건
- [ ] 사이드바 네비게이션 동작
- [ ] 페이지 전환 동작
- [ ] 한글 정상 표시

---

## 9-2. 대시보드 페이지

### 요구사항
- 전체 상태 요약 카드
- 최근 활동 로그
- 원클릭 파이프라인 실행 버튼

### 구현

```python
def render_dashboard():
    st.title("📊 대시보드")
    
    # 통계 카드
    col1, col2, col3, col4 = st.columns(4)
    stats = get_statistics()
    
    with col1:
        st.metric("🎵 음악", stats["total_music"])
    with col2:
        st.metric("🖼️ 이미지", f"{stats['images_done']}/{stats['total_music']}")
    with col3:
        st.metric("🎬 영상", f"{stats['videos_done']}/{stats['total_music']}")
    with col4:
        st.metric("✅ 완료", stats["fully_completed"])
    
    # 파이프라인 실행 버튼
    st.subheader("🚀 파이프라인 실행")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ 전체 실행", type="primary", use_container_width=True):
            run_pipeline()
    with col2:
        if st.button("🖼️ 이미지만", use_container_width=True):
            run_pipeline(only_images=True)
    with col3:
        if st.button("🎬 영상만", use_container_width=True):
            run_pipeline(only_videos=True)
    
    # 최근 로그
    st.subheader("📜 최근 활동")
    display_recent_logs()
```

### 완료 조건
- [ ] 통계 카드 표시
- [ ] 실행 버튼 동작
- [ ] 로그 표시

---

## 9-3. 음악 목록 페이지

### 요구사항
- 트랙 리스트 테이블 표시
- 상태별 필터링
- 개별 트랙 액션 버튼

### 구현

```python
def render_music_list():
    st.title("🎵 음악 목록")
    
    # 필터
    col1, col2 = st.columns([1, 3])
    with col1:
        filter_status = st.selectbox(
            "상태 필터",
            ["전체", "이미지 필요", "영상 필요", "완료", "실패"]
        )
    
    # 트랙 테이블
    tracks = get_filtered_tracks(filter_status)
    
    for track in tracks:
        with st.expander(f"🎵 {track['track_id']} - {track['duration_formatted']}"):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**상태:** 음악 ✅ | 이미지 {'✅' if track['image_exists'] else '❌'} | 영상 {'✅' if track['video_exists'] else '❌'}")
            
            with col2:
                if not track['image_exists']:
                    if st.button("🖼️ 이미지 생성", key=f"img_{track['track_id']}"):
                        generate_image_for_track(track['track_id'])
            
            with col3:
                if track['image_exists'] and not track['video_exists']:
                    if st.button("🎬 영상 생성", key=f"vid_{track['track_id']}"):
                        render_video_for_track(track['track_id'])
```

### 완료 조건
- [ ] 트랙 목록 표시
- [ ] 필터링 동작
- [ ] 개별 액션 버튼 동작

---

## 9-4. 이미지 생성 페이지

### 요구사항
- 스타일 선택 드롭다운
- 대상 트랙 선택 (체크박스)
- 생성된 이미지 갤러리

### 구현

```python
def render_image_generator():
    st.title("🖼️ 이미지 생성")
    
    # 스타일 선택
    col1, col2 = st.columns([1, 2])
    with col1:
        style = st.selectbox(
            "스타일 선택",
            get_available_styles()
        )
    with col2:
        st.info(f"선택된 스타일: {style}")
        # 프롬프트 미리보기
        st.text_area("프롬프트 미리보기", get_style_preview(style), disabled=True)
    
    # 대상 트랙 선택
    st.subheader("대상 트랙 선택")
    pending_tracks = get_tracks_needing_image()
    
    selected = []
    cols = st.columns(5)
    for i, track in enumerate(pending_tracks):
        with cols[i % 5]:
            if st.checkbox(track['track_id'], key=f"sel_{track['track_id']}"):
                selected.append(track['track_id'])
    
    # 실행 버튼
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🖼️ 선택 항목 생성", type="primary", disabled=len(selected)==0):
            run_image_generation(selected, style)
    with col2:
        if st.button("🖼️ 전체 생성"):
            run_image_generation([t['track_id'] for t in pending_tracks], style)
    
    # 이미지 갤러리
    st.subheader("생성된 이미지")
    display_image_gallery()
```

### 완료 조건
- [ ] 스타일 선택 동작
- [ ] 체크박스 선택 동작
- [ ] 갤러리 표시

---

## 9-5. 영상 렌더링 페이지

### 요구사항
- 렌더링 옵션 설정
- 대상 트랙 선택
- 진행률 표시

### 구현

```python
def render_video_page():
    st.title("🎬 영상 렌더링")
    
    # 옵션 설정
    st.subheader("렌더링 옵션")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        resolution = st.selectbox(
            "해상도",
            ["1920x1080 (YouTube)", "1080x1920 (Shorts)", "1080x1080 (Instagram)"]
        )
    with col2:
        quality = st.selectbox("품질", ["fast", "normal", "high"])
    with col3:
        ken_burns = st.checkbox("Ken Burns 효과")
    
    # 대상 트랙
    st.subheader("렌더링 대상")
    pending_tracks = get_tracks_needing_video()
    st.write(f"렌더링 대기: {len(pending_tracks)}개")
    
    # 실행
    if st.button("🎬 렌더링 시작", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, track in enumerate(pending_tracks):
            status_text.text(f"처리 중: {track['track_id']}")
            render_video(track['track_id'], resolution, quality, ken_burns)
            progress_bar.progress((i + 1) / len(pending_tracks))
        
        st.success("✅ 렌더링 완료!")
    
    # 완료된 영상 목록
    st.subheader("완료된 영상")
    display_completed_videos()
```

### 완료 조건
- [ ] 옵션 설정 동작
- [ ] 진행률 바 동작
- [ ] 완료 목록 표시

---

## 9-6. 설정 페이지

### 요구사항
- config.json 주요 항목 수정
- API 키 입력 (마스킹)
- 저장 버튼

### 구현

```python
def render_settings():
    st.title("⚙️ 설정")
    
    config = load_config()
    
    # API 키 설정
    st.subheader("🔑 API 키")
    col1, col2 = st.columns(2)
    
    with col1:
        suno_key = st.text_input(
            "Suno API Key",
            value=mask_api_key(config['suno']['api_key']),
            type="password"
        )
    with col2:
        openai_key = st.text_input(
            "OpenAI API Key",
            value=mask_api_key(config['image']['api_key']),
            type="password"
        )
    
    # 경로 설정
    st.subheader("📁 폴더 경로")
    music_folder = st.text_input("음악 폴더", config['paths']['music_folder'])
    image_folder = st.text_input("이미지 폴더", config['paths']['image_folder'])
    video_folder = st.text_input("영상 폴더", config['paths']['video_folder'])
    
    # 파이프라인 설정
    st.subheader("⚡ 파이프라인")
    retry_count = st.slider("재시도 횟수", 1, 5, config['pipeline']['auto_retry_count'])
    
    # 저장
    if st.button("💾 설정 저장", type="primary"):
        save_config(updated_config)
        st.success("✅ 설정이 저장되었습니다.")
```

### 완료 조건
- [ ] 설정 로드/저장 동작
- [ ] API 키 마스킹
- [ ] 변경사항 반영

---

## 9-7. 실시간 진행 상황 표시

### 요구사항
- 파이프라인 실행 중 실시간 업데이트
- 진행률 바 + 상태 텍스트
- 취소 버튼

### 구현

```python
def run_pipeline_with_progress(options: dict):
    """진행 상황을 표시하며 파이프라인 실행"""
    
    progress_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        eta_text = st.empty()
        cancel_button = st.button("❌ 취소")
    
    def progress_callback(stage, current, total, track_id, eta):
        if cancel_button:
            raise KeyboardInterrupt("사용자 취소")
        
        progress = current / total if total > 0 else 0
        progress_bar.progress(progress)
        status_text.text(f"[{stage}] {track_id} 처리 중... ({current}/{total})")
        eta_text.text(f"예상 남은 시간: {format_eta(eta)}")
    
    pipeline = Pipeline()
    pipeline.set_progress_callback(progress_callback)
    
    try:
        result = pipeline.run(options)
        st.success("✅ 완료!")
        display_result_summary(result)
    except KeyboardInterrupt:
        st.warning("⚠️ 사용자에 의해 취소되었습니다.")
    except Exception as e:
        st.error(f"❌ 오류 발생: {str(e)}")
```

### 완료 조건
- [ ] 실시간 진행률 업데이트
- [ ] ETA 표시
- [ ] 취소 기능 동작

---

## 9-8. 에러 및 실패 관리 UI

### 요구사항
- 실패 목록 표시
- 개별/전체 재시도 버튼
- 에러 상세 보기

### 구현

```python
def render_failed_tasks():
    st.subheader("⚠️ 실패한 작업")
    
    failed = get_failed_tasks()
    
    if not failed:
        st.info("실패한 작업이 없습니다.")
        return
    
    # 전체 재시도 버튼
    if st.button("🔄 전체 재시도"):
        retry_all_failed()
    
    # 실패 목록
    for task in failed:
        with st.expander(f"❌ {task['track_id']} - {task['stage']}"):
            st.write(f"**실패 시간:** {task['failed_at']}")
            st.write(f"**에러:** {task['error_message']}")
            st.write(f"**재시도 횟수:** {task['retry_count']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 재시도", key=f"retry_{task['track_id']}"):
                    retry_single_task(task['track_id'], task['stage'])
            with col2:
                if st.button("🗑️ 무시", key=f"ignore_{task['track_id']}"):
                    remove_from_failed(task['track_id'], task['stage'])
```

### 완료 조건
- [ ] 실패 목록 표시
- [ ] 재시도 버튼 동작
- [ ] 무시 버튼 동작

---

## 9-9. UI 실행 및 배포

### 실행 명령

```bash
# 로컬 실행
streamlit run ui_app.py

# 포트 지정
streamlit run ui_app.py --server.port 8501

# 외부 접근 허용
streamlit run ui_app.py --server.address 0.0.0.0
```

### 완료 조건
- [ ] `streamlit run ui_app.py` 정상 실행
- [ ] 모든 페이지 정상 동작
- [ ] 반응형 레이아웃

---

# 📌 10. Task 10: 확장 로드맵

## 10-1. YouTube 자동 업로드 (1단계)

### 요구사항
- YouTube Data API v3 연동
- 영상 업로드 자동화
- 제목, 설명, 태그 자동 생성

### 구현 방향

```python
# youtube_uploader.py

class YouTubeUploader:
    def __init__(self, credentials_path: str):
        self.credentials = load_credentials(credentials_path)
        self.youtube = build_youtube_service(self.credentials)
    
    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        category: str = "10",  # Music
        privacy: str = "private"
    ) -> str:
        """
        영상 업로드
        
        Returns:
            video_id
        """
        pass
    
    def generate_metadata(self, track_id: str, db: TrackDB) -> dict:
        """
        GPT로 제목/설명/태그 자동 생성
        """
        pass
```

---

## 10-2. 플레이리스트 자동 생성 (1단계)

### 요구사항
- 여러 트랙 병합하여 1시간짜리 영상 생성
- 챕터 마커 자동 삽입
- 플레이리스트 썸네일 생성

### 구현 방향

```python
def create_playlist_video(
    track_ids: list[str],
    output_path: str,
    title: str
) -> dict:
    """
    여러 트랙을 하나의 영상으로 병합
    """
    # FFmpeg concat 사용
    pass

def generate_chapter_markers(tracks: list[dict]) -> str:
    """
    YouTube 챕터 마커 텍스트 생성
    
    Returns:
        "00:00 Track 1\n03:15 Track 2\n..."
    """
    pass
```

---

## 10-3. 자동 스케줄러 (3단계)

### 요구사항
- 하루 1회 또는 지정 시간마다 자동 실행
- Windows Task Scheduler / cron 연동
- 실행 결과 알림 (이메일, 슬랙 등)

### 구현 방향

```python
# scheduler.py

def create_windows_task(
    task_name: str,
    script_path: str,
    schedule: str  # "daily 09:00" | "hourly"
) -> bool:
    """Windows Task Scheduler에 작업 등록"""
    pass

def create_cron_job(
    schedule: str,  # "0 9 * * *"
    script_path: str
) -> bool:
    """Linux cron 작업 등록"""
    pass
```

---

## 10-4. 원격 모니터링 (3단계)

### 요구사항
- 웹 대시보드로 원격 상태 확인
- 푸시 알림
- 모바일 접근 가능

---

# 📌 공통: 개발 규칙 (최종)

## 코드 품질 규칙

1. **타입 힌트 필수**
   ```python
   def process_track(track_id: str, options: dict = None) -> dict:
   ```

2. **Docstring 필수**
   ```python
   def generate_image(prompt: str) -> bytes:
       """
       이미지 생성 API 호출
       
       Args:
           prompt: 이미지 프롬프트
       
       Returns:
           이미지 바이너리 데이터
       
       Raises:
           APIError: API 호출 실패 시
       """
   ```

3. **에러 처리 필수**
   - 모든 외부 호출(API, 파일 I/O)은 try-except로 감싸기
   - 사용자 친화적 에러 메시지

4. **로깅 필수**
   - 주요 동작마다 INFO 로그
   - 에러는 ERROR 로그 + traceback

## 아키텍처 규칙

1. **모듈 분리**
   - 각 모듈은 단일 책임
   - 순환 의존성 금지

2. **설정 외부화**
   - 하드코딩 금지
   - 모든 설정은 config.json 또는 환경변수

3. **상태 관리**
   - 모든 상태는 DB(tracks.json)에서 관리
   - 메모리 상태에 의존하지 않기

## 실행 순서 규칙

```
music → images → videos
```

이 순서는 절대 변경하지 않는다.

## 자동화 규칙

1. **자동화율 100% 목표**
   - 사람 개입 없이 전체 플로우 실행 가능해야 함

2. **재시도 필수**
   - 모든 외부 호출은 재시도 로직 포함

3. **부분 실패 허용**
   - 1개 실패해도 나머지 계속 진행

4. **재개 가능**
   - 중단 후 이어서 실행 가능

## 네이밍 규칙

| 대상 | 규칙 | 예시 |
|------|------|------|
| 파일명 | snake_case | `image_generator.py` |
| 클래스 | PascalCase | `ImageGenerator` |
| 함수 | snake_case | `generate_image()` |
| 상수 | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| 변수 | snake_case | `track_id` |

## 파일 저장 규칙

| 유형 | 위치 | 네이밍 |
|------|------|--------|
| 음악 | `/music/` | `track_001.mp3` |
| 이미지 | `/images/` | `track_001.png` |
| 영상 | `/videos/` | `track_001.mp4` |
| 썸네일 | `/thumbnails/` | `track_001_thumb.jpg` |
| 로그 | `/logs/` | `pipeline.log` |
| DB | `/db/` | `tracks.json` |

---

# 📌 공통: 에러 메시지 가이드라인

## 에러 메시지 원칙

사용자에게 표시되는 모든 에러 메시지는 다음 3가지를 포함해야 한다:

1. **무엇이 잘못됐는지** (What) - 에러 유형
2. **왜 발생했는지** (Why) - 원인 설명
3. **어떻게 해결하는지** (How) - 다음 행동 안내

## 에러 메시지 구조

```python
{
    "type": "에러 유형 (한글)",
    "message": "사용자가 이해할 수 있는 메시지",
    "action": "구체적인 다음 행동 안내",
    "technical": "개발자용 상세 정보 (로그용)"
}
```

## 에러 유형별 표준 메시지

### 🔑 인증 오류 (401, Unauthorized)

| 항목 | 내용 |
|------|------|
| 아이콘 | 🔑 |
| 메시지 | "API 키가 유효하지 않습니다." |
| 행동 안내 | "설정 페이지에서 API 키를 확인해주세요." |
| UI 추가 | [설정 페이지로 이동] 버튼 |

### ⏱️ 할당량 초과 (429, Rate Limit)

| 항목 | 내용 |
|------|------|
| 아이콘 | ⏱️ |
| 메시지 | "API 요청 한도를 초과했습니다." |
| 행동 안내 | "잠시 후 다시 시도하거나, 내일 다시 실행해주세요." |
| UI 추가 | 남은 할당량 표시 (가능한 경우) |

### 🌐 네트워크 오류 (Connection, Timeout)

| 항목 | 내용 |
|------|------|
| 아이콘 | 🌐 |
| 메시지 | "네트워크 연결에 실패했습니다." |
| 행동 안내 | "인터넷 연결을 확인하고 다시 시도해주세요." |
| UI 추가 | [재시도] 버튼 |

### 🎬 FFmpeg 오류

| 항목 | 내용 |
|------|------|
| 아이콘 | 🎬 |
| 메시지 | "영상 렌더링 중 오류가 발생했습니다." |
| 행동 안내 | "FFmpeg 설치를 확인하거나, 입력 파일을 확인해주세요." |
| UI 추가 | [FFmpeg 체크] 버튼 |

### 📁 파일 오류 (Not Found, Permission)

| 항목 | 내용 |
|------|------|
| 아이콘 | 📁 |
| 메시지 | "필요한 파일을 찾을 수 없습니다." 또는 "파일 접근 권한이 없습니다." |
| 행동 안내 | "파일 위치와 권한을 확인해주세요." |
| UI 추가 | 문제 파일 경로 표시 |

### ❌ 알 수 없는 오류

| 항목 | 내용 |
|------|------|
| 아이콘 | ❌ |
| 메시지 | "예상치 못한 오류가 발생했습니다." |
| 행동 안내 | "문제가 계속되면 로그 파일을 확인해주세요." |
| UI 추가 | [로그 보기] 버튼, 에러 코드 표시 |

## UI 에러 표시 패턴

### 기본 패턴

```python
if not result["success"]:
    error = result["error"]
    st.error(f"{error['type']}: {error['message']}")
    st.info(f"💡 {error['action']}")
```

### 상세 패턴 (디버그 정보 포함)

```python
if not result["success"]:
    error = result["error"]
    st.error(f"{error['type']}: {error['message']}")
    st.info(f"💡 {error['action']}")
    
    with st.expander("🔍 기술적 상세 정보"):
        st.code(error["technical"])
```

### 재시도 버튼 패턴

```python
if not result["success"]:
    error = result["error"]
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.error(f"{error['message']}")
    with col2:
        if st.button("🔄 재시도"):
            # 재시도 로직
            pass
    
    st.caption(f"💡 {error['action']}")
```

## 에러 로깅 규칙

```python
import logging

logger = logging.getLogger(__name__)

try:
    # 작업 수행
    pass
except Exception as e:
    # 1. 사용자용 에러 반환
    user_error = format_error(e, "context")
    
    # 2. 로그에 상세 기록
    logger.error(
        f"[{context}] {type(e).__name__}: {str(e)}",
        exc_info=True  # traceback 포함
    )
    
    return {"success": False, "error": user_error}
```

## 금지 사항

❌ **하지 말 것:**

```python
# 너무 기술적인 메시지
st.error(f"Exception: {str(e)}")

# 정보 없는 메시지
st.error("오류가 발생했습니다.")

# 영어 에러 그대로 노출
st.error("ConnectionRefusedError: [Errno 111] Connection refused")

# 다음 행동 안내 없음
st.error("API 키가 잘못되었습니다.")  # 그래서 어쩌라고?
```

✅ **이렇게 할 것:**

```python
st.error("🔑 인증 오류: API 키가 유효하지 않습니다.")
st.info("💡 설정 페이지에서 API 키를 확인해주세요.")
if st.button("⚙️ 설정으로 이동"):
    st.switch_page("settings")
```

---

# 📌 최종 테스트 체크리스트

## Task 7 (FFmpeg) 테스트

- [ ] FFmpeg 설치 체크 동작
- [ ] 기본 렌더링 동작 (이미지+음악→영상)
- [ ] 해상도 변경 동작
- [ ] Ken Burns 효과 동작
- [ ] 텍스트 오버레이 동작
- [ ] 썸네일 생성 동작
- [ ] 배치 렌더링 동작

## Task 8 (파이프라인) 테스트

- [ ] 전체 파이프라인 정상 동작
- [ ] --only-images, --only-videos 옵션 동작
- [ ] checkpoint 저장/복구 동작
- [ ] 진행률 콜백 동작
- [ ] 개별 실패 시 계속 진행
- [ ] 실행 리포트 생성

## Task 9 (UI) 테스트

- [ ] Streamlit 정상 실행
- [ ] 대시보드 통계 표시
- [ ] 음악 목록 표시 및 필터링
- [ ] 이미지 생성 실행 및 갤러리
- [ ] 영상 렌더링 실행 및 진행률
- [ ] 설정 저장/로드
- [ ] 실패 작업 재시도

## 통합 테스트

- [ ] 빈 상태에서 전체 플로우 (음악 1개 → 이미지 → 영상)
- [ ] 60개 트랙 배치 처리
- [ ] 중간에 강제 종료 후 재개
- [ ] API 키 없을 때 명확한 에러
- [ ] 모든 CLI 명령 동작

