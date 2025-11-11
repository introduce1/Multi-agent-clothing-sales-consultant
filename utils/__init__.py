# -*- coding: utf-8 -*-
"""
工具类包
"""

# 日志相关
from .logger import (
    setup_logger, 
    get_logger, 
    structured_logger,
    LoggerMixin,
    log_function_call,
    log_performance
)

# 辅助函数
from .helpers import (
    generate_id,
    generate_short_id,
    generate_session_id,
    generate_customer_id,
    generate_order_id,
    format_datetime,
    parse_datetime,
    get_beijing_now,
    validate_email,
    validate_phone,
    validate_url,
    hash_password,
    verify_password,
    sanitize_string,
    extract_keywords,
    format_file_size,
    truncate_text,
    deep_merge_dict,
    safe_json_loads,
    safe_json_dumps,
    chunk_list,
    flatten_list,
    calculate_similarity,
    retry_async,
    rate_limit,
    Timer
)

# 缓存相关
from .cache import (
    CacheManager,
    MemoryCache,
    RedisCache,
    cached,
    init_cache,
    get_default_cache_manager,
    CacheKeyGenerator
)

# 配置管理工具已移除

# 异常处理
from .exceptions import (
    ErrorCode,
    BaseCustomException,
    ValidationException,
    AuthenticationException,
    BusinessException,
    SystemException,
    ExternalServiceException,
    RateLimitException,
    TimeoutException,
    ErrorHandler,
    handle_exceptions,
    safe_execute,
    validation_error,
    not_found_error,
    permission_denied_error,
    rate_limit_error,
    timeout_error,
    database_error,
    cache_error,
    external_service_error
)