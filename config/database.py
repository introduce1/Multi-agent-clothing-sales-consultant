# -*- coding: utf-8 -*-
"""
数据库配置模块
"""

from typing import Optional
import os

class DatabaseConfig:
    """数据库配置类"""
    
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "3306"))
        self.username = os.getenv("DB_USERNAME", "root")
        self.password = os.getenv("DB_PASSWORD", "")
        self.database = os.getenv("DB_DATABASE", "customer_service")
        
    @property
    def connection_string(self) -> str:
        """获取数据库连接字符串"""
        return f"mysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

# 全局数据库配置实例
_database_config: Optional[DatabaseConfig] = None

def get_database() -> DatabaseConfig:
    """获取数据库配置实例"""
    global _database_config
    if _database_config is None:
        _database_config = DatabaseConfig()
    return _database_config