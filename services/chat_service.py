"""
对话服务层
处理对话相关的业务逻辑
"""

import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from models.customer import Customer
from models.session import ChatSession
from models.analytics import Analytics

def get_agent_classes():
    from agents.base_agent import Message, MessageType, Priority
    return Message, MessageType, Priority

def get_agent_dispatcher():
    from agents.agent_dispatcher import SmartAgentDispatcher
    return SmartAgentDispatcher

from utils.logger import get_logger
from utils.cache import CacheManager, MemoryCache
from utils.rate_limiter import RateLimiter
from config.settings import settings

logger = get_logger(__name__)
beijing_tz = timezone(timedelta(hours=8))


class ChatService:
    """对话服务类"""
    
    def __init__(self):
        # 延迟导入避免循环导入
        SmartAgentDispatcher = get_agent_dispatcher()
        
        # 需要传入LLM客户端
        from services.llm_service import LLMService
        llm_service = LLMService()
        
        self.dispatcher = SmartAgentDispatcher(llm_service)
        self.cache_manager = CacheManager(backend=MemoryCache())
        self.rate_limiter = RateLimiter()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def _convert_to_priority(self, priority_str: str) -> 'Priority':
        """将字符串转换为Priority枚举"""
        Message, MessageType, Priority = get_agent_classes()
        priority_mapping = {
            "low": Priority.LOW,
            "normal": Priority.NORMAL,
            "medium": Priority.MEDIUM,
            "high": Priority.HIGH,
            "urgent": Priority.URGENT
        }
        
        priority_lower = priority_str.lower()
        if priority_lower in priority_mapping:
            return priority_mapping[priority_lower]
        else:
            logger.warning(f"无效的优先级值: {priority_str}, 使用默认值 'normal'")
            return Priority.NORMAL
    
    async def process_message(
        self,
        message_content: str,
        session_id: Optional[str] = None,
        customer_id: Optional[int] = None,
        message_type: str = "text",
        priority: str = "normal",
        context: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            message_content: 消息内容
            session_id: 会话ID
            customer_id: 客户ID
            message_type: 消息类型
            priority: 消息优先级
            context: 上下文信息
            db: 数据库会话
            
        Returns:
            处理结果
        """
        try:
            # 获取类定义
            Message, MessageType, Priority = get_agent_classes()
            
            # 生成消息ID
            message_id = str(uuid.uuid4())
            
            # 如果没有会话ID，创建新会话
            if not session_id:
                session_id = await self._create_new_session(customer_id, db)
            
            # 检查会话是否存在
            session_info = await self._get_or_create_session(session_id, customer_id, db)
            
            # 速率限制检查
            if not await self._check_rate_limit(session_id, customer_id):
                return {
                    "success": False,
                    "error": "请求过于频繁，请稍后再试",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }
            
            # 创建消息对象
            try:
                msg_type = MessageType(message_type) if isinstance(message_type, str) else message_type
            except ValueError:
                msg_type = MessageType.TEXT  # 默认为文本类型
                
            message = Message(
                content=message_content,
                message_type=msg_type,
                priority=self._convert_to_priority(priority),
                sender_id=customer_id or session_info.get("customer_id", "anonymous"),
                conversation_id=session_id,
                metadata=context or {},
                timestamp=datetime.now(beijing_tz)
            )
            
            # 更新会话活跃状态
            await self._update_session_activity(session_id, message)
            
            # 通过智能体调度器处理消息
            response = await self.dispatcher.process_message(
                user_id=customer_id or session_info.get("customer_id", "anonymous"),
                message=message
            )
            
            # 保存对话记录
            await self._save_conversation_record(message, response, db)
            
            # 更新分析统计
            await self._update_analytics(session_id, message, response, db)
            
            # 缓存响应
            await self._cache_response(session_id, message_id, response)
            
            return {
                "success": True,
                "message_id": message_id,
                "session_id": session_id,
                "response": response.content,
                "confidence": response.confidence,
                "agent_id": response.agent_id or "unknown",
                # 兼容字符串或枚举类型的意图值
                "intent_type": (getattr(response.intent_type, "value", response.intent_type)
                                 if response.intent_type is not None else None),
                "requires_human": response.requires_human,
                "escalation_reason": response.escalation_reason,
                "next_action": response.next_action,
                "metadata": response.metadata,
                "timestamp": datetime.now(beijing_tz).isoformat()
            }
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": "消息处理失败",
                "error_code": "MESSAGE_PROCESSING_ERROR",
                "details": str(e)
            }
    
    async def get_session_info(
        self,
        session_id: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        获取会话信息
        
        Args:
            session_id: 会话ID
            db: 数据库会话
            
        Returns:
            会话信息
        """
        try:
            # 从缓存获取
            cached_info = await self.cache_manager.get(f"session:{session_id}")
            if cached_info:
                return cached_info
            
            # 从数据库获取
            if db:
                session = db.query(ChatSession).filter(
                    ChatSession.id == session_id
                ).first()
                
                if session:
                    session_info = {
                        "session_id": session.id,
                        "customer_id": session.customer_id,
                        "status": session.status,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "message_count": len(session.messages) if hasattr(session, 'messages') else 0,
                        "current_agent": session.current_agent,
                        "context": session.context or {}
                    }
                    
                    # 缓存会话信息
                    await self.cache_manager.set(
                        f"session:{session_id}",
                        session_info,
                        expire=3600  # 1小时
                    )
                    
                    return session_info
            
            # 检查内存中的活跃会话
            if session_id in self.active_sessions:
                return self.active_sessions[session_id]
            
            return {
                "error": "会话不存在",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"获取会话信息失败: {e}")
            return {
                "error": "获取会话信息失败",
                "details": str(e)
            }
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        获取对话历史
        
        Args:
            session_id: 会话ID
            limit: 限制数量
            offset: 偏移量
            db: 数据库会话
            
        Returns:
            对话历史
        """
        try:
            # 从缓存获取
            cache_key = f"history:{session_id}:{limit}:{offset}"
            cached_history = await self.cache_manager.get(cache_key)
            if cached_history:
                return cached_history
            
            # 从数据库获取（这里需要实现具体的数据库查询逻辑）
            history = {
                "session_id": session_id,
                "messages": [],
                "total_count": 0,
                "has_more": False
            }
            
            # 缓存历史记录
            await self.cache_manager.set(cache_key, history, expire=1800)  # 30分钟
            
            return history
            
        except Exception as e:
            logger.error(f"获取对话历史失败: {e}")
            return {
                "error": "获取对话历史失败",
                "details": str(e)
            }
    
    async def end_session(
        self,
        session_id: str,
        reason: str = "user_ended",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        结束会话
        
        Args:
            session_id: 会话ID
            reason: 结束原因
            db: 数据库会话
            
        Returns:
            结束结果
        """
        try:
            # 更新数据库中的会话状态
            if db:
                session = db.query(ChatSession).filter(
                    ChatSession.id == session_id
                ).first()
                
                if session:
                    session.status = "ended"
                    session.end_reason = reason
                    session.ended_at = datetime.now(beijing_tz)
                    db.commit()
            
            # 从活跃会话中移除
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # 清除相关缓存
            await self.cache_manager.delete(f"session:{session_id}")
            await self.cache_manager.delete_pattern(f"history:{session_id}:*")
            
            # 清理调度器中的会话
            if hasattr(self.dispatcher, 'cleanup_session'):
                await self.dispatcher.cleanup_session(session_id)
            
            return {
                "success": True,
                "session_id": session_id,
                "message": "会话已结束"
            }
            
        except Exception as e:
            logger.error(f"结束会话失败: {e}")
            return {
                "success": False,
                "error": "结束会话失败",
                "details": str(e)
            }
    
    async def transfer_to_human(
        self,
        session_id: str,
        reason: str,
        agent_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        转接人工客服
        
        Args:
            session_id: 会话ID
            reason: 转接原因
            agent_id: 指定的人工客服ID
            db: 数据库会话
            
        Returns:
            转接结果
        """
        try:
            # 更新会话状态
            if db:
                session = db.query(ChatSession).filter(
                    ChatSession.id == session_id
                ).first()
                
                if session:
                    session.status = "human_transfer"
                    session.human_agent_id = agent_id
                    session.transfer_reason = reason
                    session.transferred_at = datetime.now(beijing_tz)
                    db.commit()
            
            # 更新活跃会话信息
            if session_id in self.active_sessions:
                self.active_sessions[session_id].update({
                    "status": "human_transfer",
                    "human_agent_id": agent_id,
                    "transfer_reason": reason,
                    "transferred_at": datetime.now(beijing_tz).isoformat()
                })
            
            # 通知调度器转接人工
            if hasattr(self.dispatcher, 'transfer_to_human'):
                await self.dispatcher.transfer_to_human(session_id, reason)
            
            return {
                "success": True,
                "session_id": session_id,
                "message": "已转接人工客服",
                "human_agent_id": agent_id,
                "transfer_reason": reason
            }
            
        except Exception as e:
            logger.error(f"转接人工客服失败: {e}")
            return {
                "success": False,
                "error": "转接人工客服失败",
                "details": str(e)
            }
    
    async def _create_new_session(
        self,
        customer_id: Optional[int] = None,
        db: Optional[Session] = None
    ) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        
        # 创建会话记录
        if db and customer_id:
            new_session = ChatSession(
                session_id=session_id,
                customer_id=customer_id,
                status="active",
                created_at=datetime.now(beijing_tz),
                updated_at=datetime.now(beijing_tz)
            )
            db.add(new_session)
            db.commit()
        
        # 添加到活跃会话
        self.active_sessions[session_id] = {
            "session_id": session_id,
            "customer_id": customer_id,
            "status": "active",
            "created_at": datetime.now(beijing_tz).isoformat(),
            "message_count": 0,
            "current_agent": None
        }
        
        return session_id
    
    async def _get_or_create_session(
        self,
        session_id: str,
        customer_id: Optional[int] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """获取或创建会话"""
        session_info = await self.get_session_info(session_id, db)
        
        if "error" in session_info:
            # 会话不存在，创建新会话
            if customer_id:
                new_session_id = await self._create_new_session(customer_id, db)
                return await self.get_session_info(new_session_id, db)
            else:
                raise ValueError("会话不存在且未提供客户ID")
        
        return session_info
    
    async def _check_rate_limit(
        self,
        session_id: str,
        customer_id: Optional[str] = None
    ) -> bool:
        """检查速率限制"""
        try:
            # 基于会话的速率限制
            session_key = f"rate_limit:session:{session_id}"
            allowed, info = await self.rate_limiter.is_allowed(session_key)
            if not allowed:
                return False
            
            # 基于客户的速率限制
            if customer_id:
                customer_key = f"rate_limit:customer:{customer_id}"
                allowed, info = await self.rate_limiter.is_allowed(customer_key)
                if not allowed:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"速率限制检查失败: {e}")
            return True  # 出错时允许通过
    
    async def _update_session_activity(
        self,
        session_id: str,
        message: 'Message'
    ):
        """更新会话活跃状态"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].update({
                "last_activity": datetime.now(beijing_tz).isoformat(),
                "message_count": self.active_sessions[session_id].get("message_count", 0) + 1,
                "last_message_type": message.message_type.value
            })
    
    async def _save_conversation_record(
        self,
        message: 'Message',
        response: 'Message',
        db: Optional[Session] = None
    ):
        """保存对话记录"""
        try:
            # 这里应该实现具体的数据库保存逻辑
            # 保存用户消息和AI响应
            pass
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")
    
    async def _update_analytics(
        self,
        session_id: str,
        message: 'Message',
        response: 'Message',
        db: Optional[Session] = None
    ):
        """更新分析统计"""
        try:
            if db:
                # 更新或创建分析记录
                today = datetime.now(beijing_tz).date()
                analytics = db.query(Analytics).filter(
                    Analytics.date == today
                ).first()
                
                if not analytics:
                    analytics = Analytics(
                        date=today,
                        total_messages=0,
                        successful_responses=0,
                        failed_responses=0,
                        avg_response_time=0.0,
                        unique_users=0,
                        agent_usage={}
                    )
                    db.add(analytics)
                
                # 更新统计数据
                analytics.total_messages += 1
                if response.confidence > 0.7:
                    analytics.successful_responses += 1
                else:
                    analytics.failed_responses += 1
                
                # 更新智能体使用统计
                agent_usage = analytics.agent_usage or {}
                agent_id = response.agent_id or "unknown"
                agent_usage[agent_id] = agent_usage.get(agent_id, 0) + 1
                analytics.agent_usage = agent_usage
                
                db.commit()
                
        except Exception as e:
            logger.error(f"更新分析统计失败: {e}")
    
    async def _cache_response(
        self,
        session_id: str,
        message_id: str,
        response: 'Message'
    ):
        """缓存响应"""
        try:
            cache_key = f"response:{session_id}:{message_id}"
            response_data = {
                "content": response.content,
                "confidence": response.confidence,
                "agent_id": response.agent_id,
                "timestamp": response.timestamp.isoformat(),
                "metadata": response.metadata
            }
            
            await self.cache_manager.set(
                cache_key,
                response_data,
                expire=3600  # 1小时
            )
            
        except Exception as e:
            logger.error(f"缓存响应失败: {e}")
    
    async def get_active_sessions_count(self) -> int:
        """获取活跃会话数量"""
        return len(self.active_sessions)
    
    async def cleanup_inactive_sessions(self, max_inactive_minutes: int = 30):
        """清理非活跃会话"""
        try:
            current_time = datetime.now(beijing_tz)
            inactive_sessions = []
            
            for session_id, session_info in self.active_sessions.items():
                last_activity = session_info.get("last_activity")
                if last_activity:
                    last_activity_time = datetime.fromisoformat(last_activity)
                    if (current_time - last_activity_time).total_seconds() > max_inactive_minutes * 60:
                        inactive_sessions.append(session_id)
            
            # 清理非活跃会话
            for session_id in inactive_sessions:
                await self.end_session(session_id, "inactive_timeout")
                logger.info(f"清理非活跃会话: {session_id}")
            
            return len(inactive_sessions)
            
        except Exception as e:
            logger.error(f"清理非活跃会话失败: {e}")
            return 0


# 全局对话服务实例 - 延迟初始化
chat_service = None

def get_chat_service():
    """获取聊天服务实例"""
    global chat_service
    if chat_service is None:
        chat_service = ChatService()
    return chat_service