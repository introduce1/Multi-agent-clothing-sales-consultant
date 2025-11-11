"""
CORS中间件
处理跨域请求
"""
from typing import List, Optional, Union, Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, PlainTextResponse
import logging

logger = logging.getLogger(__name__)

class CORSMiddleware(BaseHTTPMiddleware):
    """CORS中间件"""
    
    def __init__(
        self,
        app,
        allow_origins: Union[List[str], str] = None,
        allow_methods: Union[List[str], str] = None,
        allow_headers: Union[List[str], str] = None,
        allow_credentials: bool = False,
        allow_origin_regex: Optional[str] = None,
        expose_headers: Union[List[str], str] = None,
        max_age: int = 600
    ):
        super().__init__(app)
        
        # 处理允许的源
        if allow_origins is None:
            self.allow_origins = ["*"]
        elif isinstance(allow_origins, str):
            self.allow_origins = [allow_origins]
        else:
            self.allow_origins = list(allow_origins)
        
        # 处理允许的方法
        if allow_methods is None:
            self.allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"]
        elif isinstance(allow_methods, str):
            self.allow_methods = [allow_methods]
        else:
            self.allow_methods = list(allow_methods)
        
        # 处理允许的头部
        if allow_headers is None:
            self.allow_headers = [
                "Accept",
                "Accept-Language",
                "Content-Language",
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-Request-ID"
            ]
        elif isinstance(allow_headers, str):
            self.allow_headers = [allow_headers]
        else:
            self.allow_headers = list(allow_headers)
        
        # 处理暴露的头部
        if expose_headers is None:
            self.expose_headers = [
                "X-Request-ID",
                "X-Process-Time",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset"
            ]
        elif isinstance(expose_headers, str):
            self.expose_headers = [expose_headers]
        else:
            self.expose_headers = list(expose_headers)
        
        self.allow_credentials = allow_credentials
        self.allow_origin_regex = allow_origin_regex
        self.max_age = max_age
        
        # 编译正则表达式
        if self.allow_origin_regex:
            import re
            self.origin_regex = re.compile(self.allow_origin_regex)
        else:
            self.origin_regex = None
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        origin = request.headers.get("Origin")
        
        # 处理预检请求
        if request.method == "OPTIONS":
            return self._handle_preflight_request(request, origin)
        
        # 处理实际请求
        response = await call_next(request)
        
        # 添加CORS头部
        self._add_cors_headers(response, origin)
        
        return response
    
    def _handle_preflight_request(self, request: Request, origin: Optional[str]) -> Response:
        """处理预检请求"""
        # 检查源是否被允许
        if not self._is_origin_allowed(origin):
            logger.warning(f"CORS预检请求被拒绝，源: {origin}")
            return PlainTextResponse(
                "CORS预检请求被拒绝",
                status_code=400
            )
        
        # 检查请求方法是否被允许
        requested_method = request.headers.get("Access-Control-Request-Method")
        if requested_method and requested_method not in self.allow_methods:
            logger.warning(f"CORS预检请求被拒绝，方法: {requested_method}")
            return PlainTextResponse(
                f"方法 {requested_method} 不被允许",
                status_code=400
            )
        
        # 检查请求头部是否被允许
        requested_headers = request.headers.get("Access-Control-Request-Headers")
        if requested_headers:
            requested_headers_list = [h.strip() for h in requested_headers.split(",")]
            for header in requested_headers_list:
                if header.lower() not in [h.lower() for h in self.allow_headers]:
                    logger.warning(f"CORS预检请求被拒绝，头部: {header}")
                    return PlainTextResponse(
                        f"头部 {header} 不被允许",
                        status_code=400
                    )
        
        # 创建预检响应
        response = PlainTextResponse("OK", status_code=200)
        
        # 添加CORS头部
        self._add_cors_headers(response, origin, is_preflight=True)
        
        # 添加预检特定的头部
        if requested_method:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
        
        if requested_headers:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
        
        response.headers["Access-Control-Max-Age"] = str(self.max_age)
        
        logger.debug(f"CORS预检请求成功，源: {origin}")
        return response
    
    def _add_cors_headers(
        self,
        response: Response,
        origin: Optional[str],
        is_preflight: bool = False
    ):
        """添加CORS头部"""
        # 设置允许的源
        if self._is_origin_allowed(origin):
            if "*" in self.allow_origins and not self.allow_credentials:
                response.headers["Access-Control-Allow-Origin"] = "*"
            else:
                response.headers["Access-Control-Allow-Origin"] = origin or "*"
        
        # 设置是否允许凭据
        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # 设置暴露的头部
        if self.expose_headers and not is_preflight:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
        
        # 添加Vary头部以支持缓存
        vary_headers = []
        if "Origin" not in response.headers.get("Vary", ""):
            vary_headers.append("Origin")
        
        if is_preflight:
            if "Access-Control-Request-Method" not in response.headers.get("Vary", ""):
                vary_headers.append("Access-Control-Request-Method")
            if "Access-Control-Request-Headers" not in response.headers.get("Vary", ""):
                vary_headers.append("Access-Control-Request-Headers")
        
        if vary_headers:
            existing_vary = response.headers.get("Vary", "")
            if existing_vary:
                vary_headers.insert(0, existing_vary)
            response.headers["Vary"] = ", ".join(vary_headers)
    
    def _is_origin_allowed(self, origin: Optional[str]) -> bool:
        """检查源是否被允许"""
        if not origin:
            return True  # 同源请求
        
        # 检查通配符
        if "*" in self.allow_origins:
            return True
        
        # 检查精确匹配
        if origin in self.allow_origins:
            return True
        
        # 检查正则表达式匹配
        if self.origin_regex and self.origin_regex.match(origin):
            return True
        
        return False

# 预定义的CORS配置
class CORSConfig:
    """CORS配置类"""
    
    @staticmethod
    def development():
        """开发环境配置"""
        return {
            "allow_origins": ["*"],
            "allow_methods": ["*"],
            "allow_headers": ["*"],
            "allow_credentials": True,
            "max_age": 86400
        }
    
    @staticmethod
    def production(allowed_origins: List[str]):
        """生产环境配置"""
        return {
            "allow_origins": allowed_origins,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Accept",
                "Accept-Language",
                "Content-Language",
                "Content-Type",
                "Authorization",
                "X-Requested-With"
            ],
            "allow_credentials": True,
            "expose_headers": [
                "X-Request-ID",
                "X-Process-Time"
            ],
            "max_age": 3600
        }
    
    @staticmethod
    def api_only():
        """仅API配置"""
        return {
            "allow_origins": ["*"],
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-API-Key"
            ],
            "allow_credentials": False,
            "max_age": 3600
        }
    
    @staticmethod
    def strict(allowed_origins: List[str]):
        """严格配置"""
        return {
            "allow_origins": allowed_origins,
            "allow_methods": ["GET", "POST"],
            "allow_headers": [
                "Content-Type",
                "Authorization"
            ],
            "allow_credentials": True,
            "max_age": 300
        }

# 便捷函数
def create_cors_middleware(app, config_type: str = "development", **kwargs):
    """创建CORS中间件"""
    if config_type == "development":
        config = CORSConfig.development()
    elif config_type == "production":
        allowed_origins = kwargs.get("allowed_origins", ["http://localhost:3000"])
        config = CORSConfig.production(allowed_origins)
    elif config_type == "api_only":
        config = CORSConfig.api_only()
    elif config_type == "strict":
        allowed_origins = kwargs.get("allowed_origins", ["http://localhost:3000"])
        config = CORSConfig.strict(allowed_origins)
    else:
        config = kwargs
    
    # 覆盖配置
    config.update(kwargs)
    
    return CORSMiddleware(app, **config)

# 装饰器版本
def cors_enabled(
    allow_origins: Union[List[str], str] = "*",
    allow_methods: Union[List[str], str] = None,
    allow_headers: Union[List[str], str] = None,
    allow_credentials: bool = False
):
    """CORS装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 这里需要根据具体的框架实现
            # 暂时只是一个占位符
            return await func(*args, **kwargs)
        
        # 添加CORS元数据
        wrapper._cors_config = {
            "allow_origins": allow_origins,
            "allow_methods": allow_methods,
            "allow_headers": allow_headers,
            "allow_credentials": allow_credentials
        }
        
        return wrapper
    return decorator