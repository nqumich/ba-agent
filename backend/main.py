"""
BA-Agent FastAPI 服务入口

提供 HTTP API 供前端对话调用
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 延迟导入，避免启动时加载过重
_agent = None


def get_agent():
    """获取单例 Agent 实例（懒加载）"""
    global _agent
    if _agent is None:
        from backend.agents.agent import create_agent
        _agent = create_agent()
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时预加载可选的 Agent（可选，也可首次请求时再加载）"""
    yield
    # shutdown: 如需清理可在此执行
    global _agent
    _agent = None


app = FastAPI(
    title="BA-Agent API",
    description="商业分析助手 Agent HTTP 接口",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
def catch_all_exception_handler(request, exc: Exception):
    """任何未捕获异常都返回 200 + JSON，避免前端只看到 500 Internal Server Error。"""
    logger.exception("unhandled exception")
    return JSONResponse(
        status_code=200,
        content={
            "response": f"请求处理失败：{str(exc)}",
            "success": False,
            "conversation_id": "",
            "timestamp": "",
        },
    )


# 最外层中间件：捕获所有未处理异常，统一返回 200+JSON，绝不返回 500
class No500Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception("middleware caught exception")
            return JSONResponse(
                status_code=200,
                content={
                    "response": f"请求处理失败：{str(e)}",
                    "success": False,
                    "conversation_id": "",
                    "timestamp": "",
                },
            )


# CORS：允许前端开发服务器
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://localhost:8080,http://localhost:8081,http://localhost:8082").split(",")
app.add_middleware(No500Middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 请求/响应模型 ----------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入消息")
    conversation_id: Optional[str] = Field(None, description="会话 ID，不传则新建会话")
    user_id: Optional[str] = Field(None, description="用户 ID")


class ChatResponse(BaseModel):
    response: str
    success: bool
    conversation_id: str
    timestamp: str


# ---------- 路由 ----------

@app.get("/health")
def health():
    """健康检查（供 docker-compose / 负载均衡使用）"""
    return {"status": "ok"}


@app.get("/api/v1/chat/debug")
def chat_debug():
    """始终返回 200，用于确认当前运行的是本 main.py。若此接口返回 200 则说明后端入口正确。"""
    return JSONResponse(
        status_code=200,
        content={
            "response": "[debug] 后端 main.py 已加载，聊天接口可用",
            "success": True,
            "conversation_id": "",
            "timestamp": "",
        },
    )


def _chat_response(response: str, success: bool, conversation_id: str = "", timestamp: str = ""):
    """统一返回 200 + JSON，绝不返回 5xx。"""
    return JSONResponse(
        status_code=200,
        content={
            "response": str(response),
            "success": bool(success),
            "conversation_id": str(conversation_id or ""),
            "timestamp": str(timestamp or ""),
        },
    )


@app.post("/api/v1/chat")
async def chat(request: Request):
    """
    发送一条消息，返回 Agent 回复。
    使用原始 Request，手动解析 body，确保任何异常都返回 200+JSON，绝不返回 500。
    """
    try:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("chat body parse failed: %s", e)
            return _chat_response(f"请求体解析失败：{e}", False)

        message = (body.get("message") or "").strip()
        if not message:
            return _chat_response("消息不能为空", False)

        conversation_id = body.get("conversation_id")
        user_id = body.get("user_id")

        try:
            agent = get_agent()
            result = agent.invoke(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
            )
            return _chat_response(
                response=result.get("response") or "",
                success=bool(result.get("success", False)),
                conversation_id=result.get("conversation_id") or "",
                timestamp=result.get("timestamp") or "",
            )
        except Exception as e:
            logger.exception("chat request failed")
            return _chat_response(f"请求处理失败：{str(e)}", False)
    except BaseException as e:
        logger.exception("chat unexpected error")
        return _chat_response(f"请求处理失败：{str(e)}", False)
