"""
对话上下文管理服务
负责管理多轮对话的上下文信息，包括对话历史、用户状态、意图跟踪等
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ContextType(Enum):
    """上下文类型"""
    USER_PROFILE = "user_profile"
    CONVERSATION_HISTORY = "conversation_history"
    INTENT_TRACKING = "intent_tracking"
    AGENT_STATE = "agent_state"
    SESSION_DATA = "session_data"

class IntentState(Enum):
    """意图状态"""
    INITIAL = "initial"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ESCALATED = "escalated"

@dataclass
class ConversationTurn:
    """对话轮次"""
    turn_id: str
    timestamp: datetime
    user_message: str
    agent_response: str
    agent_id: str
    intent_type: str
    confidence: float
    metadata: Dict[str, Any] = None

@dataclass
class IntentContext:
    """意图上下文"""
    intent_type: str
    state: IntentState
    start_time: datetime
    last_update: datetime
    collected_info: Dict[str, Any]
    required_info: List[str]
    completion_rate: float
    next_questions: List[str] = None

@dataclass
class UserContext:
    """用户上下文"""
    user_id: str
    session_id: str
    current_agent: str
    conversation_turns: List[ConversationTurn]
    intent_stack: List[IntentContext]
    user_profile: Dict[str, Any]
    preferences: Dict[str, Any]
    emotional_state: str
    satisfaction_score: float
    created_at: datetime
    last_activity: datetime

class ContextService:
    """上下文管理服务"""
    
    def __init__(self):
        # 内存存储（生产环境应使用Redis等）
        self.contexts: Dict[str, UserContext] = {}
        self.session_timeout = timedelta(hours=2)  # 会话超时时间
        self._cleanup_task = None  # 延迟创建清理任务
        
        # 意图完成度阈值
        self.completion_thresholds = {
            "product_inquiry": 0.8,
            "sales_consultation": 0.9,
            "technical_support": 0.85,
            "order_management": 0.95,
            "complaint_handling": 0.9
        }
        
        logger.info("🧠 对话上下文管理服务初始化完成")
    
    async def get_or_create_context(self, user_id: str, session_id: str) -> UserContext:
        """获取或创建用户上下文"""
        # 启动清理任务（如果还没有启动）
        if self._cleanup_task is None:
            try:
                self._cleanup_task = asyncio.create_task(self._cleanup_expired_contexts())
            except RuntimeError:
                # 如果没有运行的事件循环，跳过清理任务
                pass
        
        context_key = f"{user_id}_{session_id}"
        
        if context_key in self.contexts:
            context = self.contexts[context_key]
            # 更新最后活动时间
            context.last_activity = datetime.now()
            return context
        
        # 创建新的上下文
        context = UserContext(
            user_id=user_id,
            session_id=session_id,
            current_agent="reception_agent",
            conversation_turns=[],
            intent_stack=[],
            user_profile={},
            preferences={},
            emotional_state="neutral",
            satisfaction_score=0.5,
            created_at=datetime.now(),
            last_activity=datetime.now()
        )
        
        self.contexts[context_key] = context
        logger.info(f"📝 为用户 {user_id} 创建新的对话上下文")
        return context

    async def get_user_context(self, user_id: str, session_id: str = "default") -> Optional[UserContext]:
        """获取用户上下文"""
        context_key = f"{user_id}_{session_id}"
        return self.contexts.get(context_key)

    async def add_conversation_turn(
        self, 
        user_id: str, 
        session_id: str,
        user_message: str,
        agent_response: str,
        agent_id: str,
        intent_type: str,
        confidence: float,
        metadata: Dict[str, Any] = None
    ):
        """添加对话轮次"""
        context = await self.get_or_create_context(user_id, session_id)
        
        turn = ConversationTurn(
            turn_id=f"{len(context.conversation_turns) + 1}",
            timestamp=datetime.now(),
            user_message=user_message,
            agent_response=agent_response,
            agent_id=agent_id,
            intent_type=intent_type,
            confidence=confidence,
            metadata=metadata or {}
        )
        
        context.conversation_turns.append(turn)
        context.current_agent = agent_id
        context.last_activity = datetime.now()
        
        # 限制历史记录长度
        if len(context.conversation_turns) > 50:
            context.conversation_turns = context.conversation_turns[-50:]
        
        logger.debug(f"💬 添加对话轮次: {user_id} -> {agent_id}")
    
    async def update_intent_context(
        self,
        user_id: str,
        session_id: str,
        intent_type: str,
        collected_info: Dict[str, Any],
        required_info: List[str] = None
    ):
        """更新意图上下文"""
        context = await self.get_or_create_context(user_id, session_id)
        
        # 查找现有意图上下文
        intent_context = None
        for intent in context.intent_stack:
            if intent.intent_type == intent_type and intent.state in [IntentState.INITIAL, IntentState.ONGOING]:
                intent_context = intent
                break
        
        # 创建新的意图上下文
        if not intent_context:
            intent_context = IntentContext(
                intent_type=intent_type,
                state=IntentState.INITIAL,
                start_time=datetime.now(),
                last_update=datetime.now(),
                collected_info={},
                required_info=required_info or [],
                completion_rate=0.0
            )
            context.intent_stack.append(intent_context)
        
        # 更新收集的信息
        intent_context.collected_info.update(collected_info)
        intent_context.last_update = datetime.now()
        intent_context.state = IntentState.ONGOING
        
        # 计算完成度
        if intent_context.required_info:
            completed_items = sum(1 for item in intent_context.required_info 
                                if item in intent_context.collected_info)
            intent_context.completion_rate = completed_items / len(intent_context.required_info)
        
        # 检查是否完成
        threshold = self.completion_thresholds.get(intent_type, 0.8)
        if intent_context.completion_rate >= threshold:
            intent_context.state = IntentState.COMPLETED
        
        logger.debug(f"🎯 更新意图上下文: {intent_type} ({intent_context.completion_rate:.2f})")
    
    async def get_conversation_history(
        self, 
        user_id: str, 
        session_id: str, 
        limit: int = 10
    ) -> List[ConversationTurn]:
        """获取对话历史"""
        context = await self.get_or_create_context(user_id, session_id)
        return context.conversation_turns[-limit:] if context.conversation_turns else []
    
    async def get_current_intent(self, user_id: str, session_id: str) -> Optional[IntentContext]:
        """获取当前活跃的意图"""
        context = await self.get_or_create_context(user_id, session_id)
        
        for intent in reversed(context.intent_stack):
            if intent.state in [IntentState.INITIAL, IntentState.ONGOING]:
                return intent
        
        return None
    
    async def get_context_summary(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """获取上下文摘要"""
        context = await self.get_or_create_context(user_id, session_id)
        
        # 最近的对话轮次
        recent_turns = context.conversation_turns[-5:] if context.conversation_turns else []
        
        # 当前意图
        current_intent = await self.get_current_intent(user_id, session_id)
        
        # 用户画像关键信息
        profile_summary = {
            "segment": context.user_profile.get("segment"),
            "industry": context.user_profile.get("industry"),
            "company_size": context.user_profile.get("company_size"),
            "budget_range": context.user_profile.get("budget_range")
        }
        
        return {
            "user_id": user_id,
            "session_id": session_id,
            "current_agent": context.current_agent,
            "conversation_length": len(context.conversation_turns),
            "recent_turns": [
                {
                    "user_message": turn.user_message,
                    "agent_response": turn.agent_response[:100] + "..." if len(turn.agent_response) > 100 else turn.agent_response,
                    "agent_id": turn.agent_id,
                    "intent_type": turn.intent_type
                }
                for turn in recent_turns
            ],
            "current_intent": {
                "type": current_intent.intent_type,
                "state": current_intent.state.value,
                "completion_rate": current_intent.completion_rate,
                "collected_info": current_intent.collected_info
            } if current_intent else None,
            "user_profile": profile_summary,
            "emotional_state": context.emotional_state,
            "satisfaction_score": context.satisfaction_score,
            "session_duration": (datetime.now() - context.created_at).total_seconds() / 60  # 分钟
        }
    
    async def update_user_profile(
        self, 
        user_id: str, 
        session_id: str, 
        profile_data: Dict[str, Any]
    ):
        """更新用户画像"""
        context = await self.get_or_create_context(user_id, session_id)
        context.user_profile.update(profile_data)
        context.last_activity = datetime.now()
        
        logger.debug(f"👤 更新用户画像: {user_id}")
    
    async def update_emotional_state(
        self, 
        user_id: str, 
        session_id: str, 
        emotional_state: str,
        satisfaction_score: float = None
    ):
        """更新情感状态"""
        context = await self.get_or_create_context(user_id, session_id)
        context.emotional_state = emotional_state
        
        if satisfaction_score is not None:
            context.satisfaction_score = satisfaction_score
        
        context.last_activity = datetime.now()
        
        logger.debug(f"😊 更新情感状态: {user_id} -> {emotional_state}")
    
    async def complete_intent(self, user_id: str, session_id: str, intent_type: str):
        """完成意图"""
        context = await self.get_or_create_context(user_id, session_id)
        
        for intent in context.intent_stack:
            if intent.intent_type == intent_type and intent.state == IntentState.ONGOING:
                intent.state = IntentState.COMPLETED
                intent.completion_rate = 1.0
                intent.last_update = datetime.now()
                break
        
        logger.info(f"✅ 完成意图: {intent_type}")
    
    async def escalate_intent(
        self, 
        user_id: str, 
        session_id: str, 
        intent_type: str, 
        reason: str
    ):
        """升级意图到人工处理"""
        context = await self.get_or_create_context(user_id, session_id)
        
        for intent in context.intent_stack:
            if intent.intent_type == intent_type and intent.state == IntentState.ONGOING:
                intent.state = IntentState.ESCALATED
                intent.collected_info["escalation_reason"] = reason
                intent.last_update = datetime.now()
                break
        
        logger.warning(f"⚠️ 意图升级: {intent_type} - {reason}")
    
    async def get_missing_information(
        self, 
        user_id: str, 
        session_id: str, 
        intent_type: str
    ) -> List[str]:
        """获取缺失的信息"""
        context = await self.get_or_create_context(user_id, session_id)
        
        for intent in context.intent_stack:
            if intent.intent_type == intent_type:
                missing = []
                for required in intent.required_info:
                    if required not in intent.collected_info:
                        missing.append(required)
                return missing
        
        return []
    
    async def generate_context_prompt(
        self, 
        user_id: str, 
        session_id: str, 
        agent_id: str
    ) -> str:
        """生成包含上下文的提示词"""
        context_summary = await self.get_context_summary(user_id, session_id)
        
        prompt_parts = []
        
        # 用户基本信息
        if context_summary["user_profile"]:
            profile = context_summary["user_profile"]
            prompt_parts.append(f"用户信息: {profile}")
        
        # 当前意图
        if context_summary["current_intent"]:
            intent = context_summary["current_intent"]
            prompt_parts.append(f"当前意图: {intent['type']} (完成度: {intent['completion_rate']:.0%})")
            if intent["collected_info"]:
                prompt_parts.append(f"已收集信息: {intent['collected_info']}")
        
        # 对话历史
        if context_summary["recent_turns"]:
            prompt_parts.append("最近对话:")
            for turn in context_summary["recent_turns"][-3:]:  # 最近3轮
                prompt_parts.append(f"用户: {turn['user_message']}")
                prompt_parts.append(f"{turn['agent_id']}: {turn['agent_response']}")
        
        # 情感状态
        if context_summary["emotional_state"] != "neutral":
            prompt_parts.append(f"用户情感状态: {context_summary['emotional_state']}")
        
        return "\n".join(prompt_parts)
    
    async def _cleanup_expired_contexts(self):
        """清理过期的上下文"""
        while True:
            try:
                current_time = datetime.now()
                expired_keys = []
                
                for key, context in self.contexts.items():
                    if current_time - context.last_activity > self.session_timeout:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.contexts[key]
                    logger.debug(f"🗑️ 清理过期上下文: {key}")
                
                # 每10分钟清理一次
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"清理上下文时出错: {e}")
                await asyncio.sleep(60)

# 全局上下文服务实例
context_service = ContextService()