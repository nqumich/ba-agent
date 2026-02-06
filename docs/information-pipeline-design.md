# BA-Agent Information Pipeline Design

> **Version**: v1.9
> **Status**: Production-Grade
> **Last Updated**: 2026-02-06

---

## 核心设计原则

| 原则 | 说明 |
|------|------|
| 简单消息格式 | 遵循 Claude Code 的 straightforward 方式 |
| ReAct 执行循环 | Agent 使用 Thought→Action→Observation 推理模式 |
| 简单工具输出 | 工具返回纯 observation 字符串 |
| 渐进式披露 | Skills 系统的信息加载策略 (metadata → full → resources) |
| Context Modifiers | Skills 可修改 Agent 执行上下文 |
| 高效内存管理 | 文件存储 + LRU 缓存 + 准确 Token 计数 |

---

## 核心概念（四独立概念）

| 概念 | 类型 | 目的 |
|------|------|------|
| **ReAct** | 控制流程 | Agent 推理模式 (Thought → Action → Observation) |
| **Observation** | 语义 | 工具返回内容 (LLM 输入) |
| **Output Level** | 工程优化 | 格式化详细程度 (BRIEF/STANDARD/FULL) |
| **Progressive Disclosure** | 信息加载 | Skills 如何加载 (Level 1→2→3) |

**关键理解**:
- `Observation` ≠ `Output Level` - 它们正交
- Observation 是 **WHAT**（语义内容）
- Output Level 是 **HOW**（格式化详细程度）

---

## 消息格式定义

### 1. 标准消息 (Claude Code 兼容)

```python
class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ContentBlockType(str, Enum):
    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"

class ContentBlock(BaseModel):
    type: ContentBlockType
    text: Optional[str] = None
    thinking: Optional[str] = None
    id: Optional[str] = None        # tool_use
    name: Optional[str] = None      # tool_use
    input: Optional[Dict] = None    # tool_use
    tool_use_id: Optional[str] = None  # tool_result
    is_error: bool = False
```

### 2. 工具调用

```python
class ToolCallMessage(BaseModel):
    tool_call_id: str
    tool_name: str
    parameters: Dict[str, Any]
    # 可选：指定 output_level
    output_level: Optional[OutputLevel] = None
```

### 3. 工具结果（核心）

```python
class OutputLevel(str, Enum):
    BRIEF = "brief"       # 关键事实
    STANDARD = "standard" # 可操作信息
    FULL = "full"         # 完整数据

class ToolResultMessage(BaseModel):
    tool_call_id: str

    # ReAct Observation: LLM 看到的内容
    observation: str

    # 格式化级别
    output_level: OutputLevel = OutputLevel.STANDARD

    # 文件存储（大数据）
    data_file: Optional[str] = None  # >1MB 或 FULL 级别
    data_size_bytes: int = 0
    data_summary: Optional[str] = None

    # 状态
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_raw_data(
        cls, tool_call_id: str, raw_data: Any,
        output_level: OutputLevel,
        storage_dir: Path
    ) -> "ToolResultMessage":
        """从原始数据创建结果，自动选择存储策略"""

    def format_error_observation(self) -> str:
        """统一的错误格式"""
        return f"""Operation failed.
Error Type: {self.error_type}
Error Code: {self.error_code}
Error Message: {self.error_message}
Tool Call ID: {self.tool_call_id}"""
```

**设计决策**:
- 单一 `observation` 字段（LLM 的 ReAct Observation）
- `output_level` 控制格式化（工程优化）
- 大数据存储到文件（防止内存问题）
- 统一错误格式

---

## 工具 ↔ Agent 通信协议

### Output Level 决策机制

```python
def get_effective_output_level(
    self,
    tool_config_default: Optional[OutputLevel],
    global_default: OutputLevel,
    context_window_usage: float
) -> OutputLevel:
    """
    优先级：
    1. Agent 显式指定
    2. 工具配置默认值
    3. 全局默认值 (STANDARD)
    4. 动态调整（上下文 >80% → BRIEF）
    """
```

### 重试策略

```python
class ToolRetryPolicy(BaseModel):
    max_retries: int = 3
    retry_on: List[ToolErrorType] = [TIMEOUT, RESOURCE_ERROR]
    backoff_multiplier: float = 1.5
    initial_delay_ms: int = 1000
    max_delay_ms: int = 10000

    def should_retry(self, error_type: ToolErrorType, attempt: int) -> bool
    def get_delay(self, attempt: int) -> int
    def get_retry_timeout(self, original_timeout: int, attempt: int) -> int
```

### 超时处理

```python
class ToolTimeoutHandler:
    @staticmethod
    def validate_input_size(parameters: Dict, max_size_mb: int = 10) -> bool

    @staticmethod
    async def execute_with_timeout(
        func: Callable,
        timeout_ms: int,
        on_timeout: Optional[Callable] = None
    ) -> Any

    @staticmethod
    def create_timeout_fallback(request_id: str) -> ToolExecutionResult
```

---

## Skills ↔ Agent 通信协议

### 渐进式披露（Progressive Disclosure）

```python
class SkillActivationRequest(BaseModel):
    skill_name: str
    activation_id: str

    # 渐进式披露控制
    load_level: Literal[1, 2, 3] = 2
    # Level 1: Frontmatter (~100 tokens)
    # Level 2: Full SKILL.md (~5000 tokens)
    # Level 3: 资源文件 (按需)

    # 循环依赖检测
    activation_depth: int = 0
    max_depth: int = 3
    activation_chain: List[str] = []  # 累积完整路径

    def can_activate_nested(self, skill_name: str) -> bool:
        """检测直接和间接循环 (A→B→C→A)"""
        if skill_name in self.activation_chain:
            return False  # 直接循环
        if self.activation_depth >= self.max_depth:
            return False  # 深度限制
        return True
```

### 消息注入协议（线程安全）

```python
class MessageInjectionProtocol:
    """使用 LRU 缓存防止内存泄漏"""

    @classmethod
    @lru_cache(maxsize=1000)
    def _get_lock(cls, conversation_id: str) -> threading.Lock:
        return threading.Lock()

    @staticmethod
    def inject_into_state(
        messages: List[Dict],
        conversation_id: str,
        agent_state: Any
    ) -> bool
```

---

## Token 计数与监控

### 准确 Token 计数（使用 tiktoken）

```python
class TokenCounter:
    @classmethod
    def count_tokens(cls, text: str, model: str = "claude-3") -> int:
        encoder = tiktoken.get_encoding("cl100k_base")
        return len(encoder.encode(text))

    @classmethod
    def count_message_tokens(cls, message: Dict, model: str) -> int

    @classmethod
    def count_conversation_tokens(cls, messages: List[Dict], model: str) -> int
```

### 监控指标

```python
@dataclass
class ToolMetrics:
    tool_name: str
    duration_ms: float
    input_tokens: int
    output_tokens: int
    success: bool
    retry_count: int
    output_level: str

@dataclass
class ConversationMetrics:
    conversation_id: str
    total_input_tokens: int
    total_output_tokens: int
    tool_calls: List[ToolMetrics]

    def get_tool_stats(self) -> Dict[str, Dict]:  # 每工具统计
    def to_report(self) -> str  # 人类可读报告

class MetricsCollector:
    """全局指标收集器"""
    def record_tool_call(self, metrics: ToolMetrics, conversation_id: str)
    def get_global_stats(self) -> Dict
```

---

## 多轮对话流程

### 对话轮次

```python
class ConversationRound(BaseModel):
    round_id: str
    user_message: str
    thoughts: List[str]  # Agent 推理
    tool_calls: List[ToolCallMessage]
    tool_observations: List[str]  # 简单字符串
    final_answer: Optional[str]
    tokens_used: int
```

### 上下文管理

```python
class ContextManager:
    def __init__(self, max_tokens: int = 200000):
        self.max_tokens = max_tokens
        self.compression_threshold = 0.8

    def should_compress_context(self) -> bool:
        """使用准确 Token 计数判断"""

    def get_compressed_history(self) -> List[Dict]:
        """策略：
        - 保留最近 5 轮完整
        - 旧轮次压缩为摘要
        - 保留 tool observations
        """
```

---

## 文件存储策略

```python
class DataStorage:
    """工具数据的文件存储管理"""

    STORAGE_DIR = Path("tool_data")

    @classmethod
    def store_large_data(
        cls,
        tool_call_id: str,
        data: Any,
        data_hash: str
    ) -> str:
        """存储大数据到文件，返回文件路径"""

    @classmethod
    def retrieve_data(cls, file_path: str) -> Any:
        """从文件读取数据"""

    @classmethod
    def cleanup_old_files(cls, max_age_hours: int = 24):
        """清理过期文件"""
```

---

## 实施路线图

### Phase 1: 核心消息格式（Week 1）
- [x] OutputLevel 枚举定义
- [x] ToolResultMessage 接口（observation + output_level + data_file）
- [ ] StandardMessage 实现
- [ ] 格式化辅助函数
- [ ] 20 单元测试

### Phase 2: 工具通信协议（Week 2）
- [ ] ToolInvocationRequest + Output Level 决策
- [ ] ToolExecutionResult + 重试支持
- [ ] ToolTimeoutHandler
- [ ] 统一错误格式
- [ ] 15 集成测试

### Phase 3: Skills 通信协议（Week 2）
- [ ] SkillActivationRequest + 间接循环检测
- [ ] SkillLoader 3-level 加载
- [ ] MessageInjectionProtocol + LRU 缓存
- [ ] 10 集成测试

### Phase 4: 多轮对话（Week 3）
- [ ] ConversationRound + ReAct 追踪
- [ ] ContextManager + 压缩
- [ ] 5 E2E 测试

### Phase 5: 监控与迁移（Week 4）
- [ ] TokenCounter (tiktoken)
- [ ] MetricsCollector
- [ ] 迁移现有工具
- [ ] 性能基准测试

---

## 版本历史

### v1.9 (2026-02-06) - LLM 增强上下文管理
**3 项新增**:
1. LLM 摘要压缩 - 三种策略（TRUNCATE/EXTRACT/SUMMARIZE）
2. LLMCompressor - 使用 Claude 3 Haiku 生成摘要
3. SummaryCache - 避免重复摘要，TTL 清理

**新增评分**:
| 方面 | v1.7 | v1.9 |
|------|------|------|
| 上下文压缩 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 成本优化 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 智能化 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### v1.8 (2026-02-05) - 修复评审问题
**高优先级修复**:
1. Token Counter - Claude tokenizer 修正（15% safety margin）
2. DataFileManager - threading 替代 asyncio
3. LockManager - 引用计数锁管理

**中优先级新增**:
4. ToolErrorType - is_retryable 属性
5. IdempotencyCache - 幂等性支持

### v1.7 (2026-02-05) - 生产级完整性
**6 项新增**:
1. 文件清理策略（时间 + 大小 + LRU）
2. Activation Chain 完整管理（push/pop）
3. 增强的上下文压缩（重要性评分）
4. 完整线程安全（ThreadSafeContainer）
5. Schema 版本控制（迁移支持）
6. 可观测性配置（OpenTelemetry）

### v1.6 (2026-02-05) - 生产环境增强

**9 项关键改进**:

1. Output Level 决策机制（四级回退）
2. 文件数据存储（>1MB 自动存储）
3. LRU 缓存锁管理（防止内存泄漏）
4. 统一错误格式
5. 间接循环检测
6. 准确 Token 计数（tiktoken）
7. 重试策略（指数退避）
8. 超时处理（异步控制）
9. 监控指标（MetricsCollector）

### v1.5 (2026-02-05) - Output Level 澄清
- Observation（语义）vs Output Level（工程）正交关系

### v1.4 (2026-02-05) - 概念修正
- ReAct 执行循环 ≠ 工具输出格式
- 移除错误的 summary/observation/result 三层结构

### 早期版本
- v1.3: 工程生产就绪
- v1.2: 生产环境增强
- v1.1: 评审响应

---

## 附录：快速参考

### ReAct 执行循环

```
Thought: 我需要搜索文件
Action: call file_search("**/*.py")
Observation: file1.py, file2.py, file3.py
Thought: 我需要读取 file1.py
Action: call file_reader("file1.py")
Observation: [文件内容]
Final Answer: 分析结果...
```

### Output Level 示例

```python
# 同一数据，不同级别
data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, ...]

BRIEF:    "Found 10 items"
STANDARD: "Found 10 items:\n  - {id: 1, name: Alice}\n  - {id: 2, name: Bob}..."
FULL:     "[{\"id\": 1, \"name\": \"Alice\"}, ...]"  # 完整 JSON
         # 或: "Data stored in file: tool_data/call_123_xyz.json"
```

### 文件存储规则

| 条件 | 存储策略 |
|------|----------|
| data_size < 1MB & level != FULL | 内存（observation 直接包含） |
| data_size >= 1MB 或 level == FULL | 文件（observation 包含引用） |

### Token 计数精度

| 方法 | 精度 | 用途 |
|------|------|------|
| 字符估算 (chars/3) | ±30% | 粗略判断 |
| tiktoken | ±1% | 生产环境 |
| API 返回 | 精确 | 最终验证 |

---

**文档版本**: v1.8 (Simplified)
**详细版**: 3159 行 | **简化版**: ~465 行
**双文档结构**: 快速参考 + 完整实现
