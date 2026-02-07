"""
Context Manager - 上下文管理器

统一处理所有与模型上下文相关的操作：
1. 文件内容清理（read_file 结果清理为梗概）
2. 文件上下文处理
3. 消息历史管理
4. 上下文压缩和总结

v1.4.0 变更：移除自动代码注入，改用模型主动调用 file_reader 工具
"""

import re
import logging
import ast
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextManager:
    """
    上下文管理器

    负责处理所有与模型上下文相关的操作
    """

    def __init__(self, file_store=None):
        """
        初始化上下文管理器

        Args:
            file_store: FileStore 实例，用于读取代码和上传文件
        """
        self.file_store = file_store
        self.code_store = file_store.code if file_store else None
        self.upload_store = file_store.upload if file_store else None

    # ===== 文件内容清理方法（v1.4.0 新增）=====

    def _is_read_file_result(self, msg: Dict[str, str]) -> bool:
        """
        检查消息是否来自 read_file 工具调用

        识别规则：tool_call_id 以 "call_read_file_" 开头

        Args:
            msg: 消息字典

        Returns:
            是否是 read_file 工具结果
        """
        tool_call_id = msg.get("tool_call_id", "")
        return tool_call_id.startswith("call_read_file_")

    def _parse_file_result(self, content: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
        """
        从 read_file 返回内容中解析文件路径、内容和元数据

        支持的格式：
        - JSON 格式：{"path": "...", "content": "...", "metadata": {...}}
        - 纯文本格式：直接返回文件内容

        Args:
            content: read_file 返回的内容

        Returns:
            (file_path, file_content, metadata) 元组
        """
        metadata = {}

        # 尝试解析 JSON 格式
        try:
            data = json.loads(content)
            file_path = data.get("path")
            file_content = data.get("content", "")
            metadata = data.get("metadata", {})
            return file_path, file_content, metadata
        except (json.JSONDecodeError, TypeError):
            pass

        # 纯文本格式，尝试从内容中提取路径信息
        # 常见格式："[文件] path/to/file.py\n..." 或 "文件 path/to/file.py:\n..."
        path_match = re.search(r'(?:文件|\[FILE\]|\[文件\])\s+([^\s\n]+)', content[:200])
        if path_match:
            file_path = path_match.group(1)
            file_content = content
            return file_path, file_content, metadata

        # 无法解析，返回原始内容
        return None, content, metadata

    def _generate_file_summary(self, file_path: str, file_content: str, metadata: Dict[str, Any]) -> str:
        """
        生成文件内容梗概（基于元数据，不使用 LLM）

        Args:
            file_path: 文件路径
            file_content: 文件内容
            metadata: 文件元数据

        Returns:
            文件梗概字符串
        """
        if not file_path:
            return "未知文件"

        # 获取文件扩展名
        ext = Path(file_path).suffix.lower()
        filename = Path(file_path).name

        # 计算文件大小
        size_bytes = len(file_content.encode('utf-8'))
        size_str = self._format_size(size_bytes)

        # 根据文件类型生成不同的梗概
        if ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.php', '.rb']:
            return self._generate_code_summary(filename, ext, file_content, metadata)
        elif ext in ['.csv', '.xlsx', '.xls']:
            return self._generate_data_summary(filename, ext, file_content, metadata)
        elif ext == '.json':
            return self._generate_json_summary(filename, file_content, metadata)
        else:
            # 默认格式
            file_type = ext[1:] if ext else 'text'
            return f"{filename} ({file_type}, {size_str})"

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"

    def _generate_code_summary(self, filename: str, ext: str, content: str, metadata: Dict[str, Any]) -> str:
        """生成代码文件梗概"""
        lines = content.count('\n') + 1

        # 提取函数和类信息
        functions = []
        classes = []

        if ext == '.py':
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions.append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        classes.append(node.name)
            except SyntaxError:
                pass

        # 构建梗概
        parts = [filename, f"({ext[1:]}", f"{lines}行"]

        if functions:
            func_list = ', '.join(functions[:5])  # 最多显示5个
            if len(functions) > 5:
                func_list += f" 等{len(functions)}个"
            parts.append(f"函数: {func_list}")

        if classes:
            class_list = ', '.join(classes[:3])  # 最多显示3个
            if len(classes) > 3:
                class_list += f" 等{len(classes)}个"
            parts.append(f"类: {class_list}")

        parts.append(")")
        return ' '.join(parts)

    def _generate_data_summary(self, filename: str, ext: str, content: str, metadata: Dict[str, Any]) -> str:
        """生成数据文件梗概"""
        lines = content.split('\n')
        row_count = len(lines)

        # 对于 CSV，尝试提取列名
        columns = []
        if ext == '.csv' and lines:
            first_line = lines[0]
            # 简单的逗号分隔
            columns = [col.strip().strip('"\'') for col in first_line.split(',')]

        parts = [filename, f"({ext[1:]}", f"{row_count}行"]

        if columns:
            col_list = ', '.join(columns[:5])  # 最多显示5列
            if len(columns) > 5:
                col_list += f" 等{len(columns)}列"
            parts.append(f"列: {col_list}")

        parts.append(")")
        return ' '.join(parts)

    def _generate_json_summary(self, filename: str, content: str, metadata: Dict[str, Any]) -> str:
        """生成 JSON 文件梗概"""
        try:
            data = json.loads(content)
            keys = []

            if isinstance(data, dict):
                keys = list(data.keys())[:5]  # 最多显示5个键
                if len(data) > 5:
                    keys.append(f"...等{len(data)}个")
            elif isinstance(data, list):
                keys = [f"数组({len(data)}项)"]

            key_str = ', '.join(str(k) for k in keys)
            return f"{filename} (JSON, 键: {key_str})"
        except (json.JSONDecodeError, TypeError):
            size_str = self._format_size(len(content.encode('utf-8')))
            return f"{filename} (JSON, {size_str})"

    def clean_file_contents(
        self,
        messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        清理 read_file 工具返回的文件内容，替换为梗概

        适用范围：代码文件、用户上传文件、中间过程文件

        清理策略：
        - 代码文件：保留文件标识 + 元数据（函数列表、类列表、行数等）
        - 数据文件（CSV/Excel）：保留文件标识 + 列信息 + 行数 + 数据预览
        - 中间文件：保留文件标识 + 文件类型 + 大小 + 简要描述

        梗概格式：
        [文件已读取] <filename> (<type>, <info>)

        示例：
        [文件已读取] sales_analysis.py (Python, 150行, 函数: load_data, clean_data, visualize)
        [文件已读取] data.csv (CSV, 5000行, 列: date, product, amount, region)
        [文件已读取] chart_result.json (JSON, 2.5KB, 包含图表配置数据)

        Args:
            messages: 原始消息列表

        Returns:
            清理后的消息列表
        """
        cleaned_messages = []
        cleaned_count = 0

        for msg in messages:
            content = msg.get("content", "")

            # 检查是否是 read_file 结果
            if self._is_read_file_result(msg):
                # 解析文件信息
                file_path, file_content, metadata = self._parse_file_result(content)

                if file_path:
                    # 生成梗概
                    summary = self._generate_file_summary(file_path, file_content or content, metadata)

                    # 替换内容为梗概
                    cleaned_messages.append({
                        **msg,
                        "content": f"[文件已读取] {summary}",
                        "cleaned": True
                    })
                    cleaned_count += 1
                    continue

            # 非 read_file 结果，保持原样
            cleaned_messages.append(msg)

        if cleaned_count > 0:
            logger.info(f"已清理 {cleaned_count} 个文件读取结果")

        return cleaned_messages

    def build_context(
        self,
        message: str,
        file_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        history_messages: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        构建完整的上下文消息列表

        处理流程：
        1. 如果有历史消息，清理 read_file 返回的文件内容，替换为梗概
        2. 添加系统提示
        3. 添加可用代码文件列表（如果有）
        4. 处理用户上传的文件上下文
        5. 添加用户消息

        v1.4.0 变更：移除自动代码注入，模型通过 read_file 工具主动读取文件

        Args:
            message: 用户消息
            file_context: 文件上下文（用户上传的文件）
            conversation_id: 对话 ID
            history_messages: 历史消息列表（可选）
            session_id: 会话 ID（用于获取该会话的代码文件列表）

        Returns:
            构建后的消息列表
        """
        messages = []

        # 1. 处理历史消息（如果有）
        # 注：自 v1.4.0 起，不再自动注入代码块，改用模型主动 read_file 机制
        # 历史消息中清理 read_file 返回的文件内容，替换为梗概
        if history_messages:
            messages.extend(self.clean_file_contents(history_messages))

        # 2. 添加系统提示
        from backend.models.response import STRUCTURED_RESPONSE_SYSTEM_PROMPT
        messages.append({
            "role": "system",
            "content": STRUCTURED_RESPONSE_SYSTEM_PROMPT
        })

        # 3. 添加可用代码文件列表（在系统提示之后）
        if session_id and self.code_store:
            code_list_context = self._build_code_list_context(session_id)
            if code_list_context:
                messages.append({
                    "role": "system",
                    "content": code_list_context
                })

        # 4. 处理用户上传的文件上下文
        if file_context:
            messages.extend(self._build_file_context(file_context))

        # 5. 添加用户消息
        # 注：自 v1.4.0 起，移除自动代码注入，模型通过 read_file 工具主动读取文件
        # messages = self.inject_code_blocks(message, messages)  # 已移除自动注入

        # 6. 添加用户消息
        messages.append({
            "role": "user",
            "content": message
        })

        logger.info(f"上下文构建完成: {len(messages)} 条消息")

        return messages

    def _build_code_list_context(self, session_id: str) -> Optional[str]:
        """
        构建统一文件列表上下文（markdown 格式）

        包含代码文件和用户上传文件，格式化为模型可理解的 markdown

        Args:
            session_id: 会话 ID

        Returns:
            文件列表上下文字符串（markdown），如果没有文件则返回 None
        """
        try:
            from backend.models.response import FileInfo

            lines = ["可用文件列表：\n"]

            has_files = False
            file_infos: List[FileInfo] = []

            # 获取代码文件
            if self.code_store:
                try:
                    codes = self.code_store.list_session_codes(session_id)
                    for code_info in codes:
                        file_infos.append(FileInfo.from_code_metadata(
                            file_id=code_info["file_id"],
                            filename=code_info["filename"],
                            file_type=code_info["file_type"],
                            size_bytes=code_info["size_bytes"],
                            description=code_info.get("description", ""),
                            language=code_info["language"]
                        ))
                except Exception as e:
                    logger.warning(f"获取代码文件列表失败: {e}")

            # 获取用户上传文件
            if self.upload_store:
                try:
                    uploads = self.upload_store.list_session_files(session_id)
                    for upload_info in uploads:
                        file_infos.append(FileInfo.from_upload_metadata(
                            file_id=upload_info["file_id"],
                            filename=upload_info["filename"],
                            file_type=upload_info["file_type"],
                            size_bytes=upload_info["size_bytes"],
                            description=upload_info.get("description", upload_info["filename"])
                        ))
                except Exception as e:
                    logger.warning(f"获取上传文件列表失败: {e}")

            if not file_infos:
                return None

            # 按文件类型分组
            code_files = [f for f in file_infos if f.language is not None]
            upload_files = [f for f in file_infos if f.language is None]

            # 添加代码文件
            if code_files:
                lines.append("**代码文件：**")
                for file_info in code_files:
                    lines.append(file_info.to_markdown())
                lines.append("")

            # 添加上传文件
            if upload_files:
                lines.append("**上传文件：**")
                for file_info in upload_files:
                    lines.append(file_info.to_markdown())
                lines.append("")

            # 添加使用说明
            lines.append("**你可以：**")
            lines.append("- 使用 `<code_ref>code_id</code_ref>` 引用代码文件")
            lines.append("- 使用 `<file_ref>file_id</file_ref>` 引用上传文件")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"构建文件列表上下文失败: {e}")
            return None

    def _build_file_context(self, file_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        构建文件上下文消息

        Args:
            file_context: 文件上下文

        Returns:
            文件上下文消息列表
        """
        messages = []

        if "file_id" in file_context:
            file_ref = f"upload:{file_context['file_id']}"
            messages.append({
                "role": "system",
                "content": f"用户已上传文件，文件引用: {file_ref}"
            })

        if "file_list" in file_context:
            file_list = file_context.get("file_list", [])
            if file_list:
                file_refs = ", ".join([f"upload:{f}" for f in file_list])
                messages.append({
                    "role": "system",
                    "content": f"用户已上传文件: {file_refs}"
                })

        return messages

    def should_clean_context(self, messages: List[Dict[str, str]]) -> bool:
        """
        判断是否需要清理上下文

        Args:
            messages: 消息列表

        Returns:
            是否需要清理
        """
        # 如果消息数量超过阈值，或者包含大量代码块，则需要清理
        if len(messages) > 20:
            return True

        # 检查代码块数量
        code_block_count = sum(
            1 for msg in messages
            if self.has_code_blocks(msg.get("content", ""))
        )

        if code_block_count > 3:
            return True

        return False

    def summarize_context(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        总结上下文（当上下文过长时）

        Args:
            messages: 原始消息列表

        Returns:
            总结后的消息列表
        """
        # 简化实现：保留最近的用户消息和系统提示
        # 更复杂的实现可以使用 LLM 来总结
        summarized = []

        # 保留系统提示
        for msg in messages:
            if msg.get("role") == "system":
                # 检查是否是结构化响应提示，只保留一个
                if "STRUCTURED_RESPONSE_SYSTEM_PROMPT" in str(msg.get("content", "")):
                    if not any("STRUCTURED_RESPONSE_SYSTEM_PROMPT" in m.get("content", "") for m in summarized):
                        summarized.append(msg)
                else:
                    summarized.append(msg)

        # 保留最近的 5 条消息
        for msg in messages[-5:]:
            summarized.append(msg)

        logger.info(f"上下文总结: {len(messages)} -> {len(summarized)} 条消息")

        return summarized


def create_context_manager(file_store=None) -> ContextManager:
    """
    创建上下文管理器实例

    Args:
        file_store: FileStore 实例

    Returns:
        ContextManager 实例
    """
    return ContextManager(file_store)
