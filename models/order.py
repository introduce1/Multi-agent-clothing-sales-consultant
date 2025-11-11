# -*- coding: utf-8 -*-
"""
订单相关数据模型
包括订单、订单项、支付信息和物流信息
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from .database import Base

beijing_tz = timezone(timedelta(hours=8))


class OrderStatus(str, Enum):
    """订单状态枚举"""
    PENDING = "pending"         # 待处理
    CONFIRMED = "confirmed"     # 已确认
    PAID = "paid"              # 已支付
    PROCESSING = "processing"   # 处理中
    SHIPPED = "shipped"        # 已发货
    DELIVERED = "delivered"    # 已送达
    COMPLETED = "completed"    # 已完成
    CANCELLED = "cancelled"    # 已取消
    REFUNDED = "refunded"      # 已退款


class PaymentStatus(str, Enum):
    """支付状态枚举"""
    PENDING = "pending"         # 待支付
    PROCESSING = "processing"   # 支付中
    PAID = "paid"              # 已支付
    FAILED = "failed"          # 支付失败
    REFUNDED = "refunded"      # 已退款
    PARTIAL_REFUND = "partial_refund"  # 部分退款


class PaymentMethod(str, Enum):
    """支付方式枚举"""
    ALIPAY = "alipay"          # 支付宝
    WECHAT = "wechat"          # 微信支付
    BANK_CARD = "bank_card"    # 银行卡
    CREDIT_CARD = "credit_card"  # 信用卡
    CASH = "cash"              # 现金
    TRANSFER = "transfer"      # 转账


class ShippingStatus(str, Enum):
    """物流状态枚举"""
    PENDING = "pending"         # 待发货
    PICKED_UP = "picked_up"    # 已揽收
    IN_TRANSIT = "in_transit"  # 运输中
    OUT_FOR_DELIVERY = "out_for_delivery"  # 派送中
    DELIVERED = "delivered"    # 已送达
    FAILED = "failed"          # 配送失败
    RETURNED = "returned"      # 已退回


class Order(Base):
    """订单模型"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    
    # 订单基本信息
    status = Column(String(20), default=OrderStatus.PENDING)
    order_type = Column(String(20), default="normal")  # 订单类型
    source = Column(String(50))  # 订单来源
    
    # 金额信息
    subtotal = Column(Numeric(10, 2), default=0)      # 小计
    tax_amount = Column(Numeric(10, 2), default=0)    # 税费
    shipping_fee = Column(Numeric(10, 2), default=0)  # 运费
    discount_amount = Column(Numeric(10, 2), default=0)  # 优惠金额
    total_amount = Column(Numeric(10, 2), default=0)  # 总金额
    
    # 优惠信息
    coupon_code = Column(String(50))     # 优惠券代码
    promotion_id = Column(String(50))    # 促销活动ID
    
    # 收货信息
    shipping_name = Column(String(100))
    shipping_phone = Column(String(20))
    shipping_address = Column(Text)
    shipping_city = Column(String(50))
    shipping_province = Column(String(50))
    shipping_postal_code = Column(String(20))
    
    # 备注信息
    customer_notes = Column(Text)        # 客户备注
    internal_notes = Column(Text)        # 内部备注
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    confirmed_at = Column(DateTime)
    shipped_at = Column(DateTime)
    delivered_at = Column(DateTime)
    
    # 元数据
    meta_data = Column(JSON)
    
    # 关联关系
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment_info = relationship("PaymentInfo", back_populates="order", uselist=False)
    shipping_info = relationship("ShippingInfo", back_populates="order", uselist=False)
    
    @hybrid_property
    def item_count(self):
        """商品数量"""
        return sum(item.quantity for item in self.items)
    
    @hybrid_property
    def is_paid(self):
        """是否已支付"""
        return self.payment_info and self.payment_info.status == PaymentStatus.PAID
    
    @hybrid_property
    def is_shipped(self):
        """是否已发货"""
        return self.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED]
    
    @hybrid_property
    def shipping_address_full(self):
        """完整收货地址"""
        parts = [self.shipping_province, self.shipping_city, self.shipping_address]
        return ", ".join([part for part in parts if part])
    
    def calculate_total(self):
        """计算订单总金额"""
        self.subtotal = sum(item.total_price for item in self.items)
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_fee - self.discount_amount
        return float(self.total_amount)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "status": self.status,
            "order_type": self.order_type,
            "source": self.source,
            "subtotal": float(self.subtotal) if self.subtotal else 0,
            "tax_amount": float(self.tax_amount) if self.tax_amount else 0,
            "shipping_fee": float(self.shipping_fee) if self.shipping_fee else 0,
            "discount_amount": float(self.discount_amount) if self.discount_amount else 0,
            "total_amount": float(self.total_amount) if self.total_amount else 0,
            "coupon_code": self.coupon_code,
            "shipping_address": self.shipping_address_full,
            "shipping_name": self.shipping_name,
            "shipping_phone": self.shipping_phone,
            "customer_notes": self.customer_notes,
            "item_count": self.item_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "shipped_at": self.shipped_at.isoformat() if self.shipped_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None
        }


class OrderItem(Base):
    """订单项模型"""
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    
    # 商品信息
    product_id = Column(String(50), nullable=False)
    product_name = Column(String(200), nullable=False)
    product_sku = Column(String(100))
    product_category = Column(String(100))
    
    # 规格信息
    specifications = Column(JSON)  # 商品规格
    
    # 价格和数量
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    discount_amount = Column(Numeric(10, 2), default=0)
    
    # 备注
    notes = Column(Text)
    
    # 关联关系
    order = relationship("Order", back_populates="items")
    
    @hybrid_property
    def total_price(self):
        """总价"""
        return (self.unit_price * self.quantity) - (self.discount_amount or 0)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_sku": self.product_sku,
            "product_category": self.product_category,
            "specifications": self.specifications or {},
            "unit_price": float(self.unit_price),
            "quantity": self.quantity,
            "discount_amount": float(self.discount_amount) if self.discount_amount else 0,
            "total_price": float(self.total_price),
            "notes": self.notes
        }


class PaymentInfo(Base):
    """支付信息模型"""
    __tablename__ = "payment_info"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True)
    
    # 支付基本信息
    payment_id = Column(String(100), unique=True, index=True)
    status = Column(String(20), default=PaymentStatus.PENDING)
    method = Column(String(20), nullable=False)
    
    # 金额信息
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), default="CNY")
    
    # 第三方支付信息
    transaction_id = Column(String(100))  # 第三方交易ID
    gateway = Column(String(50))          # 支付网关
    gateway_response = Column(JSON)       # 网关响应
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    paid_at = Column(DateTime)
    failed_at = Column(DateTime)
    refunded_at = Column(DateTime)
    
    # 失败信息
    failure_reason = Column(Text)
    
    # 退款信息
    refund_amount = Column(Numeric(10, 2), default=0)
    refund_reason = Column(Text)
    
    # 关联关系
    order = relationship("Order", back_populates="payment_info")
    
    @hybrid_property
    def is_successful(self):
        """是否支付成功"""
        return self.status == PaymentStatus.PAID
    
    @hybrid_property
    def refundable_amount(self):
        """可退款金额"""
        return self.amount - (self.refund_amount or 0)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "payment_id": self.payment_id,
            "status": self.status,
            "method": self.method,
            "amount": float(self.amount),
            "currency": self.currency,
            "transaction_id": self.transaction_id,
            "gateway": self.gateway,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
            "failure_reason": self.failure_reason,
            "refund_amount": float(self.refund_amount) if self.refund_amount else 0,
            "refund_reason": self.refund_reason,
            "refundable_amount": float(self.refundable_amount)
        }


class ShippingInfo(Base):
    """物流信息模型"""
    __tablename__ = "shipping_info"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True)
    
    # 物流基本信息
    tracking_number = Column(String(100), unique=True, index=True)
    carrier = Column(String(50))          # 承运商
    service_type = Column(String(50))     # 服务类型
    status = Column(String(20), default=ShippingStatus.PENDING)
    
    # 地址信息
    origin_address = Column(Text)         # 发货地址
    destination_address = Column(Text)    # 收货地址
    
    # 包裹信息
    weight = Column(Float)                # 重量(kg)
    dimensions = Column(JSON)             # 尺寸信息
    package_count = Column(Integer, default=1)  # 包裹数量
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    shipped_at = Column(DateTime)
    estimated_delivery = Column(DateTime)  # 预计送达时间
    delivered_at = Column(DateTime)
    
    # 物流轨迹
    tracking_events = Column(JSON)        # 物流轨迹事件
    
    # 费用信息
    shipping_cost = Column(Numeric(10, 2))
    insurance_cost = Column(Numeric(10, 2), default=0)
    
    # 备注
    notes = Column(Text)
    
    # 关联关系
    order = relationship("Order", back_populates="shipping_info")
    
    @hybrid_property
    def is_delivered(self):
        """是否已送达"""
        return self.status == ShippingStatus.DELIVERED
    
    @hybrid_property
    def total_cost(self):
        """总费用"""
        return (self.shipping_cost or 0) + (self.insurance_cost or 0)
    
    def add_tracking_event(self, event_type: str, description: str, location: str = None):
        """添加物流轨迹事件"""
        if not self.tracking_events:
            self.tracking_events = []
        
        event = {
            "timestamp": datetime.now(beijing_tz).isoformat(),
            "event_type": event_type,
            "description": description,
            "location": location
        }
        
        self.tracking_events.append(event)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "tracking_number": self.tracking_number,
            "carrier": self.carrier,
            "service_type": self.service_type,
            "status": self.status,
            "origin_address": self.origin_address,
            "destination_address": self.destination_address,
            "weight": self.weight,
            "dimensions": self.dimensions or {},
            "package_count": self.package_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "shipped_at": self.shipped_at.isoformat() if self.shipped_at else None,
            "estimated_delivery": self.estimated_delivery.isoformat() if self.estimated_delivery else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "tracking_events": self.tracking_events or [],
            "shipping_cost": float(self.shipping_cost) if self.shipping_cost else 0,
            "insurance_cost": float(self.insurance_cost) if self.insurance_cost else 0,
            "total_cost": float(self.total_cost),
            "notes": self.notes
        }