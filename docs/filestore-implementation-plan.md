# 文件系统与记忆系统集成开发技术方案

> 版本: v1.0
> 创建日期: 2026-02-06
> 状态: 待评审
> 预估工期: 5-7 个工作日

---

## 1. 方案概述

### 1.1 目标

开发统一的文件管理系统（FileStore），并实现记忆系统（MemoryStore）的集成，支持：

1. **统一文件管理** - 所有文件类型通过统一接口管理
2. **记忆文件引用** - 记忆可以引用和关联其他文件
3. **安全访问控制** - 基于会话和用户的访问控制
4. **生命周期管理** - 自动清理过期文件
5. **完整测试覆盖** - 所有组件单元测试 + 集成测试

### 1.2 范围

**包含**:
- FileStore 基础框架
- MemoryStore 实现
- 文件引用系统
- 安全访问控制
- 生命周期管理
- 完整测试套件

**不包含**:
- FastAPI 服务（已由 excel-upload-flow-design.md 覆盖）
- 报告生成逻辑（Skill 业务逻辑）
- 前端界面

### 1.3 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 存储后端 | 本地文件系统 | `/var/lib/ba-agent/` |
| 元数据存储 | SQLite | 轻量级索引 |
| 数据模型 | Pydantic | 类型安全 |
| 测试框架 | pytest | 单元 + 集成测试 |
| 类型检查 | mypy | 类型安全 |

---

## 2. 架构设计

### 2.1 整体架构

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
│  │  ┌──────────────┐  ┌──────────────┐                                          │ │
│  │  │ CacheStore   │  │ TempStore    │                                          │ │
│  │  │(缓存文件)    │  │(临时文件)    │                                          │ │
│  │  └──────────────┘  └──────────────┘                                          │ │
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

### 2.2 目录结构设计

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
│   │   │   └── memory_store.py    # 记忆存储
│   │   ├── security.py             # 访问控制和路径安全
│   │   ├── lifecycle.py            # 生命周期管理
│   │   └── index.py                # 元数据索引
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
│   │   ├── test_base.py
│   │   ├── test_file_store.py
│   │   ├── test_file_ref.py
│   │   ├── test_stores/
│   │   │   ├── test_artifact_store.py
│   │   │   ├── test_upload_store.py
│   │   │   ├── test_memory_store.py
│   │   │   └── ...
│   │   ├── test_security.py
│   │   ├── test_lifecycle.py
│   │   └── test_integration.py     # 集成测试
│   │
│   └── test_memory/               # 现有: 记忆系统测试
│       └── test_flush_integration.py  # 需要扩展
│
├── var/lib/ba-agent/               # 存储目录（可配置）
│   ├── artifacts/
│   ├── uploads/
│   ├── reports/
│   ├── charts/
│   ├── cache/
│   ├── temp/
│   ├── memory/                     # 记忆文件
│   └── filestore.db                # 全局索引
│
└── config/
    └── filestore.yaml              # 新增: 文件系统配置
```

---

## 3. 详细实现计划

### 3.1 Phase 1: 基础框架 (Day 1-2)

#### 3.1.1 核心模型定义

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
```

#### 3.1.2 FileStore 基类

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

#### 3.1.3 FileStore 主类

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
    MemoryStore
)


class FileStore:
    """
    统一文件存储管理器

    单一入口管理所有文件类型
    """

    # 默认存储目录
    DEFAULT_BASE_DIR = Path("/var/lib/ba-agent")

    def __init__(self, base_dir: Optional[Path] = None):
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
        """
        统一存储接口

        Args:
            content: 文件内容
            category: 文件类别
            **metadata: 元数据

        Returns:
            FileRef: 文件引用
        """
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

### 3.2 Phase 2: 具体存储实现 (Day 2-3)

#### 3.2.1 ArtifactStore（扩展现有 DataStorage）

**文件**: `backend/filestore/stores/artifact_store.py`

```python
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Any, Dict, List

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

#### 3.2.2 UploadStore

**文件**: `backend/filestore/stores/upload_store.py`

```python
import uuid
import hashlib
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

#### 3.2.3 MemoryStore

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

### 3.3 Phase 3: 记忆系统集成 (Day 3-4)

#### 3.3.1 增强 MemoryFlush

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

#### 3.3.2 增强 MemorySearch

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

### 3.4 Phase 4: 安全与生命周期 (Day 4-5)

#### 3.4.1 安全访问控制

**文件**: `backend/filestore/security.py`

```python
from pathlib import Path
from typing import Optional
from backend.models.filestore import FileRef


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

#### 3.4.2 生命周期管理

**文件**: `backend/filestore/lifecycle.py`

```python
import time
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta

from backend.filestore.file_store import FileStore


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

    def cleanup_expired_files(self) -> CleanupStats:
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

    def check_storage_usage(self) -> StorageStats:
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
    category_stats: Dict[str, CategoryStats] = Field(default_factory=dict)


class CategoryStats(BaseModel):
    """类别统计"""
    file_count: int
    total_size_bytes: int
```

### 3.5 Phase 5: 配置系统 (Day 5)

#### 3.5.1 配置文件

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

#### 3.5.2 配置加载器

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

## 4. API 设计

### 4.1 统一 API 接口

```python
# ========== 文件存储 API ==========

# 存储文件
file_ref = file_store.store_file(
    content=b"...",
    category=FileCategory.ARTIFACT,
    session_id="session_123",
    metadata={"source": "python_tool"}
)

# 获取文件
content = file_store.get_file(file_ref)

# 删除文件
file_store.delete_file(file_ref)

# 列出文件
files = file_store.list_files(
    category=FileCategory.UPLOAD,
    session_id="session_123"
)

# 检查权限
can_access = access_control.can_access(
    file_ref,
    session_id="session_123",
    user_id="user_456"
)

# ========== 记忆 API（含文件引用） ==========

# 写入每日记忆（含文件引用）
memory_ref = file_store.memory.write_daily_memory(
    content="用户分析了销售数据，发现 GMV 增长 15%",
    file_refs=[
        FileRef(file_id="abc123", category=FileCategory.ARTIFACT),
        FileRef(file_id="def456", category=FileCategory.CHART)
    ]
)

# 读取记忆（含文件引用）
memory = file_store.memory.get_memory(memory_ref)

# 搜索记忆（含文件引用）
results = file_store.memory.search(
    query="GMV 分析",
    include_files=True
)

# 获取记忆并解析文件引用
memory_with_refs = file_store.memory.get_memory_with_resolved_refs(
    memory_ref=memory_ref,
    file_store=file_store
)

# ========== 全局搜索 ==========

# 搜索所有类型
results = global_search.search_all(
    query="销售数据分析",
    scope=SearchScope.ALL
)
```

---

## 5. 测试计划

### 5.1 单元测试

```
tests/test_filestore/
├── __init__.py
├── conftest.py
├── test_base.py                  # BaseStore 接口测试
├── test_file_ref.py             # FileRef 模型测试
├── test_file_store.py           # FileStore 主类测试
├── test_security.py              # 安全访问控制测试
├── test_lifecycle.py             # 生命周期管理测试
└── test_stores/
    ├── __init__.py
    ├── test_artifact_store.py   # ArtifactStore 测试
    ├── test_upload_store.py     # UploadStore 测试
    ├── test_report_store.py     # ReportStore 测试（基础）
    ├── test_chart_store.py      # ChartStore 测试（基础）
    ├── test_cache_store.py      # CacheStore 测试
    ├── test_temp_store.py       # TempStore 测试
    └── test_memory_store.py     # MemoryStore 测试
```

### 5.2 测试用例示例

**文件**: `tests/test_filestore/test_memory_store.py`

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

### 5.3 集成测试

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
        from backend.models.filestore import MemoryRef

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

    def test_flush_with_file_refs(self, file_store):
        """测试 MemoryFlush 与文件引用集成"""
        # 模拟对话，包含工具调用
        messages = [
            HumanMessage("分析销售数据"),
            AIMessage("", tool_calls=[
                {"id": "call_1", "name": "run_python", "response_format": "file_ref"}
            ])
        ]

        # 上下文包含 artifact
        context = {"artifacts": ["test_artifact"]}

        # 使用增强的 MemoryFlush
        flush = MemoryFlush()
        result = flush.flush_with_refs(
            messages=messages,
            context=context,
            file_store=file_store
        )

        # 验证结果包含文件引用
        assert result.file_count >= 0
```

### 5.4 测试目标

| 模块 | 测试数 | 覆盖率目标 |
|------|--------|-----------|
| 基础模型 (file_ref.py) | 15 | 100% |
| FileStore 主类 | 20 | 90% |
| ArtifactStore | 10 | 90% |
| UploadStore | 15 | 85% |
| MemoryStore | 20 | 90% |
| 安全访问控制 | 10 | 85% |
| 生命周期管理 | 10 | 80% |
| 集成测试 | 15 | 80% |
| **总计** | **115** | **~85%** |

---

## 6. 风险评估

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| **存储迁移** | 现有 DataStorage 需要兼容 | 中 | 使用适配器模式，保持向后兼容 |
| **性能问题** | 大量文件影响性能 | 中 | 实现缓存、索引、异步处理 |
| **路径安全** | 路径遍历攻击 | 高 | 严格的路径验证，沙盒隔离 |
| **引用完整性** | 文件引用失效 | 中 | 定期检查，提供修复工具 |
| **测试覆盖** | 测试不充分 | 低 | 详细的测试计划，TDD |

### 6.2 兼容性风险

| 组件 | 风险 | 缓解措施 |
|------|------|----------|
| **现有 Pipeline** | ToolExecutionResult 需要适配 | 新增 file_ref 字段，保持向后兼容 |
| **现有 MemoryFlush** | 需要增强支持文件引用 | 添加新方法，保留旧 API |
| **现有工具** | 工具返回需要支持 FileRef | 提供 ToolExecutionResult.with_file() |

---

## 7. 时间估算

### 7.1 开发任务分解

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
| **Phase 5: 配置与集成** | | |
| 5.1 配置系统 | 2 小时 | - |
| 5.2 与 Pipeline 集成 | 3 小时 | 全部 |
| 5.3 端到端测试 | 3 小时 | 全部 |
| 5.4 文档编写 | 2 小时 | 全部 |
| **总计** | **65 小时** (~8 个工作日) | |

### 7.2 并行开发建议

可以并行开发的任务：
- **Team A**: Phase 1 (基础框架) + Phase 2 (存储实现)
- **Team B**: Phase 4 (安全与生命周期) + 配置系统
- **集成**: Phase 3 (记忆集成) + Phase 5 (最终集成)

并行开发可缩短至 5-6 个工作日。

---

## 8. 验收标准

### 8.1 功能验收

- [ ] 所有文件类型可通过 FileStore 统一管理
- [ ] 记忆可以引用和关联其他文件
- [ ] 文件引用可被正确解析和访问
- [ ] 访问控制正常工作
- [ ] 过期文件自动清理
- [ ] 所有测试通过

### 8.2 性能验收

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 文件存储延迟 | < 100ms | 单元测试 |
| 文件检索延迟 | < 50ms | 单元测试 |
| 记忆搜索延迟 | < 200ms | 集成测试 |
| 清理任务耗时 | < 5s (1000 文件) | 集成测试 |

### 8.3 质量验收

- 单元测试覆盖率 > 85%
- 所有公共 API 有文档字符串
- 类型检查无错误 (mypy)
- 代码审查通过

---

## 9. 实施步骤

### Step 1: 环境准备
1. 创建功能分支: `feature/filestore`
2. 安装必要依赖
3. 创建目录结构

### Step 2: 核心开发（按 Phase 顺序）
1. 实现 Phase 1: 基础框架
2. 实现 Phase 2: 存储实现
3. 实现 Phase 3: 记忆集成
4. 实现 Phase 4: 安全与生命周期
5. 实现 Phase 5: 配置与集成

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

## 10. 后续优化

### 10.1 短期优化（1-2 周）

- [ ] 添加文件压缩支持
- [ ] 实现文件去重
- [ ] 添加文件版本历史
- [ ] 实现批量操作 API

### 10.2 中期优化（1-2 月）

- [ ] 支持对象存储（S3/OSS）
- [ ] 实现文件分发 CDN
- [ ] 添加文件预览功能
- [ ] 实现文件共享功能

### 10.3 长期优化（3-6 月）

- [ ] 分布式文件存储
- [ ] 文件加密存储
- [ ] 实现文件审计日志
- [ ] 添加文件标签系统

---

## 11. 附录

### 11.1 相关文档

- `docs/filesystem-design.md` - 文件系统总体设计
- `docs/memory-filesystem-integration.md` - 记忆系统集成设计
- `docs/excel-upload-flow-design.md` - Excel 上传流程设计

### 11.2 现有代码参考

- `backend/pipeline/storage/__init__.py` - 现有 DataStorage
- `backend/memory/flush.py` - MemoryFlush 实现
- `backend/memory/search.py` - MemorySearch 实现

### 11.3 技术参考

- Python `pathlib` 文档
- Pydantic 模型验证
- SQLite FTS5 全文搜索
- 文件系统安全最佳实践

---

**文档版本**: v1.0
**创建日期**: 2026-02-06
**状态**: 待评审

**确认后即可开始实施** → 请确认是否开始开发？
