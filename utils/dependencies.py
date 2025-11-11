# -*- coding: utf-8 -*-
"""
依赖注入工具
提供FastAPI路由的依赖注入函数
"""

from fastapi import Request, HTTPException
from typing import Optional

def get_dispatcher(request: Request):
    """获取智能体调度器实例"""
    dispatcher = getattr(request.app.state, 'dispatcher', None)
    if not dispatcher:
        raise HTTPException(
            status_code=503,
            detail="智能体调度器未初始化"
        )
    return dispatcher

def get_orchestrator(request: Request):
    """兼容性函数：获取调度器实例（保持向后兼容）"""
    return get_dispatcher(request)