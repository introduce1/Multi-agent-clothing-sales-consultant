"""
仓储模式基类
提供通用的数据库操作方法
"""
from typing import TypeVar, Generic, List, Optional, Dict, Any, Type, Union
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.sql import Select
import logging

logger = logging.getLogger(__name__)

# 泛型类型变量
ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")

class BaseRepository(Generic[ModelType], ABC):
    """仓储基类"""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def create(self, obj_in: Union[CreateSchemaType, Dict[str, Any]]) -> ModelType:
        """创建记录"""
        try:
            if isinstance(obj_in, dict):
                db_obj = self.model(**obj_in)
            else:
                obj_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in.__dict__
                db_obj = self.model(**obj_data)
            
            self.session.add(db_obj)
            await self.session.flush()
            await self.session.refresh(db_obj)
            return db_obj
        except Exception as e:
            logger.error(f"创建记录失败: {e}")
            raise
    
    async def get(self, id: Any) -> Optional[ModelType]:
        """根据ID获取记录"""
        try:
            result = await self.session.execute(
                select(self.model).where(self.model.id == id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"获取记录失败: {e}")
            raise
    
    async def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[ModelType]:
        """获取多条记录"""
        try:
            query = select(self.model)
            
            # 应用过滤条件
            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        if isinstance(value, list):
                            query = query.where(getattr(self.model, key).in_(value))
                        else:
                            query = query.where(getattr(self.model, key) == value)
            
            # 应用排序
            if order_by and hasattr(self.model, order_by):
                order_column = getattr(self.model, order_by)
                if order_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))
            
            # 应用分页
            query = query.offset(skip).limit(limit)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"获取多条记录失败: {e}")
            raise
    
    async def update(
        self, 
        id: Any, 
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """更新记录"""
        try:
            # 获取现有记录
            db_obj = await self.get(id)
            if not db_obj:
                return None
            
            # 准备更新数据
            if isinstance(obj_in, dict):
                update_data = obj_in
            else:
                update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in.__dict__
            
            # 更新字段
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            await self.session.flush()
            await self.session.refresh(db_obj)
            return db_obj
        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            raise
    
    async def delete(self, id: Any) -> bool:
        """删除记录"""
        try:
            result = await self.session.execute(
                delete(self.model).where(self.model.id == id)
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            raise
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """统计记录数量"""
        try:
            query = select(func.count(self.model.id))
            
            # 应用过滤条件
            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        if isinstance(value, list):
                            query = query.where(getattr(self.model, key).in_(value))
                        else:
                            query = query.where(getattr(self.model, key) == value)
            
            result = await self.session.execute(query)
            return result.scalar()
        except Exception as e:
            logger.error(f"统计记录数量失败: {e}")
            raise
    
    async def exists(self, id: Any) -> bool:
        """检查记录是否存在"""
        try:
            result = await self.session.execute(
                select(func.count(self.model.id)).where(self.model.id == id)
            )
            return result.scalar() > 0
        except Exception as e:
            logger.error(f"检查记录存在性失败: {e}")
            raise
    
    async def bulk_create(self, objs_in: List[Union[CreateSchemaType, Dict[str, Any]]]) -> List[ModelType]:
        """批量创建记录"""
        try:
            db_objs = []
            for obj_in in objs_in:
                if isinstance(obj_in, dict):
                    db_obj = self.model(**obj_in)
                else:
                    obj_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in.__dict__
                    db_obj = self.model(**obj_data)
                db_objs.append(db_obj)
            
            self.session.add_all(db_objs)
            await self.session.flush()
            
            # 刷新所有对象
            for db_obj in db_objs:
                await self.session.refresh(db_obj)
            
            return db_objs
        except Exception as e:
            logger.error(f"批量创建记录失败: {e}")
            raise
    
    async def bulk_update(
        self, 
        filters: Dict[str, Any], 
        update_data: Dict[str, Any]
    ) -> int:
        """批量更新记录"""
        try:
            query = update(self.model)
            
            # 应用过滤条件
            conditions = []
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        conditions.append(getattr(self.model, key).in_(value))
                    else:
                        conditions.append(getattr(self.model, key) == value)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            query = query.values(**update_data)
            
            result = await self.session.execute(query)
            return result.rowcount
        except Exception as e:
            logger.error(f"批量更新记录失败: {e}")
            raise
    
    async def bulk_delete(self, filters: Dict[str, Any]) -> int:
        """批量删除记录"""
        try:
            query = delete(self.model)
            
            # 应用过滤条件
            conditions = []
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if isinstance(value, list):
                        conditions.append(getattr(self.model, key).in_(value))
                    else:
                        conditions.append(getattr(self.model, key) == value)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            result = await self.session.execute(query)
            return result.rowcount
        except Exception as e:
            logger.error(f"批量删除记录失败: {e}")
            raise
    
    async def search(
        self, 
        search_term: str, 
        search_fields: List[str],
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """搜索记录"""
        try:
            query = select(self.model)
            
            # 构建搜索条件
            search_conditions = []
            for field in search_fields:
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    search_conditions.append(column.ilike(f"%{search_term}%"))
            
            if search_conditions:
                query = query.where(or_(*search_conditions))
            
            # 应用分页
            query = query.offset(skip).limit(limit)
            
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"搜索记录失败: {e}")
            raise
    
    def _build_query(self, base_query: Select = None) -> Select:
        """构建基础查询"""
        if base_query is None:
            return select(self.model)
        return base_query
    
    async def execute_raw_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """执行原生SQL查询"""
        try:
            from sqlalchemy import text
            result = await self.session.execute(text(query), params or {})
            return result
        except Exception as e:
            logger.error(f"执行原生查询失败: {e}")
            raise