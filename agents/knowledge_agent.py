"""
知识智能体 - 基于GPT-4o的服装知识咨询系统

主要功能：
1. 服装面料知识介绍和咨询
2. 衣物保养和护理指导
3. 服装材质特性说明
4. 洗涤护理建议
5. 服装相关问题智能解答
"""

import json
import logging
from typing import Dict, List, Optional, Any

from .base_agent import BaseAgent, AgentResponse, Message

logger = logging.getLogger(__name__)

# 系统提示词 - 让GPT-4o发挥专业知识能力
KNOWLEDGE_SYSTEM_PROMPT = """你是一个专业的服装知识顾问，专门负责服装面料、护理和材质相关的知识咨询。

## 核心职责（严格限定）：
1. **面料知识** - 详细介绍各种服装面料的特性、优缺点、适用场合和季节
2. **护理指导** - 提供专业的衣物洗涤、保养、收纳和去污建议
3. **材质识别** - 帮助用户识别和了解不同服装材质的特点
4. **知识解答** - 回答各种服装相关的专业问题
5. **材质建议** - 根据用户需求推荐合适的面料和材质选择

## 严格禁止处理以下内容（必须转接）：
- **订单查询** - 关于订单状态、物流信息 → 转接订单智能体
- **购买咨询** - 关于商品购买、价格优惠 → 转接销售智能体
- **穿搭建议** - 关于服装搭配、风格建议 → 转接穿搭智能体
- **尺寸咨询** - 关于尺码选择、尺寸问题 → 转接销售智能体

## 边界检查规则：
当客户咨询包含以下关键词时，必须转接到相应智能体：
- 订单智能体：订单、快递、物流、发货、收货、配送
- 销售智能体：购买、价格、优惠、推荐、商品咨询、尺码
- 穿搭智能体：搭配、风格、场合、颜色、体型、穿搭

## 专业原则：
- 提供准确、实用的服装知识
- 用通俗易懂的语言解释专业概念
- 结合用户的实际使用场景给出建议
- 考虑不同季节、气候和个人需求
- 遇到非知识相关问题，立即转接到相应智能体

## 回答风格：
- 专业而友好，像一个经验丰富的服装顾问
- 提供具体、可操作的建议
- 适当举例说明，让用户更容易理解
- 主动询问用户的具体需求以提供更精准的建议
"""


class KnowledgeAgent(BaseAgent):
    """知识智能体 - 专业的服装知识咨询顾问"""
    
    def __init__(self, llm_client=None, product_search_service=None):
        super().__init__("knowledge_agent", "knowledge", llm_client)
        self.product_search_service = product_search_service
        self.capabilities = [
            "服装面料知识介绍",
            "衣物保养护理指导", 
            "材质特性说明",
            "洗涤护理建议",
            "服装知识问答",
            "面料选择建议",
            "相关商品推荐"  # 新增功能
        ]
        
        # 简化的关键词匹配（仅作为备用）
        self.keywords = [
            "面料", "材质", "保养", "洗涤", "护理", "材料", "成分", "清洁",
            "棉质", "丝绸", "羊毛", "亚麻", "聚酯", "尼龙", "氨纶", "羊绒",
            "牛仔布", "皮革", "洗衣", "晾晒", "熨烫", "收纳", "去污", "防皱",
            "推荐", "购买", "商品", "哪里买"  # 新增搜索相关关键词
        ]

    async def process_message(self, message: Message, context: Dict[str, Any] = None) -> AgentResponse:
        """处理用户消息 - 智能知识咨询"""
        try:
            # 构建知识咨询提示词
            knowledge_prompt = self._build_knowledge_prompt(message, context or {})
            
            # 使用GPT-4o进行智能分析和回答
            response_content = await self._generate_knowledge_response(knowledge_prompt)
            
            # 解析响应
            parsed_response = self._parse_response(response_content)
            
            # 如果需要推荐相关商品，调用搜索API
            if parsed_response.get('need_product_search'):
                search_results = await self._search_knowledge_products(parsed_response.get('search_params', {}))
                if search_results and search_results.get('success'):
                    # 重新生成包含商品推荐的响应
                    product_prompt = self._build_product_knowledge_prompt(message, search_results, parsed_response)
                    response_content = await self._generate_knowledge_response(product_prompt)
                    parsed_response = self._parse_response(response_content)
            
            # 更新对话记忆
            self._update_conversation_memory(message, parsed_response, context or {})
            
            return AgentResponse(
                content=parsed_response.get("content", "我会尽力为您提供专业的服装知识建议。"),
                agent_id=self.agent_id,
                confidence=parsed_response.get("confidence", 0.8),
                next_action=parsed_response.get("next_action", "continue"),
                metadata={
                    "knowledge_type": parsed_response.get("knowledge_type", "general"),
                    "topics_covered": parsed_response.get("topics_covered", []),
                    "suggestions": parsed_response.get("suggestions", []),
                    "related_questions": parsed_response.get("related_questions", []),
                    "recommended_products": parsed_response.get("recommended_products", [])  # 新增商品推荐
                }
            )
            
        except Exception as e:
            logger.error(f"知识智能体处理消息失败: {e}")
            return AgentResponse(
                content="抱歉，我在处理您的问题时遇到了困难。请重新描述您想了解的服装知识问题，我会尽力为您解答。",
                agent_id=self.agent_id,
                confidence=0.3,
                next_action="retry"
            )

    def _build_knowledge_prompt(self, message: Message, context: Dict[str, Any]) -> str:
        """构建知识咨询提示词（输出为纯自然语言，禁止JSON/代码块）"""
        # 获取对话历史
        conversation_history = context.get("conversation_history", [])
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-3:]  # 最近3轮对话
            history_text = "\n".join([
                f"用户: {h.get('user', '')}\n助手: {h.get('assistant', '')}" 
                for h in recent_history if h.get('user') and h.get('assistant')
            ])
        
        # 构建完整提示词
        prompt = f"""
作为专业的服装知识顾问，请先进行边界检查，再提供清晰、实用的自然语言回答。

## 边界检查（重要）：
请严格检查用户消息是否属于知识智能体的职责范围。如果包含以下内容，必须转接到相应智能体：
- 订单查询、物流信息 → 转接订单智能体
- 购买咨询、价格优惠、推荐具体商品 → 转接销售智能体
- 穿搭建议、风格搭配 → 转接穿搭智能体
- 尺寸咨询、尺码选择 → 转接销售智能体

用户问题：{message.content}

{f"对话历史：{history_text}" if history_text else ""}

## 输出要求（务必遵守）：
- 使用纯自然语言，不要输出任何JSON或代码块（禁止```json```）。
- 结构化但自然：
  1) 简短总结用户意图与边界判断；
  2) 核心知识点（要点式，2-5条）；
  3) 场景化建议（可操作步骤或注意事项，3-6条）；
  4) 若需更多信息，礼貌提出1-2个澄清问题；
  5) 可选：延伸阅读或相关问题提示（1-3条）。
- 用通俗易懂的语言解释专业概念，避免过度术语。
- 不进行商品购买建议或价格讨论，涉及购买请明确建议转接销售智能体。
"""
        return prompt

    async def _generate_knowledge_response(self, prompt: str) -> str:
        """使用GPT-4o生成知识回答"""
        if not self.llm_client:
            return self._fallback_knowledge_response()
        
        try:
            messages = [
                {"role": "system", "content": KNOWLEDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
            
            # 使用统一的智能体响应接口，自动选择模型并返回文本内容
            llm_response = await self.llm_client.get_agent_response(
                agent_name=self.agent_id,
                messages=messages,
                context_info={"agent_type": "knowledge"}
            )
            return llm_response.content or self._fallback_knowledge_response()
            
        except Exception as e:
            logger.error(f"GPT-4o知识回答生成失败: {e}")
            return self._fallback_knowledge_response()

    def _fallback_knowledge_response(self) -> str:
        """备用知识回答（自然语言，无JSON）"""
        return (
            "我是专业的服装知识顾问，可以为您介绍面料特性、护理方法与材质知识。"
            "请告诉我您想了解的具体内容（如某种面料的优缺点、洗涤注意事项、收纳保养等），"
            "我会用通俗易懂的语言给出可操作的建议。"
        )

    def _parse_response(self, response_content: str) -> Dict[str, Any]:
        """解析响应：剔除代码块/JSON，输出纯自然语言内容"""
        try:
            cleaned = response_content.strip()

            # 移除任意位置的三引号代码块（包括```json```）
            while True:
                start = cleaned.find("```")
                if start == -1:
                    break
                end = cleaned.find("```", start + 3)
                if end == -1:
                    # 无闭合，移除起始标记以避免残留
                    cleaned = cleaned[:start] + cleaned[start + 3:]
                    break
                cleaned = (cleaned[:start] + cleaned[end + 3:]).strip()

            cleaned = cleaned.replace("**", "")
            # 返回自然语言内容
            return {
                "content": cleaned,
                "confidence": 0.8,
                "knowledge_type": "general",
                "topics_covered": ["服装知识"],
                "suggestions": [],
                "related_questions": [],
                "next_action": "continue"
            }

        except Exception:
            return {
                "content": response_content.replace("**", ""),
                "confidence": 0.7,
                "knowledge_type": "general",
                "topics_covered": ["服装知识"],
                "suggestions": [],
                "related_questions": [],
                "next_action": "continue"
            }

    def can_handle(self, message: Message) -> bool:
        """判断是否能处理该消息 - 关键词匹配"""
        content = message.content.lower()
        return any(keyword in content for keyword in self.keywords)

    async def _search_knowledge_products(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """搜索知识相关商品"""
        if not self.product_search_service:
            return self._get_mock_knowledge_products(search_params)
        
        try:
            # 构建搜索关键词
            keyword = self._build_knowledge_search_keyword(search_params)
            
            # 调用搜索服务
            search_result = await self.product_search_service.search_products(
                keyword=keyword,
                page=search_params.get('page', 1),
                page_size=search_params.get('page_size', 6),
                sort=search_params.get('sort', 'total_sales_des'),
                price_min=search_params.get('price_min', 0),
                price_max=search_params.get('price_max', 1000)
            )
            
            return search_result
            
        except Exception as e:
            logger.error(f"知识商品搜索失败: {e}")
            return self._get_mock_knowledge_products(search_params)

    def _build_knowledge_search_keyword(self, search_params: Dict[str, Any]) -> str:
        """构建知识搜索关键词"""
        keyword_parts = []
        
        # 基础关键词
        if search_params.get('keyword'):
            keyword_parts.append(search_params['keyword'])
        
        # 材质关键词
        if search_params.get('material'):
            keyword_parts.append(search_params['material'])
        
        # 类别关键词
        if search_params.get('category'):
            keyword_parts.append(search_params['category'])
        
        # 如果没有关键词，使用默认
        if not keyword_parts:
            keyword_parts.append('优质服装')
        
        return ' '.join(keyword_parts)

    def _build_product_knowledge_prompt(self, message: Message, search_results: Dict[str, Any], knowledge_response: Dict[str, Any]) -> str:
        """构建包含商品推荐的知识提示词（自然语言，不使用JSON）"""
        prompt_parts = [
            KNOWLEDGE_SYSTEM_PROMPT,
            "",
            "## 任务：基于知识建议推荐相关商品",
            f"## 用户问题：{message.content}",
            f"## 之前的知识回答：{knowledge_response.get('content', '')}",
            "",
            "## 搜索到的相关商品：",
        ]
        
        # 处理搜索结果
        if search_results.get('success') and search_results.get('items'):
            products = search_results['items'][:6]  # 最多展示6个商品
            prompt_parts.append(f"找到 {search_results.get('count', len(products))} 个相关商品")
            prompt_parts.append("")
            
            for i, product in enumerate(products, 1):
                prompt_parts.append(f"{i}. {product.get('title', '未知商品')}")
                prompt_parts.append(f"   原价: ¥{product.get('price', '未知')}")
                if product.get('quanhou_jiage'):
                    prompt_parts.append(f"   券后价: ¥{product.get('quanhou_jiage')}")
                if product.get('coupon_info_money'):
                    prompt_parts.append(f"   优惠券: ¥{product.get('coupon_info_money')}")
                prompt_parts.append(f"   品牌: {product.get('brand', '未知')}")
                prompt_parts.append(f"   店铺: {product.get('nick', '未知')}")
                prompt_parts.append(f"   销量: {product.get('volume', '未知')}")
                if product.get('jianjie'):
                    prompt_parts.append(f"   简介: {product.get('jianjie')}")
                prompt_parts.append("")
        else:
            prompt_parts.append("未找到相关商品")
            prompt_parts.append("")
        
        prompt_parts.extend([
            "## 回答要求（务必遵守）：",
            "- 使用纯自然语言，禁止输出JSON或任何代码块。",
            "- 以清晰结构给出：",
            "  1) 简短引导语；",
            "  2) 基于上述商品列表，推荐最相关的2-3件并给出理由；",
            "  3) 选购建议与注意事项（材质/工艺/养护）；",
            "  4) 如涉及购买细节或价格，请建议转接销售智能体。"
        ])

        return "\n".join(prompt_parts)

    def _get_mock_knowledge_products(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """获取模拟知识商品数据"""
        keyword = search_params.get('keyword', '优质服装')
        material = search_params.get('material', '棉质')
        
        mock_items = [
            {
                'title': f'{material}{keyword}',
                'price': '189',
                'quanhou_jiage': '159',
                'brand': '品质品牌',
                'item_url': 'https://example.com/knowledge1',
                'jianjie': f'采用优质{material}材质，品质保证',
                'nick': '品质服装专营店',
                'volume': '600+',
                'coupon_info_money': '30'
            },
            {
                'title': f'高档{material}服装',
                'price': '299',
                'quanhou_jiage': '259',
                'brand': '高端品牌',
                'item_url': 'https://example.com/knowledge2',
                'jianjie': f'精选{material}面料，工艺精良',
                'nick': '高端服装旗舰店',
                'volume': '400+',
                'coupon_info_money': '40'
            },
            {
                'title': f'经典{material}款式',
                'price': '129',
                'quanhou_jiage': '109',
                'brand': '经典品牌',
                'item_url': 'https://example.com/knowledge3',
                'jianjie': f'经典{material}设计，舒适耐穿',
                'nick': '经典服装专营店',
                'volume': '1000+',
                'coupon_info_money': '20'
            }
        ]
        
        return {
            'success': True,
            'count': len(mock_items),
            'items': mock_items,
            'message': f'找到 {len(mock_items)} 个{material}材质相关商品（模拟数据）',
            'search_keyword': f'{keyword} {material}'
        }

    def _update_conversation_memory(self, message: Message, response: Dict[str, Any], context: Dict[str, Any]):
        """更新对话记忆"""
        if "conversation_history" not in context:
            context["conversation_history"] = []
        
        context["conversation_history"].append({
            "user": message.content,
            "assistant": response.get("content", ""),
            "knowledge_type": response.get("knowledge_type", "general"),
            "topics": response.get("topics_covered", [])
        })
        
        # 保持最近10轮对话
        if len(context["conversation_history"]) > 10:
            context["conversation_history"] = context["conversation_history"][-10:]

    def get_system_prompt(self) -> str:
        """获取智能体的系统提示词"""
        return KNOWLEDGE_SYSTEM_PROMPT

    def get_capabilities(self) -> List[str]:
        """获取智能体的核心能力列表"""
        return self.capabilities


# 创建知识智能体的工厂函数
def create_knowledge_agent(llm_client: Any = None, product_search_service: Any = None) -> KnowledgeAgent:
    """创建知识智能体实例"""
    return KnowledgeAgent(llm_client, product_search_service)


__all__ = ["KnowledgeAgent", "create_knowledge_agent"]