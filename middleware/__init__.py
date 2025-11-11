"""中间件包
提供各种中间件功能
"""

# 认证中间件
from .auth import (
    AuthMiddleware,
    JWTAuthMiddleware,
    JWTManager,
    PermissionChecker,
    AuthService,
    get_current_user,
    get_current_active_user,
    require_permission,
    require_role,
    require_any_permission
)

# 速率限制中间件
from .rate_limit import (
    RateLimitMiddleware,
    RateLimiter,
    TokenBucket,
    SlidingWindowCounter,
    rate_limit
)

# 日志中间件
from .logging import (
    LoggingMiddleware,
    RequestLoggingMiddleware,
    PerformanceLoggingMiddleware,
    LogContext
)

# CORS中间件
from .cors import (
    CORSMiddleware,
    CORSConfig,
    create_cors_middleware,
    cors_enabled
)

# 错误处理中间件
from .error_handler import (
    ErrorHandlerMiddleware,
    create_error_handler_middleware,
    handle_exceptions
)

# 安全中间件
from .security import (
    SecurityMiddleware,
    CSRFProtection,
    SecurityHeaders,
    create_security_middleware
)

__all__ = [
    # 认证中间件
    "AuthMiddleware",
    "JWTAuthMiddleware", 
    "JWTManager",
    "PermissionChecker",
    "AuthService",
    "get_current_user",
    "get_current_active_user",
    "require_permission",
    "require_role",
    "require_any_permission",
    
    # 速率限制中间件
    "RateLimitMiddleware",
    "RateLimiter",
    "TokenBucket", 
    "SlidingWindowCounter",
    "rate_limit",
    
    # 日志中间件
    "LoggingMiddleware",
    "RequestLoggingMiddleware",
    "PerformanceLoggingMiddleware",
    "LogContext",
    
    # CORS中间件
    "CORSMiddleware",
    "CORSConfig",
    "create_cors_middleware",
    "cors_enabled",
    
    # 错误处理中间件
    "ErrorHandlerMiddleware",
    "create_error_handler_middleware",
    "handle_exceptions",
    
    # 安全中间件
    "SecurityMiddleware",
    "CSRFProtection",
    "SecurityHeaders",
    "create_security_middleware"
]