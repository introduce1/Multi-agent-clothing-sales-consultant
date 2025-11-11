"""
具体仓储实现
为每个模型提供专门的数据访问方法
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import selectinload, joinedload

from .base_repository import BaseRepository
from models import Customer, ChatSession, KnowledgeEntry, Order, PerformanceMetric
import logging

logger = logging.getLogger(__name__)

class CustomerRepository(BaseRepository[Customer]):
    """客户仓储"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Customer, session)
    
    async def get_by_phone(self, phone: str) -> Optional[Customer]:
        """根据手机号获取客户"""
        try:
            result = await self.session.execute(
                select(self.model).where(self.model.phone == phone)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"根据手机号获取客户失败: {e}")
            raise
    
    async def get_by_email(self, email: str) -> Optional[Customer]:
        """根据邮箱获取客户"""
        try:
            result = await self.session.execute(
                select(self.model).where(self.model.email == email)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"根据邮箱获取客户失败: {e}")
            raise
    
    async def get_with_sessions(self, customer_id: str) -> Optional[Customer]:
        """获取客户及其会话信息"""
        try:
            result = await self.session.execute(
                select(self.model)
                .options(selectinload(self.model.sessions))
                .where(self.model.id == customer_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取客户及会话信息失败: {e}")
            raise
    
    async def get_active_customers(self, days: int = 30) -> List[Customer]:
        """获取活跃客户（指定天数内有活动）"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await self.session.execute(
                select(self.model)
                .where(self.model.last_active_at >= cutoff_date)
                .order_by(desc(self.model.last_active_at))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取活跃客户失败: {e}")
            raise
    
    async def search_customers(
        self, 
        search_term: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Customer]:
        """搜索客户"""
        return await self.search(
            search_term=search_term,
            search_fields=["name", "phone", "email"],
            skip=skip,
            limit=limit
        )
    
    async def get_customer_statistics(self) -> Dict[str, Any]:
        """获取客户统计信息"""
        try:
            # 总客户数
            total_customers = await self.count()
            
            # 活跃客户数（30天内）
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            active_result = await self.session.execute(
                select(func.count(self.model.id))
                .where(self.model.last_active_at >= cutoff_date)
            )
            active_customers = active_result.scalar()
            
            # 新客户数（7天内）
            new_cutoff = datetime.utcnow() - timedelta(days=7)
            new_result = await self.session.execute(
                select(func.count(self.model.id))
                .where(self.model.created_at >= new_cutoff)
            )
            new_customers = new_result.scalar()
            
            return {
                "total_customers": total_customers,
                "active_customers": active_customers,
                "new_customers": new_customers,
                "activity_rate": round(active_customers / total_customers * 100, 2) if total_customers > 0 else 0
            }
        except Exception as e:
            logger.error(f"获取客户统计信息失败: {e}")
            raise

class SessionRepository(BaseRepository[ChatSession]):
    """会话仓储"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(ChatSession, session)
    
    async def get_by_customer(self, customer_id: str) -> List[ChatSession]:
        """获取客户的所有会话"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(self.model.customer_id == customer_id)
                .order_by(desc(self.model.created_at))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取客户会话失败: {e}")
            raise
    
    async def get_active_sessions(self) -> List[ChatSession]:
        """获取活跃会话"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(self.model.status == "active")
                .order_by(desc(self.model.last_activity_at))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取活跃会话失败: {e}")
            raise
    
    async def get_sessions_by_agent(self, agent_id: str) -> List[ChatSession]:
        """获取指定智能体处理的会话"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(self.model.current_agent_id == agent_id)
                .order_by(desc(self.model.created_at))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取智能体会话失败: {e}")
            raise
    
    async def get_session_with_customer(self, session_id: str) -> Optional[ChatSession]:
        """获取会话及客户信息"""
        try:
            result = await self.session.execute(
                select(self.model)
                .options(joinedload(self.model.customer))
                .where(self.model.id == session_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取会话及客户信息失败: {e}")
            raise
    
    async def update_last_activity(self, session_id: str) -> bool:
        """更新会话最后活动时间"""
        try:
            result = await self.session.execute(
                select(self.model).where(self.model.id == session_id)
            )
            session_obj = result.scalar_one_or_none()
            if session_obj:
                session_obj.last_activity_at = datetime.utcnow()
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"更新会话活动时间失败: {e}")
            raise
    
    async def get_session_statistics(self, days: int = 30) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # 总会话数
            total_result = await self.session.execute(
                select(func.count(self.model.id))
                .where(self.model.created_at >= cutoff_date)
            )
            total_sessions = total_result.scalar()
            
            # 活跃会话数
            active_result = await self.session.execute(
                select(func.count(self.model.id))
                .where(self.model.status == "active")
            )
            active_sessions = active_result.scalar()
            
            # 已完成会话数
            completed_result = await self.session.execute(
                select(func.count(self.model.id))
                .where(and_(
                    self.model.status == "completed",
                    self.model.created_at >= cutoff_date
                ))
            )
            completed_sessions = completed_result.scalar()
            
            # 平均会话时长
            duration_result = await self.session.execute(
                select(func.avg(
                    func.extract('epoch', self.model.ended_at - self.model.created_at)
                ))
                .where(and_(
                    self.model.status == "completed",
                    self.model.ended_at.isnot(None),
                    self.model.created_at >= cutoff_date
                ))
            )
            avg_duration = duration_result.scalar() or 0
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "completed_sessions": completed_sessions,
                "completion_rate": round(completed_sessions / total_sessions * 100, 2) if total_sessions > 0 else 0,
                "avg_duration_minutes": round(avg_duration / 60, 2)
            }
        except Exception as e:
            logger.error(f"获取会话统计信息失败: {e}")
            raise

class KnowledgeBaseRepository(BaseRepository[KnowledgeEntry]):
    """知识库仓储"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(KnowledgeEntry, session)
    
    async def search_knowledge(
        self, 
        query: str, 
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[KnowledgeEntry]:
        """搜索知识库"""
        try:
            search_query = select(self.model)
            
            # 文本搜索条件
            search_conditions = [
                self.model.title.ilike(f"%{query}%"),
                self.model.content.ilike(f"%{query}%"),
                self.model.tags.ilike(f"%{query}%")
            ]
            search_query = search_query.where(or_(*search_conditions))
            
            # 分类过滤
            if category:
                search_query = search_query.where(self.model.category == category)
            
            # 只返回启用的知识
            search_query = search_query.where(self.model.is_active == True)
            
            # 按相关性排序（使用使用次数作为权重）
            search_query = search_query.order_by(desc(self.model.usage_count))
            search_query = search_query.limit(limit)
            
            result = await self.session.execute(search_query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"搜索知识库失败: {e}")
            raise
    
    async def get_by_category(self, category: str) -> List[KnowledgeEntry]:
        """根据分类获取知识"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(and_(
                    self.model.category == category,
                    self.model.is_active == True
                ))
                .order_by(desc(self.model.usage_count))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"根据分类获取知识失败: {e}")
            raise
    
    async def get_popular_knowledge(self, limit: int = 10) -> List[KnowledgeEntry]:
        """获取热门知识"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(self.model.is_active == True)
                .order_by(desc(self.model.usage_count))
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取热门知识失败: {e}")
            raise
    
    async def increment_usage(self, knowledge_id: str) -> bool:
        """增加知识使用次数"""
        try:
            result = await self.session.execute(
                select(self.model).where(self.model.id == knowledge_id)
            )
            knowledge = result.scalar_one_or_none()
            if knowledge:
                knowledge.usage_count += 1
                knowledge.last_used_at = datetime.utcnow()
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"增加知识使用次数失败: {e}")
            raise
    
    async def get_categories(self) -> List[str]:
        """获取所有分类"""
        try:
            result = await self.session.execute(
                select(self.model.category)
                .where(self.model.is_active == True)
                .distinct()
            )
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"获取分类失败: {e}")
            raise

class OrderRepository(BaseRepository[Order]):
    """订单仓储"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Order, session)
    
    async def get_by_customer(self, customer_id: str) -> List[Order]:
        """获取客户的所有订单"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(self.model.customer_id == customer_id)
                .order_by(desc(self.model.created_at))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取客户订单失败: {e}")
            raise
    
    async def get_by_status(self, status: str) -> List[Order]:
        """根据状态获取订单"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(self.model.status == status)
                .order_by(desc(self.model.created_at))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"根据状态获取订单失败: {e}")
            raise
    
    async def get_recent_orders(self, days: int = 7) -> List[Order]:
        """获取最近订单"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await self.session.execute(
                select(self.model)
                .where(self.model.created_at >= cutoff_date)
                .order_by(desc(self.model.created_at))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取最近订单失败: {e}")
            raise
    
    async def get_order_statistics(self, days: int = 30) -> Dict[str, Any]:
        """获取订单统计信息"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # 总订单数
            total_result = await self.session.execute(
                select(func.count(self.model.id))
                .where(self.model.created_at >= cutoff_date)
            )
            total_orders = total_result.scalar()
            
            # 总金额
            amount_result = await self.session.execute(
                select(func.sum(self.model.total_amount))
                .where(self.model.created_at >= cutoff_date)
            )
            total_amount = amount_result.scalar() or 0
            
            # 各状态订单数
            status_result = await self.session.execute(
                select(self.model.status, func.count(self.model.id))
                .where(self.model.created_at >= cutoff_date)
                .group_by(self.model.status)
            )
            status_counts = {row[0]: row[1] for row in status_result.fetchall()}
            
            return {
                "total_orders": total_orders,
                "total_amount": float(total_amount),
                "average_amount": float(total_amount / total_orders) if total_orders > 0 else 0,
                "status_distribution": status_counts
            }
        except Exception as e:
            logger.error(f"获取订单统计信息失败: {e}")
            raise

class AnalyticsRepository(BaseRepository[PerformanceMetric]):
    """分析统计仓储"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(PerformanceMetric, session)
    
    async def get_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        metric_type: Optional[str] = None
    ) -> List[PerformanceMetric]:
        """根据日期范围获取分析数据"""
        try:
            query = select(self.model).where(
                and_(
                    self.model.date >= start_date.date(),
                    self.model.date <= end_date.date()
                )
            )
            
            if metric_type:
                query = query.where(self.model.metric_type == metric_type)
            
            query = query.order_by(self.model.date)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"根据日期范围获取分析数据失败: {e}")
            raise
    
    async def get_latest_metrics(self, metric_type: str) -> Optional[PerformanceMetric]:
        """获取最新的指标数据"""
        try:
            result = await self.session.execute(
                select(self.model)
                .where(self.model.metric_type == metric_type)
                .order_by(desc(self.model.date))
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取最新指标数据失败: {e}")
            raise
    
    async def aggregate_metrics(
        self, 
        metric_type: str, 
        days: int = 30
    ) -> Dict[str, Any]:
        """聚合指标数据"""
        try:
            cutoff_date = datetime.utcnow().date() - timedelta(days=days)
            
            result = await self.session.execute(
                select(
                    func.avg(self.model.value).label('avg_value'),
                    func.min(self.model.value).label('min_value'),
                    func.max(self.model.value).label('max_value'),
                    func.sum(self.model.value).label('sum_value'),
                    func.count(self.model.id).label('count')
                )
                .where(and_(
                    self.model.metric_type == metric_type,
                    self.model.date >= cutoff_date
                ))
            )
            
            row = result.first()
            return {
                "average": float(row.avg_value) if row.avg_value else 0,
                "minimum": float(row.min_value) if row.min_value else 0,
                "maximum": float(row.max_value) if row.max_value else 0,
                "total": float(row.sum_value) if row.sum_value else 0,
                "count": row.count or 0
            }
        except Exception as e:
            logger.error(f"聚合指标数据失败: {e}")
            raise
    
    async def get_trend_data(
        self, 
        metric_type: str, 
        days: int = 30
    ) -> List[Tuple[str, float]]:
        """获取趋势数据"""
        try:
            cutoff_date = datetime.utcnow().date() - timedelta(days=days)
            
            result = await self.session.execute(
                select(self.model.date, self.model.value)
                .where(and_(
                    self.model.metric_type == metric_type,
                    self.model.date >= cutoff_date
                ))
                .order_by(self.model.date)
            )
            
            return [(row.date.isoformat(), float(row.value)) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"获取趋势数据失败: {e}")
            raise