"""
Checkpoint Store - Python 中间结果存储

支持检查点创建、恢复，变量/DataFrame/图表存储
"""

import pickle
import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.models.filestore import (
    FileRef,
    FileCategory,
    CheckpointRef,
)
from backend.filestore.base import WriteableStore


class CheckpointStore(WriteableStore):
    """
    检查点存储

    特性:
    - 保存变量快照
    - 保存 DataFrame（parquet 格式）
    - 保存图表（PNG 格式）
    - 支持检查点恢复
    """

    def __init__(self, storage_dir: Path):
        """
        初始化 CheckpointStore

        Args:
            storage_dir: 存储目录
        """
        super().__init__(storage_dir)
        self.checkpoints_dir = storage_dir
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def create_checkpoint(
        self,
        session_id: str,
        checkpoint_name: str,
        variables: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> CheckpointRef:
        """
        创建检查点

        Args:
            session_id: 会话 ID
            checkpoint_name: 检查点名称
            variables: 变量字典
            metadata: 元数据

        Returns:
            CheckpointRef: 检查点引用
        """
        checkpoint_id = f"checkpoint_{session_id}_{checkpoint_name}"
        checkpoint_dir = self.checkpoints_dir / session_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # 序列化变量
        serializable_vars = {}
        file_refs = []

        for name, value in variables.items():
            try:
                # 处理不同类型的变量
                if self._is_dataframe(value):
                    # DataFrame: 保存为 parquet
                    df_ref = self._save_dataframe(value, checkpoint_dir, name)
                    serializable_vars[name] = {'type': 'dataframe', 'ref': str(df_ref)}
                    file_refs.append(df_ref)

                elif self._is_chart(value):
                    # 图表: 保存为 PNG
                    chart_ref = self._save_chart(value, checkpoint_dir, name)
                    serializable_vars[name] = {'type': 'chart', 'ref': str(chart_ref)}
                    file_refs.append(chart_ref)

                elif self._is_serializable(value):
                    # 可序列化对象
                    serializable_vars[name] = {
                        'type': 'serializable',
                        'data': self._serialize_value(value)
                    }

                else:
                    # 其他类型，转换为字符串
                    serializable_vars[name] = {
                        'type': 'string',
                        'data': str(value)
                    }

            except Exception as e:
                serializable_vars[name] = {'type': 'error', 'error': str(e)}

        # 保存检查点元数据
        checkpoint_metadata = {
            'checkpoint_id': checkpoint_id,
            'session_id': session_id,
            'name': checkpoint_name,
            'created_at': datetime.now().isoformat(),
            'variables': serializable_vars,
            'metadata': metadata or {}
        }

        metadata_file = checkpoint_dir / f"{checkpoint_name}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_metadata, f, indent=2, default=str)

        return CheckpointRef(
            checkpoint_id=checkpoint_id,
            session_id=session_id,
            name=checkpoint_name,
            variables=list(variables.keys()),
            file_refs=file_refs,
            created_at=time.time(),
            metadata=checkpoint_metadata
        )

    def restore_checkpoint(
        self,
        checkpoint_ref: CheckpointRef
    ) -> Dict[str, Any]:
        """
        恢复检查点

        Args:
            checkpoint_ref: 检查点引用

        Returns:
            变量字典（尽可能恢复原始对象）

        Raises:
            ValueError: 检查点不存在
        """
        checkpoint_dir = self.checkpoints_dir / checkpoint_ref.session_id
        metadata_file = checkpoint_dir / f"{checkpoint_ref.name}.json"

        if not metadata_file.exists():
            raise ValueError(f"Checkpoint not found: {checkpoint_ref.checkpoint_id}")

        # 读取元数据
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        restored_vars = {}

        # 恢复变量
        for name, var_info in metadata['variables'].items():
            try:
                if var_info['type'] == 'dataframe':
                    # 从文件恢复 DataFrame（如果 pandas 可用）
                    restored_vars[name] = self._load_dataframe_info(var_info['ref'], checkpoint_dir)

                elif var_info['type'] == 'chart':
                    # 图表暂不支持恢复（只返回引用信息）
                    restored_vars[name] = var_info['ref']

                elif var_info['type'] == 'serializable':
                    # 反序列化对象
                    restored_vars[name] = self._deserialize_value(var_info['data'])

                else:
                    restored_vars[name] = var_info.get('data')

            except Exception as e:
                restored_vars[name] = None

        return restored_vars

    def list_checkpoints(self, session_id: str) -> List[CheckpointRef]:
        """
        列出会话的所有检查点

        Args:
            session_id: 会话 ID

        Returns:
            CheckpointRef 列表
        """
        checkpoint_dir = self.checkpoints_dir / session_id

        if not checkpoint_dir.exists():
            return []

        checkpoints = []
        for metadata_file in checkpoint_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                checkpoints.append(CheckpointRef(
                    checkpoint_id=metadata['checkpoint_id'],
                    session_id=metadata['session_id'],
                    name=metadata['name'],
                    variables=list(metadata.get('variables', {}).keys()),
                    file_refs=[],
                    created_at=datetime.fromisoformat(metadata['created_at']).timestamp(),
                    metadata=metadata
                ))
            except Exception:
                continue

        return sorted(checkpoints, key=lambda x: x.created_at)

    def delete_checkpoint(self, session_id: str, checkpoint_name: str) -> bool:
        """
        删除检查点

        Args:
            session_id: 会话 ID
            checkpoint_name: 检查点名称

        Returns:
            是否成功删除
        """
        checkpoint_dir = self.checkpoints_dir / session_id
        metadata_file = checkpoint_dir / f"{checkpoint_name}.json"

        if not metadata_file.exists():
            return False

        # 删除元数据文件
        metadata_file.unlink()

        # TODO: 删除关联的文件（DataFrame、图表等）

        return True

    def delete_session_checkpoints(self, session_id: str) -> int:
        """
        删除会话的所有检查点

        Args:
            session_id: 会话 ID

        Returns:
            删除的检查点数量
        """
        checkpoint_dir = self.checkpoints_dir / session_id

        if not checkpoint_dir.exists():
            return 0

        import shutil
        shutil.rmtree(checkpoint_dir)
        return 1

    def _is_dataframe(self, obj: Any) -> bool:
        """检查是否是 DataFrame"""
        try:
            import pandas as pd
            return isinstance(obj, pd.DataFrame)
        except ImportError:
            return False

    def _is_chart(self, obj: Any) -> bool:
        """检查是否是图表对象"""
        try:
            import matplotlib.figure
            return isinstance(obj, matplotlib.figure.Figure)
        except ImportError:
            return False

    def _is_serializable(self, obj: Any) -> bool:
        """检查是否可序列化"""
        try:
            pickle.dumps(obj)
            return True
        except Exception:
            return False

    def _save_dataframe(
        self,
        df: Any,
        checkpoint_dir: Path,
        name: str
    ) -> FileRef:
        """保存 DataFrame"""
        # 使用 JSON 格式（更通用，避免 parquet 依赖）
        file_path = checkpoint_dir / f"df_{name}.json"

        try:
            import pandas as pd
            data = df.to_dict(orient='records')
        except Exception:
            # 如果不是 pandas DataFrame，尝试其他方式
            data = {'data': str(df)}

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        # 计算哈希
        content_hash = hashlib.md5(file_path.read_bytes()).hexdigest()

        return FileRef(
            file_id=f"df_{name}",
            category=FileCategory.TEMP,
            size_bytes=file_path.stat().st_size,
            hash=content_hash,
            metadata={
                'type': 'dataframe',
                'format': 'json',
                'rows': len(data) if isinstance(data, list) else 0
            }
        )

    def _save_chart(
        self,
        fig: Any,
        checkpoint_dir: Path,
        name: str
    ) -> FileRef:
        """保存图表"""
        file_path = checkpoint_dir / f"chart_{name}.png"

        try:
            fig.savefig(file_path, format='png', bbox_inches='tight')
        except Exception:
            # 创建一个占位符文件
            file_path.write_text(f"[Chart placeholder: {name}]")

        # 计算哈希
        content_hash = hashlib.md5(file_path.read_bytes()).hexdigest()

        return FileRef(
            file_id=f"chart_{name}",
            category=FileCategory.CHART,
            size_bytes=file_path.stat().st_size,
            hash=content_hash,
            metadata={
                'type': 'chart',
                'format': 'png'
            }
        )

    def _load_dataframe_info(self, ref_str: str, checkpoint_dir: Path) -> Any:
        """加载 DataFrame（返回信息，不是实际 DataFrame）"""
        # 提取文件名
        file_name = ref_str.split(':')[-1]
        file_path = checkpoint_dir / f"{file_name}.json"

        if not file_path.exists():
            return None

        with open(file_path, 'r') as f:
            data = json.load(f)

        return {'type': 'dataframe_info', 'data': data}

    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        return pickle.dumps(value).hex()

    def _deserialize_value(self, hex_str: str) -> Any:
        """反序列化值"""
        try:
            return pickle.loads(bytes.fromhex(hex_str))
        except Exception:
            return None

    # ========== BaseStore 接口实现（最小化） ==========

    def store(self, content: bytes, **metadata) -> FileRef:
        """存储（兼容 BaseStore）"""
        # 检查点存储通常不直接使用此方法
        import uuid
        file_id = f"checkpoint_{uuid.uuid4().hex[:12]}"
        return FileRef(
            file_id=file_id,
            category=FileCategory.CHECKPOINT,
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """检索"""
        return None

    def delete(self, file_ref: FileRef) -> bool:
        """删除"""
        return False

    def exists(self, file_ref: FileRef) -> bool:
        """检查是否存在"""
        return False

    def list_files(self, **filters) -> List:
        """列出文件"""
        session_id = filters.get('session_id')
        if session_id:
            return self.list_checkpoints(session_id)
        return []


__all__ = [
    "CheckpointStore",
]
