
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base_agent import Message, AgentResponse

logger = logging.getLogger(__name__)


class SmartCollaborationSystem:
    """面向多智能体协作的系统，负责分析是否需要协作、制定任务并执行。"""

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self.agent_id = "smart_collaboration_system"
        self.llm_client = llm_client
        # 代理性能统计（由调度器在每次协作后更新）
        # 结构: { agent_id: { total_calls, success_calls, avg_response_time, min_response_time, max_response_time, last_updated } }
        self._agent_performance: Dict[str, Dict[str, Any]] = {}

    async def analyze_collaboration_need(self, message: Message, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """分析是否需要协作，并输出推荐的协作方案。优先使用 LLM，失败时返回保守默认值。"""
        prompt = self._build_collaboration_analysis_prompt(message, context or {})
        analysis: Dict[str, Any] = {
            "requires_collaboration": False,
            "reason": "默认单代理处理",
            "collaboration_mode": "none",
            "recommended_agents": [{"agent_id": "reception_agent", "role": "primary"}],
        }

        if self.llm_client:
            try:
                llm_resp = await self.llm_client.get_agent_response(
                    agent_name=self.agent_id,
                    messages=[{"role": "system", "content": "你是负责客户服务协作分析的系统。"},
                              {"role": "user", "content": prompt}],
                    context_info={"agent_type": "system", "task": "collaboration_analysis"}
                )
                content = getattr(llm_resp, "content", None) or (llm_resp["content"] if isinstance(llm_resp, dict) else "")
                if content:
                    parsed = self._try_parse_json(content)
                    if parsed:
                        analysis = self._validate_collaboration_analysis(parsed, fallback=analysis)
            except Exception as e:
                logger.warning(f"LLM 协作分析失败，使用默认：{e}")

        return analysis

    async def create_collaboration_task(self, analysis: Dict[str, Any], message: Message, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """根据分析结果创建协作任务。"""
        context = context or {}
        task_id = f"collab-{uuid.uuid4().hex[:8]}"
        recommended: List[Dict[str, Any]] = analysis.get("recommended_agents", [])

        primary = next((a for a in recommended if a.get("role") == "primary"), None) or {
            "agent_id": "reception_agent", "role": "primary"
        }
        supports = [a for a in recommended if a.get("role") == "support" and a.get("agent_id")]

        workflow_type = analysis.get("collaboration_mode") or ("parallel" if supports else "single")
        priority = getattr(message, "priority", None)

        task = {
            "task_id": task_id,
            "workflow_type": workflow_type,
            "primary_agent": primary.get("agent_id") or "reception_agent",
            "support_agents": [a["agent_id"] for a in supports],
            "message": self._serialize_message(message),
            "priority": getattr(priority, "value", priority) or "medium",
            "context": context,
        }
        return task

    async def execute_collaboration_task(self, task: Dict[str, Any], agents: Dict[str, Any]) -> Dict[str, Any]:
        """执行协作任务：调用主代理与支持代理，聚合结果。
        支持两种模式：
        - parallel：主代理与支持代理分别处理原始消息（并发执行）
        - sequential：先执行主代理，再将主响应内容作为消息传递给支持代理
        """
        results: List[Dict[str, Any]] = []
        message_dict = task.get("message")
        # 将序列化的 message 还原为简单 Message，以最小依赖方式传递
        msg = Message(
            content=message_dict.get("content"),
            sender_id=message_dict.get("sender_id"),
            conversation_id=message_dict.get("conversation_id"),
            message_type=message_dict.get("message_type"),
            priority=message_dict.get("priority"),
            metadata=message_dict.get("metadata"),
        )

        async def _invoke(agent_id: str, role: str) -> Dict[str, Any]:
            agent = agents.get(agent_id)
            if not agent:
                return {"agent_id": agent_id, "role": role, "error": "agent_not_found"}
            try:
                resp: AgentResponse = await agent.process_message(msg, context=task.get("context", {}))
                payload = {
                    "agent_id": agent_id,
                    "role": role,
                    "response": {
                        "content": resp.content,
                        "confidence": resp.confidence,
                        "next_action": resp.next_action,
                        "suggested_agents": resp.suggested_agents,
                        "requires_human": resp.requires_human,
                        "agent_id": resp.agent_id,
                        "metadata": resp.metadata,
                        "intent_type": getattr(resp.intent_type, "value", resp.intent_type),
                        "escalation_reason": resp.escalation_reason,
                        "timestamp": getattr(resp.timestamp, "isoformat", lambda: str(resp.timestamp))()
                    }
                }
                return payload
            except Exception as e:
                logger.exception(f"代理 {agent_id} 执行失败：{e}")
                return {"agent_id": agent_id, "role": role, "error": str(e)}

        primary_id = task.get("primary_agent")
        support_ids: List[str] = task.get("support_agents", [])
        workflow_type = task.get("workflow_type", "single")

        # 主代理先执行
        primary_payload = None
        if primary_id:
            primary_payload = await _invoke(primary_id, role="primary")
            results.append(primary_payload)

        # 在所有场景下强制穿搭→销售的顺序协作：
        # 如果主代理是穿搭智能体，且当前支持列表中没有销售智能体，则追加销售智能体并切换为顺序协作。
        try:
            if primary_id == "styling_agent" and ("sales_agent" not in support_ids):
                support_ids = support_ids + ["sales_agent"]
                workflow_type = "sequential"
        except Exception:
            pass

        # 支持代理执行
        if support_ids:
            if workflow_type == "sequential" and primary_payload:
                # 以主响应的内容作为支持代理的输入消息，并在 metadata 中附加来源信息
                primary_resp = primary_payload.get("response", {})
                derived_msg = Message(
                    content=primary_resp.get("content", msg.content),
                    sender_id=msg.sender_id,
                    conversation_id=msg.conversation_id,
                    message_type=msg.message_type,
                    priority=msg.priority,
                    metadata={
                        **(msg.metadata or {}),
                        "source_agent": primary_payload.get("agent_id"),
                        "primary_response": primary_resp,
                        "original_message": self._serialize_message(msg),
                    },
                )

                async def _invoke_support(aid: str) -> Dict[str, Any]:
                    agent = agents.get(aid)
                    if not agent:
                        return {"agent_id": aid, "role": "support", "error": "agent_not_found"}
                    try:
                        resp: AgentResponse = await agent.process_message(derived_msg, context=task.get("context", {}))
                        payload = {
                            "agent_id": aid,
                            "role": "support",
                            "response": {
                                "content": resp.content,
                                "confidence": resp.confidence,
                                "next_action": resp.next_action,
                                "suggested_agents": resp.suggested_agents,
                                "requires_human": resp.requires_human,
                                "agent_id": resp.agent_id,
                                "metadata": resp.metadata,
                                "intent_type": getattr(resp.intent_type, "value", resp.intent_type),
                                "escalation_reason": resp.escalation_reason,
                                "timestamp": getattr(resp.timestamp, "isoformat", lambda: str(resp.timestamp))()
                            }
                        }
                        return payload
                    except Exception as e:
                        logger.exception(f"支持代理 {aid} 执行失败：{e}")
                        return {"agent_id": aid, "role": "support", "error": str(e)}

                support_results = await asyncio.gather(*[ _invoke_support(aid) for aid in support_ids ])
                results.extend(support_results)
            else:
                # 并行模式或无主响应内容，则支持代理使用原始消息
                support_results = await asyncio.gather(*[ _invoke(aid, role="support") for aid in support_ids ])
                results.extend(support_results)

        final_context = task.get("context", {}).copy()
        final_context.update({
            "last_collaboration_results": results,
            "workflow_type": workflow_type,
        })

        return {
            "success": True,
            "task_id": task.get("task_id"),
            "workflow_type": task.get("workflow_type"),
            "results": results,
            "final_context": final_context,
        }

    # ------------------------ 序列化与解析辅助 ------------------------
    def _serialize_message(self, message: Message) -> Dict[str, Any]:
        return {
            "content": message.content,
            "sender_id": message.sender_id,
            "conversation_id": message.conversation_id,
            "message_type": getattr(message.message_type, "value", message.message_type),
            "priority": getattr(message.priority, "value", message.priority),
            "metadata": message.metadata or {},
            "timestamp": getattr(message.timestamp, "isoformat", lambda: str(message.timestamp))()
        }

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        # 处理可能出现的多段文本，只取第一段 JSON
        if "{" in text and "}" in text:
            prefix = text[text.find("{") : text.rfind("}") + 1]
        else:
            prefix = text
        try:
            return json.loads(prefix)
        except Exception:
            fixed = self._fix_incomplete_json(prefix)
            try:
                return json.loads(fixed)
            except Exception:
                logger.debug("JSON 解析失败，内容: %s", text[:300])
                return None

    def _fix_incomplete_json(self, text: str) -> str:
        # 简单修复：闭合未配对的括号与引号
        opens = text.count("{") - text.count("}")
        if opens > 0:
            text += "}" * opens
        quotes = text.count('"')
        if quotes % 2 == 1:
            text += '"'
        return text

    def _validate_collaboration_analysis(self, data: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        try:
            requires = bool(data.get("requires_collaboration", False))
            mode = data.get("collaboration_mode") or ("parallel" if requires else "none")
            agents = data.get("recommended_agents") or []
            if not isinstance(agents, list):
                agents = []
            normalized = []
            for a in agents:
                if not isinstance(a, dict):
                    continue
                aid = a.get("agent_id") or a.get("id")
                role = a.get("role") or ("primary" if not normalized else "support")
                if aid:
                    normalized.append({"agent_id": str(aid), "role": role})
            if not normalized:
                normalized = [{"agent_id": "reception_agent", "role": "primary"}]
            return {
                "requires_collaboration": requires,
                "reason": data.get("reason") or "",
                "collaboration_mode": mode,
                "recommended_agents": normalized,
            }
        except Exception as e:
            logger.warning(f"协作分析校验失败，使用回退：{e}")
            return fallback

    # ------------------------ Prompt 构建与安全 JSON ------------------------
    def _build_collaboration_analysis_prompt(self, message: Message, context: Dict[str, Any]) -> str:
        context_json = self._safe_json_dump({
            "message": self._serialize_message(message),
            "context": context,
        }, ensure_ascii=False, indent=2, max_len=4000)

        return (
            "你是客户服务系统中的协作调度器，任务是判断是否需要让多个代理协作，"
            "并给出结构化 JSON 建议。\n\n"
            "请严格输出如下 JSON 结构：\n"
            "{\n"
            "  \"requires_collaboration\": true|false,\n"
            "  \"reason\": \"为什么需要或不需要协作\",\n"
            "  \"collaboration_mode\": \"parallel|sequential|none\",\n"
            "  \"recommended_agents\": [\n"
            "    { \"agent_id\": \"reception_agent|sales_agent|order_agent|knowledge_agent|styling_agent\", \"role\": \"primary|support\" }\n"
            "  ]\n"
            "}\n\n"
            f"上下文：\n{context_json}\n"
        )

    def _safe_json_dump(self, obj: Any, ensure_ascii: bool = False, indent: int = 2, max_len: int = 4000) -> str:
        """将对象安全地转换为 JSON 字符串，处理不可序列化类型并截断过长文本。"""
        try:
            sanitized = self._sanitize_for_json(obj)
            text = json.dumps(sanitized, ensure_ascii=ensure_ascii, indent=indent)
            if max_len and len(text) > max_len:
                return text[:max_len] + "\n(上下文过长，已截断)"
            return text
        except Exception as e:
            logger.warning(f"上下文 JSON 序列化失败，改用字符串表示: {e}")
            return str(obj)

    def _sanitize_for_json(self, obj: Any, _depth: int = 0, _max_depth: int = 3) -> Any:
        """递归清洗对象，使其可被 JSON 序列化。限制深度以避免过深嵌套。"""
        if _depth > _max_depth:
            return str(obj)
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, datetime):
            return obj.isoformat()
        try:
            from enum import Enum
            if isinstance(obj, Enum):
                return getattr(obj, 'value', str(obj))
        except Exception:
            pass
        if isinstance(obj, AgentResponse):
            intent = obj.intent_type
            return {
                "content": obj.content,
                "confidence": obj.confidence,
                "next_action": obj.next_action,
                "suggested_agents": obj.suggested_agents,
                "requires_human": obj.requires_human,
                "agent_id": obj.agent_id,
                "metadata": self._sanitize_for_json(obj.metadata, _depth + 1, _max_depth),
                "intent_type": getattr(intent, 'value', intent),
                "escalation_reason": obj.escalation_reason,
                "timestamp": getattr(obj.timestamp, 'isoformat', lambda: str(obj.timestamp))()
            }
        if isinstance(obj, Message):
            return self._serialize_message(obj)
        if isinstance(obj, dict):
            return {str(k): self._sanitize_for_json(v, _depth + 1, _max_depth) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            cleaned = [self._sanitize_for_json(v, _depth + 1, _max_depth) for v in obj]
            return cleaned[:50]
        return str(obj)

    # ------------------------ 性能统计接口 ------------------------
    def update_agent_performance(self, agent_id: str, response_time: float, success: bool) -> None:
        """更新指定代理的性能指标。
        由调度器在一次协作完成后调用，增量维护平均响应时间与成功次数。
        """
        if not agent_id:
            return
        perf = self._agent_performance.get(agent_id)
        if not perf:
            perf = {
                "total_calls": 0,
                "success_calls": 0,
                "avg_response_time": 0.0,
                "min_response_time": None,
                "max_response_time": None,
                "last_updated": None,
            }
            self._agent_performance[agent_id] = perf

        # 更新次数与成功数
        old_total = perf["total_calls"]
        perf["total_calls"] = old_total + 1
        if success:
            perf["success_calls"] = perf.get("success_calls", 0) + 1

        # 增量更新平均响应时间
        try:
            old_avg = float(perf.get("avg_response_time", 0.0))
            new_avg = ((old_avg * old_total) + float(response_time)) / max(1, perf["total_calls"])
            perf["avg_response_time"] = new_avg
        except Exception:
            # 防御性处理，出现异常时直接覆盖
            perf["avg_response_time"] = float(response_time) if response_time is not None else 0.0

        # 更新最小/最大响应时间
        rt = float(response_time) if response_time is not None else 0.0
        if perf["min_response_time"] is None or rt < perf["min_response_time"]:
            perf["min_response_time"] = rt
        if perf["max_response_time"] is None or rt > perf["max_response_time"]:
            perf["max_response_time"] = rt

        perf["last_updated"] = datetime.now().isoformat()

    def get_collaboration_stats(self) -> Dict[str, Any]:
        """获取协作统计数据，包括各代理的性能指标摘要。"""
        # 计算每个代理的成功率
        agent_perf: Dict[str, Any] = {}
        for aid, p in self._agent_performance.items():
            total = p.get("total_calls", 0) or 0
            succ = p.get("success_calls", 0) or 0
            success_rate = (succ / total) if total > 0 else 0.0
            agent_perf[aid] = {
                **p,
                "success_rate": success_rate,
            }

        return {
            "agent_performance": agent_perf,
            "total_agents": len(agent_perf),
            "updated_at": datetime.now().isoformat(),
        }
