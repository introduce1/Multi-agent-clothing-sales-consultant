"""
穿搭智能体 - 基于GPT-4o的智能服装搭配顾问

主要功能：
1. 个性化穿搭建议和搭配方案
2. 身材分析和服装推荐
3. 场合着装指导
4. 色彩搭配建议
5. 风格定位和形象设计
"""

import json
import logging
from typing import Dict, List, Optional, Any

from .base_agent import BaseAgent, AgentResponse, Message

logger = logging.getLogger(__name__)

# 系统提示词 - 让GPT-4o发挥专业搭配能力
STYLING_SYSTEM_PROMPT = """你是一个专业的服装搭配顾问，拥有丰富的时尚搭配经验和审美能力。

你的核心职责：
1. 个性化搭配：根据用户的身材、肤色、年龄、职业等特点提供个性化穿搭建议
2. 场合着装：为不同场合（工作、约会、聚会、旅行等）推荐合适的服装搭配
3. 风格定位：帮助用户找到适合的穿衣风格（简约、甜美、职业、休闲等）
4. 色彩搭配：提供专业的色彩搭配建议，考虑肤色和季节因素
5. 身材优化：根据身材特点推荐能够扬长避短的服装款式
6. 购买建议：推荐具体的服装单品和搭配组合

专业原则：
- 以用户的实际情况为出发点，提供实用的搭配建议
- 考虑用户的预算、生活方式和个人喜好
- 提供具体、可操作的搭配方案
- 注重整体协调性和实用性
- 鼓励用户发展个人风格，增强自信
- 必要时可以建议用户咨询销售智能体了解具体产品

回答风格：
- 专业而亲切，像一个经验丰富的时尚顾问
- 提供具体的搭配建议和理由说明
- 适当询问用户的具体需求和偏好
- 给出多种搭配选择，让用户有选择空间
- 注重实用性，避免过于理论化的建议
"""


class StylingAgent(BaseAgent):
    """穿搭智能体 - 专业的服装搭配顾问"""
    
    def __init__(self, agent_id: str = "styling_agent", llm_client=None, product_search_service=None, config: Dict[str, Any] = None):
        super().__init__(agent_id, "styling", llm_client, config)
        self.product_search_service = product_search_service
        self.capabilities = [
            "个性化穿搭建议",
            "场合着装指导",
            "身材分析和优化",
            "色彩搭配建议",
            "风格定位指导",
            "服装单品推荐",
            "整体形象设计"
        ]
        # 简化的关键词匹配（仅作为备用），扩展常见风格/场景偏好
        self.keywords = [
            "搭配", "穿搭", "搭配建议", "怎么穿", "穿什么", "搭什么",
            "显瘦", "显高", "身材", "体型", "风格", "时尚", "潮流",
            "约会", "上班", "聚会", "旅行", "婚礼", "面试", "约会装",
            "颜色", "色彩", "配色", "肤色", "显白", "气质", "形象",
            "休闲", "通勤", "正式", "简约", "复古", "法式", "韩系", "日系",
            "商务", "度假", "户外", "运动", "学院风", "街头", "极简",
            "推荐", "购买", "商品", "单品"  # 新增搜索相关关键词
        ]

    def get_system_prompt(self) -> str:
        """获取穿搭智能体的系统提示词"""
        return """你是一个专业的时尚穿搭顾问，专门负责服装搭配和形象设计相关的咨询。

## 核心职责（严格限定）：
1. **个性化穿搭建议** - 根据用户的身材、肤色、风格偏好提供定制化建议
2. **场合着装指导** - 为不同场合（工作、约会、聚会等）推荐合适的穿搭
3. **身材优化建议** - 通过服装搭配帮助用户扬长避短
4. **色彩搭配指导** - 提供专业的色彩搭配建议
5. **风格定位** - 帮助用户找到适合的穿衣风格
6. **搭配推荐** - 推荐具体的服装搭配组合和形象设计方案

## 严格禁止处理以下内容（必须转接）：
- **订单查询** - 关于订单状态、物流信息 → 转接订单智能体
- **购买咨询** - 关于商品购买、价格优惠 → 转接销售智能体
- **知识咨询** - 关于面料知识、洗涤保养 → 转接知识智能体
- **尺寸咨询** - 关于尺码选择、尺寸问题 → 转接销售智能体

## 边界检查规则：
当客户咨询包含以下关键词时，必须转接到相应智能体：
- 订单智能体：订单、快递、物流、发货、收货、配送
- 销售智能体：购买、价格、优惠、推荐、商品咨询、尺码
- 知识智能体：面料、材质、洗涤、保养、成分

## 专业能力：
- 深度理解时尚趋势和经典搭配原则
- 精通色彩理论和身材比例优化
- 熟悉各种风格特点和适用场合
- 能够提供实用且美观的搭配方案
- 遇到非穿搭相关问题，立即转接到相应智能体

## 对话风格：
- 专业而亲切，像一个经验丰富的时尚顾问
- 提供具体的搭配建议和理由说明
- 适当询问用户的具体需求和偏好
- 给出多种搭配选择，让用户有选择空间
- 注重实用性，避免过于理论化的建议"""

    def get_capabilities(self) -> List[str]:
        """获取穿搭智能体的核心能力"""
        return [
            "个性化穿搭建议",
            "场合着装指导", 
            "身材分析和优化",
            "色彩搭配建议",
            "风格定位指导",
            "服装单品推荐",
            "整体形象设计",
            "搭配商品推荐"
        ]
        
        # 简化的关键词匹配（仅作为备用）
        self.keywords = [
            "搭配", "穿搭", "搭配建议", "怎么穿", "穿什么", "搭什么",
            "显瘦", "显高", "身材", "体型", "风格", "时尚", "潮流",
            "约会", "上班", "聚会", "旅行", "婚礼", "面试", "约会装",
            "颜色", "色彩", "配色", "肤色", "显白", "气质", "形象",
            "推荐", "购买", "商品", "单品"  # 新增搜索相关关键词
        ]

    async def process_message(self, message: Message, context: Dict[str, Any] = None) -> AgentResponse:
        """处理用户消息 - 智能穿搭建议"""
        try:
            # 构建穿搭咨询提示词
            styling_prompt = self._build_styling_prompt(message, context or {})
            
            # 使用GPT-4o进行智能分析和建议
            response_content = await self._generate_styling_response(styling_prompt)
            
            # 解析响应
            parsed_response = self._parse_response(response_content)

            # 移除自动商品搜索与附加逻辑，改由销售智能体在顺序协作中完成
            # 现在穿搭智能体仅输出专业的穿搭建议与搭配思路，不再直接追加商品列表。
            
            # 更新对话记忆
            self._update_conversation_memory(message, parsed_response, context or {})
            
            return AgentResponse(
                content=parsed_response.get("content", "我会为您提供专业的穿搭建议，让您更加自信美丽。"),
                agent_id=self.agent_id,
                confidence=parsed_response.get("confidence", 0.8),
                next_action=parsed_response.get("next_action", "continue"),
                metadata={
                    "styling_type": parsed_response.get("styling_type", "general"),
                    "occasion": parsed_response.get("occasion", ""),
                    "style_suggestions": parsed_response.get("style_suggestions", []),
                    "color_recommendations": parsed_response.get("color_recommendations", []),
                    "body_type_tips": parsed_response.get("body_type_tips", []),
                    "outfit_ideas": parsed_response.get("outfit_ideas", []),
                    "recommended_products": parsed_response.get("recommended_products", [])  # 新增商品推荐
                }
            )
            
        except Exception as e:
            logger.error(f"穿搭智能体处理消息失败: {e}")
            return AgentResponse(
                content="抱歉，我在为您提供穿搭建议时遇到了困难。请重新描述您的穿搭需求，我会尽力为您提供专业的搭配建议。",
                agent_id=self.agent_id,
                confidence=0.3,
                next_action="retry"
            )

    def _build_styling_prompt(self, message: Message, context: Dict[str, Any]) -> str:
        """构建穿搭咨询提示词"""
        # 获取对话历史
        conversation_history = context.get("conversation_history", [])
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-3:]  # 最近3轮对话
            history_text = "\n".join([
                f"用户: {h.get('user', '')}\n助手: {h.get('assistant', '')}" 
                for h in recent_history if h.get('user') and h.get('assistant')
            ])

        # 解析用户偏好信号（风格/场景等），用于提示词定向
        prefs = self._extract_preferences(message.content or "")
        pref_text_parts = []
        if prefs.get("style"):
            pref_text_parts.append(f"风格偏好：{prefs['style']}")
        if prefs.get("occasion"):
            pref_text_parts.append(f"场合：{prefs['occasion']}")
        pref_text = ("\n" + "；".join(pref_text_parts)) if pref_text_parts else ""
        
        # 构建完整提示词（自然语言输出，禁止JSON）
        prompt = f"""
作为专业的服装搭配顾问，请分析用户的穿搭需求并提供专业建议。

## 边界检查规则（必须严格遵守）：
- 如果用户咨询包含以下关键词，必须转接到相应智能体：
  *订单相关*：订单、快递、物流、发货、收货、配送 → 转接订单智能体
  *购买相关*：购买、价格、优惠、推荐、商品咨询、尺码 → 转接销售智能体  
  *知识相关*：面料、材质、洗涤、保养、成分 → 转接知识智能体

用户需求：{message.content}{pref_text}

{f"对话历史：{history_text}" if history_text else ""}

请用自然语言直接给出建议，不要使用代码块或JSON。输出要求：
- 先简短总结穿搭思路（1–2句）
- 给出3–5条可执行的具体建议（分点列出）
- 如涉及场合或风格，明确说明适用场景与理由
- 如有身材或色彩关注点，给出优化建议与配色参考
- 最后一行用一句话邀请用户补充偏好或预算
"""
        return prompt

    def _extract_preferences(self, text: str) -> Dict[str, Any]:
        """轻量解析用户偏好：识别常见风格与场景关键词"""
        t = (text or "").lower()
        styles = [
            ("休闲", "休闲"), ("通勤", "通勤"), ("正式", "正式"), ("简约", "简约"), ("极简", "极简"),
            ("复古", "复古"), ("法式", "法式"), ("韩系", "韩系"), ("日系", "日系"), ("街头", "街头"),
            ("学院风", "学院风"), ("商务", "商务"), ("运动", "运动")
        ]
        occasions = [
            ("上班", "通勤/上班"), ("职场", "通勤/上班"), ("约会", "约会"), ("聚会", "聚会"),
            ("旅行", "旅行"), ("婚礼", "婚礼"), ("面试", "面试"), ("晚宴", "晚宴")
        ]
        style = next((val for key, val in styles if key in t), "")
        occasion = next((val for key, val in occasions if key in t), "")
        return {"style": style, "occasion": occasion}

    async def _generate_styling_response(self, prompt: str) -> str:
        """使用GPT-4o生成穿搭建议"""
        if not self.llm_client:
            return self._fallback_styling_response()
        
        try:
            messages = [
                {"role": "system", "content": STYLING_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
            
            # 使用统一的智能体响应接口，自动选择模型并返回文本内容
            llm_response = await self.llm_client.get_agent_response(
                agent_name=self.agent_id,
                messages=messages,
                context_info={"agent_type": "styling"}
            )
            return llm_response.content or self._fallback_styling_response()
            
        except Exception as e:
            logger.error(f"GPT-4o穿搭建议生成失败: {e}")
            return self._fallback_styling_response()

    def _fallback_styling_response(self) -> str:
        """备用穿搭建议"""
        return json.dumps({
            "content": "我是专业的服装搭配顾问，可以为您提供个性化的穿搭建议。请告诉我您的身材特点、喜欢的风格、需要搭配的场合，我会为您量身定制搭配方案！",
            "confidence": 0.6,
            "styling_type": "general",
            "occasion": "",
            "style_suggestions": ["请描述您的具体需求"],
            "color_recommendations": ["根据肤色选择合适颜色"],
            "body_type_tips": ["了解身材特点很重要"],
            "outfit_ideas": ["我会为您提供多种搭配方案"],
            "next_action": "ask_details"
        }, ensure_ascii=False)

    def _parse_response(self, response_content: str) -> Dict[str, Any]:
        """解析GPT-4o的响应，兼容Markdown代码块中的JSON"""
        try:
            cleaned = response_content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            elif cleaned.startswith("```") and cleaned.endswith("```"):
                cleaned = cleaned[3:-3].strip()
            cleaned = cleaned.replace("**", "")

            # 尝试解析JSON
            if cleaned.startswith('{'):
                return json.loads(cleaned)

            # 如果不是JSON格式，提取内容
            return {
                "content": cleaned,
                "confidence": 0.7,
                "styling_type": "general",
                "occasion": "",
                "style_suggestions": [],
                "color_recommendations": [],
                "body_type_tips": [],
                "outfit_ideas": [],
                "next_action": "continue"
            }

        except json.JSONDecodeError:
            return {
                "content": response_content.replace("**", ""),
                "confidence": 0.7,
                "styling_type": "general",
                "occasion": "",
                "style_suggestions": [],
                "color_recommendations": [],
                "body_type_tips": [],
                "outfit_ideas": [],
                "next_action": "continue"
            }

    def can_handle(self, message: Message) -> bool:
        """判断是否能处理该消息 - 关键词匹配"""
        content = message.content.lower()
        return any(keyword in content for keyword in self.keywords)

    async def _search_styling_products(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """搜索搭配相关商品"""
        if not self.product_search_service:
            return self._get_mock_styling_products(search_params)
        
        try:
            # 构建搜索关键词
            keyword = self._build_styling_search_keyword(search_params)
            
            # 调用搜索服务
            search_result = await self.product_search_service.search_products(
                keyword=keyword,
                page=search_params.get('page', 1),
                page_size=search_params.get('page_size', 8),
                sort=search_params.get('sort', 'total_sales_des'),
                price_min=search_params.get('price_min', 0),
                price_max=search_params.get('price_max', 1000)
            )
            
            return search_result
            
        except Exception as e:
            logger.error(f"搭配商品搜索失败: {e}")
            return self._get_mock_styling_products(search_params)

    def _build_styling_search_keyword(self, search_params: Dict[str, Any]) -> str:
        """构建搭配搜索关键词"""
        keyword_parts = []
        
        # 基础关键词
        if search_params.get('keyword'):
            keyword_parts.append(search_params['keyword'])
        
        # 风格关键词
        if search_params.get('style'):
            keyword_parts.append(search_params['style'])
        
        # 场合关键词
        if search_params.get('occasion'):
            keyword_parts.append(search_params['occasion'])
        
        # 类别关键词
        if search_params.get('category'):
            keyword_parts.append(search_params['category'])
        
        # 如果没有关键词，使用默认
        if not keyword_parts:
            keyword_parts.append('时尚服装')
        
        return ' '.join(keyword_parts)

    def _build_product_styling_prompt(self, message: Message, search_results: Dict[str, Any], styling_response: Dict[str, Any]) -> str:
        """构建包含商品推荐的穿搭提示词（自然语言）"""
        prompt_parts = [
            STYLING_SYSTEM_PROMPT,
            "",
            "## 任务：基于搭配建议推荐具体商品",
            f"## 用户需求：{message.content}",
            f"## 之前的搭配建议：{styling_response.get('content', '')}",
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
            "## 输出要求：",
            "- 用自然语言列出2–4款更契合的商品并简述推荐理由",
            "- 每款商品说明与整体搭配的呼应点（颜色/版型/风格）",
            "- 给出1–2套具体穿搭组合示例",
            "- 不使用代码块或JSON",
        ])
        
        return "\n".join(prompt_parts)

    def _extract_items_from_styling_advice(self, text: str) -> List[str]:
        """从穿搭建议文本中提取可能的单品关键词（轻量启发式）。
        迁移自销售智能体，现由穿搭智能体维护与使用。
        """
        if not text:
            return []
        text_lower = text.lower()
        # 常见服饰关键词（可根据需要扩展）
        keywords = [
            "白衬衫", "衬衫", "牛仔裤", "运动鞋", "西装外套", "外套", "西装",
            "尖头鞋", "高跟鞋", "乐福鞋", "短靴", "长靴", "半身裙", "裙子",
            "针织开衫", "开衫", "毛衣", "马甲", "风衣", "大衣", "t恤", "卫衣",
            "珍珠耳环", "耳环", "腰带", "手袋", "包包", "休闲裤", "西裤", "阔腿裤",
        ]
        found: List[str] = []
        for k in keywords:
            if k in text_lower:
                found.append(k)
        # 去重并保留原始顺序
        deduped = []
        for k in found:
            if k not in deduped:
                deduped.append(k)
        return deduped

    async def _process_styling_advice_followup(self, message: Message, advice_text: str, context: Dict[str, Any]) -> AgentResponse:
        """基于穿搭建议解析出单品，并为每个单品搜索真实商品（由穿搭智能体执行）。"""
        try:
            # 解析建议中的单品关键词
            items = self._extract_items_from_styling_advice(advice_text)
            if not items:
                guidance = (
                    "我已记录搭配建议。为便于推荐商品，请告诉我更偏好的单品类型，例如：白衬衫/牛仔裤/运动鞋/西装外套等。"
                )
                return AgentResponse(
                    content=guidance,
                    agent_id=self.agent_id,
                    confidence=0.75,
                    next_action="clarify",
                    intent_type=IntentType.STYLE_ADVICE,
                    metadata={
                        "from_styling": True,
                        "parsed_items": [],
                        "source_agent": "styling_agent",
                    },
                )

            # 为每个单品搜索商品
            grouped_results: Dict[str, List[Dict[str, Any]]] = {}
            for item in items[:6]:
                products = []
                try:
                    if self.product_search_service:
                        search_result = await self.product_search_service.search_products(
                            keyword=item,
                            page=1,
                            page_size=3,
                            sort="total_sales_des",
                        )
                        products = (search_result or {}).get("items", [])
                    else:
                        products = self._get_mock_styling_products({"keyword": item}).get("items", [])[:3]
                except Exception as e:
                    logger.warning(f"穿搭智能体搜索单品失败: {item} - {e}")
                grouped_results[item] = products

            # 格式化输出
            lines: List[str] = [
                "我已根据搭配建议为每个单品挑选了真实商品，供你快速查看：",
            ]

            for idx, (item, products) in enumerate(grouped_results.items(), start=1):
                lines.append(f"{idx}. {item}")
                if products:
                    if self.product_search_service and hasattr(self.product_search_service, "format_product_display"):
                        display = self.product_search_service.format_product_display(
                            products,
                            requirements={"search_keyword": item, "price_range": "不限"}
                        )
                        lines.append(display)
                    else:
                        for i, p in enumerate(products, start=1):
                            price = p.get("quanhou_jiage") or p.get("price")
                            link = p.get("item_url") or p.get("search_url")
                            title = p.get("title") or p.get("name") or "未知商品"
                            lines.append(f"   - {i}. {title} | 价格: ¥{price} | 链接: {link}")
                else:
                    lines.append("   - 暂未检索到合适商品，可尝试调整关键词")

            lines.append("如果你对其中某款感兴趣，我可以进一步对比或寻找同类款式。")

            content = "\n".join(lines)
            return AgentResponse(
                content=content,
                agent_id=self.agent_id,
                confidence=0.85,
                next_action="continue",
                intent_type=IntentType.STYLE_ADVICE,
                metadata={
                    "from_styling": True,
                    "parsed_items": items,
                    "grouped_recommendations": grouped_results,
                    "source_agent": "styling_agent",
                },
            )
        except Exception as e:
            logger.error(f"穿搭建议跟进处理失败: {e}")
            return AgentResponse(
                content="我在根据搭配建议推荐商品时遇到问题，请稍后重试或告诉我你更想看的单品类型。",
                agent_id=self.agent_id,
                confidence=0.6,
                next_action="retry",
                intent_type=IntentType.STYLE_ADVICE,
                metadata={"from_styling": True, "error": str(e)},
            )

    def _infer_search_params(self, content: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """基于用户文本与建议内容推断搜索参数（轻量启发式）"""
        kw = self._infer_keyword_from_message(content) or self._infer_keyword_from_message(parsed.get('content',''))
        if not kw:
            return {}
        return {
            'keyword': kw,
            'page': 1,
            'page_size': 6,
            'sort': 'total_sales_des'
        }

    def _infer_keyword_from_message(self, text: str) -> Optional[str]:
        """从文本中提取适合的商品搜索关键词"""
        if not text:
            return None
        t = text.lower()
        candidates = [
            ('白衬衫','白衬衫'), ('衬衫','衬衫'), ('t恤','T恤'), ('卫衣','卫衣'), ('毛衣','毛衣'),
            ('针织衫','针织衫'), ('连衣裙','连衣裙'), ('半身裙','半身裙'), ('牛仔裤','牛仔裤'),
            ('休闲裤','休闲裤'), ('西装外套','西装外套'), ('风衣','风衣'), ('大衣','大衣'),
            ('运动鞋','运动鞋'), ('高跟鞋','高跟鞋'), ('乐福鞋','乐福鞋'), ('小白鞋','小白鞋'),
            ('手提包','手提包'), ('斜挎包','斜挎包'), ('腰带','腰带'), ('项链','项链')
        ]
        # 选择最先匹配到的关键词
        for key, val in candidates:
            if key in t:
                return val
        # 颜色+品类的简单组合
        colors = ['白色','黑色','米色','卡其','灰色','蓝色','粉色','红色','绿色']
        items = ['衬衫','T恤','卫衣','毛衣','连衣裙','半身裙','牛仔裤','休闲裤','外套']
        chosen_color = next((c for c in colors if c in text), None)
        chosen_item = next((i for i in items if i in text), None)
        if chosen_item:
            return f"{chosen_color or ''}{chosen_item}".strip()
        return None

    def _get_mock_styling_products(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """获取模拟搭配商品数据"""
        keyword = search_params.get('keyword', '时尚服装')
        style = search_params.get('style', '休闲')
        
        mock_items = [
            {
                'title': f'{keyword} {style}风格上衣',
                'price': '159',
                'quanhou_jiage': '139',
                'brand': '时尚品牌',
                'item_url': 'https://example.com/styling1',
                'jianjie': f'适合{style}风格搭配的时尚上衣',
                'nick': '时尚搭配专营店',
                'volume': '500+',
                'coupon_info_money': '20'
            },
            {
                'title': f'{keyword} {style}风格下装',
                'price': '199',
                'quanhou_jiage': '169',
                'brand': '搭配品牌',
                'item_url': 'https://example.com/styling2',
                'jianjie': f'完美搭配{style}风格的下装',
                'nick': '搭配专家旗舰店',
                'volume': '800+',
                'coupon_info_money': '30'
            },
            {
                'title': f'{keyword} {style}风格配饰',
                'price': '89',
                'quanhou_jiage': '79',
                'brand': '配饰品牌',
                'item_url': 'https://example.com/styling3',
                'jianjie': f'提升{style}风格整体效果的配饰',
                'nick': '配饰精选店',
                'volume': '300+',
                'coupon_info_money': '10'
            }
        ]
        
        return {
            'success': True,
            'count': len(mock_items),
            'items': mock_items,
            'message': f'找到 {len(mock_items)} 个{style}风格搭配商品（模拟数据）',
            'search_keyword': f'{keyword} {style}'
        }

    def _update_conversation_memory(self, message: Message, response: Dict[str, Any], context: Dict[str, Any]):
        """更新对话记忆"""
        if "conversation_history" not in context:
            context["conversation_history"] = []
        
        context["conversation_history"].append({
            "user": message.content,
            "assistant": response.get("content", ""),
            "styling_type": response.get("styling_type", "general"),
            "occasion": response.get("occasion", ""),
            "suggestions": response.get("style_suggestions", [])
        })
        
        # 保持最近10轮对话
        if len(context["conversation_history"]) > 10:
            context["conversation_history"] = context["conversation_history"][-10:]


def create_styling_agent(llm_client: Any = None, product_search_service: Any = None) -> StylingAgent:
    """创建穿搭智能体工厂函数"""
    return StylingAgent(llm_client, product_search_service)