# -*- coding: utf-8 -*-
"""
销售智能体 - 基于GPT-4o的智能销售系统
负责产品推荐、需求理解和购买引导
"""
from typing import Dict, Any, List
from agents.base_agent import BaseAgent, Message, AgentResponse, IntentType
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class SalesAgent(BaseAgent):
    """销售智能体 - 智能化版本"""
    
    def __init__(self, agent_id: str = "sales_agent", llm_client=None, config: Dict[str, Any] = None):
        super().__init__(agent_id, "sales", llm_client, config)
        
        # 初始化产品搜索服务
        self.product_search_service = self._init_product_search_service()
        
        # 销售状态跟踪
        self.sales_sessions = {}

    def _init_product_search_service(self):
        """初始化产品搜索服务"""
        try:
            from services.product_search_service import product_search_service
            return product_search_service
        except ImportError:
            logger.warning("无法导入产品搜索服务，将使用模拟数据")
            return None

    def get_system_prompt(self) -> str:
        """获取销售智能体的系统提示词"""
        return f"""你是一个专业的服装销售顾问，专注于购买咨询和商品推荐。

## 核心职责（严格限定）：
1. **购买咨询** - 只处理与购买相关的咨询：价格询问、商品选购、下单指导
2. **产品推荐** - 基于客户需求推荐合适的产品
3. **购买引导** - 协助客户完成购买决策流程

## 严格禁止处理的内容：
- ❌ 订单查询、物流跟踪、退换货处理 → 转给order_agent
- ❌ 面料知识、保养方法、洗涤指导 → 转给knowledge_agent  
- ❌ 穿搭建议、搭配指导、风格推荐 → 转给styling_agent
- ❌ 尺码咨询、尺寸建议、试穿指导 → 转给knowledge_agent

## 销售流程（严格执行）：
1. **需求确认** - 确认客户确实有购买意图
2. **需求收集** - 了解具体需求（服装类型、场合、预算、偏好）
3. **产品搜索** - 调用搜索API查找匹配产品
4. **产品推荐** - 展示推荐产品并详细介绍
5. **购买引导** - 协助客户做出购买决策

## 对话风格：
- 专业热情，专注购买咨询
- 精准推荐，不泛泛而谈
- 耐心解答购买相关问题
- 适时引导完成交易

## 特别注意：
- 只处理明确的购买意图，不要处理其他类型的咨询
- 如果客户咨询非购买问题，明确告知并建议转接相应专业智能体
- 深度理解客户真实购买需求，不要急于推销
- 基于客户反馈调整推荐策略
- 利用真实的产品搜索API提供准确信息
- 始终以客户满意为目标"""

    def get_capabilities(self) -> List[str]:
        """获取销售智能体的核心能力"""
        return [
            "需求分析",
            "产品推荐", 
            "购买咨询",
            "价格解答",
            "库存查询"
        ]

    async def process_message(self, message: Message, context: Dict[str, Any] = None) -> AgentResponse:
        """
        处理用户消息 - 智能销售流程
        """
        try:
            self.status = self.AgentStatus.PROCESSING
            
            # 顺序协作场景：当来自穿搭智能体的建议被传递过来时，直接执行单品解析与商品搜索
            try:
                meta = message.metadata or {}
                src_agent = meta.get("source_agent") or (context or {}).get("source_agent")
                if src_agent == "styling_agent":
                    advice_text = message.content or ""
                    return await self._process_styling_advice_followup(message, advice_text, context or {})
            except Exception:
                pass

            # 转接逻辑交由调度器处理：销售智能体不主动转接到穿搭智能体

            # 强知识意图优先转接到知识智能体（避免销售话术干扰专业解答）
            try:
                if self._has_strong_knowledge_intent(message.content or ""):
                    return AgentResponse(
                        content="我已识别到您是在咨询面料/保养/洗涤等知识问题，已为您切换到知识智能体，由其提供更专业的解答。",
                        confidence=0.92,
                        next_action="transfer",
                        suggested_agents=["knowledge_agent"],
                        metadata={"reason": "strong_knowledge_intent"}
                    )
            except Exception:
                pass

            # 获取或创建销售会话
            session = self._get_or_create_session(message.conversation_id)
            
            # 构建销售提示词
            prompt = self._build_sales_prompt(message, session, context)
            
            # 调用GPT-4o进行智能分析和响应
            response_content = await self._generate_response(prompt)
            
            # 解析响应
            parsed_response = self._parse_sales_response(response_content, session)
            
            # 如果需要搜索产品，调用搜索API
            if parsed_response.get('need_product_search'):
                search_results = await self._search_products(parsed_response.get('search_params', {}))
                if search_results and search_results.get('success'):
                    # 重新生成包含搜索结果的响应
                    product_prompt = self._build_product_display_prompt(message, search_results, session)
                    response_content = await self._generate_response(product_prompt)
                    parsed_response = self._parse_sales_response(response_content, session)
            
            # 更新会话状态
            self._update_session(message.conversation_id, message, parsed_response)
            
            # 创建AgentResponse对象
            agent_response = AgentResponse(
                content=parsed_response.get('content', ''),
                confidence=parsed_response.get('confidence', 0.8),
                next_action=parsed_response.get('next_action'),
                suggested_agents=parsed_response.get('suggested_agents', []),
                requires_human=parsed_response.get('requires_human', False),
                metadata=parsed_response.get('metadata', {})
            )
            
            # 更新对话记忆
            self._update_memory(message, agent_response)
            
            self.status = self.AgentStatus.IDLE
            return agent_response
            
        except Exception as e:
            logger.error(f"销售智能体处理失败: {e}")
            self.status = self.AgentStatus.ERROR
            return AgentResponse(
                content="抱歉，我在处理您的需求时遇到了问题。让我重新为您服务，请告诉我您想要什么类型的服装？",
                confidence=0.6
            )

    async def _process_styling_advice_followup(self, message: Message, advice_text: str, context: Dict[str, Any]) -> AgentResponse:
        """基于穿搭建议解析出单品，并为每个单品搜索真实商品。"""
        try:
            # 解析建议中的单品关键词
            items = self._extract_items_from_styling_advice(advice_text)
            if not items:
                # 无法解析出具体单品，给出引导
                guidance = (
                    "我已收到搭配建议。为便于推荐商品，请告知您更偏好的单品类型，例如：白衬衫/牛仔裤/运动鞋/西装外套等。"
                )
                return AgentResponse(
                    content=guidance,
                    agent_id=self.agent_id,
                    confidence=0.75,
                    next_action="clarify",
                    intent_type=IntentType.SALES_CONSULTATION,
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
                        products = self._get_mock_products({"keyword": item})[:3]
                except Exception as e:
                    logger.warning(f"销售智能体搜索单品失败: {item} - {e}")
                grouped_results[item] = products

            # 格式化输出
            lines: List[str] = [
                "我已根据穿搭建议为每个单品挑选了真实商品，供你快速查看：",
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
                intent_type=IntentType.SALES_CONSULTATION,
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
                content="我收到搭配建议后在推荐商品时遇到问题，请稍后重试或告诉我你更想看的单品类型。",
                agent_id=self.agent_id,
                confidence=0.6,
                next_action="retry",
                intent_type=IntentType.SALES_CONSULTATION,
                metadata={"from_styling": True, "error": str(e)},
            )

    def _extract_items_from_styling_advice(self, text: str) -> List[str]:
        """从穿搭建议文本中提取可能的单品关键词（轻量启发式）。"""
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

    def _get_or_create_session(self, conversation_id: str) -> Dict[str, Any]:
        """获取或创建销售会话"""
        if conversation_id not in self.sales_sessions:
            self.sales_sessions[conversation_id] = {
                'stage': 'greeting',  # greeting, requirement_collection, product_search, recommendation, purchase_guide, satisfaction_inquiry, follow_up
                'requirements': {},
                'recommended_products': [],
                'interaction_count': 0,
                'requirement_collection_count': 0,  # 需求收集轮次计数
                'last_requirement_update': None,    # 最后需求更新时间
                'satisfaction_asked': False,        # 是否已询问满意度
                'satisfaction_response': None,      # 用户满意度回应
                'follow_up_count': 0,               # 跟进次数
                'last_follow_up': None              # 最后跟进时间
            }
        return self.sales_sessions[conversation_id]

    def _build_sales_prompt(self, message: Message, session: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """构建销售提示词"""
        prompt_parts = [
            self.get_system_prompt(),
            "",
            f"## 当前销售阶段：{session['stage']}",
            f"## 已收集需求：{json.dumps(session['requirements'], ensure_ascii=False) if session['requirements'] else '暂无'}",
        ]

        # 如果尚未收集到具体需求，添加强约束，要求先进行需求澄清
        if not session.get('requirements'):
            prompt_parts.append("## 严格约束：当前尚未收集到具体需求，请只进行需求澄清，不要做任何产品推荐或给出解决方案。")
            prompt_parts.append("必须提出具体且可回答的澄清问题，覆盖：服装类型/场合/预算/尺码或常穿尺码/风格或颜色偏好。")
            prompt_parts.append("JSON响应必须设置：\"stage\": \"requirement_collection\", \"need_product_search\": false, \"next_action\": \"continue\"。")
            if context and isinstance(context, dict) and context.get('consultation_mode'):
                prompt_parts.append("可参考支持智能体提供的信息，但仍需先完成需求澄清，禁止直接给出推荐或方案。")
        
        # 需求收集轮次指导：至少需要两轮需求收集才能进行产品搜索
        if session.get('requirement_collection_count', 0) < 2:
            prompt_parts.append(f"## 需求收集进度：已完成 {session.get('requirement_collection_count', 0)}/2 轮需求收集")
            prompt_parts.append("## 搜索约束：必须至少完成两轮需求收集后才能进行产品搜索")
            prompt_parts.append("当前禁止设置 \"need_product_search\": true，必须继续收集更多需求信息")
            prompt_parts.append("请专注于收集以下信息：品牌偏好、材质要求、具体款式、特殊需求等")
        
        # 如果是初次问候阶段，添加自我介绍提示
        if session['stage'] == 'greeting' and session['interaction_count'] == 0:
            prompt_parts.append("## 特别提示：这是与客户的第一次交互，请先进行自我介绍")
            prompt_parts.append("自我介绍内容应包括：")
            prompt_parts.append("- 你的身份：专业的服装销售顾问")
            prompt_parts.append("- 你的专长：服装推荐、价格咨询（不提供穿搭建议）")
            prompt_parts.append("- 服务承诺：个性化推荐、专业建议、热情服务")
            prompt_parts.append("- 引导语：询问客户的具体需求")
            prompt_parts.append("")
            prompt_parts.append("示例：")
            prompt_parts.append('"您好！我是您的专属服装销售顾问，很高兴为您服务。我专注于为您推荐最适合的服装款式，并提供专业的价格咨询（穿搭建议将由穿搭顾问提供）。请问您今天想了解什么类型的服装呢？"')
            prompt_parts.append("")
        
        # 如果是推荐阶段且尚未询问满意度，添加满意度询问提示
        elif session['stage'] == 'recommendation' and session['interaction_count'] >= 3 and not session['satisfaction_asked']:
            prompt_parts.append("## 满意度询问提示：您已完成产品推荐，现在可以询问用户对推荐的满意度")
            prompt_parts.append("可以这样询问：")
            prompt_parts.append('"您对这些推荐还满意吗？如果有任何不满意的地方，或者想要了解其他款式，请随时告诉我！"')
            prompt_parts.append("JSON响应可以设置：\"stage\": \"satisfaction_inquiry\"")
            prompt_parts.append("")
        
        # 添加对话历史
        history = self._get_conversation_history(message.conversation_id)
        if history:
            prompt_parts.append("\n### 对话历史：")
            for item in history[-3:]:  # 保留最近3轮对话
                prompt_parts.append(f"客户: {item['user']}")
                prompt_parts.append(f"销售: {item['assistant']}")
        
        # 添加当前消息和任务
        prompt_parts.extend([
            f"\n## 客户当前消息：",
            message.content,
            "",
            "## 严格职责边界检查（必须执行）：",
            "1. 首先判断消息是否属于销售智能体的职责范围",
            "2. 如果包含以下关键词，说明不属于销售职责，必须转接：",
            "   - 订单相关：订单、物流、发货、收货、退货、退款、售后、退换货、订单号、快递、配送",
            "   - 知识咨询：材质、保养、洗涤、面料、质量、怎么选、什么好、如何清洁、耐用性、成分、特性",
            "   - 穿搭建议：穿搭、搭配、场合、风格、适合、推荐穿、穿衣、着装、造型、配什么、怎么搭",
            "   - 尺码咨询：尺码、尺寸、试穿、大小、合身、测量",
            "3. 如果确定不属于销售职责，必须设置 next_action: 'transfer' 并指定正确的智能体",
            "",
            "## 销售分析任务（仅在确认属于销售职责后执行）：",
            "1. 理解客户当前的购买需求和意图",
            "2. 判断是否需要收集更多需求信息",
            "3. 决定是否需要搜索产品",
            "4. 生成合适的销售响应",
            "5. 在适当的时候询问用户满意度",
            "6. 根据用户反馈进行跟进",
            "",
            "## 满意度询问和跟进指导：",
            "- 当完成产品推荐后，可以询问用户对推荐的满意度",
            "- 如果用户表示满意，可以询问是否需要进一步帮助或推荐其他产品",
            "- 如果用户表示不满意，询问具体原因并提供改进建议",
            "- 对于未回复的用户，可以在适当间隔后进行跟进",
            "",
            "## 响应格式（JSON）：",
            "{",
            '  "content": "你的销售回复（如果转接，请说明转接原因）",',
            '  "confidence": 0.9,',
            '  "stage": "当前阶段：greeting/requirement_collection/product_search/recommendation/purchase_guide/satisfaction_inquiry/follow_up",',
            '  "need_product_search": true/false,',
            '  "search_params": {"keyword": "搜索关键词", "category": "类别", "price_min": 0, "price_max": 1000},',
            '  "requirements_update": {"新收集到的需求信息"},',
            '  "next_action": "continue/search_products/transfer",',
            '  "suggested_agents": ["如需转接其他智能体：order_agent/knowledge_agent/styling_agent"],',
            '  "requires_human": false',
            "}"
        ])
        
        return "\n".join(prompt_parts)

    def _build_product_display_prompt(self, message: Message, search_results: Dict[str, Any], session: Dict[str, Any]) -> str:
        """构建产品展示提示词（图二风格展示 + 销售总结，无破折号）"""
        prompt_parts = [
            self.get_system_prompt(),
            "",
            "## 任务：按“图二风格”先展示产品信息，再输出销售风格总结",
            f"## 客户需求：{json.dumps(session['requirements'], ensure_ascii=False)}",
            f"## 客户消息：{message.content}",
            "",
            "## 展示风格（必须严格遵守）：",
            "- 每个字段前使用合适的emoji标识，不使用破折号或列表符号",
            "- 先输出“产品清单（销售展示）”并分条展示商品的关键信息",
            "- 字段示例：📦 商品、💰 价格、🎁 优惠、🏷️ 品牌、🏪 店铺、📈 销量、📝 简介、🔗 链接",
            "- 每个商品块之间使用一行分隔符：==========================",
            "- 之后输出‘产品特性总结（销售风格）’，像线下导购一样突出优势与优惠",
            "- 严禁在任何输出行首使用 '-' 或 '•' 等符号",
            "",
            "## 搜索到的商品：",
        ]

        # 处理搜索结果（最多6个）
        if search_results.get('success') and search_results.get('items'):
            products = search_results['items'][:6]
            prompt_parts.append(f"找到 {search_results.get('count', len(products))} 个相关商品")
            prompt_parts.append("")
            for i, product in enumerate(products, 1):
                title = product.get('title', '未知商品')
                price = product.get('price')
                sale_price = product.get('quanhou_jiage')
                coupon = product.get('coupon_info_money')
                brand = product.get('brand') or '未知'
                shop = product.get('nick') or '未知'
                volume = product.get('volume')
                desc = product.get('jianjie')
                link = self._resolve_product_link(product)

                prompt_parts.append(f"商品{i}：{title}")
                if price is not None:
                    prompt_parts.append(f"💰 原价：¥{price}")
                if sale_price:
                    prompt_parts.append(f"💳 券后价：¥{sale_price}")
                if coupon:
                    prompt_parts.append(f"🎁 优惠券：¥{coupon}")
                prompt_parts.append(f"🏷️ 品牌：{brand}")
                prompt_parts.append(f"🏪 店铺：{shop}")
                if volume is not None:
                    prompt_parts.append(f"📈 销量：{volume}")
                if desc:
                    prompt_parts.append(f"📝 简介：{desc}")
                if link:
                    prompt_parts.append(f"🔗 链接：{link}")
                prompt_parts.append("==========================")
        else:
            prompt_parts.append("未找到相关商品")
            prompt_parts.append("")

        # 输出总结与推荐的明确指令
        prompt_parts.extend([
            "",
            "## 写作任务：生成‘产品特性总结（销售风格）’",
            "- 用自然口语化的销售话术，针对用户需求总结价格、材质、品质、适用场景等",
            "- 强调价格优势：如果有券后价或优惠券，请明确比较原价与优惠价",
            "- 可引用品牌与销量信息增强可信度（如有）",
            "- 语言简洁有力，避免重复；不要出现任何前缀破折号",
            "- 总结后给出1-2句引导性话术（如：是否需要我帮您对比、看尺码、进店）",
            "",
            "## 响应格式（JSON，仅返回）：",
            "{",
            '  "content": "先是产品清单（图二风格），随后是销售风格总结",',
            '  "confidence": 0.9,',
            '  "stage": "recommendation",',
            '  "recommended_products": [1,2,3],',
            '  "next_action": "continue"',
            "}"
        ])

        return "\n".join(prompt_parts)

    def _has_strong_knowledge_intent(self, content: str) -> bool:
        """简单规则识别强知识咨询意图：材质/保养/洗涤/面料/清洁/耐用性/成分/特性等。"""
        if not content:
            return False
        text = content.strip()
        knowledge_keywords = [
            "材质", "保养", "洗涤", "面料", "质量", "怎么选", "如何选择", "如何清洁", "清洁", "耐用性", "成分", "特性", "护理", "护理方法", "防皱", "防菌", "缩水", "褪色"
        ]
        hits = sum(1 for k in knowledge_keywords if k in text)
        return hits >= 2 or (hits >= 1 and any(x in text for x in ["怎么", "如何", "指南"]))

    def _resolve_product_link(self, product: Dict[str, Any]) -> str:
        """直接返回API返回的原始链接，不进行任何优化。"""
        try:
            # 直接返回item_url，不进行任何优化处理
            return product.get('item_url', '')
        except Exception:
            return ''

    async def _search_products(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """调用产品搜索API - 优化版本，包含重试机制和详细错误处理"""
        if not self.product_search_service:
            logger.warning("产品搜索服务未初始化，使用模拟数据")
            return self._get_mock_search_result(search_params)
        
        # 构建搜索关键词
        keyword = self._build_search_keyword(search_params)
        
        # 添加重试机制
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"尝试产品搜索 (尝试 {attempt + 1}/{max_retries + 1}): {keyword}")
                
                # 调用真实的搜索API
                search_result = await self.product_search_service.search_products(
                    keyword=keyword,
                    page=search_params.get('page', 1),
                    page_size=search_params.get('page_size', 6),
                    sort=search_params.get('sort', 'total_sales_des'),
                    price_min=search_params.get('price_min'),
                    price_max=search_params.get('price_max')
                )
                
                logger.info(f"商品搜索结果: {search_result.get('message', '搜索完成')}")
                
                # 检查搜索结果的有效性
                if search_result.get('success') and search_result.get('items'):
                    logger.info(f"成功找到 {len(search_result['items'])} 个商品")
                    return search_result
                else:
                    logger.warning(f"搜索未找到商品或结果无效: {search_result.get('message')}")
                    if attempt < max_retries:
                        continue  # 重试
                    else:
                        return search_result  # 返回原始结果，即使没有商品
                        
            except Exception as e:
                logger.error(f"产品搜索失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    # 等待一段时间后重试
                    import asyncio
                    await asyncio.sleep(1)
                    continue
                else:
                    # 所有重试都失败，返回模拟数据
                    logger.warning("所有搜索尝试都失败，使用模拟数据")
                    mock_result = self._get_mock_search_result(search_params)
                    mock_result['error_message'] = f"搜索服务暂时不可用: {str(e)}"
                    return mock_result

    def _build_search_keyword(self, search_params: Dict[str, Any]) -> str:
        """构建智能搜索关键词"""
        keywords = []
        
        # 基础关键词
        base_keyword = search_params.get('keyword', '')
        if base_keyword:
            keywords.append(base_keyword)
        
        # 添加类别信息
        category = search_params.get('category', '')
        if category and category not in base_keyword:
            keywords.append(category)
        
        # 添加性别信息
        gender = search_params.get('gender', '')
        if gender and gender not in ' '.join(keywords):
            keywords.append(gender)
        
        # 添加风格偏好
        style = search_params.get('style', '')
        if style and style not in ' '.join(keywords):
            keywords.append(style)
        
        # 构建最终关键词
        final_keyword = ' '.join(keywords) if keywords else '服装'
        logger.info(f"构建的搜索关键词: {final_keyword}")
        return final_keyword

    def _get_mock_search_result(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """获取模拟搜索结果（当搜索API不可用时）"""
        keyword = search_params.get('keyword', '服装')
        mock_items = [
            {
                'title': f'{keyword} - 经典款式',
                'price': '199',
                'quanhou_jiage': '179',
                'brand': '优质品牌',
                'item_url': 'https://example.com/product1',
                'jianjie': '经典设计，品质保证',
                'nick': '优质品牌旗舰店',
                'volume': '1000+',
                'coupon_info_money': '20'
            },
            {
                'title': f'{keyword} - 时尚新款',
                'price': '299',
                'quanhou_jiage': '259',
                'brand': '时尚品牌',
                'item_url': 'https://example.com/product2',
                'jianjie': '时尚设计，潮流首选',
                'nick': '时尚品牌旗舰店',
                'volume': '800+',
                'coupon_info_money': '40'
            },
            {
                'title': f'{keyword} - 性价比之选',
                'price': '99',
                'quanhou_jiage': '89',
                'brand': '实惠品牌',
                'item_url': 'https://example.com/product3',
                'jianjie': '性价比高，物超所值',
                'nick': '实惠品牌专营店',
                'volume': '2000+',
                'coupon_info_money': '10'
            }
        ]
        
        return {
            'success': True,
            'count': len(mock_items),
            'items': mock_items,
            'message': f'找到 {len(mock_items)} 个相关商品（模拟数据）',
            'search_keyword': keyword
        }

    def _get_mock_products(self, search_params: Dict[str, Any]) -> List[Dict]:
        """获取模拟产品数据（当搜索API不可用时）"""
        keyword = search_params.get('keyword', '服装')
        return [
            {
                'title': f'{keyword} - 经典款式',
                'price': '199',
                'brand': '优质品牌',
                'url': 'https://example.com/product1',
                'description': '经典设计，品质保证'
            },
            {
                'title': f'{keyword} - 时尚新款',
                'price': '299',
                'brand': '时尚品牌',
                'url': 'https://example.com/product2',
                'description': '时尚设计，潮流首选'
            },
            {
                'title': f'{keyword} - 性价比之选',
                'price': '99',
                'brand': '实惠品牌',
                'url': 'https://example.com/product3',
                'description': '性价比高，物超所值'
            }
        ]

    def _parse_sales_response(self, response_content: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """解析销售响应，兼容Markdown代码块中的JSON"""
        try:
            # 先清理可能的markdown代码块标记
            cleaned = response_content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]  # 去掉```json
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            elif cleaned.startswith("```") and cleaned.endswith("```"):
                # 普通代码块，尝试去掉并解析
                cleaned = cleaned[3:-3].strip()

            # 尝试解析JSON响应
            if cleaned.startswith('{'):
                parsed = json.loads(cleaned)

                # 更新会话阶段
                if 'stage' in parsed:
                    session['stage'] = parsed['stage']

                # 更新需求信息
                if 'requirements_update' in parsed and parsed['requirements_update']:
                    session['requirements'].update(parsed['requirements_update'])
                    session['last_requirement_update'] = session['interaction_count']
                    # 增加需求收集轮次计数
                    session['requirement_collection_count'] += 1

                # 行为保护：若尚未收集到需求，禁止进入推荐/搜索阶段，强制改为需求澄清
                empty_requirements = not session.get('requirements') or len(session.get('requirements', {})) == 0
                if empty_requirements and parsed.get('stage') in ('recommendation', 'product_search'):
                    parsed['stage'] = 'requirement_collection'
                    parsed['need_product_search'] = False
                    # 若回复缺少澄清问题，补充标准澄清话术
                    default_clarify = (
                        "为了更好地为您推荐，请先告诉我：1) 想要的服装类型或款式；"
                        "2) 使用场合（通勤/约会/旅行等）；3) 预算范围；"
                        "4) 身高体重或常穿尺码；5) 喜好的风格或颜色。"
                    )
                    if not parsed.get('content') or parsed.get('content', '').strip() == '':
                        parsed['content'] = default_clarify
                    parsed['next_action'] = 'continue'

                # 智能搜索触发逻辑：至少完成两轮需求收集后才允许搜索
                if parsed.get('need_product_search') and session['requirement_collection_count'] < 2:
                    logger.info(f"需求收集轮次不足 ({session['requirement_collection_count']}/2)，暂不进行产品搜索")
                    parsed['need_product_search'] = False
                    parsed['stage'] = 'requirement_collection'
                    # 添加继续收集需求的提示
                    if parsed.get('content'):
                        parsed['content'] += "\n\n为了给您更精准的推荐，请再告诉我一些您的偏好：比如喜欢的品牌、材质或者具体的款式要求？"

                # 边界检测与转接由调度器统一处理，不在销售智能体内触发

                # 满意度询问后的跟进逻辑
                if session['stage'] == 'satisfaction_inquiry' and session['satisfaction_response']:
                    if session['satisfaction_response'] == 'positive':
                        # 用户满意，询问是否需要进一步帮助
                        if parsed.get('content'):
                            parsed['content'] += "\n\n很高兴您对推荐满意！需要我为您推荐其他款式或查看更多选项吗？如需穿搭建议，我将为您转接穿搭顾问。"
                    elif session['satisfaction_response'] == 'negative':
                        # 用户不满意，询问具体原因并提供改进
                        if parsed.get('content'):
                            parsed['content'] += "\n\n很抱歉您对推荐不满意。能告诉我具体哪里不满意吗？是款式、价格还是其他方面？我会根据您的反馈重新为您推荐。"
                    # 重置满意度状态以便后续跟进
                    session['satisfaction_response'] = None

                return parsed
            else:
                # 如果不是JSON格式，包装成标准响应
                # 非JSON文本直接按销售流程返回，由调度器负责统一转接判定
                return {
                    'content': cleaned,
                    'confidence': 0.7,
                    'stage': session['stage'],
                    'next_action': 'continue'
                }
        except json.JSONDecodeError:
            return {
                'content': response_content,
                'confidence': 0.6,
                'stage': session['stage'],
                'next_action': 'continue'
            }

    def _update_session(self, conversation_id: str, message: Message, response: Dict[str, Any]):
        """更新销售会话状态"""
        if conversation_id in self.sales_sessions:
            session = self.sales_sessions[conversation_id]
            
            # 先处理用户满意度回应（基于当前会话阶段）
            if session['stage'] == 'satisfaction_inquiry' and message.content:
                # 分析用户对满意度询问的回应
                content_lower = message.content.lower()
                if any(word in content_lower for word in ['满意', '不错', '很好', '喜欢', '可以', '还行']):
                    session['satisfaction_response'] = 'positive'
                    logger.info(f"会话 {conversation_id} - 用户表示满意")
                elif any(word in content_lower for word in ['不满意', '不好', '不喜欢', '不行', '一般', '差点']):
                    session['satisfaction_response'] = 'negative'
                    logger.info(f"会话 {conversation_id} - 用户表示不满意")
                else:
                    session['satisfaction_response'] = 'neutral'
                    logger.info(f"会话 {conversation_id} - 用户回应中性")
            
            # 更新会话状态
            if 'stage' in response:
                session['stage'] = response['stage']
            
            # 处理满意度询问状态
            if response.get('stage') == 'satisfaction_inquiry':
                session['satisfaction_asked'] = True
                session['last_satisfaction_ask'] = datetime.now().isoformat()
                logger.info(f"会话 {conversation_id} - 已询问用户满意度")
            
            # 处理跟进状态
            if response.get('stage') == 'follow_up':
                session['follow_up_count'] = session.get('follow_up_count', 0) + 1
                session['last_follow_up'] = datetime.now().isoformat()
                logger.info(f"会话 {conversation_id} - 跟进次数: {session['follow_up_count']}")
            
            # 更新需求收集计数
            if response.get('stage') == 'requirement_collection':
                session['requirement_collection_count'] += 1
                session['last_requirement_update'] = datetime.now().isoformat()
                logger.info(f"会话 {conversation_id} - 需求收集轮次更新: {session['requirement_collection_count']}")
            
            # 更新推荐产品
            if 'recommended_products' in response:
                session['recommended_products'] = response['recommended_products']
            
            # 更新交互计数
            session['interaction_count'] += 1
            
            logger.info(f"会话 {conversation_id} - 阶段: {session['stage']}, 需求收集: {session['requirement_collection_count']}, 交互: {session['interaction_count']}, 满意度询问: {session.get('satisfaction_asked', False)}, 跟进次数: {session.get('follow_up_count', 0)}")

    def can_handle(self, message: Message, context: Dict[str, Any] = None) -> float:
        """判断是否能处理该消息；强知识意图时主动降低处理分数以便调度切换。"""
        content = (message.content or "")

        # 强知识意图：显著降低置信度，促使路由到知识智能体
        if self._has_strong_knowledge_intent(content):
            return 0.05

        # 销售相关关键词
        sales_keywords = [
            "买", "购买", "推荐", "产品", "商品", "价格", "多少钱",
            "衣服", "服装", "上衣", "裤子", "裙子", "外套", "鞋子",
            "品牌", "款式", "新款", "打折", "优惠", "便宜", "贵"
        ]
        keyword_score = sum(1 for k in sales_keywords if k in content) / max(1, len(sales_keywords))
        return min(0.9, keyword_score * 2 + 0.3)


# 创建销售智能体的工厂函数
def create_sales_agent(agent_id: str = None, config: Dict[str, Any] = None) -> SalesAgent:
    """创建销售智能体实例"""
    if agent_id is None:
        agent_id = "sales_agent"
    return SalesAgent(agent_id, config=config)


__all__ = ["SalesAgent", "create_sales_agent"]