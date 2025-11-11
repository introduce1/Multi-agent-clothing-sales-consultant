# -*- coding: utf-8 -*-
"""
对话服务API路由
提供客户与智能体的交互接口
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import json

from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# 自定义JSON响应类以支持中文字符
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

from models.session import MessageType
from agents.base_agent import Priority, Message
from utils.dependencies import get_dispatcher, get_orchestrator
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
beijing_tz = timezone(timedelta(hours=8))


class ChatRequest(BaseModel):
    """对话请求模型"""
    message: str = Field(..., description="用户消息内容", min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="会话ID，如果不提供将自动生成")
    customer_id: Optional[str] = Field(None, description="客户ID")
    message_type: str = Field("text", description="消息类型")
    priority: str = Field("normal", description="消息优先级")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class ChatResponse(BaseModel):
    """对话响应模型"""
    success: bool
    message_id: str
    session_id: str
    response: str
    confidence: float
    agent_id: Optional[str] = None
    intent_type: Optional[str] = None
    requires_human: bool = False
    escalation_reason: Optional[str] = None
    next_action: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str


class SessionInfo(BaseModel):
    """会话信息模型"""
    session_id: str
    customer_id: str
    current_agent: Optional[str] = None
    agent_history: List[str] = []
    escalation_level: str = "none"
    created_at: str
    last_activity: str
    is_active: bool = True
    message_count: int = 0


class SessionListResponse(BaseModel):
    """会话列表响应模型"""
    success: bool
    sessions: List[SessionInfo]
    total_count: int
    active_count: int


def get_orchestrator(request: Request):
    """获取智能体调度器（兼容性函数）"""
    from utils.dependencies import get_dispatcher
    return get_dispatcher(request)


def validate_message_type(message_type: str) -> MessageType:
    """验证消息类型"""
    try:
        return MessageType(message_type.lower())
    except ValueError:
        return MessageType.TEXT


def validate_priority(priority: str) -> Priority:
    """验证优先级"""
    try:
        return Priority(priority.upper())
    except ValueError:
        return Priority.NORMAL


@router.post("/", response_model=ChatResponse)
async def send_message(
    chat_request: ChatRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    orchestrator=Depends(get_orchestrator)
):
    """发送消息给智能体"""
    try:
        # 生成消息ID和会话ID
        message_id = str(uuid.uuid4())
        session_id = chat_request.session_id or str(uuid.uuid4())
        
        # 创建消息对象
        message = Message(
            content=chat_request.message,
            conversation_id=session_id,
            sender_id=chat_request.customer_id or "anonymous",
            message_type=validate_message_type(chat_request.message_type),
            priority=validate_priority(chat_request.priority),
            metadata=chat_request.context or {}
        )
        
        logger.info(f"收到消息: {message_id} - {chat_request.message[:50]}...")
        
        # 通过调度器处理消息
        response = await orchestrator.process_message(
            user_id=chat_request.customer_id or "anonymous",
            message=message
        )
        
        # 记录响应日志
        logger.info(f"消息处理完成: {message_id} - 置信度: {response.confidence}")
        
        # 构建响应数据
        response_data = {
            "success": True,
            "message_id": message_id,
            "session_id": session_id,
            "response": response.content,
            "agent_id": response.agent_id or "unknown",
            "confidence": response.confidence,
            "intent_type": response.intent_type.value if response.intent_type else None,
            "requires_human": response.requires_human,
            "escalation_reason": response.escalation_reason,
            "timestamp": datetime.now(beijing_tz).isoformat()
        }
        
        # 异步记录统计信息
        background_tasks.add_task(
            log_chat_statistics,
            message_id,
            session_id,
            chat_request.message,
            response.content,
            response.confidence
        )
        
        return UnicodeJSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"消息处理失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"消息处理失败: {str(e)}"
        )


@router.get("/chat/sessions", response_model=SessionListResponse)
async def get_sessions(
    request: Request,
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    orchestrator=Depends(get_orchestrator)
):
    """获取会话列表"""
    try:
        # 获取所有会话
        all_sessions = orchestrator.get_system_stats().get("sessions", {})
        
        # 过滤活跃会话
        if active_only:
            sessions = {k: v for k, v in all_sessions.items() if v.is_active}
        else:
            sessions = all_sessions
        
        # 转换为响应格式
        session_list = []
        for session_id, session_data in list(all_sessions.items())[offset:offset + limit]:
            session_info = SessionInfo(
                session_id=session_id,
                customer_id=session_data.get("user_id", "unknown"),
                current_agent=session_data.get("current_agent", "reception"),
                agent_history=session_data.get("agent_history", []),
                escalation_level="normal",
                created_at=session_data.get("created_at", datetime.now(beijing_tz).isoformat()),
                last_activity=session_data.get("last_activity", datetime.now(beijing_tz).isoformat()),
                is_active=session_data.get("status") == "active",
                message_count=session_data.get("message_count", 0)
            )
            session_list.append(session_info)
        
        return SessionListResponse(
            success=True,
            sessions=session_list,
            total_count=len(all_sessions),
            active_count=len([s for s in all_sessions.values() if s.is_active])
        )
        
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取会话列表失败: {str(e)}"
        )


@router.get("/chat/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    request: Request,
    orchestrator=Depends(get_orchestrator)
):
    """获取会话详情"""
    try:
        # 获取会话信息
        session_info = orchestrator.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 获取消息历史
        message_history = session_info.get("message_history", [])
        
        return {
            "success": True,
            "session": {
                "session_id": session_id,
                "customer_id": session_info.get("user_id", "unknown"),
                "current_agent": session_info.get("current_agent", "reception"),
                "agent_history": session_info.get("agent_history", []),
                "escalation_level": "normal",
                "created_at": session_info.get("created_at", datetime.now(beijing_tz).isoformat()),
                "last_activity": session_info.get("last_activity", datetime.now(beijing_tz).isoformat()),
                "is_active": session_info.get("status") == "active",
                "context": session_info.get("context", {}),
                "message_count": len(message_history)
            },
            "message_history": message_history[-50:]  # 最近50条消息
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取会话详情失败: {str(e)}"
        )


@router.delete("/chat/sessions/{session_id}")
async def close_session(
    session_id: str,
    request: Request,
    orchestrator=Depends(get_orchestrator)
):
    """关闭会话"""
    try:
        # 获取会话信息
        session_info = orchestrator.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 清理会话
        if hasattr(orchestrator, 'cleanup_session'):
            await orchestrator.cleanup_session(session_id)
        
        logger.info(f"会话已关闭: {session_id}")
        
        return {
            "success": True,
            "message": "会话已关闭",
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"关闭会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"关闭会话失败: {str(e)}"
        )


@router.post("/chat/sessions/{session_id}/escalate")
async def escalate_session(
    session_id: str,
    request: Request,
    escalation_reason: str = "用户请求人工服务",
    orchestrator=Depends(get_orchestrator)
):
    """升级会话到人工服务"""
    try:
        # 获取会话信息
        session_info = orchestrator.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 尝试转接到人工
        if hasattr(orchestrator, 'transfer_to_human'):
            result = await orchestrator.transfer_to_human(session_id, escalation_reason)
            if result:
                logger.info(f"会话已升级到人工服务: {session_id} - {escalation_reason}")
                return {
                    "success": True,
                    "message": "会话已升级到人工服务",
                    "session_id": session_id,
                    "escalation_level": "human"
                }
        
        # 如果调度器不支持转接，返回成功但标记为待处理
        logger.info(f"会话升级请求已记录: {session_id} - {escalation_reason}")
        return {
            "success": True,
            "message": "升级请求已记录，等待人工客服接入",
            "session_id": session_id,
            "escalation_level": "pending_human"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"会话升级失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"会话升级失败: {str(e)}"
        )


@router.get("/chat/stream/{session_id}")
async def chat_stream(
    session_id: str,
    request: Request,
    orchestrator=Depends(get_orchestrator)
):
    """流式对话接口（Server-Sent Events）"""
    async def event_generator():
        try:
            # 检查会话是否存在
            session_info = orchestrator.get_session_info(session_id)
            if not session_info:
                yield {
                    "event": "error",
                    "data": '{"error": "会话不存在"}'
                }
                return
            
            session = orchestrator.sessions[session_id]
            last_message_count = len(session.context.get("message_history", []))
            
            # 持续监听会话更新
            while session.is_active:
                current_message_count = len(session.context.get("message_history", []))
                
                # 检查是否有新消息
                if current_message_count > last_message_count:
                    message_history = session.context.get("message_history", [])
                    new_messages = message_history[last_message_count:]
                    
                    for message in new_messages:
                        yield {
                            "event": "message",
                            "data": f'{{"type": "new_message", "content": {message}}}'
                        }
                    
                    last_message_count = current_message_count
                
                # 检查会话状态变化
                yield {
                    "event": "status",
                    "data": f'{{"session_id": "{session_id}", "is_active": {str(session.is_active).lower()}, "current_agent": "{session.current_agent or ""}", "escalation_level": "{session.escalation_level.value}"}}'
                }
                
                # 等待一段时间再检查
                await asyncio.sleep(1)
            
            # 会话结束
            yield {
                "event": "close",
                "data": '{"message": "会话已结束"}'
            }
            
        except Exception as e:
            logger.error(f"流式对话错误: {e}")
            yield {
                "event": "error",
                "data": f'{{"error": "{str(e)}"}}'
            }
    
    return EventSourceResponse(event_generator())


@router.get("/chat/suggestions")
async def get_chat_suggestions(
    request: Request,
    query: str = "",
    limit: int = 5,
    orchestrator=Depends(get_orchestrator)
):
    """获取对话建议"""
    try:
        # 基于查询内容提供建议
        suggestions = []
        
        query_lower = query.lower()
        
        # 常见问题建议
        common_questions = [
            "你好，我想了解一下你们的产品",
            "请问有什么优惠活动吗？",
            "我的订单什么时候能到？",
            "如何申请退款？",
            "产品使用遇到问题怎么办？",
            "请问客服工作时间是什么时候？",
            "我想投诉一个问题",
            "能帮我查一下订单状态吗？"
        ]
        
        # 根据查询匹配建议
        if query:
            for question in common_questions:
                if any(word in question for word in query_lower.split()):
                    suggestions.append(question)
                    if len(suggestions) >= limit:
                        break
        else:
            suggestions = common_questions[:limit]
        
        return {
            "success": True,
            "suggestions": suggestions,
            "query": query
        }
        
    except Exception as e:
        logger.error(f"获取对话建议失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取对话建议失败: {str(e)}"
        )


async def log_chat_statistics(
    message_id: str,
    session_id: str,
    user_message: str,
    bot_response: str,
    confidence: float
):
    """记录对话统计信息（后台任务）"""
    try:
        # 这里可以记录到数据库或日志文件
        logger.info(f"对话统计 - 消息ID: {message_id}, 会话ID: {session_id}, 置信度: {confidence}")
        
        # 可以添加更多统计逻辑，如：
        # - 用户满意度分析
        # - 响应时间统计
        # - 热门问题统计
        # - 智能体性能分析
        
    except Exception as e:
        logger.error(f"记录对话统计失败: {e}")


# 导入asyncio用于流式接口
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_connections: Dict[str, str] = {}  # session_id -> connection_id
    
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
        # 清理会话连接映射
        for session_id, conn_id in list(self.session_connections.items()):
            if conn_id == connection_id:
                del self.session_connections[session_id]
                break
        logger.info(f"WebSocket连接已断开: {connection_id}")
    
    async def send_personal_message(self, message: str, connection_id: str):
        """发送个人消息"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(message)
    
    async def send_to_session(self, message: str, session_id: str):
        """发送消息到特定会话"""
        if session_id in self.session_connections:
            connection_id = self.session_connections[session_id]
            await self.send_personal_message(message, connection_id)


# 创建连接管理器实例
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = None):
    """WebSocket端点"""
    connection_id = str(uuid.uuid4())
    
    try:
        await manager.connect(websocket, connection_id, session_id)
        
        # 发送连接成功消息
        await websocket.send_text(json.dumps({
            "type": "connection",
            "status": "connected",
            "connection_id": connection_id,
            "session_id": session_id,
            "timestamp": datetime.now(beijing_tz).isoformat()
        }))
        
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "message")
                
                if message_type == "ping":
                    # 心跳检测
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now(beijing_tz).isoformat()
                    }))
                
                elif message_type == "message":
                    # 处理聊天消息
                    user_message = message_data.get("message", "")
                    current_session_id = message_data.get("session_id", session_id)
                    
                    if user_message:
                        # 发送消息接收确认
                        await websocket.send_text(json.dumps({
                            "type": "message_received",
                            "message": user_message,
                            "session_id": current_session_id,
                            "timestamp": datetime.now(beijing_tz).isoformat()
                        }))
                        
                        # 这里可以集成智能体处理逻辑
                        # 暂时返回一个简单的回复
                        bot_response = f"收到您的消息：{user_message}"
                        
                        await websocket.send_text(json.dumps({
                            "type": "bot_response",
                            "message": bot_response,
                            "session_id": current_session_id,
                            "timestamp": datetime.now(beijing_tz).isoformat()
                        }))
                
            except json.JSONDecodeError:
                # 处理非JSON消息
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "消息格式错误，请发送有效的JSON格式",
                    "timestamp": datetime.now(beijing_tz).isoformat()
                }))
            
            except Exception as e:
                logger.error(f"WebSocket消息处理错误: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "消息处理失败",
                    "timestamp": datetime.now(beijing_tz).isoformat()
                }))
    
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
        logger.info(f"WebSocket客户端断开连接: {connection_id}")
    
    except Exception as e:
        logger.error(f"WebSocket连接错误: {e}")
        manager.disconnect(connection_id)