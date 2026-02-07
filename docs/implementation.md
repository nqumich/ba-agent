# BA-Agent 实现方案

> 版本: v1.0
> 创建日期: 2026-02-06
> 状态: 待评审
> 预估工期: 81 小时 (~10 个工作日)

---

## 文档说明

本文档整合了 BA-Agent 项目的所有实现和执行相关文档，包括：
- 文件系统与记忆系统集成实现方案
- Excel 上传处理流程实现
- FastAPI 服务实现
- Python 中间结果存储设计

**配套文档**:
- `docs/architecture.md` - 产品愿景和技术架构设计
- `docs/implementation.md` - 具体实现方案（本文档）

---

## 目录

1. [文件系统实现方案](#1-文件系统实现方案)
2. [Excel 上传处理流程](#2-excel-上传处理流程)
3. [FastAPI 服务实现](#3-fastapi-服务实现)
4. [测试计划](#4-测试计划)
5. [验收标准](#5-验收标准)
6. [实施步骤](#6-实施步骤)
7. [后续优化](#7-后续优化)

---

# 1. 文件系统实现方案

## 1.1 概述

### 1.1.1 目标

开发统一的文件管理系统（FileStore），并实现记忆系统（MemoryStore）的集成，支持：

1. **统一文件管理** - 所有文件类型通过统一接口管理
2. **记忆文件引用** - 记忆可以引用和关联其他文件
3. **安全访问控制** - 基于会话和用户的访问控制
4. **生命周期管理** - 自动清理过期文件
5. **Python 中间结果** - 检查点和中间数据存储
6. **完整测试覆盖** - 所有组件单元测试 + 集成测试

### 1.1.2 范围

**包含**:
- FileStore 基础框架
- MemoryStore 实现
- 文件引用系统
- 安全访问控制
- 生命周期管理
- Python 中间结果存储（CheckpointStore）
- 完整测试套件

**不包含**:
- 报告生成逻辑（Skill 业务逻辑）
- 前端界面

### 1.1.3 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 存储后端 | 本地文件系统 | `/var/lib/ba-agent/` |
| 元数据存储 | SQLite | 轻量级索引 |
| 数据模型 | Pydantic | 类型安全 |
| 测试框架 | pytest | 单元 + 集成测试 |
| 类型检查 | mypy | 类型安全 |

---

## 1.2 架构设计

### 1.2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BA-Agent 文件系统架构                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         FileStore (统一管理层)                           │ │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │ │
│  │  │  • store_file()      # 统一存储接口                              │  │ │
│  │  │  • get_file()        # 统一读取接口                              │  │ │
│  │  │  • delete_file()     # 统一删除接口                              │  │ │
│  │  │  • list_files()      # 统一列表接口                              │  │ │
│  │  │  • cleanup()         # 清理接口                                   │  │ │
│  │  └───────────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│                                        ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        具体存储实现层                                   │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │ArtifactStore │  │ UploadStore  │  │ ReportStore  │  │ ChartStore   │ │ │
│  │  │(工具结果)    │  │(用户上传)    │  │(报告文件)    │  │(图表文件)    │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │ │
│  │  │ CacheStore   │  │ TempStore    │  │CheckpointStore│                    │ │
│  │  │(缓存文件)    │  │(临时文件)    │  │(中间结果)    │                     │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                     │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                      MemoryStore (记忆存储)                          │  │ │
│  │  │  • write_memory()           # 写入记忆                             │  │ │
│  │  │  • get_memory()             # 读取记忆                             │  │ │
│  │  │  • search()                  # 搜索记忆                             │  │ │
│  │  │  • 支持 file_refs 参数       # 文件引用                             │  │ │
│  │  └──────────────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2.2 目录结构设计

```
ba-agent/
├── backend/
│   ├── filestore/                 # 新增: 文件系统模块
│   │   ├── __init__.py
│   │   ├── base.py                # 基础类和接口
│   │   ├── file_store.py          # FileStore 主类
│   │   ├── file_ref.py            # FileRef 和相关模型
│   │   ├── stores/                # 各类存储实现
│   │   │   ├── __init__.py
│   │   │   ├── artifact_store.py
│   │   │   ├── upload_store.py
│   │   │   ├── report_store.py
│   │   │   ├── chart_store.py
│   │   │   ├── cache_store.py
│   │   │   ├── temp_store.py
│   │   │   ├── checkpoint_store.py
│   │   │   └── memory_store.py    # 记忆存储
│   │   ├── security.py             # 访问控制和路径安全
│   │   ├── lifecycle.py            # 生命周期管理
│   │   ├── config.py               # 配置加载
│   │   └── checkpoint.py           # 中间结果捕获
│   │
│   ├── memory/                     # 现有: 记忆系统
│   │   ├── flush.py                # 需要增强: 支持文件引用
│   │   └── search.py               # 需要增强: 返回文件引用
│   │
│   └── models/
│       ├── filestore.py            # 新增: 文件系统模型
│       └── memory.py               # 现有: 记忆模型 (需要扩展)
│
├── tests/
│   ├── test_filestore/             # 新增: 文件系统测试
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_base.py
│   │   ├── test_file_store.py
│   │   ├── test_file_ref.py
│   │   ├── test_security.py
│   │   ├── test_lifecycle.py
│   │   ├── test_checkpoint.py
│   │   ├── test_stores/
│   │   │   ├── __init__.py
│   │   │   ├── test_artifact_store.py
│   │   │   ├── test_upload_store.py
│   │   │   ├── test_checkpoint_store.py
│   │   │   ├── test_memory_store.py
│   │   │   └── ...
│   │   └── test_integration.py     # 集成测试
│   │
│   └── test_memory/               # 现有: 记忆系统测试
│       └── test_flush_integration.py  # 需要扩展
│
├── var/lib/ba-agent/               # 存储目录（可配置）
│   ├── artifacts/
│   ├── uploads/
│   │   └── sessions/
│   ├── reports/
│   ├── charts/
│   ├── cache/
│   ├── temp/
│   │   └── checkpoints/
│   ├── memory/
│   │   ├── daily/
│   │   ├── context/
│   │   └── knowledge/
│   └── filestore.db                # 全局索引
│
└── config/
    └── filestore.yaml              # 新增: 文件系统配置
```

---

## 1.3 核心模型定义

**文件**: `backend/models/filestore.py`

```python
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime


class FileCategory(str, Enum):
    """文件类别"""
    ARTIFACT = "artifact"
    UPLOAD = "upload"
    REPORT = "report"
    CHART = "chart"
    CACHE = "cache"
    TEMP = "temp"
    MEMORY = "memory"


class FileRef(BaseModel):
    """
    统一文件引用

    安全特性:
    - 不暴露真实路径
    - 包含签名防篡改
    - 会话绑定
    """
    file_id: str = Field(..., description="唯一文件 ID")
    category: FileCategory = Field(..., description="文件类别")
    session_id: Optional[str] = Field(None, description="所属会话")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    size_bytes: int = Field(0, description="文件大小")
    hash: str = Field("", description="内容哈希")
    mime_type: str = Field("application/octet-stream", description="MIME 类型")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:
        """字符串表示: category:file_id"""
        return f"{self.category.value}:{self.file_id}"


class FileContent(BaseModel):
    """文件内容"""
    data: bytes
    mime_type: str
    size_bytes: int
    hash: str


class FileMetadata(BaseModel):
    """文件元数据"""
    file_ref: FileRef
    filename: str
    created_at: datetime
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class MemoryLayer(str, Enum):
    """记忆层级"""
    DAILY = "daily"
    CONTEXT = "context"
    KNOWLEDGE = "knowledge"


class MemoryRef(BaseModel):
    """记忆文件引用"""
    file_id: str
    layer: MemoryLayer
    path: Path
    created_at: float
    file_refs: List[FileRef] = Field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.layer.value}:{self.file_id}"


class MemoryContent(BaseModel):
    """记忆内容"""
    content: str
    file_refs: List[FileRef] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CheckpointRef(BaseModel):
    """检查点引用"""
    checkpoint_id: str
    session_id: str
    name: str
    variables: List[str]
    file_refs: List[FileRef] = Field(default_factory=list)
    created_at: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## 1.4 开发阶段

### Phase 1: 基础框架 (Day 1-2)

#### 1.4.1 BaseStore 接口

**文件**: `backend/filestore/base.py`

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any


class BaseStore(ABC):
    """存储基类"""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        storage_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def store(self, content: bytes, **metadata) -> FileRef:
        """存储文件"""
        pass

    @abstractmethod
    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """检索文件"""
        pass

    @abstractmethod
    def delete(self, file_ref: FileRef) -> bool:
        """删除文件"""
        pass

    @abstractmethod
    def exists(self, file_ref: FileRef) -> bool:
        """检查文件是否存在"""
        pass

    @abstractmethod
    def list_files(self, **filters) -> List[FileMetadata]:
        """列出文件"""
        pass
```

#### 1.4.2 FileStore 主类

**文件**: `backend/filestore/file_store.py`

```python
from typing import Optional, List, Dict, Any
from pathlib import Path

from backend.models.filestore import FileRef, FileCategory, FileMetadata
from backend.filestore.base import BaseStore
from backend.filestore.stores import (
    ArtifactStore,
    UploadStore,
    ReportStore,
    ChartStore,
    CacheStore,
    TempStore,
    MemoryStore,
    CheckpointStore
)


class FileStore:
    """
    统一文件存储管理器

    单一入口管理所有文件类型
    """

    # 默认存储目录
    DEFAULT_BASE_DIR = Path("/var/lib/ba-agent")

    def __init__(self, base_dir: Optional[Path] = None, config: Optional["FileStoreConfig"] = None):
        self.base_dir = base_dir or self.DEFAULT_BASE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各个存储
        self.artifacts = ArtifactStore(self.base_dir / "artifacts")
        self.uploads = UploadStore(self.base_dir / "uploads")
        self.reports = ReportStore(self.base_dir / "reports")
        self.charts = ChartStore(self.base_dir / "charts")
        self.cache = CacheStore(self.base_dir / "cache")
        self.temp = TempStore(self.base_dir / "temp")
        self.memory = MemoryStore(self.base_dir / "memory")
        self.checkpoints = CheckpointStore(self.base_dir / "temp" / "checkpoints")

        # 存储映射表
        self._stores = {
            FileCategory.ARTIFACT: self.artifacts,
            FileCategory.UPLOAD: self.uploads,
            FileCategory.REPORT: self.reports,
            FileCategory.CHART: self.charts,
            FileCategory.CACHE: self.cache,
            FileCategory.TEMP: self.temp,
            FileCategory.MEMORY: self.memory,
        }

    def store_file(
        self,
        content: bytes,
        category: FileCategory,
        **metadata
    ) -> FileRef:
        """统一存储接口"""
        store = self._stores.get(category)
        if not store:
            raise ValueError(f"Unknown category: {category}")

        return store.store(content, **metadata)

    def get_file(self, file_ref: FileRef) -> Optional[bytes]:
        """获取文件内容"""
        store = self._stores.get(file_ref.category)
        if not store:
            raise ValueError(f"Unknown category: {file_ref.category}")

        return store.retrieve(file_ref)

    def delete_file(self, file_ref: FileRef) -> bool:
        """删除文件"""
        store = self._stores.get(file_ref.category)
        if not store:
            return False

        return store.delete(file_ref)

    def file_exists(self, file_ref: FileRef) -> bool:
        """检查文件是否存在"""
        store = self._stores.get(file_ref.category)
        if not store:
            return False

        return store.exists(file_ref)

    def list_files(
        self,
        category: Optional[FileCategory] = None,
        **filters
    ) -> List[FileMetadata]:
        """列出文件"""
        if category:
            store = self._stores.get(category)
            if store:
                return store.list_files(**filters)
            return []

        # 列出所有类别的文件
        results = []
        for store in self._stores.values():
            results.extend(store.list_files(**filters))

        return results

    def get_store(self, category: FileCategory) -> BaseStore:
        """获取特定存储"""
        return self._stores.get(category)
```

---

### Phase 2: 存储实现 (Day 2-3)

#### 1.4.3 ArtifactStore（扩展现有 DataStorage）

**文件**: `backend/filestore/stores/artifact_store.py`

```python
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Any, Dict, List
from datetime import datetime

from backend.models.filestore import FileRef, FileCategory, FileMetadata
from backend.filestore.base import BaseStore
from backend.pipeline.storage import DataStorage


class ArtifactStore(BaseStore):
    """
    工具执行结果存储

    扩展现有 DataStorage 功能:
    - 实现 BaseStore 接口
    - 支持 FileRef 转换
    - 增加元数据管理
    """

    def __init__(self, storage_dir: Path):
        super().__init__(storage_dir)
        # 复用现有 DataStorage
        self._data_storage = DataStorage(
            storage_dir=str(storage_dir),
            max_age_hours=24,
            max_size_mb=1000
        )

    def store(self, content: bytes, **metadata) -> FileRef:
        """存储数据"""
        # 反序列化 JSON
        try:
            data = json.loads(content.decode('utf-8'))
        except Exception:
            # 如果不是 JSON，作为二进制存储
            data = content.decode('utf-8', errors='ignore')

        # 使用现有 DataStorage 存储
        artifact_id, observation, artifact_meta = self._data_storage.store(
            data=data,
            tool_name=metadata.get('tool_name', ''),
            summary=metadata.get('summary')
        )

        # 转换为 FileRef
        return FileRef(
            file_id=artifact_id,
            category=FileCategory.ARTIFACT,
            size_bytes=artifact_meta.size_bytes,
            hash=artifact_meta.hash,
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """检索数据"""
        data = self._data_storage.retrieve(file_ref.file_id)
        if data is None:
            return None

        return json.dumps(data).encode('utf-8')

    def delete(self, file_ref: FileRef) -> bool:
        """删除数据"""
        return self._data_storage.delete(file_ref.file_id)

    def exists(self, file_ref: FileRef) -> bool:
        """检查是否存在"""
        return file_ref.file_id in self._data_storage._metadata

    def list_files(self, **filters) -> List[FileMetadata]:
        """列出文件"""
        artifacts = self._data_storage.list_artifacts(
            tool_name=filters.get('tool_name')
        )

        return [
            FileMetadata(
                file_ref=FileRef(
                    file_id=art.artifact_id,
                    category=FileCategory.ARTIFACT,
                    size_bytes=art.size_bytes,
                    hash=art.hash
                ),
                filename=art.filename,
                created_at=datetime.fromtimestamp(art.created_at)
            )
            for art in artifacts
        ]

    def cleanup(self, max_age_hours: int = 24) -> int:
        """清理过期文件"""
        return self._data_storage.cleanup(max_age_hours)
```

#### 1.4.4 UploadStore

**文件**: `backend/filestore/stores/upload_store.py`

```python
import uuid
import hashlib
import json
import time
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from backend.models.filestore import FileRef, FileCategory, FileMetadata
from backend.filestore.base import BaseStore


class UploadStore(BaseStore):
    """
    用户上传文件存储

    特性:
    - 按会话隔离
    - 自动提取元数据
    - 支持 Excel/CSV 解析
    """

    def __init__(self, storage_dir: Path):
        super().__init__(storage_dir)
        self._sessions_dir = storage_dir / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._index_db = storage_dir / "uploads_index.db"

        # 初始化索引数据库
        self._init_index()

    def _init_index(self):
        """初始化索引数据库"""
        import sqlite3

        self.conn = sqlite3.connect(self._index_db)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                file_id TEXT PRIMARY KEY,
                session_id TEXT,
                original_filename TEXT,
                file_path TEXT,
                size_bytes INTEGER,
                hash TEXT,
                mime_type TEXT,
                created_at REAL,
                metadata TEXT,
                expires_at REAL
            )
        """)
        self.conn.commit()

    def store(
        self,
        content: bytes,
        filename: str,
        session_id: str,
        user_id: str,
        **metadata
    ) -> FileRef:
        """存储上传文件"""

        # 生成 file_id
        file_id = f"upload_{uuid.uuid4().hex[:12]}"
        content_hash = hashlib.md5(content).hexdigest()

        # 创建会话目录
        session_dir = self._sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_path = session_dir / f"{file_id}_{filename}"
        with open(file_path, 'wb') as f:
            f.write(content)

        # 检测 MIME 类型
        mime_type = self._detect_mime_type(filename)

        # 解析元数据（如果是 Excel/CSV）
        extra_metadata = self._extract_metadata(content, filename, mime_type)
        metadata.update(extra_metadata)

        # 保存到索引
        self.conn.execute("""
            INSERT INTO uploads
            (file_id, session_id, original_filename, file_path, size_bytes,
             hash, mime_type, created_at, metadata, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id, session_id, filename, str(file_path),
            len(content), content_hash, mime_type,
            time.time(), json.dumps(metadata),
            None  # expires_at
        ))
        self.conn.commit()

        return FileRef(
            file_id=file_id,
            category=FileCategory.UPLOAD,
            session_id=session_id,
            size_bytes=len(content),
            hash=content_hash,
            mime_type=mime_type,
            metadata=metadata
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """检索文件"""
        # 查询索引
        cursor = self.conn.execute("""
            SELECT file_path FROM uploads WHERE file_id = ?
        """, (file_ref.file_id,))

        row = cursor.fetchone()
        if not row:
            return None

        file_path = Path(row[0])
        if not file_path.exists():
            return None

        with open(file_path, 'rb') as f:
            return f.read()

    def delete(self, file_ref: FileRef) -> bool:
        """删除文件"""
        # 查询索引
        cursor = self.conn.execute("""
            SELECT file_path FROM uploads WHERE file_id = ?
        """, (file_ref.file_id,))

        row = cursor.fetchone()
        if not row:
            return False

        file_path = Path(row[0])

        # 删除文件
        if file_path.exists():
            file_path.unlink()

        # 删除索引
        self.conn.execute("""
            DELETE FROM uploads WHERE file_id = ?
        """, (file_ref.file_id,))
        self.conn.commit()

        return True

    def exists(self, file_ref: FileRef) -> bool:
        """检查文件是否存在"""
        cursor = self.conn.execute("""
            SELECT 1 FROM uploads WHERE file_id = ?
        """, (file_ref.file_id,))
        return cursor.fetchone() is not None

    def list_files(self, session_id: Optional[str] = None, **filters) -> List[FileMetadata]:
        """列出文件"""
        query = "SELECT * FROM uploads"
        params = []

        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)

        cursor = self.conn.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=row[0],
                    category=FileCategory.UPLOAD,
                    session_id=row[1],
                    size_bytes=row[4],
                    hash=row[5],
                    mime_type=row[6]
                ),
                filename=row[2],
                created_at=datetime.fromtimestamp(row[7])
            ))

        return results

    def delete_session_files(self, session_id: str) -> int:
        """删除会话的所有文件"""
        cursor = self.conn.execute("""
            SELECT file_id, file_path FROM uploads WHERE session_id = ?
        """, (session_id,))

        count = 0
        for row in cursor.fetchall():
            file_path = Path(row[1])
            if file_path.exists():
                file_path.unlink()
            count += 1

        self.conn.execute("""
            DELETE FROM uploads WHERE session_id = ?
        """, (session_id,))
        self.conn.commit()

        return count

    def _detect_mime_type(self, filename: str) -> str:
        """检测 MIME 类型"""
        ext = Path(filename).suffix.lower()
        mime_map = {
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.csv': 'text/csv',
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
        }
        return mime_map.get(ext, 'application/octet-stream')

    def _extract_metadata(
        self,
        content: bytes,
        filename: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """提取文件元数据"""
        metadata = {}

        # 如果是 Excel/CSV，尝试解析
        if 'excel' in mime_type or 'spreadsheet' in mime_type:
            try:
                import pandas as pd
                import io

                df = pd.read_excel(io.BytesIO(content), nrows=100)
                metadata.update({
                    'rows': len(df),
                    'columns': list(df.columns),
                    'preview': df.head(10).to_dict(orient='records')
                })
            except Exception:
                pass
        elif mime_type == 'text/csv':
            try:
                import pandas as pd
                import io

                df = pd.read_csv(io.BytesIO(content), nrows=100)
                metadata.update({
                    'rows': len(df),
                    'columns': list(df.columns),
                    'preview': df.head(10).to_dict(orient='records')
                })
            except Exception:
                pass

        return metadata
```

#### 1.4.5 MemoryStore

**文件**: `backend/filestore/stores/memory_store.py`

```python
import re
from pathlib import Path
from typing import Optional, List
from datetime import date, datetime

from backend.models.filestore import FileRef, FileCategory, MemoryRef, MemoryLayer, MemoryContent
from backend.filestore.base import BaseStore


class MemoryStore(BaseStore):
    """
    记忆文件存储

    特性:
    - 保留 Markdown 格式
    - 支持文件引用
    - 三层架构 (daily/context/knowledge)
    """

    def __init__(self, storage_dir: Path):
        super().__init__(storage_dir)
        self.daily_dir = storage_dir / "daily"
        self.context_dir = storage_dir / "context"
        self.knowledge_dir = storage_dir / "knowledge"

        for dir_path in [self.daily_dir, self.context_dir, self.knowledge_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def write_daily_memory(
        self,
        content: str,
        date: Optional[date] = None,
        file_refs: List[FileRef] = None,
        append: bool = True
    ) -> MemoryRef:
        """写入每日记忆"""

        target_date = date or date.today()
        file_path = self.daily_dir / f"{target_date.isoformat()}.md"

        # 添加文件引用块
        if file_refs:
            content = self._append_file_refs_block(content, file_refs)

        # 写入文件
        if append and file_path.exists():
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n{content}")
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return MemoryRef(
            file_id=file_path.stem,
            layer=MemoryLayer.DAILY,
            path=file_path,
            created_at=datetime.now().timestamp(),
            file_refs=file_refs or []
        )

    def write_context_memory(
        self,
        name: str,
        content: str,
        file_refs: List[FileRef] = None
    ) -> MemoryRef:
        """写入上下文记忆"""

        file_path = self.context_dir / f"{name}.md"

        if file_refs:
            content = self._append_file_refs_block(content, file_refs)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return MemoryRef(
            file_id=name,
            layer=MemoryLayer.CONTEXT,
            path=file_path,
            created_at=datetime.now().timestamp(),
            file_refs=file_refs or []
        )

    def get_memory(self, memory_ref: MemoryRef) -> MemoryContent:
        """获取记忆内容"""

        content = self._read_file(memory_ref.path)
        file_refs = self._extract_file_refs(content)

        return MemoryContent(
            content=content,
            file_refs=file_refs
        )

    # ========== BaseStore 接口实现 ==========

    def store(self, content: bytes, **metadata) -> FileRef:
        """存储（用于 BaseStore 兼容）"""
        text_content = content.decode('utf-8')
        layer = metadata.get('layer', MemoryLayer.DAILY)

        if layer == MemoryLayer.DAILY:
            mem_ref = self.write_daily_memory(text_content)
        elif layer == MemoryLayer.CONTEXT:
            name = metadata.get('name', 'memory')
            mem_ref = self.write_context_memory(name, text_content)
        else:
            # 其他层级
            mem_ref = self.write_daily_memory(text_content)

        return FileRef(
            file_id=mem_ref.file_id,
            category=FileCategory.MEMORY,
            metadata={'memory_ref': mem_ref}
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """检索"""
        memory_ref = file_ref.metadata.get('memory_ref')
        if not memory_ref:
            return None

        content = self._read_file(memory_ref.path)
        return content.encode('utf-8')

    def delete(self, file_ref: FileRef) -> bool:
        """删除"""
        memory_ref = file_ref.metadata.get('memory_ref')
        if not memory_ref:
            return False

        if memory_ref.path.exists():
            memory_ref.path.unlink()
            return True

        return False

    def exists(self, file_ref: FileRef) -> bool:
        """检查是否存在"""
        memory_ref = file_ref.metadata.get('memory_ref')
        if not memory_ref:
            return False

        return memory_ref.path.exists()

    def list_files(self, **filters) -> List:
        """列出文件"""
        layer = filters.get('layer')

        if layer == MemoryLayer.DAILY:
            dir_path = self.daily_dir
        elif layer == MemoryLayer.CONTEXT:
            dir_path = self.context_dir
        else:
            dir_path = self.daily_dir

        results = []
        for file_path in dir_path.glob("*.md"):
            stat = file_path.stat()
            results.append({
                'path': file_path,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'size': stat.st_size
            })

        return results

    # ========== 内部方法 ==========

    def _read_file(self, file_path: Path) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ""

    def _append_file_refs_block(
        self,
        content: str,
        file_refs: List[FileRef]
    ) -> str:
        """在内容末尾添加文件引用块"""

        if not file_refs:
            return content

        refs_block = "\n\n**关联文件**:\n"
        for ref in file_refs:
            refs_block += f"- `{ref.category.value}:{ref.file_id}`\n"

        return content + refs_block

    def _extract_file_refs(self, content: str) -> List[FileRef]:
        """从内容中提取文件引用"""

        pattern = r'`(\w+):([a-zA-Z0-9_:.-]+)`'
        refs = []

        for match in re.finditer(pattern, content):
            try:
                category = FileCategory(match.group(1))
                refs.append(FileRef(
                    file_id=match.group(2),
                    category=category
                ))
            except ValueError:
                continue

        return refs
```

---

### Phase 3: 记忆系统集成 (Day 3-4)

#### 1.4.6 增强 MemoryFlush

**修改**: `backend/memory/flush.py`

```python
# 在 MemoryFlush 类中添加方法

def _detect_file_refs(
    self,
    messages: List[BaseMessage],
    context: Dict
) -> List[FileRef]:
    """
    检测对话中的文件引用

    从工具调用和上下文中提取文件引用
    """
    from backend.models.filestore import FileRef, FileCategory

    refs = []

    # 从工具调用中提取
    for msg in messages:
        if hasattr(msg, 'tool_calls'):
            for call in msg.tool_calls:
                # 检查是否有文件返回
                if call.get('response_format') == 'file_ref':
                    refs.append(FileRef(
                        file_id=call.get('file_id'),
                        category=FileCategory(call.get('category', 'artifact'))
                    ))

    # 从上下文中提取
    if 'artifacts' in context:
        for artifact_id in context['artifacts']:
            refs.append(FileRef(
                file_id=artifact_id,
                category=FileCategory.ARTIFACT
            ))

    return refs


def flush_with_refs(
    self,
    messages: List[BaseMessage],
    context: Dict,
    file_store: Optional[FileStore] = None
) -> FlushResult:
    """
    提取并保存记忆（支持文件引用）

    新增参数:
        file_store: FileStore 实例，用于验证文件引用
    """
    from backend.filestore.file_store import FileStore

    if file_store is None:
        file_store = FileStore()

    # 1. LLM 提取记忆
    extracted = self._extract_with_llm(messages)

    # 2. 检测文件引用
    file_refs = self._detect_file_refs(messages, context)

    # 3. 验证文件引用（如果提供 file_store）
    if file_refs:
        valid_refs = []
        for ref in file_refs:
            if file_store.file_exists(ref):
                valid_refs.append(ref)
            else:
                logger.warning(f"File reference not found: {ref}")
        file_refs = valid_refs

    # 4. 写入记忆（含文件引用）
    memory_ref = file_store.memory.write_daily_memory(
        content=extracted.content,
        file_refs=file_refs
    )

    return FlushResult(
        memory_ref=memory_ref,
        file_count=len(file_refs)
    )
```

#### 1.4.7 增强 MemorySearch

**修改**: `backend/memory/search.py`

```python
# 在 MemorySearchEngine 类中添加方法

def search_with_file_refs(
    self,
    query: str,
    layers: Optional[List[MemoryLayer]] = None,
    file_store: Optional[FileStore] = None,
    hybrid: bool = True
) -> List[MemorySearchResultWithRefs]:
    """
    搜索记忆（包含文件引用）

    新增参数:
        file_store: FileStore 实例，用于解析文件引用

    返回:
        包含文件引用的搜索结果
    """
    from backend.filestore.file_store import FileStore

    if file_store is None:
        file_store = FileStore()

    # 原有搜索逻辑
    results = self._search_index(query, layers, hybrid)

    # 扩展结果，包含文件引用
    enriched = []
    for result in results:
        memory = file_store.memory.get_memory(result.memory_ref)

        enriched.append(MemorySearchResultWithRefs(
            **result.model_dump(),
            file_refs=memory.file_refs
        ))

    return enriched
```

---

### Phase 4: 安全与生命周期 (Day 4-5)

#### 1.4.8 安全访问控制

**文件**: `backend/filestore/security.py`

```python
from pathlib import Path
from typing import Optional
from backend.models.filestore import FileRef, FileCategory


class FileAccessControl:
    """文件访问控制"""

    def can_access(
        self,
        file_ref: FileRef,
        session_id: str,
        user_id: str
    ) -> bool:
        """
        检查访问权限

        规则:
        1. UPLOAD 文件：仅上传者所属会话可访问
        2. TEMP 文件：仅创建者会话可访问
        3. REPORT 文件：会话参与者可访问
        4. ARTIFACT 文件：同一会话可访问
        5. MEMORY 文件：全局可访问（只读）
        """

        if file_ref.category == FileCategory.UPLOAD:
            return file_ref.session_id == session_id

        elif file_ref.category == FileCategory.TEMP:
            return file_ref.session_id == session_id

        elif file_ref.category in (FileCategory.REPORT, FileCategory.ARTIFACT):
            return file_ref.session_id == session_id

        elif file_ref.category == FileCategory.MEMORY:
            return True  # 记忆文件全局可读

        return False


class SecurePathResolver:
    """安全路径解析器"""

    def resolve(self, file_ref: FileRef, storage_dir: Path) -> Path:
        """
        解析文件引用为物理路径

        安全措施:
        1. 验证 file_id 格式
        2. 禁止路径遍历
        3. 确保路径在存储目录内
        """

        # 验证 file_id 格式
        if not self._validate_file_id(file_ref.file_id):
            raise ValueError(f"Invalid file_id format: {file_ref.file_id}")

        # 构建路径
        category_dir = storage_dir / file_ref.category.value
        file_path = category_dir / f"{file_ref.file_id}"

        # 安全检查：确保路径在存储目录内
        try:
            resolved = file_path.resolve()
            storage_resolved = storage_dir.resolve()

            if not str(resolved).startswith(str(storage_resolved)):
                raise ValueError(f"Security violation: path outside sandbox")

            return resolved

        except Exception as e:
            raise ValueError(f"Path resolution failed: {e}")

    def _validate_file_id(self, file_id: str) -> bool:
        """验证 file_id 格式"""
        # 禁止路径分隔符
        if "/" in file_id or "\\" in file_id:
            return False

        # 禁止路径遍历
        if ".." in file_id:
            return False

        return True
```

#### 1.4.9 生命周期管理

**文件**: `backend/filestore/lifecycle.py`

```python
import time
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta

from backend.filestore.file_store import FileStore
from backend.models.filestore import FileCategory
from pydantic import BaseModel, Field


class FileLifecycleManager:
    """文件生命周期管理器"""

    # TTL 配置（小时）
    TTL_CONFIG = {
        'artifact': 24,
        'upload': 168,    # 7 天
        'report': 720,    # 30 天
        'chart': 168,     # 7 天
        'cache': 1,
        'temp': 0,
        'memory': 8760,  # 永久（不清理）
    }

    def __init__(self, file_store: FileStore):
        self.file_store = file_store

    def cleanup_expired_files(self) -> "CleanupStats":
        """清理过期文件"""

        stats = CleanupStats()

        for category, ttl_hours in self.TTL_CONFIG.items():
            if ttl_hours == 0:
                continue  # 不清理

            store = self.file_store.get_store(FileCategory(category))

            # 获取过期文件
            cutoff_time = time.time() - (ttl_hours * 3600)
            expired = store.list_expired(cutoff_time)

            # 删除过期文件
            for file_ref in expired:
                if store.delete(file_ref):
                    stats.deleted_count += 1
                    stats.freed_space += file_ref.size_bytes

            stats.category_stats[category] = len(expired)

        return stats

    def check_storage_usage(self) -> "StorageStats":
        """检查存储使用情况"""

        stats = StorageStats()

        for category in FileCategory:
            store = self.file_store.get_store(category)
            files = store.list_files()

            total_size = sum(f.file_ref.size_bytes for f in files)

            stats.category_stats[category] = CategoryStats(
                file_count=len(files),
                total_size_bytes=total_size
            )

            stats.total_size += total_size
            stats.total_files += len(files)

        return stats

    def cleanup_if_needed(self, threshold_percent: float = 90.0) -> bool:
        """如果存储使用超过阈值，执行清理"""

        stats = self.check_storage_usage()

        # 计算使用率（需要配置最大存储限制）
        max_size_gb = 10  # 从配置读取
        usage_percent = (stats.total_size / (max_size_gb * 1024**3)) * 100

        if usage_percent > threshold_percent:
            self.cleanup_expired_files()
            return True

        return False


class CleanupStats(BaseModel):
    """清理统计"""
    deleted_count: int = 0
    freed_space: int = 0
    category_stats: Dict[str, int] = Field(default_factory=dict)


class StorageStats(BaseModel):
    """存储统计"""
    total_size: int = 0
    total_files: int = 0
    category_stats: Dict[str, "CategoryStats"] = Field(default_factory=dict)


class CategoryStats(BaseModel):
    """类别统计"""
    file_count: int
    total_size_bytes: int
```

---

### Phase 5: Python 中间结果存储 (Day 5-6)

#### 1.4.10 CheckpointCapture - 中间结果捕获器

**文件**: `backend/filestore/checkpoint.py`

```python
import ast
import pickle
import json
from typing import Any, Dict, List, Optional
from pathlib import Path


class CheckpointCapture:
    """
    Python 代码中间结果捕获器

    功能:
    1. 通过 AST 分析自动检测关键变量
    2. 拦截特定函数调用（plt.savefig, df.to_*）
    3. 提供显式 checkpoint() 函数
    4. 自动序列化并存储中间结果
    """

    def __init__(self, session_id: str, checkpoint_store: "CheckpointStore"):
        self.session_id = session_id
        self.store = checkpoint_store
        self.checkpoints: Dict[str, Checkpoint] = {}
        self.current_step = 0

    def capture_execution(
        self,
        code: str,
        sandbox: "DockerSandbox",
        enable_auto_capture: bool = True
    ) -> "ExecutionResult":
        """
        执行代码并捕获中间结果

        Args:
            code: Python 代码
            sandbox: Docker 沙盒实例
            enable_auto_capture: 是否启用自动捕获

        Returns:
            ExecutionResult:
                - output: 执行输出
                - checkpoints: 检查点列表
                - intermediate_files: 中间文件列表
        """

        # 1. 预处理代码：注入捕获逻辑
        instrumented_code = self._instrument_code(code, enable_auto_capture)

        # 2. 执行代码
        result = sandbox.execute(instrumented_code)

        # 3. 提取捕获的检查点
        checkpoints = self._extract_checkpoints(result)

        # 4. 收集中间文件引用
        file_refs = self._collect_file_refs(result)

        return ExecutionResult(
            output=result['stdout'],
            error=result.get('stderr'),
            checkpoints=checkpoints,
            file_refs=file_refs,
            success=result['exit_code'] == 0
        )

    def _instrument_code(self, code: str, enable_auto: bool) -> str:
        """
        注入代码以支持中间结果捕获

        策略:
        1. 添加 checkpoint() 函数
        2. 包装特定函数调用（plt.savefig, df.to_csv 等）
        3. 注入变量追踪
        """

        if not enable_auto:
            return code

        # 生成注入代码
        preamble = self._generate_preamble()
        postamble = self._generate_postamble()

        return f"{preamble}\n\n{code}\n\n{postamble}"

    def _generate_preamble(self) -> str:
        """生成代码前导（导入和工具函数）"""

        return """
# ========== 中间结果捕获工具 ==========
import sys
import json
import pickle

# 全局存储
_CHECKPOINT_DATA = {}

def checkpoint(name: str, variables: list = None):
    '''创建检查点'''
    global _CHECKPOINT_DATA

    # 获取指定变量
    if variables is None:
        # 获取所有局部变量（排除内置模块）
        import inspect
        frame = inspect.currentframe()
        caller_locals = {k: v for k, v in frame.f_back.f_locals.items()
                        if not k.startswith('_') and k not in ['code', 'inspect']}
    else:
        frame = inspect.currentframe()
        caller_locals = {k: frame.f_back.f_locals[k] for k in variables}

    _CHECKPOINT_DATA[name] = {
        'variables': caller_locals,
        'step': len(_CHECKPOINT_DATA) + 1
    }

    return f"Checkpoint '{name}' created with {len(caller_locals)} variables"

def save_var(name: str, value):
    '''保存单个变量'''
    global _CHECKPOINT_DATA
    if '__saved_vars__' not in _CHECKPOINT_DATA:
        _CHECKPOINT_DATA['__saved_vars__'] = {}
    _CHECKPOINT_DATA['__saved_vars__'][name] = value

def save_df(df, name: str, format: str = 'parquet'):
    '''保存 DataFrame'''
    global _CHECKPOINT_DATA
    if '__saved_dfs__' not in _CHECKPOINT_DATA:
        _CHECKPOINT_DATA['__saved_dfs__'] = {}

    # 序列化
    if format == 'parquet':
        _CHECKPOINT_DATA['__saved_dfs__'][name] = {
            'format': 'parquet',
            'data': df.to_dict(orient='records')  # 简化：实际用 parquet
        }
    elif format == 'csv':
        _CHECKPOINT_DATA['__saved_dfs__'][name] = {
            'format': 'csv',
            'data': df.to_csv(index=False)
        }

def save_chart(fig, name: str):
    '''保存图表'''
    global _CHECKPOINT_DATA
    if '__saved_charts__' not in _CHECKPOINT_DATA:
        _CHECKPOINT_DATA['__saved_charts__'] = {}

    # 获取图像数据
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    _CHECKPOINT_DATA['__saved_charts__'][name] = {
        'format': 'png',
        'data': buf.getvalue()
    }

# ========== Hook 常用函数 ==========
_original_savefig = None

def _hook_savefig(*args, **kwargs):
    '''Hook matplotlib.pyplot.savefig'''
    import matplotlib.pyplot as plt
    global _CHECKPOINT_DATA

    # 调用原始函数
    result = _original_savefig(*args, **kwargs)

    # 记录保存的文件
    if args and hasattr(args[0], 'endswith') and args[0].endswith('.png'):
        filename = Path(args[0]).stem
        save_chart(plt.gcf(), filename)

    return result

# 安装 hook
import matplotlib.pyplot
_original_savefig = matplotlib.pyplot.savefig
matplotlib.pyplot.savefig = _hook_savefig

"""

    def _generate_postamble(self) -> str:
        """生成代码后记（提取和序列化检查点）"""

        return """
# ========== 提取中间结果 ==========
import json

# 导出检查点数据
if '_CHECKPOINT_DATA' in dir():
    print(f"\\n__CHECKPOINT__:{json.dumps(_CHECKPOINT_DATA, indent=2, default=str)}")
"""
```

#### 1.4.11 CheckpointStore 实现

**文件**: `backend/filestore/stores/checkpoint_store.py`

```python
import pickle
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.models.filestore import FileRef, FileCategory, CheckpointRef
from backend.filestore.base import BaseStore


class CheckpointStore(BaseStore):
    """
    检查点和中间结果存储

    特性:
    - 保存变量快照
    - 保存 DataFrame
    - 保存图表
    - 支持检查点恢复
    """

    def __init__(self, storage_dir: Path):
        super().__init__(storage_dir)
        self.checkpoints_dir = storage_dir
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def create_checkpoint(
        self,
        session_id: str,
        checkpoint_name: str,
        variables: Dict[str, Any],
        metadata: Optional[Dict] = None
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
                    serializable_vars[name] = {'type': 'dataframe', 'ref': df_ref}
                    file_refs.append(df_ref)

                elif self._is_chart(value):
                    # 图表: 保存为 PNG
                    chart_ref = self._save_chart(value, checkpoint_dir, name)
                    serializable_vars[name] = {'type': 'chart', 'ref': chart_ref}
                    file_refs.append(chart_ref)

                elif self._is_serializable(value):
                    # 可序列化对象
                    serializable_vars[name] = {
                        'type': 'serializable',
                        'data': self._serialize_value(value)
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
                    # 从文件恢复 DataFrame
                    restored_vars[name] = self._load_dataframe(var_info['ref'], checkpoint_dir)

                elif var_info['type'] == 'chart':
                    # 图表暂不支持恢复（只返回引用）
                    restored_vars[name] = var_info['ref']

                elif var_info['type'] == 'serializable':
                    # 反序列化对象
                    restored_vars[name] = self._deserialize_value(var_info['data'])

                else:
                    restored_vars[name] = None

            except Exception as e:
                restored_vars[name] = None

        return restored_vars

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
        df: "pd.DataFrame",
        checkpoint_dir: Path,
        name: str
    ) -> FileRef:
        """保存 DataFrame"""
        # 使用 parquet 格式（高效）
        file_path = checkpoint_dir / f"df_{name}.parquet"

        try:
            import pandas as pd
            df.to_parquet(file_path, index=False)

            # 计算哈希
            content_hash = hashlib.md5(file_path.read_bytes()).hexdigest()

            return FileRef(
                file_id=f"df_{name}",
                category=FileCategory.TEMP,
                size_bytes=file_path.stat().st_size,
                hash=content_hash,
                metadata={
                    'type': 'dataframe',
                    'format': 'parquet',
                    'rows': len(df),
                    'columns': list(df.columns)
                }
            )
        except Exception as e:
            raise ValueError(f"Failed to save DataFrame: {e}")

    def _save_chart(
        self,
        fig,
        checkpoint_dir: Path,
        name: str
    ) -> FileRef:
        """保存图表"""
        file_path = checkpoint_dir / f"chart_{name}.png"

        try:
            fig.savefig(file_path, format='png', bbox_inches='tight')

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
        except Exception as e:
            raise ValueError(f"Failed to save chart: {e}")

    def _load_dataframe(self, file_ref: FileRef, checkpoint_dir: Path) -> Any:
        """加载 DataFrame"""
        try:
            import pandas as pd
            file_path = checkpoint_dir / f"{file_ref.file_id}.parquet"
            return pd.read_parquet(file_path)
        except Exception as e:
            raise ValueError(f"Failed to load DataFrame: {e}")

    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        return pickle.dumps(value).hex()

    def _deserialize_value(self, hex_str: str) -> Any:
        """反序列化值"""
        return pickle.loads(bytes.fromhex(hex_str))

    def list_checkpoints(self, session_id: str) -> List[CheckpointRef]:
        """列出会话的所有检查点"""
        checkpoint_dir = self.checkpoints_dir / session_id

        if not checkpoint_dir.exists():
            return []

        checkpoints = []
        for metadata_file in checkpoint_dir.glob("*.json"):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            # 获取文件引用
            file_refs = []
            for var_name, var_info in metadata.get('variables', {}).items():
                if 'ref' in var_info:
                    file_refs.append(FileRef(
                        file_id=var_info['ref'].split(':')[1],
                        category=FileCategory(var_info['ref'].split(':')[0])
                    ))

            checkpoints.append(CheckpointRef(
                checkpoint_id=metadata['checkpoint_id'],
                session_id=metadata['session_id'],
                name=metadata['name'],
                variables=list(metadata.get('variables', {}).keys()),
                file_refs=file_refs,
                metadata=metadata
            ))

        return sorted(checkpoints, key=lambda x: x.created_at)

    def delete_session_checkpoints(self, session_id: str) -> int:
        """删除会话的所有检查点"""
        checkpoint_dir = self.checkpoints_dir / session_id

        if not checkpoint_dir.exists():
            return 0

        import shutil
        shutil.rmtree(checkpoint_dir)
        return 1

    # ========== BaseStore 接口实现（最小化） ==========

    def store(self, content: bytes, **metadata) -> FileRef:
        """存储（兼容 BaseStore）"""
        # 检查点存储通常不直接使用此方法
        raise NotImplementedError("Use create_checkpoint() instead")

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
```

#### 1.4.12 增强的 PythonSandbox

**修改**: `tools/python_sandbox.py`

```python
from backend.filestore.checkpoint import CheckpointCapture
from backend.filestore.file_store import FileStore


class PythonSandbox:
    """Python 沙盒（增强版：支持中间结果捕获）"""

    def __init__(self, ..., file_store: Optional[FileStore] = None):
        # 现有初始化
        ...

        # 新增: CheckpointCapture 支持
        self.file_store = FileStore() if file_store is None else file_store

    def execute_with_checkpoints(
        self,
        code: str,
        session_id: str,
        enable_checkpoints: bool = True,
        checkpoint_interval: int = 0  # 0 = 仅在 checkpoint() 调用时
    ) -> PythonExecutionResult:
        """
        执行 Python 代码并捕获中间结果

        Args:
            code: Python 代码
            session_id: 会话 ID
            enable_checkpoints: 是否启用检查点
            checkpoint_interval: 自动检查点间隔（0 = 手动）

        Returns:
            PythonExecutionResult:
                - output: 标准输出
                - checkpoints: 检查点列表
                - file_refs: 生成的文件引用
        """

        # 创建检查点捕获器
        capture = CheckpointCapture(
            session_id=session_id,
            checkpoint_store=self.file_store.checkpoints
        )

        # 执行代码并捕获
        exec_result = capture.capture_execution(
            code=code,
            sandbox=self,
            enable_auto_capture=enable_checkpoints
        )

        # 转换为 ToolExecutionResult
        return ToolExecutionResult(
            tool_call_id=...,
            observation=self._format_output_with_checkpoints(exec_result),
            output_level=OutputLevel.STANDARD,
            tool_name="run_python",
            file_refs=exec_result.file_refs,
            metadata={
                'checkpoints': exec_result.checkpoints
            }
        )

    def _format_output_with_checkpoints(self, result: "ExecutionResult") -> str:
        """格式化输出（包含检查点信息）"""
        output = result.output

        if result.checkpoints:
            output += f"\n\n{len(result.checkpoints)} checkpoints created:\n"
            for cp in result.checkpoints:
                output += f"  - {cp.name} ({len(cp.variables)} variables)\n"

        if result.file_refs:
            output += f"\n{len(result.file_refs)} files saved:\n"
            for ref in result.file_refs:
                output += f"  - {ref.category.value}:{ref.file_id}\n"

        return output
```

---

### Phase 6: 配置系统 (Day 6-7)

#### 1.4.13 配置文件

**文件**: `config/filestore.yaml`

```yaml
# BA-Agent 文件系统配置

filestore:
  # 存储根目录
  base_dir: "/var/lib/ba-agent"

  # 全局限制
  max_total_size_gb: 10
  cleanup_interval_hours: 1
  cleanup_threshold_percent: 90

  # 各类别配置
  categories:
    artifact:
      dir: "artifacts"
      max_size_mb: 1000
      ttl_hours: 24
      compression: true

    upload:
      dir: "uploads"
      max_size_mb: 50
      ttl_hours: 168  # 7 days
      allowed_types:
        - xlsx
        - xls
        - csv
      max_file_size_mb: 50

    report:
      dir: "reports"
      max_size_mb: 500
      ttl_hours: 720  # 30 days
      formats:
        - pdf
        - docx
        - xlsx
        - html

    chart:
      dir: "charts"
      max_size_mb: 100
      ttl_hours: 168  # 7 days
      formats:
        - png
        - svg
        - html

    cache:
      dir: "cache"
      max_size_mb: 200
      ttl_hours: 1

    temp:
      dir: "temp"
      max_size_mb: 50
      ttl_hours: 0  # 立即清理

    memory:
      dir: "memory"
      ttl_hours: 8760  # 永久（不清理）
      layers:
        daily:
          dir: "daily"
          format: "markdown"
        context:
          dir: "context"
          files:
            - CLAUDE.md
            - MEMORY.md
            - USER.md
        knowledge:
          dir: "knowledge"
          categories:
            - world
            - experience
            - opinions

    checkpoint:
      dir: "temp/checkpoints"
      ttl_hours: 24
      max_checkpoints_per_session: 100

  # 安全配置
  security:
    enable_virus_scan: false
    max_path_depth: 10
    allowed_symlinks: false

  # 索引配置
  index:
    enable_fts: true
    enable_vector: true
    vector_dimension: 1536
```

#### 1.4.14 配置加载器

**文件**: `backend/filestore/config.py`

```python
from pathlib import Path
from typing import Optional
import yaml

from pydantic import BaseModel


class FileStoreConfig(BaseModel):
    """文件系统配置"""
    base_dir: Path
    max_total_size_gb: int
    cleanup_interval_hours: int
    categories: dict

    @classmethod
    def from_yaml(cls, config_path: Optional[Path] = None) -> "FileStoreConfig":
        """从 YAML 文件加载配置"""

        if config_path is None:
            config_path = Path("config/filestore.yaml")

        if not config_path.exists():
            # 使用默认配置
            return cls.get_default()

        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        return cls(**data['filestore'])

    @classmethod
    def get_default(cls) -> "FileStoreConfig":
        """获取默认配置"""
        return cls(
            base_dir=Path("/var/lib/ba-agent"),
            max_total_size_gb=10,
            cleanup_interval_hours=1,
            categories={}
        )
```

---

# 2. Excel 上传处理流程

## 2.1 业务场景

1. 用户通过 Web 界面上传 Excel/CSV 数据文件
2. 系统解析文件并存储到临时位置
3. 用户通过自然语言查询（如"分析今天的 GMV 趋势"）
4. Agent 调用数据分析工具处理上传的数据
5. 返回分析结果或可视化图表

## 2.2 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   前端页面   │     │  FastAPI    │     │   BA-Agent  │
│  (Vue/React)│────▶│   Server    │────▶│   Engine    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ FileStore   │
                    │ (UploadStore)│
                    └─────────────┘
```

## 2.3 数据流

```
用户上传 Excel
    │
    ▼
FastAPI 文件上传接口
    │
    ├── 文件验证 (格式、大小)
    ├── 文件存储 (生成唯一路径)
    ├── 元数据提取 (列名、行数、预览)
    └── 返回 file_id
    │
    ▼
用户发送查询 (附带 file_id)
    │
    ▼
FastAPI Agent 接口
    │
    ├── 构建 file_reader_tool 调用
    ├── 构建 Agent context (包含 file_id)
    └── 调用 BAAgent.invoke()
    │
    ▼
BA-Agent 处理
    │
    ├── 调用 file_reader_tool 读取数据
    ├── 调用 run_python_tool 分析数据
    ├── 调用其他工具 (vector_search, web_search 等)
    └── 返回结果
    │
    ▼
FastAPI 返回响应
```

---

# 3. FastAPI 服务实现

## 3.1 API 设计

### 3.1.1 文件上传接口

```python
POST /api/v1/files/upload

Request:
- Content-Type: multipart/form-data
- Body: file (UploadFile)

Response:
{
    "success": true,
    "data": {
        "file_id": "f_20250206_abc123",
        "filename": "sales_data.xlsx",
        "file_path": "/var/lib/ba-agent/uploads/sessions/xxx/f_20250206_abc123.xlsx",
        "size": 102400,
        "format": "excel",
        "created_at": "2026-02-06T10:00:00Z",
        "metadata": {
            "sheets": ["Sheet1", "Sheet2"],
            "total_rows": 1000,
            "columns": ["date", "gmv", "orders", "conversion_rate"],
            "preview": [
                {"date": "2026-01-01", "gmv": 10000, "orders": 50, "conversion_rate": 0.05},
                ...
            ]
        }
    }
}
```

### 3.1.2 文件元数据接口

```python
GET /api/v1/files/{file_id}/metadata

Response:
{
    "success": true,
    "data": {
        "file_id": "f_20250206_abc123",
        "filename": "sales_data.xlsx",
        "metadata": {
            "sheets": ["Sheet1", "Sheet2"],
            "total_rows": 1000,
            "columns": ["date", "gmv", "orders", "conversion_rate"],
            "data_types": {
                "date": "datetime",
                "gmv": "float64",
                "orders": "int64",
                "conversion_rate": "float64"
            },
            "preview": [...]
        }
    }
}
```

### 3.1.3 Agent 查询接口

```python
POST /api/v1/agent/query

Request:
{
    "message": "分析今天 GMV 的趋势",
    "conversation_id": "conv_123",  // 可选
    "file_context": {
        "file_id": "f_20250206_abc123"
    }
}

Response:
{
    "success": true,
    "data": {
        "conversation_id": "conv_123",
        "response": "根据您上传的销售数据分析...",
        "tool_calls": [
            {
                "tool": "read_file",
                "input": {"path": "/var/lib/ba-agent/uploads/..."},
                "output": "..."
            },
            {
                "tool": "run_python",
                "input": {...},
                "output": "..."
            }
        ],
        "artifacts": [
            {
                "type": "chart",
                "url": "/api/v1/artifacts/{artifact_id}"
            }
        ]
    }
}
```

## 3.2 服务结构

```
ba-agent/
├── backend/
│   ├── api/                    # 新增 API 模块
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI 应用入口
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── files.py        # 文件上传接口
│   │   │   ├── agent.py        # Agent 查询接口
│   │   │   └── artifacts.py    # 结果文件下载
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py       # 上传相关模型
│   │   │   └── agent.py        # Agent 相关模型
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── file_manager.py # 文件管理服务
│   │   │   └── agent_service.py
│   │   └── middleware/
│   │       ├── __init__.py
│   │       └── auth.py         # 认证中间件
│   └── ...
├── var/lib/ba-agent/           # 存储目录
│   └── uploads/                # 上传文件存储
└── ...
```

## 3.3 核心实现

### 3.3.1 文件管理服务

**文件**: `backend/api/services/file_manager.py`

```python
class FileManager:
    """文件管理服务"""

    def __init__(self, upload_dir: str = "/var/lib/ba-agent/uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, filename: str, content: bytes, session_id: str) -> FileMetadata:
        """保存上传文件"""
        # 使用 UploadStore
        from backend.filestore.file_store import FileStore

        file_store = FileStore()
        file_ref = file_store.uploads.store(
            content=content,
            filename=filename,
            session_id=session_id,
            user_id="user_123"  # 从认证获取
        )

        return FileMetadata(
            file_id=file_ref.file_id,
            filename=filename,
            file_path=file_ref.metadata.get('file_path'),
            size=file_ref.size_bytes,
            metadata=file_ref.metadata
        )
```

### 3.3.2 Agent 服务

**文件**: `backend/api/services/agent_service.py`

```python
class AgentService:
    """Agent 服务"""

    def __init__(self):
        self.agent = None  # BAAgent 实例

    async def query(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        file_context: Optional[FileContext] = None
    ) -> AgentResponse:
        """处理 Agent 查询"""

        # 如果有文件上下文，构建系统提示
        system_prompt = self._build_prompt_with_file(file_context)

        # 调用 BAAgent
        result = self.agent.invoke(
            message=message,
            conversation_id=conversation_id,
        )

        return AgentResponse(
            conversation_id=conversation_id,
            response=result["response"],
            tool_calls=result.get("tool_calls", []),
            artifacts=result.get("artifacts", [])
        )

    def _build_prompt_with_file(self, file_context: FileContext) -> str:
        """构建包含文件上下文的系统提示"""
        if not file_context:
            return ""

        return f"""
用户已上传数据文件: {file_context.filename}

可用数据列: {', '.join(file_context.metadata.get('columns', []))}

你可以使用以下工具分析数据:
1. read_file - 读取完整数据
2. run_python - 执行数据分析代码

请根据用户查询选择合适的工具进行分析。
"""
```

---

# 4. 测试计划

## 4.1 单元测试结构

```
tests/test_filestore/
├── __init__.py
├── conftest.py
├── test_base.py                  # BaseStore 接口测试
├── test_file_ref.py              # FileRef 模型测试
├── test_file_store.py            # FileStore 主类测试
├── test_security.py              # 安全访问控制测试
├── test_lifecycle.py             # 生命周期管理测试
├── test_checkpoint.py            # 中间结果存储测试
└── test_stores/
    ├── __init__.py
    ├── test_artifact_store.py    # ArtifactStore 测试
    ├── test_upload_store.py      # UploadStore 测试
    ├── test_report_store.py      # ReportStore 测试（基础）
    ├── test_chart_store.py       # ChartStore 测试（基础）
    ├── test_cache_store.py       # CacheStore 测试
    ├── test_temp_store.py        # TempStore 测试
    ├── test_checkpoint_store.py  # CheckpointStore 测试
    └── test_memory_store.py      # MemoryStore 测试
```

## 4.2 测试用例示例

### 4.2.1 MemoryStore 测试

**文件**: `tests/test_filestore/test_stores/test_memory_store.py`

```python
import pytest
from pathlib import Path
from datetime import date

from backend.models.filestore import FileRef, FileCategory, MemoryRef
from backend.filestore.stores.memory_store import MemoryStore


class TestMemoryStore:
    """MemoryStore 测试"""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """临时目录"""
        return tmp_path / "memory"

    @pytest.fixture
    def store(self, temp_dir):
        """MemoryStore 实例"""
        return MemoryStore(temp_dir)

    def test_write_daily_memory(self, store):
        """测试写入每日记忆"""
        content = "测试记忆内容"

        memory_ref = store.write_daily_memory(content)

        assert memory_ref.layer == MemoryLayer.DAILY
        assert memory_ref.file_id.startswith(date.today().isoformat())

        # 验证文件存在
        assert memory_ref.path.exists()

        # 验证内容
        stored_content = memory_ref.path.read_text(encoding='utf-8')
        assert content in stored_content

    def test_write_memory_with_file_refs(self, store):
        """测试写入带文件引用的记忆"""
        content = "用户分析了销售数据"
        file_refs = [
            FileRef(file_id="abc123", category=FileCategory.ARTIFACT),
            FileRef(file_id="def456", category=FileCategory.CHART)
        ]

        memory_ref = store.write_daily_memory(
            content=content,
            file_refs=file_refs
        )

        # 验证文件引用
        assert memory_ref.file_refs == file_refs

        # 验证引用块被添加到内容中
        stored_content = memory_ref.path.read_text(encoding='utf-8')
        assert "**关联文件**:" in stored_content
        assert "`artifact:abc123`" in stored_content
        assert "`chart:def456`" in stored_content

    def test_get_memory_with_refs(self, store):
        """测试获取记忆及其文件引用"""
        file_refs = [
            FileRef(file_id="abc123", category=FileCategory.ARTIFACT)
        ]

        memory_ref = store.write_daily_memory(
            content="测试内容",
            file_refs=file_refs
        )

        # 获取记忆
        memory = store.get_memory(memory_ref)

        assert memory.content == "测试内容"
        assert memory.file_refs == file_refs

    def test_extract_file_refs(self, store):
        """测试从内容中提取文件引用"""
        content = """
        测试内容

        **关联文件**:
        - `artifact:abc123`
        - `chart:def456`
        """

        refs = store._extract_file_refs(content)

        assert len(refs) == 2
        assert refs[0].file_id == "abc123"
        assert refs[0].category == FileCategory.ARTIFACT
        assert refs[1].file_id == "def456"
        assert refs[1].category == FileCategory.CHART
```

### 4.2.2 CheckpointStore 测试

**文件**: `tests/test_filestore/test_stores/test_checkpoint_store.py`

```python
import pytest
from pathlib import Path

from backend.models.filestore import FileRef, FileCategory
from backend.filestore.stores.checkpoint_store import CheckpointStore


class TestCheckpointStore:
    """CheckpointStore 测试"""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """临时目录"""
        return tmp_path / "checkpoints"

    @pytest.fixture
    def store(self, temp_dir):
        """CheckpointStore 实例"""
        return CheckpointStore(temp_dir)

    def test_create_checkpoint(self, store):
        """测试创建检查点"""
        variables = {
            'x': 42,
            'name': 'test'
        }

        checkpoint_ref = store.create_checkpoint(
            session_id="session_123",
            checkpoint_name="step1",
            variables=variables
        )

        assert checkpoint_ref.session_id == "session_123"
        assert checkpoint_ref.name == "step1"
        assert set(checkpoint_ref.variables) == {'x', 'name'}

    def test_restore_checkpoint(self, store):
        """测试恢复检查点"""
        variables = {'x': 42, 'y': 100}

        checkpoint_ref = store.create_checkpoint(
            session_id="session_123",
            checkpoint_name="step1",
            variables=variables
        )

        # 恢复检查点
        restored = store.restore_checkpoint(checkpoint_ref)

        assert restored['x'] == 42
        assert restored['y'] == 100

    def test_list_checkpoints(self, store):
        """测试列出检查点"""
        session_id = "session_123"

        # 创建多个检查点
        store.create_checkpoint(session_id, "step1", {'x': 1})
        store.create_checkpoint(session_id, "step2", {'y': 2})
        store.create_checkpoint(session_id, "step3", {'z': 3})

        # 列出检查点
        checkpoints = store.list_checkpoints(session_id)

        assert len(checkpoints) == 3
        assert checkpoints[0].name == "step1"
        assert checkpoints[1].name == "step2"
        assert checkpoints[2].name == "step3"
```

### 4.2.3 集成测试

**文件**: `tests/test_filestore/test_integration.py`

```python
import pytest
from pathlib import Path

from backend.filestore.file_store import FileStore
from backend.models.filestore import FileCategory
from backend.memory.flush import MemoryFlush
from backend.memory.search import MemorySearchEngine


class TestFileStoreIntegration:
    """文件系统集成测试"""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """临时存储目录"""
        storage_dir = tmp_path / "filestore"
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir

    @pytest.fixture
    def file_store(self, temp_dir):
        """FileStore 实例"""
        return FileStore(temp_dir)

    def test_store_and_retrieve_file(self, file_store):
        """测试存储和检索文件"""
        content = b"test content"

        # 存储
        file_ref = file_store.store_file(
            content=content,
            category=FileCategory.ARTIFACT,
            session_id="session_123"
        )

        # 检索
        retrieved = file_store.get_file(file_ref)

        assert retrieved == content

    def test_memory_with_file_refs_integration(self, file_store):
        """测试记忆与文件引用集成"""
        # 1. 存储一个文件
        file_ref = file_store.store_file(
            content=b"data",
            category=FileCategory.ARTIFACT
        )

        # 2. 写入记忆，引用该文件
        memory_ref = file_store.memory.write_daily_memory(
            content="用户分析了数据",
            file_refs=[file_ref]
        )

        # 3. 获取记忆
        memory = file_store.memory.get_memory(memory_ref)

        assert len(memory.file_refs) == 1
        assert memory.file_refs[0].file_id == file_ref.file_id

    def test_checkpoint_workflow(self, file_store):
        """测试完整检查点工作流"""
        session_id = "session_123"

        # 创建检查点
        checkpoint_ref = file_store.checkpoints.create_checkpoint(
            session_id=session_id,
            checkpoint_name="step1",
            variables={'x': 42, 'y': 100}
        )

        # 列出检查点
        checkpoints = file_store.checkpoints.list_checkpoints(session_id)
        assert len(checkpoints) == 1

        # 恢复检查点
        restored = file_store.checkpoints.restore_checkpoint(checkpoint_ref)
        assert restored['x'] == 42
        assert restored['y'] == 100
```

## 4.3 测试目标

| 模块 | 测试数 | 覆盖率目标 |
|------|--------|-----------|
| 基础模型 (file_ref.py) | 15 | 100% |
| FileStore 主类 | 20 | 90% |
| ArtifactStore | 10 | 90% |
| UploadStore | 15 | 85% |
| MemoryStore | 20 | 90% |
| CheckpointStore | 15 | 85% |
| 安全访问控制 | 10 | 85% |
| 生命周期管理 | 10 | 80% |
| 集成测试 | 20 | 80% |
| **总计** | **135** | **~85%** |

---

# 5. 验收标准

## 5.1 功能验收

- [ ] 所有文件类型可通过 FileStore 统一管理
- [ ] 记忆可以引用和关联其他文件
- [ ] 文件引用可被正确解析和访问
- [ ] 访问控制正常工作
- [ ] 过期文件自动清理
- [ ] Python 中间结果可保存和恢复
- [ ] 所有测试通过

## 5.2 性能验收

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 文件存储延迟 | < 100ms | 单元测试 |
| 文件检索延迟 | < 50ms | 单元测试 |
| 记忆搜索延迟 | < 200ms | 集成测试 |
| 检查点创建延迟 | < 500ms | 单元测试 |
| 清理任务耗时 | < 5s (1000 文件) | 集成测试 |

## 5.3 质量验收

- 单元测试覆盖率 > 85%
- 所有公共 API 有文档字符串
- 类型检查无错误 (mypy)
- 代码审查通过

---

# 6. 实施步骤

## 6.1 开发任务分解

| 任务 | 预估时间 | 依赖 |
|------|----------|------|
| **Phase 1: 基础框架** | | |
| 1.1 核心模型定义 | 3 小时 | - |
| 1.2 BaseStore 接口 | 2 小时 | 1.1 |
| 1.3 FileStore 主类 | 3 小时 | 1.2 |
| 1.4 单元测试 | 3 小时 | 1.3 |
| **Phase 2: 存储实现** | | |
| 2.1 ArtifactStore | 3 小时 | 1.3 |
| 2.2 UploadStore | 4 小时 | 1.3 |
| 2.3 ReportStore/ChartStore | 3 小时 | 1.3 |
| 2.4 CacheStore/TempStore | 2 小时 | 1.3 |
| 2.5 单元测试 | 4 小时 | 2.1-2.4 |
| **Phase 3: 记忆集成** | | |
| 3.1 MemoryStore 实现 | 4 小时 | 1.3 |
| 3.2 增强 MemoryFlush | 3 小时 | 3.1 |
| 3.3 增强 MemorySearch | 2 小时 | 3.1 |
| 3.4 集成测试 | 3 小时 | 3.1-3.3 |
| **Phase 4: 安全与生命周期** | | |
| 4.1 安全访问控制 | 3 小时 | - |
| 4.2 生命周期管理 | 4 小时 | - |
| 4.3 清理任务 | 2 小时 | 4.2 |
| 4.4 测试 | 2 小时 | 4.1-4.3 |
| **Phase 5: 中间结果存储** | | |
| 5.1 CheckpointCapture 实现 | 4 小时 | Phase 1 |
| 5.2 CheckpointStore 实现 | 5 小时 | Phase 1 |
| 5.3 增强 PythonSandbox | 4 小时 | Phase 1, 5.1, 5.2 |
| 5.4 单元测试 | 3 小时 | 5.1-5.3 |
| **Phase 6: 配置与集成** | | |
| 6.1 配置系统 | 2 小时 | - |
| 6.2 与 Pipeline 集成 | 3 小时 | 全部 |
| 6.3 端到端测试 | 3 小时 | 全部 |
| 6.4 文档编写 | 2 小时 | 全部 |
| **总计** | **81 小时** (~10 个工作日) | |

### 6.1.1 并行开发建议

可以并行开发的任务：
- **Team A**: Phase 1 (基础框架) + Phase 2 (存储实现)
- **Team B**: Phase 4 (安全与生命周期) + 配置系统
- **集成**: Phase 3 (记忆集成) + Phase 5 (中间结果) + Phase 6 (最终集成)

并行开发可缩短至 6-7 个工作日。

## 6.2 实施步骤

### Step 1: 环境准备
1. 创建功能分支: `feature/filestore`
2. 安装必要依赖
3. 创建目录结构

### Step 2: 核心开发（按 Phase 顺序）
1. 实现 Phase 1: 基础框架
2. 实现 Phase 2: 存储实现
3. 实现 Phase 3: 记忆集成
4. 实现 Phase 4: 安全与生命周期
5. 实现 Phase 5: 中间结果存储
6. 实现 Phase 6: 配置与集成

### Step 3: 测试
1. 运行所有单元测试
2. 运行集成测试
3. 性能测试
4. 安全测试

### Step 4: 文档
1. API 文档
2. 架构文档更新
3. 使用指南

### Step 5: 代码审查与合并
1. 提交 Pull Request
2. 代码审查
3. 修改完善
4. 合并到主分支

---

# 7. 后续优化

## 7.1 短期优化（1-2 周）

- [ ] 添加文件压缩支持
- [ ] 实现文件去重
- [ ] 添加文件版本历史
- [ ] 实现批量操作 API
- [ ] 添加 Excel 模板支持

## 7.2 中期优化（1-2 月）

- [ ] 支持对象存储（S3/OSS）
- [ ] 实现文件分发 CDN
- [ ] 添加文件预览功能
- [ ] 实现文件共享功能
- [ ] WebSocket 实时进度推送

## 7.3 长期优化（3-6 月）

- [ ] 分布式文件存储
- [ ] 文件加密存储
- [ ] 实现文件审计日志
- [ ] 添加文件标签系统
- [ ] 多租户隔离

---

## 8. 风险评估

### 8.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| **存储迁移** | 现有 DataStorage 需要兼容 | 中 | 使用适配器模式，保持向后兼容 |
| **性能问题** | 大量文件影响性能 | 中 | 实现缓存、索引、异步处理 |
| **路径安全** | 路径遍历攻击 | 高 | 严格的路径验证，沙盒隔离 |
| **引用完整性** | 文件引用失效 | 中 | 定期检查，提供修复工具 |
| **测试覆盖** | 测试不充分 | 低 | 详细的测试计划，TDD |

### 8.2 兼容性风险

| 组件 | 风险 | 缓解措施 |
|------|------|----------|
| **现有 Pipeline** | ToolExecutionResult 需要适配 | 新增 file_ref 字段，保持向后兼容 |
| **现有 MemoryFlush** | 需要增强支持文件引用 | 添加新方法，保留旧 API |
| **现有工具** | 工具返回需要支持 FileRef | 提供 ToolExecutionResult.with_file() |

---

## 9. 附录

### 9.1 相关文档

- `docs/architecture.md` - 产品愿景和技术架构
- `docs/PRD.md` - 产品需求文档
- `docs/project-structure.md` - 项目结构说明

### 9.2 现有代码参考

- `backend/pipeline/storage/__init__.py` - 现有 DataStorage
- `backend/memory/flush.py` - MemoryFlush 实现
- `backend/memory/search.py` - MemorySearch 实现
- `tools/python_sandbox.py` - Python 沙盒（需增强）

### 9.3 技术参考

- Python `pathlib` 文档
- Pydantic 模型验证
- SQLite FTS5 全文搜索
- 文件系统安全最佳实践
- Matplotlib 图表保存
- Pandas DataFrame 序列化

---

**文档版本**: v1.0
**创建日期**: 2026-02-06
**状态**: 待评审

**确认后即可开始实施** → 请确认是否开始开发？
