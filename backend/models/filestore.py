"""
文件系统相关模型

定义统一文件存储管理系统的核心模型
"""

import os
import platform
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from pathlib import Path
from enum import Enum
from .base import TimestampMixin, MetadataMixin


def _get_default_storage_dir() -> Path:
    """
    获取默认的存储目录（跨平台）

    Returns:
        默认存储目录路径
    """
    # 检查环境变量
    env_dir = os.getenv("BA_STORAGE_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    # 根据平台选择用户本地目录
    system = platform.system()

    if system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support" / "ba-agent"
    elif system == "Windows":
        appdata = os.getenv("APPDATA", "")
        base = Path(appdata) / "ba-agent" if appdata else Path.home() / ".ba-agent"
    else:  # Linux 及其他
        xdg_data = os.getenv("XDG_DATA_HOME")
        base = Path(xdg_data) / "ba-agent" if xdg_data else Path.home() / ".local" / "share" / "ba-agent"

    return base


class FileCategory(str, Enum):
    """文件类别"""

    ARTIFACT = "artifact"  # 工具执行结果
    UPLOAD = "upload"      # 用户上传文件
    REPORT = "report"      # 报告文件
    CHART = "chart"        # 图表文件
    CACHE = "cache"        # 缓存文件
    TEMP = "temp"          # 临时文件
    MEMORY = "memory"      # 记忆文件
    CHECKPOINT = "checkpoint"  # 检查点文件


class FileRef(BaseModel):
    """
    统一文件引用

    安全特性:
    - 不暴露真实路径
    - 包含签名防篡改
    - 会话绑定
    """

    file_id: str = Field(
        ...,
        description="唯一文件 ID",
        min_length=1
    )
    category: FileCategory = Field(
        ...,
        description="文件类别"
    )
    session_id: Optional[str] = Field(
        None,
        description="所属会话 ID"
    )
    created_at: float = Field(
        default_factory=lambda: datetime.now().timestamp(),
        description="创建时间戳"
    )
    size_bytes: int = Field(
        default=0,
        ge=0,
        description="文件大小（字节）"
    )
    hash: str = Field(
        default="",
        description="内容哈希（MD5/SHA256）"
    )
    mime_type: str = Field(
        default="application/octet-stream",
        description="MIME 类型"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="附加元数据"
    )

    def __str__(self) -> str:
        """字符串表示: category:file_id"""
        return f"{self.category.value}:{self.file_id}"

    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "artifact_abc123",
                "category": "artifact",
                "session_id": "session_456",
                "created_at": 1707200000.0,
                "size_bytes": 1024,
                "hash": "d41d8cd98f00b204e9800998ecf8427e",
                "mime_type": "application/json"
            }
        }


class FileContent(BaseModel):
    """文件内容"""

    data: bytes = Field(
        ...,
        description="文件二进制数据"
    )
    mime_type: str = Field(
        ...,
        description="MIME 类型"
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="文件大小（字节）"
    )
    hash: str = Field(
        ...,
        description="内容哈希"
    )


class FileMetadata(TimestampMixin):
    """文件元数据"""

    file_ref: FileRef = Field(
        ...,
        description="文件引用"
    )
    filename: str = Field(
        ...,
        min_length=1,
        description="原始文件名"
    )
    access_count: int = Field(
        default=0,
        ge=0,
        description="访问次数"
    )
    last_accessed_at: Optional[datetime] = Field(
        None,
        description="最后访问时间"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="过期时间"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "file_ref": {
                    "file_id": "upload_xyz789",
                    "category": "upload",
                    "size_bytes": 204800
                },
                "filename": "sales_data.xlsx",
                "access_count": 5,
                "last_accessed_at": "2026-02-06T15:30:00",
                "expires_at": "2026-02-13T15:30:00"
            }
        }


class MemoryLayer(str, Enum):
    """记忆层级"""

    DAILY = "daily"        # 每日记忆 (memory/YYYY-MM-DD.md)
    CONTEXT = "context"    # 上下文记忆 (memory/context/*.md)
    KNOWLEDGE = "knowledge"  # 知识记忆 (memory/knowledge/*)


class MemoryRef(BaseModel):
    """记忆文件引用"""

    file_id: str = Field(
        ...,
        description="记忆文件 ID"
    )
    layer: MemoryLayer = Field(
        ...,
        description="记忆层级"
    )
    path: Path = Field(
        ...,
        description="文件路径"
    )
    created_at: float = Field(
        ...,
        description="创建时间戳"
    )
    file_refs: List[FileRef] = Field(
        default_factory=list,
        description="关联的文件引用"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="附加元数据"
    )

    def __str__(self) -> str:
        """字符串表示: layer:file_id"""
        return f"{self.layer.value}:{self.file_id}"

    class Config:
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "file_id": "2026-02-06",
                "layer": "daily",
                "path": "/var/lib/ba-agent/memory/daily/2026-02-06.md",
                "created_at": 1707200000.0,
                "file_refs": [
                    {"file_id": "artifact_abc", "category": "artifact"}
                ]
            }
        }


class MemoryContent(BaseModel):
    """记忆内容"""

    content: str = Field(
        ...,
        description="记忆内容（Markdown 格式）"
    )
    file_refs: List[FileRef] = Field(
        default_factory=list,
        description="关联的文件引用"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="附加元数据"
    )


class CheckpointRef(BaseModel):
    """检查点引用"""

    checkpoint_id: str = Field(
        ...,
        description="检查点 ID"
    )
    session_id: str = Field(
        ...,
        description="所属会话 ID"
    )
    name: str = Field(
        ...,
        min_length=1,
        description="检查点名称"
    )
    variables: List[str] = Field(
        default_factory=list,
        description="保存的变量名列表"
    )
    file_refs: List[FileRef] = Field(
        default_factory=list,
        description="关联的文件引用（DataFrame、图表等）"
    )
    created_at: float = Field(
        ...,
        description="创建时间戳"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="检查点元数据"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "checkpoint_id": "checkpoint_session_123_step1",
                "session_id": "session_123",
                "name": "step1",
                "variables": ["df", "result", "anomalies"],
                "created_at": 1707200000.0,
                "metadata": {"step": 1, "description": "数据加载后"}
            }
        }


class StorageStats(BaseModel):
    """存储统计信息"""

    category: FileCategory = Field(
        ...,
        description="文件类别"
    )
    file_count: int = Field(
        ...,
        ge=0,
        description="文件数量"
    )
    total_size_bytes: int = Field(
        ...,
        ge=0,
        description="总大小（字节）"
    )
    oldest_file_age_hours: Optional[float] = Field(
        None,
        description="最旧文件年龄（小时）"
    )
    newest_file_age_hours: Optional[float] = Field(
        None,
        description="最新文件年龄（小时）"
    )


class CleanupStats(BaseModel):
    """清理统计信息"""

    deleted_count: int = Field(
        default=0,
        ge=0,
        description="删除的文件数量"
    )
    freed_space_bytes: int = Field(
        default=0,
        ge=0,
        description="释放的空间（字节）"
    )
    category_stats: Dict[str, int] = Field(
        default_factory=dict,
        description="各类别删除数量"
    )
    duration_seconds: float = Field(
        ...,
        ge=0,
        description="清理耗时（秒）"
    )


class FileStoreConfig(BaseModel):
    """文件系统配置"""

    base_dir: Path = Field(
        default_factory=lambda: _get_default_storage_dir(),
        description="存储根目录（跨平台）"
    )
    max_total_size_gb: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="最大存储容量（GB）"
    )
    cleanup_interval_hours: int = Field(
        default=1,
        ge=1,
        description="清理间隔（小时）"
    )
    cleanup_threshold_percent: float = Field(
        default=90.0,
        ge=0.0,
        le=100.0,
        description="清理阈值（使用率百分比）"
    )
    ttl_config: Dict[str, int] = Field(
        default_factory=lambda: {
            "artifact": 24,
            "upload": 168,
            "report": 720,
            "chart": 168,
            "cache": 1,
            "temp": 0,
            "memory": 8760,
            "checkpoint": 24
        },
        description="各类别 TTL 配置（小时）"
    )
    max_file_sizes: Dict[str, int] = Field(
        default_factory=lambda: {
            "artifact": 100 * 1024 * 1024,  # 100 MB
            "upload": 50 * 1024 * 1024,     # 50 MB
            "report": 50 * 1024 * 1024,
            "chart": 10 * 1024 * 1024,
            "cache": 10 * 1024 * 1024,
            "temp": 50 * 1024 * 1024
        },
        description="各类别最大文件大小（字节）"
    )

    class Config:
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "base_dir": "~/.local/share/ba-agent",
                "max_total_size_gb": 10,
                "cleanup_interval_hours": 1,
                "cleanup_threshold_percent": 90.0
            }
        }


# 导出
__all__ = [
    "FileCategory",
    "FileRef",
    "FileContent",
    "FileMetadata",
    "MemoryLayer",
    "MemoryRef",
    "MemoryContent",
    "CheckpointRef",
    "StorageStats",
    "CleanupStats",
    "FileStoreConfig",
]
