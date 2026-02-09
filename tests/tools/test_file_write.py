"""
File Write 工具测试
"""

import tempfile
from pathlib import Path
import pytest

from tools.file_write import file_write, FileWriteInput

# Pipeline v2.1 模型
from backend.models.pipeline import ToolExecutionResult, OutputLevel


class TestFileWriteInput:
    """测试 FileWriteInput 输入验证"""

    def test_valid_input(self):
        """测试有效输入"""
        input_data = FileWriteInput(
            content="Hello World",
            file_path="data/test.md"
        )
        assert input_data.content == "Hello World"
        assert input_data.file_path == "data/test.md"
        assert input_data.mode == "append"

    def test_default_values(self):
        """测试默认值"""
        input_data = FileWriteInput(
            content="test",
            file_path="memory/test.md"
        )
        assert input_data.mode == "append"
        assert input_data.create_dirs is True
        assert input_data.separator == "\n\n---\n\n"

    def test_content_validation_none(self):
        """测试空内容验证"""
        with pytest.raises(ValueError):  # Pydantic 会抛出 ValueError
            FileWriteInput(
                content=None,  # type: ignore
                file_path="test.md"
            )

    def test_file_path_validation_traversal(self):
        """测试路径遍历攻击检测"""
        with pytest.raises(ValueError, match="不能包含"):
            FileWriteInput(
                content="test",
                file_path="../etc/passwd"
            )

    def test_file_path_validation_outside_allowed(self):
        """测试允许目录外的路径"""
        with pytest.raises(ValueError, match="只能写入以下目录"):
            FileWriteInput(
                content="test",
                file_path="/etc/passwd"
            )


class TestFileWrite:
    """测试 file_write 函数"""

    def test_write_new_file(self, tmp_path):
        """测试写入新文件"""
        # 创建临时目录作为工作目录
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            result = file_write(
                content="Hello World",
                file_path="data/test.md"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            # STANDARD 格式显示 "action: 追加到" 等字段
            assert "追加到" in result.observation
            assert "data/test.md" in result.observation

            # 验证文件已创建
            file_path = tmp_path / "data" / "test.md"
            assert file_path.exists()
            content = file_path.read_text(encoding='utf-8')
            assert "Hello World" in content

        finally:
            os.chdir(old_cwd)

    def test_append_mode(self, tmp_path):
        """测试追加模式"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            # 首次写入
            file_write("First line", "data/test.md")

            # 追加写入
            result = file_write("Second line", "data/test.md", mode="append")

            assert isinstance(result, ToolExecutionResult)
            assert result.success

            file_path = tmp_path / "data" / "test.md"
            content = file_path.read_text(encoding='utf-8')
            assert "First line" in content
            assert "Second line" in content
            assert "---" in content  # 分隔符

        finally:
            os.chdir(old_cwd)

    def test_overwrite_mode(self, tmp_path):
        """测试覆盖模式"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            # 首次写入
            file_write("Original content", "data/test.md")

            # 覆盖写入
            file_write("New content", "data/test.md", mode="overwrite")

            file_path = tmp_path / "data" / "test.md"
            content = file_path.read_text(encoding='utf-8')
            assert content == "New content"
            assert "Original content" not in content

        finally:
            os.chdir(old_cwd)

    def test_prepend_mode(self, tmp_path):
        """测试前置模式"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            # 首次写入
            file_write("First", "data/test.md")

            # 前置写入
            result = file_write("Second", "data/test.md", mode="prepend")

            assert isinstance(result, ToolExecutionResult)
            assert result.success

            file_path = tmp_path / "data" / "test.md"
            content = file_path.read_text(encoding='utf-8')
            assert content.startswith("Second")
            assert "First" in content
            assert "---" in content

        finally:
            os.chdir(old_cwd)

    def test_create_dirs(self, tmp_path):
        """测试自动创建目录"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            result = file_write(
                content="Nested file",
                file_path="data/nested/deep/file.md",
                create_dirs=True
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success

            file_path = tmp_path / "data" / "nested" / "deep" / "file.md"
            assert file_path.exists()
            assert file_path.parent.is_dir()

        finally:
            os.chdir(old_cwd)

    def test_custom_separator(self, tmp_path):
        """测试自定义分隔符"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            file_write("First", "data/test.md")
            file_write("Second", "data/test.md", separator="\n***\n")

            file_path = tmp_path / "data" / "test.md"
            content = file_path.read_text(encoding='utf-8')
            assert "***" in content

        finally:
            os.chdir(old_cwd)

    def test_write_memory_dir(self, tmp_path):
        """测试写入 memory 目录"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            # 创建 memory 目录
            (tmp_path / "memory").mkdir(exist_ok=True)

            result = file_write(
                content="Today's notes",
                file_path="memory/notes.md"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            assert "memory/notes.md" in result.observation or "notes.md" in result.observation

            file_path = tmp_path / "memory" / "notes.md"
            assert file_path.exists()

        finally:
            os.chdir(old_cwd)

    def test_unicode_content(self, tmp_path):
        """测试 Unicode 内容"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            result = file_write(
                content="测试中文 🎉 Emoji αβγ",
                file_path="data/unicode.md"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success

            file_path = tmp_path / "data" / "unicode.md"
            content = file_path.read_text(encoding='utf-8')
            assert "测试中文" in content
            assert "🎉" in content
            assert "αβγ" in content

        finally:
            os.chdir(old_cwd)

    def test_long_content(self, tmp_path):
        """测试长内容"""
        old_cwd = Path.cwd()
        import os
        os.chdir(tmp_path)

        try:
            # 生成 1000 行（最后一个字符不带换行符）
            long_content = "Line\n" * 999 + "Line"
            result = file_write(
                content=long_content,
                file_path="data/long.md"
            )

            assert isinstance(result, ToolExecutionResult)
            assert result.success
            # STANDARD 格式显示 line_count: 1000
            assert "1000" in result.observation

            file_path = tmp_path / "data" / "long.md"
            content = file_path.read_text(encoding='utf-8')
            assert len(content.split('\n')) == 1000

        finally:
            os.chdir(old_cwd)
