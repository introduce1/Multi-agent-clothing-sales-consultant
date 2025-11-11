# -*- coding: utf-8 -*-
"""
速率限制器
提供基于时间窗口的速率限制功能
"""
import time
import asyncio
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        初始化速率限制器
        
        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口大小（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key: str) -> Tuple[bool, Dict[str, any]]:
        """
        检查是否允许请求
        
        Args:
            key: 限制键（如用户ID、IP地址等）
            
        Returns:
            (是否允许, 限制信息)
        """
        async with self._lock:
            current_time = time.time()
            
            # 清理过期的请求记录
            self._cleanup_expired_requests(key, current_time)
            
            # 检查当前请求数
            current_requests = len(self.requests[key])
            
            if current_requests >= self.max_requests:
                # 超出限制
                oldest_request = self.requests[key][0] if self.requests[key] else current_time
                reset_time = oldest_request + self.time_window
                
                return False, {
                    "allowed": False,
                    "current_requests": current_requests,
                    "max_requests": self.max_requests,
                    "time_window": self.time_window,
                    "reset_time": reset_time,
                    "retry_after": max(0, reset_time - current_time)
                }
            
            # 允许请求，记录时间戳
            self.requests[key].append(current_time)
            
            return True, {
                "allowed": True,
                "current_requests": current_requests + 1,
                "max_requests": self.max_requests,
                "time_window": self.time_window,
                "remaining_requests": self.max_requests - current_requests - 1
            }
    
    def _cleanup_expired_requests(self, key: str, current_time: float):
        """清理过期的请求记录"""
        cutoff_time = current_time - self.time_window
        
        while self.requests[key] and self.requests[key][0] <= cutoff_time:
            self.requests[key].popleft()
    
    async def reset(self, key: str):
        """重置指定键的限制"""
        async with self._lock:
            if key in self.requests:
                del self.requests[key]
    
    async def get_status(self, key: str) -> Dict[str, any]:
        """获取限制状态"""
        async with self._lock:
            current_time = time.time()
            self._cleanup_expired_requests(key, current_time)
            
            current_requests = len(self.requests[key])
            oldest_request = self.requests[key][0] if self.requests[key] else current_time
            reset_time = oldest_request + self.time_window
            
            return {
                "current_requests": current_requests,
                "max_requests": self.max_requests,
                "time_window": self.time_window,
                "remaining_requests": max(0, self.max_requests - current_requests),
                "reset_time": reset_time,
                "window_start": oldest_request if self.requests[key] else None
            }


class TokenBucketRateLimiter:
    """令牌桶速率限制器"""
    
    def __init__(self, capacity: int = 100, refill_rate: float = 10.0):
        """
        初始化令牌桶速率限制器
        
        Args:
            capacity: 桶容量
            refill_rate: 每秒补充令牌数
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"tokens": capacity, "last_refill": time.time()}
        )
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key: str, tokens_required: int = 1) -> Tuple[bool, Dict[str, any]]:
        """
        检查是否允许请求
        
        Args:
            key: 限制键
            tokens_required: 需要的令牌数
            
        Returns:
            (是否允许, 限制信息)
        """
        async with self._lock:
            current_time = time.time()
            bucket = self.buckets[key]
            
            # 计算需要补充的令牌
            time_passed = current_time - bucket["last_refill"]
            tokens_to_add = time_passed * self.refill_rate
            
            # 更新令牌数（不超过容量）
            bucket["tokens"] = min(self.capacity, bucket["tokens"] + tokens_to_add)
            bucket["last_refill"] = current_time
            
            if bucket["tokens"] >= tokens_required:
                # 有足够令牌
                bucket["tokens"] -= tokens_required
                
                return True, {
                    "allowed": True,
                    "tokens_remaining": bucket["tokens"],
                    "capacity": self.capacity,
                    "refill_rate": self.refill_rate
                }
            else:
                # 令牌不足
                time_to_refill = (tokens_required - bucket["tokens"]) / self.refill_rate
                
                return False, {
                    "allowed": False,
                    "tokens_remaining": bucket["tokens"],
                    "capacity": self.capacity,
                    "refill_rate": self.refill_rate,
                    "retry_after": time_to_refill
                }
    
    async def reset(self, key: str):
        """重置指定键的令牌桶"""
        async with self._lock:
            if key in self.buckets:
                self.buckets[key] = {
                    "tokens": self.capacity,
                    "last_refill": time.time()
                }


# 默认实例
default_rate_limiter = RateLimiter()