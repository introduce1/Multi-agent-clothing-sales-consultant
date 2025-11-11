# -*- coding: utf-8 -*-
"""
日志工具类
提供统一的日志记录功能
"""
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# 北京时区
beijing_tz = timezone(timedelta(hours=8))


class BeijingFormatter(logging.Formatter):
    """北京时间格式化器"""
    
    def formatTime(self, record, datefmt=None):
        """格式化时间为北京时间"""
        dt = datetime.fromtimestamp(record.created, tz=beijing_tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True
) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径
        console_output: 是否输出到控制台
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 创建格式化器
    formatter = BeijingFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        日志记录器
    """
    return logging.getLogger(name)


# 默认日志配置
DEFAULT_LOG_CONFIG = {
    "level": "INFO",
    "console_output": True,
    "log_file": "logs/customer_service.log"
}

# 创建默认日志记录器
default_logger = setup_logger(
    name="customer_service",
    **DEFAULT_LOG_CONFIG
)


class LoggerMixin:
    """日志记录器混入类"""
    
    @property
    def logger(self) -> logging.Logger:
        """获取当前类的日志记录器"""
        return get_logger(self.__class__.__module__ + "." + self.__class__.__name__)


def log_function_call(func):
    """
    函数调用日志装饰器
    
    Args:
        func: 被装饰的函数
    
    Returns:
        装饰后的函数
    """
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"调用函数 {func.__name__}, 参数: args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行失败: {e}")
            raise
    
    return wrapper


def log_performance(func):
    """
    性能日志装饰器
    
    Args:
        func: 被装饰的函数
    
    Returns:
        装饰后的函数
    """
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = datetime.now(beijing_tz)
        
        try:
            result = func(*args, **kwargs)
            end_time = datetime.now(beijing_tz)
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"函数 {func.__name__} 执行时间: {duration:.3f}秒")
            return result
        except Exception as e:
            end_time = datetime.now(beijing_tz)
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"函数 {func.__name__} 执行失败 (耗时 {duration:.3f}秒): {e}")
            raise
    
    return wrapper


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def log_event(self, event_type: str, **kwargs):
        """记录结构化事件"""
        event_data = {
            "event_type": event_type,
            "timestamp": datetime.now(beijing_tz).isoformat(),
            **kwargs
        }
        
        self.logger.info(f"EVENT: {event_data}")
    
    def log_request(self, request_id: str, method: str, path: str, **kwargs):
        """记录请求日志"""
        self.log_event(
            "request",
            request_id=request_id,
            method=method,
            path=path,
            **kwargs
        )
    
    def log_response(self, request_id: str, status_code: int, duration: float, **kwargs):
        """记录响应日志"""
        self.log_event(
            "response",
            request_id=request_id,
            status_code=status_code,
            duration=duration,
            **kwargs
        )
    
    def log_agent_action(self, agent_id: str, action: str, **kwargs):
        """记录智能体动作日志"""
        self.log_event(
            "agent_action",
            agent_id=agent_id,
            action=action,
            **kwargs
        )
    
    def log_error(self, error_type: str, error_message: str, **kwargs):
        """记录错误日志"""
        self.log_event(
            "error",
            error_type=error_type,
            error_message=error_message,
            **kwargs
        )


# 创建全局结构化日志记录器
structured_logger = StructuredLogger("customer_service.structured")