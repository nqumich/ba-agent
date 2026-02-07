"""
BA-Agent FastAPI 服务

提供 REST API 接口用于文件上传、Agent 查询、Skills 管理等功能
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from backend.api.routes import files, agent, skills, health
from backend.api.state import set_app_state
from backend.filestore import get_file_store
from backend.skills import SkillLoader, SkillRegistry, SkillActivator
from pathlib import Path

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
        skill_activator = SkillActivator(skill_registry)

        set_app_state("skill_registry", skill_registry)
        set_app_state("skill_activator", skill_activator)
        set_app_state("skill_loader", skill_loader)

        # 预加载 Skills 元数据
        all_metadata = skill_registry.get_all_metadata()
        logger.info(f"Skills 系统初始化完成，已加载 {len(all_metadata)} 个 Skills")

        logger.info("BA-Agent API 服务启动完成")

        yield

    finally:
        # 关闭时清理
        logger.info("BA-Agent API 服务关闭中...")

        from backend.api.state import get_app_state
        app_state = get_app_state()

        if "file_store" in app_state:
            app_state["file_store"].close()

        logger.info("BA-Agent API 服务已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="BA-Agent API",
    description="商业分析助手 Agent - REST API 服务",
    version="2.1.0",
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


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": str(exc) if logger.isEnabledFor(logging.DEBUG) else None
            }
        }
    )


# 注册路由
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["健康检查"]
)

app.include_router(
    files.router,
    prefix="/api/v1/files",
    tags=["文件管理"]
)

app.include_router(
    agent.router,
    prefix="/api/v1/agent",
    tags=["Agent 交互"]
)

app.include_router(
    skills.router,
    prefix="/api/v1/skills",
    tags=["Skills 管理"]
)


# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "BA-Agent API",
        "version": "2.1.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/v1/health",
            "files": "/api/v1/files",
            "agent": "/api/v1/agent",
            "skills": "/api/v1/skills"
        }
    }


from backend.api.state import get_app_state

__all__ = ["app", "get_app_state"]
