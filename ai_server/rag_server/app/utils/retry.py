# app/utils/retry.py
"""
재시도 유틸리티 함수
"""
import asyncio
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    *args,
    **kwargs
) -> Any:
    """
    지수 백오프를 사용한 재시도 로직
    
    Args:
        func: 실행할 비동기 함수
        max_attempts: 최대 재시도 횟수
        initial_delay: 초기 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        backoff_factor: 백오프 배수
        exceptions: 재시도할 예외 타입
        *args, **kwargs: 함수에 전달할 인자
    
    Returns:
        함수 실행 결과
    
    Raises:
        마지막 시도에서 발생한 예외
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(1, max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            
            if attempt < max_attempts:
                logger.warning(
                    f"⚠️ {func.__name__} 실행 실패 (시도 {attempt}/{max_attempts}): {e}. "
                    f"{delay:.1f}초 후 재시도..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"❌ {func.__name__} 실행 실패 (최대 재시도 횟수 도달): {e}")
    
    # 모든 재시도 실패 시 마지막 예외 발생
    raise last_exception

