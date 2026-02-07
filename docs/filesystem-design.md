# BA-Agent 文件系统设计

> 设计日期: 2026-02-06
> 作者: BA-Agent Development Team
> 状态: 设计阶段

---

## 1. 概述

BA-Agent 需要一个统一的文件系统来管理所有类型的文件存储需求，包括：
- **工具执行结果** - 大型数据集、分析结果
- **用户上传文件** - Excel、CSV 等数据文件
- **生成的报告** - PDF、Word、Excel 格式报告
- **可视化图表** - PNG、SVG 等图表文件
- **临时文件** - 中间计算结果

---

## 2. 现有能力分析

### 2.1 已有的存储组件

| 组件 | 位置 | 功能 | 限制 |
|------|------|------|------|
| **DataStorage** | `backend/pipeline/storage/` | Artifact 存储，安全路径抽象 | 仅支持 JSON，无文件类型分类 |
| **ToolExecutionResult** | `backend/models/pipeline/` | 工具结果模型，含 artifact_id | 需配合 DataStorage 使用 |
| **file_write_tool** | `tools/file_write.py` | Agent 主动写入文件 | 白名单目录限制 |
| **python_sandbox** | `tools/python_sandbox.py` | Docker 隔离 Python 执行 | 隔离环境内文件无法直接访问 |

### 2.2 文件生成场景扫描

| 场景 | 产生位置 | 文件类型 | 当前状态 |
|------|----------|----------|----------|
| **数据分析结果** | run_python_tool | DataFrame → JSON/CSV | ✅ 支持（通过 artifact） |
| **图表生成** | run_python_tool (matplotlib/plotly) | PNG/HTML/SVG | ⚠️ 未持久化 |
| **报告生成** | report_gen Skill | PDF/Word/Excel | ⏳ 框架待实现 |
| **用户上传** | FastAPI (规划中) | Excel/CSV | ⏳ 待设计 |
| **记忆文件** | MemoryFlush | Markdown | ✅ 支持 |
| **导出数据** | query_database | CSV/Excel | ⚠️ 未实现 |
| **缓存文件** | IdempotencyCache | JSON | ✅ 内存缓存 |

---

## 3. 文件系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BA-Agent 文件系统                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        统一文件管理层 (FileStore)                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │ │
│  │  │ ArtifactStore│  │ UploadStore  │  │ ReportStore  │  │ CacheStore   │  │ │
│  │  │ (工具结果)   │  │ (用户上传)   │  │ (报告文件)   │  │ (缓存文件)   │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│                                        ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        物理存储层 (FileStorage)                         │ │
│  │                                                                         │ │
│  │  /var/lib/ba-agent/                                                    │ │
│  │  ├── artifacts/           # 工具执行结果 (JSON)                        │ │
│  │  ├── uploads/             # 用户上传文件 (Excel/CSV)                     │ │
│  │  ├── reports/             # 生成的报告 (PDF/Word/Excel)                 │ │
│  │  ├── charts/              # 可视化图表 (PNG/HTML/SVG)                   │ │
│  │  ├── cache/               # 缓存文件 (JSON)                             │ │
│  │  ├── temp/                # 临时文件                                     │ │
│  │  └── exports/             # 数据导出 (CSV/Excel)                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 目录结构设计

```
/var/lib/ba-agent/                      # 存储根目录（可配置）
│
├── artifacts/                           # 工具执行结果 (当前 DataStorage)
│   ├── artifact_*.json                  # 大型数据集 JSON
│   └── metadata.json                    # Artifact 元数据
│
├── uploads/                             # 用户上传文件
│   ├── {session_id}/                    # 按会话隔离
│   │   ├── {file_id}_original.xlsx     # 原始文件
│   │   ├── {file_id}_parsed.json       # 解析后的元数据
│   │   └── {file_id}_preview.json      # 数据预览
│   └── uploads_index.db                # 上传文件索引 (SQLite)
│
├── reports/                             # 生成的报告
│   ├── {report_id}/
│   │   ├── report.pdf                  # PDF 报告
│   │   ├── report.docx                 # Word 报告
│   │   ├── report.xlsx                 # Excel 报告（带图表）
│   │   ├── metadata.json               # 报告元数据
│   │   └── assets/                     # 报告资源（图表等）
│   │       ├── chart_1.png
│   │       └── chart_2.png
│   └── reports_index.db                # 报告索引
│
├── charts/                              # 独立图表文件
│   ├── {chart_id}.png
│   ├── {chart_id}.html
│   └── charts_index.db
│
├── cache/                               # 缓存文件
│   ├── idempotency/                     # 幂等缓存
│   │   └── {cache_key}.json
│   └── semantic/                        # 语义缓存
│       └── {semantic_hash}.json
│
├── temp/                                # 临时文件
│   └── {session_id}/
│       └── {temp_id}.*
│
├── exports/                             # 数据导出
│   ├── {export_id}.csv
│   └── {export_id}.xlsx
│
└── filestore.db                        # 全局文件索引 (SQLite)
```

---

## 4. 核心组件设计

### 4.1 FileStore - 统一文件管理器

```python
class FileStore:
    """
    统一文件存储管理器

    职责:
    1. 管理所有类型的文件存储
    2. 提供统一的文件访问接口
    3. 处理文件生命周期（创建、读取、删除、清理）
    4. 维护文件索引和元数据
    5. 实现安全访问控制
    """

    def __init__(self, base_dir: Path = Path("/var/lib/ba-agent")):
        self.base_dir = base_dir
        self.artifacts = ArtifactStore(base_dir / "artifacts")
        self.uploads = UploadStore(base_dir / "uploads")
        self.reports = ReportStore(base_dir / "reports")
        self.charts = ChartStore(base_dir / "charts")
        self.cache = CacheStore(base_dir / "cache")
        self.temp = TempStore(base_dir / "temp")

    # 统一接口
    def store_file(self, content: bytes, category: FileCategory, **metadata) -> FileRef
    def get_file(self, file_ref: FileRef) -> bytes
    def delete_file(self, file_ref: FileRef) -> bool
    def list_files(self, category: FileCategory, filters: dict) -> list[FileRef]

    # 清理
    def cleanup_old_files(self, max_age_hours: int) -> CleanupStats
    def get_storage_stats(self) -> StorageStats
```

### 4.2 ArtifactStore - 工具结果存储

```python
class ArtifactStore:
    """
    工具执行结果存储

    继承当前 DataStorage 功能，增强支持:
    - 二进制数据（图表等）
    - 多种序列化格式
    - 自动压缩
    """

    def store_large_data(self, data: Any, compress: bool = True) -> ArtifactRef:
        """存储大型数据集（自动压缩）"""

    def store_binary(self, data: bytes, format: str) -> ArtifactRef:
        """存储二进制数据（图表等）"""

    def store_dataframe(self, df: "pd.DataFrame", format: str = "parquet") -> ArtifactRef:
        """存储 DataFrame（支持 Parquet/CSV/Feather）"""
```

### 4.3 UploadStore - 用户上传文件

```python
class UploadStore:
    """
    用户上传文件管理

    特性:
    - 按会话隔离
    - 自动解析元数据
    - 支持断点续传
    - 病毒扫描（可选）
    """

    def save_upload(
        self,
        file_data: bytes,
        filename: str,
        session_id: str,
        user_id: str
    ) -> UploadRef:
        """保存上传文件"""

    def get_metadata(self, upload_ref: UploadRef) -> FileMetadata:
        """获取文件元数据"""

    def get_preview(self, upload_ref: UploadRef, rows: int = 10) -> dict:
        """获取数据预览"""

    def delete_session_files(self, session_id: str) -> int:
        """删除会话的所有文件"""
```

### 4.4 ReportStore - 报告文件存储

```python
class ReportStore:
    """
    报告文件管理

    特性:
    - 多格式支持（PDF/Word/Excel/HTML）
    - 资源管理（图表、样式）
    - 增量生成
    - 版本控制
    """

    def create_report(self, report_spec: ReportSpec) -> ReportRef:
        """创建新报告"""

    def add_asset(self, report_ref: ReportRef, asset: bytes, asset_type: str) -> AssetRef:
        """添加报告资源（图表等）"""

    def finalize_report(self, report_ref: ReportRef) -> str:
        """完成报告生成，返回下载路径"""

    def get_report_url(self, report_ref: ReportRef) -> str:
        """获取报告下载 URL"""
```

### 4.5 ChartStore - 图表存储

```python
class ChartStore:
    """
    图表文件管理

    特性:
    - 多格式支持（PNG/SVG/HTML）
    - 交互式图表（Plotly）
    - 缩略图生成
    - 图表复用
    """

    def save_chart(
        self,
        chart_data: Union[bytes, "plt.Figure", "go.Figure"],
        format: ChartFormat,
        metadata: ChartMetadata
    ) -> ChartRef:
        """保存图表"""

    def get_thumbnail(self, chart_ref: ChartRef, size: tuple[int, int]) -> bytes:
        """获取缩略图"""

    def to_interactive_html(self, chart_ref: ChartRef) -> str:
        """转换为交互式 HTML"""
```

---

## 5. 文件引用系统

### 5.1 FileRef - 统一文件引用

```python
class FileRef(BaseModel):
    """
    统一文件引用

    特性:
    - 安全：不暴露真实路径
    - 可序列化：可在 JSON 中传输
    - 可验证：包含签名防篡改
    """
    file_id: str                    # 唯一 ID
    category: FileCategory           # 文件类别
    session_id: Optional[str]        # 所属会话
    created_at: float                # 创建时间
    size_bytes: int                  # 文件大小
    hash: str                        # 内容哈希
    mime_type: str                   # MIME 类型
    metadata: dict[str, Any]         # 扩展元数据
```

### 5.2 FileCategory 枚举

```python
class FileCategory(str, Enum):
    """文件类别"""

    # 工具相关
    ARTIFACT = "artifact"            # 工具执行结果
    CHART = "chart"                  # 图表文件
    CACHE = "cache"                  # 缓存文件
    TEMP = "temp"                    # 临时文件

    # 用户相关
    UPLOAD = "upload"                # 用户上传
    EXPORT = "export"                # 数据导出

    # 业务相关
    REPORT = "report"                # 报告文件
    MEMORY = "memory"                # 记忆文件
```

---

## 6. 与各系统的集成

### 6.1 与 Pipeline 集成

```python
# 在 ToolExecutionResult 中使用 FileRef

class ToolExecutionResult(BaseModel):
    # ... 现有字段 ...

    # 文件引用（新增）
    file_ref: Optional[FileRef] = None
    file_refs: list[FileRef] = []     # 多文件情况（如多个图表）

    def with_file(self, file_ref: FileRef) -> "ToolExecutionResult":
        """关联文件"""
        self.file_ref = file_ref
        return self

    def add_files(self, file_refs: list[FileRef]) -> "ToolExecutionResult":
        """添加多个文件"""
        self.file_refs.extend(file_refs)
        return self
```

### 6.2 与 Python 沙盒集成

```python
# 在 python_sandbox.py 中增强

class PythonSandbox:
    def execute_with_files(
        self,
        code: str,
        allow_uploads: bool = True,
        capture_plots: bool = True
    ) -> tuple[str, list[FileRef]]:
        """
        执行代码并捕获生成的文件

        捕获:
        - matplotlib 图表
        - plotly 图表
        - pandas DataFrame 导出
        - 文件写入操作
        """
```

### 6.3 与 Skills 集成

```python
# 在 report_gen Skill 中

def generate_report(data: dict, format: ReportFormat) -> ReportRef:
    """生成报告并返回文件引用"""

    # 1. 分析数据
    analysis = analyze_data(data)

    # 2. 生成图表
    charts = []
    for chart_spec in analysis.charts:
        chart_ref = file_store.charts.save_chart(
            chart_spec.data,
            format=chart_spec.format
        )
        charts.append(chart_ref)

    # 3. 创建报告
    report_ref = file_store.reports.create_report(
        ReportSpec(
            title=analysis.title,
            content=analysis.content,
            charts=charts,
            format=format
        )
    )

    return report_ref
```

### 6.4 与 FastAPI 集成

```python
# 在 FastAPI 路由中

@router.post("/files/upload")
async def upload_file(
    file: UploadFile,
    request: Request
) -> UploadResponse:
    """上传文件"""

    # 保存到 UploadStore
    upload_ref = await file_store.uploads.save_upload(
        file_data=await file.read(),
        filename=file.filename,
        session_id=request.state.session_id,
        user_id=request.state.user_id
    )

    # 提取元数据
    metadata = await file_store.uploads.get_metadata(upload_ref)

    return UploadResponse(
        success=True,
        data={
            "file_id": upload_ref.file_id,
            "metadata": metadata
        }
    )

@router.get("/files/{file_id}/download")
async def download_file(file_id: str, request: Request) -> FileResponse:
    """下载文件"""

    # 验证权限
    file_ref = file_store.get_file_ref(file_id)
    if file_ref.session_id != request.state.session_id:
        raise HTTPException(403, "Access denied")

    # 获取文件
    file_path = file_store.get_file_path(file_ref)
    return FileResponse(file_path)
```

---

## 7. 文件生命周期管理

### 7.1 生命周期阶段

```
创建 → 活跃 → 归档 → 删除
 │      │      │      │
 │      │      │      └──> 物理删除
 │      │      └───> 移至冷存储
 │      └───> 定期访问
 └──> 写入存储
```

### 7.2 TTL 策略

| 文件类别 | 默认 TTL | 清理策略 |
|----------|----------|----------|
| **ARTIFACT** | 24 小时 | LRU 清理 |
| **UPLOAD** | 7 天 | 会话结束后清理 |
| **REPORT** | 30 天 | 按需保留 |
| **CHART** | 7 天 | 关联报告删除时清理 |
| **CACHE** | 1 小时 | 定时清理 |
| **TEMP** | 立即 | 会话结束时清理 |

### 7.3 清理任务

```python
class FileCleanupTask:
    """后台清理任务"""

    async def run_cleanup_cycle(self):
        """执行一次清理循环"""

        # 1. 过期文件清理
        for category in FileCategory:
            expired = file_store.list_expired(category)
            for ref in expired:
                file_store.delete_file(ref)

        # 2. 存储空间检查
        stats = file_store.get_storage_stats()
        if stats.usage_percent > 90:
            file_store.cleanup_old_files()

        # 3. 孤立文件清理
        orphans = file_store.find_orphan_files()
        for ref in orphans:
            file_store.delete_file(ref)
```

---

## 8. 安全性设计

### 8.1 访问控制

```python
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
        1. UPLOAD 文件：仅上传者可访问
        2. REPORT 文件：会话参与者可访问
        3. ARTIFACT 文件：同一会话可访问
        4. CHART 文件：继承关联报告的权限
        """
```

### 8.2 路径安全

```python
class SecurePathResolver:
    """安全路径解析器"""

    def resolve(self, file_ref: FileRef) -> Path:
        """
        解析文件引用为物理路径

        安全措施:
        1. 验证 file_id 格式
        2. 禁止路径遍历
        3. 确保路径在存储目录内
        4. 返回绝对路径
        """
```

### 8.3 内容验证

```python
class FileValidator:
    """文件内容验证器"""

    def validate_upload(self, file_data: bytes, filename: str) -> ValidationResult:
        """
        验证上传文件

        检查:
        1. 文件大小限制
        2. 文件类型白名单
        3. 病毒扫描（可选）
        4. 内容格式验证
        """
```

---

## 9. API 设计

### 9.1 FileStore API

```python
# 存储
file_ref = file_store.store_file(
    content=b"...",
    category=FileCategory.ARTIFACT,
    session_id="session_123",
    metadata={"source": "python_tool"}
)

# 读取
content = file_store.get_file(file_ref)

# 列表
files = file_store.list_files(
    category=FileCategory.UPLOAD,
    filters={"session_id": "session_123"}
)

# 删除
file_store.delete_file(file_ref)

# 清理
stats = file_store.cleanup_old_files(max_age_hours=24)
```

### 9.2 Agent 工具集成

```python
# 在工具中返回文件引用

def run_python_impl(code: str, ...) -> ToolExecutionResult:
    """执行 Python 并返回结果"""

    # 执行代码
    result = sandbox.execute(code)

    # 检测生成的文件
    if result.plots:
        file_refs = []
        for plot in result.plots:
            ref = file_store.charts.save_chart(plot, format="png")
            file_refs.append(ref)

        return ToolExecutionResult(
            tool_call_id=...,
            observation="图表已生成",
            file_refs=file_refs
        )

    return ToolExecutionResult(...)
```

---

## 10. 配置管理

### 10.1 配置项

```yaml
# config/filestore.yaml

filestore:
  base_dir: "/var/lib/ba-agent"

  # 各类别配置
  artifacts:
    dir: "artifacts"
    max_size_mb: 1000
    ttl_hours: 24
    compression: true

  uploads:
    dir: "uploads"
    max_size_mb: 50
    ttl_hours: 168  # 7 days
    allowed_types: ["xlsx", "xls", "csv"]

  reports:
    dir: "reports"
    max_size_mb: 500
    ttl_hours: 720  # 30 days

  charts:
    dir: "charts"
    max_size_mb: 100
    ttl_hours: 168

  cache:
    dir: "cache"
    max_size_mb: 200
    ttl_hours: 1

  temp:
    dir: "temp"
    max_size_mb: 50
    ttl_hours: 0  # 立即清理

  # 全局配置
  cleanup_interval_hours: 1
  max_total_size_gb: 10
  enable_virus_scan: false
```

---

## 11. 实现计划

### Phase 1: 核心框架 (P0)
- [ ] 实现 FileStore 基类
- [ ] 实现 ArtifactStore（基于现有 DataStorage）
- [ ] 实现 FileRef 和 FileCategory
- [ ] 实现安全路径解析
- [ ] 单元测试

### Phase 2: UploadStore (P0)
- [ ] 实现 UploadStore
- [ ] 会话隔离机制
- [ ] 文件元数据提取
- [ ] 与 FastAPI 集成
- [ ] 上传测试

### Phase 3: ReportStore (P1)
- [ ] 实现 ReportStore
- [ ] 多格式报告生成
- [ ] 资源管理
- [ ] 与 report_gen Skill 集成

### Phase 4: ChartStore (P1)
- [ ] 实现 ChartStore
- [ ] 图表格式转换
- [ ] 缩略图生成
- [ ] 与 python_sandbox 集成

### Phase 5: 生命周期管理 (P2)
- [ ] 清理任务调度
- [ ] TTL 策略实现
- [ ] 存储空间监控
- [ ] 孤立文件清理

---

## 12. 性能优化

### 12.1 存储优化

| 优化项 | 方案 | 预期效果 |
|--------|------|----------|
| **压缩** | gzip/zstd | 50-70% 空间节省 |
| **去重** | 内容寻址存储 | 30-50% 重复节省 |
| **分层** | 热/冷存储分离 | 减少热数据存储成本 |
| **索引** | SQLite 索引 | 查询速度提升 10x |

### 12.2 访问优化

```python
class CachedFileStore(FileStore):
    """带缓存的文件存储"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory_cache = LRUCache(maxsize=100)
        self.redis = redis_client  # 可选

    def get_file(self, file_ref: FileRef) -> bytes:
        # L1: 内存缓存
        if file_ref in self.memory_cache:
            return self.memory_cache[file_ref]

        # L2: Redis 缓存
        if self.redis:
            cached = self.redis.get(f"file:{file_ref.file_id}")
            if cached:
                return cached

        # L3: 磁盘存储
        data = super().get_file(file_ref)

        # 回填缓存
        self.memory_cache[file_ref] = data
        if self.redis:
            self.redis.setex(f"file:{file_ref.file_id}", 3600, data)

        return data
```

---

## 13. 监控与告警

### 13.1 监控指标

```python
class FileStoreMetrics:
    """文件存储指标"""

    def get_metrics(self) -> FileStoreMetrics:
        """获取监控指标"""

        return FileStoreMetrics(
            total_files=...,           # 总文件数
            total_size_gb=...,         # 总存储
            category_breakdown=...,    # 分类统计
            avg_file_size=...,         # 平均文件大小
            upload_count_24h=...,      # 24h上传数
            download_count_24h=...,    # 24h下载数
            error_count_24h=...,       # 24h错误数
        )
```

### 13.2 告警规则

| 指标 | 阈值 | 级别 | 动作 |
|------|------|------|------|
| 存储使用率 | >80% | Warning | 触发清理 |
| 存储使用率 | >95% | Critical | 紧急清理 |
| 上传失败率 | >5% | Warning | 检查服务 |
| 清理失败数 | >10 | Warning | 人工介入 |

---

## 14. 相关文档

| 文档 | 说明 |
|------|------|
| `backend/pipeline/storage/__init__.py` | 当前 DataStorage 实现 |
| `backend/models/pipeline/tool_result.py` | ToolExecutionResult 模型 |
| `docs/excel-upload-flow-design.md` | Excel 上传流程设计 |
| `tools/python_sandbox.py` | Python 沙盒工具 |

---

**文档版本**: v1.0
**最后更新**: 2026-02-06
**状态**: 设计评审中
