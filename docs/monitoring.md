# BA-Agent 监控系统文档

> **版本**: v2.4.0
> **更新时间**: 2026-02-08

本文档详细介绍 BA-Agent 的全流程监控和追踪系统。

## 📋 目录

- [系统概述](#系统概述)
- [架构设计](#架构设计)
- [核心组件](#核心组件)
- [指标说明](#指标说明)
- [API 端点](#api-端点)
- [监控仪表板](#监控仪表板)
- [配置选项](#配置选项)
- [开发指南](#开发指南)
- [故障排查](#故障排查)

## 系统概述

BA-Agent 监控系统提供了完整的 Agent 执行追踪和性能分析能力：

### 主要特性

- **完整执行追踪**: 追踪从 agent_invoke 到 LLM 调用、工具调用的完整链路
- **性能指标收集**: 自动收集 Token 使用、耗时、成本等指标
- **可视化仪表板**: 提供 Web 界面查看执行流程和性能数据
- **历史查询**: 支持按对话、时间范围查询历史执行数据
- **数据导出**: 支持 JSON 和 Mermaid 格式导出追踪数据

### 设计原则

- **低开销**: 监控系统本身对 Agent 性能的影响 < 5%
- **非侵入式**: 与现有 AgentLogger、FileStore 无缝集成
- **可扩展**: 支持自定义指标和追踪点
- **开发者友好**: 提供 API 和仪表板两种使用方式

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Agent 执行层                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  BAAgent.invoke()                                               │   │
│  │  - LangGraph Agent 执行                                         │   │
│  │  - 工具调用循环                                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Execution Tracer (新增)                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  - 追踪 span（父/子关系）                                       │   │
│  │  - 记录事件 (tool_call, llm_call, error, etc.)                 │   │
│  │  - 计时各阶段耗时                                               │   │
│  │  - 收集 Token 使用                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
┌─────────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│   Trace Store       │ │ Metrics Store │ │   AgentLogger        │
│  (FileStore)         │ │ (FileStore)   │  (现有，增强)          │
│  - Execution Traces  │ │ - Aggregated  │ │  - Round logs         │
│  - Spans/Events      │ │   metrics     │ │  - JSONL output      │
└─────────────────────┘ └──────────────┘ └──────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      查询和可视化层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Trace Viewer │  │ Metrics API  │ Log Analyzer │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 数据流

1. **Agent 执行**: BAAgent.invoke() 创建 root span
2. **追踪记录**: 每个关键操作创建对应的 child span
3. **事件记录**: 在 span 中记录事件（如 token 计数）
4. **指标收集**: MetricsCollector 自动收集性能指标
5. **持久化**: 执行结束时，保存到 TraceStore 和 MetricsStore
6. **查询分析**: 通过 API 或仪表板查询和分析

## 核心组件

### ExecutionTracer

**位置**: `backend/monitoring/execution_tracer.py`

执行追踪器负责记录 Agent 执行的完整路径。

**核心数据模型**:

```python
@dataclass
class Span:
    """执行跨度（类似 OpenTelemetry）"""
    trace_id: str          # 全局追踪 ID
    span_id: str           # 当前跨度 ID
    parent_span_id: Optional[str]  # 父跨度 ID
    name: str              # 操作名称
    start_time: float      # 开始时间戳
    end_time: Optional[float]
    duration_ms: Optional[float]
    status: str            # success, error
    span_type: str         # llm_call, tool_call, agent_invoke, etc.
    events: List[Event]    # 事件列表
    attributes: Dict[str, Any]  # token count, tool name, etc.
    children: List['Span'] # 子跨度列表
```

**Span 类型**:

| 类型 | 说明 | 使用场景 |
|------|------|----------|
| `agent_invoke` | Agent 调用 | 整个对话的根 span |
| `llm_call` | LLM API 调用 | 模型推理 |
| `tool_call` | 工具调用 | 函数/工具执行 |
| `memory_flush` | 内存刷新 | 上下文压缩 |
| `skill_activation` | Skill 激活 | Skill 动态调用 |

**使用示例**:

```python
from backend.monitoring import ExecutionTracer, SpanType, SpanStatus

# 创建追踪器
tracer = ExecutionTracer(conversation_id="conv_123", session_id="session_456")

# 创建根 span
root = tracer.create_root_span("agent_invoke", span_type=SpanType.AGENT_INVOKE)

# 创建子 span
llm_span = tracer.create_span("llm_call", SpanType.LLM_CALL, parent=root)
# ... 执行 LLM 调用 ...
tracer.end_span(llm_span, SpanStatus.SUCCESS)

# 结束根 span
tracer.end_span(root, SpanStatus.SUCCESS)

# 获取完整追踪
trace = tracer.get_trace()
```

### MetricsCollector

**位置**: `backend/monitoring/metrics_collector.py`

指标收集器负责聚合性能和成本指标。

**核心数据模型**:

```python
@dataclass
class AgentMetrics:
    """单次对话指标"""
    conversation_id: str
    session_id: str
    timestamp: float

    # Token 使用
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    tokens_by_model: Dict[str, Dict[str, int]]

    # 性能相关
    total_duration_ms: float
    llm_duration_ms: float
    tool_duration_ms: float
    other_duration_ms: float

    # 工具相关
    tool_calls_count: int
    tool_errors: int
    tool_calls_by_name: Dict[str, ToolCallStats]

    # 成本估算
    estimated_cost_usd: float
```

**模型定价配置**:

监控系统内置了主流模型的定价（USD/1M tokens）:

| 模型 | 输入 | 输出 |
|------|------|------|
| Claude Sonnet 4.5 | $3.00 | $15.00 |
| Claude Haiku 4.5 | $0.80 | $4.00 |
| GPT-4o | $5.00 | $15.00 |
| GPT-4o Mini | $0.15 | $0.60 |
| GLM-4 Plus | 按需配置 | 按需配置 |

**使用示例**:

```python
from backend.monitoring import MetricsCollector

# 创建收集器
collector = MetricsCollector(conversation_id="conv_123", session_id="session_456")

# 记录 LLM 调用
collector.record_llm_call(
    model="claude-sonnet-4-5-20250929",
    input_tokens=1000,
    output_tokens=500,
    duration_ms=2000
)

# 记录工具调用
collector.record_tool_call(
    tool_name="query_database",
    duration_ms=500,
    success=True
)

# 获取最终指标
metrics = collector.finalize()
print(f"总耗时: {metrics.total_duration_ms}ms")
print(f"预估成本: ${metrics.estimated_cost_usd:.4f}")
```

### TraceStore & MetricsStore

**位置**: `backend/monitoring/trace_store.py`

存储层提供持久化和查询功能。

**TraceStore 功能**:

- 保存追踪数据（JSON 格式）
- SQLite 索引（快速查询）
- TTL 管理（默认 7 天）
- 支持按 conversation_id、session_id、时间范围查询

**MetricsStore 功能**:

- 保存指标数据（JSONL 格式）
- 聚合统计
- 支持按时间范围聚合

**使用示例**:

```python
from backend.monitoring import get_trace_store, get_metrics_store

# 获取存储实例
trace_store = get_trace_store()
metrics_store = get_metrics_store()

# 保存追踪
trace_store.save_trace(trace, metrics)

# 查询追踪
trace = trace_store.load_trace(conversation_id="conv_123")

# 列出对话
conversations = trace_store.list_conversations(limit=100)

# 查询指标
metrics = metrics_store.get_metrics(conversation_id="conv_123")
```

## 指标说明

### 性能指标

| 指标 | 说明 | 单位 |
|------|------|------|
| `total_duration_ms` | 总执行时间 | ms |
| `llm_duration_ms` | LLM 调用耗时 | ms |
| `tool_duration_ms` | 工具调用耗时 | ms |
| `other_duration_ms` | 其他操作耗时 | ms |

### Token 指标

| 指标 | 说明 | 单位 |
|------|------|------|
| `total_input_tokens` | 输入 Token 总数 | tokens |
| `total_output_tokens` | 输出 Token 总数 | tokens |
| `total_tokens` | Token 总数 | tokens |
| `tokens_by_model` | 按模型分组的 Token 使用 | tokens |

### 工具指标

| 指标 | 说明 | 单位 |
|------|------|------|
| `tool_calls_count` | 工具调用总次数 | 次 |
| `tool_errors` | 工具调用错误数 | 次 |
| `tool_calls_by_name` | 按工具名称分组的统计 | - |

### 成本指标

| 指标 | 说明 | 单位 |
|------|------|------|
| `estimated_cost_usd` | 预估成本 | USD |

## API 端点

监控系统提供以下 REST API 端点：

### 对话列表

```
GET /api/v1/monitoring/conversations
```

**查询参数**:
- `session_id` (可选): 过滤会话 ID
- `limit` (可选): 最大返回数量（默认 100）

**响应**:
```json
[
  {
    "conversation_id": "conv_123",
    "session_id": "session_456",
    "start_time": 1675840000.0,
    "total_duration_ms": 10500,
    "trace_count": 1,
    "total_tokens": 1800,
    "tool_calls": 2
  }
]
```

### 获取追踪

```
GET /api/v1/monitoring/traces/{conversation_id}
```

**响应**: 完整的追踪 JSON，包含所有 span 和事件

### 可视化追踪

```
GET /api/v1/monitoring/traces/{conversation_id}/visualize?format=mermaid
```

**查询参数**:
- `format`: `mermaid` 或 `json`

**响应**:
```json
{
  "format": "mermaid",
  "conversation_id": "conv_123",
  "mermaid": "graph TD\n    A[agent_invoke] -->|2.0s| B[llm_call]\n    ..."
}
```

### 性能摘要

```
GET /api/v1/monitoring/performance/{conversation_id}
```

**响应**:
```json
{
  "conversation_id": "conv_123",
  "total_duration_ms": 10500,
  "llm_duration_ms": 2000,
  "tool_duration_ms": 500,
  "other_duration_ms": 8000,
  "llm_percentage": 19.0,
  "tool_percentage": 4.8,
  "other_percentage": 76.2,
  "total_tokens": 1800,
  "tool_calls_count": 2,
  "estimated_cost_usd": 0.0036
}
```

### 获取指标

```
GET /api/v1/monitoring/metrics
```

**查询参数**:
- `conversation_id` (可选): 对话 ID
- `session_id` (可选): 会话 ID
- `start_time` (可选): 开始时间戳
- `end_time` (可选): 结束时间戳

### 获取所有 Span

```
GET /api/v1/monitoring/spans/{conversation_id}
```

**响应**: 扁平化的 span 列表，包含层级信息

## 监控仪表板

### 访问地址

```
http://localhost:8000/monitoring
```

### 功能概述

监控仪表板提供三列布局：

**左侧 - 对话列表**:
- 显示所有有追踪数据的对话
- 支持按时间范围、状态筛选
- 支持搜索对话 ID
- 显示摘要信息（耗时、Token、工具调用）

**中间 - 追踪详情**:
- Mermaid 流程图可视化
- Span 详情表格
- 支持 JSON/Mermaid 导出

**右侧 - 指标仪表板**:
- 总耗时、Token 总数、预估成本
- Token 分布图
- 耗时分布图
- 工具调用统计

### 使用技巧

1. **快速定位问题**: 点击状态为 "error" 的对话
2. **性能分析**: 查看耗时分布，识别瓶颈
3. **成本控制**: 监控 Token 使用和预估成本
4. **导出分析**: 导出追踪数据进行深入分析

## 配置选项

### 环境变量

```bash
# 监控开关（默认启用）
BA_MONITORING_ENABLED=true

# 追踪数据 TTL（天）
BA_TRACE_TTL_DAYS=7

# 指标数据 TTL（天）
BA_METRICS_TTL_DAYS=30

# 存储目录
BA_MONITORING_STORAGE_DIR=/var/lib/ba-agent/monitoring
```

### Agent 配置

在 `config/settings.yaml` 中配置监控相关设置：

```yaml
monitoring:
  enabled: true
  trace_ttl_days: 7
  metrics_ttl_days: 30
  auto_cleanup: true
```

## 开发指南

### 添加自定义 Span

```python
# 在 BAAgent 中添加自定义追踪点
def invoke(self, message: str, ...):
    # 创建 root span
    tracer = self._get_tracer(conversation_id, session_id)
    root = tracer.create_root_span("custom_operation")

    try:
        # ... 执行操作 ...

        # 添加事件
        tracer.add_event("custom_event", {"key": "value"})

        # 结束 span
        tracer.end_span(root, SpanStatus.SUCCESS)
    except Exception as e:
        tracer.end_span(root, SpanStatus.ERROR)
        raise
```

### 添加自定义指标

```python
# 记录自定义指标
collector = self._get_metrics_collector(conversation_id, session_id)
collector.metadata["custom_metric"] = 123
```

### 扩展模型定价

编辑 `backend/monitoring/metrics_collector.py`:

```python
MODEL_PRICING = {
    # ... 现有配置 ...
    "your-model": {
        "input": 1.0,   # $1 per 1M input tokens
        "output": 2.0   # $2 per 1M output tokens
    }
}
```

## 故障排查

### 监控数据未保存

**症状**: 执行完成后无法找到追踪数据

**排查**:
1. 检查 `BA_MONITORING_ENABLED=true`
2. 检查存储目录权限
3. 查看日志中的错误信息

### 性能影响过大

**症状**: 启用监控后响应时间明显增加

**排查**:
1. 检查 SQLite 索引是否正常
2. 考虑增加 TTL 减少数据量
3. 监控 `other_duration_ms` 是否异常

### 仪表板无法加载

**症状**: 访问 `/monitoring` 页面空白

**排查**:
1. 检查 JWT 令牌是否有效
2. 打开浏览器控制台查看错误
3. 检查 API 端点是否正常响应

## 测试

监控系统包含完整的单元测试：

```bash
# 运行所有监控测试
pytest tests/monitoring/ -v

# 运行特定测试
pytest tests/monitoring/test_execution_tracer.py -v
pytest tests/monitoring/test_metrics_collector.py -v
pytest tests/monitoring/test_monitoring_api.py -v
```

## 相关文档

- [API 文档](api.md) - REST API 端点详情
- [开发指南](development.md) - 开发环境设置
- [项目架构](architecture.md) - 整体架构设计
