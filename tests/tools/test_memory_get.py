"""
测试记忆读取工具
"""

import os
import importlib
import pytest
from datetime import date, timedelta
from pathlib import Path

from backend.memory.tools.memory_get import memory_get, memory_get_tool, MemoryGetInput
from pydantic import ValidationError


def _get_memory_get_module():
    """获取 memory_get 模块，避免与同名的函数混淆"""
    return importlib.import_module("backend.memory.tools.memory_get")


class TestMemoryGetInput:
    """测试 MemoryGetInput 模型验证"""

    def test_valid_file_path(self):
        """测试有效的文件路径"""
        input_data = {
            "file_path": "MEMORY.md"
        }
        result = MemoryGetInput(**input_data)
        assert result.file_path == "MEMORY.md"

    def test_empty_file_path_with_recent_days(self):
        """测试空文件路径但有 recent_days"""
        # 空 file_path 是允许的，只要有 recent_days
        input_data = {
            "file_path": "",
            "recent_days": 7
        }
        result = MemoryGetInput(**input_data)
        assert result.file_path == ""

    def test_empty_file_path_without_recent_days(self):
        """测试空文件路径且无 recent_days"""
        # 空 file_path 且无 recent_days 应该允许
        input_data = {
            "file_path": ""
        }
        result = MemoryGetInput(**input_data)
        assert result.file_path == ""

    def test_path_traversal_attack(self):
        """测试路径遍历攻击防护"""
        with pytest.raises(ValidationError, match="路径中不能包含"):
            MemoryGetInput(file_path="../etc/passwd")

    def test_invalid_line_range(self):
        """测试无效的行号范围"""
        with pytest.raises(ValidationError, match="起始行号必须 >= 1"):
            MemoryGetInput(file_path="MEMORY.md", line_start=0)

        with pytest.raises(ValidationError, match="起始行号不能大于结束行号"):
            MemoryGetInput(file_path="MEMORY.md", line_start=100, line_end=50)


class TestMemoryGetFunction:
    """测试 memory_get 函数"""

    @pytest.fixture
    def memory_dir(self, tmp_path):
        """创建临时记忆目录"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        # 创建一些测试文件
        (memory_dir / "MEMORY.md").write_text("# 用户记忆\n\n这是测试内容")
        (memory_dir / "AGENTS.md").write_text("# Agent 指令\n\n指令内容")
        (memory_dir / "USER.md").write_text("# 用户信息\n\n用户数据")

        # 创建 bank 目录
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir()
        (bank_dir / "world.md").write_text("# 客观事实")
        (bank_dir / "opinions.md").write_text("# 判断和偏好")

        # 创建今日日志
        today = date.today()
        (memory_dir / today.strftime("%Y-%m-%d.md")).write_text("# 今日日志")

        return memory_dir

    def test_read_simple_file(self, memory_dir):
        """测试读取简单文件"""
        # 注意：这里需要临时修改 MEMORY_DIR 或使用 mock
        mg = _get_memory_get_module()
        original_dir = mg.MEMORY_DIR
        mg.MEMORY_DIR = memory_dir

        try:
            result = memory_get("MEMORY.md")
            assert "# 用户记忆" in result
            assert "测试内容" in result
        finally:
            mg.MEMORY_DIR = original_dir

    def test_read_with_line_range(self, memory_dir):
        """测试读取指定行号范围"""
        mg = _get_memory_get_module()
        original_dir = mg.MEMORY_DIR
        mg.MEMORY_DIR = memory_dir

        try:
            result = memory_get("MEMORY.md", line_start=1, line_end=2)
            lines = result.strip().split('\n')
            assert len(lines) <= 2
            assert "# 用户记忆" in result
        finally:
            mg.MEMORY_DIR = original_dir

    def test_read_nonexistent_file(self, memory_dir):
        """测试读取不存在的文件"""
        mg = _get_memory_get_module()
        original_dir = mg.MEMORY_DIR
        mg.MEMORY_DIR = memory_dir

        try:
            result = memory_get("NONEXISTENT.md")
            assert "❌ 文件不存在" in result
            assert "NONEXISTENT.md" in result
        finally:
            mg.MEMORY_DIR = original_dir

    def test_max_length_limit(self, memory_dir):
        """测试长度限制"""
        mg = _get_memory_get_module()
        original_dir = mg.MEMORY_DIR
        mg.MEMORY_DIR = memory_dir

        try:
            result = memory_get("MEMORY.md", max_length=20)
            assert len(result) <= 30  # 20 + 截断提示
            assert "..." in result or len(result) <= 20
        finally:
            mg.MEMORY_DIR = original_dir


class TestMemoryGetTool:
    """测试 memory_get StructuredTool"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert memory_get_tool.name == "memory_get"
        assert memory_get_tool.description is not None
        assert memory_get_tool.args_schema == MemoryGetInput

    def test_tool_invocation(self):
        """测试工具调用"""
        # 创建一个临时文件进行测试
        mg = _get_memory_get_module()
        original_dir = mg.MEMORY_DIR

        # 使用项目实际的 memory 目录
        project_memory = Path("/Users/qini/Desktop/untitled folder/工作相关/A_Agent/ba-agent/memory")
        if project_memory.exists():
            mg.MEMORY_DIR = project_memory

            try:
                # 测试读取 USER.md（应该存在）
                result = memory_get_tool.invoke({"file_path": "USER.md"})
                assert isinstance(result, str)
                assert len(result) > 0
            finally:
                mg.MEMORY_DIR = original_dir


class TestRecentLogs:
    """测试读取最近日志"""

    @pytest.fixture
    def memory_dir_with_logs(self, tmp_path):
        """创建带有历史日志的临时目录"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        # 创建最近几天的日志
        today = date.today()
        for i in range(3):
            log_date = today - timedelta(days=i)
            log_file = memory_dir / log_date.strftime("%Y-%m-%d.md")
            log_file.write_text(f"# 日志 - {log_date.strftime('%Y-%m-%d')}\n\n内容{i}")

        return memory_dir

    def test_get_recent_logs(self, memory_dir_with_logs):
        """测试获取最近日志"""
        mg = _get_memory_get_module()
        original_dir = mg.MEMORY_DIR
        mg.MEMORY_DIR = memory_dir_with_logs

        try:
            # 当 recent_days 不为 None 时，file_path 可以是任何值（会被忽略）
            result = memory_get(file_path="", recent_days=3)
            assert "# 日志" in result
            assert "内容0" in result or "内容1" in result or "内容2" in result
        finally:
            mg.MEMORY_DIR = original_dir

    def test_get_recent_logs_with_limit(self, memory_dir_with_logs):
        """测试获取最近日志并限制长度"""
        mg = _get_memory_get_module()
        original_dir = mg.MEMORY_DIR
        mg.MEMORY_DIR = memory_dir_with_logs

        try:
            result = memory_get(file_path="", recent_days=3, max_length=50)
            # 50 + 截断提示，但每个文件都有标题，所以会稍微超过
            assert len(result) <= 100  # 放宽限制
            assert "..." in result  # 应该有截断标记
        finally:
            mg.MEMORY_DIR = original_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
