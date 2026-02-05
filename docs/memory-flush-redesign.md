# Memory Flush 重构设计文档

**日期**: 2025-02-05
**状态**: 设计阶段
**目标**: 将 Memory Flush 重构为 Clawdbot 风格的静默轮次模式

---

## 背景

当前 MemoryFlush 使用**回调模式**：
- 系统触发阈值检查
- LLM 直接提取记忆
- 通过回调或直接写入文件

Clawdbot 使用**静默 ReAct 轮次**模式：
- 系统触发阈值检查
- 注入一个额外的 Agent ReAct 循环
- Agent 自己决定如何使用工具（write、edit 等）保存记忆
- 用户完全不可见（返回 `SILENT_REPLY_TOKEN`）

---

## 方案对比

### 当前实现 (回调模式)

```python
# backend/agents/agent.py
def _check_and_flush(self, ...):
    if should_flush:
        memories = self.memory_flush.extractor.extract_from_messages(messages)
        self.memory_flush._flush_memories(memories)
```

**优点**:
- 简单直接，开销小
- 不需要额外的 Agent 轮次

**缺点**:
- Agent 无法控制提取过程
- 无法使用 Agent 的工具（如 memory_retain）
- 提取质量完全依赖 Prompt 设计

### Clawdbot 实现 (静默 ReAct 轮次)

```typescript
// src/auto-reply/reply/agent-runner-memory.ts
const flushSystemPrompt = [
  "Pre-compaction memory flush turn.",
  "The session is near auto-compaction; capture durable memories to disk.",
  `You may reply, but usually ${SILENT_REPLY_TOKEN} is correct.`
].join("\n\n");

await runEmbeddedPiAgent({
  prompt: memoryFlushSettings.prompt,
  extraSystemPrompt: flushSystemPrompt,
  // Agent 使用 write/edit 工具保存记忆
});
```

**优点**:
- Agent 完全控制记忆保存过程
- 可以使用所有可用工具
- 更灵活，Agent 可以调用复杂逻辑

**缺点**:
- 需要额外的 ReAct 循环（开销更大）
- 实现更复杂
- 需要处理"静默"响应（`SILENT_REPLY_TOKEN`）

---

## 方案 A: 完全模拟 Clawdbot (静默 ReAct 轮次)

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  Token 阈值检测                                             │
│  session_tokens >= contextWindow - reserve - softThreshold  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  注入静默 Flush 轮次                                         │
│  - 添加特殊的 system prompt                                 │
│  - 提供用户不可见的 prompt                                   │
│  - Agent 执行完整的 ReAct 循环                               │
│  - Agent 调用 memory_retain / file_write 工具               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  检测响应                                                     │
│  - 如果是 SILENT_REPLY_TOKEN → 用户不可见                   │
│  - 否则显示给用户（异常情况）                                │
└─────────────────────────────────────────────────────────────┘
```

### 实现要点

1. **SILENT_REPLY_TOKEN** - 定义特殊标记
   ```python
   SILENT_REPLY_TOKEN = "_SILENT_"
   ```

2. **Flush System Prompt** - 专门的系统提示词
   ```python
   FLUSH_SYSTEM_PROMPT = """
   # Memory Flush 模式

   你现在处于 Memory Flush 模式。你的任务是从当前对话中提取重要信息并持久化到记忆文件。

   ## Retain 格式规范

   使用以下格式提取信息：
   - W @entity: 内容    # 世界事实 (World Facts)
   - B @entity: 内容    # 传记信息 (Biography)
   - O(c=0.9) @entity:  # 观点 (Opinion)
   - S @entity: 内容    # 总结 (Summary)

   ## 工具使用

   - 使用 memory_retain 工具格式化记忆
   - 使用 file_write 工具写入 memory/YYYY-MM-DD.md
   - 如果没有需要保存的内容，回复 {SILENT_REPLY_TOKEN}
   """
   ```

3. **Agent 集成** - 修改 invoke 流程
   ```python
   def invoke(self, ...):
       result = self.agent.invoke(...)

       # 检查是否需要 flush
       if self._should_flush():
           # 运行静默 flush 轮次
           flush_result = self._run_flush_turn()

           # 检查是否是静默响应
           if not flush_result.startswith(SILENT_REPLY_TOKEN):
               # 非静默，记录或显示
               pass

       return result
   ```

4. **避免重复 Flush** - 记录 compaction_count
   ```python
   self.compaction_count = 0
   self.memory_flush_compaction_count = None

   def _should_flush(self):
       # 只在 token 阈值且 compaction_count 变化时触发
       return (self.session_tokens >= threshold and
               self.memory_flush_compaction_count != self.compaction_count)
   ```

### 文件变更

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/agents/agent.py` | 重构 | 添加 `_run_flush_turn()` 方法 |
| `backend/memory/flush.py` | 简化 | 保留配置，移除提取逻辑 |
| `config/config.py` | 新增 | `SILENT_REPLY_TOKEN` 常量 |

---

## 方案 B: 简化版本 (当前实现优化)

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  Token 阈值检测                                             │
│  session_tokens >= contextWindow - reserve - softThreshold  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  直接 LLM 提取 (无额外 ReAct 循环)                          │
│  - 使用 MemoryExtractor.extract_from_messages()            │
│  - 直接写入 memory/YYYY-MM-DD.md                            │
│  - 用户完全不可见                                            │
└─────────────────────────────────────────────────────────────┘
```

### 实现要点

1. **保留当前提取逻辑** - MemoryExtractor 继续工作
2. **优化触发时机** - 添加 compaction_count 避免重复
3. **确保用户不可见** - flush 结果不返回给用户

### 文件变更

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/agents/agent.py` | 轻量修改 | 添加重复检测，隐藏 flush 结果 |
| `backend/memory/flush.py` | 保持不变 | 当前实现已满足需求 |

---

## 决策

**当前选择**: 方案 B (简化版本)

**理由**:
1. 当前 MemoryExtractor 实现已经足够好（LLM 提取 + Retain 格式）
2. 避免 ReAct 轮次的开销
3. 实现简单，风险低

**方案 A 保留为未来升级方向**:
- 当需要更复杂的记忆处理逻辑时
- 当希望 Agent 使用更多工具时

---

## 实现计划 (方案 B)

### Phase 1: 优化触发逻辑
- [ ] 添加 `memory_flush_compaction_count` 追踪
- [ ] 实现 `should_run_memory_flush()` 函数
- [ ] 避免在同一 compaction 阶段重复 flush

### Phase 2: 确保用户不可见
- [ ] flush 结果不返回给用户
- [ ] 添加日志记录（debug 级别）

### Phase 3: 测试
- [ ] 单元测试：触发条件
- [ ] 集成测试：完整流程

---

## 参考文档

- Clawdbot Memory Flush: `src/auto-reply/reply/memory-flush.ts`
- Clawdbot Agent Runner: `src/auto-reply/reply/agent-runner-memory.ts`
- 当前实现: `backend/memory/flush.py`, `backend/agents/agent.py`
