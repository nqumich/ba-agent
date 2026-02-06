# BA-Agent Information Pipeline Design

> **Version**: v2.1.0
> **Status**: Production-Ready (Full Implementation Complete)
> **Last Updated**: 2026-02-06

## v2.1.0 更新摘要

**新增组件**:
- `DynamicTokenCounter`: 多模型 Token 计数（OpenAI tiktoken + Anthropic + fallback）
- `AdvancedContextManager`: 智能上下文压缩（优先级过滤 + LLM 摘要）
- `IdempotencyCache`: 跨轮次缓存（基于语义键，非 tool_call_id）

**BAAgent 集成**:
- `_get_total_tokens()`: 使用 DynamicTokenCounter 精确计数
- `_compact_conversation()`: 使用 AdvancedContextManager 智能压缩
- `_check_and_flush()`: 双组件协同工作

**提交记录**:
- `e4ebcb6`: Phase 5 实现（IdempotencyCache, DynamicTokenCounter, AdvancedContextManager）
- `45dc323`: BAAgent 集成
- `d4d8c35`: Phase 4 工具迁移
- `358f201`: Phase 1-3 核心模型

---

## 核心设计原则

| 原则 | 说明 |
|------|------|
| **LangChain 为主** | 使用 LangChain BaseMessage (HumanMessage/AIMessage/ToolMessage) |
| **Claude Code 参考** | 研究格式仅用于调试，非生产实现 |
| **同步工具** | 工具执行为同步 `def`（非 `async def`） |
| **ReAct 执行循环** | Agent 使用 Thought→Action→Observation 推理模式 |
| **简单工具输出** | 工具返回纯 observation 字符串 |
| **渐进式披露** | Skills 系统的信息加载策略 (metadata → full → resources) |
| **安全存储** | artifact_id 替代真实路径（防路径穿越） |

---

## 核心概念（五独立概念）

| 概念 | 类型 | 目的 |
|------|------|------|
| **ReAct** | 控制流程 | Agent 推理模式 (Thought → Action → Observation) |
| **Observation** | 语义 | 工具返回内容 (LLM 输入) |
| **Output Level** | 工程优化 | 格式化详细程度 (BRIEF/STANDARD/FULL) |
| **Carrier** | 传输 | Observation 如何传递给 LLM |
| **Progressive Disclosure** | 信息加载 | Skills 如何加载 (Level 1→2→3) |

**关键理解**:
- Observation 是 **WHAT**（语义内容）
- Output Level 是 **HOW**（格式化详细程度）
- Carrier 是 **TRANSPORT**（LangChain ToolMessage vs Claude Code block）
- 它们**相互正交**，各司其职

---

## 消息格式定义

### 1. 内部消息格式（LangChain - 生产实现）

```python
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# 工具调用循环
ai_message = AIMessage(
    content="",
    tool_calls=[{
        "id": "call_abc123",    # LLM 生成
        "name": "web_search",
        "args": {"query": "..."}
    }]
)

# 工具执行后
tool_message = ToolMessage(
    content="[observation string]",  # ReAct Observation
    tool_call_id="call_abc123"       # 必须匹配 AIMessage.tool_calls[i]["id"]
)

# 下轮对话
messages.extend([ai_message, tool_message])
next_response = llm.invoke(messages)
```

**CRITICAL**: `tool_call_id` 必须来自 LLM，**不能自己生成**！

### 2. 外部/研究格式（Claude Code - 调试用）

```python
class ContentBlock(BaseModel):
    """仅用于研究/调试"""
    type: ContentBlockType
    content: Optional[str] = None      # 通用内容
    text: Optional[str] = None
    thinking: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Dict] = None
    tool_use_id: Optional[str] = None
    is_error: bool = False

class StandardMessage(BaseModel):
    """Claude Code 兼容格式（仅研究/调试）"""
    role: MessageType
    content: List[ContentBlock]

    def to_debug_dict(self) -> Dict[str, Any]:
        """转换为调试字典（不是 LangChain 格式！）"""
        ...
```

---

## 工具 ↔ Agent 通信协议

### ToolInvocationRequest（请求）

```python
class ToolInvocationRequest(BaseModel):
    # CRITICAL: tool_call_id 来自 LLM，不能生成
    tool_call_id: str  # 来自 AIMessage.tool_calls[i]["id"]
    tool_name: str
    tool_version: str = "1.0.0"
    parameters: Dict[str, Any]

    # Output level
    output_level: Optional[OutputLevel] = None

    # 执行上下文
    timeout_ms: int = 120000
    retry_on_timeout: bool = True
    storage_dir: Optional[str] = None

    # 安全
    caller_id: str
    permission_level: str = "default"

    # 幂等性
    idempotency_key: Optional[str] = None

    # 缓存策略（默认：不缓存）
    cache_policy: ToolCachePolicy = ToolCachePolicy.NO_CACHE

    def get_or_generate_idempotency_key(self) -> str:
        """
        生成幂等键（不包含 tool_call_id，支持跨轮次缓存）

        组件：tool_name + tool_version + parameters + caller_id + permission_level
        """
```

### ToolCachePolicy（缓存策略）

```python
class ToolCachePolicy(str, Enum):
    NO_CACHE = "no_cache"         # 默认（安全）
    CACHEABLE = "cacheable"       # 可缓存
    TTL_SHORT = "ttl_short"       # 5 分钟
    TTL_MEDIUM = "ttl_medium"     # 1 小时
    TTL_LONG = "ttl_long"         # 24 小时
```

**可缓存工具**：web_search, query_database, file_reader, vector_search
**不可缓存工具**：file_write, execute_command, database_write

### ToolExecutionResult（响应）

```python
class ToolExecutionResult(BaseModel):
    """工具执行的单一结果模型（v2.0.1: 已删除 ToolResultMessage）"""

    tool_call_id: str
    observation: str               # ReAct Observation
    output_level: OutputLevel = OutputLevel.STANDARD

    # 安全存储（artifact_id 非真实路径）
    _data_file: Optional[str] = None      # 私有：真实路径
    artifact_id: Optional[str] = None      # 公开：安全标识符
    data_size_bytes: int = 0
    data_hash: Optional[str] = None
    data_summary: Optional[str] = None

    # 重试跟踪
    retry_count: int = 0
    last_error: Optional[str] = None

    # 状态
    success: bool
    error_code: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # 计时
    duration_ms: float = 0.0

    # 工厂方法
    @classmethod
    def from_raw_data(
        cls, tool_call_id: str, raw_data: Any,
        output_level: OutputLevel, storage_dir: str
    ) -> "ToolExecutionResult": ...

    # 转换方法
    def to_tool_message(self) -> ToolMessage: ...    # 主要方法
    def to_llm_message(self) -> Dict[str, Any]: ...    # 调试用（已弃用）
```

**Observation 格式示例**：

```python
# FULL 级别，使用 artifact_id（安全）
observation = """Data stored as artifact: artifact_abc123

Large dataset available for subsequent tool access.

To access this data, reference the artifact_id in your next tool call.
The system will securely retrieve the data for you.

Data summary: List with 1000 items. First item keys: ['id', 'name']"""
```

### 安全：文件存储规则

| 方面 | 规则 |
|------|------|
| 存储位置 | 沙箱目录：`/var/lib/ba-agent/artifacts/` |
| 路径暴露 | 禁止在 observation/日志中暴露真实路径 |
| 标识符格式 | `artifact_{hash}`（无路径分隔符） |
| 访问验证 | file_reader 必须验证 artifact_id 并限制在沙箱内 |
| 清理策略 | TTL 24 小时，会话结束清理 |

---

## 超时与重试

### ToolTimeoutHandler（同步版本）

```python
class ToolTimeoutHandler:
    """同步超时处理器（适合同步工具）"""

    @staticmethod
    def execute_with_timeout(
        func: Callable,
        tool_call_id: str,
        timeout_ms: int = 30000
    ) -> Any:
        """
        同步执行，超时抛出 TimeoutException
        使用 threading.Timer（非 asyncio）
        """

    @staticmethod
    def create_timeout_result(tool_call_id: str, timeout_ms: int) -> ToolExecutionResult:
        """返回错误结果（而非抛出异常）"""
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            observation=f"Tool execution timed out after {timeout_ms}ms",
            success=False,
            error_type="timeout",
            ...
        )
```

**使用示例**：
```python
try:
    result = ToolTimeoutHandler.execute_with_timeout(
        func=lambda: actual_tool(params),
        tool_call_id=request.tool_call_id,
        timeout_ms=request.timeout_ms
    )
    return ToolExecutionResult(tool_call_id=..., observation=str(result), success=True)
except TimeoutException:
    return ToolTimeoutHandler.create_timeout_result(...)
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

### 动态 Token 计数器

**支持多模型的动态 Token 计数系统。**

```python
class DynamicTokenCounter:
    """
    动态 Token 计数器 - 支持多模型和插件式编码器注册

    特性：
    - 自动识别模型系列（Claude, GPT, Gemini, GLM 等）
    - 配置文件支持（config/token_encoders.yaml）
    - 精确计数 + 安全余量
    """

    def count_tokens(self, text: str, model: str = "claude-3-sonnet") -> int:
        """计算文本的 Token 数量（自动选择编码器）"""
        config = self._registry.get_encoder_config(model)
        encoder = self._registry.get_encoder(model)
        estimated = len(encoder.encode(text))
        return int(estimated * config.safety_margin)

    def count_message_tokens(self, message: Dict, model: str) -> int:
        """计算消息的 Token 数量"""

    def count_conversation_tokens(self, messages: List[Dict], model: str) -> int:
        """计算对话的总 Token 数量"""

# 全局单例
def get_token_counter() -> DynamicTokenCounter:
    """获取全局 Token 计数器实例"""

# 便捷函数
def count_tokens(text: str, model: str = "claude-3-sonnet") -> int:
    """计算文本的 Token 数量（使用全局计数器）"""
```

**支持的模型系列**:
- Claude: cl100k_base + 15% margin
- GPT-4/3.5: cl100k_base（精确）
- Gemini: cl100k_base + 20% margin
- GLM: cl100k_base + 25% margin
- Qwen, Llama, Mistal 等

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

## 核心组件（v1.9 新增）

### 1. TTL 缓存基类

**通用的 TTL 缓存抽象，支持泛型键值对。**

```python
class TTLCache(Generic[K, V], ABC):
    """
    通用 TTL 缓存基类

    特性：
    - 泛型键值对支持
    - 自动过期清理
    - 线程安全
    - 最大条目限制
    """

    def get(self, key: K) -> Optional[V]: ...
    def set(self, key: K, value: V): ...
    def clear(self): ...
```

**子类**:
- `IdempotencyCache(TTLCache[str, ToolExecutionResult])`: 幂等性缓存
- `SummaryCache(TTLCache[str, Dict[str, Any]])`: 摘要缓存

### 2. ThreadSafeMixin

**为类提供简单的线程安全支持。**

```python
class ThreadSafeMixin:
    """线程安全混入类（Mixin）"""

    def __init__(self):
        self._lock = threading.Lock()

    @contextmanager
    def _with_lock(self):
        """获取锁的上下文管理器"""
        ...
```

### 3. 配置类统一接口

**所有配置类实现了统一的接口。**

```python
class BaseConfig(ABC):
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: ...      # 序列化
    @abstractmethod
    def from_dict(cls, data: Dict) -> "BaseConfig": ...  # 反序列化
    @abstractmethod
    def validate(self) -> bool: ...                # 验证
```

**配置类列表**:
- `EncoderConfig`: Token 编码器配置
- `ContextCompressionConfig`: 上下文压缩配置
- `ObservabilityConfig`: 可观测性配置

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

### 动态 Token 计数器

**支持多模型的动态 Token 计数系统。**

```python
class DynamicTokenCounter:
    """
    动态 Token 计数器 - 支持多模型和插件式编码器注册

    特性：
    - 自动识别模型系列（Claude, GPT, Gemini, GLM 等）
    - 配置文件支持（config/token_encoders.yaml）
    - 精确计数 + 安全余量
    """

    def count_tokens(self, text: str, model: str = "claude-3-sonnet") -> int:
        """计算文本的 Token 数量（自动选择编码器）"""
        config = self._registry.get_encoder_config(model)
        encoder = self._registry.get_encoder(model)
        estimated = len(encoder.encode(text))
        return int(estimated * config.safety_margin)

    def count_message_tokens(self, message: Dict, model: str) -> int:
        """计算消息的 Token 数量"""

    def count_conversation_tokens(self, messages: List[Dict], model: str) -> int:
        """计算对话的总 Token 数量"""

# 全局单例
def get_token_counter() -> DynamicTokenCounter:
    """获取全局 Token 计数器实例"""

# 便捷函数
def count_tokens(text: str, model: str = "claude-3-sonnet") -> int:
    """计算文本的 Token 数量（使用全局计数器）"""
```

**支持的模型系列**:
- Claude: cl100k_base + 15% margin
- GPT-4/3.5: cl100k_base（精确）
- Gemini: cl100k_base + 20% margin
- GLM: cl100k_base + 25% margin
- Qwen, Llama, Mistal 等

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

## 核心组件（v2.0 新增）

### 1. TTL 缓存基类

**通用的 TTL 缓存抽象，支持泛型键值对。**

```python
class TTLCache(Generic[K, V], ABC):
    """
    通用 TTL 缓存基类

    特性：
    - 泛型键值对支持
    - 自动过期清理
    - 线程安全
    - 最大条目限制
    """

    def get(self, key: K) -> Optional[V]: ...
    def set(self, key: K, value: V): ...
    def clear(self): ...
```

**子类**:
- `IdempotencyCache(TTLCache[str, ToolExecutionResult])`: 幂等性缓存
- `SummaryCache(TTLCache[str, Dict[str, Any]])`: 摘要缓存

### 2. ThreadSafeMixin

**为类提供简单的线程安全支持。**

```python
class ThreadSafeMixin:
    """线程安全混入类（Mixin）"""

    def __init__(self):
        self._lock = threading.Lock()

    @contextmanager
    def _with_lock(self):
        """获取锁的上下文管理器"""
        ...
```

### 3. 配置类统一接口

**所有配置类实现了统一的接口。**

```python
class BaseConfig(ABC):
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: ...      # 序列化
    @abstractmethod
    def from_dict(cls, data: Dict) -> "BaseConfig": ...  # 反序列化
    @abstractmethod
    def validate(self) -> bool: ...                # 验证
```

**配置类列表**:
- `EncoderConfig`: Token 编码器配置
- `ContextCompressionConfig`: 上下文压缩配置
- `ObservabilityConfig`: 可观测性配置

---

## 上下文管理（v2.1.0）

### AdvancedContextManager（智能压缩）

**v2.1.0 实现：优先级过滤 + LLM 摘要**

```python
class CompressionMode(str, Enum):
    TRUNCATE = "truncate"  # 简单截断（最快）
    EXTRACT = "extract"    # 优先级提取（智能）
    SUMMARIZE = "summarize"  # LLM 摘要（最慢）

class MessagePriority(str, Enum):
    CRITICAL = "critical"  # 必须保留（系统消息、错误）
    HIGH = "high"         # 应该保留（用户消息、工具结果）
    MEDIUM = "medium"     # 可能保留（助手推理）
    LOW = "low"           # 可以丢弃（详细日志）

class AdvancedContextManager:
    """
    高级上下文管理器（v2.1.0）

    特性：
    - Token 感知压缩（精确计数）
    - 消息优先级过滤（CRITICAL > HIGH > MEDIUM > LOW）
    - 三种压缩模式（TRUNCATE/EXTRACT/SUMMARIZE）
    - LLM 摘要支持（可选）
    - 后台摘要线程
    """

    def compress(
        self,
        messages: List[BaseMessage],
        target_tokens: Optional[int] = None,
        mode: Optional[CompressionMode] = None,
    ) -> List[BaseMessage]:
        """
        压缩消息列表至目标 Token 数。

        EXTRACT 模式优先级顺序：
        1. SystemMessage (CRITICAL) - 永远保留
        2. HumanMessage (HIGH) - 尽可能保留
        3. ToolMessage with errors (HIGH) - 保留错误
        4. AIMessage with tool_calls (HIGH) - 保留工具调用
        5. AIMessage without tool_calls (MEDIUM) - 可丢弃
        6. ToolMessage success (MEDIUM) - 可丢弃
        7. Verbose logs (LOW) - 优先丢弃
        """
```

**集成示例（BAAgent）**:

```python
# 在 BAAgent.__init__ 中
self.context_manager = AdvancedContextManager(
    max_tokens=self.app_config.llm.max_tokens,
    compression_mode=CompressionMode.EXTRACT,
    llm_summarizer=self.llm,
    token_counter=self.token_counter,
)

# 在 _compact_conversation 中
def _compact_conversation(self, conversation_id: str, keep_recent: int = 10):
    """使用 AdvancedContextManager 智能压缩"""
    all_messages = self.conversation_store.get_messages(conversation_id)
    target_tokens = int(self.app_config.llm.max_tokens * 0.5)
    compressed_messages = self.context_manager.compress(
        all_messages,
        target_tokens=target_tokens,
        mode=CompressionMode.EXTRACT,
    )
    self.conversation_store.update_messages(conversation_id, compressed_messages)
```

---

## 多轮对话流程

### 对话轮次

```python
class ConversationRound(BaseModel):
    round_id: str
    user_message: str
    thoughts: List[str]  # Agent 推理
    tool_calls: List[ToolInvocationRequest]
    tool_observations: List[str]  # 简单字符串
    final_answer: Optional[str]
    tokens_used: int
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
        """存储大数据到文件，返回 artifact_id"""

    @classmethod
    def retrieve_data(cls, artifact_id: str) -> Any:
        """通过 artifact_id 读取数据"""

    @classmethod
    def cleanup_old_files(cls, max_age_hours: int = 24):
        """清理过期文件"""
```

---

## 实施路线图

**v2.1.0 状态：全部完成 ✅**

### Phase 1: 核心消息格式 ✅
- [x] OutputLevel 枚举（BRIEF/STANDARD/FULL）
- [x] ToolCachePolicy 枚举（NO_CACHE/CACHEABLE/TTL_*）
- [x] ToolExecutionResult（单一源模型）
- [x] ToolInvocationRequest（工具调用请求）
- [x] DataStorage（artifact 存储）

### Phase 2: 工具通信协议 ✅
- [x] ToolTimeoutHandler（同步超时）
- [x] PipelineToolWrapper（LangChain 集成）
- [x] @pipeline_tool 装饰器
- [x] artifact_id 安全机制

### Phase 3: Skills 通信协议 ✅
- [x] SkillActivationRequest（渐进式披露）
- [x] 间接循环检测
- [x] MessageInjectionProtocol（线程安全）

### Phase 4: 多轮对话 ✅
- [x] 工具迁移（database, vector_search）
- [x] 向后兼容（use_pipeline 标志）
- [x] 42 测试通过

### Phase 5: 高级特性 ✅
- [x] IdempotencyCache（跨轮次缓存）
- [x] DynamicTokenCounter（多模型支持）
- [x] AdvancedContextManager（智能压缩）
- [x] BAAgent 集成
- [x] 132 测试通过

**提交记录**:
- `358f201`: Phase 1-3 核心模型
- `d4d8c35`: Phase 4 工具迁移
- `e4ebcb6`: Phase 5 高级特性
- `45dc323`: BAAgent 集成

---

## 版本历史

### v2.1.0 (2026-02-06) - 高级特性完整实现 ✅
**新增组件**:
1. `IdempotencyCache` - 跨轮次缓存（语义键，非 tool_call_id）
2. `DynamicTokenCounter` - 多模型 Token 计数（OpenAI tiktoken + Anthropic + fallback）
3. `AdvancedContextManager` - 智能上下文压缩（优先级过滤 + LLM 摘要）

**BAAgent 集成**:
- `_get_total_tokens()`: 使用 DynamicTokenCounter 精确计数
- `_compact_conversation()`: 使用 AdvancedContextManager 智能压缩
- `_check_and_flush()`: 双组件协同工作

**提交记录**:
- `e4ebcb6`: Phase 5 高级特性实现
- `45dc323`: BAAgent 集成
- `d4d8c35`: Phase 4 工具迁移
- `358f201`: Phase 1-3 核心模型

**测试通过**: 132 skills tests

### v2.0.1 (2026-02-06) - P0-P1 修复 + 单一源模型
**关键修复**:
1. P0-1: `ContentBlock` 添加 `content` 字段
2. P0-2: `ToolTimeoutHandler` 改为同步版本
3. P1-1: 删除 `ToolResultMessage`，统一使用 `ToolExecutionResult`
4. P1-2: `tool_call_id` 必须来自 LLM（不能生成）
5. P1-3: `StandardMessage` 语法修复 + 方法重命名
6. P1-4: 幂等键移除 `tool_call_id`（支持跨轮次缓存）
7. P1-5: 安全：`artifact_id` 替代真实路径

**新增**:
- `ToolCachePolicy` 枚举
- `FileArtifactSecurity` 安全规则
- LangChain Tool-call loop 文档

### v2.0.0 (2026-02-06) - LangChain 实现对齐
**架构变更**:
1. LangChain BaseMessage 为主协议
2. Claude Code 格式降级为"研究/调试"
3. Carrier vs Semantic 概念分离
4. 同步压缩策略（LLM 后台执行）

### v1.9.6 (2026-02-06) - 简化版文档同步
**同步 detailed 版本的核心更新**:
1. Token Counter → DynamicTokenCounter（多模型支持）
2. 新增核心组件章节（TTLCache, ThreadSafeMixin, 配置类接口）
3. ContextManager → AdvancedContextManager/BasicContextManager

### v1.9.5 (2026-02-06) - Review 修复
**修复**: 删除重复定义、更新 SchemaVersion、修复 ABC import

### v1.9.4 (2026-02-06) - P2 配置类统一
**新增**:
1. 统一配置类接口（to_dict/from_dict/validate）
2. EncoderConfig, ContextCompressionConfig, ObservabilityConfig 更新

### v1.9.3 (2026-02-06) - P1 代码质量改进
**新增**:
1. TTLCache 基类 - 泛型缓存抽象
2. IdempotencyCache / SummaryCache 重构
3. ThreadSafeMixin - 统一锁管理

### v1.9.2 (2026-02-06) - P0 冗余消除
**修复**:
1. TokenCounter 统一 - 删除旧实现，保留 DynamicTokenCounter
2. ContextManager 重构 - AdvancedContextManager / BasicContextManager

**文档优化**: 从 4478 行减少到 4318 行（节省 160 行）

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

### LangChain Tool-Call Loop

```python
# 1. LLM 响应
ai_msg = llm.invoke([human_msg])
# ai_msg.tool_calls = [{"id": "call_123", "name": "Glob", "args": {...}}]

# 2. 工具执行
tool_msg = ToolMessage(
    content="file1.py\nfile2.py\nfile3.py",
    tool_call_id=ai_msg.tool_calls[0]["id"]  # 必须匹配
)

# 3. LLM 处理结果
next_msg = llm.invoke([human_msg, ai_msg, tool_msg])
```

### Output Level 示例

```python
# 同一数据，不同级别
data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, ...]

BRIEF:    "Found 10 items"
STANDARD: "Found 10 items:\n  - {id: 1, name: Alice}\n  - {id: 2, name: Bob}..."
FULL:     "[{\"id\": 1, \"name\": \"Alice\"}, ...]"  # 完整 JSON
          # 或: "Data stored as artifact: artifact_abc123"
```

### 文件存储规则

| 条件 | 存储策略 |
|------|----------|
| data_size < 1MB & level != FULL | 内存（observation 直接包含） |
| data_size >= 1MB 或 level == FULL | 文件（observation 包含 artifact_id） |

### 安全：Artifact vs 真实路径

| 场景 | 错误做法 | 正确做法 |
|------|----------|----------|
| Observation | `/var/lib/ba-agent/artifacts/abc.json` | `artifact_abc123` |
| 日志 | `Stored to {real_path}` | `Stored as artifact_{hash}` |
| 访问 | 文件路径直接读取 | artifact_id + 沙箱验证 |

### Token 计数精度

| 方法 | 精度 | 用途 |
|------|------|------|
| 字符估算 (chars/3) | ±30% | 粗略判断 |
| tiktoken | ±1% | 生产环境 |
| API 返回 | 精确 | 最终验证 |

---

**文档版本**: v2.0.1 (Simplified)
**详细版**: ~5000 行 | **简化版**: ~600 行
**双文档结构**: 快速参考 + 完整实现
