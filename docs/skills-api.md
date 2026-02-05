# Skills System API Reference

> **Version**: 1.0.0
> **Last Updated**: 2026-02-05

Complete API reference for the BA-Agent Skills system.

## Table of Contents

- [SkillLoader](#skillloader)
- [SkillRegistry](#skillregistry)
- [SkillActivator](#skillactivator)
- [SkillMessageFormatter](#skillmessageformatter)
- [SkillInstaller](#skillinstaller)
- [Data Models](#data-models)

---

## SkillLoader

Scans and loads skills from multiple source directories.

### Constructor

```python
SkillLoader(skills_dirs: List[Path])
```

**Parameters:**
- `skills_dirs`: List of directories to search for skills. Earlier directories have lower priority.

**Example:**
```python
from pathlib import Path
from backend.skills import SkillLoader

loader = SkillLoader(skills_dirs=[
    Path("skills"),              # Built-in skills
    Path(".claude/skills"),      # User-installed skills
])
```

### Methods

#### `load_all_metadata()`

Load only skill metadata (Level 1: Progressive Disclosure).

**Returns:** `Dict[str, SkillMetadata]`

**Example:**
```python
metadata_dict = loader.load_all_metadata()
# Returns: {"anomaly_detection": SkillMetadata(...), ...}
```

#### `load_skill_full(skill_name: str)`

Load full skill content (Level 2: Progressive Disclosure).

**Parameters:**
- `skill_name`: Name of the skill to load

**Returns:** `Optional[Skill]` - Complete Skill object or None if not found

**Example:**
```python
skill = loader.load_skill_full("anomaly_detection")
if skill:
    print(skill.instructions)  # Full SKILL.md content
```

#### `list_all_skills()`

List all available skill names.

**Returns:** `List[str]` - Sorted list of skill names

**Example:**
```python
skills = loader.list_all_skills()
# Returns: ["anomaly_detection", "attribution", "report_gen", ...]
```

#### `get_skill_path(skill_name: str)`

Get the path to a skill's directory.

**Parameters:**
- `skill_name`: Name of the skill

**Returns:** `Optional[Path]` - Path to skill directory, or None if not found

**Example:**
```python
path = loader.get_skill_path("anomaly_detection")
# Returns: Path("skills/anomaly_detection")
```

---

## SkillRegistry

Central registry for all available skills with caching.

### Constructor

```python
SkillRegistry(loader: SkillLoader)
```

**Parameters:**
- `loader`: SkillLoader instance for loading skills

**Example:**
```python
from backend.skills import SkillLoader, SkillRegistry

loader = SkillLoader(skills_dirs=[Path("skills")])
registry = SkillRegistry(loader)
```

### Methods

#### `get_all_metadata()`

Get all skill metadata, loading from cache if available.

**Returns:** `Dict[str, SkillMetadata]`

**Example:**
```python
metadata_dict = registry.get_all_metadata()
for name, metadata in metadata_dict.items():
    print(f"{name}: {metadata.description}")
```

#### `get_formatted_skills_list()`

Format skills for Agent's system prompt.

**Returns:** `str` - Formatted string with skill names and descriptions

**Example:**
```python
skills_list = registry.get_formatted_skills_list()
# Returns:
# "anomaly_detection: 检测数据异常波动并分析可能原因
#  attribution: 分析业务指标变化的驱动因素
#  ..."
```

#### `get_skill_metadata(skill_name: str)`

Get metadata for a specific skill.

**Parameters:**
- `skill_name`: Name of the skill

**Returns:** `Optional[SkillMetadata]` - SkillMetadata or None if not found

**Example:**
```python
metadata = registry.get_skill_metadata("anomaly_detection")
if metadata:
    print(f"Version: {metadata.version}")
    print(f"Category: {metadata.category}")
```

#### `get_skill_full(skill_name: str)`

Load full skill content.

**Parameters:**
- `skill_name`: Name of the skill to load

**Returns:** `Optional[Skill]` - Complete Skill object or None if not found

**Example:**
```python
skill = registry.get_skill_full("anomaly_detection")
if skill:
    instructions = skill.instructions
```

#### `skill_exists(skill_name: str)`

Check if a skill exists.

**Parameters:**
- `skill_name`: Name of the skill

**Returns:** `bool`

**Example:**
```python
if registry.skill_exists("anomaly_detection"):
    print("Skill is available")
```

#### `list_skill_names()`

List all available skill names.

**Returns:** `List[str]` - Sorted list of skill names

**Example:**
```python
names = registry.list_skill_names()
# Returns: ["anomaly_detection", "attribution", "report_gen", ...]
```

#### `list_mode_skills()`

List all mode command skills (shown first in skill list).

**Returns:** `List[str]`

**Example:**
```python
mode_skills = registry.list_mode_skills()
# Returns: ["code-review", "debug-mode"]
```

#### `invalidate_cache()`

Force reload of metadata on next access.

**Returns:** `None`

**Example:**
```python
# After installing/uninstalling skills
registry.invalidate_cache()
```

#### `get_skills_by_category(category: str)`

Get all skills in a specific category.

**Parameters:**
- `category`: Category name

**Returns:** `List[str]` - List of skill names in the category

**Example:**
```python
analysis_skills = registry.get_skills_by_category("Analysis")
# Returns: ["anomaly_detection", "attribution", "trend_analysis"]
```

#### `get_all_categories()`

Get all unique skill categories.

**Returns:** `List[str]` - Sorted list of category names

**Example:**
```python
categories = registry.get_all_categories()
# Returns: ["Analysis", "Visualization", "Reporting", ...]
```

#### `get_skills_info()`

Get detailed info about all skills.

**Returns:** `List[Dict[str, Any]]` - List of skill information dictionaries

**Example:**
```python
info = registry.get_skills_info()
# Returns: [
#     {"name": "anomaly_detection", "display_name": "异动检测", ...},
#     {"name": "attribution", "display_name": "归因分析", ...},
#     ...
# ]
```

---

## SkillActivator

Activate skills and inject conversation context.

### Constructor

```python
SkillActivator(loader: SkillLoader, registry: SkillRegistry)
```

**Parameters:**
- `loader`: SkillLoader instance
- `registry`: SkillRegistry instance

**Example:**
```python
from backend.skills import SkillLoader, SkillRegistry, SkillActivator

loader = SkillLoader(skills_dirs=[Path("skills")])
registry = SkillRegistry(loader)
activator = SkillActivator(loader, registry)
```

### Methods

#### `activate_skill(skill_name: str, conversation_history: Optional[List[Dict]] = None)`

Activate a skill by injecting its instructions.

**Parameters:**
- `skill_name`: Name of skill to activate
- `conversation_history`: Optional current conversation history

**Returns:** `Tuple[List[Dict[str, Any]], Dict[str, Any]]`
- `new_messages`: Messages to inject into conversation
  - Message 1 (visible): Metadata message
  - Message 2 (hidden): Full SKILL.md instructions
  - Message 3 (optional): Tool permissions
- `context_modifier`: Execution context changes
  - `allowed_tools`: Tools skill can use
  - `model`: Model override
  - `disable_model_invocation`: Prevent model invocation flag

**Raises:** `SkillActivationError` if skill not found

**Example:**
```python
try:
    messages, context = activator.activate_skill("anomaly_detection")

    # Inject messages into conversation
    for msg in messages:
        if msg.get("isMeta"):
            # Hidden instruction message
            add_to_conversation(msg, visible=False)
        else:
            # Visible metadata message
            add_to_conversation(msg, visible=True)

    # Apply context modifier
    if "allowed_tools" in context:
        grant_tool_permissions(context["allowed_tools"])

except SkillActivationError as e:
    print(f"Failed to activate skill: {e}")
```

---

## SkillMessageFormatter

Format skill-related messages for Agent consumption.

### Methods (Static)

#### `create_metadata_message(skill: Skill)`

Create visible metadata message for skill activation.

**Parameters:**
- `skill`: The skill being activated

**Returns:** `Dict[str, Any]` - Message dict with role and content

**Example:**
```python
from backend.skills import SkillMessageFormatter

msg = SkillMessageFormatter.create_metadata_message(skill)
# Returns:
# {
#     "role": "user",
#     "content": '<command-message>The "异动检测" skill is loading</command-message>\n<command-name>anomaly_detection</command-name>',
#     "isMeta": False
# }
```

#### `create_instruction_message(skill: Skill)`

Create hidden instruction message with skill content.

**Parameters:**
- `skill`: The skill being activated

**Returns:** `Dict[str, Any]` - Message dict with role and content

**Example:**
```python
msg = SkillMessageFormatter.create_instruction_message(skill)
# Returns:
# {
#     "role": "user",
#     "content": "# 异动检测分析 Skill\n\n## 描述\n\n检测数据中的异常波动...",
#     "isMeta": True
# }
```

#### `create_permissions_message(skill: Skill)`

Create tool permissions message if skill has allowed-tools.

**Parameters:**
- `skill`: The skill being activated

**Returns:** `Optional[Dict[str, Any]]` - Message dict or None if no allowed-tools

**Example:**
```python
msg = SkillMessageFormatter.create_permissions_message(skill)
if msg:
    # Returns:
    # {
    #     "role": "user",
    #     "content": {
    #         "type": "command_permissions",
    #         "allowed_tools": ["Read", "Write", "Bash(python:*)"],
    #         "model": "claude-sonnet-4-20250514"
    #     }
    # }
```

#### `create_context_modifier(skill: Skill)`

Create execution context modifier for the skill.

**Parameters:**
- `skill`: The skill being activated

**Returns:** `Dict[str, Any]` - Context modifications

**Example:**
```python
modifier = SkillMessageFormatter.create_context_modifier(skill)
# Returns:
# {
#     "allowed_tools": ["Read", "Write", "Bash(python:*)"],
#     "model": "claude-sonnet-4-20250514",
#     "disable_model_invocation": False
# }
```

#### `format_skills_list_for_prompt(skills_list: str)`

Format the skills list for the Agent's system prompt.

**Parameters:**
- `skills_list`: Formatted skills list from SkillRegistry

**Returns:** `str` - Formatted section for system prompt

**Example:**
```python
skills_list = registry.get_formatted_skills_list()
formatted = SkillMessageFormatter.format_skills_list_for_prompt(skills_list)
# Returns:
# """
# ## Available Skills
#
# 当用户请求需要特定领域知识或工作流程时，检查以下可用的 Skills：
#
# <available_skills>
# anomaly_detection: 检测数据异常波动并分析可能原因
# attribution: 分析业务指标变化的驱动因素
# ...
# </available_skills>
#
# **如何使用 Skills**：
# - Skills 提供专业化的指令和工作流程
# ...
# """
```

#### `format_skill_for_debug(skill: Skill)`

Format skill info for debug output.

**Parameters:**
- `skill`: The skill to format

**Returns:** `str` - Formatted debug string

**Example:**
```python
debug_info = SkillMessageFormatter.format_skill_for_debug(skill)
# Returns:
# """
# Skill: anomaly_detection
#   Display Name: 异动检测
#   Version: 1.0.0
#   Category: Analysis
#   Description: 检测数据中的异常波动...
#   Mode: False
#   Allowed Tools: Read,Write,Bash(python:*)
#   ...
# """
```

---

## SkillInstaller

Install and manage external skills from various sources.

### Constructor

```python
SkillInstaller(install_dir: Path, cache_dir: Optional[Path] = None)
```

**Parameters:**
- `install_dir`: Directory where skills are installed (e.g., `.claude/skills/`)
- `cache_dir`: Optional directory for caching git clones (default: `~/.cache/ba-skills`)

**Example:**
```python
from pathlib import Path
from backend.skills import SkillInstaller

installer = SkillInstaller(
    install_dir=Path(".claude/skills"),
    cache_dir=Path.home() / ".cache" / "ba-skills"
)
```

### Methods

#### `install_from_github(repo, subdirectory=None, ref=None, auth_token=None)`

Install skill from GitHub repository.

**Parameters:**
- `repo`: Repository in "owner/repo" format
- `subdirectory`: Optional path within repo
- `ref`: Branch or tag (default: "main")
- `auth_token`: Optional GitHub PAT for private repos

**Returns:** `Skill` - Installed Skill object

**Raises:** `SkillInstallError` if installation fails

**Example:**
```python
# Install from GitHub
skill = installer.install_from_github("anthropics/skills", subdirectory="sql-analyzer")

# Install specific version
skill = installer.install_from_github("owner/repo", ref="v1.2.0")

# Install from private repo
skill = installer.install_from_github(
    "owner/private-repo",
    auth_token="ghp_xxx"
)
```

#### `install_from_git_url(url, ref=None, auth_token=None)`

Install skill from any git URL.

**Parameters:**
- `url`: Git clone URL
- `ref`: Optional branch or tag
- `auth_token`: Optional auth token

**Returns:** `Skill` - Installed Skill object

**Raises:** `SkillInstallError` if installation fails

**Example:**
```python
# Install from GitLab
skill = installer.install_from_git_url("https://gitlab.com/owner/skill.git")

# Install specific branch
skill = installer.install_from_git_url("https://github.com/owner/repo.git", ref="develop")
```

#### `install_from_zip(zip_path)`

Install skill from ZIP archive.

**Parameters:**
- `zip_path`: Path to ZIP file

**Returns:** `Skill` - Installed Skill object

**Raises:** `SkillInstallError` if installation fails

**Example:**
```python
skill = installer.install_from_zip(Path("my-skill.zip"))
```

#### `uninstall(skill_name, remove_files=True)`

Uninstall a skill.

**Parameters:**
- `skill_name`: Name of skill to uninstall
- `remove_files`: Whether to delete files (default: True)

**Raises:** `SkillInstallError` if skill is not found

**Example:**
```python
installer.uninstall("sql-analyzer")
```

#### `update(skill_name, current_ref=None)`

Update an installed skill from its source.

**Parameters:**
- `skill_name`: Name of skill to update
- `current_ref`: Current branch/tag (for validation)

**Returns:** `Skill` - Updated Skill object

**Raises:** `SkillInstallError` if skill not found or update fails

**Example:**
```python
skill = installer.update("sql-analyzer")
```

#### `list_installed()`

List all installed skills.

**Returns:** `List[Dict[str, Any]]` - List of skill information dictionaries

**Example:**
```python
installed = installer.list_installed()
# Returns:
# [
#     {"name": "sql-analyzer", "display_name": "SQL Analyzer", ...},
#     {"name": "chart-gen", "display_name": "Chart Generator", ...},
#     ...
# ]
```

---

## Data Models

### SkillFrontmatter

YAML frontmatter parsed from SKILL.md files.

**Fields:**
- `name` (str): Skill name (lowercase, underscores or hyphens)
- `display_name` (Optional[str]): Human-readable display name
- `description` (str): What the skill does AND when to use it
- `version` (str): Skill version (default: "1.0.0")
- `category` (Optional[str]): Skill category for grouping
- `author` (Optional[str]): Author name or team
- `license` (Optional[str]): License identifier
- `entrypoint` (Optional[str]): Path to main.py entrypoint file
- `function` (Optional[str]): Function name to call (default: "main")
- `requirements` (List[str]): Python package requirements
- `allowed_tools` (Optional[str]): Comma-separated list of tools
- `model` (Optional[str]): Model override for this skill
- `disable_model_invocation` (bool): Prevent skill from invoking model
- `mode` (bool): Is this a mode command (shown first)
- `tags` (List[str]): Tags for categorization and search
- `examples` (List[str]): Example user queries

### SkillMetadata

Minimal metadata loaded at startup (~100 tokens per skill).

**Fields:**
- `name` (str): Skill name
- `description` (str): Description
- `path` (Path): Path to SKILL.md
- `version` (str): Version
- `category` (Optional[str]): Category
- `is_mode` (bool): Mode command flag
- `display_name` (Optional[str]): Human-readable name

### Skill

Complete skill with all content.

**Fields:**
- `metadata` (SkillFrontmatter): Frontmatter data
- `instructions` (str): Markdown content from SKILL.md
- `base_dir` (Path): Directory containing SKILL.md

**Properties:**
- `scripts_dir` (Path): Path to scripts directory
- `references_dir` (Path): Path to references directory
- `assets_dir` (Path): Path to assets directory

**Methods:**
- `has_scripts()` (bool): Check if skill has scripts directory
- `has_references()` (bool): Check if skill has references directory
- `has_assets()` (bool): Check if skill has assets directory
- `get_allowed_tools_list()` (Optional[List[str]]): Parse allowed_tools into list

### SkillSourceInfo

Information about where a skill was installed from.

**Fields:**
- `source_type` (str): "local", "github", "git_url", or "zip"
- `location` (str): Source location (repo path, URL, or local path)
- `subdirectory` (Optional[str]): Subdirectory within source
- `ref` (Optional[str]): Branch/tag reference
- `sha` (Optional[str]): Commit SHA for pinned version
- `installed_at` (str): ISO timestamp of installation

## Exceptions

### SkillLoadError

Base exception for skill loading errors.

### InvalidSkillError

Raised when a skill file is invalid (subclass of SkillLoadError).

### SkillActivationError

Raised when skill activation fails.

### SkillInstallError

Raised when skill installation fails.

## Usage Examples

### Basic Usage

```python
from pathlib import Path
from backend.skills import (
    SkillLoader,
    SkillRegistry,
    SkillActivator,
    SkillMessageFormatter,
)

# Initialize
loader = SkillLoader(skills_dirs=[Path("skills")])
registry = SkillRegistry(loader)
activator = SkillActivator(loader, registry)

# List skills
for name in registry.list_skill_names():
    metadata = registry.get_skill_metadata(name)
    print(f"{name}: {metadata.description}")

# Activate a skill
messages, context = activator.activate_skill("anomaly_detection")

# Use the messages
for msg in messages:
    print(msg["content"])
```

### Installing External Skills

```python
from pathlib import Path
from backend.skills import SkillInstaller, SkillInstallError

installer = SkillInstaller(install_dir=Path(".claude/skills"))

try:
    # Install from GitHub
    skill = installer.install_from_github(
        "anthropics/skills",
        subdirectory="sql-analyzer"
    )
    print(f"Installed: {skill.metadata.name}")

    # List installed
    for skill_info in installer.list_installed():
        print(f"- {skill_info['name']}")

except SkillInstallError as e:
    print(f"Installation failed: {e}")
```

### Creating a Custom Skill

```markdown
---
name: my_custom_skill
display_name: "My Custom Skill"
description: "Does something specific"
version: "1.0.0"
category: "Custom"
allowed_tools: Read,Write
model: claude-sonnet-4-20250514
tags:
  - custom
  - automation
---

# My Custom Skill

This skill does something specific.

## Usage

1. Read the input
2. Process the data
3. Write the output
```
