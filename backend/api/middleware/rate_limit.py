"""
API 速率限制中间件

提供基于令牌桶算法的 API 速率限制功能，支持按 IP 和用户的限制。
"""

import time
import logging
import asyncio
import os
from collections import defaultdict
from typing import Dict, Tuple, Optional, Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


# ===== 速率限制存储 =====

class RateLimitStorage:
    """速率限制存储（内存实现）"""

    def __init__(self):
        # IP 限制存储: {ip: (tokens, last_update)}
        self.ip_limits: Dict[str, Tuple[float, float]] = defaultdict(lambda: (0, 0))

        # 用户限制存储: {user_id: (tokens, last_update)}
        self.user_limits: Dict[str, Tuple[float, float]] = defaultdict(lambda: (0, 0))

    def get_ip_tokens(self, ip: str) -> Tuple[float, float]:
        """获取 IP 的令牌数和最后更新时间"""
        return self.ip_limits.get(ip, (0, 0))

    def set_ip_tokens(self, ip: str, tokens: float, last_update: float):
        """设置 IP 的令牌数和最后更新时间"""
        self.ip_limits[ip] = (tokens, last_update)

    def get_user_tokens(self, user_id: str) -> Tuple[float, float]:
        """获取用户的令牌数和最后更新时间"""
        return self.user_limits.get(user_id, (0, 0))

    def set_user_tokens(self, user_id: str, tokens: float, last_update: float):
        """设置用户的令牌数和最后更新时间"""
        self.user_limits[user_id] = (tokens, last_update)


# 全局存储实例
rate_limit_storage = RateLimitStorage()


# ===== 速率限制配置 =====

class RateLimitConfig:
    """速率限制配置"""

    # IP 级别限制（默认每分钟 60 个请求）
    IP_RATE_LIMIT = int(os.environ.get("BA_RATE_LIMIT_IP_PER_MINUTE", "60"))
    IP_RATE_WINDOW = 60  # 秒

    # 用户级别限制（默认每分钟 120 个请求）
    USER_RATE_LIMIT = int(os.environ.get("BA_RATE_LIMIT_USER_PER_MINUTE", "120"))
    USER_RATE_WINDOW = 60  # 秒

    # 突发流量缓冲（允许短时间内的突发流量）
    BURST_SIZE = int(os.environ.get("BA_RATE_LIMIT_BURST", "10"))

    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        return cls()


# ===== 速率限制检查器 =====

class RateLimiter:
    """速率限制器（令牌桶算法）"""

    def __init__(
        self,
        rate: int,  # 每秒生成的令牌数
        capacity: int,  # 桶容量
        storage: RateLimitStorage = None
    ):
        self.rate = rate
        self.capacity = capacity
        self.storage = storage or rate_limit_storage

    def is_allowed(
        self,
        key: str,
        is_user: bool = False,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Dict[str, float]]:
        """
        检查是否允许请求

        Args:
            key: 限制键（IP 或用户 ID）
            is_user: 是否为用户限制
            current_time: 当前时间戳

        Returns:
            (是否允许, 限制信息)
        """
        if current_time is None:
            current_time = time.time()

        # 获取当前令牌数和最后更新时间
        if is_user:
            tokens, last_update = self.storage.get_user_tokens(key)
        else:
            tokens, last_update = self.storage.get_ip_tokens(key)

        # 计算新增的令牌数
        time_passed = current_time - last_update
        new_tokens = time_passed * self.rate

        # 更新令牌数（不超过容量）
        tokens = min(tokens + new_tokens, self.capacity)

        # 检查是否有足够的令牌
        if tokens >= 1:
            tokens -= 1
            is_allowed = True
        else:
            is_allowed = False

        # 保存更新后的令牌数
        if is_user:
            self.storage.set_user_tokens(key, tokens, current_time)
        else:
            self.storage.set_ip_tokens(key, tokens, current_time)

        # 计算限制信息
        info = {
            "tokens": tokens,
            "capacity": self.capacity,
            "rate": self.rate,
            "retry_after": max(0, (1 - tokens) / self.rate) if not is_allowed else 0
        }

        return is_allowed, info


# ===== 速率限制中间件 =====

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件

    对所有 API 请求应用速率限制，支持 IP 级别和用户级别的限制。
    """

    def __init__(
        self,
        app,
        ip_rate: int = None,
        ip_window: int = None,
        user_rate: int = None,
        user_window: int = None,
        enabled_paths: Optional[list] = None,
        excluded_paths: Optional[list] = None
    ):
        """
        初始化速率限制中间件

        Args:
            app: FastAPI 应用
            ip_rate: IP 级别速率（请求/分钟）
            ip_window: IP 级别时间窗口（秒）
            user_rate: 用户级别速率（请求/分钟）
            user_window: 用户级别时间窗口（秒）
            enabled_paths: 启用限制的路径列表（None 表示所有）
            excluded_paths: 排除限制的路径列表
        """
        super().__init__(app)

        self.ip_rate = (ip_rate or RateLimitConfig.IP_RATE_LIMIT) / 60  # 转换为每秒
        self.ip_capacity = RateLimitConfig.IP_RATE_LIMIT + RateLimitConfig.BURST_SIZE
        self.user_rate = (user_rate or RateLimitConfig.USER_RATE_LIMIT) / 60
        self.user_capacity = RateLimitConfig.USER_RATE_LIMIT + RateLimitConfig.BURST_SIZE

        self.enabled_paths = set(enabled_paths or [])
        self.excluded_paths = set(excluded_paths or [
            "/docs",  # Swagger UI
            "/redoc",  # ReDoc
            "/openapi.json",  # OpenAPI schema
            "/api/v1/health",  # 健康检查
            "/",  # 根路径
            "/api/v1/auth/login",  # 登录
        ])

        # 创建速率限制器
        self.ip_limiter = RateLimiter(self.ip_rate, self.ip_capacity)
        self.user_limiter = RateLimiter(self.user_rate, self.user_capacity)

        logger.info(
            f"速率限制中间件已启用: IP={int(self.ip_rate * 60)}/min, "
            f"User={int(self.user_rate * 60)}/min"
        )

    async def dispatch(self, request: Request, call_next):
        """
        处理请求，应用速率限制

        Args:
            request: 请求对象
            call_next: 下一个中间件/处理器

        Returns:
            响应对象
        """
        # 检查是否需要应用速率限制
        path = request.url.path

        # 如果是排除的路径，直接通过
        if path in self.excluded_paths:
            return await call_next(request)

        # 如果有启用路径列表，检查是否在其中
        if self.enabled_paths and path not in self.enabled_paths:
            return await call_next(request)

        current_time = time.time()

        # 获取 IP
        client_ip = self._get_client_ip(request)

        # IP 级别限制检查
        ip_allowed, ip_info = self.ip_limiter.is_allowed(
            client_ip,
            is_user=False,
            current_time=current_time
        )

        if not ip_allowed:
            logger.warning(f"IP 速率限制触发: {client_ip}")
            return self._rate_limit_response(
                limit_type="ip",
                retry_after=ip_info["retry_after"],
                limit=int(self.ip_rate * 60)
            )

        # 用户级别限制检查（如果有认证信息）
        user_id = self._get_user_id(request)
        if user_id:
            user_allowed, user_info = self.user_limiter.is_allowed(
                user_id,
                is_user=True,
                current_time=current_time
            )

            if not user_allowed:
                logger.warning(f"用户速率限制触发: {user_id}")
                return self._rate_limit_response(
                    limit_type="user",
                    retry_after=user_info["retry_after"],
                    limit=int(self.user_rate * 60)
                )

        # 添加速率限制响应头
        response = await call_next(request)
        response.headers["X-RateLimit-IP-Limit"] = str(int(self.ip_rate * 60))
        response.headers["X-RateLimit-IP-Remaining"] = str(int(ip_info["tokens"]))
        response.headers["X-RateLimit-User-Limit"] = str(int(self.user_rate * 60))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP 地址"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _get_user_id(self, request: Request) -> Optional[str]:
        """从请求中获取用户 ID"""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # 简单提取用户 ID（实际应该解码 JWT）
                # 这里我们依赖后续的认证中间件来处理
                return None  # 让认证中间件处理
            except Exception:
                pass

        return None

    def _rate_limit_response(
        self,
        limit_type: str,
        retry_after: float,
        limit: int
    ) -> JSONResponse:
        """创建速率限制响应"""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"{limit_type.upper()}: 请求过于频繁，请稍后再试",
                    "limit_type": limit_type,
                    "retry_after": round(retry_after, 1),
                    "limit": limit
                }
            },
            headers={
                "Retry-After": str(int(retry_after)),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + retry_after))
            }
        )


# ===== 装饰器版本速率限制 =====

def rate_limit(
    requests: int = 60,
    window: int = 60,
    key_func: Optional[Callable[[Request], str]] = None
):
    """
    速率限制装饰器

    Args:
        requests: 时间窗口内允许的请求数
        window: 时间窗口（秒）
        key_func: 自定义键生成函数

    Returns:
        装饰器函数
    """
    from functools import wraps

    limiter = RateLimiter(requests / window, requests)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 尝试从参数中获取 Request
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request is None:
                return await func(*args, **kwargs)

            # 生成限制键
            if key_func:
                key = key_func(request)
            else:
                key = request.client.host or "unknown"

            # 检查限制
            is_allowed, _ = limiter.is_allowed(key)

            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="请求过于频繁，请稍后再试",
                    code="RATE_LIMIT_EXCEEDED"
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "RateLimitMiddleware",
    "RateLimitConfig",
    "RateLimiter",
    "RateLimitStorage",
    "rate_limit",
]
