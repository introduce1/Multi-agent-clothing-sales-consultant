# -*- coding: utf-8 -*-
"""
多智能体客服系统 - 配置模块
"""

from .settings import Settings, get_settings
from .database import DatabaseConfig, get_database

__all__ = [
    "Settings",
    "get_settings",
    "DatabaseConfig", 
    "get_database"
]