# 记忆系统与文件系统集成设计

> 设计日期: 2026-02-06
> 作者: BA-Agent Development Team
> 状态: 设计阶段

---

## 1. 分析：记忆系统现状

### 1.1 当前记忆系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           记忆系统架构                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        MemoryFlush (写入层)                              │ │
│  │  • Token 阈值触发                                                       │ │
│  │  • LLM 静声提取 (W/B/O 格式)                                            │ │
│  │  • 自动层级选择 (daily/longterm)                                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    Memory 文件存储 (存储层)                              │ │
│  │  memory/                                                                │ │
│  │  ├── YYYY-MM-DD.md           # Layer 1: 每日日志                         │ │
│  │  └── memory_index.db        # SQLite FTS5 索引                          │ │
│  │                                                                         │ │
│  │  根目录:                                                                 │ │
│  │  ├── MEMORY.md              # Layer 2: 长期记忆                          │ │
│  │  ├── CLAUDE.md              # Layer 3: 项目记忆                          │ │
│  │  └── USER.md                # 用户信息                                    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                   MemoryWatcher (监听层)                                 │ │
│  │  • 文件变更监听                                                         │ │
│  │  • 自动更新索引                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                  MemorySearch (搜索层)                                   │ │
│  │  • FTS5 全文搜索 (BM25)                                                 │ │
│  │  • 向量搜索 (Cosine)                                                    │ │
│  │  • 混合搜索 (70% 向量 + 30% 文本)                                       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 记忆系统特点

| 特性 | 描述 | 当前实现 |
|------|------|----------|
| **存储格式** | 纯文本 Markdown | ✅ |
| **目录结构** | 三层架构 | ✅ |
| **索引方式** | SQLite FTS5 + 向量 | ✅ |
| **搜索方式** | 混合搜索 | ✅ |
| **版本控制** | Git | ✅ |
| **文件引用** | 不支持 | ❌ |
| **二进制附件** | 不支持 | ❌ |
| **访问控制** | 无 | ❌ |

---

## 2. 集成需求分析

### 2.1 记忆可能需要文件引用的场景

```
场景 1: 记忆中提到数据文件
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
用户: "帮我分析 sales_2024_q1.xlsx 中的 GMV 趋势"
Agent: [分析数据并生成图表]
MemoryFlush: "用户分析了 Q1 销售数据，发现 GMV 增长 15%"
         → 需要关联 artifact_abc123 (分析结果)
         → 需要关联 chart_def456 (生成图表)

场景 2: 记忆中提到报告文件
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
用户: "生成上周的业务报告"
Agent: [生成 PDF 报告]
MemoryFlush: "用户生成了周报，包含 GMV、转化率分析"
         → 需要关联 report_123.pdf

场景 3: 记忆中包含分析图表
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Agent: "检测到 GMV 异常下降 15%"
        [附带异常分析图表]
MemoryFlush: "记录异常事件，附图表证据"
         → 需要能够存储图表引用
```

### 2.2 记忆需要文件支持的场景

| 需求 | 描述 | 优先级 |
|------|------|--------|
| **图表附件** | 记忆中引用可视化图表 | P1 |
| **数据文件引用** | 记忆中关联数据文件 | P1 |
| **报告链接** | 记忆中链接到生成的报告 | P2 |
| **富文本内容** | 支持图片、表格等 | P2 |
| **版本历史** | 记忆文件的版本管理 | P2 |

---

## 3. 集成设计方案

### 3.1 方案 A: 记忆作为文件系统的一个类别（推荐）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      统一文件系统架构（含记忆）                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FileStore                                                                  │
│  ├── ArtifactStore  # 工具执行结果                                          │
│  ├── UploadStore   # 用户上传文件                                           │
│  ├── ReportStore   # 生成的报告                                             │
│  ├── ChartStore    # 可视化图表                                             │
│  ├── CacheStore    # 缓存文件                                               │
│  ├── TempStore     # 临时文件                                               │
│  └── MemoryStore   # 记忆文件 ← 新增                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### MemoryStore 设计

```python
class MemoryStore:
    """
    记忆文件存储

    特性:
    - 继承 FileStore 基础能力
    - 保留 Markdown 格式
    - 支持文件引用
    - 保留索引能力
    - 特殊的生命周期管理
    """

    def __init__(self, base_dir: Path):
        # 记忆文件存储
        self.memory_dir = base_dir / "memory"           # 每日日志
        self.context_dir = base_dir / "context"         # 上下文文件
        self.knowledge_dir = base_dir / "knowledge"     # 知识库

    def write_memory(
        self,
        content: str,
        layer: MemoryLayer,
        file_refs: list[FileRef] = None,  # 新增：关联的文件
        attachments: list[Attachment] = None  # 新增：附件
    ) -> MemoryRef:
        """
        写入记忆

        支持富文本记忆：
        - Markdown 文本
        - 文件引用（自动解析）
        - 内联图片
        """

    def get_memory_with_refs(self, memory_ref: MemoryRef) -> MemoryWithRefs:
        """
        获取记忆及其关联的文件

        返回:
        {
            "content": "记忆文本内容",
            "file_refs": [...],  # 关联的文件引用
            "attachments": [...]  # 附件
        }
        """
```

#### 记忆引用格式

```markdown
# 记忆内容示例 (2026-02-06.md)

## 业务分析

用户分析了 Q1 销售数据，发现 GMV 增长 15%。

**关联文件**:
- 数据: `artifact:abc123`  # 原始数据
- 图表: `chart:def456`     # 趋势图
- 报告: `report:789xyz`   # 完整报告

## 异常检测

检测到 2月 3 日 GMV 异常下降。

![异常图表](chart:ghi789)  # 内联图片

详细分析见 `artifact:jkl012`
```

#### 文件引用解析

```python
class MemoryFileRefParser:
    """记忆文件引用解析器"""

    REF_PATTERN = r'(\w+):([a-zA-Z0-9_:.-]+)'

    def extract_refs(self, content: str) -> list[FileRef]:
        """从记忆内容中提取文件引用"""

        refs = []
        for match in re.finditer(self.REF_PATTERN, content):
            category = match.group(1)  # artifact, chart, report 等
            file_id = match.group(2)

            if category in FileCategory:
                refs.append(FileRef(
                    file_id=file_id,
                    category=FileCategory(category)
                ))

        return refs

    def resolve_refs(
        self,
        content: str,
        file_store: FileStore
    ) -> str:
        """
        解析文件引用为可访问的 URL

        artifact:abc123 → /api/files/artifact/abc123/download
        chart:def456 → /api/files/chart/def456/preview
        """
```

### 3.2 方案 B: 记忆系统独立，通过引用关联（备选）

```
┌──────────────────────────────┐     ┌──────────────────────────────┐
│      Memory System          │     │       FileStore              │
├──────────────────────────────┤     ├──────────────────────────────┤
│ • 独立的文件存储            │─────│• 文件引用查询                │
│ • Markdown 格式             │     │• 跨系统搜索                  │
│ • FTS5 索引                 │     │• 统一访问控制                │
│ • 向量搜索                  │     │                              │
└──────────────────────────────┘     └──────────────────────────────┘
                │                                  │
                │         引用层                  │
                └────────────┬───────────────────┘
                             ↓
                    ┌──────────────────┐
                    │  FileRefRegistry │
                    │  • 引用映射       │
                    │  • 权限同步       │
                    │  • 生命周期管理   │
                    └──────────────────┘
```

**优点**:
- 记忆系统保持独立
- 改动最小

**缺点**:
- 需要额外的同步机制
- 搜索需要跨系统

---

## 4. 推荐方案：记忆作为文件系统类别

### 4.1 架构设计

```
/var/lib/ba-agent/
│
├── memory/                             # 记忆文件目录
│   ├── 2026-02-06.md                   # 每日日志
│   ├── 2026-02-07.md
│   └── ...
│
├── context/                            # 上下文文件（新）
│   ├── CLAUDE.md                       # 项目记忆
│   ├── MEMORY.md                       # 长期记忆
│   └── USER.md                         # 用户信息
│
├── knowledge/                          # 知识库（新）
│   ├── world/                          # 世界事实
│   ├── experience/                     # 经验知识
│   └── opinions/                       # 观点记录
│
├── memory_index.db                     # 记忆索引（保留）
│
├── artifacts/                          # 工具结果
├── uploads/                            # 用户上传
├── reports/                            # 报告
└── charts/                             # 图表
```

### 4.2 MemoryStore 实现

```python
class MemoryStore:
    """记忆文件存储"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.daily_dir = base_dir / "memory"
        self.context_dir = base_dir / "context"
        self.knowledge_dir = base_dir / "knowledge"

        # 创建目录
        for dir_path in [self.daily_dir, self.context_dir, self.knowledge_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # ========== 写入接口 ==========

    def write_daily_memory(
        self,
        content: str,
        date: Optional[date] = None,
        file_refs: list[FileRef] = None,
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

        # 触发索引更新
        self._notify_indexer(file_path)

        return MemoryRef(
            file_id=file_path.stem,
            layer=MemoryLayer.DAILY,
            path=file_path,
            file_refs=file_refs or []
        )

    def write_context_memory(
        self,
        name: str,  # "CLAUDE", "MEMORY", "USER"
        content: str,
        file_refs: list[FileRef] = None
    ) -> MemoryRef:
        """写入上下文记忆"""

        file_path = self.context_dir / f"{name}.md"

        # 处理文件引用
        if file_refs:
            content = self._append_file_refs_block(content, file_refs)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return MemoryRef(
            file_id=name,
            layer=MemoryLayer.CONTEXT,
            path=file_path,
            file_refs=file_refs or []
        )

    def write_knowledge(
        self,
        category: str,  # "world", "experience", "opinions"
        key: str,
        content: str,
        file_refs: list[FileRef] = None
    ) -> MemoryRef:
        """写入知识库"""

        category_dir = self.knowledge_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        file_path = category_dir / f"{key}.md"

        # 处理文件引用
        if file_refs:
            content = self._append_file_refs_block(content, file_refs)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return MemoryRef(
            file_id=f"{category}/{key}",
            layer=MemoryLayer.KNOWLEDGE,
            path=file_path,
            file_refs=file_refs or []
        )

    # ========== 读取接口 ==========

    def get_memory(self, memory_ref: MemoryRef) -> MemoryContent:
        """获取记忆内容（含文件引用）"""

        content = self._read_file(memory_ref.path)

        # 解析文件引用
        file_refs = self._extract_file_refs(content)

        return MemoryContent(
            content=content,
            file_refs=file_refs,
            metadata=self._get_metadata(memory_ref)
        )

    def get_memory_with_resolved_refs(
        self,
        memory_ref: MemoryRef,
        file_store: FileStore
    ) -> MemoryWithResolvedRefs:
        """获取记忆并解析文件引用"""

        memory = self.get_memory(memory_ref)

        resolved_refs = []
        for ref in memory.file_refs:
            # 从 FileStore 获取文件
            file_data = file_store.get_file(ref)

            # 生成访问 URL
            url = file_store.get_access_url(ref)

            resolved_refs.append(ResolvedFileRef(
                file_ref=ref,
                data=file_data,
                url=url
            ))

        return MemoryWithResolvedRefs(
            content=memory.content,
            resolved_refs=resolved_refs
        )

    # ========== 搜索接口（保留现有能力）==========

    def search(
        self,
        query: str,
        layers: list[MemoryLayer] = None,
        hybrid: bool = True
    ) -> list[MemorySearchResult]:
        """
        搜索记忆

        使用现有的 MemoryIndexer 进行搜索
        返回匹配的记忆片段及其文件引用
        """

        # 调用现有 MemorySearch
        from backend.memory.search import MemorySearchEngine

        engine = MemorySearchEngine()
        results = engine.search(query, layers=layers, hybrid=hybrid)

        # 扩展结果，包含文件引用
        enriched_results = []
        for result in results:
            memory = self.get_memory(result.memory_ref)
            enriched_results.append(MemorySearchResult(
                **result.model_dump(),
                file_refs=memory.file_refs
            ))

        return enriched_results

    # ========== 内部方法 ==========

    def _append_file_refs_block(
        self,
        content: str,
        file_refs: list[FileRef]
    ) -> str:
        """在内容末尾添加文件引用块"""

        if not file_refs:
            return content

        refs_block = "\n\n**关联文件**:\n"
        for ref in file_refs:
            refs_block += f"- `{ref.category.value}:{ref.file_id}`\n"

        return content + refs_block

    def _extract_file_refs(self, content: str) -> list[FileRef]:
        """从内容中提取文件引用"""
        import re

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

    def _notify_indexer(self, file_path: Path):
        """通知索引器更新"""
        # 触发 MemoryWatcher 检测到变更
        # 或者直接调用 MemoryIndexer.update_index()
        pass
```

### 4.3 MemoryRef 模型

```python
class MemoryLayer(str, Enum):
    """记忆层级"""
    DAILY = "daily"              # 每日日志
    CONTEXT = "context"          # 上下文记忆
    KNOWLEDGE = "knowledge"      # 知识库


class MemoryRef(BaseModel):
    """记忆文件引用"""
    file_id: str                 # 文件标识
    layer: MemoryLayer           # 记忆层级
    path: Path                   # 文件路径
    created_at: float            # 创建时间
    file_refs: list[FileRef] = []  # 关联的文件引用


class MemoryContent(BaseModel):
    """记忆内容"""
    content: str                 # 原始内容
    file_refs: list[FileRef]     # 关联的文件引用
    metadata: dict               # 元数据


class ResolvedFileRef(BaseModel):
    """解析后的文件引用"""
    file_ref: FileRef            # 原始引用
    data: bytes                  # 文件数据
    url: str                     # 访问 URL
```

---

## 5. 与现有记忆系统集成

### 5.1 MemoryFlush 集成

```python
class MemoryFlush:
    """记忆自动持久化（增强版）"""

    def flush(
        self,
        messages: list[BaseMessage],
        context: dict
    ) -> FlushResult:
        """提取并保存记忆"""

        # 1. LLM 提取记忆
        extracted = self._extract_with_llm(messages)

        # 2. 检测文件引用
        file_refs = self._detect_file_refs(messages, context)

        # 3. 写入记忆（含文件引用）
        memory_ref = memory_store.write_daily_memory(
            content=extracted.content,
            file_refs=file_refs
        )

        return FlushResult(
            memory_ref=memory_ref,
            file_count=len(file_refs)
        )

    def _detect_file_refs(
        self,
        messages: list[BaseMessage],
        context: dict
    ) -> list[FileRef]:
        """检测对话中的文件引用"""

        refs = []

        # 从工具调用中提取
        for msg in messages:
            if hasattr(msg, 'tool_calls'):
                for call in msg.tool_calls:
                    if call.get('response_format') == 'file_ref':
                        refs.append(FileRef(
                            file_id=call.get('file_id'),
                            category=FileCategory(call.get('category'))
                        ))

        # 从上下文中提取
        if 'artifacts' in context:
            for artifact_id in context['artifacts']:
                refs.append(FileRef(
                    file_id=artifact_id,
                    category=FileCategory.ARTIFACT
                ))

        return refs
```

### 5.2 MemorySearch 集成

```python
class MemorySearchEngine:
    """记忆搜索引擎（增强版）"""

    def search(
        self,
        query: str,
        layers: list[MemoryLayer] = None,
        include_files: bool = True  # 新增
    ) -> list[MemorySearchResult]:
        """
        搜索记忆

        新增: 返回结果包含关联的文件引用
        """

        # 原有搜索逻辑
        results = self._search_index(query, layers)

        if not include_files:
            return results

        # 扩展结果，包含文件引用
        enriched = []
        for result in results:
            memory = memory_store.get_memory(result.memory_ref)
            enriched.append(MemorySearchResult(
                **result.model_dump(),
                file_refs=memory.file_refs
            ))

        return enriched
```

---

## 6. 统一搜索接口

### 6.1 全局搜索

```python
class GlobalSearchEngine:
    """
    全局搜索引擎

    统一搜索记忆和文件
    """

    def search_all(
        self,
        query: str,
        scope: SearchScope = SearchScope.ALL
    ) -> GlobalSearchResult:
        """
        全局搜索

        搜索范围:
        - 记忆文件
        - 上传文件
        - 报告
        - 图表
        - 工具结果
        """

        results = GlobalSearchResult()

        # 搜索记忆
        if scope in (SearchScope.ALL, SearchScope.MEMORY):
            results.memory_results = memory_store.search(query)

        # 搜索上传文件元数据
        if scope in (SearchScope.ALL, SearchScope.FILES):
            results.file_results = file_store.uploads.search_metadata(query)

        # 搜索报告
        if scope in (SearchScope.ALL, SearchScope.REPORTS):
            results.report_results = file_store.reports.search(query)

        return results


class SearchScope(str, Enum):
    """搜索范围"""
    ALL = "all"
    MEMORY = "memory"       # 仅记忆
    FILES = "files"         # 仅文件
    REPORTS = "reports"     # 仅报告
```

---

## 7. 生命周期管理

### 7.1 记忆文件的特殊性

| 特性 | 说明 | 处理方式 |
|------|------|----------|
| **长期保留** | 记忆应长期保存 | 不自动清理 |
| **版本控制** | 需要保留修改历史 | Git 管理 |
| **可搜索性** | 需要快速检索 | FTS5 + 向量索引 |
| **关联完整性** | 文件引用失效处理 | 定期检查引用 |

### 7.2 引用完整性检查

```python
class ReferenceIntegrityChecker:
    """引用完整性检查器"""

    def check_references(self) -> IntegrityReport:
        """
        检查所有记忆中的文件引用

        检查项:
        1. 引用的文件是否存在
        2. 孤立的文件（无记忆引用）
        3. 失效的引用
        """

        report = IntegrityReport()

        # 扫描所有记忆文件
        for memory_ref in memory_store.list_all():
            memory = memory_store.get_memory(memory_ref)

            for ref in memory.file_refs:
                # 检查文件是否存在
                exists = file_store.file_exists(ref)

                if not exists:
                    report.broken_refs.append(BrokenRef(
                        memory_ref=memory_ref,
                        file_ref=ref
                    ))

        # 检查孤立文件
        all_refs = set()
        for memory in memory_store.list_all():
            all_refs.update(memory.file_refs)

        for file_ref in file_store.list_all():
            if file_ref not in all_refs:
                report.orphan_files.append(file_ref)

        return report
```

---

## 8. API 设计

### 8.1 记忆 API（含文件引用）

```python
# 写入记忆（含文件引用）
memory_ref = memory_store.write_daily_memory(
    content="用户分析了销售数据，发现 GMV 增长 15%",
    file_refs=[
        FileRef(file_id="abc123", category=FileCategory.ARTIFACT),
        FileRef(file_id="def456", category=FileCategory.CHART)
    ]
)

# 读取记忆（含文件引用）
memory = memory_store.get_memory_with_resolved_refs(
    memory_ref=memory_ref,
    file_store=file_store
)

# 搜索记忆（含文件引用）
results = memory_store.search(
    query="GMV 分析",
    include_files=True
)
```

### 8.2 FastAPI 集成

```python
@router.post("/memory/write")
async def write_memory(
    request: MemoryWriteRequest,
    file_refs: list[str] = None  # ["artifact:abc123", "chart:def456"]
):
    """写入记忆（支持文件引用）"""

    # 解析文件引用
    refs = []
    if file_refs:
        refs = [FileRef.from_string(ref) for ref in file_refs]

    # 写入记忆
    memory_ref = memory_store.write_daily_memory(
        content=request.content,
        layer=request.layer,
        file_refs=refs
    )

    return MemoryWriteResponse(memory_ref=memory_ref)


@router.get("/memory/{memory_id}")
async def get_memory(
    memory_id: str,
    include_files: bool = True
):
    """获取记忆（可包含关联文件）"""

    memory_ref = MemoryRef.from_string(memory_id)

    if include_files:
        memory = memory_store.get_memory_with_resolved_refs(
            memory_ref=memory_ref,
            file_store=file_store
        )
    else:
        memory = memory_store.get_memory(memory_ref)

    return MemoryResponse(memory=memory)
```

---

## 9. 实现计划

### Phase 1: MemoryStore 基础实现 (P0)
- [ ] 实现 MemoryStore 类
- [ ] 实现 MemoryRef 和相关模型
- [ ] 实现文件引用解析器
- [ ] 单元测试

### Phase 2: MemoryFlush 集成 (P0)
- [ ] 增强 MemoryFlush 支持文件引用
- [ ] 实现文件引用检测
- [ ] 集成测试

### Phase 3: MemorySearch 增强 (P1)
- [ ] 搜索结果包含文件引用
- [ ] 实现统一搜索接口
- [ ] FastAPI 集成

### Phase 4: 引用完整性 (P2)
- [ ] 实现引用完整性检查
- [ ] 孤立文件检测
- [ ] 定期清理任务

### Phase 5: 高级特性 (P2)
- [ ] 记忆附件（内联图片）
- [ ] 富文本记忆
- [ ] 记忆版本历史

---

## 10. 相关文档

| 文档 | 说明 |
|------|------|
| `docs/filesystem-design.md` | 文件系统总体设计 |
| `backend/memory/flush.py` | MemoryFlush 实现 |
| `backend/memory/index.py` | MemoryIndexer 实现 |
| `backend/memory/search.py` | MemorySearch 实现 |

---

**文档版本**: v1.0
**最后更新**: 2026-02-06
**状态**: 设计评审中
