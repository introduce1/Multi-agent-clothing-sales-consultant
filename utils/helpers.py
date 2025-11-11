"""
辅助函数模块
提供通用的工具函数
"""
import uuid
import re
import hashlib
import secrets
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlparse
import asyncio
from functools import wraps
import time

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))

def generate_id(prefix: str = "") -> str:
    """
    生成唯一ID
    
    Args:
        prefix: ID前缀
    
    Returns:
        唯一ID字符串
    """
    unique_id = str(uuid.uuid4())
    return f"{prefix}{unique_id}" if prefix else unique_id

def generate_short_id(length: int = 8) -> str:
    """
    生成短ID
    
    Args:
        length: ID长度
    
    Returns:
        短ID字符串
    """
    return secrets.token_urlsafe(length)[:length]

def generate_session_id() -> str:
    """生成会话ID"""
    return generate_id("session_")

def generate_customer_id() -> str:
    """生成客户ID"""
    return generate_id("customer_")

def generate_order_id() -> str:
    """生成订单ID"""
    timestamp = int(time.time())
    random_part = generate_short_id(6)
    return f"order_{timestamp}_{random_part}"

def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化日期时间
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串
    
    Returns:
        格式化后的日期时间字符串
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # 转换为北京时间
    beijing_dt = dt.astimezone(BEIJING_TZ)
    return beijing_dt.strftime(format_str)

def parse_datetime(dt_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    解析日期时间字符串
    
    Args:
        dt_str: 日期时间字符串
        format_str: 格式字符串
    
    Returns:
        日期时间对象
    """
    dt = datetime.strptime(dt_str, format_str)
    return dt.replace(tzinfo=BEIJING_TZ)

def get_beijing_now() -> datetime:
    """获取北京时间的当前时间"""
    return datetime.now(BEIJING_TZ)

def validate_email(email: str) -> bool:
    """
    验证邮箱格式
    
    Args:
        email: 邮箱地址
    
    Returns:
        是否有效
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """
    验证手机号格式（中国大陆）
    
    Args:
        phone: 手机号
    
    Returns:
        是否有效
    """
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))

def validate_url(url: str) -> bool:
    """
    验证URL格式
    
    Args:
        url: URL地址
    
    Returns:
        是否有效
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def hash_password(password: str) -> str:
    """
    哈希密码
    
    Args:
        password: 原始密码
    
    Returns:
        哈希后的密码
    """
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{password_hash.hex()}"

def verify_password(password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        password: 原始密码
        hashed_password: 哈希后的密码
    
    Returns:
        是否匹配
    """
    try:
        salt, password_hash = hashed_password.split(':')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return password_hash == new_hash.hex()
    except Exception:
        return False

def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    清理字符串
    
    Args:
        text: 原始文本
        max_length: 最大长度
    
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 移除控制字符
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # 限制长度
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    提取关键词
    
    Args:
        text: 文本内容
        max_keywords: 最大关键词数量
    
    Returns:
        关键词列表
    """
    # 简单的关键词提取（实际项目中可以使用更复杂的NLP方法）
    words = re.findall(r'\b\w{2,}\b', text.lower())
    
    # 过滤停用词（简化版）
    stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
    keywords = [word for word in words if word not in stop_words and len(word) > 1]
    
    # 统计词频并返回最常见的关键词
    from collections import Counter
    word_counts = Counter(keywords)
    return [word for word, count in word_counts.most_common(max_keywords)]

def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节数
    
    Returns:
        格式化后的文件大小
    """
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀
    
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def deep_merge_dict(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并字典
    
    Args:
        dict1: 字典1
        dict2: 字典2
    
    Returns:
        合并后的字典
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result

def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    安全的JSON解析
    
    Args:
        json_str: JSON字符串
        default: 默认值
    
    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """
    安全的JSON序列化
    
    Args:
        obj: 要序列化的对象
        default: 默认值
    
    Returns:
        JSON字符串或默认值
    """
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return default

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    将列表分块
    
    Args:
        lst: 原始列表
        chunk_size: 块大小
    
    Returns:
        分块后的列表
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def flatten_list(nested_list: List[List[Any]]) -> List[Any]:
    """
    展平嵌套列表
    
    Args:
        nested_list: 嵌套列表
    
    Returns:
        展平后的列表
    """
    return [item for sublist in nested_list for item in sublist]

def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算文本相似度（简单版本）
    
    Args:
        text1: 文本1
        text2: 文本2
    
    Returns:
        相似度分数 (0-1)
    """
    # 简单的基于词汇重叠的相似度计算
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 and not words2:
        return 1.0
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)

def retry_async(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    异步重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间
        backoff: 退避倍数
    
    Returns:
        装饰器函数
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator

def rate_limit(calls_per_second: float = 1.0):
    """
    速率限制装饰器
    
    Args:
        calls_per_second: 每秒调用次数
    
    Returns:
        装饰器函数
    """
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            
            if left_to_wait > 0:
                await asyncio.sleep(left_to_wait)
            
            last_called[0] = time.time()
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

class Timer:
    """计时器工具类"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """开始计时"""
        self.start_time = time.time()
        return self
    
    def stop(self):
        """停止计时"""
        self.end_time = time.time()
        return self
    
    @property
    def elapsed(self) -> float:
        """获取经过的时间（秒）"""
        if self.start_time is None:
            return 0.0
        
        end_time = self.end_time or time.time()
        return end_time - self.start_time
    
    def __enter__(self):
        return self.start()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

def format_duration(seconds: float) -> str:
    """
    格式化持续时间
    
    Args:
        seconds: 秒数
    
    Returns:
        格式化后的时间字符串
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes:.0f}m {remaining_seconds:.0f}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours:.0f}h {remaining_minutes:.0f}m"