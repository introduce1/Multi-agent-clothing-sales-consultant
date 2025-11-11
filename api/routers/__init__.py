# -*- coding: utf-8 -*-
"""
多智能体客服系统 - API路由
"""

from .chat import router as chat_router
from .agents import router as agents_router
from .health import router as health_router
from .analytics import router as analytics_router
from .users import router as users_router
from .sessions import router as sessions_router
from .knowledge import router as knowledge_router

__all__ = [
    "chat_router",
    "agents_router", 
    "health_router",
    "analytics_router",
    "users_router",
    "sessions_router",
    "knowledge_router",
]