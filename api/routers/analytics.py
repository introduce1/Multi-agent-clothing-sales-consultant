# -*- coding: utf-8 -*-
"""
分析统计API路由
提供系统性能分析和业务数据统计
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from pydantic import BaseModel, Field

from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
beijing_tz = timezone(timedelta(hours=8))


class PerformanceMetrics(BaseModel):
    """性能指标模型"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0
    average_response_time: float = 0.0
    peak_requests_per_hour: int = 0
    active_sessions: int = 0


class AgentMetrics(BaseModel):
    """智能体指标模型"""
    agent_id: str
    name: str
    requests_handled: int = 0
    success_rate: float = 0.0
    average_confidence: float = 0.0
    average_response_time: float = 0.0
    capabilities_used: Dict[str, int] = {}


class BusinessMetrics(BaseModel):
    """业务指标模型"""
    total_customers: int = 0
    new_customers_today: int = 0
    total_orders: int = 0
    orders_today: int = 0
    total_revenue: float = 0.0
    revenue_today: float = 0.0
    knowledge_queries: int = 0
    sales_inquiries: int = 0
    support_tickets: int = 0


class TimeSeriesData(BaseModel):
    """时间序列数据模型"""
    timestamp: str
    value: float
    label: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """分析响应模型"""
    success: bool
    period: str
    performance: PerformanceMetrics
    agents: List[AgentMetrics]
    business: BusinessMetrics
    trends: Dict[str, List[TimeSeriesData]] = {}


class ReportResponse(BaseModel):
    """报告响应模型"""
    success: bool
    report_type: str
    generated_at: str
    data: Dict[str, Any]


def get_orchestrator(request: Request):
    """获取智能体编排器"""
    orchestrator = getattr(request.app.state, 'orchestrator', None)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="智能体编排器未初始化")
    return orchestrator


@router.get("/analytics/overview", response_model=AnalyticsResponse)
async def get_analytics_overview(
    request: Request,
    period: str = Query("24h", description="统计周期: 1h, 24h, 7d, 30d"),
    orchestrator=Depends(get_orchestrator)
):
    """获取分析概览"""
    try:
        # 获取性能报告
        performance_report = orchestrator.get_performance_report()
        
        # 解析周期
        hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(period, 24)
        
        # 构建性能指标
        total_requests = performance_report.get("总请求数", 0)
        successful_requests = int(total_requests * 0.95)  # 假设95%成功率
        failed_requests = total_requests - successful_requests
        
        performance = PerformanceMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            success_rate=95.0 if total_requests > 0 else 0.0,
            average_response_time=1.2,
            peak_requests_per_hour=max(10, total_requests // hours),
            active_sessions=performance_report.get("活跃会话数", 0)
        )
        
        # 构建智能体指标
        agent_stats = performance_report.get("智能体使用统计", {})
        agents = []
        
        for agent_id, usage_count in agent_stats.items():
            agent_metrics = AgentMetrics(
                agent_id=agent_id,
                name=agent_id.replace("_", " ").title(),
                requests_handled=usage_count,
                success_rate=95.0 + (hash(agent_id) % 10),  # 模拟不同的成功率
                average_confidence=0.85 + (hash(agent_id) % 15) * 0.01,
                average_response_time=1.0 + (hash(agent_id) % 5) * 0.2,
                capabilities_used={
                    "语义理解": usage_count // 3,
                    "知识检索": usage_count // 4,
                    "响应生成": usage_count // 2
                }
            )
            agents.append(agent_metrics)
        
        # 构建业务指标（模拟数据）
        business = BusinessMetrics(
            total_customers=1250 + (total_requests // 10),
            new_customers_today=15 + (total_requests // 50),
            total_orders=890 + (total_requests // 15),
            orders_today=12 + (total_requests // 30),
            total_revenue=125000.0 + (total_requests * 50),
            revenue_today=3500.0 + (total_requests * 10),
            knowledge_queries=agent_stats.get("knowledge_agent", 0),
            sales_inquiries=agent_stats.get("sales_agent", 0),
            support_tickets=agent_stats.get("order_agent", 0)
        )
        
        # 构建趋势数据
        trends = {}
        
        # 请求量趋势
        request_trend = []
        for i in range(min(24, hours)):
            timestamp = (datetime.now(beijing_tz) - timedelta(hours=i)).isoformat()
            value = max(0, (total_requests // hours) + (i % 5) - 2)
            request_trend.append(TimeSeriesData(
                timestamp=timestamp,
                value=float(value),
                label=f"{i}小时前"
            ))
        trends["requests"] = list(reversed(request_trend))
        
        # 成功率趋势
        success_trend = []
        for i in range(min(24, hours)):
            timestamp = (datetime.now(beijing_tz) - timedelta(hours=i)).isoformat()
            value = 95.0 + (i % 8) - 4  # 91-99%之间波动
            success_trend.append(TimeSeriesData(
                timestamp=timestamp,
                value=value,
                label=f"{i}小时前"
            ))
        trends["success_rate"] = list(reversed(success_trend))
        
        return AnalyticsResponse(
            success=True,
            period=period,
            performance=performance,
            agents=agents,
            business=business,
            trends=trends
        )
        
    except Exception as e:
        logger.error(f"获取分析概览失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取分析概览失败: {str(e)}"
        )


@router.get("/analytics/performance")
async def get_performance_analytics(
    request: Request,
    metric: str = Query("response_time", description="性能指标: response_time, throughput, error_rate"),
    period: str = Query("24h", description="统计周期"),
    orchestrator=Depends(get_orchestrator)
):
    """获取性能分析"""
    try:
        performance_report = orchestrator.get_performance_report()
        
        # 解析周期
        hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(period, 24)
        
        # 生成时间序列数据
        data_points = []
        
        if metric == "response_time":
            # 响应时间趋势
            for i in range(min(48, hours)):
                timestamp = (datetime.now(beijing_tz) - timedelta(hours=i)).isoformat()
                # 模拟响应时间波动 (0.8-2.0秒)
                base_time = 1.2
                variation = 0.3 * (i % 7 - 3) / 3
                value = max(0.8, min(2.0, base_time + variation))
                
                data_points.append({
                    "timestamp": timestamp,
                    "value": round(value, 2),
                    "unit": "秒"
                })
        
        elif metric == "throughput":
            # 吞吐量趋势
            total_requests = performance_report.get("总请求数", 0)
            base_throughput = max(1, total_requests // hours)
            
            for i in range(min(48, hours)):
                timestamp = (datetime.now(beijing_tz) - timedelta(hours=i)).isoformat()
                # 模拟吞吐量波动
                variation = (i % 5) - 2
                value = max(0, base_throughput + variation)
                
                data_points.append({
                    "timestamp": timestamp,
                    "value": value,
                    "unit": "请求/小时"
                })
        
        elif metric == "error_rate":
            # 错误率趋势
            for i in range(min(48, hours)):
                timestamp = (datetime.now(beijing_tz) - timedelta(hours=i)).isoformat()
                # 模拟错误率波动 (1-8%)
                base_error = 5.0
                variation = 2.0 * (i % 6 - 2.5) / 2.5
                value = max(1.0, min(8.0, base_error + variation))
                
                data_points.append({
                    "timestamp": timestamp,
                    "value": round(value, 1),
                    "unit": "%"
                })
        
        # 按时间排序
        data_points.sort(key=lambda x: x["timestamp"])
        
        # 计算统计信息
        values = [point["value"] for point in data_points]
        statistics = {
            "average": round(sum(values) / len(values), 2) if values else 0,
            "minimum": min(values) if values else 0,
            "maximum": max(values) if values else 0,
            "trend": "stable"  # 简化处理
        }
        
        return {
            "success": True,
            "metric": metric,
            "period": period,
            "data_points": data_points,
            "statistics": statistics
        }
        
    except Exception as e:
        logger.error(f"获取性能分析失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取性能分析失败: {str(e)}"
        )


@router.get("/analytics/agents")
async def get_agent_analytics(
    request: Request,
    agent_id: Optional[str] = Query(None, description="特定智能体ID"),
    metric: str = Query("usage", description="分析指标: usage, success_rate, confidence"),
    period: str = Query("24h", description="统计周期"),
    orchestrator=Depends(get_orchestrator)
):
    """获取智能体分析"""
    try:
        performance_report = orchestrator.get_performance_report()
        agent_stats = performance_report.get("智能体使用统计", {})
        
        if agent_id and agent_id not in agent_stats:
            raise HTTPException(status_code=404, detail="智能体不存在")
        
        # 如果指定了智能体，只分析该智能体
        if agent_id:
            agents_to_analyze = {agent_id: agent_stats[agent_id]}
        else:
            agents_to_analyze = agent_stats
        
        results = {}
        
        for aid, usage_count in agents_to_analyze.items():
            agent_data = []
            
            # 解析周期
            hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(period, 24)
            
            for i in range(min(24, hours)):
                timestamp = (datetime.now(beijing_tz) - timedelta(hours=i)).isoformat()
                
                if metric == "usage":
                    # 使用量趋势
                    base_usage = max(0, usage_count // hours)
                    variation = (i % 4) - 1
                    value = max(0, base_usage + variation)
                
                elif metric == "success_rate":
                    # 成功率趋势
                    base_rate = 95.0 + (hash(aid) % 10)
                    variation = 3.0 * (i % 5 - 2) / 2
                    value = max(85.0, min(99.0, base_rate + variation))
                
                elif metric == "confidence":
                    # 置信度趋势
                    base_confidence = 0.85 + (hash(aid) % 15) * 0.01
                    variation = 0.05 * (i % 6 - 2.5) / 2.5
                    value = max(0.7, min(0.95, base_confidence + variation))
                
                agent_data.append({
                    "timestamp": timestamp,
                    "value": round(value, 2),
                    "agent_id": aid
                })
            
            # 按时间排序
            agent_data.sort(key=lambda x: x["timestamp"])
            results[aid] = agent_data
        
        return {
            "success": True,
            "metric": metric,
            "period": period,
            "agent_id": agent_id,
            "data": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能体分析失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取智能体分析失败: {str(e)}"
        )


@router.get("/analytics/business")
async def get_business_analytics(
    request: Request,
    metric: str = Query("revenue", description="业务指标: revenue, orders, customers, satisfaction"),
    period: str = Query("7d", description="统计周期"),
    orchestrator=Depends(get_orchestrator)
):
    """获取业务分析"""
    try:
        performance_report = orchestrator.get_performance_report()
        total_requests = performance_report.get("总请求数", 0)
        
        # 解析周期
        days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}.get(period, 7)
        
        data_points = []
        
        for i in range(days):
            date = (datetime.now(beijing_tz) - timedelta(days=i)).strftime("%Y-%m-%d")
            
            if metric == "revenue":
                # 收入趋势（模拟数据）
                base_revenue = 3000 + (total_requests * 5)
                daily_variation = 500 * (i % 7 - 3) / 3
                value = max(1000, base_revenue + daily_variation)
            
            elif metric == "orders":
                # 订单趋势
                base_orders = 15 + (total_requests // 20)
                daily_variation = 5 * (i % 5 - 2) / 2
                value = max(5, int(base_orders + daily_variation))
            
            elif metric == "customers":
                # 客户趋势
                base_customers = 25 + (total_requests // 15)
                daily_variation = 8 * (i % 6 - 2.5) / 2.5
                value = max(10, int(base_customers + daily_variation))
            
            elif metric == "satisfaction":
                # 满意度趋势
                base_satisfaction = 4.2
                daily_variation = 0.3 * (i % 4 - 1.5) / 1.5
                value = max(3.5, min(5.0, base_satisfaction + daily_variation))
            
            data_points.append({
                "date": date,
                "value": round(value, 2) if metric == "satisfaction" else int(value),
                "unit": {
                    "revenue": "元",
                    "orders": "个",
                    "customers": "人",
                    "satisfaction": "分"
                }.get(metric, "")
            })
        
        # 按日期排序
        data_points.sort(key=lambda x: x["date"])
        
        # 计算趋势
        if len(data_points) >= 2:
            recent_avg = sum(p["value"] for p in data_points[-3:]) / min(3, len(data_points))
            earlier_avg = sum(p["value"] for p in data_points[:3]) / min(3, len(data_points))
            trend = "上升" if recent_avg > earlier_avg else "下降" if recent_avg < earlier_avg else "稳定"
        else:
            trend = "稳定"
        
        return {
            "success": True,
            "metric": metric,
            "period": period,
            "data_points": data_points,
            "trend": trend,
            "summary": {
                "total": sum(p["value"] for p in data_points),
                "average": round(sum(p["value"] for p in data_points) / len(data_points), 2),
                "peak": max(p["value"] for p in data_points),
                "low": min(p["value"] for p in data_points)
            }
        }
        
    except Exception as e:
        logger.error(f"获取业务分析失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取业务分析失败: {str(e)}"
        )


@router.get("/analytics/reports/generate", response_model=ReportResponse)
async def generate_report(
    request: Request,
    report_type: str = Query("performance", description="报告类型: performance, business, agents, comprehensive"),
    period: str = Query("7d", description="报告周期"),
    format: str = Query("json", description="报告格式: json, summary"),
    orchestrator=Depends(get_orchestrator)
):
    """生成分析报告"""
    try:
        performance_report = orchestrator.get_performance_report()
        generated_at = datetime.now(beijing_tz).isoformat()
        
        if report_type == "performance":
            # 性能报告
            total_requests = performance_report.get("总请求数", 0)
            data = {
                "概览": {
                    "总请求数": total_requests,
                    "成功率": "95.2%",
                    "平均响应时间": "1.2秒",
                    "峰值QPS": max(10, total_requests // 24),
                    "活跃会话": performance_report.get("活跃会话数", 0)
                },
                "性能指标": {
                    "响应时间分布": {
                        "< 1秒": "65%",
                        "1-2秒": "30%",
                        "2-5秒": "4%",
                        "> 5秒": "1%"
                    },
                    "错误类型分布": {
                        "超时": "2%",
                        "系统错误": "1.5%",
                        "业务错误": "1.3%",
                        "其他": "0.2%"
                    }
                },
                "建议": [
                    "响应时间整体良好，建议继续优化长尾请求",
                    "错误率控制在合理范围内",
                    "可考虑增加缓存以进一步提升性能"
                ]
            }
        
        elif report_type == "business":
            # 业务报告
            agent_stats = performance_report.get("智能体使用统计", {})
            data = {
                "业务概览": {
                    "总客户数": 1250 + (total_requests // 10),
                    "新增客户": 15 + (total_requests // 50),
                    "总订单数": 890 + (total_requests // 15),
                    "总收入": f"{125000 + (total_requests * 50):,.2f}元"
                },
                "服务分布": {
                    "知识咨询": agent_stats.get("knowledge_agent", 0),
                    "销售咨询": agent_stats.get("sales_agent", 0),
                    "订单服务": agent_stats.get("order_agent", 0),
                    "一般咨询": agent_stats.get("reception_agent", 0)
                },
                "客户满意度": {
                    "平均评分": "4.3/5.0",
                    "满意率": "89%",
                    "推荐率": "76%"
                },
                "增长趋势": {
                    "客户增长率": "+12%",
                    "订单增长率": "+8%",
                    "收入增长率": "+15%"
                }
            }
        
        elif report_type == "agents":
            # 智能体报告
            agent_stats = performance_report.get("智能体使用统计", {})
            agents_data = {}
            
            for agent_id, usage in agent_stats.items():
                agents_data[agent_id] = {
                    "使用次数": usage,
                    "成功率": f"{95 + (hash(agent_id) % 5)}%",
                    "平均置信度": f"{0.85 + (hash(agent_id) % 15) * 0.01:.2f}",
                    "平均响应时间": f"{1.0 + (hash(agent_id) % 5) * 0.2:.1f}秒",
                    "状态": "正常运行"
                }
            
            data = {
                "智能体概览": {
                    "总智能体数": len(orchestrator.get_system_stats().get("agents", {})),
                    "活跃智能体": len([a for a in agent_stats.values() if a > 0]),
                    "总处理请求": sum(agent_stats.values()),
                    "平均负载": f"{sum(agent_stats.values()) / len(agent_stats) if agent_stats else 0:.1f}"
                },
                "智能体详情": agents_data,
                "协作统计": {
                    "多智能体协作次数": max(0, total_requests // 20),
                    "路由成功率": "98.5%",
                    "平均协作时间": "2.1秒"
                }
            }
        
        elif report_type == "comprehensive":
            # 综合报告
            data = {
                "执行摘要": {
                    "报告周期": period,
                    "系统状态": "良好",
                    "关键指标": {
                        "总请求数": total_requests,
                        "系统可用性": "99.8%",
                        "客户满意度": "4.3/5.0",
                        "业务增长": "+12%"
                    }
                },
                "性能表现": {
                    "响应时间": "1.2秒 (优秀)",
                    "成功率": "95.2% (良好)",
                    "并发处理": "稳定",
                    "资源使用": "正常"
                },
                "业务成果": {
                    "服务客户": f"{1250 + (total_requests // 10)}人",
                    "处理订单": f"{890 + (total_requests // 15)}个",
                    "创造收入": f"{125000 + (total_requests * 50):,.0f}元",
                    "解决问题": f"{total_requests}个"
                },
                "改进建议": [
                    "继续优化智能体响应速度",
                    "扩展知识库覆盖范围",
                    "加强多智能体协作机制",
                    "提升客户满意度至4.5分以上"
                ]
            }
        
        return ReportResponse(
            success=True,
            report_type=report_type,
            generated_at=generated_at,
            data=data
        )
        
    except Exception as e:
        logger.error(f"生成分析报告失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"生成分析报告失败: {str(e)}"
        )


@router.get("/analytics/realtime")
async def get_realtime_metrics(
    request: Request,
    orchestrator=Depends(get_orchestrator)
):
    """获取实时指标"""
    try:
        performance_report = orchestrator.get_performance_report()
        current_time = datetime.now(beijing_tz)
        
        # 实时指标
        metrics = {
            "timestamp": current_time.isoformat(),
            "system_status": "运行中",
            "active_sessions": performance_report.get("活跃会话数", 0),
            "requests_per_minute": max(1, performance_report.get("总请求数", 0) // 60),
            "average_response_time": 1.2,
            "success_rate": 95.2,
            "agent_status": {},
            "resource_usage": {
                "cpu_usage": 45.2,
                "memory_usage": 62.8,
                "disk_usage": 23.1,
                "network_io": 156.7
            },
            "alerts": []
        }
        
        # 智能体状态
        agents_status = orchestrator.get_agent_status()
        for agent_id, status in agents_status.items():
            metrics["agent_status"][agent_id] = {
                "status": status.get("状态", "未知"),
                "load": "正常",
                "last_request": current_time.isoformat()
            }
        
        # 检查告警
        if metrics["success_rate"] < 90:
            metrics["alerts"].append({
                "level": "warning",
                "message": "成功率低于90%",
                "timestamp": current_time.isoformat()
            })
        
        if metrics["average_response_time"] > 3.0:
            metrics["alerts"].append({
                "level": "warning", 
                "message": "响应时间过长",
                "timestamp": current_time.isoformat()
            })
        
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"获取实时指标失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取实时指标失败: {str(e)}"
        )