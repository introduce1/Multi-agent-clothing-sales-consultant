# -*- coding: utf-8 -*-
"""
健康检查API路由
提供系统状态监控和诊断信息
"""
import psutil
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
beijing_tz = timezone(timedelta(hours=8))


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str
    timestamp: str
    uptime: str
    version: str
    system_info: Dict[str, Any]
    agents_status: Dict[str, Any]
    performance: Dict[str, Any]


class DetailedHealthResponse(BaseModel):
    """详细健康检查响应模型"""
    status: str
    timestamp: str
    uptime: str
    version: str
    system_info: Dict[str, Any]
    agents_status: Dict[str, Any]
    performance: Dict[str, Any]
    memory_usage: Dict[str, Any]
    disk_usage: Dict[str, Any]
    network_info: Dict[str, Any]


# 系统启动时间
start_time = datetime.now(beijing_tz)


def get_orchestrator(request: Request):
    """获取智能体编排器"""
    return getattr(request.app.state, 'orchestrator', None)


def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    try:
        return {
            "platform": psutil.WINDOWS if psutil.WINDOWS else "Linux",
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_total": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
            "memory_available": f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
            "memory_percent": psutil.virtual_memory().percent,
            "boot_time": datetime.fromtimestamp(psutil.boot_time(), beijing_tz).isoformat()
        }
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return {"error": str(e)}


def get_memory_usage() -> Dict[str, Any]:
    """获取内存使用情况"""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "virtual_memory": {
                "total": f"{memory.total / (1024**3):.2f} GB",
                "available": f"{memory.available / (1024**3):.2f} GB",
                "used": f"{memory.used / (1024**3):.2f} GB",
                "percent": memory.percent
            },
            "swap_memory": {
                "total": f"{swap.total / (1024**3):.2f} GB",
                "used": f"{swap.used / (1024**3):.2f} GB",
                "free": f"{swap.free / (1024**3):.2f} GB",
                "percent": swap.percent
            }
        }
    except Exception as e:
        logger.error(f"获取内存使用情况失败: {e}")
        return {"error": str(e)}


def get_disk_usage() -> Dict[str, Any]:
    """获取磁盘使用情况"""
    try:
        disk_usage = {}
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage[partition.device] = {
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": f"{usage.total / (1024**3):.2f} GB",
                    "used": f"{usage.used / (1024**3):.2f} GB",
                    "free": f"{usage.free / (1024**3):.2f} GB",
                    "percent": (usage.used / usage.total) * 100
                }
            except PermissionError:
                # 跳过无权限访问的分区
                continue
        
        return disk_usage
    except Exception as e:
        logger.error(f"获取磁盘使用情况失败: {e}")
        return {"error": str(e)}


def get_network_info() -> Dict[str, Any]:
    """获取网络信息"""
    try:
        network_info = {}
        
        # 网络接口统计
        net_io = psutil.net_io_counters(pernic=True)
        for interface, stats in net_io.items():
            network_info[interface] = {
                "bytes_sent": f"{stats.bytes_sent / (1024**2):.2f} MB",
                "bytes_recv": f"{stats.bytes_recv / (1024**2):.2f} MB",
                "packets_sent": stats.packets_sent,
                "packets_recv": stats.packets_recv,
                "errin": stats.errin,
                "errout": stats.errout,
                "dropin": stats.dropin,
                "dropout": stats.dropout
            }
        
        # 网络连接数
        connections = psutil.net_connections()
        connection_stats = {
            "total": len(connections),
            "established": len([c for c in connections if c.status == 'ESTABLISHED']),
            "listen": len([c for c in connections if c.status == 'LISTEN']),
            "time_wait": len([c for c in connections if c.status == 'TIME_WAIT'])
        }
        
        return {
            "interfaces": network_info,
            "connections": connection_stats
        }
    except Exception as e:
        logger.error(f"获取网络信息失败: {e}")
        return {"error": str(e)}


def calculate_uptime() -> str:
    """计算系统运行时间"""
    uptime = datetime.now(beijing_tz) - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return f"{days}天 {hours}小时 {minutes}分钟 {seconds}秒"


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request, orchestrator=Depends(get_orchestrator)):
    """基础健康检查"""
    try:
        # 获取智能体状态
        agents_status = {}
        performance = {}
        
        if orchestrator:
            agents_status = orchestrator.get_agent_status()
            performance = orchestrator.get_performance_report()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(beijing_tz).isoformat(),
            uptime=calculate_uptime(),
            version="1.0.0",
            system_info=get_system_info(),
            agents_status=agents_status,
            performance=performance
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now(beijing_tz).isoformat(),
            uptime=calculate_uptime(),
            version="1.0.0",
            system_info={"error": str(e)},
            agents_status={},
            performance={}
        )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(request: Request, orchestrator=Depends(get_orchestrator)):
    """详细健康检查"""
    try:
        # 获取智能体状态
        agents_status = {}
        performance = {}
        
        if orchestrator:
            agents_status = orchestrator.get_agent_status()
            performance = orchestrator.get_performance_report()
        
        return DetailedHealthResponse(
            status="healthy",
            timestamp=datetime.now(beijing_tz).isoformat(),
            uptime=calculate_uptime(),
            version="1.0.0",
            system_info=get_system_info(),
            agents_status=agents_status,
            performance=performance,
            memory_usage=get_memory_usage(),
            disk_usage=get_disk_usage(),
            network_info=get_network_info()
        )
        
    except Exception as e:
        logger.error(f"详细健康检查失败: {e}")
        return DetailedHealthResponse(
            status="unhealthy",
            timestamp=datetime.now(beijing_tz).isoformat(),
            uptime=calculate_uptime(),
            version="1.0.0",
            system_info={"error": str(e)},
            agents_status={},
            performance={},
            memory_usage={"error": str(e)},
            disk_usage={"error": str(e)},
            network_info={"error": str(e)}
        )


@router.get("/health/agents")
async def agents_health(request: Request, orchestrator=Depends(get_orchestrator)):
    """智能体健康状态"""
    if not orchestrator:
        return {
            "status": "error",
            "message": "智能体编排器未初始化"
        }
    
    try:
        agents_status = orchestrator.get_agent_status()
        
        return {
            "status": "success",
            "timestamp": datetime.now(beijing_tz).isoformat(),
            "agents": agents_status,
            "total_agents": len(agents_status),
            "healthy_agents": len([a for a in agents_status.values() 
                                 if a.get("状态") == "运行中"])
        }
        
    except Exception as e:
        logger.error(f"获取智能体状态失败: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(beijing_tz).isoformat()
        }


@router.get("/health/performance")
async def performance_metrics(request: Request, orchestrator=Depends(get_orchestrator)):
    """性能指标"""
    if not orchestrator:
        return {
            "status": "error",
            "message": "智能体编排器未初始化"
        }
    
    try:
        performance = orchestrator.get_performance_report()
        
        return {
            "status": "success",
            "timestamp": datetime.now(beijing_tz).isoformat(),
            "metrics": performance
        }
        
    except Exception as e:
        logger.error(f"获取性能指标失败: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(beijing_tz).isoformat()
        }


@router.get("/health/system")
async def system_health():
    """系统资源健康状态"""
    try:
        system_info = get_system_info()
        memory_usage = get_memory_usage()
        
        # 健康状态评估
        health_status = "healthy"
        warnings = []
        
        # CPU使用率检查
        if system_info.get("cpu_percent", 0) > 80:
            health_status = "warning"
            warnings.append("CPU使用率过高")
        
        # 内存使用率检查
        if system_info.get("memory_percent", 0) > 85:
            health_status = "warning"
            warnings.append("内存使用率过高")
        
        # 如果有严重问题，标记为不健康
        if system_info.get("cpu_percent", 0) > 95 or system_info.get("memory_percent", 0) > 95:
            health_status = "unhealthy"
        
        return {
            "status": health_status,
            "timestamp": datetime.now(beijing_tz).isoformat(),
            "warnings": warnings,
            "system_info": system_info,
            "memory_usage": memory_usage
        }
        
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(beijing_tz).isoformat()
        }