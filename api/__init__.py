# -*- coding: utf-8 -*-
"""
多智能体客服系统 - API接口层
"""

from .routers import (
    chat_router,
    agents_router,
    health_router,
    analytics_router,
    users_router,
    sessions_router,
    knowledge_router
)

__all__ = [
    "chat_router",
    "agents_router",
    "health_router", 
    "analytics_router",
    "users_router",
    "sessions_router",
    "knowledge_router"
]