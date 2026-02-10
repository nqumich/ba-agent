"""
BA-Agent FastAPI 服务

提供 REST API 接口用于文件上传、Agent 查询、Skills 管理等功能
包含 JWT 认证、速率限制、日志记录等增强功能。
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager
import os

from backend.api.routes import files, agent, skills, health
from backend.api.routes.monitoring import router as monitoring_router
from backend.api.state import set_app_state
from backend.api.auth import auth_router
from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.errors import (
    api_exception_handler,
    http_exception_handler,
    global_exception_handler,
    LoggingMiddleware,
    APIException
)
from backend.api.logging_config import setup_logging
from dotenv import load_dotenv
from backend.filestore import get_file_store

# 加载 .env 文件
load_dotenv()
from backend.skills import SkillLoader, SkillRegistry, SkillActivator
from pathlib import Path

# 设置日志
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "api.log")
setup_logging(log_level=LOG_LEVEL, log_file=LOG_FILE)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("BA-Agent API 服务启动中...")

    try:
        # 初始化 FileStore
        file_store = get_file_store()
        set_app_state("file_store", file_store)
        logger.info("FileStore 初始化完成")

        # 初始化 Skills 系统
        skills_dirs = [
            Path("skills"),
            Path(".claude/skills")
        ]
        skill_loader = SkillLoader(skills_dirs)
        skill_registry = SkillRegistry(skill_loader)
        skill_activator = SkillActivator(skill_loader, skill_registry)

        set_app_state("skill_registry", skill_registry)
        set_app_state("skill_activator", skill_activator)
        set_app_state("skill_loader", skill_loader)

        # 预加载 Skills 元数据
        all_metadata = skill_registry.get_all_metadata()
        logger.info(f"Skills 系统初始化完成，已加载 {len(all_metadata)} 个 Skills")

        # 启动数据库定期清理任务
        try:
            from tools.database import start_periodic_cleanup
            start_periodic_cleanup()
            logger.info("数据库定期清理任务已启动")
        except Exception as e:
            logger.warning(f"启动数据库清理任务失败: {e}")

        logger.info("BA-Agent API 服务启动完成")

        yield

    finally:
        # 关闭时清理
        logger.info("BA-Agent API 服务关闭中...")

        from backend.api.state import get_app_state
        app_state = get_app_state()

        if "file_store" in app_state:
            app_state["file_store"].close()

        # 关闭数据库连接并清理文件
        try:
            from tools.database import _close_connections
            _close_connections()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接时出错: {e}")

        logger.info("BA-Agent API 服务已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="BA-Agent API",
    description="商业分析助手 Agent - REST API 服务",
    version="2.2.0",  # 更新版本号
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 日志中间件
app.add_middleware(LoggingMiddleware, log_level="INFO")

# 速率限制中间件
app.add_middleware(
    RateLimitMiddleware,
    ip_rate=60,  # 每分钟 60 个请求
    user_rate=120,  # 每分钟 120 个请求
)


# ===== 异常处理 =====

@app.exception_handler(APIException)
async def api_exception_handler_wrapper(request: Request, exc: APIException):
    """API 异常处理"""
    return await api_exception_handler(request, exc)


@app.exception_handler(Exception)
async def global_exception_handler_wrapper(request: Request, exc: Exception):
    """全局异常处理"""
    return await global_exception_handler(request, exc)


# ===== 注册路由 =====

# 健康检查（无需认证）
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["健康检查"]
)

# 认证路由
app.include_router(
    auth_router,
    prefix="/api/v1",
    tags=["认证"]
)

# 文件管理（需要认证）
app.include_router(
    files.router,
    prefix="/api/v1/files",
    tags=["文件管理"]
)

# Agent 交互（需要认证）
app.include_router(
    agent.router,
    prefix="/api/v1/agent",
    tags=["Agent 交互"]
)

# Skills 管理（需要认证）
app.include_router(
    skills.router,
    prefix="/api/v1/skills",
    tags=["Skills 管理"]
)

# 监控和调试（需要认证）
app.include_router(
    monitoring_router,
    prefix="/api/v1",
    tags=["监控和调试"]
)


# ===== 根路径 =====

from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

frontend_path = Path(__file__).parent.parent.parent / "coco-frontend" / "index.html"
monitoring_path = Path(__file__).parent.parent.parent / "coco-frontend" / "monitoring" / "index.html"

@app.get("/", response_class=HTMLResponse)
async def root():
    """前端页面"""
    if frontend_path.exists():
        with open(frontend_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>前端文件不存在</h1>", status_code=404)

@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring():
    """监控仪表板页面"""
    if monitoring_path.exists():
        with open(monitoring_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>监控仪表板文件不存在</h1>", status_code=404)


# ---------- 简易聊天接口（与 backend.main 一致，供前端 ChatInterface 使用，绝不返回 500）----------
_CHAT_AGENT = None

def _get_chat_agent():
    global _CHAT_AGENT
    if _CHAT_AGENT is None:
        from backend.agents.agent import create_agent
        _CHAT_AGENT = create_agent()
    return _CHAT_AGENT

def _chat_json(response: str, success: bool, conversation_id: str = "", timestamp: str = ""):
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
async def chat_simple(request: Request):
    """
    简易聊天接口，与 backend.main 的 /api/v1/chat 行为一致。
    不校验 JWT，任何异常均返回 200+JSON，绝不返回 500。
    """
    try:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("chat body parse failed: %s", e)
            return _chat_json(f"请求体解析失败：{e}", False)
        message = (body.get("message") or "").strip()
        if not message:
            return _chat_json("消息不能为空", False)
        conversation_id = body.get("conversation_id")
        user_id = body.get("user_id")
        try:
            agent = _get_chat_agent()
            result = agent.invoke(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
            )
            return _chat_json(
                response=result.get("response") or "",
                success=bool(result.get("success", False)),
                conversation_id=result.get("conversation_id") or "",
                timestamp=result.get("timestamp") or "",
            )
        except Exception as e:
            logger.exception("chat request failed")
            return _chat_json(f"请求处理失败：{str(e)}", False)
    except BaseException as e:
        logger.exception("chat unexpected error")
        return _chat_json(f"请求处理失败：{str(e)}", False)


@app.get("/api")
async def api_info():
    """API 信息"""
    return {
        "name": "BA-Agent API",
        "version": "2.2.0",
        "status": "running",
        "docs": "/docs",
        "features": [
            "JWT 认证",
            "速率限制",
            "请求日志",
            "文件管理",
            "Agent 交互",
            "Skills 管理"
        ],
        "endpoints": {
            "health": "/api/v1/health",
            "auth": "/api/v1/auth",
            "chat": "/api/v1/chat",
            "files": "/api/v1/files",
            "agent": "/api/v1/agent",
            "skills": "/api/v1/skills"
        }
    }


from backend.api.state import get_app_state

__all__ = ["app", "get_app_state"]
