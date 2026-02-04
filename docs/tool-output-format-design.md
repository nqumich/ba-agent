# BA-Agent 统一工具输出格式设计

> 基于对 Anthropic、Claude Code、Manus 等优秀 Agent 产品的研究
> 2025-02-05

## 设计目标

### 1. 模型间上下文传递 (Model Context Passing)
- 结构化的 Observation/Results 供下一轮使用
- Token 高效的压缩格式
- 规划提示 (Context Hints)

### 2. 工程系统流转 (Engineering System Flow)
- 遥测数据 (Token 使用、延迟、错误)
- 状态管理 (进度、检查点)
- 调试/日志信息
- KV-Cache 优化提示

### 3. ReAct 兼容性
- 标准化的 Observation 格式
- Thought → Action → Observation 循环支持
- LangGraph 状态集成

## 核心数据模型

```python
# 统一工具输出格式
class ToolOutput(BaseModel):
    """所有工具返回的统一格式"""

    # ========== 模型上下文部分 (传递给下一轮) ==========
    result: Optional[Any] = None           # 主要结果数据
    summary: str = ""                      # 人类可读的摘要（供模型直接使用）
    observation: str = ""                  # ReAct Observation 格式

    # ========== Token 效率控制 ==========
    response_format: ResponseFormat = ResponseFormat.CONCISE
    compressed: bool = False               # 是否使用压缩格式

    # ========== 工程遥测部分 (工程系统使用，不传给模型) ==========
    telemetry: ToolTelemetry = Field(default_factory=ToolTelemetry)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # ========== 状态管理 ==========
    state_update: Optional[Dict[str, Any]] = None  # 状态更新
    checkpoint: Optional[str] = None               # 检查点标识

    class Config:
        # 遥测数据不序列化给模型
        exclude = {"telemetry", "metadata"}
```

## 响应格式枚举

```python
class ResponseFormat(str, Enum):
    """响应格式控制"""

    # Concise: 仅关键信息（默认）
    # - 最少 Token 使用
    # - 仅包含直接影响后续决策的信息
    CONCISE = "concise"

    # STANDARD: 标准格式
    # - 平衡信息量和 Token 使用
    # - 包含常用字段和上下文
    STANDARD = "standard"

    # DETAILED: 详细格式
    # - 完整信息（调试用）
    # - 包含所有可用字段、元数据
    DETAILED = "detailed"

    # RAW: 原始格式
    # - 不经过处理的原始数据
    RAW = "raw"
```

## 遥测数据模型

```python
class ToolTelemetry(BaseModel):
    """工具遥测数据（工程系统使用）"""

    # 执行信息
    tool_name: str = ""
    tool_version: str = "1.0.0"
    execution_id: str = ""               # UUID
    timestamp: str = ""                  # ISO 8601

    # 性能指标
    latency_ms: float = 0.0              # 执行延迟
    duration_ms: float = 0.0             # 总耗时

    # Token 统计
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # 缓存状态
    cache_hit: bool = False              # 是否命中缓存
    cache_key: Optional[str] = None

    # 错误追踪
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0

    # 资源使用
    memory_mb: float = 0.0
    cpu_percent: float = 0.0

    # 自定义指标
    metrics: Dict[str, float] = Field(default_factory=dict)
```

## ReAct Observation 格式

```python
def format_observation(output: ToolOutput) -> str:
    """格式化为 ReAct Observation"""

    if output.response_format == ResponseFormat.CONCISE:
        # 简洁格式：仅关键信息
        return f"Observation: {output.summary}"

    elif output.response_format == ResponseFormat.STANDARD:
        # 标准格式：包含结构化信息
        return f"""Observation: {output.summary}

Result Type: {type(output.result).__name__}
Status: {'Success' if output.telemetry.success else 'Failed'}
"""

    elif output.response_format == ResponseFormat.DETAILED:
        # 详细格式：完整调试信息
        return f"""Observation: {output.summary}

Tool: {output.telemetry.tool_name}
Execution ID: {output.telemetry.execution_id}
Latency: {output.telemetry.latency_ms:.2f}ms
Tokens: {output.telemetry.output_tokens}

Result: {json.dumps(output.result, ensure_ascii=False, indent=2)}

Metadata: {output.metadata}
"""
```

## Token 优化策略

### 1. 压缩格式 (TOON-like)

```python
# 紧凑的键值对格式 (TOON - Token Optimized Object Notation)
COMPACT_FORMAT = """
res:{base64(result)}|sum:{summary}|tok:{tokens}|err:{error_code}
"""
```

### 2. 安全 YAML

```python
# 可读但紧凑的配置格式
SAFE_YAML_FORMAT = """
result:
  data: {result}
  summary: {summary}
  tokens: {token_count}
"""
```

### 3. XML (LLM 友好)

```python
# LLM 训练数据中常见格式
XML_FORMAT = """
<tool_result name="{tool_name}">
  <summary>{summary}</summary>
  <data>{result}</data>
  <metadata tokens="{tokens}" latency="{latency_ms}"/>
</tool_result>
"""
```

## 工具包装器

```python
class UnifiedToolWrapper:
    """统一工具包装器"""

    @staticmethod
    def wrap_tool(
        tool_func: Callable,
        tool_name: str,
        response_format: ResponseFormat = ResponseFormat.CONCISE
    ) -> Callable:
        """包装工具函数以返回统一格式"""

        def wrapped(*args, **kwargs) -> str:
            telemetry = ToolTelemetry(
                tool_name=tool_name,
                execution_id=str(uuid.uuid4()),
                timestamp=datetime.now().isoformat()
            )

            start_time = time.time()

            try:
                # 执行原始工具
                raw_result = tool_func(*args, **kwargs)

                # 更新遥测
                telemetry.duration_ms = (time.time() - start_time) * 1000
                telemetry.success = True

                # 根据格式化选项处理结果
                if response_format == ResponseFormat.CONCISE:
                    summary = _extract_summary(raw_result)
                    result = None  # Concise 模式不返回详细数据
                else:
                    summary = _extract_summary(raw_result)
                    result = raw_result

                # 构建统一输出
                output = ToolOutput(
                    result=result,
                    summary=summary,
                    observation=format_observation(summary, telemetry),
                    response_format=response_format,
                    telemetry=telemetry
                )

                return output.model_dump_json(exclude={"telemetry"})

            except Exception as e:
                telemetry.duration_ms = (time.time() - start_time) * 1000
                telemetry.success = False
                telemetry.error_code = type(e).__name__
                telemetry.error_message = str(e)

                output = ToolOutput(
                    summary=f"Error: {str(e)}",
                    observation=f"Observation: Error - {str(e)}",
                    telemetry=telemetry
                )

                return output.model_dump_json(exclude={"telemetry"})

        return wrapped
```

## 集成示例

```python
# 现有工具集成
@UnifiedToolWrapper.wrap_tool(
    tool_name="file_reader",
    response_format=ResponseFormat.STANDARD
)
def file_reader_impl(path: str, **kwargs) -> dict:
    """文件读取实现"""
    # ... 原有逻辑
    pass

# 返回格式：
# {
#   "summary": "读取了 data/sales.csv，共 1000 行，5 列",
#   "result": {"rows": 1000, "columns": 5, ...},
#   "observation": "Observation: 读取了 data/sales.csv，共 1000 行，5 列\n...",
#   "response_format": "standard",
#   "state_update": null,
#   "checkpoint": null
# }

# 遥测数据自动收集，不返回给模型：
# - execution_id: "123e4567-e89b-12d3-a456-426614174000"
# - latency_ms: 45.2
# - output_tokens: 127
# - success: true
```

## LangGraph 状态集成

```python
from langgraph.graph import StateGraph
from typing import TypedDict

class AgentState(TypedDict):
    messages: List[BaseMessage]
    tool_outputs: List[ToolOutput]
    telemetry_summary: Dict[str, Any]

def tool_node(state: AgentState):
    """处理工具调用的节点"""
    outputs = []
    telemetry_summary = {
        "total_tokens": 0,
        "total_latency_ms": 0,
        "tool_calls": []
    }

    for message in state["messages"]:
        if hasattr(message, "tool_calls"):
            for tool_call in message.tool_calls:
                # 执行工具
                output_json = execute_tool(tool_call)
                output = ToolOutput.model_validate_json(output_json)

                # 收集遥测
                outputs.append(output)
                telemetry_summary["total_tokens"] += output.telemetry.output_tokens
                telemetry_summary["total_latency_ms"] += output.telemetry.latency_ms
                telemetry_summary["tool_calls"].append({
                    "tool": output.telemetry.tool_name,
                    "success": output.telemetry.success,
                    "latency_ms": output.telemetry.latency_ms
                })

    return {
        "tool_outputs": outputs,
        "telemetry_summary": telemetry_summary
    }
```

## 埋点和监控

```python
class TelemetryCollector:
    """遥测数据收集器"""

    def __init__(self):
        self.metrics: List[ToolTelemetry] = []
        self.aggregated: Dict[str, Any] = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_latency_ms": 0,
            "error_rate": 0.0,
            "cache_hit_rate": 0.0
        }

    def record(self, telemetry: ToolTelemetry):
        """记录遥测数据"""
        self.metrics.append(telemetry)
        self._update_aggregated()

    def _update_aggregated(self):
        """更新聚合统计"""
        self.aggregated["total_calls"] = len(self.metrics)
        self.aggregated["total_tokens"] = sum(m.output_tokens for m in self.metrics)
        self.aggregated["total_latency_ms"] = sum(m.latency_ms for m in self.metrics)
        self.aggregated["error_rate"] = sum(1 for m in self.metrics if not m.success) / len(self.metrics)
        self.aggregated["cache_hit_rate"] = sum(1 for m in self.metrics if m.cache_hit) / len(self.metrics)

    def get_report(self) -> str:
        """生成遥测报告"""
        return f"""
工具执行统计:
- 总调用次数: {self.aggregated['total_calls']}
- 总 Token 使用: {self.aggregated['total_tokens']}
- 平均延迟: {self.aggregated['total_latency_ms'] / self.aggregated['total_calls']:.2f}ms
- 错误率: {self.aggregated['error_rate']:.2%}
- 缓存命中率: {self.aggregated['cache_hit_rate']:.2%}
"""
```

## KV-Cache 优化

```python
class CacheOptimizedOutput:
    """KV-Cache 优化的输出格式"""

    @staticmethod
    def stable_prefix(tool_name: str) -> str:
        """稳定的输出前缀（保持一致性以利用 KV-Cache）"""
        return f"<tool_result name=\"{tool_name}\">"

    @staticmethod
    def format_with_stable_prefix(output: ToolOutput) -> str:
        """使用稳定前缀格式化输出"""
        prefix = CacheOptimizedOutput.stable_prefix(output.telemetry.tool_name)
        body = output.summary  # 仅摘要，Token 高效
        return f"{prefix}\n  <summary>{body}</summary>\n</tool_result>"
```

## 下一步实现

1. **创建核心模型** (`models/tool_output.py`)
   - `ToolOutput`, `ToolTelemetry`, `ResponseFormat`

2. **创建工具包装器** (`tools/base.py`)
   - `UnifiedToolWrapper`
   - `format_observation()`

3. **更新现有工具**
   - 集成 `UnifiedToolWrapper`
   - 返回统一格式

4. **LangGraph 集成**
   - 更新 Agent 状态定义
   - 集成遥测收集

5. **监控和调试**
   - 实现 `TelemetryCollector`
   - 添加日志输出
