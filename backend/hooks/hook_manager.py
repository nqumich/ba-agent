"""
BA-Agent Hooks Manager

基于 Claude Code Hooks 的系统：

- PreToolUse: 工具调用前的检查和上下文注入
- PostToolUse: 工具调用后的日志和状态更新
- Stop: 会话结束时的验证和清理
- UserPromptSubmit: 用户输入验证

Hooks 可以：
- 阻止操作 (block: true)
- 修改输入/输出
- 记录日志
- 触发副作用
"""

import json
import subprocess
from enum import Enum
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass


class HookEvent(Enum):
    """Hook 事件类型"""
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    NOTIFICATION = "Notification"
    PRE_COMPACT = "PreCompact"


@dataclass
class HookConfig:
    """Hook 配置"""
    event: HookEvent
    matcher: Dict[str, Any]  # 匹配条件，如 {"tool_name": ["run_python"]}
    script: str  # Hook 脚本路径
    description: str  # 描述


@dataclass
class HookContext:
    """Hook 上下文"""
    event: HookEvent
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    tool_result: Optional[Any] = None
    user_input: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[Dict] = None


@dataclass
class HookResult:
    """Hook 执行结果"""
    blocked: bool  # 是否阻止操作
    reason: Optional[str] = None  # 阻止原因
    modified_input: Optional[Dict] = None  # 修改后的输入
    extra: Optional[Dict] = None  # 额外信息


class HookManager:
    """
    Hooks 管理器

    负责加载、执行和管理所有 Hooks
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 Hooks 管理器

        Args:
            config_path: Hooks 配置文件路径 (默认: .claude/hooks.json)
        """
        if config_path is None:
            config_path = ".claude/hooks.json"

        self.config_path = Path(config_path)
        self.hooks: Dict[HookEvent, List[HookConfig]] = {
            event: [] for event in HookEvent
        }
        self.hook_results: List[Dict] = []

        # 加载配置
        if self.config_path.exists():
            self._load_hooks()

    def _load_hooks(self):
        """从配置文件加载 Hooks"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            for hook_config in config.get("hooks", []):
                event = HookEvent(hook_config["eventName"])
                hook = HookConfig(
                    event=event,
                    matcher=hook_config.get("matcher", {}),
                    script=hook_config["hook"],
                    description=hook_config.get("description", "")
                )
                self.hooks[event].append(hook)

        except Exception as e:
            print(f"Warning: Failed to load hooks config: {e}")

    def trigger(
        self,
        event: HookEvent,
        context: HookContext
    ) -> HookResult:
        """
        触发特定事件的所有 Hooks

        Args:
            event: 事件类型
            context: Hook 上下文

        Returns:
            Hook 执行结果
        """
        hooks = self.hooks.get(event, [])
        result = HookResult(blocked=False)

        for hook in hooks:
            # 检查匹配条件
            if not self._matches(hook.matcher, context):
                continue

            # 执行 Hook
            hook_result = self._execute_hook(hook, context)

            # 记录结果
            self.hook_results.append({
                "hook": hook.description,
                "event": event.value,
                "result": hook_result,
                "timestamp": self._get_timestamp()
            })

            # 如果 Hook 阻止了操作，立即返回
            if hook_result.get("blocked", False):
                return HookResult(
                    blocked=True,
                    reason=hook_result.get("reason"),
                    extra=hook_result.get("extra")
                )

        return result

    def _matches(self, matcher: Dict, context: HookContext) -> bool:
        """
        检查上下文是否匹配匹配条件

        Args:
            matcher: 匹配条件
            context: Hook 上下文

        Returns:
            是否匹配
        """
        if not matcher:
            return True

        # 检查 tool_name
        if "toolName" in matcher:
            allowed_tools = matcher["toolName"]
            if context.tool_name not in allowed_tools:
                return False

        return True

    def _execute_hook(self, hook: HookConfig, context: HookContext) -> Dict:
        """
        执行 Hook 脚本

        Args:
            hook: Hook 配置
            context: Hook 上下文

        Returns:
            Hook 执行结果
        """
        try:
            # 构建输入 JSON
            input_data = {
                "event": context.event.value,
                "toolName": context.tool_name,
                "toolArgs": context.tool_args,
                "result": str(context.tool_result) if context.tool_result else None,
                "userInput": context.user_input,
                "sessionId": context.session_id,
                **(context.extra or {})
            }

            # 执行脚本
            result = subprocess.run(
                hook.script,
                input=json.dumps(input_data),
                capture_output=True,
                text=True,
                shell=True,
                timeout=30  # 30秒超时
            )

            # 解析输出
            if result.stdout:
                return json.loads(result.stdout)
            else:
                return {"blocked": False}

        except subprocess.TimeoutExpired:
            return {"blocked": True, "reason": "Hook execution timeout"}
        except json.JSONDecodeError:
            return {"blocked": False}
        except Exception as e:
            print(f"Warning: Hook execution failed: {e}")
            return {"blocked": False}

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_history(self) -> List[Dict]:
        """获取 Hook 执行历史"""
        return self.hook_results

    def clear_history(self):
        """清除 Hook 执行历史"""
        self.hook_results = []


# 预定义的 Hook 模板
HOOK_TEMPLATES = {
    "pre_tool_use_permission": {
        "eventName": "PreToolUse",
        "matcher": {
            "toolName": ["execute_command", "run_python"]
        },
        "hook": "bash .claude/hooks/check-permissions.sh",
        "description": "检查执行权限"
    },
    "pre_tool_use_path_check": {
        "eventName": "PreToolUse",
        "matcher": {
            "toolName": ["write", "edit", "create"]
        },
        "hook": "bash .claude/hooks/check-path-whitelist.sh",
        "description": "检查路径白名单"
    },
    "post_tool_use_log": {
        "eventName": "PostToolUse",
        "matcher": {
            "toolName": ["invoke_skill"]
        },
        "hook": "bash .claude/hooks/log-skill-execution.sh",
        "description": "记录 Skill 执行"
    },
    "stop_check_completion": {
        "eventName": "Stop",
        "hook": "bash .claude/hooks/check-completion.sh",
        "description": "检查任务完成度"
    }
}
