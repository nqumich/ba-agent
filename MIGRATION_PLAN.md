# Pipeline Models Migration Plan

## Status: Phase 1-3 Complete, Phase 4 In Progress

### Completed ✅
- [x] Phase 1: Core pipeline models (OutputLevel, ToolCachePolicy, ToolExecutionResult)
- [x] Phase 2: Tool protocol (ToolInvocationRequest, ToolTimeoutHandler, DataStorage)
- [x] Phase 3: Agent integration (PipelineToolWrapper)

### In Progress 🔄
- [ ] Phase 4: Migrate existing tools to use new pipeline models

### Pending ⏳
- [ ] Phase 5: Add IdempotencyCache
- [ ] Phase 6: Add DynamicTokenCounter
- [ ] Phase 7: Remove deprecated models

---

## Conflict Summary

| Old Model | New Model | Action |
|-----------|-----------|--------|
| `ResponseFormat` | `OutputLevel` | Keep parallel, migrate incrementally |
| `ToolOutput` (tool_output.py) | `ToolExecutionResult` | Keep parallel, migrate incrementally |
| `ToolInput` (tool.py) | `ToolInvocationRequest` | Keep parallel, migrate incrementally |

**DO NOT DELETE old models yet** - they are used by:
- `tools/base.py` - Core tool wrapper
- `tools/database.py` - Database query tool
- `tools/vector_search.py` - Vector search tool
- 15+ test files

---

## Migration Steps

### Step 1: Update tools/base.py (HIGH PRIORITY)
Create adapter to support both old and new formats:
```python
# tools/base.py should be updated to:
# 1. Support both ResponseFormat and OutputLevel
# 2. Convert ToolOutput to ToolExecutionResult when needed
```

### Step 2: Update individual tools
Migrate tools one by one:
- tools/database.py
- tools/vector_search.py
- Other tools

### Step 3: Update tests
Migrate tests to use new models where appropriate.

### Step 4: Deprecate old models
Add deprecation warnings to old models.

### Step 5: Remove old models (FINAL STEP)
Only after all tools and tests are migrated.

---

## Compatibility Layer

```python
# backend/models/compat.py - To be created
# Provides adapters between old and new formats

def tool_output_to_execution_result(tool_output: ToolOutput) -> ToolExecutionResult:
    """Convert old ToolOutput to new ToolExecutionResult."""
    pass

def response_format_to_output_level(response_format: ResponseFormat) -> OutputLevel:
    """Convert old ResponseFormat to new OutputLevel."""
    pass
```

---

## Timeline

- Week 1: Core models (DONE)
- Week 2: Tool protocol + Agent integration (DONE)
- Week 3: Migrate tools base + database
- Week 4: Migrate remaining tools + tests
- Week 5: Deprecation + removal
