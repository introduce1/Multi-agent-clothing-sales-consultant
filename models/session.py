# -*- coding: utf-8 -*-
"""
会话相关数据模型
包括对话会话、消息记录和会话统计
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from .database import Base

beijing_tz = timezone(timedelta(hours=8))


class SessionStatus(str, Enum):
    """会话状态枚举"""
    ACTIVE = "active"           # 活跃
    WAITING = "waiting"         # 等待中
    ESCALATED = "escalated"     # 已升级
    RESOLVED = "resolved"       # 已解决
    CLOSED = "closed"           # 已关闭
    TIMEOUT = "timeout"         # 超时
    ABANDONED = "abandoned"     # 已放弃


class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"               # 文本消息
    IMAGE = "image"             # 图片消息
    FILE = "file"               # 文件消息
    AUDIO = "audio"             # 音频消息
    VIDEO = "video"             # 视频消息
    SYSTEM = "system"           # 系统消息
    QUICK_REPLY = "quick_reply" # 快捷回复
    CARD = "card"               # 卡片消息


class MessageSender(str, Enum):
    """消息发送者枚举"""
    CUSTOMER = "customer"       # 客户
    AGENT = "agent"             # 智能体
    HUMAN = "human"             # 人工客服
    SYSTEM = "system"           # 系统


class EscalationReason(str, Enum):
    """升级原因枚举"""
    COMPLEX_ISSUE = "complex_issue"         # 复杂问题
    CUSTOMER_REQUEST = "customer_request"   # 客户要求
    AGENT_LIMITATION = "agent_limitation"   # 智能体限制
    QUALITY_ISSUE = "quality_issue"         # 质量问题
    TIMEOUT = "timeout"                     # 超时
    ERROR = "error"                         # 错误


class ChatSession(Base):
    """对话会话模型"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    
    # 会话基本信息
    status = Column(String(20), default=SessionStatus.ACTIVE)
    channel = Column(String(50))            # 渠道 (web, mobile, wechat, etc.)
    source = Column(String(50))             # 来源
    
    # 智能体信息
    current_agent = Column(String(50))      # 当前处理的智能体
    agent_history = Column(JSON)            # 智能体处理历史
    
    # 人工客服信息
    human_agent_id = Column(String(50))     # 人工客服ID
    escalation_reason = Column(String(50))  # 升级原因
    escalated_at = Column(DateTime)         # 升级时间
    
    # 会话属性
    priority = Column(String(20), default="normal")  # 优先级
    language = Column(String(10), default="zh")      # 语言
    timezone = Column(String(50), default="Asia/Shanghai")  # 时区
    
    # 统计信息
    message_count = Column(Integer, default=0)       # 消息数量
    agent_response_count = Column(Integer, default=0)  # 智能体回复数量
    human_response_count = Column(Integer, default=0)  # 人工回复数量
    
    # 满意度
    satisfaction_rating = Column(Integer)    # 满意度评分 1-5
    satisfaction_comment = Column(Text)      # 满意度评论
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    first_response_at = Column(DateTime)     # 首次回复时间
    last_activity_at = Column(DateTime)      # 最后活动时间
    resolved_at = Column(DateTime)           # 解决时间
    closed_at = Column(DateTime)             # 关闭时间
    
    # 会话上下文
    context = Column(JSON)                   # 会话上下文
    meta_data = Column(JSON)                  # 元数据
    
    # 关联关系
    customer = relationship("Customer", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    @hybrid_property
    def duration_minutes(self):
        """会话持续时间(分钟)"""
        if self.closed_at and self.created_at:
            return (self.closed_at - self.created_at).total_seconds() / 60
        elif self.last_activity_at and self.created_at:
            return (self.last_activity_at - self.created_at).total_seconds() / 60
        return 0
    
    @hybrid_property
    def response_time_minutes(self):
        """首次响应时间(分钟)"""
        if self.first_response_at and self.created_at:
            return (self.first_response_at - self.created_at).total_seconds() / 60
        return None
    
    @hybrid_property
    def is_escalated(self):
        """是否已升级"""
        return self.status == SessionStatus.ESCALATED
    
    @hybrid_property
    def is_active(self):
        """是否活跃"""
        return self.status in [SessionStatus.ACTIVE, SessionStatus.WAITING, SessionStatus.ESCALATED]
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity_at = datetime.now(beijing_tz)
        self.updated_at = datetime.now(beijing_tz)
    
    def escalate_to_human(self, reason: str, human_agent_id: str = None):
        """升级到人工客服"""
        self.status = SessionStatus.ESCALATED
        self.escalation_reason = reason
        self.escalated_at = datetime.now(beijing_tz)
        if human_agent_id:
            self.human_agent_id = human_agent_id
        self.update_activity()
    
    def resolve_session(self):
        """解决会话"""
        self.status = SessionStatus.RESOLVED
        self.resolved_at = datetime.now(beijing_tz)
        self.update_activity()
    
    def close_session(self):
        """关闭会话"""
        self.status = SessionStatus.CLOSED
        self.closed_at = datetime.now(beijing_tz)
        self.update_activity()
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "customer_id": self.customer_id,
            "status": self.status,
            "channel": self.channel,
            "source": self.source,
            "current_agent": self.current_agent,
            "human_agent_id": self.human_agent_id,
            "escalation_reason": self.escalation_reason,
            "priority": self.priority,
            "language": self.language,
            "message_count": self.message_count,
            "agent_response_count": self.agent_response_count,
            "human_response_count": self.human_response_count,
            "satisfaction_rating": self.satisfaction_rating,
            "satisfaction_comment": self.satisfaction_comment,
            "duration_minutes": self.duration_minutes,
            "response_time_minutes": self.response_time_minutes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "first_response_at": self.first_response_at.isoformat() if self.first_response_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "context": self.context or {},
            "metadata": self.metadata or {}
        }


class ChatMessage(Base):
    """对话消息模型"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    message_id = Column(String(100), unique=True, index=True)
    
    # 消息基本信息
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default=MessageType.TEXT)
    sender_type = Column(String(20), nullable=False)
    sender_id = Column(String(50))          # 发送者ID
    sender_name = Column(String(100))       # 发送者名称
    
    # 消息属性
    is_internal = Column(Boolean, default=False)  # 是否内部消息
    is_sensitive = Column(Boolean, default=False) # 是否敏感信息
    confidence_score = Column(Float)        # 置信度分数
    
    # 附件信息
    attachments = Column(JSON)              # 附件列表
    
    # 智能体处理信息
    agent_name = Column(String(50))         # 处理的智能体名称
    processing_time_ms = Column(Integer)    # 处理时间(毫秒)
    intent = Column(String(100))            # 识别的意图
    entities = Column(JSON)                 # 提取的实体
    
    # 回复信息
    reply_to_message_id = Column(String(100))  # 回复的消息ID
    quick_replies = Column(JSON)            # 快捷回复选项
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    delivered_at = Column(DateTime)         # 送达时间
    read_at = Column(DateTime)              # 已读时间
    
    # 元数据
    meta_data = Column(JSON)
    
    # 关联关系
    session = relationship("ChatSession", back_populates="messages")
    
    @hybrid_property
    def is_from_customer(self):
        """是否来自客户"""
        return self.sender_type == MessageSender.CUSTOMER
    
    @hybrid_property
    def is_from_agent(self):
        """是否来自智能体"""
        return self.sender_type == MessageSender.AGENT
    
    @hybrid_property
    def is_from_human(self):
        """是否来自人工客服"""
        return self.sender_type == MessageSender.HUMAN
    
    @hybrid_property
    def has_attachments(self):
        """是否有附件"""
        return bool(self.attachments)
    
    def mark_as_delivered(self):
        """标记为已送达"""
        self.delivered_at = datetime.now(beijing_tz)
    
    def mark_as_read(self):
        """标记为已读"""
        self.read_at = datetime.now(beijing_tz)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "content": self.content,
            "message_type": self.message_type,
            "sender_type": self.sender_type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "is_internal": self.is_internal,
            "is_sensitive": self.is_sensitive,
            "confidence_score": self.confidence_score,
            "attachments": self.attachments or [],
            "agent_name": self.agent_name,
            "processing_time_ms": self.processing_time_ms,
            "intent": self.intent,
            "entities": self.entities or {},
            "reply_to_message_id": self.reply_to_message_id,
            "quick_replies": self.quick_replies or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "metadata": self.metadata or {}
        }


class SessionStatistics(Base):
    """会话统计模型"""
    __tablename__ = "session_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), index=True)   # 日期 YYYY-MM-DD
    hour = Column(Integer)                  # 小时 0-23
    
    # 会话统计
    total_sessions = Column(Integer, default=0)
    active_sessions = Column(Integer, default=0)
    resolved_sessions = Column(Integer, default=0)
    escalated_sessions = Column(Integer, default=0)
    abandoned_sessions = Column(Integer, default=0)
    
    # 消息统计
    total_messages = Column(Integer, default=0)
    customer_messages = Column(Integer, default=0)
    agent_messages = Column(Integer, default=0)
    human_messages = Column(Integer, default=0)
    
    # 性能统计
    avg_response_time = Column(Float, default=0)    # 平均响应时间(分钟)
    avg_session_duration = Column(Float, default=0) # 平均会话时长(分钟)
    avg_messages_per_session = Column(Float, default=0)  # 平均每会话消息数
    
    # 满意度统计
    satisfaction_count = Column(Integer, default=0)
    avg_satisfaction_rating = Column(Float, default=0)
    
    # 智能体统计
    agent_usage = Column(JSON)              # 智能体使用统计
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    @hybrid_property
    def resolution_rate(self):
        """解决率"""
        if self.total_sessions > 0:
            return self.resolved_sessions / self.total_sessions
        return 0
    
    @hybrid_property
    def escalation_rate(self):
        """升级率"""
        if self.total_sessions > 0:
            return self.escalated_sessions / self.total_sessions
        return 0
    
    @hybrid_property
    def abandonment_rate(self):
        """放弃率"""
        if self.total_sessions > 0:
            return self.abandoned_sessions / self.total_sessions
        return 0
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "date": self.date,
            "hour": self.hour,
            "total_sessions": self.total_sessions,
            "active_sessions": self.active_sessions,
            "resolved_sessions": self.resolved_sessions,
            "escalated_sessions": self.escalated_sessions,
            "abandoned_sessions": self.abandoned_sessions,
            "total_messages": self.total_messages,
            "customer_messages": self.customer_messages,
            "agent_messages": self.agent_messages,
            "human_messages": self.human_messages,
            "avg_response_time": self.avg_response_time,
            "avg_session_duration": self.avg_session_duration,
            "avg_messages_per_session": self.avg_messages_per_session,
            "satisfaction_count": self.satisfaction_count,
            "avg_satisfaction_rating": self.avg_satisfaction_rating,
            "resolution_rate": self.resolution_rate,
            "escalation_rate": self.escalation_rate,
            "abandonment_rate": self.abandonment_rate,
            "agent_usage": self.agent_usage or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }