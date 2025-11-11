# -*- coding: utf-8 -*-
"""
多智能体客服系统 - 智能体基类
基于GPT-4o的智能对话系统，减少硬编码，提升语义理解能力
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import logging
import uuid

logger = logging.getLogger(__name__)
beijing_tz = timezone(timedelta(hours=8))

# 延迟导入避免循环导入
def get_llm_service():
    from services.llm_service import llm_service
    return llm_service

def get_context_service():
    from services.context_service import context_service
    return context_service


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    SYSTEM = "system"
    AGENT_RESPONSE = "agent_response"


class Priority(Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AgentStatus(Enum):
    """智能体状态"""
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"


class IntentType(Enum):
    """意图类型 - 简化版"""
    GREETING = "greeting"
    PRODUCT_INQUIRY = "product_inquiry"
    SALES_CONSULTATION = "sales_consultation"
    ORDER_INQUIRY = "order_inquiry"
    SIZE_CONSULTATION = "size_consultation"
    STYLE_ADVICE = "style_advice"
    COMPLAINT = "complaint"
    OTHER = "other"


class Message:
    """消息类 - 简化版"""
    def __init__(self, content: str, sender_id: str = "", conversation_id: str = "", 
                 message_type: MessageType = MessageType.TEXT, priority: Priority = Priority.NORMAL,
                 metadata: Dict = None, timestamp: datetime = None, user_id: str = None):
        self.content = content
        # 兼容旧代码：既支持 sender_id，也支持 user_id
        self.sender_id = sender_id or (user_id or "")
        self.user_id = user_id or sender_id or ""
        self.conversation_id = conversation_id
        # 兼容传入字符串或枚举类型
        try:
            self.message_type = message_type if isinstance(message_type, MessageType) else MessageType(message_type)
        except Exception:
            self.message_type = MessageType.TEXT
        self.priority = priority
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now(beijing_tz)


class AgentResponse:
    """智能体响应类 - 简化版"""
    def __init__(self, content: str, confidence: float = 0.8, 
                 next_action: str = None, suggested_agents: List[str] = None,
                 requires_human: bool = False, agent_id: str = None,
                 metadata: Dict[str, Any] = None,
                 intent_type: Optional[IntentType] = None,
                 escalation_reason: Optional[str] = None):
        self.content = content
        self.confidence = confidence
        self.next_action = next_action
        self.suggested_agents = suggested_agents or []
        self.requires_human = requires_human
        self.agent_id = agent_id
        self.metadata = metadata or {}
        self.intent_type = intent_type
        self.escalation_reason = escalation_reason
        self.timestamp = datetime.now(beijing_tz)


class BaseAgent(ABC):
    """智能体基类 - 基于GPT-4o的智能对话"""
    
    def __init__(self, agent_id: str, agent_type: str, llm_client=None, config: Dict[str, Any] = None):
        self.agent_id = agent_id
        self.agent_type = agent_type
        # 确保 llm_client 是有效的 LLM 服务对象，否则使用默认服务
        if llm_client is None or not hasattr(llm_client, 'get_agent_response'):
            self.llm_client = get_llm_service()
        else:
            self.llm_client = llm_client
        self.config = config or {}
        self.status = AgentStatus.IDLE
        # 为旧代码提供枚举别名，兼容 self.AgentStatus 等引用
        self.AgentStatus = AgentStatus
        self.MessageType = MessageType
        self.IntentType = IntentType
        self.Priority = Priority
        
        # 对话记忆 - 简化版
        self.conversation_memory = {}
        
        logger.info(f"智能体 {agent_id} ({agent_type}) 初始化完成")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取智能体的系统提示词"""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """获取智能体的核心能力列表"""
        pass

    async def process_message(self, message: Message, context: Dict[str, Any] = None) -> AgentResponse:
        """
        处理消息 - 智能化版本
        """
        try:
            self.status = AgentStatus.PROCESSING
            
            # 构建智能提示词
            prompt = self._build_intelligent_prompt(message, context)
            
            # 调用GPT-4o生成回复
            response_content = await self._generate_response(prompt)
            
            # 解析响应并提取结构化信息
            parsed_response = self._parse_response(response_content)
            
            # 更新对话记忆
            self._update_memory(message, parsed_response)
            
            self.status = AgentStatus.IDLE
            return parsed_response
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            self.status = AgentStatus.ERROR
            return AgentResponse(
                content="抱歉，我暂时无法处理您的请求，请稍后再试。",
                confidence=0.0
            )

    def _build_intelligent_prompt(self, message: Message, context: Dict[str, Any] = None) -> str:
        """构建智能提示词"""
        prompt_parts = [
            self.get_system_prompt(),
            "",
            "## 当前对话上下文："
        ]
        
        # 添加对话历史
        history = self._get_conversation_history(message.conversation_id)
        if history:
            prompt_parts.append("### 对话历史：")
            for item in history[-3:]:  # 只保留最近3轮对话
                prompt_parts.append(f"用户: {item['user']}")
                prompt_parts.append(f"助手: {item['assistant']}")
            prompt_parts.append("")
        
        # 添加上下文信息
        if context:
            prompt_parts.append("### 上下文信息：")
            for key, value in context.items():
                if value:
                    prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("")
        
        # 添加当前用户消息
        prompt_parts.extend([
            "## 用户当前消息：",
            message.content,
            "",
            "## 请求：",
            "请根据上述信息，以JSON格式返回响应：",
            "{",
            '  "content": "你的回复内容",',
            '  "confidence": 0.8,',
            '  "next_action": "continue/transfer/complete",',
            '  "suggested_agents": ["如果需要转接，建议的智能体"],',
            '  "requires_human": false',
            "}"
        ])
        
        return "\n".join(prompt_parts)

    async def _generate_response(self, prompt: str) -> str:
        """调用GPT-4o生成回复"""
        if not self.llm_client:
            return '{"content": "抱歉，当前无法提供智能回复服务。", "confidence": 0.0}'
        
        try:
            # 使用统一的智能体响应接口，自动选择模型并返回文本内容
            llm_response = await self.llm_client.get_agent_response(
                agent_name=self.agent_id,
                messages=[{"role": "user", "content": prompt}],
                context_info={"agent_type": self.agent_type}
            )
            return llm_response.content or '{"content": "", "confidence": 0.0}'
        except Exception as e:
            logger.error(f"GPT-4o调用失败: {e}")
            return '{"content": "抱歉，我暂时无法理解您的问题。", "confidence": 0.0}'

    def _parse_response(self, response_content: str) -> AgentResponse:
        """解析GPT-4o的JSON响应"""
        try:
            # 尝试提取JSON部分
            if "```json" in response_content:
                json_start = response_content.find("```json") + 7
                json_end = response_content.find("```", json_start)
                json_content = response_content[json_start:json_end].strip()
            elif response_content.strip().startswith("{"):
                json_content = response_content.strip()
            else:
                # 如果不是JSON格式，直接返回文本内容
                return AgentResponse(
                    content=response_content.replace("**", ""), 
                    confidence=0.5,
                    intent_type=None,
                    escalation_reason=None
                )
            
            # 尝试修复不完整的JSON
            try:
                parsed = json.loads(json_content)
            except json.JSONDecodeError:
                # 尝试修复JSON
                fixed_content = self._fix_incomplete_json(json_content)
                if fixed_content != json_content:
                    logger.info("尝试修复不完整的JSON响应")
                    try:
                        parsed = json.loads(fixed_content)
                    except json.JSONDecodeError:
                        # 修复失败，返回原始内容
                        return AgentResponse(
                            content=response_content, 
                            confidence=0.5,
                            intent_type=None,
                            escalation_reason=None
                        )
                else:
                    # 无法修复，返回原始内容
                    return AgentResponse(
                        content=response_content, 
                        confidence=0.5,
                        intent_type=None,
                        escalation_reason=None
                    )
            
            return AgentResponse(
                content=parsed.get("content", response_content).replace("**", ""),
                confidence=parsed.get("confidence", 0.8),
                next_action=parsed.get("next_action"),
                suggested_agents=parsed.get("suggested_agents", []),
                requires_human=parsed.get("requires_human", False),
                intent_type=parsed.get("intent_type"),
                escalation_reason=parsed.get("escalation_reason")
            )
            
        except json.JSONDecodeError:
            # JSON解析失败，返回原始内容
            return AgentResponse(
                content=response_content.replace("**", ""), 
                confidence=0.5,
                intent_type=None,
                escalation_reason=None
            )

    def _get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_memory.get(conversation_id, [])

    def _update_memory(self, message: Message, response: AgentResponse):
        """更新对话记忆"""
        conversation_id = message.conversation_id
        if conversation_id not in self.conversation_memory:
            self.conversation_memory[conversation_id] = []
        
        self.conversation_memory[conversation_id].append({
            "user": message.content,
            "assistant": response.content,
            "timestamp": datetime.now(beijing_tz)
        })
        
        # 限制记忆长度，只保留最近10轮对话
        if len(self.conversation_memory[conversation_id]) > 10:
            self.conversation_memory[conversation_id] = self.conversation_memory[conversation_id][-10:]

    async def can_handle(self, message: Message) -> Dict[str, Any]:
        """
        智能判断是否能处理该消息
        """
        capabilities = self.get_capabilities()
        
        # 使用GPT-4o进行智能匹配
        match_prompt = f"""
        请判断以下用户消息是否属于我的处理范围：
        
        我的能力范围：{', '.join(capabilities)}
        用户消息：{message.content}
        
        请返回JSON格式：
        {{
            "can_handle": true/false,
            "confidence": 0.8,
            "reason": "判断理由"
        }}
        """
        
        try:
            response = await self._generate_response(match_prompt)
            result = json.loads(response)
            return result
        except:
            # 如果智能判断失败，使用关键词匹配作为后备
            return self._fallback_keyword_match(message)

    def _fallback_keyword_match(self, message: Message) -> Dict[str, Any]:
        """关键词匹配后备方案"""
        capabilities = self.get_capabilities()
        content_lower = message.content.lower()
        
        # 简单的关键词匹配逻辑
        for capability in capabilities:
            if capability.lower() in content_lower:
                return {
                    "can_handle": True,
                    "confidence": 0.6,
                    "reason": f"关键词匹配: {capability}"
                }
        
        return {
            "can_handle": False,
            "confidence": 0.3,
            "reason": "无匹配的关键词"
        }

    def _fix_incomplete_json(self, content: str) -> str:
        """修复不完整的JSON响应"""
        if not content or not content.strip():
            return content
        
        # 移除可能的Markdown代码块标记
        content = content.strip()
        if content.startswith('```json'):
            content = content[7:].strip()
        if content.startswith('```'):
            content = content[3:].strip()
        if content.endswith('```'):
            content = content[:-3].strip()
        
        # 检查是否以{开头，以}结尾
        if content.startswith('{') and not content.endswith('}'):
            # 尝试找到最后一个有效的JSON结构并闭合
            stack = []
            last_valid_pos = 0
            
            for i, char in enumerate(content):
                if char == '{':
                    stack.append('{')
                    last_valid_pos = i
                elif char == '}':
                    if stack:
                        stack.pop()
                    last_valid_pos = i
                elif char == '[':
                    stack.append('[')
                    last_valid_pos = i
                elif char == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
                    last_valid_pos = i
            
            # 如果栈不为空，说明有未闭合的结构
            if stack:
                # 在最后一个有效位置后截断并添加闭合符号
                truncated = content[:last_valid_pos + 1]
                # 闭合所有未闭合的结构
                for brace in reversed(stack):
                    if brace == '{':
                        truncated += '}'
                    elif brace == '[':
                        truncated += ']'
                return truncated
        
        # 如果内容不以{开头，尝试提取JSON部分
        if not content.startswith('{'):
            # 查找第一个{和最后一个}
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                return content[start_idx:end_idx + 1]
        
        return content