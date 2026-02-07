"""
Agent 交互路由

处理 Agent 查询、对话等
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from backend.api.state import get_app_state

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== 请求/响应模型 =====

class AgentQueryRequest(BaseModel):
    """Agent 查询请求"""
    message: str = Field(..., description="用户消息", min_length=1, max_length=10000)
    conversation_id: Optional[str] = Field(None, description="对话 ID")
    file_context: Optional[Dict[str, Any]] = Field(None, description="文件上下文")
    session_id: Optional[str] = Field(None, description="会话 ID")
    user_id: Optional[str] = Field(None, description="用户 ID")


class AgentQueryResponse(BaseModel):
    """Agent 查询响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class ConversationHistoryResponse(BaseModel):
    """对话历史响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


# ===== 辅助函数 =====

def _get_agent_service():
    """获取 BAAgentService 实例"""
    app_state = get_app_state()
    service = app_state.get("agent_service")
    if not service:
        # 延迟初始化
        from backend.api.services.ba_agent import BAAgentService
        service = BAAgentService()
        app_state["agent_service"] = service
        logger.info("BAAgentService 初始化完成")
    return service


# ===== 端点 =====

@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest):
    """
    Agent 查询接口

    处理用户查询并返回 Agent 响应
    """
    try:
        service = _get_agent_service()

        # 调用 Agent 查询
        result = await service.query(
            message=request.message,
            conversation_id=request.conversation_id,
            file_context=request.file_context,
            session_id=request.session_id,
            user_id=request.user_id
        )

        logger.info(f"Agent 响应: conversation_id={result.get('conversation_id')}")

        return AgentQueryResponse(data=result)

    except Exception as e:
        logger.error(f"Agent 查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent 查询失败: {str(e)}"
        )


@router.post("/conversation/start", response_model=AgentQueryResponse)
async def start_conversation(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    开始新对话

    创建新的对话会话并返回 conversation_id
    """
    try:
        import uuid
        from datetime import datetime

        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        result = {
            "conversation_id": conversation_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id or "anonymous",
            "session_id": session_id or "default",
            "status": "active"
        }

        logger.info(f"创建新对话: {conversation_id}")

        return AgentQueryResponse(data=result)

    except Exception as e:
        logger.error(f"创建对话失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"创建对话失败: {str(e)}"
        )


@router.get("/conversation/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    limit: int = 50
):
    """
    获取对话历史

    返回指定对话的消息历史
    """
    try:
        service = _get_agent_service()
        history = service.get_conversation_history(conversation_id, limit)

        result = {
            "conversation_id": conversation_id,
            "total_messages": len(history),
            "messages": history[:limit]
        }

        return ConversationHistoryResponse(data=result)

    except Exception as e:
        logger.error(f"获取对话历史失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取对话历史失败: {str(e)}"
        )


@router.delete("/conversation/{conversation_id}")
async def end_conversation(conversation_id: str):
    """
    结束对话

    标记对话为已结束状态
    """
    try:
        service = _get_agent_service()
        success = service.end_conversation(conversation_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"对话不存在: {conversation_id}"
            )

        return {
            "success": True,
            "message": "对话已结束",
            "conversation_id": conversation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"结束对话失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"结束对话失败: {str(e)}"
        )


@router.get("/status")
async def get_agent_status():
    """
    获取 Agent 服务状态

    返回 Agent 服务的当前状态信息
    """
    try:
        app_state = get_app_state()

        # 获取服务状态
        service = _get_agent_service()
        service_status = service.get_status()

        status = {
            "agent_initialized": service_status["agent_initialized"],
            "filestore_initialized": "file_store" in app_state,
            "skills_initialized": "skill_registry" in app_state,
            "active_conversations": service_status["active_conversations"],
            "total_conversations": service_status["total_conversations"],
            "model_name": service_status["model_name"],
            "version": "2.1.0"
        }

        return status

    except Exception as e:
        logger.error(f"获取 Agent 状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取 Agent 状态失败: {str(e)}"
        )


__all__ = ["router"]
