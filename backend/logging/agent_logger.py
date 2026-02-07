"""
Agent Logger - 后端日志系统

按模型上下文轮次记录：
1. 模型输入 (user message, system prompt)
2. 模型输出 (raw response)
3. 工程后端处理 (tool calls, code management, etc.)

日志格式：
- 每个会话一个日志文件
- 按轮次分组
- 区分模型内容和工程处理
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field

from backend.api.state import get_app_state


@dataclass
class ModelInput:
    """模型输入记录"""
    timestamp: str
    round: int
    role: str  # "system" or "user"
    content: str
    token_count: Optional[int] = None


@dataclass
class ModelOutput:
    """模型输出记录"""
    timestamp: str
    round: int
    raw_content: str
    token_count: Optional[int] = None
    structured_response: Optional[Dict[str, Any]] = None
    parsing_success: bool = True


@dataclass
class BackendProcessing:
    """后端处理记录"""
    timestamp: str
    round: int
    processing_type: str  # "tool_call", "code_management", "response_parsing", etc.
    details: Dict[str, Any]
    duration_ms: Optional[float] = None


@dataclass
class RoundLog:
    """单轮次日志"""
    round: int
    start_time: str
    end_time: Optional[str] = None
    inputs: List[ModelInput] = field(default_factory=list)
    outputs: List[ModelOutput] = field(default_factory=list)
    backend_processing: List[BackendProcessing] = field(default_factory=list)


@dataclass
class ConversationLog:
    """完整对话日志"""
    conversation_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    start_time: str = None
    end_time: Optional[str] = None
    rounds: List[RoundLog] = field(default_factory=list)

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.utcnow().isoformat() + "Z"


class AgentLogger:
    """
    Agent 后端日志系统

    使用方式：
    ```python
    logger = AgentLogger(conversation_id, session_id, user_id)

    # 记录模型输入
    logger.log_model_input(round=1, role="user", content="分析销售数据")

    # 记录模型输出
    logger.log_model_output(round=1, raw_content="{...}", structured_response={...})

    # 记录后端处理
    logger.log_backend_processing(round=1, processing_type="tool_call", details={...})

    # 完成后保存
    logger.save()
    ```
    """

    def __init__(
        self,
        conversation_id: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """
        初始化 AgentLogger

        Args:
            conversation_id: 对话 ID
            session_id: 会话 ID
            user_id: 用户 ID
        """
        self.conversation_id = conversation_id
        self.session_id = session_id
        self.user_id = user_id

        self.conversation_log = ConversationLog(
            conversation_id=conversation_id,
            session_id=session_id,
            user_id=user_id
        )

        # 获取日志目录
        try:
            app_state = get_app_state()
            file_store = app_state.get("file_store")
            if file_store:
                self.log_dir = file_store.storage_dir / "logs"
            else:
                self.log_dir = Path("/tmp/ba-agent/logs")
        except:
            self.log_dir = Path("/tmp/ba-agent/logs")

        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_or_create_round(self, round: int) -> RoundLog:
        """获取或创建轮次日志"""
        for round_log in self.conversation_log.rounds:
            if round_log.round == round:
                return round_log

        # 创建新轮次
        new_round = RoundLog(
            round=round,
            start_time=datetime.utcnow().isoformat() + "Z"
        )
        self.conversation_log.rounds.append(new_round)
        return new_round

    def log_model_input(
        self,
        round: int,
        role: str,
        content: str,
        token_count: Optional[int] = None
    ):
        """
        记录模型输入

        Args:
            round: 轮次
            role: 角色 (system/user)
            content: 输入内容
            token_count: Token 数量（可选）
        """
        round_log = self._get_or_create_round(round)

        input_log = ModelInput(
            timestamp=datetime.utcnow().isoformat() + "Z",
            round=round,
            role=role,
            content=content,
            token_count=token_count
        )
        round_log.inputs.append(input_log)

    def log_model_output(
        self,
        round: int,
        raw_content: str,
        token_count: Optional[int] = None,
        structured_response: Optional[Dict[str, Any]] = None,
        parsing_success: bool = True
    ):
        """
        记录模型输出

        Args:
            round: 轮次
            raw_content: 原始输出内容
            token_count: Token 数量（可选）
            structured_response: 解析后的结构化响应
            parsing_success: 是否解析成功
        """
        round_log = self._get_or_create_round(round)

        output_log = ModelOutput(
            timestamp=datetime.utcnow().isoformat() + "Z",
            round=round,
            raw_content=raw_content,
            token_count=token_count,
            structured_response=structured_response,
            parsing_success=parsing_success
        )
        round_log.outputs.append(output_log)

    def log_backend_processing(
        self,
        round: int,
        processing_type: str,
        details: Dict[str, Any],
        duration_ms: Optional[float] = None
    ):
        """
        记录后端处理

        Args:
            round: 轮次
            processing_type: 处理类型
                - "tool_call": 工具调用
                - "code_management": 代码管理
                - "response_parsing": 响应解析
                - "code_saved": 代码保存
                - "code_retrieved": 代码检索
                - "context_cleaned": 上下文清理
            details: 处理详情
            duration_ms: 处理耗时（毫秒）
        """
        round_log = self._get_or_create_round(round)

        processing_log = BackendProcessing(
            timestamp=datetime.utcnow().isoformat() + "Z",
            round=round,
            processing_type=processing_type,
            details=details,
            duration_ms=duration_ms
        )
        round_log.backend_processing.append(processing_log)

    def end_round(self, round: int):
        """结束一个轮次"""
        round_log = self._get_or_create_round(round)
        if round_log.end_time is None:
            round_log.end_time = datetime.utcnow().isoformat() + "Z"

    def save(self) -> Path:
        """
        保存日志到文件

        Returns:
            日志文件路径
        """
        # 设置结束时间
        self.conversation_log.end_time = datetime.utcnow().isoformat() + "Z"

        # 生成文件名: conversation_{id}_{timestamp}.jsonl
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{self.conversation_id}_{timestamp}.jsonl"
        file_path = self.log_dir / filename

        # 写入日志（JSONL 格式）
        with open(file_path, 'w', encoding='utf-8') as f:
            # 写入对话元数据
            metadata = {
                "type": "conversation_metadata",
                "conversation_id": self.conversation_log.conversation_id,
                "session_id": self.conversation_log.session_id,
                "user_id": self.conversation_log.user_id,
                "start_time": self.conversation_log.start_time,
                "end_time": self.conversation_log.end_time,
                "round_count": len(self.conversation_log.rounds)
            }
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')

            # 写入各轮次日志
            for round_log in self.conversation_log.rounds:
                # 轮次元数据
                round_metadata = {
                    "type": "round_metadata",
                    "round": round_log.round,
                    "start_time": round_log.start_time,
                    "end_time": round_log.end_time
                }
                f.write(json.dumps(round_metadata, ensure_ascii=False) + '\n')

                # 输入日志
                for input_log in round_log.inputs:
                    log_entry = {
                        "type": "model_input",
                        **asdict(input_log)
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

                # 输出日志
                for output_log in round_log.outputs:
                    log_entry = {
                        "type": "model_output",
                        **asdict(output_log)
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

                # 后端处理日志
                for processing_log in round_log.backend_processing:
                    log_entry = {
                        "type": "backend_processing",
                        **asdict(processing_log)
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        return file_path

    def get_summary(self) -> Dict[str, Any]:
        """
        获取日志摘要

        Returns:
            日志摘要统计
        """
        total_inputs = sum(len(r.inputs) for r in self.conversation_log.rounds)
        total_outputs = sum(len(r.outputs) for r in self.conversation_log.rounds)
        total_processing = sum(len(r.backend_processing) for r in self.conversation_log.rounds)

        # 统计各类型处理
        processing_types = {}
        for round_log in self.conversation_log.rounds:
            for proc in round_log.backend_processing:
                pt = proc.processing_type
                processing_types[pt] = processing_types.get(pt, 0) + 1

        return {
            "conversation_id": self.conversation_id,
            "round_count": len(self.conversation_log.rounds),
            "total_inputs": total_inputs,
            "total_outputs": total_outputs,
            "total_backend_processing": total_processing,
            "processing_types": processing_types
        }
