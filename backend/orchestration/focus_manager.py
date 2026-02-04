"""
BA-Agent Focus Manager

基于 Manus AI 的注意力操控机制：

- 定期重新读取计划文件
- 避免目标漂移 (Goal Drift)
- 上下文压缩和恢复
- 状态持久化
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class FocusManager:
    """
    焦点管理器

    核心功能：
    1. 定期重新聚焦 (每 N 步重新读取计划)
    2. 上下文注入 (将目标推送到上下文末尾)
    3. 进度追踪 (更新任务计划)
    4. 状态持久化 (保存到文件)
    """

    def __init__(
        self,
        workspace: str = ".",
        plan_file: str = "task_plan.md",
        findings_file: str = "findings.md",
        progress_file: str = "progress.md",
        refocus_interval: int = 5
    ):
        """
        初始化焦点管理器

        Args:
            workspace: 工作目录
            plan_file: 任务计划文件
            findings_file: 研究发现文件
            progress_file: 进度文件
            refocus_interval: 重新聚焦间隔 (步数)
        """
        self.workspace = Path(workspace)
        self.plan_file = self.workspace / plan_file
        self.findings_file = self.workspace / findings_file
        self.progress_file = self.workspace / progress_file
        self.refocus_interval = refocus_interval

        self.step_count = 0
        self.context_messages: List[str] = []

    def maintain_focus(self) -> Optional[str]:
        """
        维持焦点 - 每 N 步重新读取计划

        Returns:
            如果需要重新聚焦，返回焦点消息；否则返回 None
        """
        self.step_count += 1

        # 检查是否需要重新聚焦
        if self.step_count % self.refocus_interval == 0:
            return self._refocus()

        return None

    def _refocus(self) -> str:
        """
        重新聚焦 - 读取计划并生成焦点消息

        Returns:
            焦点消息
        """
        # 读取任务计划
        plan_content = self._read_plan()

        # 生成焦点消息
        focus_message = f"""
# Current Focus (Step {self.step_count})

{plan_content}

Remember to stay focused on the current task and avoid getting sidetracked.
"""

        # 记录到上下文消息
        self.context_messages.append(focus_message)

        return focus_message

    def _read_plan(self) -> str:
        """读取任务计划"""
        if self.plan_file.exists():
            with open(self.plan_file, 'r') as f:
                return f.read()
        else:
            return "# No active plan"

    def update_plan(self, phases: List[str], completed: List[str]) -> bool:
        """
        更新任务计划

        Args:
            phases: 所有阶段列表
            completed: 已完成的阶段列表

        Returns:
            是否更新成功
        """
        try:
            content = f"# BA-Agent 任务计划\n\n"
            content += f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

            content += "## 📋 总体目标\n\n"
            content += "构建一个完整的商业分析助手 Agent。\n\n"

            content += "## 🎯 当前进度\n\n"

            for phase in phases:
                if phase in completed:
                    content += f"- [x] {phase}\n"
                else:
                    content += f"- [ ] {phase}\n"

            content += f"\n---\n\n**最后更新**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

            # 写入文件
            self.plan_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.plan_file, 'w') as f:
                f.write(content)

            return True

        except Exception as e:
            print(f"Warning: Failed to update plan: {e}")
            return False

    def add_finding(self, finding: str) -> bool:
        """
        添加研究发现

        Args:
            finding: 研究发现内容

        Returns:
            是否添加成功
        """
        try:
            # 读取现有内容
            existing_content = ""
            if self.findings_file.exists():
                with open(self.findings_file, 'r') as f:
                    existing_content = f.read()

            # 添加新发现
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            new_entry = f"\n## {timestamp}\n\n{finding}\n"

            # 写入文件
            self.findings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.findings_file, 'w') as f:
                f.write(existing_content + new_entry)

            return True

        except Exception as e:
            print(f"Warning: Failed to add finding: {e}")
            return False

    def log_progress(self, action: str, result: str) -> bool:
        """
        记录进度

        Args:
            action: 执行的动作
            result: 执行结果

        Returns:
            是否记录成功
        """
        try:
            # 读取现有内容
            existing_content = ""
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    existing_content = f.read()

            # 添加新进度
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            new_entry = f"\n### {timestamp} - {action}\n\n{result}\n"

            # 写入文件
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.progress_file, 'w') as f:
                f.write(existing_content + new_entry)

            return True

        except Exception as e:
            print(f"Warning: Failed to log progress: {e}")
            return False

    def get_context_messages(self) -> List[str]:
        """获取所有上下文消息"""
        return self.context_messages

    def clear_context_messages(self):
        """清除上下文消息"""
        self.context_messages = []

    def get_step_count(self) -> int:
        """获取当前步数"""
        return self.step_count

    def reset(self):
        """重置焦点管理器"""
        self.step_count = 0
        self.context_messages = []


# 上下文压缩和恢复策略
class ContextCompressor:
    """
    上下文压缩器

    用于压缩长上下文，同时保留恢复能力
    """

    @staticmethod
    def compress_context(context_items: List[Dict]) -> List[Dict]:
        """
        压缩上下文

        策略：
        - 保留 URL 和路径 (可通过工具恢复)
        - 压缩长文本内容
        - 保留最近的项目完整

        Args:
            context_items: 上下文项目列表

        Returns:
            压缩后的上下文
        """
        compressed = []

        for item in context_items:
            if item.get("type") == "webpage":
                # 保留 URL，内容可通过 web_reader 恢复
                compressed.append({
                    "type": "webpage",
                    "url": item.get("url"),
                    "compressed": True
                })

            elif item.get("type") == "file":
                # 保留路径，内容可通过 read_file 恢复
                compressed.append({
                    "type": "file",
                    "path": item.get("path"),
                    "compressed": True
                })

            elif item.get("type") == "tool_result":
                # 压缩长结果
                result = item.get("result", "")
                if len(result) > 1000:
                    compressed.append({
                        "type": "tool_result",
                        "tool": item.get("tool"),
                        "preview": result[:500],
                        "compressed": True
                    })
                else:
                    compressed.append(item)

            else:
                # 保留其他项目
                compressed.append(item)

        return compressed

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        估算 token 数量

        Args:
            text: 输入文本

        Returns:
            估算的 token 数量
        """
        # 粗略估算：英文约 4 字符/token，中文约 2 字符/token
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        return (chinese_chars // 2) + (other_chars // 4)
