"""
메모리 기반 프레임 버퍼 관리자
- Redis 대신 in-memory deque를 사용하여 실시간 프레임 스트리밍
- 최대 20프레임 유지 (sliding window)
"""

from collections import deque
import numpy as np
from typing import List, Optional
import asyncio

# 전역 프레임 버퍼 (thread-safe를 위해 lock 사용)
_frame_buffer: deque = deque(maxlen=20)
_buffer_lock = asyncio.Lock()


async def add_frame(frame: np.ndarray) -> None:
    """
    프레임을 버퍼에 추가 (최대 20프레임 유지)
    Args:
        frame: OpenCV 이미지 (BGR, np.ndarray)
    """
    async with _buffer_lock:
        _frame_buffer.append(frame.copy())  # 복사본 저장


async def get_latest_frames(limit: int = 20) -> List[np.ndarray]:
    """
    버퍼에서 최근 프레임들을 가져옴
    Args:
        limit: 가져올 최대 프레임 수 (기본값 20)
    Returns:
        프레임 리스트 (최신 순서, 복사본 반환)
    """
    async with _buffer_lock:
        frames = list(_frame_buffer)
        # 최신 프레임부터 역순으로 반환
        frames.reverse()
        return frames[:limit].copy() if frames else []


async def get_frame_count() -> int:
    """버퍼에 저장된 프레임 수 반환"""
    async with _buffer_lock:
        return len(_frame_buffer)


async def clear_buffer() -> None:
    """버퍼 초기화"""
    async with _buffer_lock:
        _frame_buffer.clear()

