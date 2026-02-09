"""
健康检查路由
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    """健康状态模型"""
    status: str = Field(description="服务状态: healthy/unhealthy")
    timestamp: str = Field(description="当前时间戳")
    version: str = Field(description="API 版本")
    uptime_seconds: float = Field(description="运行时间（秒）")


import time
_start_time = time.time()


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    健康检查接口

    返回服务当前状态
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        version="2.1.0",
        uptime_seconds=time.time() - _start_time
    )


@router.get("/ping")
async def ping():
    """
    简单的 ping 接口

    用于快速检查服务是否可用
    """
    return Response(content="pong", media_type="text/plain")


@router.get("/ready")
async def readiness_check():
    """
    就绪检查接口

    检查服务是否准备好接收请求
    """
    # 这里可以添加更多的就绪检查逻辑
    # 例如：数据库连接、文件系统等

    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """
    存活检查接口

    检查服务是否存活（用于 Kubernetes 存活探针）
    """
    return {"status": "alive"}


__all__ = ["router"]
