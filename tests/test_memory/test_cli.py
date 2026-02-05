"""
Memory CLI 测试
"""

import tempfile
from pathlib import Path
from click.testing import CliRunner

from backend.memory.cli import memory, main


class TestMemoryCLI:
    """测试 Memory CLI 命令"""

    def test_cli_exists(self):
        """测试 CLI 存在"""
        runner = CliRunner()
        result = runner.invoke(memory, ["--help"])
        assert result.exit_code == 0
        assert "记忆管理 CLI" in result.output

    def test_index_command_help(self):
        """测试 index 命令帮助"""
        runner = CliRunner()
        result = runner.invoke(memory, ["index", "--help"])
        assert result.exit_code == 0
        assert "重建记忆索引" in result.output

    def test_search_command_help(self):
        """测试 search 命令帮助"""
        runner = CliRunner()
        result = runner.invoke(memory, ["search", "--help"])
        assert result.exit_code == 0
        assert "搜索记忆" in result.output

    def test_status_command_no_index(self):
        """测试 status 命令（无索引）"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(memory, ["status"])
            assert result.exit_code == 0
            assert "索引不存在" in result.output

    def test_retain_command_w(self):
        """测试 retain 命令 (W 类型)"""
        runner = CliRunner()
        result = runner.invoke(memory, [
            "retain",
            "完成 GMV 异常检测功能",
            "--type", "W",
            "--entity", "数据团队"
        ])
        assert result.exit_code == 0
        assert "W @数据团队: 完成 GMV 异常检测功能" in result.output

    def test_retain_command_b(self):
        """测试 retain 命令 (B 类型)"""
        runner = CliRunner()
        result = runner.invoke(memory, [
            "retain",
            "用户偏好 Markdown 格式的报告",
            "--type", "B",
            "--entity", "张三"
        ])
        assert result.exit_code == 0
        assert "B @张三: 用户偏好 Markdown 格式的报告" in result.output

    def test_retain_command_o(self):
        """测试 retain 命令 (O 类型)"""
        runner = CliRunner()
        result = runner.invoke(memory, [
            "retain",
            "安全库存应保持 7 天以上",
            "--type", "O",
            "--entity", "库存管理",
            "--confidence", "0.9"
        ])
        assert result.exit_code == 0
        assert "O(c=0.9) @库存管理: 安全库存应保持 7 天以上" in result.output

    def test_retain_command_s(self):
        """测试 retain 命令 (S 类型)"""
        runner = CliRunner()
        result = runner.invoke(memory, [
            "retain",
            "讨论了 Q1 季度规划",
            "--type", "S"
        ])
        assert result.exit_code == 0
        assert "S: 讨论了 Q1 季度规划" in result.output

    def test_retain_command_no_entity(self):
        """测试 retain 命令（无实体）"""
        runner = CliRunner()
        result = runner.invoke(memory, [
            "retain",
            "测试内容",
            "--type", "W"
        ])
        assert result.exit_code == 0
        assert "W: 测试内容" in result.output


class TestMainEntry:
    """测试主入口函数"""

    def test_main_exists(self):
        """测试 main 函数存在"""
        assert main is not None
        assert callable(main)
