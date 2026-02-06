# BA-Agent Context Manager 使用指南

> **版本**: v1.0
> **日期**: 2026-02-06
> **目标读者**: 开发者、运维人员

---

## 目录

1. [核心功能](#核心功能)
2. [监控压缩效果](#监控压缩效果)
3. [两种实现对比](#两种实现对比)
4. [使用示例](#使用示例)
5. [配置指南](#配置指南)
6. [最佳实践](#最佳实践)

---

## 核心功能

### Context Manager 的作用

**核心目标**: 管理对话历史（上下文），防止超出模型的上下文窗口限制。

```
问题: 上下文窗口有限 (Claude: 200K tokens)
    ↓
解决: Context Manager 自动压缩旧消息
    ↓
结果: 对话可以持续进行，关键信息不丢失
```

### 关键特性

| 特性 | 说明 |
|------|------|
| **Token 监控** | 实时计算对话的 Token 使用量 |
| **自动压缩** | 超过阈值时自动触发压缩 |
| **智能保留** | 根据消息重要性决定是否保留 |
| **多策略支持** | TRUNCATE / EXTRACT / SUMMARIZE |
| **线程安全** | 支持并发访问 |

---

## 监控压缩效果

### 1. 基础监控指标

#### ConversationMetrics（对话级指标）

```python
@dataclass
class ConversationMetrics:
    conversation_id: str

    # Token 使用
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0

    # 消息管理
    messages_count: int = 0
    compression_events: int = int  # 压缩次数

    # 压缩效果追踪
    compressed_tokens_saved: int = 0  # 压缩节省的 tokens
    compression_rate: float = 0.0      # 压缩率 (0-1)
```

#### 使用示例

```python
# 初始化时关联 MetricsCollector
manager = AdvancedContextManager(
    max_tokens=200000,
    metrics_collector=get_metrics_collector()
)

# 添加消息时自动记录
manager.add_message(
    message={"role": "user", "content": "你好"},
    conversation_id="conv_123"
)

# 获取压缩统计
metrics = manager.get_compression_stats()
print(f"压缩次数: {metrics['compression_events']}")
print(f"节省 Token: {metrics['tokens_saved']}")
print(f"压缩率: {metrics['compression_rate']:.1%}")
```

### 2. 高级监控指标

#### 实时监控 API

```python
class AdvancedContextManager:
    def get_compression_stats(self) -> Dict[str, Any]:
        """获取压缩统计信息"""
        total_tokens = sum(m.tokens for m in self._messages)
        original_tokens = total_tokens  # 简化版，实际应该是累积值
        compressed_tokens = total_tokens  # 当前实际使用

        # 计算压缩率
        if hasattr(self, '_original_total_tokens'):
            compression_rate = 1 - (compressed_tokens / self._original_total_tokens)
        else:
            compression_rate = 0.0

        return {
            "total_messages": len(self._messages),
            "total_tokens": total_tokens,
            "max_tokens": self.max_tokens,
            "usage_rate": total_tokens / self.max_tokens,
            "compression_events": getattr(self, '_compression_count', 0),
            "compression_rate": compression_rate,
            "tokens_saved": self._original_total_tokens - total_tokens if hasattr(self, '_original_total_tokens') else 0,
        }
```

#### 监控输出示例

```python
{
    "total_messages": 127,
    "total_tokens": 84500,
    "max_tokens": 200000,
    "usage_rate": 0.4225,
    "compression_events": 3,
    "compression_rate": 0.67,
    "tokens_saved": 171500,
    "last_compression": "2026-02-06T14:30:00"
}
```

### 3. 压缩效果评估

#### 评估维度

| 维度 | 指标 | 良好值 | 说明 |
|------|------|--------|------|
| **压缩率** | compression_rate | > 0.5 | 节省 50% 以上 |
| **保留质量** | 关键信息保留率 | > 0.9 | 90% 关键信息保留 |
| **性能** | 压缩延迟 | < 1s | 不影响用户体验 |
| **成本** | LLM 调用成本 | < $0.01/h | 可接受的 API 成本 |

#### 日志记录

```python
import logging

logger = logging.getLogger(__name__)

class AdvancedContextManager:
    def _compress_context(self):
        """执行上下文压缩（带日志）"""
        before_tokens = sum(m.tokens for m in self._messages)

        logger.info(f"[Context] Compression triggered")
        logger.info(f"[Context] Before: {before_tokens} tokens, {len(self._messages)} messages")

        # 执行压缩
        strategy = self._select_compression_strategy(before_tokens)
        logger.info(f"[Context] Strategy: {strategy.value}")

        if strategy == ContextCompressionStrategy.SUMMARIZE:
            await self._compress_summarize()
        elif strategy == ContextCompressionStrategy.EXTRACT:
            self._compress_extract()
        else:
            self._compress_truncate()

        after_tokens = sum(m.tokens for m in self._messages)
        saved_tokens = before_tokens - after_tokens

        logger.info(
            f"[Context] Compression complete: "
            f"{before_tokens} → {after_tokens} (saved {saved_tokens}, {saved/before_tokens:.1%})"
        )

        # 记录指标
        self._compression_count += 1
        if hasattr(self, '_metrics_collector') and self._metrics_collector:
            self._metrics_collector.record_compression(
                conversation_id=self.conversation_id,
                before_tokens=before_tokens,
                after_tokens=after_tokens,
                strategy=strategy.value
            )
```

### 4. 可视化监控

#### Grafana Dashboard 示例

```yaml
# context-metrics-dashboard.json
{
  "title": "Context Manager 监控",
  "panels": [
    {
      "title": "Token 使用趋势",
      "type": "graph",
      "targets": [
        {
          "expr": "context_tokens_total",
          "legendFormat": "总 Tokens"
        },
        {
          "expr": "context_tokens_compressed",
          "legendFormat": "压缩后 Tokens"
        }
      ]
    },
    {
      "title": "压缩率",
      "type": "gauge",
      "targets": [
        {
          "expr": "context_compression_rate",
          "legendFormat": "压缩率"
        }
      ]
    },
    {
      "title": "压缩次数",
      "type": "stat",
      "targets": [
        {
          "expr": "context_compression_events_total",
          "legendFormat": "总压缩次数"
        }
      ]
    }
  ]
}
```

---

## 两种实现对比

### BasicContextManager vs AdvancedContextManager

| 特性 | Basic | Advanced |
|------|-------|----------|
| **压缩策略** | 基于重要性 | 3 种策略（自动选择） |
| **LLM 支持** | ❌ | ✅ (Claude 3 Haiku) |
| **异步支持** | ❌ | ✅ |
| **压缩质量** | 中等 | 高 |
| **性能** | 快（同步） | 中等（异步） |
| **复杂度** | 低 | 中 |
| **成本** | 0 | 低 API 调用成本 |

### 选择决策树

```
是否需要 LLM 智能摘要？
    │
    ├─ YES → AdvancedContextManager
    │         ↓
    │     能接受异步吗？
    │     │
    │     ├─ YES → AdvancedContextManager (异步)
    │     └─ NO  → AdvancedContextManager (同步包装)
    │
    └─ NO  → BasicContextManager
              ↓
           能接受简单压缩吗？
              ├─ YES → BasicContextManager
              └─ NO  → 自定义方案
```

---

## 使用示例

### 示例 1: 基础使用

```python
from ba_agent.context import BasicContextManager
from ba_agent.models import MessageImportance

# 初始化
manager = BasicContextManager(max_tokens=100000)

# 添加消息
manager.add_message(
    message={"role": "user", "content": "分析销售数据"},
    importance=MessageImportance.CRITICAL,  # 用户消息 = CRITICAL
    round_id="round_1"
)

# 工具调用结果
manager.add_message(
    message={"role": "assistant", "content": "", "tool_calls": [...]},
    importance=MessageImportance.HIGH,  # Tool observations = HIGH
    round_id="round_1"
)

# 检查状态
stats = manager.get_compression_stats()
print(f"Token 使用率: {stats['usage_rate']:.1%}")
```

### 示例 2: 高级使用（带监控）

```python
import asyncio
from ba_agent.context import AdvancedContextManager
from ba_agent.monitoring import MetricsCollector

# 初始化（带监控）
metrics = MetricsCollector()
manager = AdvancedContextManager(
    max_tokens=200000,
    compression_config=ContextCompressionConfig(
        strategy=ContextCompressionStrategy.EXTRACT,
        enable_llm_summarization=True,
        llm_summarization_threshold=50
    ),
    metrics_collector=metrics
)

async def chat_loop():
    conversation_id = "conv_123"

    # 第一轮
    await process_user_message(
        "帮我分析本月销售数据",
        manager,
        conversation_id
    )

    # 检查压缩效果
    stats = manager.get_compression_stats()
    print(f"压缩次数: {stats['compression_events']}")
    print(f"压缩率: {stats['compression_rate']:.1%}")

    # 获取全局指标
    global_stats = metrics.get_global_stats()
    print(f"全局 Token 使用: {global_stats['total_tokens']}")

asyncio.run(chat_loop())
```

### 示例 3: 自定义监控

```python
class MonitoredContextManager(AdvancedContextManager):
    """带自定义监控的上下文管理器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._compression_history = []

    async def _compress_context(self):
        """重写压缩方法，添加详细监控"""
        before = {
            "timestamp": datetime.now().isoformat(),
            "tokens": sum(m.tokens for m in self._messages),
            "messages": len(self._messages)
        }

        # 调用父类压缩方法
        await super()._compress_context()

        after = {
            "timestamp": datetime.now().isoformat(),
            "tokens": sum(m.tokens for m in self._messages),
            "messages": len(self._messages)
        }

        # 记录历史
        record = {
            "before": before,
            "after": after,
            "saved": before["tokens"] - after["tokens"],
            "rate": 1 - (after["tokens"] / before["tokens"])
        }
        self._compression_history.append(record)

        # 触发告警
        if record["rate"] < 0.3:  # 压缩率低于 30%
            logger.warning(f"Low compression rate: {record['rate']:.1%}")

        # 发送到监控系统
        self._send_metrics(record)

    def _send_metrics(self, record):
        """发送到监控系统"""
        # Prometheus
        # prometheus_metrics.compression_rate.set(record["rate"])
        pass

    def get_compression_history(self):
        """获取压缩历史"""
        return self._compression_history
```

---

## 配置指南

### 1. 基础配置

```python
# config/context.yaml

context_manager:
  # Token 限制（根据模型选择）
  max_tokens:
    claude-3-opus: 200000
    claude-3-sonnet: 200000
    claude-3-haiku: 200000
    gpt-4: 128000
    gpt-3.5-turbo: 16000

  # 压缩阈值
  compression_threshold: 0.8  # 80% 时触发

  # 默认压缩策略
  default_strategy: "extract"  # truncate/extract/summarize
```

### 2. 高级配置

```python
# config/context-advanced.yaml

advanced_context_manager:
  # 压缩策略配置
  compression:
    strategy: "extract"  # 固定策略或 "auto"

    # LLM 摘要配置
    llm_summarization:
      enabled: true
      model: "claude-3-haiku"
      max_summary_tokens: 500
      threshold: 50  # 超过 50 条消息才使用 LLM
      cache_ttl: 24  # 摘要缓存 24 小时

    # 成本控制
    max_cost_per_hour: 0.1  # 每小时最大 LLM 成本（美元）

  # 监控配置
  monitoring:
    enabled: true
    log_level: "INFO"

    # 告警阈值
    alerts:
      low_compression_rate: 0.3  # 压缩率低于 30%
      high_compression_frequency: 10  # 每小时压缩超过 10 次

    # Prometheus 指标
    prometheus:
      enabled: true
      port: 9090
```

### 3. 监控集成

#### Prometheus 集成

```python
from prometheus_client import Counter, Gauge, Histogram

# 定义指标
context_tokens_total = Gauge(
    'context_tokens_total',
    'Current token usage in context',
    ['conversation_id']
)

context_compression_events_total = Counter(
    'context_compression_events_total',
    'Total number of compression events',
    ['strategy', 'conversation_id']
)

context_compression_rate = Gauge(
    'context_compression_rate',
    'Compression rate (0-1)',
    ['conversation_id']
)

class MonitoredContextManager(AdvancedContextManager):
    """集成 Prometheus 监控"""

    def __init__(self, *args, conversation_id: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_id = conversation_id

    def add_message(self, message, importance, round_id=""):
        """添加消息并更新指标"""
        super().add_message(message, importance, round_id)

        # 更新 Token 指标
        total_tokens = sum(m.tokens for m in self._messages)
        context_tokens_total.labels(conversation_id=self.conversation_id).set(total_tokens)

    async def _compress_context(self):
        """压缩并记录指标"""
        before_tokens = sum(m.tokens for m in self._messages)

        # 执行压缩
        strategy = self._select_compression_strategy(before_tokens)
        await super()._compress_context()

        after_tokens = sum(m.tokens for m in self._messages)

        # 记录压缩事件
        context_compression_events_total.labels(
            strategy=strategy.value,
            conversation_id=self.conversation_id
        ).inc()

        # 更新压缩率
        rate = 1 - (after_tokens / before_tokens) if before_tokens > 0 else 0
        context_compression_rate.labels(conversation_id=self.conversation_id).set(rate)
```

---

## 最佳实践

### 1. 选择合适的 Token 限制

```python
# 根据模型选择 max_tokens
MODEL_MAX_TOKENS = {
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "gpt-4": 128000,
    "gpt-3.5-turbo": 16000,
    "gemini-pro": 128000,
}

def get_max_tokens(model: str) -> int:
    """获取模型的 Token 限制"""
    return MODEL_MAX_TOKENS.get(model, 200000) * 0.95  # 保留 5% 余量
```

### 2. 设置合理的压缩阈值

```python
# 不推荐：阈值太高
manager = AdvancedContextManager(
    max_tokens=200000,
    compression_threshold=0.95  # 95% 才压缩，太晚
)

# 推荐：阈值适中
manager = AdvancedContextManager(
    max_tokens=200000,
    compression_threshold=0.75  # 75% 时压缩
)
```

### 3. 监控关键指标

```python
# 关键指标
KEY_METRICS = [
    "compression_rate",      # 压缩率（目标 > 0.5）
    "compression_frequency", # 压缩频率（目标 < 5 次/小时）
    "token_usage_rate",     # Token 使用率（目标 < 80%）
    "critical_preserved",    # 关键信息保留率（目标 > 0.95）
]

# 告警规则
ALERT_RULES = {
    "compression_rate_low": {"condition": "< 0.3", "severity": "warning"},
    "compression_frequent": {"condition": "> 10/hour", "severity": "warning"},
    "token_usage_high": {"condition": "> 0.9", "severity": "critical"},
}
```

### 4. 定期审查压缩效果

```python
def review_compression_effectiveness(manager):
    """审查压缩效果"""
    stats = manager.get_compression_stats()

    # 评估压缩率
    if stats['compression_rate'] < 0.3:
        print("⚠️  压缩率过低，建议:")
        print("   - 降低 compression_threshold")
        print("   - 启用 LLM summarization")

    # 评估压缩频率
    if stats['compression_events'] > 10:
        print("⚠️  压缩过于频繁，建议:")
        print("   - 增加 max_tokens")
        print("   - 优化 prompt 减少输出")

    # 评估 Token 使用
    if stats['usage_rate'] > 0.9:
        print("⚠️  Token 使用率过高，建议:")
        print("   - 立即触发压缩")
        print("   - 考虑清理不重要的历史消息")
```

---

## 附录

### A. 常见问题

**Q1: 如何知道压缩是否有效？**

A: 查看监控指标：
- `compression_rate`: 应该 > 0.5（节省 50% 以上）
- `critical_preserved`: 应该 > 0.95（95% 关键信息保留）
- 日志中的 "saved X tokens" 信息

**Q2: 压缩后的信息丢失了怎么办？**

A:
- BasicContextManager: 按重要性压缩，重要信息不会丢失
- AdvancedContextManager: LLM 摘要保留语义，关键信息保留
- 可以通过 `get_compressed_messages()` 查看当前状态

**Q3: 如何调优压缩效果？**

A:
1. 调整 `compression_threshold`（默认 0.8）
2. 调整 `llm_threshold`（默认 50 条消息）
3. 优化 `MessageImportance` 标记
4. 启用摘要缓存减少 LLM 调用

### B. 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 压缩率低 | 阈值太高、策略不当 | 降低 threshold、启用 SUMMARIZE |
| 频繁压缩 | Token 限制太小 | 增加 max_tokens |
| 关键信息丢失 | 重要性标记错误 | 检查 MessageImportance |
| 压缩慢 | LLM 调用慢 | 启用摘要缓存、降低 LLM 频率 |

---

## 相关文档

- [信息管道设计文档](./information-pipeline-design.md) - 简化版
- [信息管道设计详细版](./information-pipeline-design-detailed.md) - 完整实现
- [监控系统配置](./monitoring-setup.md) - 监控配置指南

---

**更新**: 2026-02-06
**维护者**: BA-Agent Development Team
