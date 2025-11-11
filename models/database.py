# -*- coding: utf-8 -*-
"""
数据库配置
设置SQLAlchemy数据库连接和会话管理
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import BaseConfig
from utils.logger import get_logger

logger = get_logger(__name__)

# 数据库URL
DATABASE_URL = BaseConfig.DATABASE_URL

# 确保数据目录存在
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if not db_path.startswith(":memory:"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# 创建数据库引擎
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=BaseConfig.DATABASE_ECHO
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=BaseConfig.DATABASE_ECHO
    )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()

# 元数据
metadata = MetaData()


def get_db():
    """
    获取数据库会话
    
    Yields:
        数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """创建所有数据表"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据表创建成功")
    except Exception as e:
        logger.error(f"数据表创建失败: {e}")
        raise


def drop_tables():
    """删除所有数据表"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("数据表删除成功")
    except Exception as e:
        logger.error(f"数据表删除失败: {e}")
        raise


def init_database():
    """初始化数据库"""
    try:
        # 创建数据表
        create_tables()
        
        # 基础数据初始化已移除
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


def init_db():
    """初始化数据库 - 别名函数"""
    return init_database()


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def get_session(self):
        """获取数据库会话"""
        return SessionLocal()
    
    def execute_query(self, query, params=None):
        """执行查询"""
        with self.get_session() as session:
            try:
                result = session.execute(query, params or {})
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                logger.error(f"查询执行失败: {e}")
                raise
    
    def health_check(self):
        """数据库健康检查"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return False
    
    def get_connection_info(self):
        """获取连接信息"""
        return {
            "url": str(self.engine.url).replace(str(self.engine.url.password), "***") if self.engine.url.password else str(self.engine.url),
            "driver": self.engine.dialect.name,
            "pool_size": getattr(self.engine.pool, 'size', None),
            "max_overflow": getattr(self.engine.pool, 'max_overflow', None),
            "echo": self.engine.echo
        }
    
    def close(self):
        """关闭数据库连接"""
        try:
            if hasattr(self.engine, 'dispose'):
                self.engine.dispose()
                logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")


# 全局数据库管理器实例
db_manager = DatabaseManager()