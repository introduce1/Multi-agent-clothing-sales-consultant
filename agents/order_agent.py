# -*- coding: utf-8 -*-
"""
订单智能体 - 基于GPT-4o的智能订单管理系统
负责订单查询、处理和售后服务
"""
from typing import Dict, Any, List
from agents.base_agent import BaseAgent, Message, AgentResponse, IntentType
import logging
import json
import re

logger = logging.getLogger(__name__)


class OrderAgent(BaseAgent):
    """订单智能体 - 智能化版本"""
    
    def __init__(self, agent_id: str = "order_agent", llm_client=None, config: Dict[str, Any] = None):
        super().__init__(agent_id, "order", llm_client, config)
        
        # 初始化订单服务
        self.order_service = self._init_order_service()
        
        # 订单会话跟踪
        self.order_sessions = {}

    def _init_order_service(self):
        """初始化订单服务"""
        try:
            from services.order_service import order_service
            return order_service
        except ImportError:
            logger.warning("无法导入订单服务，将使用模拟数据")
            return None

    def get_system_prompt(self) -> str:
        """获取订单智能体的系统提示词"""
        return f"""你是一个专业的订单管理专员，专门负责订单相关的查询和处理。

## 核心职责（严格限定）：
1. **订单查询** - 帮助客户查询订单状态、详情和物流信息
2. **订单处理** - 协助处理订单修改、取消、退款等操作
3. **物流跟踪** - 提供物流配送状态和预计送达时间
4. **售后服务** - 处理退换货、投诉等售后问题

## 严格禁止处理以下内容（必须转接）：
- **产品咨询** - 关于商品功能、材质、尺寸等问题 → 转接销售智能体
- **穿搭建议** - 关于服装搭配、风格建议 → 转接穿搭智能体
- **知识咨询** - 关于面料知识、洗涤保养 → 转接知识智能体
- **购买咨询** - 关于商品购买、价格优惠 → 转接销售智能体

## 服务流程：
1. **身份确认** - 通过订单号或手机号确认客户身份
2. **需求理解** - 准确理解客户的订单相关需求
3. **信息查询** - 调用订单系统获取准确信息（当前为模拟数据）
4. **问题解决** - 提供解决方案或转接相关部门

## 边界检查规则：
当客户咨询包含以下关键词时，必须转接到相应智能体：
- 销售智能体：购买、价格、优惠、推荐、商品咨询
- 穿搭智能体：搭配、风格、场合、颜色、体型
- 知识智能体：面料、材质、洗涤、保养、成分

## 模拟环境说明：
- 当前运行在演示模式下，订单数据为模拟生成
- 对于订单查询，会生成合理的模拟订单信息
- 请自然地处理客户请求，就像处理真实订单一样

## 对话风格：
- 专业耐心，细致周到
- 准确高效，及时响应
- 主动关怀，超越期待
- 问题导向，解决为先

## 特别注意：
- 保护客户隐私，确认身份后再提供详细信息
- 准确理解客户需求，避免误解
- 及时更新订单状态，保持信息同步
- 遇到非订单相关问题，立即转接到相应智能体
- 在模拟环境中，可以生成合理的订单信息来帮助客户"""

    def get_capabilities(self) -> List[str]:
        """获取订单智能体的核心能力"""
        return [
            "订单查询",
            "物流跟踪", 
            "订单修改",
            "退换货处理",
            "售后服务"
        ]

    async def process_message(self, message: Message, context: Dict[str, Any] = None) -> AgentResponse:
        """
        处理用户消息 - 智能订单服务流程
        """
        try:
            self.status = self.AgentStatus.PROCESSING
            
            # 获取或创建订单会话
            session = self._get_or_create_session(message.conversation_id)
            
            # 构建订单处理提示词
            prompt = self._build_order_prompt(message, session, context)
            
            # 调用GPT-4o进行智能分析和响应
            response_content = await self._generate_response(prompt)
            
            # 解析响应
            parsed_response = self._parse_order_response(response_content, session)
            
            # 如果需要查询订单，调用订单API（模拟）
            if parsed_response.get('need_order_query'):
                order_info = await self._query_order(parsed_response.get('query_params', {}))
                if order_info:
                    # 重新生成包含订单信息的响应
                    order_prompt = self._build_order_info_prompt(message, order_info, session)
                    response_content = await self._generate_response(order_prompt)
                    parsed_response = self._parse_order_response(response_content, session)
            
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
            logger.error(f"订单智能体处理失败: {e}")
            self.status = self.AgentStatus.ERROR
            return AgentResponse(
                content="抱歉，我在处理您的订单需求时遇到了问题。请提供您的订单号，我来帮您查询。",
                confidence=0.6
            )

    def _get_or_create_session(self, conversation_id: str) -> Dict[str, Any]:
        """获取或创建订单会话"""
        if conversation_id not in self.order_sessions:
            self.order_sessions[conversation_id] = {
                'stage': 'greeting',  # greeting, identity_verification, order_query, problem_solving, service_completion
                'customer_info': {},
                'order_info': {},
                'interaction_count': 0
            }
        return self.order_sessions[conversation_id]

    def _build_order_prompt(self, message: Message, session: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """构建订单处理提示词"""
        prompt_parts = [
            self.get_system_prompt(),
            "",
            f"## 当前服务阶段：{session['stage']}",
            f"## 客户信息：{json.dumps(session['customer_info'], ensure_ascii=False) if session['customer_info'] else '暂无'}",
            f"## 订单信息：{json.dumps(session['order_info'], ensure_ascii=False) if session['order_info'] else '暂无'}",
        ]
        
        # 添加对话历史
        history = self._get_conversation_history(message.conversation_id)
        if history:
            prompt_parts.append("\n### 对话历史：")
            for item in history[-3:]:  # 保留最近3轮对话
                prompt_parts.append(f"客户: {item['user']}")
                prompt_parts.append(f"客服: {item['assistant']}")
        
        # 添加当前消息和任务
        prompt_parts.extend([
            f"\n## 客户当前消息：",
            message.content,
            "",
            "## 边界检查（重要）：",
            "请严格检查客户消息是否属于订单智能体的职责范围。如果包含以下内容，必须转接到相应智能体：",
            "- 购买咨询、商品推荐、价格优惠 → 转接销售智能体",
            "- 服装搭配、风格建议、场合穿着 → 转接穿搭智能体", 
            "- 面料知识、洗涤保养、材质成分 → 转接知识智能体",
            "- 尺寸咨询、尺码建议 → 转接销售智能体",
            "",
            "## 分析任务：",
            "1. 首先进行边界检查，判断是否属于订单智能体职责",
            "2. 如果不属于订单职责，立即转接到相应智能体",
            "3. 如果属于订单职责，理解客户的订单相关需求",
            "4. 判断是否需要验证客户身份",
            "5. 决定是否需要查询订单信息",
            "6. 生成合适的客服响应",
            "",
            "## 响应格式（JSON）：",
            "{",
            '  "content": "你的客服回复",',
            '  "confidence": 0.9,',
            '  "stage": "当前阶段：greeting/identity_verification/order_query/problem_solving/service_completion",',
            '  "need_order_query": true/false,',
            '  "query_params": {"order_number": "订单号", "phone": "手机号"},',
            '  "customer_info_update": {"新收集到的客户信息"},',
            '  "next_action": "continue/query_order/transfer/escalate",',
            '  "suggested_agents": ["如需转接其他智能体"],',
            '  "requires_human": false,',
            '  "transfer_reason": "如果需要转接，说明转接原因"',
            "}"
        ])
        
        return "\n".join(prompt_parts)

    def _build_order_info_prompt(self, message: Message, order_info: Dict, session: Dict[str, Any]) -> str:
        """构建包含订单信息的提示词"""
        prompt_parts = [
            self.get_system_prompt(),
            "",
            "## 任务：基于查询到的订单信息回复客户",
            f"## 客户消息：{message.content}",
            f"## 客户信息：{json.dumps(session['customer_info'], ensure_ascii=False)}",
            "",
            "## 订单信息：",
        ]
        
        # 格式化订单信息
        if order_info.get('orders'):
            for i, order in enumerate(order_info['orders'], 1):
                prompt_parts.append(f"订单 {i}:")
                prompt_parts.append(f"  订单号: {order.get('order_number', '未知')}")
                prompt_parts.append(f"  状态: {order.get('status', '未知')}")
                prompt_parts.append(f"  商品: {order.get('product_name', '未知')}")
                prompt_parts.append(f"  金额: ¥{order.get('amount', '未知')}")
                prompt_parts.append(f"  下单时间: {order.get('create_time', '未知')}")
                if order.get('logistics_info'):
                    prompt_parts.append(f"  物流信息: {order['logistics_info']}")
                prompt_parts.append("")
        else:
            prompt_parts.append("未找到相关订单信息")
        
        prompt_parts.extend([
            "## 要求：",
            "1. 基于订单信息回答客户问题",
            "2. 如果有问题需要处理，提供解决方案",
            "3. 保持专业和耐心的服务态度",
            "",
            "## 响应格式（JSON）：",
            "{",
            '  "content": "基于订单信息的回复",',
            '  "confidence": 0.9,',
            '  "stage": "problem_solving",',
            '  "next_action": "continue"',
            "}"
        ])
        
        return "\n".join(prompt_parts)

    async def _query_order(self, query_params: Dict[str, Any]) -> Dict:
        """调用订单查询API"""
        if not self.order_service:
            return self._get_mock_order_info(query_params)
        
        try:
            # 调用真实的订单API
            if query_params.get('order_number'):
                result = await self.order_service.get_order_by_number(query_params['order_number'])
            elif query_params.get('phone'):
                result = await self.order_service.get_orders_by_phone(query_params['phone'])
            else:
                return None
            
            return result
        except Exception as e:
            logger.error(f"订单查询失败: {e}")
            return self._get_mock_order_info(query_params)

    def _get_mock_order_info(self, query_params: Dict[str, Any]) -> Dict:
        """获取模拟订单数据（当订单API不可用时）"""
        import random
        from datetime import datetime, timedelta
        
        order_number = query_params.get('order_number', f'202312{random.randint(10, 31):02d}{random.randint(1000, 9999)}')
        phone = query_params.get('phone', f'138{random.randint(1000, 9999)}{random.randint(1000, 9999)}')
        
        # 随机生成订单状态和商品
        statuses = ['已下单', '已付款', '已发货', '配送中', '已送达', '已完成']
        products = [
            {'name': '时尚休闲T恤', 'price': '199.00', 'color': '白色', 'size': 'M'},
            {'name': '牛仔裤', 'price': '299.00', 'color': '蓝色', 'size': 'L'},
            {'name': '运动鞋', 'price': '599.00', 'color': '黑色', 'size': '42'},
            {'name': '连衣裙', 'price': '399.00', 'color': '粉色', 'size': 'S'},
            {'name': '羽绒服', 'price': '899.00', 'color': '深蓝', 'size': 'XL'}
        ]
        
        selected_product = random.choice(products)
        status = random.choice(statuses)
        
        # 根据状态生成相应的物流信息
        logistics_messages = {
            '已下单': '订单已提交，正在处理中',
            '已付款': '付款成功，商品正在准备发货',
            '已发货': '商品已发货，物流单号：SF1234567890',
            '配送中': '您的包裹正在配送中，预计今日送达',
            '已送达': '包裹已送达，感谢您的购买',
            '已完成': '订单已完成，如有问题请联系客服'
        }
        
        # 生成订单时间（最近30天内）
        days_ago = random.randint(1, 30)
        order_time = datetime.now() - timedelta(days=days_ago)
        
        return {
            'success': True,
            'orders': [
                {
                    'order_number': order_number,
                    'status': status,
                    'product_name': selected_product['name'],
                    'product_details': f"{selected_product['color']} {selected_product['size']}",
                    'amount': selected_product['price'],
                    'create_time': order_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'logistics_info': logistics_messages[status],
                    'phone': phone,
                    'delivery_address': '北京市朝阳区xxx街道xxx号',
                    'estimated_delivery': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d') if status in ['已发货', '配送中'] else None
                }
            ]
        }

    def _parse_order_response(self, response_content: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """解析订单响应"""
        try:
            # 清理响应内容，移除markdown代码块标记
            cleaned_content = response_content.strip()
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content[7:]  # 移除 ```json
            if cleaned_content.endswith('```'):
                cleaned_content = cleaned_content[:-3]  # 移除 ```
            cleaned_content = cleaned_content.strip()
            
            # 尝试解析JSON响应
            if cleaned_content.startswith('{'):
                parsed = json.loads(cleaned_content)
                
                # 更新会话阶段
                if 'stage' in parsed:
                    session['stage'] = parsed['stage']
                
                # 更新客户信息
                if 'customer_info_update' in parsed and parsed['customer_info_update']:
                    session['customer_info'].update(parsed['customer_info_update'])
                
                return parsed
            else:
                # 如果不是JSON格式，包装成标准响应
                return {
                    'content': response_content,
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
        """更新订单会话状态"""
        if conversation_id in self.order_sessions:
            session = self.order_sessions[conversation_id]
            session['interaction_count'] += 1
            
            # 更新订单信息
            if 'order_info' in response:
                session['order_info'] = response['order_info']

    def _extract_order_number(self, text: str) -> str:
        """从文本中提取订单号"""
        # 常见订单号格式：数字、字母数字组合
        patterns = [
            r'[0-9]{10,20}',  # 纯数字订单号
            r'[A-Z0-9]{8,20}',  # 字母数字组合
            r'DD[0-9]{8,}',  # DD开头的订单号
            r'TB[0-9]{8,}',  # TB开头的订单号
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.upper())
            if match:
                return match.group()
        
        return None

    def _extract_phone_number(self, text: str) -> str:
        """从文本中提取手机号"""
        # 中国手机号格式
        pattern = r'1[3-9]\d{9}'
        match = re.search(pattern, text)
        if match:
            return match.group()
        
        return None

    def can_handle(self, message: Message, context: Dict[str, Any] = None) -> float:
        """判断是否能处理该消息"""
        content = message.content.lower()
        
        # 订单相关关键词
        order_keywords = [
            "订单", "快递", "物流", "发货", "收货", "配送",
            "退货", "退款", "换货", "售后", "投诉",
            "查询", "状态", "进度", "到哪了", "什么时候到"
        ]
        
        # 订单号模式
        has_order_number = bool(self._extract_order_number(message.content))
        
        # 手机号模式
        has_phone_number = bool(self._extract_phone_number(message.content))
        
        # 关键词匹配
        keyword_score = sum(1 for keyword in order_keywords if keyword in content) / len(order_keywords)
        
        # 综合评分
        base_score = keyword_score * 2
        if has_order_number:
            base_score += 0.4
        if has_phone_number:
            base_score += 0.2
        
        return min(0.9, base_score + 0.2)  # 基础分0.2


# 创建订单智能体的工厂函数
def create_order_agent(agent_id: str = None, config: Dict[str, Any] = None) -> OrderAgent:
    """创建订单智能体实例"""
    if agent_id is None:
        agent_id = "order_agent"
    return OrderAgent(agent_id, config=config)


__all__ = ["OrderAgent", "create_order_agent"]