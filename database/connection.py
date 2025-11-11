"""
数据库连接管理模块
处理数据库连接、会话管理和初始化
"""
import os
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    AsyncEngine, 
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool
from sqlalchemy import text
import asyncio

# 配置日志
logger = logging.getLogger(__name__)

# 数据库基类
Base = declarative_base()

# 全局变量
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None

def get_database_url() -> str:
    """获取数据库连接URL"""
    # 从环境变量获取数据库配置
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "customer_service")
    db_user = os.getenv("DB_USER", "app_user")
    db_password = os.getenv("DB_PASSWORD", "secure_password")
    
    # 构建异步PostgreSQL连接URL
    return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def create_engine() -> AsyncEngine:
    """创建数据库引擎"""
    database_url = get_database_url()
    
    # 引擎配置
    engine_kwargs = {
        "echo": os.getenv("DB_ECHO", "false").lower() == "true",
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
        "pool_pre_ping": True,
    }
    
    return create_async_engine(database_url, **engine_kwargs)

async def init_database() -> None:
    """初始化数据库"""
    global _engine, _session_factory
    
    try:
        # 创建引擎
        _engine = create_engine()
        
        # 创建会话工厂
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        # 导入所有模型以确保表被创建
        from ..models import Customer, ChatSession, KnowledgeEntry, Order, PerformanceMetric, BusinessMetric, SystemMonitoring, AlertRule, AlertLog
        
        # 创建所有表
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 测试连接
        await test_connection()
        
        logger.info("数据库初始化成功")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

async def close_database() -> None:
    """关闭数据库连接"""
    global _engine, _session_factory
    
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("数据库连接已关闭")

async def test_connection() -> bool:
    """测试数据库连接"""
    try:
        async with get_database_session() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False

@asynccontextmanager
async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话上下文管理器"""
    if not _session_factory:
        raise RuntimeError("数据库未初始化，请先调用 init_database()")
    
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"数据库会话错误: {e}")
        raise
    finally:
        await session.close()

async def get_session() -> AsyncSession:
    """获取数据库会话（用于依赖注入）"""
    if not _session_factory:
        raise RuntimeError("数据库未初始化，请先调用 init_database()")
    
    return _session_factory()

class DatabaseHealthCheck:
    """数据库健康检查"""
    
    @staticmethod
    async def check_connection() -> dict:
        """检查数据库连接状态"""
        try:
            start_time = asyncio.get_event_loop().time()
            is_connected = await test_connection()
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return {
                "status": "healthy" if is_connected else "unhealthy",
                "response_time_ms": round(response_time, 2),
                "connection_pool": await DatabaseHealthCheck._get_pool_status()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": None,
                "connection_pool": None
            }
    
    @staticmethod
    async def _get_pool_status() -> dict:
        """获取连接池状态"""
        if not _engine:
            return {"status": "not_initialized"}
        
        pool = _engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }

# 数据库事务装饰器
def transactional(func):
    """数据库事务装饰器"""
    async def wrapper(*args, **kwargs):
        async with get_database_session() as session:
            try:
                result = await func(session, *args, **kwargs)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e
    return wrapper