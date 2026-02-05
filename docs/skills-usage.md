# Skills System Usage Guide

> **Version**: 1.0.0
> **Last Updated**: 2026-02-05

Practical guide for using the BA-Agent Skills system.

## Table of Contents

- [Overview](#overview)
- [Creating a New Skill](#creating-a-new-skill)
- [Activating Skills Programmatically](#activating-skills-programmatically)
- [Installing External Skills](#installing-external-skills)
- [Managing Skill Permissions](#managing-skill-permissions)
- [Best Practices](#best-practices)
- [Patterns and Examples](#patterns-and-examples)

---

## Overview

The BA-Agent Skills system implements **Anthropic's Agent Skills specification**, where skills are instruction packages that modify Agent behavior through context injection, not function execution.

### Key Concepts

1. **Progressive Disclosure**: Three-level loading (metadata → instructions → resources)
2. **Semantic Discovery**: Agent selects skills based on description matching
3. **Context Modification**: Skills inject instructions and modify tool permissions
4. **Open Standard**: Compatible with Claude Code's skills format

### Architecture

```
User Request → Agent Reads Skill Descriptions → Activates Matching Skill
                                              ↓
                         Injects Instructions + Tool Permissions
                                              ↓
                         Agent Follows Specialized Workflow
```

---

## Creating a New Skill

### Basic Skill Structure

```
skills/my_skill/
├── SKILL.md              # Required: Skill definition
├── main.py              # Optional: Entrypoint function
├── scripts/             # Optional: Automation scripts
│   └── process.py
├── references/          # Optional: Documentation
│   └── api_reference.md
└── assets/              # Optional: Templates, configs
    └── template.json
```

### SKILL.md Format

A skill file has two parts: **YAML frontmatter** and **markdown instructions**.

#### Example: Data Analysis Skill

```markdown
---
name: data_analysis
display_name: "数据分析"
description: "执行数据分析任务，包括统计计算、趋势识别和异常检测。适用于需要深入理解数据模式的场景。"
version: "1.0.0"
category: "Analysis"
author: "Your Team"
entrypoint: "skills/data_analysis/main.py"
function: "analyze"
requirements:
  - "pandas>=2.0.0"
  - "numpy>=1.24.0"
allowed_tools: "database,python_sandbox,web_reader"
model: claude-sonnet-4-20250514
tags:
  - analysis
  - data
  - statistics
examples:
  - "分析最近30天的销售趋势"
  - "计算用户留存率的统计指标"
  - "检测GMV数据中的异常值"
---

# 数据分析 Skill

## 描述

此技能提供完整的数据分析工作流程，包括数据获取、清洗、分析和可视化。

## 何时使用

当用户请求以下任务时激活此技能：
- 分析数据趋势和模式
- 计算统计指标
- 检测异常值
- 生成分析报告

## 分析流程

### Step 1: 理解需求

确认以下信息：
1. **数据源**: 哪些数据需要分析？
2. **时间范围**: 分析什么时间段？
3. **分析目标**: 要回答什么问题？
4. **输出格式**: 报告、图表、原始数据？

### Step 2: 获取数据

使用 `database` 工具查询数据：

```python
# 查询示例
query = """
SELECT
    DATE(order_time) as date,
    SUM(amount) as gmv,
    COUNT(*) as orders
FROM orders
WHERE order_time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(order_time)
ORDER BY date
"""
```

### Step 3: 数据分析

使用 `python_sandbox` 执行分析：

```python
import pandas as pd
import numpy as np

# 计算统计指标
df['gmv_ma7'] = df['gmv'].rolling(7).mean()
df['growth_yoy'] = df['gmv'].pct_change(365) * 100

# 检测异常值 (3-sigma)
mean = df['gmv'].mean()
std = df['gmv'].std()
df['is_anomaly'] = np.abs(df['gmv'] - mean) > 3 * std
```

### Step 4: 结果呈现

生成结构化报告：

```markdown
## 数据分析报告

### 数据概览
- 分析周期: [起始日期] 至 [结束日期]
- 数据点数: N
- 平均GMV: X元

### 关键发现
1. **趋势**: GMV呈现[上升/下降/波动]趋势
2. **异常**: 检测到N个异常点
3. **相关性**: [发现的相关关系]

### 建议
基于分析结果的建议...
```

## 可用资源

- **脚本**: `{baseDir}/scripts/analysis.py` - 统计分析函数
- **参考**: `{baseDir}/references/methods.md` - 统计方法说明
```

### Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Skill identifier (lowercase, underscores/hyphens) |
| `display_name` | string | - | Human-readable name |
| `description` | string | ✅ | What it does AND when to use it (max 500 chars) |
| `version` | string | - | Semantic version (default: "1.0.0") |
| `category` | string | - | Category for grouping |
| `author` | string | - | Author name or team |
| `entrypoint` | string | - | Path to main.py |
| `function` | string | - | Function name (default: "main") |
| `requirements` | list | - | Python package dependencies |
| `allowed_tools` | string | - | Comma-separated tool list |
| `model` | string | - | Model override |
| `disable_model_invocation` | boolean | - | Prevent model from invoking itself |
| `mode` | boolean | - | Mode command (shown first) |
| `tags` | list | - | Search tags |
| `examples` | list | - | Example queries |

---

## Activating Skills Programmatically

### Direct Activation

```python
from pathlib import Path
from backend.skills import (
    SkillLoader,
    SkillRegistry,
    SkillActivator,
)

# Initialize
loader = SkillLoader(skills_dirs=[Path("skills")])
registry = SkillRegistry(loader)
activator = SkillActivator(loader, registry)

# Activate a skill
try:
    messages, context_modifier = activator.activate_skill("data_analysis")

    # Process messages
    for msg in messages:
        if msg.get("isMeta"):
            # Hidden instruction - add to conversation without showing user
            conversation.add_hidden_message(msg)
        else:
            # Visible metadata - show user
            conversation.add_message(msg)

    # Apply context modifier
    if "allowed_tools" in context_modifier:
        agent.grant_tool_permissions(context_modifier["allowed_tools"])

    if "model" in context_modifier:
        agent.switch_model(context_modifier["model"])

except SkillActivationError as e:
    print(f"Failed to activate: {e}")
```

### Integration with BAAgent

The BAAgent class has built-in skills integration:

```python
from backend.agents import BAAgent

# Initialize agent (skills system auto-initialized)
agent = BAAgent(app_config=...)

# Skills are automatically discovered and their descriptions
# are included in the system prompt

# Agent can activate skills based on semantic matching
# (activation happens automatically during conversation)
```

### Checking Available Skills

```python
# List all skills
skill_names = registry.list_skill_names()
print(f"Available skills: {skill_names}")

# Get skill metadata
metadata = registry.get_skill_metadata("data_analysis")
print(f"Name: {metadata.display_name}")
print(f"Description: {metadata.description}")
print(f"Version: {metadata.version}")

# Get formatted skills list (for system prompt)
skills_list = registry.get_formatted_skills_list()
print(skills_list)
```

---

## Installing External Skills

### From GitHub

```python
from pathlib import Path
from backend.skills import SkillInstaller

installer = SkillInstaller(install_dir=Path(".claude/skills"))

# Install from GitHub repository
skill = installer.install_from_github(
    repo="anthropics/skills",
    subdirectory="sql-analyzer",
    ref="v1.2.0"  # Optional: specific version
)

print(f"Installed: {skill.metadata.name}")
print(f"Version: {skill.metadata.version}")
```

### From Private Repository

```python
import os
from backend.skills import SkillInstaller

installer = SkillInstaller(install_dir=Path(".claude/skills"))

# Use GitHub PAT for private repos
skill = installer.install_from_github(
    repo="my-company/internal-skills",
    subdirectory="proprietary-analysis",
    auth_token=os.environ.get("GITHUB_TOKEN")
)
```

### From Git URL

```python
from backend.skills import SkillInstaller

installer = SkillInstaller(install_dir=Path(".claude/skills"))

# Install from any git hosting service
skill = installer.install_from_git_url(
    url="https://gitlab.com/owner/skill.git",
    ref="main"  # Optional: branch or tag
)
```

### From ZIP File

```python
from pathlib import Path
from backend.skills import SkillInstaller

installer = SkillInstaller(install_dir=Path(".claude/skills"))

# Install from ZIP archive
skill = installer.install_from_zip(Path("my-skill.zip"))
print(f"Installed: {skill.metadata.name}")
```

### Managing Installed Skills

```python
from backend.skills import SkillInstaller

installer = SkillInstaller(install_dir=Path(".claude/skills"))

# List installed skills
for skill_info in installer.list_installed():
    print(f"- {skill_info['name']} v{skill_info['version']}")
    print(f"  {skill_info['description']}")

# Update a skill
updated_skill = installer.update("sql-analyzer")

# Uninstall a skill
installer.uninstall("sql-analyzer", remove_files=True)
```

---

## Managing Skill Permissions

### Granting Tool Access

Skills can pre-approve tools using `allowed_tools` in frontmatter:

```yaml
---
name: data_export
allowed_tools: "database,python_sandbox,file_writer"
---
```

This means when the skill is activated, the Agent can use these tools without additional approval.

### Permission Format

```yaml
# Single tool
allowed_tools: "database"

# Multiple tools (comma-separated)
allowed_tools: "database,python_sandbox,file_writer"

# Tools with parameters
allowed_tools: "Bash(python:*),Read(*.csv),Write(data/*.json)"
```

### Model Override

Skills can specify which model to use:

```yaml
---
name: complex_analysis
model: claude-opus-4-20250514  # Use more capable model
---
```

### Disabling Model Invocation

For pure automation skills:

```yaml
---
name: automated_report
disable_model_invocation: true  # Skill handles execution directly
---
```

### Context Modifier

When a skill is activated, the context modifier is returned:

```python
messages, context = activator.activate_skill("my_skill")

# Context modifier contains:
# {
#     "allowed_tools": ["database", "python_sandbox"],
#     "model": "claude-sonnet-4-20250514",
#     "disable_model_invocation": False
# }
```

---

## Best Practices

### 1. Write Clear Descriptions

The `description` field is critical for semantic discovery:

❌ **Bad**: "Analyzes data"

✅ **Good**: "执行数据分析任务，包括统计计算、趋势识别和异常检测。适用于需要深入理解数据模式的场景。"

### 2. Use Progressive Disclosure

Keep frontmatter minimal, put details in instructions:

```yaml
---
name: my_skill
description: "Brief one-line description for discovery"
version: "1.0.0"
---

# Detailed Instructions

This is where the full workflow goes...
```

### 3. Specify Tool Permissions

Only request tools the skill actually needs:

```yaml
---
allowed_tools: "database,python_sandbox"  # Only what's needed
---
```

### 4. Use Categories

Group related skills:

```yaml
---
category: "Analysis"  # Or: Visualization, Reporting, Automation
---
```

### 5. Provide Examples

Help users understand when to use the skill:

```yaml
---
examples:
  - "分析GMV趋势"
  - "计算留存率"
  - "检测数据异常"
---
```

### 6. Version Your Skills

Use semantic versioning:

```yaml
---
version: "1.2.0"  # MAJOR.MINOR.PATCH
---
```

### 7. Document Resources

Let the Agent know what's available:

```markdown
## 可用资源

- **脚本**: `{baseDir}/scripts/process.py` - 数据处理脚本
- **参考**: `{baseDir}/references/api.md` - API文档
- **模板**: `{baseDir}/templates/report.json` - 报告模板
```

---

## Patterns and Examples

### Pattern 1: Read-Process-Write

```markdown
---
name: csv_transformer
description: "读取CSV文件，处理数据，写入新文件"
allowed_tools: "file_reader,python_sandbox,file_writer"
---

# CSV 数据转换

## 流程

1. **读取**: 使用 `file_reader` 读取源文件
2. **处理**: 使用 `python_sandbox` 运行 `{baseDir}/scripts/transform.py`
3. **写入**: 使用 `file_writer` 保存结果

## 示例

```python
# 使用内置脚本
import sys
sys.path.append('{baseDir}')
from scripts.transform import transform_csv

result = transform_csv(input_data)
```
```

### Pattern 2: Database Query Automation

```markdown
---
name: query_runner
description: "执行数据库查询并格式化结果"
allowed_tools: "database,python_sandbox"
---

# 数据库查询执行

## 查询模板

使用 `{baseDir}/templates/queries.sql` 中的模板。

## 格式化选项

- `table`: Markdown 表格格式
- `json`: JSON 格式
- `csv`: CSV 格式
```

### Pattern 3: Multi-Step Workflow

```markdown
---
name: report_generator
description: "完整的数据报告生成流程"
allowed_tools: "database,python_sandbox,web_reader,file_writer"
---

# 报告生成器

## 完整流程

### 1. 数据收集
使用 `database` 查询原始数据

### 2. 数据分析
使用 `{baseDir}/scripts/analyze.py` 进行分析

### 3. 数据验证
使用 `{baseDir}/scripts/validate.py` 验证结果

### 4. 报告生成
使用 `{baseDir}/templates/report.md` 生成报告

### 5. 输出保存
使用 `file_writer` 保存最终报告
```

### Pattern 4: External API Integration

```markdown
---
name: weather_fetcher
description: "获取天气数据并进行分析"
allowed_tools: "web_reader,python_sandbox"
---

# 天气数据获取

## API 端点

- 基础URL: `https://api.weather.com/v1`
- 认证: 使用配置中的 API key

## 数据处理

使用 `{baseDir}/scripts/parse_weather.py` 解析响应数据
```

### Pattern 5: Mode Command (Mutually Exclusive)

```markdown
---
name: debug_mode
description: "启用调试模式，提供详细的执行日志"
mode: true  # Shown first in skill list
allowed_tools: "file_reader,bash"
---

# 调试模式

当前处于调试模式，所有操作将输出详细日志。

## 调试输出

- 每个工具调用前打印输入
- 每个工具调用后打印输出
- 显示执行时间
- 显示错误堆栈
```

---

## Troubleshooting

### Skill Not Found

```python
# Check if skill exists
if not registry.skill_exists("my_skill"):
    print("Skill not found")
    print("Available:", registry.list_skill_names())
```

### Installation Fails

```python
try:
    skill = installer.install_from_github("owner/repo")
except SkillInstallError as e:
    print(f"Installation failed: {e}")
    # Common issues:
    # - No SKILL.md found
    # - Invalid YAML frontmatter
    # - Network errors
    # - Authentication failures
```

### Permission Errors

```python
# Check what tools a skill needs
skill = loader.load_skill_full("my_skill")
tools = skill.get_allowed_tools_list()
print(f"This skill needs: {tools}")
```

### Cache Issues

```python
# Force reload after installing/uninstalling
registry.invalidate_cache()
```

---

## Migration from Old System

If you were using the old `skill_invoker` tool:

### Before

```python
# Old way: Tool invocation
invoke_skill(
    skill_name="data_analysis",
    params={"metric": "gmv", "days": 30}
)
```

### After

```python
# New way: Context-based activation
# Agent automatically activates based on semantic matching
# No explicit invocation needed

# If you need to activate programmatically:
activator.activate_skill("data_analysis")
```

The new system:
- ✅ No explicit tool calls needed
- ✅ Skills modify Agent behavior, not just return results
- ✅ Progressive disclosure reduces token usage
- ✅ Semantic matching vs algorithmic routing

---

## Additional Resources

- [API Reference](./skills-api.md) - Complete API documentation
- [Design Document](./skill-system-redesign.md) - Architecture and design decisions
- [Anthropic Agent Skills Spec](https://agentskills.io/specification) - Official specification
