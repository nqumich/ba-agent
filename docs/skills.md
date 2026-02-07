# BA-Agent Skills 系统

> **Version**: 2.1.0
> **Status**: ✅ Implementation Complete
> **Last Updated**: 2026-02-07

完整的 BA-Agent Skills 系统指南，涵盖架构设计、API 参考、使用指南和最佳实践。

---

## 目录

- [概述](#概述)
- [架构设计](#架构设计)
- [快速开始](#快速开始)
- [创建 Skill](#创建-skill)
- [API 参考](#api-参考)
- [使用指南](#使用指南)
- [最佳实践](#最佳实践)

---

## 概述

BA-Agent Skills 系统实现了 **Anthropic Agent Skills 开放标准**，Skills 是**指令包**，通过上下文注入来修改 Agent 行为，而非函数执行。

### 核心特性

| 特性 | 说明 |
|------|------|
| **渐进式加载** | 三级加载（metadata → instructions → resources） |
| **语义发现** | Agent 基于描述匹配选择 Skills |
| **上下文修改** | Skills 注入指令并修改工具权限 |
| **开放标准** | 兼容 Claude Code 的 skills 格式 |

### 实现状态

| Phase | 状态 | 说明 |
|-------|------|------|
| **Phase 1: 核心基础设施** | ✅ 完成 | SkillLoader, SkillRegistry, models (55 tests) |
| **Phase 2: 激活系统** | ✅ 完成 | SkillActivator, BAAgent 集成 (17 tests) |
| **Phase 2.5: 外部 Skills** | ✅ 完成 | SkillInstaller - GitHub/git/ZIP (16 tests) |
| **Phase 3: 工具废弃** | ✅ 完成 | 移除旧的 skill_invoker/skill_manager |
| **Phase 4: 测试与文档** | ✅ 完成 | 集成测试、文档 (24 tests) |
| **Phase 5: 消息注入** | ✅ 完成 | Meta-tool 实现 (14 tests) |

**总计**: 126 个 skills 测试

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BAAgent                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Tools Array:                                                   │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ activate_skill (Meta-Tool)                               │  │   │
│  │  │  - Description: 所有 Skills 列表                          │  │   │
│  │  │  - Returns: SkillActivationResult                        │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ other_tool                                               │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Message Injection:                                             │   │
│  │  1. 检查 activate_skill 是否被调用                              │   │
│  │  2. 从响应中提取 SkillActivationResult                           │   │
│  │  3. 将消息注入到对话状态中                                      │   │
│  │  4. 应用 context_modifier（工具权限、模型覆盖）                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 组件关系

```
SkillLoader (发现和加载)
    ↓
SkillRegistry (元数据注册表)
    ↓
SkillActivator (激活和注入)
    ↓
SkillMessageFormatter (消息格式化)
```

---

## 快速开始

### 安装

Skills 系统已集成在 BA-Agent 中，无需额外安装。

### 基本使用

```python
from pathlib import Path
from backend.skills import (
    SkillLoader,
    SkillRegistry,
    SkillActivator,
)

# 初始化
loader = SkillLoader(skills_dirs=[Path("skills")])
registry = SkillRegistry(loader)
activator = SkillActivator(loader, registry)

# 列出所有 Skills
for name in registry.list_skill_names():
    metadata = registry.get_skill_metadata(name)
    print(f"{name}: {metadata.description}")

# 激活一个 Skill
try:
    messages, context = activator.activate_skill("anomaly_detection")

    # 处理消息
    for msg in messages:
        if msg.get("isMeta"):
            # 隐藏指令消息
            add_hidden_message(msg)
        else:
            # 可见元数据消息
            add_message(msg)

    # 应用上下文修改
    if "allowed_tools" in context:
        grant_tool_permissions(context["allowed_tools"])

except Exception as e:
    print(f"激活失败: {e}")
```

---

## 创建 Skill

### Skill 目录结构

```
skills/my_skill/
├── SKILL.md              # 必需: Skill 定义
├── main.py              # 可选: 入口函数
├── scripts/             # 可选: 自动化脚本
│   └── process.py
├── references/          # 可选: 文档
│   └── api_reference.md
└── assets/              # 可选: 模板、配置
    └── template.json
```

### SKILL.md 格式

#### 示例：数据分析 Skill

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

使用 `database` 工具查询数据。

### Step 3: 数据分析

使用 `python_sandbox` 执行分析，可使用内置脚本：
```python
import sys
sys.path.append('{baseDir}')
from scripts.analysis import analyze_data

result = analyze_data(data)
```

### Step 4: 结果呈现

生成结构化报告。

## 可用资源

- **脚本**: `{baseDir}/scripts/analysis.py` - 统计分析函数
- **参考**: `{baseDir}/references/methods.md` - 统计方法说明
```

### Frontmatter 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | Skill 标识符（小写，下划线/连字符） |
| `display_name` | string | - | 人类可读名称 |
| `description` | string | ✅ | 功能描述 + 使用场景（最多 500 字符） |
| `version` | string | - | 语义版本（默认 "1.0.0"） |
| `category` | string | - | 分类（用于分组） |
| `author` | string | - | 作者或团队 |
| `entrypoint` | string | - | main.py 路径 |
| `function` | string | - | 函数名（默认 "main"） |
| `requirements` | list | - | Python 包依赖 |
| `allowed_tools` | string | - | 逗号分隔的工具列表 |
| `model` | string | - | 模型覆盖 |
| `disable_model_invocation` | boolean | - | 禁止模型自我调用 |
| `mode` | boolean | - | 模式命令（优先显示） |
| `tags` | list | - | 搜索标签 |
| `examples` | list | - | 示例查询 |

---

## API 参考

### SkillLoader

发现和加载 Skills 的类。

```python
SkillLoader(skills_dirs: List[Path])
```

**方法**:
- `load_all_metadata() -> Dict[str, SkillMetadata]` - 加载所有元数据（Level 1）
- `load_skill_full(skill_name: str) -> Optional[Skill]` - 加载完整 Skill（Level 2）
- `list_all_skills() -> List[str]` - 列出所有 Skill 名称
- `get_skill_path(skill_name: str) -> Optional[Path]` - 获取 Skill 目录路径

### SkillRegistry

Skills 中央注册表，带缓存。

```python
SkillRegistry(loader: SkillLoader)
```

**方法**:
- `get_all_metadata() -> Dict[str, SkillMetadata]` - 获取所有元数据
- `get_formatted_skills_list() -> str` - 格式化用于 Agent 提示词
- `get_skill_metadata(skill_name: str) -> Optional[SkillMetadata]` - 获取特定元数据
- `get_skill_full(skill_name: str) -> Optional[Skill]` - 加载完整 Skill
- `skill_exists(skill_name: str) -> bool` - 检查 Skill 是否存在
- `list_skill_names() -> List[str]` - 列出所有名称
- `list_mode_skills() -> List[str]` - 列出模式命令
- `invalidate_cache()` - 强制重新加载
- `get_skills_by_category(category: str) -> List[str]` - 按分类获取
- `get_all_categories() -> List[str]` - 获取所有分类

### SkillActivator

激活 Skills 并注入对话上下文。

```python
SkillActivator(loader: SkillLoader, registry: SkillRegistry)
```

**方法**:
```python
activate_skill(
    skill_name: str,
    conversation_history: Optional[List[Dict]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]
```

**返回**:
- `new_messages`: 要注入到对话的消息列表
  - Message 1 (可见): 元数据消息
  - Message 2 (隐藏): 完整的 SKILL.md 指令
  - Message 3 (可选): 工具权限
- `context_modifier`: 执行上下文修改
  - `allowed_tools`: Skill 可用的工具
  - `model`: 模型覆盖
  - `disable_model_invocation`: 禁止模型调用标志

### SkillMessageFormatter

格式化 Skill 相关消息。

**静态方法**:
- `create_metadata_message(skill: Skill) -> Dict` - 创建可见元数据消息
- `create_instruction_message(skill: Skill) -> Dict` - 创建隐藏指令消息
- `create_permissions_message(skill: Skill) -> Optional[Dict]` - 创建工具权限消息
- `create_context_modifier(skill: Skill) -> Dict` - 创建上下文修改器
- `format_skills_list_for_prompt(skills_list: str) -> str` - 格式化用于系统提示词
- `format_skill_for_debug(skill: Skill) -> str` - 格式化调试信息

### SkillInstaller

从各种来源安装和管理外部 Skills。

```python
SkillInstaller(
    install_dir: Path,
    cache_dir: Optional[Path] = None
)
```

**方法**:
```python
# 从 GitHub 安装
install_from_github(
    repo: str,              # "owner/repo"
    subdirectory: Optional[str] = None,
    ref: Optional[str] = None,  # branch or tag
    auth_token: Optional[str] = None
) -> Skill

# 从 Git URL 安装
install_from_git_url(
    url: str,
    ref: Optional[str] = None,
    auth_token: Optional[str] = None
) -> Skill

# 从 ZIP 安装
install_from_zip(zip_path: Path) -> Skill

# 卸载
uninstall(skill_name: str, remove_files: bool = True)

# 更新
update(skill_name: str, current_ref: Optional[str] = None) -> Skill

# 列出已安装
list_installed() -> List[Dict[str, Any]]
```

### 数据模型

#### SkillFrontmatter
从 SKILL.md 解析的 YAML frontmatter。

#### SkillMetadata
启动时加载的最小元数据（每个 Skill ~100 tokens）。

#### Skill
包含所有内容的完整 Skill。

#### SkillSourceInfo
Skill 安装来源信息。

### 异常

- `SkillLoadError` - 加载错误基类
- `InvalidSkillError` - 无效的 Skill 文件
- `SkillActivationError` - 激活失败
- `SkillInstallError` - 安装失败

---

## 使用指南

### 激活 Skills

#### 直接激活

```python
from pathlib import Path
from backend.skills import (
    SkillLoader, SkillRegistry, SkillActivator
)

loader = SkillLoader(skills_dirs=[Path("skills")])
registry = SkillRegistry(loader)
activator = SkillActivator(loader, registry)

try:
    messages, context = activator.activate_skill("data_analysis")

    # 注入消息到对话
    for msg in messages:
        if msg.get("isMeta"):
            # 隐藏指令消息
            add_to_conversation(msg, visible=False)
        else:
            # 可见元数据消息
            add_to_conversation(msg, visible=True)

    # 应用上下文修改
    if "allowed_tools" in context:
        grant_tool_permissions(context["allowed_tools"])

    if "model" in context:
        switch_model(context["model"])

except SkillActivationError as e:
    print(f"激活失败: {e}")
```

#### BAAgent 集成

BAAgent 类内置了 Skills 集成：

```python
from backend.agents import BAAgent

# 初始化 Agent（Skills 系统自动初始化）
agent = BAAgent(app_config=...)

# Skills 自动发现，描述包含在系统提示词中
# Agent 可以基于语义匹配激活 Skills
```

### 安装外部 Skills

#### 从 GitHub

```python
from pathlib import Path
from backend.skills import SkillInstaller

installer = SkillInstaller(install_dir=Path(".claude/skills"))

# 从 GitHub 安装
skill = installer.install_from_github(
    repo="anthropics/skills",
    subdirectory="sql-analyzer"
)

# 安装特定版本
skill = installer.install_from_github(
    repo="owner/repo",
    ref="v1.2.0"
)

# 从私有仓库安装
skill = installer.install_from_github(
    repo="owner/private-repo",
    auth_token="ghp_xxx"
)
```

#### 从 Git URL

```python
# 从 GitLab 安装
skill = installer.install_from_git_url(
    "https://gitlab.com/owner/skill.git"
)

# 安装特定分支
skill = installer.install_from_git_url(
    "https://github.com/owner/repo.git",
    ref="develop"
)
```

#### 从 ZIP

```python
skill = installer.install_from_zip(Path("my-skill.zip"))
```

#### 管理已安装的 Skills

```python
# 列出已安装
for skill_info in installer.list_installed():
    print(f"- {skill_info['name']} v{skill_info['version']}")

# 更新
updated_skill = installer.update("sql-analyzer")

# 卸载
installer.uninstall("sql-analyzer", remove_files=True)
```

### 管理 Skill 权限

#### 授予工具访问

Skills 可以使用 `allowed_tools` 预先批准工具：

```yaml
---
name: data_export
allowed_tools: "database,python_sandbox,file_writer"
---
```

#### 权限格式

```yaml
# 单个工具
allowed_tools: "database"

# 多个工具（逗号分隔）
allowed_tools: "database,python_sandbox,file_writer"

# 带参数的工具
allowed_tools: "Bash(python:*),Read(*.csv),Write(data/*.json)"
```

#### 模型覆盖

```yaml
---
name: complex_analysis
model: claude-opus-4-20250514  # 使用更强大的模型
---
```

#### 禁止模型调用

```yaml
---
name: automated_report
disable_model_invocation: true  # Skill 直接处理执行
---
```

---

## 最佳实践

### 1. 编写清晰的描述

`description` 字段对语义发现至关重要：

❌ **不好**: "Analyzes data"

✅ **好**: "执行数据分析任务，包括统计计算、趋势识别和异常检测。适用于需要深入理解数据模式的场景。"

### 2. 使用渐进式加载

保持 frontmatter 最小化，详细信息放在指令中：

```yaml
---
name: my_skill
description: "简短的一行描述用于发现"
version: "1.0.0"
---

# 详细指令

这里是完整的工作流程...
```

### 3. 指定工具权限

只请求 Skill 实际需要的工具：

```yaml
---
allowed_tools: "database,python_sandbox"  # 只需要的
---
```

### 4. 使用分类

将相关的 Skills 分组：

```yaml
---
category: "Analysis"  # 或: Visualization, Reporting, Automation
---
```

### 5. 提供示例

帮助用户理解何时使用 Skill：

```yaml
---
examples:
  - "分析GMV趋势"
  - "计算留存率"
  - "检测数据异常"
---
```

### 6. 版本控制

使用语义版本：

```yaml
---
version: "1.2.0"  # MAJOR.MINOR.PATCH
---
```

### 7. 文档化资源

让 Agent 知道可用的资源：

```markdown
## 可用资源

- **脚本**: `{baseDir}/scripts/process.py` - 数据处理脚本
- **参考**: `{baseDir}/references/api.md` - API文档
- **模板**: `{baseDir}/templates/report.json` - 报告模板
```

---

## 常见模式

### 模式 1: 读取-处理-写入

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
```

### 模式 2: 数据库查询自动化

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

### 模式 3: 多步骤工作流

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

### 模式 4: 外部 API 集成

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

### 模式 5: 模式命令（互斥）

```markdown
---
name: debug_mode
description: "启用调试模式，提供详细的执行日志"
mode: true  # 在 Skill 列表中优先显示
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

## 故障排除

### Skill 未找到

```python
# 检查 Skill 是否存在
if not registry.skill_exists("my_skill"):
    print("Skill 未找到")
    print("可用的:", registry.list_skill_names())
```

### 安装失败

```python
try:
    skill = installer.install_from_github("owner/repo")
except SkillInstallError as e:
    print(f"安装失败: {e}")
    # 常见问题:
    # - 未找到 SKILL.md
    # - 无效的 YAML frontmatter
    # - 网络错误
    # - 认证失败
```

### 权限错误

```python
# 检查 Skill 需要什么工具
skill = loader.load_skill_full("my_skill")
tools = skill.get_allowed_tools_list()
print(f"此 Skill 需要: {tools}")
```

### 缓存问题

```python
# 在安装/卸载后强制重新加载
registry.invalidate_cache()
```

---

## 从旧系统迁移

如果您之前使用旧的 `skill_invoker` 工具：

### 之前

```python
# 旧方式: 工具调用
invoke_skill(
    skill_name="data_analysis",
    params={"metric": "gmv", "days": 30}
)
```

### 之后

```python
# 新方式: 基于上下文的激活
# Agent 基于语义匹配自动激活
# 无需显式调用

# 如果需要编程方式激活:
activator.activate_skill("data_analysis")
```

新系统的优势：
- ✅ 无需显式工具调用
- ✅ Skills 修改 Agent 行为，不只是返回结果
- ✅ 渐进式加载减少 token 使用
- ✅ 语义匹配 vs 算法路由

---

## 相关文档

- [architecture.md](architecture.md) - 完整技术架构
- [implementation.md](implementation.md) - 实现方案详情
- [development.md](development.md) - 开发指南
- [Anthropic Agent Skills Spec](https://agentskills.io/specification) - 官方规范
