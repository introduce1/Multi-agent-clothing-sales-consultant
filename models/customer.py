# -*- coding: utf-8 -*-
"""
客户相关数据模型
包括客户信息、客户画像和客户交互记录
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from .database import Base

beijing_tz = timezone(timedelta(hours=8))


class CustomerStatus(str, Enum):
    """客户状态枚举"""
    ACTIVE = "active"           # 活跃
    INACTIVE = "inactive"       # 非活跃
    POTENTIAL = "potential"     # 潜在客户
    VIP = "vip"                # VIP客户
    BLACKLIST = "blacklist"    # 黑名单


class CustomerSegment(str, Enum):
    """客户细分枚举"""
    ENTERPRISE = "enterprise"   # 企业客户
    SMB = "smb"                # 中小企业
    INDIVIDUAL = "individual"   # 个人客户
    GOVERNMENT = "government"   # 政府客户
    EDUCATION = "education"     # 教育客户


class InteractionType(str, Enum):
    """交互类型枚举"""
    CHAT = "chat"              # 聊天
    EMAIL = "email"            # 邮件
    PHONE = "phone"            # 电话
    ORDER = "order"            # 订单
    COMPLAINT = "complaint"    # 投诉
    FEEDBACK = "feedback"      # 反馈


class Customer(Base):
    """客户基础信息模型"""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20), index=True)
    company = Column(String(200))
    
    # 状态信息
    status = Column(String(20), default=CustomerStatus.POTENTIAL)
    segment = Column(String(20), default=CustomerSegment.INDIVIDUAL)
    
    # 地址信息
    address = Column(Text)
    city = Column(String(50))
    province = Column(String(50))
    country = Column(String(50), default="中国")
    postal_code = Column(String(20))
    
    # 业务信息
    source = Column(String(50))  # 客户来源
    referrer = Column(String(100))  # 推荐人
    tags = Column(JSON)  # 标签列表
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    last_contact_at = Column(DateTime)
    
    # 关联关系
    profile = relationship("CustomerProfile", back_populates="customer", uselist=False)
    interactions = relationship("CustomerInteraction", back_populates="customer")
    orders = relationship("Order", back_populates="customer")
    chat_sessions = relationship("ChatSession", back_populates="customer")
    
    @hybrid_property
    def full_address(self):
        """完整地址"""
        parts = [self.country, self.province, self.city, self.address]
        return ", ".join([part for part in parts if part])
    
    @hybrid_property
    def is_vip(self):
        """是否VIP客户"""
        return self.status == CustomerStatus.VIP
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "status": self.status,
            "segment": self.segment,
            "address": self.full_address,
            "source": self.source,
            "tags": self.tags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_contact_at": self.last_contact_at.isoformat() if self.last_contact_at else None
        }


class CustomerProfile(Base):
    """客户画像模型"""
    __tablename__ = "customer_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), unique=True)
    
    # 基础画像
    age_range = Column(String(20))  # 年龄段
    gender = Column(String(10))     # 性别
    occupation = Column(String(100))  # 职业
    income_level = Column(String(20))  # 收入水平
    education = Column(String(50))   # 教育程度
    
    # 行为画像
    preferred_contact_method = Column(String(20), default="chat")
    preferred_contact_time = Column(String(50))  # 偏好联系时间
    communication_style = Column(String(20))     # 沟通风格
    
    # 业务画像
    purchase_frequency = Column(String(20))      # 购买频率
    average_order_value = Column(Float, default=0.0)  # 平均订单价值
    total_spent = Column(Float, default=0.0)     # 总消费金额
    lifetime_value = Column(Float, default=0.0)  # 客户生命周期价值
    
    # 偏好信息
    product_preferences = Column(JSON)           # 产品偏好
    service_preferences = Column(JSON)           # 服务偏好
    interests = Column(JSON)                     # 兴趣爱好
    
    # 满意度信息
    satisfaction_score = Column(Float, default=0.0)  # 满意度评分
    nps_score = Column(Integer, default=0)       # 净推荐值
    
    # 风险信息
    risk_level = Column(String(20), default="low")  # 风险等级
    churn_probability = Column(Float, default=0.0)  # 流失概率
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    # 关联关系
    customer = relationship("Customer", back_populates="profile")
    
    @hybrid_property
    def is_high_value(self):
        """是否高价值客户"""
        return self.lifetime_value > 10000 or self.average_order_value > 1000
    
    @hybrid_property
    def risk_category(self):
        """风险类别"""
        if self.churn_probability > 0.7:
            return "high_risk"
        elif self.churn_probability > 0.3:
            return "medium_risk"
        else:
            return "low_risk"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "age_range": self.age_range,
            "gender": self.gender,
            "occupation": self.occupation,
            "income_level": self.income_level,
            "education": self.education,
            "preferred_contact_method": self.preferred_contact_method,
            "communication_style": self.communication_style,
            "purchase_frequency": self.purchase_frequency,
            "average_order_value": self.average_order_value,
            "total_spent": self.total_spent,
            "lifetime_value": self.lifetime_value,
            "satisfaction_score": self.satisfaction_score,
            "nps_score": self.nps_score,
            "risk_level": self.risk_level,
            "churn_probability": self.churn_probability,
            "product_preferences": self.product_preferences or [],
            "service_preferences": self.service_preferences or [],
            "interests": self.interests or []
        }


class CustomerInteraction(Base):
    """客户交互记录模型"""
    __tablename__ = "customer_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    
    # 交互信息
    interaction_type = Column(String(20), nullable=False)
    channel = Column(String(50))  # 渠道
    agent_id = Column(String(50))  # 处理的智能体ID
    
    # 内容信息
    subject = Column(String(200))  # 主题
    content = Column(Text)         # 内容
    summary = Column(Text)         # 摘要
    
    # 结果信息
    status = Column(String(20), default="completed")  # 状态
    resolution = Column(Text)      # 解决方案
    satisfaction_rating = Column(Integer)  # 满意度评分 (1-5)
    
    # 分类信息
    category = Column(String(50))  # 分类
    priority = Column(String(20), default="medium")  # 优先级
    tags = Column(JSON)           # 标签
    
    # 时间信息
    started_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    ended_at = Column(DateTime)
    duration = Column(Integer)    # 持续时间(秒)
    
    # 元数据
    meta_data = Column(JSON)       # 额外元数据
    
    # 关联关系
    customer = relationship("Customer", back_populates="interactions")
    
    @hybrid_property
    def duration_minutes(self):
        """持续时间(分钟)"""
        if self.duration:
            return round(self.duration / 60, 2)
        return 0
    
    @hybrid_property
    def is_resolved(self):
        """是否已解决"""
        return self.status in ["completed", "resolved"]
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "interaction_type": self.interaction_type,
            "channel": self.channel,
            "agent_id": self.agent_id,
            "subject": self.subject,
            "content": self.content,
            "summary": self.summary,
            "status": self.status,
            "resolution": self.resolution,
            "satisfaction_rating": self.satisfaction_rating,
            "category": self.category,
            "priority": self.priority,
            "tags": self.tags or [],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration": self.duration,
            "duration_minutes": self.duration_minutes
        }