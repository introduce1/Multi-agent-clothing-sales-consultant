"""
模拟LLM服务模块
提供可控的LLM模拟响应，用于本地开发和测试
"""

import json
import time
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass

from .llm_service import LLMResponse, ChatMessage


@dataclass
class MockLLMResponse:
    """模拟LLM响应数据类"""
    content: str
    model: str = "mock-model"
    provider: str = "mock"
    usage: Dict[str, int] = None
    response_time: float = 0.1
    success: bool = True
    error: Optional[str] = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}


class MockLLMService:
    """模拟LLM服务类"""
    
    def __init__(self):
        self.response_templates = self._get_response_templates()
    
    def _get_response_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取各智能体的响应模板"""
        return {
            "reception_agent": {
                "response": {
                    "content": "您好！欢迎来到我们的客服系统。我是接待助手，很高兴为您服务。请问您需要什么帮助？",
                    "metadata": {"agent_id": "reception_agent", "next_action": "continue"},
                    "suggested_agents": []
                }
            },
            "sales_agent": {
                "response": {
                    "content": "您好！我是销售助手，专门帮助您选购商品。请告诉我您想购买什么类型的商品？",
                    "metadata": {"agent_id": "sales_agent", "next_action": "continue"},
                    "suggested_agents": []
                }
            },
            "order_agent": {
                "response": {
                    "content": "您好！我是订单助手，可以帮您查询订单状态、处理售后问题。请提供您的订单号或手机号。",
                    "metadata": {"agent_id": "order_agent", "next_action": "continue"},
                    "suggested_agents": []
                }
            },
            "knowledge_agent": {
                "response": {
                    "content": "您好！我是知识助手，为您提供产品知识和使用指南。请问您想了解什么？",
                    "metadata": {"agent_id": "knowledge_agent", "next_action": "continue"},
                    "suggested_agents": []
                }
            },
            "styling_agent": {
                "response": {
                    "content": "您好！我是穿搭助手，可以为您提供时尚搭配建议。请告诉我您的穿搭需求或场合。",
                    "metadata": {"agent_id": "styling_agent", "next_action": "continue"},
                    "suggested_agents": []
                }
            }
        }
    
    async def get_agent_response(
        self,
        agent_name: str,
        messages: List[Union[ChatMessage, Dict[str, str]]],
        context_info: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """
        获取智能体响应（模拟版本）
        
        Args:
            agent_name: 智能体名称
            messages: 消息列表
            context_info: 上下文信息
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            LLMResponse: LLM响应对象
        """
        start_time = time.time()
        
        # 获取用户最后一条消息
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
            elif isinstance(msg, ChatMessage) and msg.role == "user":
                user_message = msg.content
                break
        
        # 根据智能体类型和用户消息生成响应
        response_content = self._generate_mock_response(agent_name, user_message, context_info)
        
        response_time = time.time() - start_time
        
        return LLMResponse(
            content=response_content,
            model="mock-model",
            provider="mock",
            usage={"prompt_tokens": len(str(messages)), "completion_tokens": len(response_content), "total_tokens": len(str(messages)) + len(response_content)},
            response_time=response_time,
            success=True
        )
    
    def _generate_mock_response(self, agent_name: str, user_message: str, context_info: Optional[Dict[str, Any]] = None) -> str:
        """生成模拟响应内容"""
        
        # 默认响应模板
        default_response = {
            "content": f"您好！我是{agent_name}，很高兴为您服务。请问您需要什么帮助？",
            "metadata": {"agent_id": agent_name, "next_action": "continue"},
            "suggested_agents": []
        }
        
        # 获取特定智能体的响应模板
        template = self.response_templates.get(agent_name, {}).get("response", default_response)
        
        # 根据用户消息内容动态调整响应
        if user_message:
            user_message_lower = user_message.lower()
            
            # 接待智能体逻辑
            if agent_name == "reception_agent":
                if any(word in user_message_lower for word in ["购买", "商品", "买东西", "购物"]):
                    template["content"] = "好的，我将为您转接到销售助手，帮助您选购商品。"
                    template["metadata"]["next_action"] = "transfer"
                    template["suggested_agents"] = ["sales_agent"]
                elif any(word in user_message_lower for word in ["订单", "物流", "售后", "退货"]):
                    template["content"] = "好的，我将为您转接到订单助手，处理您的订单相关问题。"
                    template["metadata"]["next_action"] = "transfer"
                    template["suggested_agents"] = ["order_agent"]
                elif any(word in user_message_lower for word in ["知识", "说明", "指南", "怎么用"]):
                    template["content"] = "好的，我将为您转接到知识助手，为您提供产品相关知识。"
                    template["metadata"]["next_action"] = "transfer"
                    template["suggested_agents"] = ["knowledge_agent"]
                elif any(word in user_message_lower for word in ["搭配", "穿搭", "时尚", "衣服怎么穿"]):
                    template["content"] = "好的，我将为您转接到穿搭助手，为您提供时尚搭配建议。"
                    template["metadata"]["next_action"] = "transfer"
                    template["suggested_agents"] = ["styling_agent"]
            
            # 销售智能体逻辑
            elif agent_name == "sales_agent":
                if "t恤" in user_message_lower or "衬衫" in user_message_lower:
                    template["content"] = "我们有很多优质的T恤和衬衫供您选择。请问您需要什么款式、颜色和尺码？"
                elif "裤子" in user_message_lower or "牛仔裤" in user_message_lower:
                    template["content"] = "我们提供多种款式的裤子和牛仔裤。请告诉我您的偏好和尺码要求。"
                elif "鞋子" in user_message_lower or "运动鞋" in user_message_lower:
                    template["content"] = "我们有很多时尚的鞋子和运动鞋。请问您需要什么类型和尺码？"
                elif "价格" in user_message_lower or "多少钱" in user_message_lower:
                    template["content"] = "我们的商品价格从几十元到几百元不等，具体取决于款式和品牌。您有预算范围吗？"
            
            # 订单智能体逻辑
            elif agent_name == "order_agent":
                if "查询" in user_message_lower or "状态" in user_message_lower:
                    template["content"] = "请提供您的订单号，我可以帮您查询订单状态。"
                elif "物流" in user_message_lower or "发货" in user_message_lower:
                    template["content"] = "请提供订单号，我可以查询物流信息。"
                elif "退货" in user_message_lower or "退款" in user_message_lower:
                    template["content"] = "请描述您要退货的原因，我会帮您处理退款流程。"
            
            # 知识智能体逻辑
            elif agent_name == "knowledge_agent":
                if "材质" in user_message_lower or "面料" in user_message_lower:
                    template["content"] = "我们的商品采用优质面料，包括棉、麻、丝、化纤等不同材质，各有特点。"
                elif "保养" in user_message_lower or "清洗" in user_message_lower:
                    template["content"] = "建议按照商品标签上的洗涤说明进行清洗，不同材质有不同的保养要求。"
                elif "尺寸" in user_message_lower or "尺码" in user_message_lower:
                    template["content"] = "我们提供详细的尺码表，请参考商品页面的尺码指南选择合适尺寸。"
            
            # 穿搭智能体逻辑
            elif agent_name == "styling_agent":
                if "休闲" in user_message_lower or "日常" in user_message_lower:
                    template["content"] = "休闲日常穿搭建议：T恤+牛仔裤+运动鞋，舒适又时尚。"
                elif "正式" in user_message_lower or "商务" in user_message_lower:
                    template["content"] = "商务正式穿搭建议：衬衫+西裤+皮鞋，专业得体。"
                elif "运动" in user_message_lower or "健身" in user_message_lower:
                    template["content"] = "运动健身穿搭建议：运动T恤+运动裤+专业运动鞋，活动自如。"
        
        # 返回JSON格式的响应
        return json.dumps(template, ensure_ascii=False)
    
    async def chat_completion(
        self,
        provider: str,
        model: str,
        messages: List[Union[ChatMessage, Dict[str, str]]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> LLMResponse:
        """
        模拟聊天完成接口
        
        Args:
            provider: 提供商名称
            model: 模型名称
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            LLMResponse: LLM响应对象
        """
        start_time = time.time()
        
        # 生成模拟响应
        response_text = "这是一个模拟的LLM响应，用于测试目的。"
        
        response_time = time.time() - start_time
        
        return LLMResponse(
            content=response_text,
            model=model,
            provider=provider,
            usage={"prompt_tokens": len(str(messages)), "completion_tokens": len(response_text), "total_tokens": len(str(messages)) + len(response_text)},
            response_time=response_time,
            success=True
        )