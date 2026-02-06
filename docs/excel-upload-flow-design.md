# Excel 上传处理流程设计

> 设计日期: 2026-02-06
> 作者: BA-Agent Development Team
> 状态: 设计阶段

---

## 1. 概述

本文档设计用户在前端页面上传 Excel 文件后，系统解析并由 Agent 处理的完整流程。

### 1.1 业务场景

1. 用户通过 Web 界面上传 Excel/CSV 数据文件
2. 系统解析文件并存储到临时位置
3. 用户通过自然语言查询（如"分析今天的 GMV 趋势"）
4. Agent 调用数据分析工具处理上传的数据
5. 返回分析结果或可视化图表

### 1.2 现有能力分析

| 能力 | 状态 | 说明 |
|------|------|------|
| Excel 读取 | ✅ 已有 | `file_reader_tool` 支持 pandas + openpyxl |
| Python 数据分析 | ✅ 已有 | `run_python_tool` 支持数据分析 |
| Agent 框架 | ✅ 已有 | LangGraph + Claude |
| FastAPI 服务 | ❌ 待实现 | US-021 |
| 文件上传接口 | ❌ 待实现 | 本文档设计 |
| 会话文件管理 | ❌ 待实现 | 本文档设计 |

---

## 2. 系统架构

### 2.1 组件图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   前端页面   │     │  FastAPI    │     │   BA-Agent  │
│  (Vue/React)│────▶│   Server    │────▶│   Engine    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ File Storage│
                    │ (/tmp/data) │
                    └─────────────┘
```

### 2.2 数据流

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

## 3. API 设计

### 3.1 文件上传接口

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
        "file_path": "/tmp/data/uploads/f_20250206_abc123.xlsx",
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

### 3.2 文件元数据接口

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

### 3.3 Agent 查询接口

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
                "input": {"path": "/tmp/data/uploads/f_20250206_abc123.xlsx"},
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

---

## 4. 实现方案

### 4.1 FastAPI 服务结构

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
├── data/
│   └── uploads/                # 上传文件存储
└── ...
```

### 4.2 核心实现

#### 4.2.1 文件管理服务 (file_manager.py)

```python
class FileManager:
    """文件管理服务"""

    def __init__(self, upload_dir: str = "/tmp/data/uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, filename: str, content: bytes) -> FileMetadata:
        """保存上传文件"""
        file_id = self._generate_file_id()
        file_path = self.upload_dir / f"{file_id}_{filename}"

        with open(file_path, "wb") as f:
            f.write(content)

        # 提取元数据
        metadata = await self._extract_metadata(str(file_path))

        return FileMetadata(
            file_id=file_id,
            filename=filename,
            file_path=str(file_path),
            size=len(content),
            metadata=metadata
        )

    def _generate_file_id(self) -> str:
        """生成唯一文件 ID"""
        timestamp = datetime.now().strftime("%Y%m%d")
        random_str = uuid.uuid4().hex[:8]
        return f"f_{timestamp}_{random_str}"

    async def _extract_metadata(self, file_path: str) -> dict:
        """提取 Excel/CSV 元数据"""
        try:
            import pandas as pd

            # 检测文件类型
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, nrows=100)
            else:
                df = pd.read_excel(file_path, nrows=100)

            return {
                "columns": list(df.columns),
                "preview": df.head(10).to_dict(orient='records'),
                "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()}
            }
        except Exception as e:
            return {"error": str(e)}
```

#### 4.2.2 Agent 服务 (agent_service.py)

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

#### 4.2.3 文件上传路由 (files.py)

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.api.services.file_manager import FileManager
from backend.api.models.upload import UploadResponse

router = APIRouter(prefix="/api/v1/files", tags=["files"])
file_manager = FileManager()

@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传 Excel/CSV 文件"""

    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(400, "仅支持 Excel (.xlsx, .xls) 和 CSV 文件")

    # 验证文件大小 (最大 50MB)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "文件大小不能超过 50MB")

    # 保存文件
    metadata = await file_manager.save_upload(file.filename, content)

    return UploadResponse(success=True, data=metadata)
```

---

## 5. 前端集成

### 5.1 前端页面流程

```vue
<template>
  <div class="data-analysis">
    <!-- 文件上传区域 -->
    <div class="upload-section">
      <el-upload
        :action="uploadUrl"
        :on-success="handleUploadSuccess"
        :before-upload="beforeUpload"
      >
        <el-button>上传 Excel/CSV</el-button>
      </el-upload>
    </div>

    <!-- 数据预览 -->
    <div v-if="fileData" class="preview-section">
      <h3>{{ fileData.filename }}</h3>
      <el-table :data="fileData.metadata.preview">
        <el-table-column
          v-for="col in fileData.metadata.columns"
          :key="col"
          :prop="col"
          :label="col"
        />
      </el-table>
    </div>

    <!-- 查询输入 -->
    <div class="query-section">
      <el-input
        v-model="query"
        placeholder="例如: 分析今天的 GMV 趋势"
        @keyup.enter="sendQuery"
      />
      <el-button @click="sendQuery">分析</el-button>
    </div>

    <!-- 分析结果 -->
    <div v-if="result" class="result-section">
      <div v-html="result.response"></div>
      <div v-if="result.artifacts" class="artifacts">
        <img
          v-for="artifact in result.artifacts"
          :key="artifact.url"
          :src="artifact.url"
        />
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      uploadUrl: '/api/v1/files/upload',
      query: '',
      fileData: null,
      result: null
    }
  },
  methods: {
    beforeUpload(file) {
      const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.csv')
      if (!isExcel) {
        this.$message.error('仅支持 Excel 和 CSV 文件')
      }
      return isExcel
    },
    handleUploadSuccess(response) {
      this.fileData = response.data
    },
    async sendQuery() {
      const response = await fetch('/api/v1/agent/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: this.query,
          file_context: { file_id: this.fileData.file_id }
        })
      })
      this.result = await response.json()
    }
  }
}
</script>
```

---

## 6. 实现优先级

### 6.1 MVP (最小可行产品)

| 任务 | 优先级 | 说明 |
|------|--------|------|
| FastAPI 基础框架 | P0 | US-021 部分 |
| 文件上传接口 | P0 | 核心功能 |
| 文件元数据提取 | P0 | 数据预览必需 |
| Agent 查询接口 | P0 | 核心功能 |
| 文件上下文注入 | P0 | Agent 理解数据 |

### 6.2 增强功能

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 文件清理机制 | P1 | 定期清理临时文件 |
| 多文件上传 | P1 | 支持多个数据源 |
| 会话历史 | P1 | 保存分析上下文 |
| 结果缓存 | P2 | 提升性能 |
| 可视化图表 | P2 | 图表生成和展示 |

---

## 7. 安全考虑

1. **文件验证**:
   - 文件类型白名单 (.xlsx, .xls, .csv)
   - 文件大小限制 (50MB)
   - 内容验证 (防止恶意文件)

2. **路径安全**:
   - 使用 file_id 而非原始文件名
   - 文件存储在隔离目录
   - 防止路径遍历攻击

3. **会话隔离**:
   - 每个会话的文件访问隔离
   - 定期清理过期文件

---

## 8. 下一步行动

1. **创建 FastAPI 项目结构** (backend/api/)
2. **实现文件管理服务** (file_manager.py)
3. **实现文件上传接口** (routes/files.py)
4. **实现 Agent 服务** (agent_service.py)
5. **集成测试**

---

**文档版本**: v1.0
**最后更新**: 2026-02-06
