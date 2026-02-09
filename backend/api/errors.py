"""
API 错误处理模块

提供统一的错误处理、异常类和错误响应格式。
"""

import logging
import time
import traceback
from typing import Optional, Dict, Any, Union
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ===== 错误代码定义 =====

class ErrorCode:
    """标准错误代码"""

    # 认证/授权错误
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # 客户端错误
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # 服务端错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"

    # 业务错误
    BUSINESS_ERROR = "BUSINESS_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INVALID_OPERATION = "INVALID_OPERATION"


# ===== 自定义异常 =====

class APIException(Exception):
    """
    API 异常基类

    用于抛出带有结构化错误信息的异常。
    """

    def __init__(
        self,
        message: str,
        code: str = ErrorCode.INTERNAL_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationException(APIException):
    """验证错误"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=error_details
        )


class NotFoundException(APIException):
    """资源未找到错误"""

    def __init__(
        self,
        message: str,
        resource_type: str = "Resource",
        resource_id: Optional[str] = None
    ):
        details = {"resource_type": resource_type}
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class BusinessException(APIException):
    """业务逻辑错误"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.BUSINESS_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details or {}
        )


class UnauthorizedException(APIException):
    """未授权错误"""

    def __init__(
        self,
        message: str = "未授权访问",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHORIZED,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details or {}
        )


class ForbiddenException(APIException):
    """禁止访问错误"""

    def __init__(
        self,
        message: str = "没有权限访问此资源",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details or {}
        )


# ===== 错误响应模型 =====

class ErrorDetail(BaseModel):
    """错误详情"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: ErrorDetail


# ===== 错误处理函数 =====

def error_response(
    message: str,
    code: str = ErrorCode.INTERNAL_ERROR,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    details: Optional[Dict[str, Any]] = None,
    include_stack: bool = False
) -> JSONResponse:
    """
    创建错误响应

    Args:
        message: 错误消息
        code: 错误代码
        status_code: HTTP 状态码
        details: 错误详情
        include_stack: 是否包含堆栈跟踪

    Returns:
        JSON 响应
    """
    error_detail = {
        "code": code,
        "message": message,
        "details": details
    }

    if include_stack and logger.isEnabledFor(logging.DEBUG):
        error_detail["stack_trace"] = traceback.format_exc()

    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=ErrorDetail(**error_detail)).model_dump()
    )


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """
    API 异常处理器

    Args:
        request: 请求对象
        exc: API 异常

    Returns:
        错误响应
    """
    logger.error(f"API 异常: {exc.message}", exc_info=True)

    return error_response(
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
        include_stack=True
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    HTTP 异常处理器

    Args:
        request: 请求对象
        exc: HTTP 异常

    Returns:
        错误响应
    """
    logger.warning(f"HTTP 异常: {exc.status_code} - {exc.detail}")

    # 从 detail 中提取错误代码
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    code = ErrorCode.INTERNAL_ERROR

    # 尝试从 detail 中解析错误代码
    if hasattr(exc, "code") and exc.code:
        code = exc.code

    return error_response(
        message=detail,
        code=code,
        status_code=exc.status_code
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理器

    Args:
        request: 请求对象
        exc: 异常对象

    Returns:
        错误响应
    """
    logger.error(f"未处理的异常: {exc}", exc_info=True)

    return error_response(
        message="服务器内部错误",
        code=ErrorCode.INTERNAL_ERROR,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        include_stack=True
    )


# ===== 请求日志中间件 =====

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    记录所有 API 请求和响应的详细信息。
    """

    def __init__(self, app, log_level: str = "INFO"):
        """
        初始化日志中间件

        Args:
            app: FastAPI 应用
            log_level: 日志级别
        """
        super().__init__(app)
        self.log_level = getattr(logging, log_level.upper())
        self.logger = logging.getLogger(__name__)

    async def dispatch(self, request: Request, call_next):
        """
        处理请求，记录日志

        Args:
            request: 请求对象
            call_next: 下一个中间件/处理器

        Returns:
            响应对象
        """
        start_time = time.time()

        # 记录请求信息
        if self.logger.isEnabledFor(logging.INFO):
            self.logger.info(
                f"请求: {request.method} {request.url.path} "
                f"from {self._get_client_ip(request)}"
            )

        # 处理请求
        try:
            response = await call_next(request)
        except Exception as exc:
            # 记录异常
            self.logger.error(
                f"请求异常: {request.method} {request.url.path} - {exc}",
                exc_info=True
            )
            raise

        # 计算处理时间
        process_time = (time.time() - start_time) * 1000

        # 记录响应信息
        if self.logger.isEnabledFor(logging.INFO):
            self.logger.info(
                f"响应: {request.method} {request.url.path} "
                f"status={response.status_code} "
                f"time={process_time:.2f}ms"
            )

        # 添加处理时间响应头
        response.headers["X-Process-Time"] = f"{process_time:.2f}"

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


__all__ = [
    "ErrorCode",
    "APIException",
    "ValidationException",
    "NotFoundException",
    "BusinessException",
    "UnauthorizedException",
    "ForbiddenException",
    "ErrorResponse",
    "ErrorDetail",
    "error_response",
    "api_exception_handler",
    "http_exception_handler",
    "global_exception_handler",
    "LoggingMiddleware",
]
