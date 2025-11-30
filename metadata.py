"""
메타데이터 분석 모듈
MP3 파일의 길이, 태그 정보 분석 및 처리
"""

import os
from pathlib import Path
from typing import Dict, Optional, List, Any
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC
from mutagen import File as MutagenFile
from pydub import AudioSegment

from config_manager import load_config, get_path
from db_manager import TrackDB
from logger import setup_logger


class AudioFormatError(Exception):
    """오디오 포맷 관련 예외"""
    pass


def get_duration_mutagen(path: str) -> float:
    """
    mutagen 라이브러리 사용하여 오디오 길이 반환
    
    Args:
        path: 파일 경로
    
    Returns:
        길이(초), 소수점 포함
    
    Raises:
        FileNotFoundError: 파일 없음
        AudioFormatError: 지원하지 않는 포맷
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    
    try:
        audio = MP3(path)
        return float(audio.info.length)
    except Exception as e:
        raise AudioFormatError(f"오디오 파일 분석 실패 ({path}): {str(e)}")


def get_duration_pydub(path: str) -> float:
    """
    pydub 라이브러리 사용하여 오디오 길이 반환
    
    Args:
        path: 파일 경로
    
    Returns:
        길이(초), 소수점 포함
    
    Raises:
        FileNotFoundError: 파일 없음
        AudioFormatError: 지원하지 않는 포맷
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    
    try:
        audio = AudioSegment.from_mp3(path)
        return len(audio) / 1000.0  # milliseconds to seconds
    except Exception as e:
        raise AudioFormatError(f"오디오 파일 분석 실패 ({path}): {str(e)}")


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
    if method == "mutagen":
        return get_duration_mutagen(path)
    elif method == "pydub":
        return get_duration_pydub(path)
    else:
        raise ValueError(f"지원하지 않는 메서드: {method}")


def seconds_to_mmss(seconds: float) -> str:
    """
    초를 MM:SS 형식으로 변환
    
    Args:
        seconds: 초 단위 시간
    
    Returns:
        MM:SS 형식 문자열
        예: 185.5 → "03:05"
    """
    if seconds < 0:
        seconds = 0
    
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    
    return f"{minutes:02d}:{secs:02d}"


def seconds_to_hhmmss(seconds: float) -> str:
    """
    초를 HH:MM:SS 형식으로 변환
    
    Args:
        seconds: 초 단위 시간
    
    Returns:
        HH:MM:SS 형식 문자열
        예: 3725.5 → "01:02:05"
    """
    if seconds < 0:
        seconds = 0
    
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def seconds_to_ffmpeg_time(seconds: float) -> str:
    """
    FFmpeg 타임스탬프 형식으로 변환
    
    Args:
        seconds: 초 단위 시간
    
    Returns:
        FFmpeg 타임스탬프 형식 문자열
        예: 185.5 → "00:03:05.500"
    """
    if seconds < 0:
        seconds = 0
    
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    milliseconds = int((seconds - total_seconds) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def parse_time_string(time_str: str) -> float:
    """
    시간 문자열을 초로 변환
    
    Args:
        time_str: 시간 문자열 ("MM:SS" 또는 "HH:MM:SS")
    
    Returns:
        초 단위 시간
    
    예:
        "03:05" → 185.0
        "01:02:05" → 3725.0
    """
    parts = time_str.strip().split(":")
    
    if len(parts) == 2:
        # MM:SS 형식
        minutes, seconds = map(int, parts)
        return float(minutes * 60 + seconds)
    elif len(parts) == 3:
        # HH:MM:SS 형식
        hours, minutes, seconds = map(int, parts)
        return float(hours * 3600 + minutes * 60 + seconds)
    else:
        raise ValueError(f"지원하지 않는 시간 형식: {time_str}")


def get_mp3_tags(path: str) -> Dict[str, Any]:
    """
    MP3 태그 정보 추출
    
    Args:
        path: 파일 경로
    
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
    result = {
        "title": None,
        "artist": None,
        "album": None,
        "genre": None,
        "year": None,
        "duration": None
    }
    
    try:
        # 길이 정보
        result["duration"] = get_audio_duration(path, method="mutagen")
    except Exception:
        pass
    
    try:
        audio_file = MutagenFile(path)
        if audio_file is None:
            return result
        
        # ID3 태그 추출
        if hasattr(audio_file, 'tags') and audio_file.tags is not None:
            tags = audio_file.tags
            
            # Title
            if 'TIT2' in tags:
                result["title"] = str(tags['TIT2'][0])
            elif 'TITLE' in tags:
                result["title"] = str(tags['TITLE'][0])
            
            # Artist
            if 'TPE1' in tags:
                result["artist"] = str(tags['TPE1'][0])
            elif 'ARTIST' in tags:
                result["artist"] = str(tags['ARTIST'][0])
            
            # Album
            if 'TALB' in tags:
                result["album"] = str(tags['TALB'][0])
            elif 'ALBUM' in tags:
                result["album"] = str(tags['ALBUM'][0])
            
            # Genre
            if 'TCON' in tags:
                result["genre"] = str(tags['TCON'][0])
            elif 'GENRE' in tags:
                result["genre"] = str(tags['GENRE'][0])
            
            # Year
            if 'TDRC' in tags:
                year_str = str(tags['TDRC'][0])
                try:
                    # 연도만 추출 (예: "2025" 또는 "2025-01-01")
                    result["year"] = int(year_str.split('-')[0])
                except (ValueError, IndexError):
                    pass
            elif 'DATE' in tags:
                year_str = str(tags['DATE'][0])
                try:
                    result["year"] = int(year_str.split('-')[0])
                except (ValueError, IndexError):
                    pass
    
    except Exception:
        # 태그가 없거나 읽을 수 없는 경우 None 유지
        pass
    
    return result


def set_mp3_tags(path: str, tags: Dict[str, Any]) -> bool:
    """
    MP3 태그 설정 (Suno 생성 후 메타데이터 추가용)
    
    Args:
        path: 파일 경로
        tags: 태그 딕셔너리 {
            "title": str,
            "artist": str,
            "album": str,
            "genre": str,
            "year": int
        }
    
    Returns:
        성공 여부
    """
    try:
        audio_file = MP3(path, ID3=ID3)
        
        # ID3 태그가 없으면 생성
        if audio_file.tags is None:
            audio_file.add_tags()
        
        # 태그 설정
        if "title" in tags and tags["title"]:
            audio_file.tags.add(TIT2(encoding=3, text=tags["title"]))
        
        if "artist" in tags and tags["artist"]:
            audio_file.tags.add(TPE1(encoding=3, text=tags["artist"]))
        
        if "album" in tags and tags["album"]:
            audio_file.tags.add(TALB(encoding=3, text=tags["album"]))
        
        if "genre" in tags and tags["genre"]:
            audio_file.tags.add(TCON(encoding=3, text=tags["genre"]))
        
        if "year" in tags and tags["year"]:
            year_str = str(tags["year"])
            audio_file.tags.add(TDRC(encoding=3, text=year_str))
        
        # 저장
        audio_file.save()
        return True
    
    except Exception as e:
        logger = setup_logger("metadata")
        logger.error(f"태그 설정 실패 ({path}): {e}")
        return False


def analyze_folder(folder_path: str) -> List[Dict[str, Any]]:
    """
    폴더 내 모든 mp3 분석
    
    Args:
        folder_path: 폴더 경로
    
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
    folder = Path(folder_path)
    if not folder.exists():
        return []
    
    results = []
    
    # MP3 파일만 찾기
    for file_path in folder.glob("*.mp3"):
        try:
            file_name = file_path.name
            track_id = file_path.stem
            
            # 파일 크기
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            
            # 길이 분석
            duration = get_audio_duration(str(file_path), method="mutagen")
            duration_formatted = seconds_to_mmss(duration)
            
            # 태그 정보
            tags = get_mp3_tags(str(file_path))
            
            results.append({
                "file_name": file_name,
                "file_path": str(file_path),
                "track_id": track_id,
                "duration": duration,
                "duration_formatted": duration_formatted,
                "file_size_mb": round(file_size_mb, 2),
                "tags": tags
            })
        
        except Exception as e:
            logger = setup_logger("metadata")
            logger.warning(f"파일 분석 실패 ({file_path}): {e}")
            continue
    
    return results


def get_total_duration(folder_path: str) -> float:
    """
    폴더 내 모든 음악 총 길이 (초)
    
    Args:
        folder_path: 폴더 경로
    
    Returns:
        총 길이(초)
    """
    files = analyze_folder(folder_path)
    return sum(f["duration"] for f in files if f.get("duration"))


def get_folder_statistics(folder_path: str) -> Dict[str, Any]:
    """
    폴더 통계
    
    Args:
        folder_path: 폴더 경로
    
    Returns:
        {
            "total_files": 60,
            "total_duration_seconds": 12500.5,
            "total_duration_formatted": "03:28:20",
            "average_duration": 208.3,
            "total_size_mb": 245.8
        }
    """
    files = analyze_folder(folder_path)
    
    if not files:
        return {
            "total_files": 0,
            "total_duration_seconds": 0.0,
            "total_duration_formatted": "00:00",
            "average_duration": 0.0,
            "total_size_mb": 0.0
        }
    
    total_files = len(files)
    total_duration = sum(f["duration"] for f in files if f.get("duration"))
    total_size = sum(f["file_size_mb"] for f in files)
    average_duration = total_duration / total_files if total_files > 0 else 0.0
    
    return {
        "total_files": total_files,
        "total_duration_seconds": round(total_duration, 2),
        "total_duration_formatted": seconds_to_hhmmss(total_duration),
        "average_duration": round(average_duration, 2),
        "total_size_mb": round(total_size, 2)
    }


def update_track_metadata(track_id: str, db: TrackDB) -> bool:
    """
    단일 트랙 메타데이터 DB 업데이트
    
    Args:
        track_id: 트랙 ID
        db: TrackDB 인스턴스
    
    Returns:
        성공 여부
    """
    try:
        track = db.get_track(track_id)
        if not track:
            return False
        
        music_info = track.get("music", {})
        file_path = music_info.get("file_path")
        
        if not file_path or not os.path.exists(file_path):
            return False
        
        # 길이 분석
        duration = get_audio_duration(file_path, method="mutagen")
        
        # 태그 정보
        tags = get_mp3_tags(file_path)
        
        # DB 업데이트
        updates = {
            "music": {
                "duration_seconds": duration,
                "duration_formatted": seconds_to_mmss(duration)
            }
        }
        
        # 태그 정보도 추가 (있는 경우)
        if tags.get("title"):
            updates["music"]["title"] = tags["title"]
        if tags.get("artist"):
            updates["music"]["artist"] = tags["artist"]
        
        db.update_track(track_id, updates)
        return True
    
    except Exception as e:
        logger = setup_logger("metadata")
        logger.error(f"메타데이터 업데이트 실패 ({track_id}): {e}")
        return False


def update_all_metadata(db: TrackDB) -> Dict[str, int]:
    """
    모든 트랙 메타데이터 일괄 업데이트
    
    Args:
        db: TrackDB 인스턴스
    
    Returns:
        {
            "updated": 45,
            "skipped": 15,  # 이미 있는 경우
            "failed": 0
        }
    """
    all_tracks = db.get_all_tracks()
    updated = 0
    skipped = 0
    failed = 0
    
    for track in all_tracks:
        track_id = track.get("track_id")
        if not track_id:
            continue
        
        music_info = track.get("music", {})
        
        # 이미 duration이 있으면 스킵 (선택적)
        if music_info.get("duration_seconds"):
            skipped += 1
            continue
        
        if update_track_metadata(track_id, db):
            updated += 1
        else:
            failed += 1
    
    return {
        "updated": updated,
        "skipped": skipped,
        "failed": failed
    }


def get_waveform_data(path: str, samples: int = 100) -> List[float]:
    """
    파형 데이터 추출 (정규화된 진폭)
    
    Args:
        path: 파일 경로
        samples: 샘플 개수
    
    Returns:
        [0.0 ~ 1.0] 범위의 진폭 리스트
    """
    try:
        audio = AudioSegment.from_mp3(path)
        
        # 오디오를 샘플 개수만큼 나누기
        chunk_length = len(audio) // samples
        waveform = []
        
        for i in range(samples):
            start = i * chunk_length
            end = start + chunk_length
            
            if end > len(audio):
                end = len(audio)
            
            chunk = audio[start:end]
            
            # RMS (Root Mean Square) 계산하여 진폭 추정
            if len(chunk) > 0:
                rms = chunk.rms
                # 정규화 (최대값 32767.0 기준)
                normalized = min(rms / 32767.0, 1.0)
                waveform.append(normalized)
            else:
                waveform.append(0.0)
        
        return waveform
    
    except Exception as e:
        logger = setup_logger("metadata")
        logger.error(f"파형 데이터 추출 실패 ({path}): {e}")
        return [0.0] * samples


def detect_bpm(path: str) -> Optional[float]:
    """
    BPM 감지 (선택)
    
    Args:
        path: 파일 경로
    
    Returns:
        BPM 값 또는 None
    """
    # BPM 감지는 복잡한 알고리즘이 필요하므로
    # 기본 구현은 제공하지 않고, 향후 확장 가능하도록 구조만 제공
    # 실제 구현은 librosa 같은 라이브러리 필요
    logger = setup_logger("metadata")
    logger.warning("BPM 감지 기능은 아직 구현되지 않았습니다.")
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="메타데이터 분석 도구")
    parser.add_argument("--analyze", type=str, help="단일 파일 분석")
    parser.add_argument("--folder", type=str, help="폴더 전체 분석")
    parser.add_argument("--stats", type=str, help="폴더 통계 출력")
    parser.add_argument("--update-db", action="store_true", help="DB 업데이트")
    parser.add_argument("--set-tags", type=str, help="태그 설정 (트랙 ID)")
    parser.add_argument("--title", type=str, help="제목")
    parser.add_argument("--artist", type=str, help="아티스트")
    parser.add_argument("--album", type=str, help="앨범")
    parser.add_argument("--genre", type=str, help="장르")
    parser.add_argument("--year", type=int, help="연도")
    
    args = parser.parse_args()
    
    if args.analyze:
        # 단일 파일 분석
        file_path = args.analyze
        print(f"\n📁 파일 분석: {file_path}")
        print("=" * 60)
        
        try:
            duration = get_audio_duration(file_path)
            tags = get_mp3_tags(file_path)
            
            print(f"길이: {seconds_to_mmss(duration)} ({duration:.2f}초)")
            print(f"\n태그 정보:")
            print(f"  제목: {tags.get('title', 'N/A')}")
            print(f"  아티스트: {tags.get('artist', 'N/A')}")
            print(f"  앨범: {tags.get('album', 'N/A')}")
            print(f"  장르: {tags.get('genre', 'N/A')}")
            print(f"  연도: {tags.get('year', 'N/A')}")
        
        except Exception as e:
            print(f"❌ 분석 실패: {e}")
    
    elif args.folder:
        # 폴더 전체 분석
        folder_path = args.folder
        print(f"\n📁 폴더 분석: {folder_path}")
        print("=" * 60)
        
        files = analyze_folder(folder_path)
        
        if not files:
            print("분석할 파일이 없습니다.")
        else:
            print(f"\n총 {len(files)}개 파일")
            print("\n파일 목록:")
            print(f"{'파일명':<30} {'길이':<10} {'크기(MB)':<10}")
            print("-" * 60)
            
            for f in files:
                print(f"{f['file_name']:<30} {f['duration_formatted']:<10} {f['file_size_mb']:<10.2f}")
    
    elif args.stats:
        # 통계 출력
        folder_path = args.stats
        print(f"\n📊 폴더 통계: {folder_path}")
        print("=" * 60)
        
        stats = get_folder_statistics(folder_path)
        
        print(f"총 파일 수: {stats['total_files']}개")
        print(f"총 길이: {stats['total_duration_formatted']} ({stats['total_duration_seconds']:.2f}초)")
        print(f"평균 길이: {seconds_to_mmss(stats['average_duration'])}")
        print(f"총 크기: {stats['total_size_mb']:.2f} MB")
    
    elif args.update_db:
        # DB 업데이트
        print("\n🔄 DB 메타데이터 업데이트 중...")
        print("=" * 60)
        
        db = TrackDB()
        result = update_all_metadata(db)
        
        print(f"\n✅ 업데이트 완료!")
        print(f"  - 업데이트: {result['updated']}개")
        print(f"  - 스킵: {result['skipped']}개")
        print(f"  - 실패: {result['failed']}개")
    
    elif args.set_tags:
        # 태그 설정
        track_id = args.set_tags
        config = load_config()
        music_folder = Path(get_path('music_folder', config))
        file_path = music_folder / f"{track_id}.mp3"
        
        if not file_path.exists():
            print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        else:
            tags = {}
            if args.title:
                tags["title"] = args.title
            if args.artist:
                tags["artist"] = args.artist
            if args.album:
                tags["album"] = args.album
            if args.genre:
                tags["genre"] = args.genre
            if args.year:
                tags["year"] = args.year
            
            if tags:
                if set_mp3_tags(str(file_path), tags):
                    print(f"✅ 태그 설정 완료: {track_id}")
                    print(f"  설정된 태그: {tags}")
                else:
                    print(f"❌ 태그 설정 실패: {track_id}")
            else:
                print("설정할 태그가 없습니다.")
    
    else:
        parser.print_help()


