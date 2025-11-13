"""
하이브리드 프레임 수집기 (최적화 버전)
- 평소: 최소한의 프레임만 유지 (device_monitor용, 약 5~10프레임)
- CV 분석 필요 시: 즉시 사용 가능하도록 최근 프레임 확보
- 메모리 효율적 + 즉시 사용 가능
"""

from collections import deque
import numpy as np
from typing import List, Optional
import asyncio
from datetime import datetime

# 실시간 프레임 스트림 (최소한만 유지)
# device_monitor는 2초마다 1장만 필요하므로, 최소 5~10프레임이면 충분
# CV 분석은 필요할 때 최근 프레임을 수집하므로, 약간의 버퍼만 유지
_FRAME_BUFFER_SIZE = 10  # 최대 10프레임 (약 0.33초 @ 30fps) - device_monitor용
_frame_stream: deque = deque(maxlen=_FRAME_BUFFER_SIZE)
_stream_lock = asyncio.Lock()

# CV 분석용 실시간 수집 버퍼 (필요할 때만 활성화)
_cv_collection_active = False
_cv_collection_buffer: deque = deque(maxlen=30)  # CV 분석용 (약 1초 @ 30fps)
_cv_collection_lock = asyncio.Lock()


async def add_frame(frame: np.ndarray, timestamp: Optional[float] = None) -> None:
    """
    프레임을 스트림에 추가
    - 기본 버퍼: 최소한만 유지 (device_monitor용)
    - CV 수집 버퍼: 활성화 시에만 추가
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    frame_data = {
        "frame": frame.copy(),
        "timestamp": timestamp
    }
    
    # 기본 버퍼에 항상 추가 (device_monitor용)
    async with _stream_lock:
        _frame_stream.append(frame_data)
    
    # CV 수집 버퍼에 조건부 추가
    async with _cv_collection_lock:
        if _cv_collection_active:
            _cv_collection_buffer.append(frame_data)


async def start_cv_collection() -> None:
    """CV 분석 시작 시 호출 - 이후 프레임들을 수집 시작"""
    global _cv_collection_active
    async with _cv_collection_lock:
        _cv_collection_active = True
        _cv_collection_buffer.clear()  # 새로 시작


async def stop_cv_collection() -> None:
    """CV 분석 완료 시 호출 - 수집 중지"""
    global _cv_collection_active
    async with _cv_collection_lock:
        _cv_collection_active = False
        _cv_collection_buffer.clear()  # 메모리 해제


async def collect_recent_frames(
    duration_seconds: float = 1.0,
    max_frames: int = 20,
    min_frames: int = 3
) -> List[np.ndarray]:
    """
    CV 분석용 프레임 수집
    - CV 수집 버퍼 + 기본 버퍼에서 최근 N초 분량 수집
    """
    # 두 lock을 순차적으로 획득
    async with _cv_collection_lock:
        cv_frames = list(_cv_collection_buffer)
    
    async with _stream_lock:
        stream_frames = list(_frame_stream)
    
    # 두 버퍼 합치기 (CV 버퍼가 우선)
    all_frames = cv_frames + stream_frames
    
    if len(all_frames) == 0:
        return []
    
    # 중복 제거 (타임스탬프 기준)
    seen_timestamps = set()
    unique_frames = []
    for item in all_frames:
        ts = item["timestamp"]
        if ts not in seen_timestamps:
            seen_timestamps.add(ts)
            unique_frames.append(item)
    
    # 타임스탬프 기준 정렬 (최신순)
    unique_frames.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # 최근 N초 분량 필터링
    now = datetime.now().timestamp()
    cutoff_time = now - duration_seconds
    
    recent_frames = []
    for item in unique_frames:
        if item["timestamp"] >= cutoff_time:
            recent_frames.append(item["frame"].copy())
            if len(recent_frames) >= max_frames:
                break
    
    # 최소 프레임 수 확인
    if len(recent_frames) < min_frames:
        return []
    
    return recent_frames


async def collect_latest_n_frames(n: int = 1) -> List[np.ndarray]:
    """
    최근 N개 프레임 수집 (device_monitor용 - 간단한 버전)
    """
    async with _stream_lock:
        if len(_frame_stream) == 0:
            return []
        
        frames = [item["frame"].copy() for item in list(_frame_stream)[-n:]]
        frames.reverse()  # 최신 순서
        return frames


async def get_stream_size() -> int:
    """스트림에 저장된 프레임 수 반환"""
    async with _stream_lock:
        return len(_frame_stream)
