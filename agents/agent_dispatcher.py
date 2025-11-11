"""
智能调度器 - 基于GPT-4o的智能体协作和路由系统

主要功能：
1. 智能路由：基于GPT-4o的语义理解进行智能体选择
2. 协作管理：支持多种协作模式的智能体协同工作
3. 会话管理：维护智能化的会话状态和上下文
4. 工作流优化：自动选择最优的协作工作流
5. 性能监控：实时监控和优化智能体性能
"""

import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .base_agent import BaseAgent, AgentResponse, Message
from .reception_agent import ReceptionAgent
from .sales_agent import SalesAgent
from .order_agent import OrderAgent
from .knowledge_agent import KnowledgeAgent
from .styling_agent import StylingAgent
from .smart_collaboration import SmartCollaborationSystem
from services.product_search_service import product_search_service

logger = logging.getLogger(__name__)

# 智能体类型枚举
class AgentType(Enum):
    RECEPTION = "reception"
    SALES = "sales"
    ORDER = "order"
    KNOWLEDGE = "knowledge"
    STYLING = "styling"


# 会话状态枚举
class SessionStatus(Enum):
    ACTIVE = "活跃"
    COLLABORATING = "协作中"
    WAITING = "等待中"
    COMPLETED = "已完成"
    ERROR = "异常"


@dataclass
class SmartSession:
    """智能会话管理"""
    user_id: str
    session_id: str
    current_agents: List[str] = field(default_factory=list)
    collaboration_tasks: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    status: SessionStatus = SessionStatus.ACTIVE
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class SmartAgentDispatcher:
    """智能调度器 - 基于GPT-4o的智能协作系统"""
    
    def __init__(self, llm_client=None):
        # 确保 llm_client 是有效的 LLM 服务对象，否则使用默认服务
        if llm_client is None or not hasattr(llm_client, 'get_agent_response'):
            from agents.base_agent import get_llm_service
            self.llm_client = get_llm_service()
        else:
            self.llm_client = llm_client
        
        # 智能协作系统
        self.collaboration_system = SmartCollaborationSystem(llm_client)
        
        # 智能体实例
        self.agents = {
            "reception_agent": ReceptionAgent("reception_agent", llm_client),
            "sales_agent": SalesAgent("sales_agent", llm_client),
            "order_agent": OrderAgent("order_agent", llm_client),
            "knowledge_agent": KnowledgeAgent(llm_client=llm_client, product_search_service=product_search_service),
            "styling_agent": StylingAgent("styling_agent", llm_client, product_search_service=product_search_service)
        }
        
        # 会话管理
        self.sessions: Dict[str, SmartSession] = {}
        
        # 性能统计
        self.stats = {
            "total_messages": 0,
            "successful_collaborations": 0,
            "average_response_time": 0.0,
            "agent_usage": {agent_id: 0 for agent_id in self.agents.keys()},
            "collaboration_patterns": {}
        }
        
        # 简化的关键词映射（作为备用）
        self.keyword_mapping = {
            "reception": ["你好", "咨询", "帮助", "客服"],
            "sales": ["买", "购买", "推荐", "产品", "价格", "T恤", "连衣裙", "衬衫"],
            "order": ["订单", "物流", "快递", "发货", "退货", "换货", "售后"],
            "knowledge": ["面料", "材质", "保养", "洗涤", "护理"],
            "styling": ["搭配", "穿搭", "尺码", "风格", "颜色", "场合"]
        }

    async def process_message(self, user_id: str, message: Message) -> AgentResponse:
        """处理用户消息 - 智能协作流程"""
        start_time = datetime.now()
        
        try:
            # 获取或创建会话
            session = self._get_or_create_session(user_id, message.conversation_id)
            
            # 更新会话活跃时间
            session.last_active = datetime.now()
            session.conversation_history.append({
                "timestamp": datetime.now().isoformat(),
                "type": "user_message",
                "content": message.content,
                "metadata": message.metadata
            })
            
            # 分析协作需求
            collaboration_analysis = await self.collaboration_system.analyze_collaboration_need(
                message=message,
                context=session.context
            )

            # 基于强意图的规则覆盖：对明显购买/销售意图或用户确认转接强制优先路由到销售智能体
            collaboration_analysis = self._apply_override_rules(message, collaboration_analysis, session)
            
            # 创建协作任务
            collaboration_task = await self.collaboration_system.create_collaboration_task(
                analysis=collaboration_analysis,
                message=message,
                context=session.context
            )
            
            # 执行协作任务
            collaboration_result = await self.collaboration_system.execute_collaboration_task(
                task=collaboration_task,
                agents=self.agents
            )
            
            # 处理协作结果
            response = self._process_collaboration_result(collaboration_result, session)
            
            # 更新会话状态
            self._update_session_state(session, message, response, collaboration_result)
            
            # 更新性能统计
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_performance_stats(collaboration_result, response_time)
            
            return response
            
        except Exception as e:
            logger.error(f"消息处理失败: {e}")
            return await self._handle_error(user_id, message, str(e))

    def _apply_override_rules(self, message: Message, analysis: Dict[str, Any], session: SmartSession) -> Dict[str, Any]:
        """强意图覆盖规则：当检测到明显的购买/销售相关意图时，确保销售智能体为主处理者。
        这样可避免LLM分析偶发返回接待或其它智能体导致的误路由。
        """
        try:
            content = (message.content or "").lower()
            sales_keywords = [
                "购买", "买", "下单", "推荐", "价格", "优惠", "折扣", "产品", "商品",
                "衣服", "服装", "上衣", "裤子", "裙子", "外套", "衬衫", "t恤"
            ]
            # 扩展穿搭/风格相关关键词，覆盖常见偏好与场景
            styling_keywords = [
                "搭配", "穿搭", "尺码", "风格", "颜色",
                "休闲", "通勤", "正式", "约会", "运动", "街头", "简约", "复古",
                "法式", "韩系", "日系", "商务", "职场", "上班", "聚会", "旅行"
            ]
            # 订单相关强意图关键词
            order_keywords = [
                "订单", "查询订单", "订单查询", "订单号", "物流", "快递", "发货", "收货", "配送",
                "退货", "退款", "售后", "退换货", "跟踪", "物流查询", "快递查询"
            ]
            # 明确的强销售意图（更接近成交/报价）
            sales_strong_keywords = [
                "购买", "买", "下单", "推荐", "价格", "优惠", "折扣", "促销", "活动", "报价"
            ]

            affirmative_keywords = [
                "可以", "好的", "好", "行", "没问题", "是的", "嗯", "ok", "好啊", "没事", "确认"
            ]
            transfer_to_sales_keywords = [
                "转销售", "转接销售", "销售智能体", "销售顾问", "找销售", "请销售帮忙"
            ]
            transfer_to_order_keywords = [
                "转订单", "转接订单", "订单智能体", "订单顾问", "找订单", "请订单帮忙", "转到订单智能体"
            ]
            transfer_to_knowledge_keywords = [
                "转知识", "转接知识", "知识智能体", "知识顾问", "找知识", "请知识帮忙", "转到知识智能体"
            ]
            transfer_to_styling_keywords = [
                "转穿搭", "转接穿搭", "穿搭智能体", "穿搭顾问", "找穿搭", "请穿搭帮忙", "转到穿搭智能体"
            ]

            def contains_any(keywords: List[str]) -> bool:
                return any(k in content for k in keywords)

            # 当接待/其它智能体已建议转接某目标，且用户明确确认时，强制切到该目标
            handoff_pending = session.context.get("handoff_pending", False)
            handoff_target = session.context.get("handoff_target", "")
            if handoff_pending and handoff_target:
                confirm = contains_any(affirmative_keywords)
                if handoff_target == "sales_agent":
                    confirm = confirm or contains_any(transfer_to_sales_keywords)
                elif handoff_target == "order_agent":
                    confirm = confirm or contains_any(transfer_to_order_keywords)
                elif handoff_target == "knowledge_agent":
                    confirm = confirm or contains_any(transfer_to_knowledge_keywords)
                elif handoff_target == "styling_agent":
                    confirm = confirm or contains_any(transfer_to_styling_keywords)

                if confirm:
                    recommended = analysis.get("recommended_agents", []) or []
                    new_recommended: List[Dict[str, Any]] = [{"agent_id": handoff_target, "role": "primary", "priority": 1}]
                    for a in recommended:
                        aid = a.get("agent_id")
                        if aid and aid != handoff_target and not any(r.get("agent_id") == aid for r in new_recommended):
                            a2 = {**a}
                            a2["role"] = "support"
                            a2["parallel"] = True
                            a2["priority"] = max(2, a.get("priority", 2))
                            new_recommended.append(a2)
                    analysis["recommended_agents"] = new_recommended
                    analysis["collaboration_mode"] = "consultation"
                    analysis["task_priority"] = "high"
                    analysis["fallback_agent"] = handoff_target
                    session.context["handoff_pending"] = False

            # 显式转接到订单/知识/穿搭智能体（无需依赖先前建议）
            if contains_any(transfer_to_order_keywords):
                analysis["recommended_agents"] = [{"agent_id": "order_agent", "role": "primary", "priority": 1}]
                analysis["collaboration_mode"] = "consultation"
                analysis["task_priority"] = "high"
                analysis["fallback_agent"] = "order_agent"
            elif contains_any(transfer_to_knowledge_keywords):
                analysis["recommended_agents"] = [{"agent_id": "knowledge_agent", "role": "primary", "priority": 1}]
                analysis["collaboration_mode"] = "consultation"
                analysis["task_priority"] = "high"
                analysis["fallback_agent"] = "knowledge_agent"
            elif contains_any(transfer_to_styling_keywords):
                analysis["recommended_agents"] = [{"agent_id": "styling_agent", "role": "primary", "priority": 1}]
                analysis["collaboration_mode"] = "consultation"
                analysis["task_priority"] = "high"
                analysis["fallback_agent"] = "styling_agent"

            # 会话粘性：当前处于销售对话，除非用户明确要求转穿搭或存在强订单意图，保持销售为主
            try:
                if ("sales_agent" in session.current_agents) and not contains_any(transfer_to_styling_keywords) and not contains_any(order_keywords):
                    recommended = analysis.get("recommended_agents", []) or []
                    new_recommended: List[Dict[str, Any]] = []
                    # 保持销售为主
                    new_recommended.append({"agent_id": "sales_agent", "role": "primary", "priority": 1})
                    # 若出现穿搭相关词，加入穿搭为支持（并行）
                    if contains_any(styling_keywords) and not any(a.get("agent_id") == "styling_agent" for a in recommended):
                        new_recommended.append({"agent_id": "styling_agent", "role": "support", "priority": 3, "parallel": True})
                    # 知识智能体并行支持
                    knowledge_added = False
                    for a in recommended:
                        if a.get("agent_id") == "knowledge_agent":
                            a2 = {**a}
                            a2["role"] = "support"
                            a2["parallel"] = True
                            a2["priority"] = max(2, a.get("priority", 2))
                            new_recommended.append(a2)
                            knowledge_added = True
                            break
                    if not knowledge_added:
                        new_recommended.append({"agent_id": "knowledge_agent", "role": "support", "priority": 2, "parallel": True})
                    # 保留其它推荐项为支持（避免重复）
                    for a in recommended:
                        aid = a.get("agent_id")
                        if aid and aid not in {"sales_agent", "styling_agent", "knowledge_agent"} and not any(r.get("agent_id") == aid for r in new_recommended):
                            a2 = {**a}
                            a2["role"] = "support"
                            a2["parallel"] = True
                            a2["priority"] = max(3, a.get("priority", 3))
                            new_recommended.append(a2)
                    analysis["recommended_agents"] = new_recommended
                    analysis["collaboration_mode"] = "consultation"
                    analysis["task_priority"] = "high"
                    analysis["fallback_agent"] = "sales_agent"
            except Exception:
                pass

            # 穿搭主导但需要销售跟进：采用顺序协作（先穿搭，后销售）
            if contains_any(styling_keywords) and not contains_any(sales_keywords) and not contains_any(order_keywords):
                recommended = analysis.get("recommended_agents", []) or []
                new_recommended: List[Dict[str, Any]] = []
                new_recommended.append({"agent_id": "styling_agent", "role": "primary", "priority": 1})
                # 销售作为支持，在穿搭建议后为单品检索
                new_recommended.append({"agent_id": "sales_agent", "role": "support", "priority": 2})

                # 可选：知识智能体作为并行补充（材质/保养等），但不影响顺序协作
                knowledge_added = False
                for a in recommended:
                    if a.get("agent_id") == "knowledge_agent":
                        a2 = {**a}
                        a2["role"] = "support"
                        a2["priority"] = max(3, a.get("priority", 3))
                        a2["parallel"] = True
                        new_recommended.append(a2)
                        knowledge_added = True
                        break
                if not knowledge_added:
                    new_recommended.append({"agent_id": "knowledge_agent", "role": "support", "priority": 3, "parallel": True})

                analysis["recommended_agents"] = new_recommended
                analysis["collaboration_mode"] = "sequential"
                analysis["task_priority"] = "high"
                analysis["fallback_agent"] = "sales_agent"

            # 存在购买/销售相关意图时，默认销售为主；如同时包含穿搭意图，则将穿搭作为支持
            if contains_any(sales_keywords) and not contains_any(order_keywords):
                recommended = analysis.get("recommended_agents", []) or []

                # 构建新的推荐列表，确保 sales_agent 作为 primary 且排在首位
                new_recommended: List[Dict[str, Any]] = []
                new_recommended.append({"agent_id": "sales_agent", "role": "primary", "priority": 1})

                # 保留/添加知识智能体作为并行支持
                knowledge_added = False
                for a in recommended:
                    if a.get("agent_id") == "knowledge_agent":
                        a2 = {**a}
                        a2["role"] = "support"
                        a2["priority"] = max(2, a.get("priority", 2))
                        a2["parallel"] = True
                        new_recommended.append(a2)
                        knowledge_added = True
                        break
                if not knowledge_added:
                    new_recommended.append({"agent_id": "knowledge_agent", "role": "support", "priority": 2, "parallel": True})

                # 如涉及穿搭/尺码等，加入造型智能体支持（并行）
                if contains_any(styling_keywords):
                    new_recommended.append({"agent_id": "styling_agent", "role": "support", "priority": 3, "parallel": True})

                # 追加其它已推荐的非销售智能体，避免重复；接待智能体不设为主
                for a in recommended:
                    aid = a.get("agent_id")
                    if aid and aid != "sales_agent" and not any(r.get("agent_id") == aid for r in new_recommended):
                        new_recommended.append(a)

                analysis["recommended_agents"] = new_recommended
                # 咨询模式更适合销售为主、其它为辅的协作
                analysis["collaboration_mode"] = "consultation"
                analysis["task_priority"] = "high"
                analysis["fallback_agent"] = "sales_agent"

            # 同时出现穿搭与销售关键词：依据会话粘性与强销售意图确定主代理
            if contains_any(styling_keywords) and contains_any(sales_keywords) and not contains_any(order_keywords):
                prefer_sales = ("sales_agent" in session.current_agents) or contains_any(sales_strong_keywords)
                recommended: List[Dict[str, Any]] = []
                if prefer_sales:
                    # 销售为主，穿搭支持
                    recommended.append({"agent_id": "sales_agent", "role": "primary", "priority": 1})
                    recommended.append({"agent_id": "styling_agent", "role": "support", "priority": 2})
                    recommended.append({"agent_id": "knowledge_agent", "role": "support", "priority": 3, "parallel": True})
                    analysis["recommended_agents"] = recommended
                    analysis["collaboration_mode"] = "consultation"
                    analysis["task_priority"] = "high"
                    analysis["fallback_agent"] = "sales_agent"
                else:
                    # 穿搭为主，销售顺序跟进
                    recommended.append({"agent_id": "styling_agent", "role": "primary", "priority": 1})
                    recommended.append({"agent_id": "sales_agent", "role": "support", "priority": 2})
                    recommended.append({"agent_id": "knowledge_agent", "role": "support", "priority": 3, "parallel": True})
                    analysis["recommended_agents"] = recommended
                    analysis["collaboration_mode"] = "sequential"
                    analysis["task_priority"] = "high"
                    analysis["fallback_agent"] = "sales_agent"

            # 订单强意图：无论是否混杂其它关键词，优先订单为主
            if contains_any(order_keywords):
                recommended = analysis.get("recommended_agents", []) or []
                new_recommended: List[Dict[str, Any]] = [{"agent_id": "order_agent", "role": "primary", "priority": 1}]
                # 可选并行支持：知识/接待
                for a in recommended:
                    aid = a.get("agent_id")
                    if aid and aid != "order_agent" and not any(r.get("agent_id") == aid for r in new_recommended):
                        a2 = {**a}
                        a2["role"] = "support"
                        a2["parallel"] = True
                        a2["priority"] = max(2, a.get("priority", 2))
                        new_recommended.append(a2)
                analysis["recommended_agents"] = new_recommended
                analysis["collaboration_mode"] = "consultation"
                analysis["task_priority"] = "high"
                analysis["fallback_agent"] = "order_agent"

            # 会话粘性：上一轮协作包含穿搭智能体，且当前无明确销售意图 → 继续以穿搭为主，销售顺序支持
            try:
                if ("styling_agent" in session.current_agents) and not contains_any(sales_keywords) and not contains_any(order_keywords):
                    recommended = analysis.get("recommended_agents", []) or []
                    # 构建新的推荐，确保穿搭为主、销售支持
                    new_recommended: List[Dict[str, Any]] = []
                    # 保持穿搭为主
                    new_recommended.append({"agent_id": "styling_agent", "role": "primary", "priority": 1})
                    # 确保追加销售支持（避免重复）
                    if not any(a.get("agent_id") == "sales_agent" for a in recommended):
                        new_recommended.append({"agent_id": "sales_agent", "role": "support", "priority": 2})
                    # 追加其它推荐为并行支持
                    for a in recommended:
                        aid = a.get("agent_id")
                        if aid and aid not in {"styling_agent", "sales_agent"}:
                            a2 = {**a}
                            a2["role"] = "support"
                            a2["parallel"] = True
                            a2["priority"] = max(3, a.get("priority", 3))
                            new_recommended.append(a2)
                    analysis["recommended_agents"] = new_recommended
                    analysis["collaboration_mode"] = "sequential"
                    analysis["task_priority"] = "high"
                    analysis["fallback_agent"] = "sales_agent"
            except Exception:
                # 粘性规则失败不影响主流程
                pass

            # 兜底：如果当前推荐的主代理是穿搭智能体，则追加销售智能体支持并设置为顺序协作
            try:
                recommended = analysis.get("recommended_agents", []) or []
                primary = next((a for a in recommended if a.get("role") == "primary"), None)
                if primary and (primary.get("agent_id") == "styling_agent"):
                    has_sales = any(a.get("agent_id") == "sales_agent" for a in recommended)
                    if not has_sales:
                        recommended.append({"agent_id": "sales_agent", "role": "support", "priority": 2})
                        analysis["recommended_agents"] = recommended
                    analysis["collaboration_mode"] = "sequential"
            except Exception:
                pass

            return analysis
        except Exception:
            # 任何异常下保持原始分析结果，避免影响流程
            return analysis

    def _get_or_create_session(self, user_id: str, session_id: str) -> SmartSession:
        """获取或创建智能会话"""
        session_key = f"{user_id}_{session_id}"
        
        if session_key not in self.sessions:
            self.sessions[session_key] = SmartSession(
                user_id=user_id,
                session_id=session_id
            )
        
        return self.sessions[session_key]

    def _process_collaboration_result(self, collaboration_result: Dict[str, Any], session: SmartSession) -> AgentResponse:
        """处理协作结果"""
        if not collaboration_result.get("success", False):
            return AgentResponse(
                content="抱歉，处理您的请求时遇到了问题，请稍后重试。",
                agent_id="system",
                confidence=0.5,
                next_action="retry",
                metadata={"error": True, "collaboration_result": collaboration_result}
            )
        
        results = collaboration_result.get("results", [])
        if not results:
            return AgentResponse(
                content="抱歉，没有找到合适的处理方式。",
                agent_id="system",
                confidence=0.3,
                next_action="clarify"
            )
        
        # 获取主要结果。默认取 primary 角色；在穿搭→销售的顺序协作中，保持穿搭为主展示，销售作为补充。
        primary_result = None
        for result in results:
            if result.get("role") == "primary":
                primary_result = result
                break

        # 在没有明确primary时，保持默认选择，不再用支持结果覆盖
        
        if not primary_result:
            primary_result = results[-1]  # 使用最后一个结果
        
        # 处理主响应，兼容对象或字典
        primary_resp = primary_result.get("response")
        if isinstance(primary_resp, AgentResponse):
            base_content = primary_resp.content or "处理完成"
            base_confidence = primary_resp.confidence or 0.8
            base_next_action = primary_resp.next_action or "continue"
            base_metadata = primary_resp.metadata or {}
            base_requires_human = primary_resp.requires_human
            base_suggested_agents = getattr(primary_resp, "suggested_agents", []) or []
            base_intent_type = getattr(primary_resp, "intent_type", None)
            base_escalation_reason = getattr(primary_resp, "escalation_reason", None)
        else:
            primary_dict = primary_resp or {}
            base_content = primary_dict.get("content", "处理完成")
            base_confidence = primary_dict.get("confidence", 0.8)
            base_next_action = primary_dict.get("next_action", "continue")
            base_metadata = primary_dict.get("metadata", {})
            base_requires_human = primary_dict.get("requires_human", False)
            base_suggested_agents = primary_dict.get("suggested_agents", [])
            base_intent_type = primary_dict.get("intent_type")
            base_escalation_reason = primary_dict.get("escalation_reason")

        # 如果有多个智能体参与，默认不把辅助智能体内容拼接到主文本中
        # 改为将辅助信息放入 metadata，便于前端按需展示，避免混乱话术
        support_contents = []
        if len(results) > 1:
            for result in results:
                if result != primary_result:
                    resp = result.get("response")
                    if isinstance(resp, AgentResponse):
                        response_content = resp.content or ""
                    else:
                        response_content = (resp or {}).get("content", "")
                    if response_content:
                        support_contents.append({
                            "agent_id": result.get("agent_id", "unknown"),
                            "content": response_content
                        })

        # 特例：在“顺序协作”且由穿搭为主时，将销售的推荐简要拼接到主内容末尾，便于用户一屏看到建议→商品
        try:
            workflow_type = collaboration_result.get("workflow_type")
            primary_agent_id = primary_result.get("agent_id")
            if workflow_type == "sequential" and primary_agent_id == "styling_agent":
                sales_support = next((r for r in results if r.get("agent_id") == "sales_agent"), None)
                if sales_support:
                    sresp = sales_support.get("response")
                    scontent = (sresp.content if isinstance(sresp, AgentResponse) else (sresp or {}).get("content")) or ""
                    if scontent:
                        # 只追加一个简要分隔标题，保持主文风格
                        base_content = f"{base_content}\n\n——\n商品推荐（销售智能体）：\n{scontent}"
        except Exception:
            pass

        response = AgentResponse(
            content=base_content,
            agent_id=primary_result.get("agent_id", "system"),
            confidence=base_confidence,
            next_action=base_next_action,
            requires_human=base_requires_human,
            suggested_agents=base_suggested_agents,
            intent_type=base_intent_type,
            escalation_reason=base_escalation_reason,
            metadata={
                **base_metadata,
                "collaboration_info": {
                    "task_id": collaboration_result.get("task_id"),
                    "workflow_type": collaboration_result.get("workflow_type"),
                    "participating_agents": [r.get("agent_id") for r in results],
                    "collaboration_success": True,
                    "support_contents": support_contents
                }
            }
        )
        
        # 添加 current_agent 属性
        response.current_agent = primary_result.get("agent_id", "system")
        
        # 如果主响应建议转接某智能体，记录到会话上下文以便下轮用户确认时强制路由
        try:
            suggested_agents = response.suggested_agents or []
            next_action = response.next_action or "continue"
            # 统一建议名为内部 agent_id
            def normalize_agent_id(aid: str) -> str:
                if not aid:
                    return ""
                aid = aid.strip().lower()
                mapping = {
                    "sales": "sales_agent",
                    "order": "order_agent",
                    "knowledge": "knowledge_agent",
                    "styling": "styling_agent",
                }
                return mapping.get(aid, aid)

            normalized_suggestions = [normalize_agent_id(a) for a in suggested_agents]
            if next_action == "transfer" and normalized_suggestions:
                target = normalized_suggestions[0]
                mapped = None
                if target in {"sales_agent", "sales"}:
                    mapped = "sales_agent"
                elif target in {"order_agent", "order", "订单"}:
                    mapped = "order_agent"
                elif target in {"knowledge_agent", "knowledge"}:
                    mapped = "knowledge_agent"
                elif target in {"styling_agent", "styling", "穿搭"}:
                    mapped = "styling_agent"
                if mapped:
                    session.context["handoff_pending"] = True
                    session.context["handoff_target"] = mapped
        except Exception:
            pass

        return response
        try:
            suggested_agents = response.suggested_agents or []
            next_action = response.next_action or "continue"
            # 统一建议名为内部 agent_id
            def normalize_agent_id(aid: str) -> str:
                if not aid:
                    return ""
                aid = aid.strip().lower()
                mapping = {
                    "sales": "sales_agent",
                    "order": "order_agent",
                    "knowledge": "knowledge_agent",
                    "styling": "styling_agent",
                }
                return mapping.get(aid, aid)

            normalized_suggestions = [normalize_agent_id(a) for a in suggested_agents]
            if next_action == "transfer" and normalized_suggestions:
                target = normalized_suggestions[0]
                mapped = None
                if target in {"sales_agent", "sales"}:
                    mapped = "sales_agent"
                elif target in {"order_agent", "order", "订单"}:
                    mapped = "order_agent"
                elif target in {"knowledge_agent", "knowledge"}:
                    mapped = "knowledge_agent"
                elif target in {"styling_agent", "styling", "穿搭"}:
                    mapped = "styling_agent"
                if mapped:
                    session.context["handoff_pending"] = True
                    session.context["handoff_target"] = mapped
        except Exception:
            pass

    def _update_session_state(self, session: SmartSession, message: Message, response: AgentResponse, collaboration_result: Dict[str, Any]):
        """更新会话状态"""
        # 更新当前活跃的智能体
        participating_agents = [r.get("agent_id") for r in collaboration_result.get("results", [])]
        session.current_agents = participating_agents
        
        # 添加协作任务ID
        task_id = collaboration_result.get("task_id")
        if task_id and task_id not in session.collaboration_tasks:
            session.collaboration_tasks.append(task_id)
        
        # 更新上下文
        final_context = collaboration_result.get("final_context", {})
        session.context.update(final_context)
        
        # 记录响应
        session.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "agent_response",
            "agent_id": response.agent_id,
            "content": response.content,
            "collaboration_info": collaboration_result
        })
        
        # 更新性能指标
        if "performance_metrics" not in session.performance_metrics:
            session.performance_metrics = {
                "total_interactions": 0,
                "successful_collaborations": 0,
                "agent_switches": 0,
                "average_satisfaction": 0.0
            }
        
        session.performance_metrics["total_interactions"] += 1
        if collaboration_result.get("success"):
            session.performance_metrics["successful_collaborations"] += 1

    def _update_performance_stats(self, collaboration_result: Dict[str, Any], response_time: float):
        """更新性能统计"""
        self.stats["total_messages"] += 1
        
        # 更新平均响应时间
        total_time = self.stats["average_response_time"] * (self.stats["total_messages"] - 1) + response_time
        self.stats["average_response_time"] = total_time / self.stats["total_messages"]
        
        # 更新智能体使用统计
        for result in collaboration_result.get("results", []):
            agent_id = result.get("agent_id")
            if agent_id in self.stats["agent_usage"]:
                self.stats["agent_usage"][agent_id] += 1
        
        # 更新协作成功率
        if collaboration_result.get("success"):
            self.stats["successful_collaborations"] += 1
        
        # 记录协作模式
        workflow_type = collaboration_result.get("workflow_type", "unknown")
        if workflow_type not in self.stats["collaboration_patterns"]:
            self.stats["collaboration_patterns"][workflow_type] = 0
        self.stats["collaboration_patterns"][workflow_type] += 1
        
        # 更新智能体性能
        for result in collaboration_result.get("results", []):
            agent_id = result.get("agent_id")
            if agent_id:
                self.collaboration_system.update_agent_performance(
                    agent_id=agent_id,
                    response_time=response_time,
                    success=collaboration_result.get("success", False)
                )

    async def _handle_error(self, user_id: str, message: Message, error: str) -> AgentResponse:
        """处理错误情况"""
        logger.error(f"用户 {user_id} 消息处理错误: {error}")
        
        # 尝试使用接待智能体作为备用
        try:
            reception_agent = self.agents.get("reception_agent")
            if reception_agent:
                return await reception_agent.process_message(message, {})
        except Exception as e:
            logger.error(f"备用处理也失败: {e}")
        
        return AgentResponse(
            content="抱歉，系统暂时遇到问题，请稍后重试或联系人工客服。",
            agent_id="system",
            confidence=0.1,
            next_action="human_handoff",
            metadata={"error": True, "error_message": error}
        )

    def get_session_info(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        session_key = f"{user_id}_{session_id}"
        session = self.sessions.get(session_key)
        
        if not session:
            return None
        
        return {
            "user_id": session.user_id,
            "session_id": session.session_id,
            "current_agents": session.current_agents,
            "collaboration_tasks": session.collaboration_tasks,
            "status": session.status.value,
            "start_time": session.start_time.isoformat(),
            "last_active": session.last_active.isoformat(),
            "total_interactions": len(session.conversation_history),
            "performance_metrics": session.performance_metrics,
            "context_summary": {
                "keys": list(session.context.keys()),
                "size": len(session.context)
            }
        }

    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        collaboration_stats = self.collaboration_system.get_collaboration_stats()
        
        success_rate = 0.0
        if self.stats["total_messages"] > 0:
            success_rate = self.stats["successful_collaborations"] / self.stats["total_messages"]
        
        # 构建智能体信息（供管理与能力路由使用）
        agents_info: Dict[str, Any] = {}
        for agent_id, agent in self.agents.items():
            try:
                capabilities = agent.get_capabilities()
            except Exception:
                capabilities = []
            # 统一为“运行中/异常”状态（空闲与处理中都视为运行中）
            try:
                status_str = "异常" if getattr(agent, "status", None) == getattr(agent, "AgentStatus", None).ERROR else "运行中"
            except Exception:
                status_str = "运行中"
            agents_info[agent_id] = {
                "agent_id": agent_id,
                "name": agent_id.replace("_", " ").title(),
                "type": getattr(agent, "agent_type", "unknown"),
                "status": status_str,
                "capabilities": capabilities,
                "usage_count": self.stats.get("agent_usage", {}).get(agent_id, 0),
                "success_rate": 0.0,
                "average_confidence": 0.0,
                "last_active": None
            }

        # 路由规则信息（与覆盖规则保持一致，提供基础展示数据）
        routing_info = {
            "rules": [
                {
                    "rule_id": "sales_priority",
                    "name": "强意图优先销售",
                    "target_agent": "sales_agent",
                    "priority": 10,
                    "enabled": True,
                    "description": "当用户出现销售相关强意图，优先路由到销售。",
                    "conditions": ["包含关键词: 购买/价格/推荐/商品/下单"]
                }
            ]
        }

        return {
            "dispatcher_stats": {
                **self.stats,
                "success_rate": success_rate,
                "active_sessions": len(self.sessions),
                "total_agents": len(self.agents)
            },
            "collaboration_stats": collaboration_stats,
            "agents": agents_info,
            "routing": routing_info,
            "agent_health": {
                agent_id: {
                    "available": agent is not None,
                    "type": type(agent).__name__
                }
                for agent_id, agent in self.agents.items()
            }
        }

    def get_agent_status(self) -> Dict[str, Any]:
        """获取智能体运行状态（供健康与分析接口使用）"""
        status_map: Dict[str, Any] = {}
        for agent_id, agent in self.agents.items():
            try:
                status_str = "异常" if getattr(agent, "status", None) == getattr(agent, "AgentStatus", None).ERROR else "运行中"
            except Exception:
                status_str = "运行中"
            status_map[agent_id] = {
                "状态": status_str,
                "类型": getattr(agent, "agent_type", "unknown")
            }
        return status_map

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告（供统计分析接口使用）"""
        try:
            total_requests = int(self.stats.get("total_messages", 0))
            active_sessions = len(self.sessions)
            agent_usage = dict(self.stats.get("agent_usage", {}))
            # 可扩展的附加指标
            average_response_time = float(self.stats.get("average_response_time", 0.0))
            successful = int(self.stats.get("successful_collaborations", 0))
            success_rate = (successful / total_requests) if total_requests > 0 else 0.0
            return {
                "总请求数": total_requests,
                "活跃会话数": active_sessions,
                "智能体使用统计": agent_usage,
                "平均响应时间": average_response_time,
                "成功率": success_rate
            }
        except Exception:
            # 防御性返回最小结构
            return {
                "总请求数": self.stats.get("total_messages", 0),
                "活跃会话数": len(self.sessions),
                "智能体使用统计": self.stats.get("agent_usage", {})
            }

    async def cleanup_inactive_sessions(self, inactive_hours: int = 24) -> int:
        """清理非活跃会话"""
        cutoff_time = datetime.now() - timedelta(hours=inactive_hours)
        inactive_sessions = []
        
        for session_key, session in self.sessions.items():
            if session.last_active < cutoff_time:
                inactive_sessions.append(session_key)
        
        for session_key in inactive_sessions:
            del self.sessions[session_key]
        
        logger.info(f"清理了 {len(inactive_sessions)} 个非活跃会话")
        return len(inactive_sessions)

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_messages": 0,
            "successful_collaborations": 0,
            "average_response_time": 0.0,
            "agent_usage": {agent_id: 0 for agent_id in self.agents.keys()},
            "collaboration_patterns": {}
        }
        logger.info("统计信息已重置")


# 保持向后兼容性
AgentDispatcher = SmartAgentDispatcher

