# -*- coding: utf-8 -*-
"""
数据模型包
包含所有数据库模型定义
"""

# 导入数据库配置
from .database import Base, engine, SessionLocal, get_db, DatabaseManager

# 导入客户相关模型
from .customer import (
    Customer, CustomerProfile, CustomerInteraction,
    CustomerStatus, CustomerSegment, InteractionType
)

# 导入订单相关模型
from .order import (
    Order, OrderItem, PaymentInfo, ShippingInfo,
    OrderStatus, PaymentStatus, PaymentMethod, ShippingStatus
)

# 导入知识库相关模型
from .knowledge import (
    KnowledgeEntry, KnowledgeCategory, KnowledgeTag, KnowledgeSearchIndex, KnowledgeFeedback,
    KnowledgeStatus, KnowledgeType, ContentFormat, knowledge_tags
)

# 导入会话相关模型
from .session import (
    ChatSession, ChatMessage, SessionStatistics,
    SessionStatus, MessageType, MessageSender, EscalationReason
)

# 导入分析统计相关模型
from .analytics import (
    PerformanceMetric, BusinessMetric, SystemMonitoring, AlertRule, AlertLog,
    MetricType, MetricCategory
)

# 淘宝商品模型已移除，现在使用API直接搜索商品

# 导出所有模型类
__all__ = [
    # 数据库
    "Base", "engine", "SessionLocal", "get_db", "DatabaseManager",
    
    # 客户模型
    "Customer", "CustomerProfile", "CustomerInteraction",
    "CustomerStatus", "CustomerSegment", "InteractionType",
    
    # 订单模型
    "Order", "OrderItem", "PaymentInfo", "ShippingInfo",
    "OrderStatus", "PaymentStatus", "PaymentMethod", "ShippingStatus",
    
    # 知识库模型
    "KnowledgeEntry", "KnowledgeCategory", "KnowledgeTag", "KnowledgeSearchIndex", "KnowledgeFeedback",
    "KnowledgeStatus", "KnowledgeType", "ContentFormat", "knowledge_tags",
    
    # 会话模型
    "ChatSession", "ChatMessage", "SessionStatistics",
    "SessionStatus", "MessageType", "MessageSender", "EscalationReason",
    
    # 分析统计
    "PerformanceMetric", "BusinessMetric", "SystemMonitoring", "AlertRule", "AlertLog",
    "MetricType", "MetricCategory"
]