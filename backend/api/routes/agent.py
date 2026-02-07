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


class ToolCallInfo(BaseModel):
    """工具调用信息"""
    tool: str = Field(description="工具名称")
    input: Dict[str, Any] = Field(description="工具输入")
    output: Optional[str] = Field(None, description="工具输出")
    duration_ms: Optional[float] = Field(None, description="执行耗时（毫秒）")


class AgentQueryResponse(BaseModel):
    """Agent 查询响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class ConversationHistoryResponse(BaseModel):
    """对话历史响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


# ===== 端点 =====

@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest):
    """
    Agent 查询接口

    处理用户查询并返回 Agent 响应
    """
    try:
        # 检查是否有 BAAgent 实例
        app_state = get_app_state()
        agent = app_state.get("agent")

        if not agent:
            raise HTTPException(
                status_code=503,
                detail="Agent 服务未初始化，请稍后重试"
            )

        # 构建消息
        messages = []
        if request.file_context and "file_id" in request.file_context:
            # 添加文件上下文到消息中
            file_ref = f"upload:{request.file_context['file_id']}"
            messages.append({
                "role": "system",
                "content": f"用户已上传文件，文件引用: {file_ref}"
            })

        messages.append({
            "role": "user",
            "content": request.message
        })

        # 调用 Agent
        logger.info(f"Agent 查询: conversation_id={request.conversation_id}, message={request.message[:100]}...")

        # TODO: 实际调用 BAAgent
        # result = agent.invoke(
        #     messages=messages,
        #     conversation_id=request.conversation_id,
        #     session_id=request.session_id
        # )

        # 模拟响应（待 BAAgent 集成后移除）
        result = {
            "response": f"这是对 '{request.message}' 的模拟响应。BAAgent 集成后将返回实际分析结果。",
            "conversation_id": request.conversation_id or "conv_new",
            "tool_calls": [],
            "artifacts": []
        }

        logger.info(f"Agent 响应: conversation_id={result.get('conversation_id')}")

        return AgentQueryResponse(data=result)

    except HTTPException:
        raise
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
        # TODO: 从 MemoryStore 或数据库获取对话历史
        # 这里返回模拟数据

        messages = [
            {
                "role": "user",
                "content": "你好",
                "timestamp": "2026-02-07T10:00:00Z"
            },
            {
                "role": "assistant",
                "content": "你好！我是商业分析助手，有什么可以帮您的？",
                "timestamp": "2026-02-07T10:00:01Z"
            }
        ]

        result = {
            "conversation_id": conversation_id,
            "total_messages": len(messages),
            "messages": messages[:limit]
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
        # TODO: 更新对话状态
        logger.info(f"结束对话: {conversation_id}")

        return {
            "success": True,
            "message": "对话已结束",
            "conversation_id": conversation_id
        }

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

        status = {
            "agent_initialized": "agent" in app_state,
            "filestore_initialized": "file_store" in app_state,
            "active_conversations": 0,  # TODO: 实际统计
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
