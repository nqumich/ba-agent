"""
Pipeline 与 FileStore 集成

提供 ToolExecutionResult 与 FileStore 的集成功能
"""

from typing import Optional, Any, Dict, List
from pathlib import Path

from backend.models.pipeline import ToolExecutionResult, OutputLevel, ToolCachePolicy
from backend.models.filestore import FileRef, FileCategory
from backend.filestore import FileStore


class FileStorePipelineIntegration:
    """
    FileStore 与 Pipeline 集成管理器

    负责:
    - 将工具执行结果存储到 FileStore
    - 从 ToolExecutionResult 创建 FileRef
    - 管理工具结果的生命周期
    """

    def __init__(self, file_store: Optional[FileStore] = None):
        """
        初始化集成管理器

        Args:
            file_store: FileStore 实例，为 None 则创建默认实例
        """
        self.file_store = file_store

    def store_tool_result(
        self,
        result: ToolExecutionResult,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[FileRef]:
        """
        将工具执行结果存储到 FileStore

        Args:
            result: ToolExecutionResult 实例
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            FileRef 如果成功存储，None 如果不需要存储
        """
        # 只存储有数据的结果
        if result.data_size_bytes == 0 and not result.artifact_id:
            return None

        # 如果已经有 artifact_id，创建 FileRef
        if result.artifact_id:
            return FileRef(
                file_id=result.artifact_id,
                category=FileCategory.ARTIFACT,
                session_id=session_id,
                size_bytes=result.data_size_bytes,
                hash=result.data_hash or "",
                metadata={
                    'tool_name': result.tool_name,
                    'summary': result.data_summary
                }
            )

        # 如果有 data_file，读取并存储
        if result.data_file:
            try:
                with open(result.data_file, 'rb') as f:
                    content = f.read()

                return self.file_store.store_file(
                    content=content,
                    category=FileCategory.ARTIFACT,
                    session_id=session_id,
                    tool_name=result.tool_name,
                    summary=result.data_summary
                )
            except Exception:
                return None

        return None

    def result_with_file_ref(
        self,
        result: ToolExecutionResult,
        file_ref: FileRef
    ) -> ToolExecutionResult:
        """
        为 ToolExecutionResult 添加 FileRef 信息

        Args:
            result: ToolExecutionResult 实例
            file_ref: FileRef 实例

        Returns:
            更新后的 ToolExecutionResult
        """
        # 更新 metadata 包含 file_ref
        metadata = result.metadata.copy()
        metadata['file_ref'] = {
            'file_id': file_ref.file_id,
            'category': file_ref.category.value,
            'session_id': file_ref.session_id
        }

        return result.model_copy(update={
            'metadata': metadata,
            'artifact_id': file_ref.file_id  # 也更新 artifact_id 字段
        })

    @classmethod
    def create_result_with_storage(
        cls,
        tool_call_id: str,
        raw_data: Any,
        output_level: OutputLevel,
        tool_name: str = "",
        file_store: Optional[FileStore] = None,
        session_id: Optional[str] = None,
        cache_policy: ToolCachePolicy = ToolCachePolicy.NO_CACHE,
        **kwargs
    ) -> tuple[ToolExecutionResult, Optional[FileRef]]:
        """
        创建工具执行结果并自动存储到 FileStore

        这是 from_raw_data 的增强版本，支持 FileStore

        Args:
            tool_call_id: Tool call ID
            raw_data: 原始数据
            output_level: 输出级别
            tool_name: 工具名称
            file_store: FileStore 实例
            session_id: 会话 ID
            cache_policy: 缓存策略
            **kwargs: 额外参数

        Returns:
            (ToolExecutionResult, FileRef) 元组
        """
        import json
        import hashlib

        # 序列化数据
        data_json = json.dumps(raw_data, ensure_ascii=False, default=str)
        data_size = len(data_json.encode('utf-8'))
        data_hash = hashlib.md5(data_json.encode()).hexdigest()

        # 生成 observation
        if output_level == OutputLevel.BRIEF:
            observation = ToolExecutionResult._format_brief(raw_data)
        elif output_level == OutputLevel.STANDARD:
            observation = ToolExecutionResult._format_standard(raw_data)
        else:  # FULL
            # 如果有 FileStore，使用它存储大数据
            if file_store and data_size >= 1_000_000:
                file_ref = file_store.store_file(
                    content=data_json.encode('utf-8'),
                    category=FileCategory.ARTIFACT,
                    session_id=session_id,
                    tool_name=tool_name
                )

                observation = f"""Data stored as artifact: {file_ref.file_id}

Large dataset available for subsequent tool access.

To access this data, reference the file_id in your next tool call.
The system will securely retrieve the data for you.

Data summary: {cls._generate_summary(raw_data)}"""

                result = ToolExecutionResult(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    observation=observation,
                    output_level=output_level,
                    artifact_id=file_ref.file_id,
                    data_size_bytes=data_size,
                    data_hash=data_hash,
                    cache_policy=cache_policy,
                    **kwargs
                )

                return result, file_ref
            else:
                observation = ToolExecutionResult._format_full(raw_data)

        # 提取 success 状态
        is_success = raw_data.get("success", True) if isinstance(raw_data, dict) else True

        result = ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            observation=observation,
            output_level=output_level,
            data_size_bytes=data_size,
            data_hash=data_hash,
            success=is_success,
            cache_policy=cache_policy,
            **kwargs
        )

        return result, None

    @staticmethod
    def _generate_summary(data: Any) -> str:
        """生成数据摘要"""
        if isinstance(data, list):
            summary = f"List with {len(data)} items"
            if len(data) > 0 and isinstance(data[0], dict):
                keys = list(data[0].keys())[:5]
                summary += f". First item keys: {keys}"
            return summary
        elif isinstance(data, dict):
            return f"Dict with {len(data)} keys: {list(data.keys())[:10]}"
        else:
            return type(data).__name__

    def extract_file_refs_from_context(
        self,
        context: Dict[str, Any]
    ) -> List[FileRef]:
        """
        从执行上下文中提取文件引用

        Args:
            context: 工具执行上下文

        Returns:
            FileRef 列表
        """
        refs = []

        # 从 context 中查找 artifact_id
        if 'artifact_id' in context:
            refs.append(FileRef(
                file_id=context['artifact_id'],
                category=FileCategory.ARTIFACT,
                session_id=context.get('session_id')
            ))

        # 查找已有的 file_ref
        if 'file_ref' in context:
            file_ref_data = context['file_ref']
            if isinstance(file_ref_data, dict):
                refs.append(FileRef(
                    file_id=file_ref_data['file_id'],
                    category=FileCategory(file_ref_data.get('category', 'artifact')),
                    session_id=file_ref_data.get('session_id')
                ))

        return refs


# 便捷函数
def get_file_store_integration(
    file_store: Optional[FileStore] = None
) -> FileStorePipelineIntegration:
    """
    获取 FileStore 集成管理器实例

    Args:
        file_store: FileStore 实例

    Returns:
        FileStorePipelineIntegration 实例
    """
    return FileStorePipelineIntegration(file_store)


# 将 FileStore 添加到 Pipeline 导出
def update_pipeline_exports():
    """更新 Pipeline 模块导出以包含 FileStore"""
    import sys
    from pathlib import Path

    pipeline_init = Path(__file__).parent.parent / "pipeline" / "__init__.py"

    # 检查是否已经导出
    content = pipeline_init.read_text()
    if "FileStore" in content:
        return  # 已经导出

    # 添加 FileStore 导入
    import_section = content.find("# Models")
    if import_section > 0:
        # 在 Models 部分之前添加 FileStore 导入
        filestore_import = "\n# FileStore Integration\nfrom backend.filestore import FileStore, get_file_store\n"
        content = content[:import_section] + filestore_import + content[import_section:]

        pipeline_init.write_text(content)


__all__ = [
    "FileStorePipelineIntegration",
    "get_file_store_integration",
]
