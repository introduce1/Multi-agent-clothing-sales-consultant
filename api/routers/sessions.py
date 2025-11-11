# -*- coding: utf-8 -*-
"""
会话管理API路由
提供会话创建、管理、历史记录等功能
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from pydantic import BaseModel, Field

from agents.base_agent import Message, MessageType, Priority
# 移除已删除的ConversationManager导入
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
beijing_tz = timezone(timedelta(hours=8))


class SessionCreate(BaseModel):
    """会话创建模型"""
    customer_id: str = Field(..., description="客户ID")
    initial_message: Optional[str] = Field(None, description="初始消息")
    context: Optional[Dict[str, Any]] = Field(None, description="初始上下文")
    priority: str = Field("normal", description="会话优先级")


class SessionInfo(BaseModel):
    """会话信息模型"""
    session_id: str
    customer_id: str
    state: str
    current_agent: Optional[str] = None
    agent_history: List[str] = []
    escalation_level: str = "none"
    created_at: str
    updated_at: str
    last_activity: str
    is_active: bool = True
    message_count: int = 0
    context: Dict[str, Any] = {}
    summary: Optional[str] = None


class SessionMessage(BaseModel):
    """会话消息模型"""
    message_id: str
    session_id: str
    sender_type: str  # "user", "agent", "system"
    sender_id: Optional[str] = None
    content: str
    message_type: str = "text"
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class MessageCreate(BaseModel):
    """消息创建模型"""
    message_content: str = Field(..., description="消息内容")
    sender_type: str = Field(..., description="发送者类型")
    sender_id: Optional[str] = Field(None, description="发送者ID")
    message_type: str = Field("text", description="消息类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="消息元数据")


class SessionUpdate(BaseModel):
    """会话更新模型"""
    state: Optional[str] = Field(None, description="会话状态")
    current_agent: Optional[str] = Field(None, description="当前智能体")
    escalation_level: Optional[str] = Field(None, description="升级级别")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文更新")


class SessionEnd(BaseModel):
    """会话结束模型"""
    reason: Optional[str] = Field(None, description="结束原因")


class SessionHistory(BaseModel):
    """会话历史模型"""
    session_id: str
    messages: List[SessionMessage]
    total_count: int
    page: int
    page_size: int


class SessionListResponse(BaseModel):
    """会话列表响应模型"""
    success: bool
    sessions: List[SessionInfo]
    total_count: int
    active_count: int
    page: int
    page_size: int


class SessionResponse(BaseModel):
    """会话响应模型"""
    success: bool
    session: SessionInfo


class SessionStatsResponse(BaseModel):
    """会话统计响应模型"""
    success: bool
    stats: Dict[str, Any]


# 模拟会话数据库
sessions_db = {}
messages_db = {}


# ConversationManager已删除，使用简化的会话管理


def get_orchestrator(request: Request):
    """获取智能体编排器"""
    orchestrator = getattr(request.app.state, 'orchestrator', None)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="智能体编排器未初始化")
    return orchestrator


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    request: Request
):
    """创建新会话"""
    try:
        session_id = str(uuid.uuid4())
        
        # 初始化会话上下文
        context = session_data.context or {}
        
        # 创建会话记录
        session_info = {
            "session_id": session_id,
            "customer_id": session_data.customer_id,
            "state": "active",
            "current_agent": None,
            "agent_history": [],
            "escalation_level": "none",
            "created_at": datetime.now(beijing_tz).isoformat(),
            "updated_at": datetime.now(beijing_tz).isoformat(),
            "last_activity": datetime.now(beijing_tz).isoformat(),
            "is_active": True,
            "message_count": 0,
            "context": context,
            "summary": None
        }
        
        sessions_db[session_id] = session_info
        messages_db[session_id] = []
        
        # 如果有初始消息，添加到会话中
        if session_data.initial_message:
            message_id = str(uuid.uuid4())
            message = {
                "message_id": message_id,
                "session_id": session_id,
                "sender_type": "user",
                "sender_id": session_data.customer_id,
                "content": session_data.initial_message,
                "message_type": "text",
                "timestamp": datetime.now(beijing_tz).isoformat(),
                "metadata": {}
            }
            
            messages_db[session_id].append(message)
            session_info["message_count"] = 1
            session_info["last_activity"] = message["timestamp"]
        
        logger.info(f"会话创建成功: {session_id}")
        
        return SessionResponse(
            success=True,
            session=SessionInfo(**session_info)
        )
        
    except Exception as e:
        logger.error(f"会话创建失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="会话创建失败"
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """获取会话信息"""
    if session_id not in sessions_db:
        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )
    
    session_info = sessions_db[session_id]
    return SessionResponse(
        success=True,
        session=SessionInfo(**session_info)
    )


@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions(
    customer_id: Optional[str] = Query(None, description="客户ID过滤"),
    state: Optional[str] = Query(None, description="会话状态过滤"),
    active_only: bool = Query(True, description="仅显示活跃会话"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小")
):
    """获取会话列表"""
    try:
        # 过滤会话
        filtered_sessions = []
        active_count = 0
        
        for session_info in sessions_db.values():
            # 应用过滤条件
            if customer_id and session_info["customer_id"] != customer_id:
                continue
            if state and session_info["state"] != state:
                continue
            if active_only and not session_info["is_active"]:
                continue
            
            filtered_sessions.append(SessionInfo(**session_info))
            if session_info["is_active"]:
                active_count += 1
        
        # 按最后活动时间排序
        filtered_sessions.sort(key=lambda x: x.last_activity, reverse=True)
        
        # 分页
        total_count = len(filtered_sessions)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_sessions = filtered_sessions[start_idx:end_idx]
        
        return SessionListResponse(
            success=True,
            sessions=paginated_sessions,
            total_count=total_count,
            active_count=active_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取会话列表失败"
        )


@router.get("/sessions/{session_id}/messages", response_model=SessionHistory)
async def get_session_messages(
    session_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页大小")
):
    """获取会话消息历史"""
    if session_id not in sessions_db:
        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )
    
    try:
        messages = messages_db.get(session_id, [])
        
        # 分页
        total_count = len(messages)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_messages = messages[start_idx:end_idx]
        
        # 转换为SessionMessage对象
        session_messages = [SessionMessage(**msg) for msg in paginated_messages]
        
        return SessionHistory(
            session_id=session_id,
            messages=session_messages,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"获取会话消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取会话消息失败"
        )


@router.post("/sessions/{session_id}/messages")
async def add_session_message(
    session_id: str,
    message_data: MessageCreate,
    request: Request
):
    """添加会话消息"""
    if session_id not in sessions_db:
        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )
    
    try:
        message_id = str(uuid.uuid4())
        timestamp = datetime.now(beijing_tz).isoformat()
        
        # 创建消息记录
        message = {
            "message_id": message_id,
            "session_id": session_id,
            "sender_type": message_data.sender_type,
            "sender_id": message_data.sender_id,
            "content": message_data.message_content,
            "message_type": message_data.message_type,
            "timestamp": timestamp,
            "metadata": message_data.metadata or {}
        }
        
        # 添加到消息数据库
        if session_id not in messages_db:
            messages_db[session_id] = []
        messages_db[session_id].append(message)
        
        # 更新会话信息
        session_info = sessions_db[session_id]
        session_info["message_count"] += 1
        session_info["last_activity"] = timestamp
        session_info["updated_at"] = timestamp
        
        # 记录用户消息（简化处理）
        if message_data.sender_type == "user":
            # 可以在这里添加消息处理逻辑
            pass
        
        logger.info(f"会话消息添加成功: {session_id} - {message_id}")
        
        return {
            "success": True,
            "message_id": message_id,
            "timestamp": timestamp
        }
        
    except Exception as e:
        logger.error(f"添加会话消息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="添加会话消息失败"
        )


@router.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    update_data: SessionUpdate,
    request: Request
):
    """更新会话信息"""
    if session_id not in sessions_db:
        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )
    
    try:
        session_info = sessions_db[session_id]
        
        # 更新字段
        if update_data.state is not None:
            session_info["state"] = update_data.state
            if update_data.state == "ended":
                session_info["is_active"] = False
        
        if update_data.current_agent is not None:
            if update_data.current_agent != session_info["current_agent"]:
                # 记录智能体切换历史
                if session_info["current_agent"]:
                    session_info["agent_history"].append(session_info["current_agent"])
                session_info["current_agent"] = update_data.current_agent
        
        if update_data.escalation_level is not None:
            session_info["escalation_level"] = update_data.escalation_level
        
        if update_data.context is not None:
            session_info["context"].update(update_data.context)
            # 上下文已更新到会话信息中
        
        session_info["updated_at"] = datetime.now(beijing_tz).isoformat()
        
        logger.info(f"会话更新成功: {session_id}")
        
        return SessionResponse(
            success=True,
            session=SessionInfo(**session_info)
        )
        
    except Exception as e:
        logger.error(f"会话更新失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="会话更新失败"
        )


@router.delete("/sessions/{session_id}")
async def end_session(
    session_id: str,
    end_data: SessionEnd,
    request: Request
):
    """结束会话"""
    if session_id not in sessions_db:
        raise HTTPException(
            status_code=404,
            detail="会话不存在"
        )
    
    try:
        session_info = sessions_db[session_id]
        
        # 生成简单的会话摘要
        messages = messages_db.get(session_id, [])
        summary_text = f"会话包含 {len(messages)} 条消息" if messages else "空会话"
        
        # 更新会话状态
        session_info["state"] = "ended"
        session_info["is_active"] = False
        session_info["summary"] = summary_text
        session_info["updated_at"] = datetime.now(beijing_tz).isoformat()
        
        logger.info(f"会话结束: {session_id}")
        
        return {
            "success": True,
            "message": "会话已结束",
            "summary": summary_text
        }
        
    except Exception as e:
        logger.error(f"结束会话失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="结束会话失败"
        )


@router.get("/sessions/stats", response_model=SessionStatsResponse)
async def get_session_stats(
    period: str = Query("24h", description="统计周期: 1h, 24h, 7d, 30d")
):
    """获取会话统计信息"""
    try:
        # 解析时间周期
        hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(period, 24)
        cutoff_time = datetime.now(beijing_tz) - timedelta(hours=hours)
        
        # 统计数据
        total_sessions = len(sessions_db)
        active_sessions = sum(1 for s in sessions_db.values() if s["is_active"])
        recent_sessions = sum(
            1 for s in sessions_db.values() 
            if datetime.fromisoformat(s["created_at"]) > cutoff_time
        )
        
        # 按状态统计
        state_stats = {}
        for session in sessions_db.values():
            state = session["state"]
            state_stats[state] = state_stats.get(state, 0) + 1
        
        # 按升级级别统计
        escalation_stats = {}
        for session in sessions_db.values():
            level = session["escalation_level"]
            escalation_stats[level] = escalation_stats.get(level, 0) + 1
        
        # 平均消息数
        avg_messages = (
            sum(s["message_count"] for s in sessions_db.values()) / total_sessions
            if total_sessions > 0 else 0
        )
        
        stats = {
            "period": period,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "recent_sessions": recent_sessions,
            "state_distribution": state_stats,
            "escalation_distribution": escalation_stats,
            "average_messages_per_session": round(avg_messages, 2),
            "total_messages": sum(len(messages) for messages in messages_db.values())
        }
        
        return SessionStatsResponse(
            success=True,
            stats=stats
        )
        
    except Exception as e:
        logger.error(f"获取会话统计失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取会话统计失败"
        )