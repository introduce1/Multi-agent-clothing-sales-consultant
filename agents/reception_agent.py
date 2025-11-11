# -*- coding: utf-8 -*-
"""
接待智能体 - 基于GPT-4o的智能接待和路由系统
负责用户接待、意图识别和智能路由
"""
from typing import Dict, Any, List
import json
from agents.base_agent import BaseAgent, Message, AgentResponse, IntentType
import logging

logger = logging.getLogger(__name__)


class ReceptionAgent(BaseAgent):
    """接待智能体 - 智能化版本"""
    
    def __init__(self, agent_id: str = "reception_agent", llm_client=None, config: Dict[str, Any] = None):
        super().__init__(agent_id, "reception", llm_client, config)
        
        # 智能体路由映射
        self.agent_routing = {
            "sales": ["销售咨询", "产品推荐", "购买建议", "价格咨询"],
            "order": ["订单查询", "订单状态", "物流信息", "订单修改"],
            "size": ["尺码咨询", "尺寸建议", "试穿指导", "尺码表"],
            "style": ["搭配建议", "风格推荐", "穿搭指导", "时尚建议"],
            "complaint": ["投诉处理", "售后服务", "退换货", "质量问题"]
        }

    def get_system_prompt(self) -> str:
        """获取接待智能体的系统提示词"""
        return f"""你是一个专业的服装客服接待智能体，负责精确的意图识别和智能路由。

## 核心职责：
1. **精确意图识别** - 深度分析用户消息，准确判断真实需求
2. **专业路由决策** - 基于明确的职责边界，将用户引导到最合适的专业智能体
3. **需求澄清** - 当意图不明确时，友好询问具体需求

## 智能体职责边界（严格遵循）：
- **sales_agent**: 购买咨询、产品推荐、价格询问、下单指导、商品选购
- **order_agent**: 订单查询、物流跟踪、订单修改、退换货处理、售后问题
- **knowledge_agent**: 面料知识、保养方法、洗涤指导、材质咨询、产品特性
- **styling_agent**: 穿搭建议、搭配指导、风格推荐、场合着装、形象设计

## 精确路由规则：
1. **购买意图关键词**: 买、购买、想买、多少钱、价格、选购、商品、下单、订购 → sales_agent
2. **订单相关关键词**: 订单、物流、发货、收货、退货、退款、订单号、快递、配送 → order_agent  
3. **知识咨询关键词**: 材质、保养、洗涤、面料、质量、怎么选、什么好、如何清洁、耐用性 → knowledge_agent
4. **穿搭建议关键词**: 穿搭、搭配、场合、风格、适合、推荐穿、穿衣、着装、造型 → styling_agent

## 对话风格：
- 专业精准，避免模糊
- 热情友好，耐心细致
- 主动澄清，避免误解
- 高效路由，减少转接

## 特别注意：
- 只有在需求明确匹配专业智能体职责时才建议转接
- 避免随意转接，特别是不要将所有请求都转给sales_agent
- 当意图不明确时，主动询问具体需求类型（购买、订单、知识、穿搭）
- 保持专业的服装客服形象，提供准确的引导服务"""

    def get_capabilities(self) -> List[str]:
        """获取接待智能体的核心能力"""
        return [
            "用户接待",
            "意图识别", 
            "智能路由",
            "需求澄清",
            "服务引导"
        ]

    async def process_message(self, message: Message, context: Dict[str, Any] = None) -> AgentResponse:
        """
        处理用户消息 - 智能接待和路由
        """
        try:
            self.status = self.AgentStatus.PROCESSING

            # 问候语快捷响应：简单问候无需意图分析，直接友好自我介绍
            if self._is_greeting(message.content):
                self.status = self.AgentStatus.IDLE
                return AgentResponse(
                    content="您好，我是服装客服接待助手，很高兴为您服务！您可以咨询购买、订单、穿搭或面料知识相关问题。",
                    agent_id=self.agent_id,
                    confidence=0.95,
                    next_action="continue",
                    intent_type=IntentType.GREETING,
                )
            
            # 构建智能路由提示词
            prompt = self._build_routing_prompt(message, context)
            
            # 调用GPT-4o进行智能分析和路由
            response_content = await self._generate_response(prompt)

            # 使用接待智能体专用解析：将路由JSON转换为友好话术与可转接指示
            parsed_response = self._parse_reception_response(response_content, message)
            
            # 更新对话记忆
            self._update_memory(message, parsed_response)
            
            self.status = self.AgentStatus.IDLE
            return parsed_response
            
        except Exception as e:
            logger.error(f"接待智能体处理失败: {e}")
            self.status = self.AgentStatus.ERROR
            return AgentResponse(
                content="您好！欢迎来到我们的服装店，请问有什么可以帮助您的吗？",
                confidence=0.8
            )

    def _build_routing_prompt(self, message: Message, context: Dict[str, Any] = None) -> str:
        """构建路由决策的提示词"""
        return f"""你是一个专业的服装客服接待智能体，负责精确的意图识别和智能路由。

## 当前用户消息：
{message.content}

## 智能体职责边界（严格分析后选择）：
- **sales_agent**: 仅限购买咨询、产品推荐、价格询问、下单指导、商品选购
- **order_agent**: 仅限订单查询、物流跟踪、订单修改、退换货处理、售后问题
- **knowledge_agent**: 仅限面料知识、保养方法、洗涤指导、材质咨询、产品特性
- **styling_agent**: 仅限穿搭建议、搭配指导、风格推荐、场合着装、形象设计

## 精确路由规则（必须严格遵循）：
1. **购买意图** (sales_agent): 包含"买、购买、想买、多少钱、价格、选购、商品、下单、订购、付款、支付"等关键词
2. **订单意图** (order_agent): 包含"订单、物流、发货、收货、退货、退款、订单号、快递、配送、售后、退换货"等关键词  
3. **知识意图** (knowledge_agent): 包含"材质、保养、洗涤、面料、质量、怎么选、什么好、如何清洁、耐用性、成分、特性"等关键词
4. **穿搭意图** (styling_agent): 包含"穿搭、搭配、场合、风格、适合、推荐穿、穿衣、着装、造型、配什么、怎么搭"等关键词

## 严格禁止：
- 不要将所有请求都转给sales_agent
- 不要将知识咨询转给sales_agent
- 不要将穿搭建议转给sales_agent
- 不要将订单问题转给sales_agent

## 输出要求：
请严格按照以下JSON格式输出，不要包含任何其他内容：
{{
  "intent": "意图类型",
  "target_agent": "目标智能体名称",
  "confidence": 置信度分数(0-1),
  "reason": "具体路由理由，说明关键词匹配情况"
}}

## 意图类型说明：
- purchase: 明确的购买咨询/商品选购意图
- order: 明确的订单相关/售后服务意图  
- knowledge: 明确的产品知识/保养咨询意图
- styling: 明确的穿搭建议/搭配指导意图
- unclear: 意图不明确，需要进一步询问用户具体需求

请严格分析用户消息，基于关键词匹配和语义理解，输出精确的路由决策。"""

    def _is_greeting(self, message_content: str) -> bool:
        """简单判断是否为问候语"""
        greetings = ["你好", "您好", "hi", "hello", "在吗", "客服", "接待", "接待专员", "你是不是", "你是客服吗"]
        content_lower = message_content.lower()
        return any(greeting in content_lower for greeting in greetings)

    def _get_suggested_agent(self, message_content: str) -> str:
        """基于关键词的智能体建议（后备方案）"""
        content_lower = message_content.lower()
        
        # 销售相关
        if any(word in content_lower for word in ["买", "购买", "价格", "多少钱", "推荐", "产品"]):
            return "sales"
        
        # 订单相关
        if any(word in content_lower for word in ["订单", "物流", "快递", "发货", "查询"]):
            return "order"
        
        # 尺码相关
        if any(word in content_lower for word in ["尺码", "尺寸", "大小", "合适", "试穿"]):
            return "size"
        
        # 搭配相关
        if any(word in content_lower for word in ["搭配", "穿搭", "风格", "款式", "好看"]):
            return "style"
        
        # 投诉相关
        if any(word in content_lower for word in ["投诉", "退货", "换货", "质量", "问题", "不满意"]):
            return "complaint"
        
        return "sales"  # 默认推荐销售智能体

    def _parse_reception_response(self, response_content: str, message: Message) -> AgentResponse:
        """解析接待智能体的路由JSON，并输出友好话术与可转接指示。
        - 当意图明确：设置 next_action="transfer" 与 suggested_agents，话术为转接确认/引导；
        - 当意图不明确：不转接，进行灵活聊天与澄清，引导用户说明需求。
        """
        try:
            cleaned = response_content.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned) if cleaned.startswith('{') else {}
        except Exception:
            # 如果解析失败，回退到基础解析（可能是直接话术）
            return super()._parse_response(response_content)

        intent = str(parsed.get("intent", "unclear")).lower()
        target = str(parsed.get("target_agent", "reception")).lower()
        confidence = float(parsed.get("confidence", 0.8))
        reason = parsed.get("reason", "")

        # 规范化目标智能体ID
        mapping = {
            "sales": "sales_agent",
            "order": "order_agent",
            "knowledge": "knowledge_agent",
            "styling": "styling_agent",
            "reception": "reception_agent"
        }
        normalized_target = mapping.get(target, target if target.endswith("_agent") else "reception_agent")

        # 明确意图 → 生成转接确认话术
        if intent in {"purchase", "order", "knowledge", "styling"}:
            agent_id = {
                "purchase": "sales_agent",
                "order": "order_agent",
                "knowledge": "knowledge_agent",
                "styling": "styling_agent"
            }[intent]

            zh_name = {
                "sales_agent": "销售助手",
                "order_agent": "订单助手",
                "knowledge_agent": "知识助手",
                "styling_agent": "穿搭助手"
            }[agent_id]

            # 友好且明确的转接确认话术
            content = (
                f"我已理解您的需求（{reason or '已识别为明确意图'}）。"
                f"为更快解决问题，我可以为您转接到{zh_name}。需要我现在为您转接吗？"
            )

            # 设置意图类型
            intent_type_map = {
                "purchase": IntentType.SALES_CONSULTATION,
                "order": IntentType.ORDER_INQUIRY,
                "knowledge": IntentType.OTHER,
                "styling": IntentType.STYLE_ADVICE
            }

            return AgentResponse(
                content=content,
                agent_id=self.agent_id,
                confidence=confidence,
                next_action="transfer",
                suggested_agents=[agent_id],
                intent_type=intent_type_map[intent],
                metadata={
                    "route_reason": reason,
                    "detected_intent": intent,
                    "detected_target": agent_id
                }
            )

        # 意图不明确 → 灵活聊天与澄清（不输出JSON）
        # 生成自然话术，体现“接待专员”身份与可聊天能力
        base_clarify = (
            "是的，我是接待专员，可以先和您聊聊，也可以帮您转接到相关专员。"
            "您更倾向于咨询哪方面：购买选购、订单/物流、穿搭建议，还是面料知识？"
        )
        # 若用户在问身份或寒暄，追加亲切问候
        if self._is_greeting(message.content):
            content = (
                "您好，我是接待专员，很高兴认识您！" + base_clarify
            )
        else:
            content = base_clarify

        return AgentResponse(
            content=content,
            agent_id=self.agent_id,
            confidence=confidence,
            next_action="continue",
            intent_type=IntentType.OTHER,
            metadata={
                "route_reason": reason,
                "detected_intent": "unclear",
                "detected_target": normalized_target
            }
        )


# 为了保持兼容性，保留原有的类名
class ClothingReceptionAgent(ReceptionAgent):
    """服装接待智能体 - 兼容性别名"""
    pass