"""
缓存工具类
提供内存缓存和Redis缓存功能
"""
import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List, Union, Callable
from datetime import datetime, timedelta
import logging
from functools import wraps

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    Redis = None
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

class CacheBackend(ABC):
    """缓存后端抽象基类"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """清空所有缓存"""
        pass
    
    @abstractmethod
    async def get_ttl(self, key: str) -> Optional[int]:
        """获取缓存TTL"""
        pass

class MemoryCache(CacheBackend):
    """内存缓存实现"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            if key not in self._cache:
                return None
            
            cache_item = self._cache[key]
            
            # 检查是否过期
            if cache_item['expires_at'] and time.time() > cache_item['expires_at']:
                await self._remove_key(key)
                return None
            
            # 更新访问时间
            self._access_times[key] = time.time()
            return cache_item['value']
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        async with self._lock:
            # 检查缓存大小限制
            if len(self._cache) >= self.max_size and key not in self._cache:
                await self._evict_lru()
            
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl if ttl > 0 else None
            
            self._cache[key] = {
                'value': value,
                'created_at': time.time(),
                'expires_at': expires_at
            }
            self._access_times[key] = time.time()
            
            return True
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        async with self._lock:
            return await self._remove_key(key)
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        return await self.get(key) is not None
    
    async def clear(self) -> bool:
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()
            self._access_times.clear()
            return True
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """获取缓存TTL"""
        async with self._lock:
            if key not in self._cache:
                return None
            
            cache_item = self._cache[key]
            if not cache_item['expires_at']:
                return -1  # 永不过期
            
            remaining = cache_item['expires_at'] - time.time()
            return max(0, int(remaining))
    
    async def _remove_key(self, key: str) -> bool:
        """移除缓存键"""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_times:
            del self._access_times[key]
        return True
    
    async def _evict_lru(self):
        """移除最近最少使用的缓存项"""
        if not self._access_times:
            return
        
        # 找到最久未访问的键
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        await self._remove_key(lru_key)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        async with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': 0,  # 简化实现，不统计命中率
                'memory_usage': sum(len(str(item)) for item in self._cache.values())
            }

class RedisCache(CacheBackend):
    """Redis缓存实现"""
    
    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 6379, 
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600,
        key_prefix: str = "cs:"
    ):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package is required for RedisCache")
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self._redis: Optional[Redis] = None
    
    async def _get_redis(self) -> Redis:
        """获取Redis连接"""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True
            )
        return self._redis
    
    def _make_key(self, key: str) -> str:
        """生成带前缀的键"""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            redis_client = await self._get_redis()
            value = await redis_client.get(self._make_key(key))
            
            if value is None:
                return None
            
            # 尝试JSON反序列化
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            redis_client = await self._get_redis()
            ttl = ttl or self.default_ttl
            
            # JSON序列化
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value, ensure_ascii=False, default=str)
            
            if ttl > 0:
                return await redis_client.setex(self._make_key(key), ttl, value)
            else:
                return await redis_client.set(self._make_key(key), value)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            redis_client = await self._get_redis()
            result = await redis_client.delete(self._make_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            redis_client = await self._get_redis()
            return await redis_client.exists(self._make_key(key)) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def clear(self) -> bool:
        """清空所有缓存"""
        try:
            redis_client = await self._get_redis()
            keys = await redis_client.keys(f"{self.key_prefix}*")
            if keys:
                await redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """获取缓存TTL"""
        try:
            redis_client = await self._get_redis()
            ttl = await redis_client.ttl(self._make_key(key))
            return ttl if ttl >= 0 else None
        except Exception as e:
            logger.error(f"Redis TTL error: {e}")
            return None
    
    async def close(self):
        """关闭Redis连接"""
        if self._redis:
            await self._redis.close()

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, backend: CacheBackend):
        self.backend = backend
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        return await self.backend.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, expire: Optional[int] = None) -> bool:
        """设置缓存"""
        # 兼容expire参数，优先使用ttl
        cache_ttl = ttl if ttl is not None else expire
        return await self.backend.set(key, value, cache_ttl)
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        return await self.backend.delete(key)
    
    async def get_or_set(
        self, 
        key: str, 
        factory: Callable[[], Any], 
        ttl: Optional[int] = None
    ) -> Any:
        """获取缓存，如果不存在则通过工厂函数创建"""
        value = await self.get(key)
        if value is not None:
            return value
        
        # 调用工厂函数
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        await self.set(key, value, ttl)
        return value
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存"""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    async def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量设置缓存"""
        success = True
        for key, value in mapping.items():
            if not await self.set(key, value, ttl):
                success = False
        return success
    
    async def delete_many(self, keys: List[str]) -> int:
        """批量删除缓存"""
        count = 0
        for key in keys:
            if await self.delete(key):
                count += 1
        return count
    
    async def clear(self) -> bool:
        """清空所有缓存"""
        return await self.backend.clear()

def cached(
    ttl: int = 3600, 
    key_func: Optional[Callable] = None,
    cache_manager: Optional[CacheManager] = None
):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存时间（秒）
        key_func: 键生成函数
        cache_manager: 缓存管理器
    
    Returns:
        装饰器函数
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 使用默认缓存管理器
            if cache_manager is None:
                cm = get_default_cache_manager()
            else:
                cm = cache_manager
            
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认键生成策略
                func_name = f"{func.__module__}.{func.__name__}"
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"{func_name}:{hash(args_str)}"
            
            # 尝试从缓存获取
            cached_result = await cm.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await cm.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator

# 全局缓存管理器
_default_cache_manager: Optional[CacheManager] = None

def init_cache(backend: CacheBackend):
    """初始化默认缓存管理器"""
    global _default_cache_manager
    _default_cache_manager = CacheManager(backend)

def get_default_cache_manager() -> CacheManager:
    """获取默认缓存管理器"""
    if _default_cache_manager is None:
        # 使用内存缓存作为默认后端
        init_cache(MemoryCache())
    return _default_cache_manager

# 缓存键生成器
class CacheKeyGenerator:
    """缓存键生成器"""
    
    @staticmethod
    def user_session(user_id: str, session_id: str) -> str:
        """用户会话缓存键"""
        return f"user_session:{user_id}:{session_id}"
    
    @staticmethod
    def agent_response(agent_id: str, query_hash: str) -> str:
        """智能体响应缓存键"""
        return f"agent_response:{agent_id}:{query_hash}"
    
    @staticmethod
    def knowledge_search(query: str, category: Optional[str] = None) -> str:
        """知识搜索缓存键"""
        query_hash = hash(query)
        if category:
            return f"knowledge_search:{query_hash}:{category}"
        return f"knowledge_search:{query_hash}"
    
    @staticmethod
    def user_profile(user_id: str) -> str:
        """用户档案缓存键"""
        return f"user_profile:{user_id}"
    
    @staticmethod
    def system_stats(metric_type: str) -> str:
        """系统统计缓存键"""
        return f"system_stats:{metric_type}"