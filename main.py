"""
智能客服系统主应用入口文件
"""

# 设置编码环境
import os
import sys
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    # Windows 系统设置控制台编码
    os.system('chcp 65001 > nul')

import asyncio
import uvicorn
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
import time
import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi.encoders import jsonable_encoder

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from utils.logger import get_logger, setup_logger
from models.database import DatabaseManager, init_db
from services.chat_service import get_chat_service

# 设置日志
setup_logger("customer_service", settings.LOG_LEVEL, settings.LOG_FILE)
logger = get_logger(__name__)

beijing_tz = timezone(timedelta(hours=8))

# 数据库管理器
db_manager = DatabaseManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 启动小衣助手系统...")
    
    try:
        # 初始化数据库
        logger.info("📊 初始化数据库...")
        init_db()
        
        # 检查数据库连接
        if db_manager.health_check():
            logger.info("✅ 数据库连接正常")
        else:
            logger.error("❌ 数据库连接失败")
            raise Exception("数据库连接失败")
        
        # 初始化智能体
        logger.info("🤖 初始化智能体...")
        
        # 延迟导入避免循环导入
        from agents.agent_dispatcher import AgentDispatcher
        
        # 创建全局智能体调度器实例
        app.state.dispatcher = AgentDispatcher()
        
        logger.info("✅ 智能体调度器初始化完成")
        
        logger.info("✅ 系统启动完成")
        
    except Exception as e:
        logger.error(f"❌ 系统启动失败: {e}")
        raise
    
    yield
    
    # 关闭时执行
    logger.info("🔄 正在关闭系统...")
    
    try:
        # 关闭数据库连接
        db_manager.close()
        logger.info("✅ 数据库连接已关闭")
        
        # 清理智能体资源
        logger.info("🧹 清理智能体资源...")
        if hasattr(app.state, 'dispatcher'):
            # 清理调度器资源
            app.state.dispatcher = None
        if hasattr(app.state, 'conversation_manager'):
            # 清理对话管理器资源
            app.state.conversation_manager = None
        if hasattr(app.state, 'intent_recognizer'):
            # 清理意图识别器资源
            app.state.intent_recognizer = None
        if hasattr(app.state, 'knowledge_retriever'):
            # 清理知识检索器资源
            app.state.knowledge_retriever = None
        logger.info("✅ 智能体资源清理完成")
        
        logger.info("✅ 系统已安全关闭")
        
    except Exception as e:
        logger.error(f"❌ 系统关闭时出错: {e}")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description="基于多智能体架构的智能服装销售顾问系统",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# 自定义JSON响应类以支持中文字符
from fastapi.responses import JSONResponse
import json

class UnicodeJSONResponse(JSONResponse):
    def __init__(self, content, **kwargs):
        super().__init__(content, **kwargs)
        self.headers["content-type"] = "application/json; charset=utf-8"
    
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")

# 设置默认响应类
app.default_response_class = UnicodeJSONResponse

# 添加中间件
# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# 会话中间件
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=1800,  # 30分钟
    same_site="lax",
    https_only=not settings.DEBUG
)

# 压缩中间件
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 受信任主机中间件
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # 在生产环境中应该配置具体的域名
    )
# 请求处理中间件
@app.middleware("http")
async def process_request(request: Request, call_next):
    """请求处理中间件"""
    start_time = time.time()
    
    # 记录请求信息
    logger.info(
        f"📥 {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", "")
        }
    )
    
    try:
        # 处理请求
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 记录响应信息
        logger.info(
            f"📤 {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": process_time
            }
        )
        
        # 添加响应头
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Server-Version"] = settings.APP_VERSION
        
        return response
        
    except Exception as e:
        # 记录错误
        process_time = time.time() - start_time
        logger.error(
            f"❌ {request.method} {request.url.path} - Error: {str(e)} ({process_time:.3f}s)",
            extra={
                "method": request.method,
                "path": request.url.path,
                "error": str(e),
                "process_time": process_time
            }
        )
        
        # 返回错误响应
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "服务器内部错误，请稍后重试",
                "timestamp": time.time()
            }
        )


# 全局异常处理器
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.warning(
        f"⚠️ HTTP异常: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    logger.error(
        f"❌ 未处理的异常: {str(exc)}",
        extra={
            "error": str(exc),
            "path": request.url.path,
            "exception_type": type(exc).__name__
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "服务器内部错误，请稍后重试",
            "timestamp": time.time()
        }
    )


# 导入路由模块
from api.routers import chat, agents, analytics, health, users, sessions, knowledge

app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(agents.router, prefix="/api/agents", tags=["智能体"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["分析统计"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["会话管理"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])

# WebSocket路由 - 直接在根路径注册
# WebSocket连接管理器
class WSConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: dict = {}
        self.session_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str, session_id: str = None):
        """接受WebSocket连接"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        if session_id:
            self.session_connections[session_id] = connection_id
        logger.info(f"WebSocket连接已建立: {connection_id}")
    
    def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        for session_id, conn_id in list(self.session_connections.items()):
            if conn_id == connection_id:
                del self.session_connections[session_id]
                break
        logger.info(f"WebSocket连接已断开: {connection_id}")

ws_manager = WSConnectionManager()

async def safe_websocket_send(websocket: WebSocket, message: dict):
    """安全发送WebSocket消息，检查连接状态"""
    try:
        # 检查WebSocket连接状态
        if websocket.client_state.value == 1:  # WebSocketState.CONNECTED
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
            return True
        else:
            logger.warning(f"WebSocket连接已关闭，无法发送消息: {message.get('type', 'unknown')}")
            return False
    except Exception as e:
        logger.error(f"WebSocket发送消息失败: {e}")
        return False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = None):
    """WebSocket端点"""
    connection_id = str(uuid.uuid4())
    
    try:
        await ws_manager.connect(websocket, connection_id, session_id)
        
        # 发送连接成功消息
        await safe_websocket_send(websocket, {
            "type": "connection",
            "status": "connected",
            "connection_id": connection_id,
            "session_id": session_id,
            "timestamp": datetime.now(beijing_tz).isoformat()
        })
        
        # AI主动介绍自己的角色 - 不指定具体智能体，避免影响后续路由
        await safe_websocket_send(websocket, {
            "type": "welcome",
            "message": "您好！我是小衣助手，很高兴为您服务！🤖\n\n我可以帮助您：\n• 服装搭配和尺码建议\n• 产品咨询和面料介绍\n• 订单查询和物流跟踪\n• 穿搭建议和风格推荐\n\n请问有什么可以帮助您的吗？",
            "session_id": session_id,
            "timestamp": datetime.now(beijing_tz).isoformat()
        })
        
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "message")
                
                if message_type == "ping":
                    # 心跳检测
                    await safe_websocket_send(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now(beijing_tz).isoformat()
                    })
                
                elif message_type == "message":
                    # 处理聊天消息
                    user_message = message_data.get("message", "")
                    current_session_id = message_data.get("session_id", session_id)
                    
                    if user_message:
                        # 发送消息接收确认
                        await safe_websocket_send(websocket, {
                            "type": "message_received",
                            "message": user_message,
                            "session_id": current_session_id,
                            "timestamp": datetime.now(beijing_tz).isoformat()
                        })
                        
                        # 调用AI客服服务处理消息
                        try:
                            chat_service = get_chat_service()
                            db = db_manager.get_session()
                            
                            try:
                                # 处理消息并获取AI响应
                                result = await chat_service.process_message(
                                    message_content=user_message,
                                    session_id=current_session_id,
                                    customer_id=1,  # 使用默认WebSocket客户的ID
                                    message_type="text",
                                    priority="normal",
                                    context={
                                        "channel": "websocket",
                                        "connection_id": connection_id
                                    },
                                    db=db
                                )
                            finally:
                                # 确保数据库连接被正确关闭
                                db.close()
                            
                            if result.get("success"):
                                # 发送AI客服响应
                                await safe_websocket_send(websocket, {
                                    "type": "bot_response",
                                    "message": result.get("response", "抱歉，我暂时无法处理您的请求。"),
                                    "session_id": result.get("session_id", current_session_id),
                                    "agent_id": result.get("agent_id"),
                                    "current_agent": result.get("agent_id"),  # 添加当前智能体信息
                                    "confidence": result.get("confidence", 0.0),
                                    "intent_type": result.get("intent_type"),
                                    "requires_human": result.get("requires_human", False),
                                    "timestamp": datetime.now(beijing_tz).isoformat()
                                })
                            else:
                                # 处理失败时的回退响应
                                await safe_websocket_send(websocket, {
                                    "type": "bot_response",
                                    "message": "抱歉，系统暂时繁忙，请稍后再试。",
                                    "session_id": current_session_id,
                                    "current_agent": "reception",  # 默认智能体
                                    "error": result.get("error"),
                                    "timestamp": datetime.now(beijing_tz).isoformat()
                                })
                                
                        except Exception as ai_error:
                            logger.error(f"AI客服处理错误: {ai_error}")
                            # 发送错误回退响应
                            await safe_websocket_send(websocket, {
                                "type": "bot_response",
                                "message": "抱歉，小衣助手暂时不可用，请稍后再试。",
                                "session_id": current_session_id,
                                "current_agent": "reception",  # 默认智能体
                                "error": "ai_service_error",
                                "timestamp": datetime.now(beijing_tz).isoformat()
                            })
                
            except json.JSONDecodeError:
                # 发送格式错误消息
                await safe_websocket_send(websocket, {
                    "type": "error",
                    "message": "消息格式错误",
                    "timestamp": datetime.now(beijing_tz).isoformat()
                })
            
            except Exception as e:
                logger.error(f"WebSocket消息处理错误: {e}")
                logger.error(f"错误详情: {traceback.format_exc()}")
                # 发送处理错误消息
                await safe_websocket_send(websocket, {
                    "type": "error",
                    "message": "消息处理失败",
                    "timestamp": datetime.now(beijing_tz).isoformat()
                })
    
    except WebSocketDisconnect:
        ws_manager.disconnect(connection_id)
        logger.info(f"WebSocket客户端断开连接: {connection_id}")
    
    except Exception as e:
        logger.error(f"WebSocket连接错误: {e}")
        ws_manager.disconnect(connection_id)

# 静态文件服务
if settings.DEBUG:
    # 开发环境下提供静态文件服务
    static_dir = project_root / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# 根路径
@app.get("/", tags=["根路径"])
async def root():
    """根路径"""
    return {
        "message": "欢迎使用小衣助手",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/api/health",
        "timestamp": time.time()
    }


# 系统信息
@app.get("/info", tags=["系统信息"])
async def system_info():
    """获取系统信息"""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "python_version": sys.version,
        "timestamp": time.time()
    }


def create_app() -> FastAPI:
    """创建应用实例"""
    return app


if __name__ == "__main__":
    # 直接运行时的配置
    logger.info(f"🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🌍 环境: {'development' if settings.DEBUG else 'production'}")
    logger.info(f"🐛 调试模式: {settings.DEBUG}")
    
    # 运行服务器
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        server_header=False,
        date_header=False,
        workers=1 if settings.DEBUG else 4
    )