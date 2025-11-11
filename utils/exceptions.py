"""
异常处理工具类
定义自定义异常和错误处理
"""
import traceback
from typing import Any, Dict, Optional, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ErrorCode(Enum):
    """错误代码枚举"""
    # 通用错误 (1000-1999)
    UNKNOWN_ERROR = (1000, "未知错误")
    INVALID_PARAMETER = (1001, "参数无效")
    MISSING_PARAMETER = (1002, "缺少必需参数")
    VALIDATION_ERROR = (1003, "数据验证失败")
    PERMISSION_DENIED = (1004, "权限不足")
    RESOURCE_NOT_FOUND = (1005, "资源不存在")
    RESOURCE_ALREADY_EXISTS = (1006, "资源已存在")
    OPERATION_FAILED = (1007, "操作失败")
    
    # 认证错误 (2000-2999)
    AUTHENTICATION_FAILED = (2000, "认证失败")
    TOKEN_INVALID = (2001, "令牌无效")
    TOKEN_EXPIRED = (2002, "令牌已过期")
    LOGIN_REQUIRED = (2003, "需要登录")
    PASSWORD_INCORRECT = (2004, "密码错误")
    ACCOUNT_LOCKED = (2005, "账户已锁定")
    ACCOUNT_DISABLED = (2006, "账户已禁用")
    
    # 业务错误 (3000-3999)
    CUSTOMER_NOT_FOUND = (3000, "客户不存在")
    SESSION_NOT_FOUND = (3001, "会话不存在")
    SESSION_EXPIRED = (3002, "会话已过期")
    AGENT_NOT_AVAILABLE = (3003, "智能体不可用")
    AGENT_BUSY = (3004, "智能体忙碌")
    KNOWLEDGE_BASE_ERROR = (3005, "知识库错误")
    ORDER_NOT_FOUND = (3006, "订单不存在")
    ORDER_STATUS_INVALID = (3007, "订单状态无效")
    
    # 系统错误 (4000-4999)
    DATABASE_ERROR = (4000, "数据库错误")
    CACHE_ERROR = (4001, "缓存错误")
    NETWORK_ERROR = (4002, "网络错误")
    SERVICE_UNAVAILABLE = (4003, "服务不可用")
    RATE_LIMIT_EXCEEDED = (4004, "请求频率超限")
    TIMEOUT_ERROR = (4005, "请求超时")
    CONFIGURATION_ERROR = (4006, "配置错误")
    
    # 外部服务错误 (5000-5999)
    THIRD_PARTY_API_ERROR = (5000, "第三方API错误")
    AI_SERVICE_ERROR = (5001, "AI服务错误")
    PAYMENT_SERVICE_ERROR = (5002, "支付服务错误")
    SMS_SERVICE_ERROR = (5003, "短信服务错误")
    EMAIL_SERVICE_ERROR = (5004, "邮件服务错误")
    
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

class BaseCustomException(Exception):
    """自定义异常基类"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.error_code = error_code
        self.message = message or error_code.message
        self.details = details or {}
        self.cause = cause
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "error_code": self.error_code.code,
            "error_type": self.error_code.name,
            "message": self.message,
            "details": self.details
        }
        
        if self.cause:
            result["cause"] = str(self.cause)
        
        return result
    
    def __str__(self) -> str:
        return f"[{self.error_code.code}] {self.message}"

class ValidationException(BaseCustomException):
    """数据验证异常"""
    
    def __init__(
        self,
        message: str = "数据验证失败",
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details)

class AuthenticationException(BaseCustomException):
    """认证异常"""
    
    def __init__(
        self,
        error_code: ErrorCode = ErrorCode.AUTHENTICATION_FAILED,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(error_code, message, details)

class BusinessException(BaseCustomException):
    """业务异常"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(error_code, message, details)

class SystemException(BaseCustomException):
    """系统异常"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(error_code, message, details, cause)

class ExternalServiceException(BaseCustomException):
    """外部服务异常"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        service_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        if details is None:
            details = {}
        details["service_name"] = service_name
        
        super().__init__(error_code, message, details, cause)

class RateLimitException(BaseCustomException):
    """速率限制异常"""
    
    def __init__(
        self,
        limit: int,
        window: int,
        retry_after: Optional[int] = None,
        message: Optional[str] = None
    ):
        details = {
            "limit": limit,
            "window": window
        }
        
        if retry_after:
            details["retry_after"] = retry_after
        
        if message is None:
            message = f"请求频率超限，限制: {limit}次/{window}秒"
        
        super().__init__(ErrorCode.RATE_LIMIT_EXCEEDED, message, details)

class TimeoutException(BaseCustomException):
    """超时异常"""
    
    def __init__(
        self,
        timeout: float,
        operation: Optional[str] = None,
        message: Optional[str] = None
    ):
        details = {"timeout": timeout}
        
        if operation:
            details["operation"] = operation
        
        if message is None:
            message = f"操作超时: {timeout}秒"
            if operation:
                message = f"{operation}超时: {timeout}秒"
        
        super().__init__(ErrorCode.TIMEOUT_ERROR, message, details)

class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def handle_exception(
        exc: Exception,
        context: Optional[Dict[str, Any]] = None,
        log_error: bool = True
    ) -> Dict[str, Any]:
        """处理异常"""
        if isinstance(exc, BaseCustomException):
            error_info = exc.to_dict()
        else:
            # 处理标准异常
            error_info = {
                "error_code": ErrorCode.UNKNOWN_ERROR.code,
                "error_type": ErrorCode.UNKNOWN_ERROR.name,
                "message": str(exc),
                "details": {"exception_type": type(exc).__name__}
            }
        
        # 添加上下文信息
        if context:
            error_info["context"] = context
        
        # 记录错误日志
        if log_error:
            ErrorHandler._log_error(exc, error_info, context)
        
        return error_info
    
    @staticmethod
    def _log_error(
        exc: Exception,
        error_info: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ):
        """记录错误日志"""
        log_data = {
            "error_code": error_info.get("error_code"),
            "error_type": error_info.get("error_type"),
            "message": error_info.get("message"),
            "details": error_info.get("details", {}),
            "traceback": traceback.format_exc()
        }
        
        if context:
            log_data["context"] = context
        
        # 根据错误类型选择日志级别
        if isinstance(exc, (ValidationException, AuthenticationException)):
            logger.warning(f"业务异常: {log_data}")
        elif isinstance(exc, (SystemException, ExternalServiceException)):
            logger.error(f"系统异常: {log_data}")
        else:
            logger.error(f"未知异常: {log_data}")
    
    @staticmethod
    def create_error_response(
        exc: Exception,
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建错误响应"""
        error_info = ErrorHandler.handle_exception(exc, context)
        
        return {
            "success": False,
            "error": error_info,
            "status_code": status_code,
            "timestamp": None  # 将在API层添加时间戳
        }

# 异常处理装饰器
def handle_exceptions(
    default_error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    log_errors: bool = True,
    reraise: bool = False
):
    """异常处理装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseCustomException:
                # 自定义异常直接重新抛出
                if reraise:
                    raise
                return None
            except Exception as e:
                # 标准异常转换为自定义异常
                if log_errors:
                    logger.exception(f"函数 {func.__name__} 发生异常")
                
                custom_exc = BaseCustomException(
                    error_code=default_error_code,
                    message=f"{func.__name__} 执行失败: {str(e)}",
                    cause=e
                )
                
                if reraise:
                    raise custom_exc
                return None
        
        return wrapper
    return decorator

def safe_execute(
    func,
    *args,
    default_value=None,
    error_code: ErrorCode = ErrorCode.OPERATION_FAILED,
    log_errors: bool = True,
    **kwargs
):
    """安全执行函数"""
    try:
        return func(*args, **kwargs)
    except BaseCustomException:
        if log_errors:
            logger.exception(f"执行函数 {func.__name__} 时发生自定义异常")
        raise
    except Exception as e:
        if log_errors:
            logger.exception(f"执行函数 {func.__name__} 时发生异常")
        
        raise BaseCustomException(
            error_code=error_code,
            message=f"执行 {func.__name__} 失败: {str(e)}",
            cause=e
        )

# 常用异常快捷创建函数
def validation_error(message: str, field: Optional[str] = None, value: Optional[Any] = None):
    """创建验证错误"""
    return ValidationException(message, field, value)

def not_found_error(resource: str, identifier: Optional[str] = None):
    """创建资源不存在错误"""
    message = f"{resource}不存在"
    if identifier:
        message += f": {identifier}"
    
    return BusinessException(
        ErrorCode.RESOURCE_NOT_FOUND,
        message,
        {"resource": resource, "identifier": identifier}
    )

def permission_denied_error(action: str, resource: Optional[str] = None):
    """创建权限不足错误"""
    message = f"无权限执行操作: {action}"
    if resource:
        message += f" (资源: {resource})"
    
    return BaseCustomException(
        ErrorCode.PERMISSION_DENIED,
        message,
        {"action": action, "resource": resource}
    )

def rate_limit_error(limit: int, window: int, retry_after: Optional[int] = None):
    """创建速率限制错误"""
    return RateLimitException(limit, window, retry_after)

def timeout_error(timeout: float, operation: Optional[str] = None):
    """创建超时错误"""
    return TimeoutException(timeout, operation)

def database_error(message: str, cause: Optional[Exception] = None):
    """创建数据库错误"""
    return SystemException(ErrorCode.DATABASE_ERROR, message, cause=cause)

def cache_error(message: str, cause: Optional[Exception] = None):
    """创建缓存错误"""
    return SystemException(ErrorCode.CACHE_ERROR, message, cause=cause)

def external_service_error(service_name: str, message: str, cause: Optional[Exception] = None):
    """创建外部服务错误"""
    return ExternalServiceException(
        ErrorCode.THIRD_PARTY_API_ERROR,
        service_name,
        message,
        cause=cause
    )