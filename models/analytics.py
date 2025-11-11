# -*- coding: utf-8 -*-
"""
分析统计相关数据模型
包括性能指标、业务指标和系统监控
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float
from sqlalchemy.ext.hybrid import hybrid_property

from .database import Base

beijing_tz = timezone(timedelta(hours=8))


class MetricType(str, Enum):
    """指标类型枚举"""
    PERFORMANCE = "performance"     # 性能指标
    BUSINESS = "business"          # 业务指标
    SYSTEM = "system"              # 系统指标
    USER = "user"                  # 用户指标
    QUALITY = "quality"            # 质量指标


class MetricCategory(str, Enum):
    """指标分类枚举"""
    RESPONSE_TIME = "response_time"         # 响应时间
    THROUGHPUT = "throughput"               # 吞吐量
    ERROR_RATE = "error_rate"               # 错误率
    SATISFACTION = "satisfaction"           # 满意度
    CONVERSION = "conversion"               # 转化率
    ENGAGEMENT = "engagement"               # 参与度
    RESOURCE_USAGE = "resource_usage"       # 资源使用


class PerformanceMetric(Base):
    """性能指标模型"""
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(20), default=MetricType.PERFORMANCE)
    category = Column(String(50), default=MetricCategory.RESPONSE_TIME)
    
    # 指标值
    value = Column(Float, nullable=False)
    unit = Column(String(20))               # 单位
    target_value = Column(Float)            # 目标值
    threshold_warning = Column(Float)       # 警告阈值
    threshold_critical = Column(Float)      # 严重阈值
    
    # 维度信息
    agent_name = Column(String(50))         # 智能体名称
    service_name = Column(String(50))       # 服务名称
    endpoint = Column(String(100))          # 接口端点
    
    # 时间维度
    timestamp = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    date = Column(String(10), index=True)   # 日期 YYYY-MM-DD
    hour = Column(Integer)                  # 小时 0-23
    minute = Column(Integer)                # 分钟 0-59
    
    # 统计信息
    sample_count = Column(Integer, default=1)  # 样本数量
    min_value = Column(Float)               # 最小值
    max_value = Column(Float)               # 最大值
    avg_value = Column(Float)               # 平均值
    percentile_95 = Column(Float)           # 95分位数
    percentile_99 = Column(Float)           # 99分位数
    
    # 元数据
    meta_data = Column(JSON)
    
    @hybrid_property
    def is_warning(self):
        """是否达到警告阈值"""
        return self.threshold_warning and self.value >= self.threshold_warning
    
    @hybrid_property
    def is_critical(self):
        """是否达到严重阈值"""
        return self.threshold_critical and self.value >= self.threshold_critical
    
    @hybrid_property
    def target_achievement_rate(self):
        """目标达成率"""
        if self.target_value and self.target_value > 0:
            return min(self.value / self.target_value, 1.0)
        return None
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "metric_type": self.metric_type,
            "category": self.category,
            "value": self.value,
            "unit": self.unit,
            "target_value": self.target_value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "agent_name": self.agent_name,
            "service_name": self.service_name,
            "endpoint": self.endpoint,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "date": self.date,
            "hour": self.hour,
            "minute": self.minute,
            "sample_count": self.sample_count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "avg_value": self.avg_value,
            "percentile_95": self.percentile_95,
            "percentile_99": self.percentile_99,
            "is_warning": self.is_warning,
            "is_critical": self.is_critical,
            "target_achievement_rate": self.target_achievement_rate,
            "metadata": self.metadata or {}
        }


class BusinessMetric(Base):
    """业务指标模型"""
    __tablename__ = "business_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    category = Column(String(50), default=MetricCategory.CONVERSION)
    
    # 指标值
    value = Column(Float, nullable=False)
    count = Column(Integer, default=0)      # 计数
    rate = Column(Float)                    # 比率
    
    # 业务维度
    business_unit = Column(String(50))      # 业务单元
    product_category = Column(String(50))   # 产品分类
    customer_segment = Column(String(50))   # 客户细分
    channel = Column(String(50))            # 渠道
    
    # 时间维度
    date = Column(String(10), index=True)   # 日期 YYYY-MM-DD
    week = Column(String(10))               # 周 YYYY-WW
    month = Column(String(7))               # 月 YYYY-MM
    quarter = Column(String(7))             # 季度 YYYY-QQ
    year = Column(String(4))                # 年 YYYY
    
    # 对比数据
    previous_period_value = Column(Float)   # 上期值
    year_over_year_value = Column(Float)    # 同比值
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    # 元数据
    meta_data = Column(JSON)
    
    @hybrid_property
    def period_over_period_growth(self):
        """环比增长率"""
        if self.previous_period_value and self.previous_period_value > 0:
            return (self.value - self.previous_period_value) / self.previous_period_value
        return None
    
    @hybrid_property
    def year_over_year_growth(self):
        """同比增长率"""
        if self.year_over_year_value and self.year_over_year_value > 0:
            return (self.value - self.year_over_year_value) / self.year_over_year_value
        return None
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "category": self.category,
            "value": self.value,
            "count": self.count,
            "rate": self.rate,
            "business_unit": self.business_unit,
            "product_category": self.product_category,
            "customer_segment": self.customer_segment,
            "channel": self.channel,
            "date": self.date,
            "week": self.week,
            "month": self.month,
            "quarter": self.quarter,
            "year": self.year,
            "previous_period_value": self.previous_period_value,
            "year_over_year_value": self.year_over_year_value,
            "period_over_period_growth": self.period_over_period_growth,
            "year_over_year_growth": self.year_over_year_growth,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata or {}
        }


class SystemMonitoring(Base):
    """系统监控模型"""
    __tablename__ = "system_monitoring"
    
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(50), nullable=False, index=True)
    instance_id = Column(String(100))       # 实例ID
    
    # 系统资源
    cpu_usage = Column(Float)               # CPU使用率
    memory_usage = Column(Float)            # 内存使用率
    disk_usage = Column(Float)              # 磁盘使用率
    network_in = Column(Float)              # 网络入流量
    network_out = Column(Float)             # 网络出流量
    
    # 应用指标
    active_connections = Column(Integer)    # 活跃连接数
    request_count = Column(Integer)         # 请求数量
    error_count = Column(Integer)           # 错误数量
    response_time_avg = Column(Float)       # 平均响应时间
    
    # 健康状态
    health_status = Column(String(20))      # 健康状态
    uptime_seconds = Column(Integer)        # 运行时间(秒)
    
    # 时间信息
    timestamp = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    
    # 元数据
    meta_data = Column(JSON)
    
    @hybrid_property
    def error_rate(self):
        """错误率"""
        if self.request_count and self.request_count > 0:
            return self.error_count / self.request_count
        return 0
    
    @hybrid_property
    def uptime_hours(self):
        """运行时间(小时)"""
        if self.uptime_seconds:
            return self.uptime_seconds / 3600
        return 0
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "disk_usage": self.disk_usage,
            "network_in": self.network_in,
            "network_out": self.network_out,
            "active_connections": self.active_connections,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "response_time_avg": self.response_time_avg,
            "error_rate": self.error_rate,
            "health_status": self.health_status,
            "uptime_seconds": self.uptime_seconds,
            "uptime_hours": self.uptime_hours,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata or {}
        }


class AlertRule(Base):
    """告警规则模型"""
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    
    # 规则配置
    metric_name = Column(String(100), nullable=False)
    condition = Column(String(20), nullable=False)  # >, <, >=, <=, ==, !=
    threshold_value = Column(Float, nullable=False)
    duration_minutes = Column(Integer, default=5)   # 持续时间
    
    # 告警级别
    severity = Column(String(20), default="warning")  # info, warning, critical
    
    # 通知配置
    notification_channels = Column(JSON)    # 通知渠道
    notification_template = Column(Text)    # 通知模板
    
    # 状态信息
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime)
    trigger_count = Column(Integer, default=0)
    
    # 时间信息
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    # 元数据
    meta_data = Column(JSON)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "description": self.description,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold_value": self.threshold_value,
            "duration_minutes": self.duration_minutes,
            "severity": self.severity,
            "notification_channels": self.notification_channels or [],
            "notification_template": self.notification_template,
            "is_active": self.is_active,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata or {}
        }


class AlertLog(Base):
    """告警日志模型"""
    __tablename__ = "alert_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, index=True)
    rule_id = Column(Integer, nullable=False)
    rule_name = Column(String(100), nullable=False)
    
    # 告警信息
    severity = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    # 触发信息
    metric_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    condition = Column(String(20), nullable=False)
    
    # 状态信息
    status = Column(String(20), default="active")  # active, resolved, suppressed
    resolved_at = Column(DateTime)
    resolved_by = Column(String(50))
    resolution_notes = Column(Text)
    
    # 通知信息
    notification_sent = Column(Boolean, default=False)
    notification_channels = Column(JSON)
    notification_errors = Column(JSON)
    
    # 时间信息
    triggered_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    
    # 元数据
    meta_data = Column(JSON)
    
    @hybrid_property
    def duration_minutes(self):
        """告警持续时间(分钟)"""
        if self.resolved_at and self.triggered_at:
            return (self.resolved_at - self.triggered_at).total_seconds() / 60
        return None
    
    def resolve_alert(self, resolved_by: str, notes: str = None):
        """解决告警"""
        self.status = "resolved"
        self.resolved_at = datetime.now(beijing_tz)
        self.resolved_by = resolved_by
        if notes:
            self.resolution_notes = notes
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "condition": self.condition,
            "status": self.status,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_notes": self.resolution_notes,
            "duration_minutes": self.duration_minutes,
            "notification_sent": self.notification_sent,
            "notification_channels": self.notification_channels or [],
            "notification_errors": self.notification_errors or [],
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "metadata": self.metadata or {}
        }


class Analytics(Base):
    """分析统计数据模型"""
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True)
    
    # 消息统计
    total_messages = Column(Integer, default=0)
    successful_responses = Column(Integer, default=0)
    failed_responses = Column(Integer, default=0)
    
    # 响应时间统计
    avg_response_time = Column(Float, default=0.0)
    total_response_time = Column(Float, default=0.0)
    
    # 智能体使用统计
    agent_usage = Column(JSON)  # {"agent_name": count}
    
    # 用户统计
    unique_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    
    # 满意度统计
    satisfaction_scores = Column(JSON)  # {"1": count, "2": count, ...}
    avg_satisfaction = Column(Float, default=0.0)
    
    # 转化统计
    conversions = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)
    
    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(beijing_tz))
    updated_at = Column(DateTime, default=lambda: datetime.now(beijing_tz), onupdate=lambda: datetime.now(beijing_tz))
    
    def __repr__(self):
        return f"<Analytics(date={self.date}, total_messages={self.total_messages})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "total_messages": self.total_messages,
            "successful_responses": self.successful_responses,
            "failed_responses": self.failed_responses,
            "avg_response_time": self.avg_response_time,
            "total_response_time": self.total_response_time,
            "agent_usage": self.agent_usage or {},
            "unique_users": self.unique_users,
            "new_users": self.new_users,
            "satisfaction_scores": self.satisfaction_scores or {},
            "avg_satisfaction": self.avg_satisfaction,
            "conversions": self.conversions,
            "conversion_rate": self.conversion_rate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }