"""
MemoryFlush 文件引用增强

为 MemoryFlush 添加文件引用检测和保存功能
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from backend.models.filestore import FileRef, FileCategory
from backend.filestore import FileStore
from backend.memory.flush import MemoryFlush, MemoryExtractor

logger = logging.getLogger(__name__)


class FileRefDetector:
    """
    文件引用检测器

    从工具调用和执行结果中检测文件引用
    """

    # 工具名称到文件类别的映射
    TOOL_FILE_CATEGORIES = {
        # 数据分析工具可能生成的文件类型
        'run_python': FileCategory.TEMP,
        'query_database': FileCategory.ARTIFACT,
        'search_knowledge': FileCategory.ARTIFACT,
        'file_reader': FileCategory.UPLOAD,
        'file_writer': FileCategory.ARTIFACT,
        'visualization': FileCategory.CHART,
        'chart': FileCategory.CHART,
        'report_gen': FileCategory.REPORT,
        'anomaly_detection': FileCategory.ARTIFACT,
        'attribution': FileCategory.ARTIFACT,
    }

    @classmethod
    def detect_from_tool_call(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Dict[str, Any]
    ) -> List[FileRef]:
        """
        从工具调用中检测文件引用

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            tool_output: 工具输出

        Returns:
            检测到的 FileRef 列表
        """
        refs = []

        # 1. 检查工具输出中的 artifact_id
        if 'artifact_id' in tool_output:
            refs.append(FileRef(
                file_id=tool_output['artifact_id'],
                category=FileCategory.ARTIFACT,
                size_bytes=tool_output.get('data_size_bytes', 0),
                metadata={
                    'tool_name': tool_name,
                    'summary': tool_output.get('summary')
                }
            ))

        # 2. 检查工具输出中的 file_ref
        if 'file_ref' in tool_output:
            file_ref_data = tool_output['file_ref']
            if isinstance(file_ref_data, dict):
                refs.append(FileRef(
                    file_id=file_ref_data['file_id'],
                    category=FileCategory(file_ref_data.get('category', 'artifact')),
                    session_id=file_ref_data.get('session_id'),
                    size_bytes=file_ref_data.get('size_bytes', 0),
                    metadata=file_ref_data.get('metadata', {})
                ))

        # 3. 根据工具名称推断可能的文件类型
        if tool_name in cls.TOOL_FILE_CATEGORIES:
            # 检查工具输入中的文件引用字符串
            refs.extend(cls._parse_file_refs_from_input(tool_input))

        return refs

    @classmethod
    def _parse_file_refs_from_input(cls, tool_input: Dict[str, Any]) -> List[FileRef]:
        """
        从工具输入中解析文件引用字符串

        Args:
            tool_input: 工具输入

        Returns:
            FileRef 列表
        """
        refs = []

        # 检查常见的文件引用字段
        for key, value in tool_input.items():
            if key in ('file_id', 'artifact_id', 'chart_id', 'upload_id'):
                if isinstance(value, str):
                    # 解析 category:file_id 格式
                    if ':' in value:
                        try:
                            category_str, file_id = value.split(':', 1)
                            category = FileCategory(category_str)
                            refs.append(FileRef(
                                file_id=file_id,
                                category=category
                            ))
                        except ValueError:
                            continue

        return refs

    @classmethod
    def detect_from_messages(
        cls,
        messages: List[BaseMessage],
        context: Dict[str, Any]
    ) -> List[FileRef]:
        """
        从对话消息中检测文件引用

        Args:
            messages: LangChain 消息列表
            context: 对话上下文

        Returns:
            检测到的 FileRef 列表
        """
        refs = []

        # 1. 从上下文中检测
        if 'artifacts' in context:
            for artifact_id in context['artifacts']:
                refs.append(FileRef(
                    file_id=artifact_id,
                    category=FileCategory.ARTIFACT,
                    metadata={'source': 'context'}
                ))

        # 2. 从消息内容中检测（工具调用结果）
        for msg in messages:
            if hasattr(msg, 'tool_calls'):
                for call in msg.tool_calls:
                    # 检查工具调用结果
                    if 'response_format' in call and call['response_format'] == 'file_ref':
                        refs.append(FileRef(
                            file_id=call.get('file_id', ''),
                            category=FileCategory(call.get('category', 'artifact')),
                            metadata={'source': 'tool_call'}
                        ))

        return refs

    @classmethod
    def extract_all_file_refs(
        cls,
        messages: List[BaseMessage],
        context: Dict[str, Any],
        tool_history: List[Dict[str, Any]]
    ) -> List[FileRef]:
        """
        提取所有文件引用

        Args:
            messages: LangChain 消息列表
            context: 对话上下文
            tool_history: 工具调用历史

        Returns:
            所有检测到的 FileRef
        """
        all_refs = []

        # 从消息中检测
        all_refs.extend(cls.detect_from_messages(messages, context))

        # 从工具历史中检测
        for tool_call in tool_history:
            tool_name = tool_call.get('name', '')
            tool_input = tool_call.get('input', {})
            tool_output = tool_call.get('output', {})

            refs = cls.detect_from_tool_call(tool_name, tool_input, tool_output)
            all_refs.extend(refs)

        # 去重
        seen = set()
        unique_refs = []
        for ref in all_refs:
            ref_key = (ref.category.value, ref.file_id)
            if ref_key not in seen:
                seen.add(ref_key)
                unique_refs.append(ref)

        return unique_refs


class EnhancedMemoryFlush(MemoryFlush):
    """
    增强的 MemoryFlush

    在原有功能基础上添加：
    - 文件引用自动检测
    - 文件引用保存到记忆
    - 与 FileStore 集成
    """

    def __init__(
        self,
        config: Optional["MemoryFlushConfig"] = None,
        memory_path: Optional[Path] = None,
        extractor: Optional[MemoryExtractor] = None,
        file_store: Optional[FileStore] = None
    ):
        """
        初始化增强的 MemoryFlush

        Args:
            config: Flush 配置
            memory_path: 记忆文件路径
            extractor: 记忆提取器
            file_store: FileStore 实例（可选）
        """
        super().__init__(config, memory_path, extractor)

        self.file_store = file_store
        self.file_ref_detector = FileRefDetector()

    def add_message_with_context(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加消息并保存上下文（用于文件引用检测）

        Args:
            role: 消息角色
            content: 消息内容
            tool_calls: 工具调用列表
            context: 执行上下文
        """
        # 调用父类方法
        self.add_message(role, content)

        # 保存上下文用于后续的文件引用检测
        if not hasattr(self, '_contexts'):
            self._contexts = []

        self._contexts.append({
            'role': role,
            'content': content,
            'tool_calls': tool_calls or [],
            'context': context or {},
            'timestamp': __import__('time').time()
        })

    def flush_with_file_refs(
        self,
        messages: List[BaseMessage],
        context: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        提取记忆并保存文件引用

        Args:
            messages: LangChain 消息列表
            context: 对话上下文
            session_id: 会话 ID

        Returns:
            Flush 结果字典
        """
        from langchain_core.messages import HumanMessage, AIMessage

        # 1. 检测文件引用
        file_refs = self._detect_file_refs_from_session(session_id)

        if not file_refs:
            # 没有文件引用，使用原有逻辑
            return self.check_and_flush(
                current_tokens=self.total_tokens,
                force=False
            )

        # 2. 提取记忆内容
        memories = self.extractor.extract_from_messages(
            self._convert_messages_to_dict(messages)
        )

        if not memories:
            return {
                "flushed": False,
                "memories_extracted": 0,
                "memories_written": 0,
                "file_refs_count": len(file_refs),
                "error": None
            }

        # 3. 将文件引用附加到记忆内容
        enhanced_memories = []
        for memory in memories:
            # 在记忆末尾添加文件引用块
            if file_refs:
                memory_with_refs = f"{memory}\n\n**关联文件**:\n"
                for ref in file_refs:
                    memory_with_refs += f"- `{ref.category.value}:{ref.file_id}`\n"
                enhanced_memories.append(memory_with_refs)
            else:
                enhanced_memories.append(memory)

        # 4. 保存到文件系统
        memories_written = 0
        try:
            if self.file_store:
                for memory in enhanced_memories:
                    self.file_store.memory.write_daily_memory(
                        content=memory,
                        file_refs=file_refs,
                        append=True
                    )
                    memories_written += 1
            else:
                # 回退到原有文件系统
                for memory in enhanced_memories:
                    self._write_to_file(memory)
                memories_written = len(enhanced_memories)
        except Exception as e:
            logger.error(f"保存文件引用失败: {e}")
            return {
                "flushed": False,
                "memories_extracted": len(memories),
                "memories_written": 0,
                "file_refs_count": len(file_refs),
                "error": str(e)
            }

        # 5. 清空缓存
        self.message_buffer.clear()
        self.last_flush_tokens = self.total_tokens

        return {
            "flushed": True,
            "memories_extracted": len(memories),
            "memories_written": memories_written,
            "file_refs_count": len(file_refs),
            "file_refs": [str(ref) for ref in file_refs],
            "reason": "File references detected"
        }

    def _detect_file_refs_from_session(self, session_id: Optional[str]) -> List[FileRef]:
        """
        从当前会话中检测文件引用

        Args:
            session_id: 会话 ID

        Returns:
            检测到的 FileRef 列表
        """
        refs = []

        # 从保存的上下文中检测
        if hasattr(self, '_contexts'):
            for ctx in self._contexts:
                # 从工具调用中检测
                for tool_call in ctx.get('tool_calls', []):
                    refs.extend(self.file_ref_detector.detect_from_tool_call(
                        tool_call.get('name', ''),
                        tool_call.get('input', {}),
                        tool_call.get('output', {})
                    ))

        # 去重
        seen = set()
        unique_refs = []
        for ref in refs:
            ref_key = (ref.category.value, ref.file_id)
            if ref_key not in seen:
                seen.add(ref_key)
                unique_refs.append(ref)

        return unique_refs

    def _convert_messages_to_dict(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """将 LangChain 消息转换为字典格式"""
        dict_messages = []
        for msg in messages:
            content = msg.content if hasattr(msg, 'content') else str(msg)
            dict_messages.append({
                'role': 'user' if isinstance(msg, HumanMessage) else 'assistant',
                'content': content
            })
        return dict_messages

    def _write_to_file(self, content: str) -> bool:
        """写入记忆文件"""
        try:
            self.memory_path.mkdir(parents=True, exist_ok=True)
            today = __import__('datetime').date.today()
            file_path = self.memory_path / f"{today.isoformat()}.md"

            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n{content}")

            return True
        except Exception as e:
            logger.error(f"写入记忆文件失败: {e}")
            return False


# 便捷函数
def create_enhanced_memory_flush(
    file_store: Optional[FileStore] = None,
    **kwargs
) -> EnhancedMemoryFlush:
    """
    创建增强的 MemoryFlush 实例

    Args:
        file_store: FileStore 实例
        **kwargs: MemoryFlush 的其他参数

    Returns:
        EnhancedMemoryFlush 实例
    """
    return EnhancedMemoryFlush(
        file_store=file_store,
        **kwargs
    )


__all__ = [
    "FileRefDetector",
    "EnhancedMemoryFlush",
    "create_enhanced_memory_flush",
]
