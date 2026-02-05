"""
memory_write 工具测试
"""

import pytest
from pathlib import Path
from datetime import date
from tools.memory_write import (
    memory_write,
    _auto_detect_layer,
    _resolve_target_file,
    MEMORY_DIR,
    memory_write_tool
)


class TestMemoryWriteInput:
    """测试 MemoryWriteInput 验证"""

    def test_empty_content_raises_error(self):
        """测试空内容会抛出错误"""
        from pydantic import ValidationError
        from tools.memory_write import MemoryWriteInput

        with pytest.raises(ValidationError):
            MemoryWriteInput(content="")

        with pytest.raises(ValidationError):
            MemoryWriteInput(content="   ")

    def test_invalid_layer_raises_error(self):
        """测试无效的 layer 会抛出错误"""
        from pydantic import ValidationError
        from tools.memory_write import MemoryWriteInput

        with pytest.raises(ValidationError):
            MemoryWriteInput(content="test", layer="invalid")

    def test_invalid_category_raises_error(self):
        """测试无效的 category 会抛出错误"""
        from pydantic import ValidationError
        from tools.memory_write import MemoryWriteInput

        with pytest.raises(ValidationError):
            MemoryWriteInput(content="test", category="invalid")

    def test_category_with_non_bank_layer_raises_error(self):
        """测试非 bank 层使用 category 会抛出错误"""
        from pydantic import ValidationError
        from tools.memory_write import MemoryWriteInput

        with pytest.raises(ValidationError):
            MemoryWriteInput(content="test", layer="daily", category="world")

    def test_path_traversal_attack_raises_error(self):
        """测试路径遍历攻击会抛出错误"""
        from pydantic import ValidationError
        from tools.memory_write import MemoryWriteInput

        with pytest.raises(ValidationError):
            MemoryWriteInput(content="test", file_path="../etc/passwd")

    def test_valid_input(self):
        """测试有效输入"""
        from tools.memory_write import MemoryWriteInput

        input_obj = MemoryWriteInput(
            content="测试内容",
            layer="daily",
            append=True
        )
        assert input_obj.content == "测试内容"
        assert input_obj.layer == "daily"
        assert input_obj.append is True


class TestAutoDetectLayer:
    """测试 _auto_detect_layer 函数"""

    def test_detect_from_file_path_bank(self):
        """测试从 bank/ 路径检测"""
        result = _auto_detect_layer("", "bank/world.md")
        assert result == "bank"

    def test_detect_from_file_path_longterm(self):
        """测试从长期记忆文件检测"""
        result = _auto_detect_layer("", "MEMORY.md")
        assert result == "longterm"

        result = _auto_detect_layer("", "USER.md")
        assert result == "longterm"

    def test_detect_from_file_path_context(self):
        """测试从上下文文件检测"""
        result = _auto_detect_layer("", "CLAUDE.md")
        assert result == "context"

        result = _auto_detect_layer("", "AGENTS.md")
        assert result == "context"

        result = _auto_detect_layer("", "SOUL.md")
        assert result == "context"

    def test_detect_from_file_path_daily(self):
        """测试从日期格式文件检测"""
        result = _auto_detect_layer("", "2025-02-05.md")
        assert result == "daily"

    def test_detect_retain_format_markers(self):
        """测试 Retain 格式标记检测"""
        # W @ 标记
        result = _auto_detect_layer("W @Python: 这是知识", None)
        assert result == "bank"

        # B @ 标记
        result = _auto_detect_layer("B @项目: 完成了任务", None)
        assert result == "bank"

        # O(c=) 标记
        result = _auto_detect_layer("O(c=0.9) @架构: 这是正确的", None)
        assert result == "bank"

        # S @ 标记
        result = _auto_detect_layer("S @进度: 已完成", None)
        assert result == "bank"

    def test_detect_daily_keywords(self):
        """测试每日关键词检测"""
        result = _auto_detect_layer("今天完成了任务", None)
        assert result == "daily"

        result = _auto_detect_layer("今日学习了 Python", None)
        assert result == "daily"

        result = _auto_detect_layer("待办事项", None)
        assert result == "daily"

    def test_default_to_daily(self):
        """测试默认为 daily"""
        result = _auto_detect_layer("一些普通内容", None)
        assert result == "daily"


class TestResolveTargetFile:
    """测试 _resolve_target_file 函数"""

    def test_explicit_file_path(self):
        """测试明确指定的文件路径"""
        result = _resolve_target_file("daily", "custom.md", None)
        assert result == MEMORY_DIR / "custom.md"

    def test_daily_layer_today(self):
        """测试 daily 层级使用今天日期"""
        result = _resolve_target_file("daily", None, None)
        today = date.today().strftime("%Y-%m-%d")
        assert result == MEMORY_DIR / f"{today}.md"

    def test_longterm_layer_memory_md(self):
        """测试 longterm 层级使用 MEMORY.md"""
        result = _resolve_target_file("longterm", None, None)
        assert result == MEMORY_DIR / "MEMORY.md"

    def test_context_layer_returns_none(self):
        """测试 context 层级返回 None（需要明确指定文件）"""
        result = _resolve_target_file("context", None, None)
        assert result is None

    def test_bank_layer_with_category(self):
        """测试 bank 层级使用 category"""
        result = _resolve_target_file("bank", None, "world")
        assert result == MEMORY_DIR / "bank" / "world.md"

        result = _resolve_target_file("bank", None, "experience")
        assert result == MEMORY_DIR / "bank" / "experience.md"

        result = _resolve_target_file("bank", None, "opinions")
        assert result == MEMORY_DIR / "bank" / "opinions.md"

    def test_bank_layer_default_category(self):
        """测试 bank 层级默认使用 experience"""
        result = _resolve_target_file("bank", None, None)
        assert result == MEMORY_DIR / "bank" / "experience.md"

    def test_unknown_layer_returns_none(self):
        """测试未知层级返回 None"""
        result = _resolve_target_file("unknown", None, None)
        assert result is None


class TestMemoryWriteFunction:
    """测试 memory_write 函数"""

    def test_write_to_daily_log(self, tmp_path):
        """测试写入每日日志"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write("今天学习了 Python", layer="daily")
            assert "成功" in result
            assert "daily" in result.lower() or str(date.today()) in result

            # 验证文件已创建
            today = date.today().strftime("%Y-%m-%d")
            log_file = memory_dir / f"{today}.md"
            assert log_file.exists()
            content = log_file.read_text()
            assert "今天学习了 Python" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_write_to_memory_md(self, tmp_path):
        """测试写入 MEMORY.md"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write("# 用户偏好\n\n喜欢简洁的代码", layer="longterm")
            assert "成功" in result
            assert "MEMORY.md" in result

            # 验证文件内容
            memory_file = memory_dir / "MEMORY.md"
            assert memory_file.exists()
            content = memory_file.read_text()
            assert "用户偏好" in content
            assert "喜欢简洁的代码" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_write_to_bank_world(self, tmp_path):
        """测试写入 bank/world.md"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write(
                "W @Python: 装饰器可以在不修改原函数的情况下扩展功能",
                layer="bank",
                category="world"
            )
            assert "成功" in result
            assert "bank/world.md" in result

            # 验证文件内容
            world_file = bank_dir / "world.md"
            assert world_file.exists()
            content = world_file.read_text()
            assert "W @Python" in content
            assert "装饰器" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_write_to_bank_experience(self, tmp_path):
        """测试写入 bank/experience.md"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write(
                "B @项目: Phase 2 核心工具全部完成",
                layer="bank",
                category="experience"
            )
            assert "成功" in result

            # 验证文件内容
            exp_file = bank_dir / "experience.md"
            assert exp_file.exists()
            content = exp_file.read_text()
            assert "B @项目" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_write_to_bank_opinions(self, tmp_path):
        """测试写入 bank/opinions.md"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write(
                "O(c=0.9) @架构: 双记忆系统设计是正确的方向",
                layer="bank",
                category="opinions"
            )
            assert "成功" in result

            # 验证文件内容
            opinions_file = bank_dir / "opinions.md"
            assert opinions_file.exists()
            content = opinions_file.read_text()
            assert "O(c=0.9)" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_append_mode(self, tmp_path):
        """测试追加模式"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            # 第一次写入
            memory_write("第一条内容", layer="bank", category="world")

            # 追加写入
            result = memory_write("第二条内容", layer="bank", category="world", append=True)
            assert "成功" in result

            # 验证两条内容都存在
            world_file = bank_dir / "world.md"
            content = world_file.read_text()
            assert "第一条内容" in content
            assert "第二条内容" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_overwrite_mode(self, tmp_path):
        """测试覆盖模式"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            # 第一次写入
            memory_write("原始内容", layer="bank", category="world")

            # 覆盖写入
            result = memory_write("新内容", layer="bank", category="world", append=False)
            assert "成功" in result

            # 验证只有新内容存在
            world_file = bank_dir / "world.md"
            content = world_file.read_text()
            assert "原始内容" not in content
            assert "新内容" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_timestamp_disabled(self, tmp_path):
        """测试禁用时间戳"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write("内容", layer="bank", category="world", timestamp=False)
            assert "成功" in result

            # 验证没有时间戳
            world_file = bank_dir / "world.md"
            content = world_file.read_text()
            assert "## " not in content  # 时间戳格式是 ## YYYY-MM-DD HH:MM:SS
            assert "内容" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_timestamp_enabled(self, tmp_path):
        """测试启用时间戳"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write("内容", layer="bank", category="world", timestamp=True)
            assert "成功" in result

            # 验证有时间戳
            world_file = bank_dir / "world.md"
            content = world_file.read_text()
            assert "## " in content  # 时间戳格式
            assert "内容" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_context_layer_requires_file_path(self, tmp_path):
        """测试 context 层级需要明确指定文件路径"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write("内容", layer="context")
            assert "无法确定目标文件" in result
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_context_layer_with_file_path(self, tmp_path):
        """测试 context 层级配合文件路径"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write("# 新指令\n\n内容", layer="context", file_path="AGENTS.md")
            assert "成功" in result

            # 验证文件内容
            agents_file = memory_dir / "AGENTS.md"
            assert agents_file.exists()
            content = agents_file.read_text()
            assert "新指令" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_auto_detect_with_retain_format(self, tmp_path):
        """测试 auto 层级自动检测 Retain 格式"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            # 包含 Retain 格式，应自动写入 bank/experience.md
            result = memory_write("B @测试: 这是经历", layer="auto")
            assert "成功" in result

            # 验证写入到 experience.md（默认 bank category）
            exp_file = bank_dir / "experience.md"
            assert exp_file.exists()
            content = exp_file.read_text()
            assert "B @测试" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_auto_detect_with_daily_keywords(self, tmp_path):
        """测试 auto 层级自动检测每日关键词"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write("今天完成了任务", layer="auto")
            assert "成功" in result

            # 验证写入到今天的日志
            today = date.today().strftime("%Y-%m-%d")
            log_file = memory_dir / f"{today}.md"
            assert log_file.exists()
            content = log_file.read_text()
            assert "今天完成了任务" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir


class TestMemoryWriteTool:
    """测试 memory_write_tool 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert memory_write_tool.name == "memory_write"
        assert "写入" in memory_write_tool.description
        assert memory_write_tool.args_schema is not None

    def test_tool_invocation(self, tmp_path):
        """测试工具调用"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            result = memory_write_tool.invoke({
                "content": "W @测试: 通过工具调用写入",
                "layer": "bank",
                "category": "world"
            })
            assert "成功" in result

            # 验证文件内容
            world_file = bank_dir / "world.md"
            content = world_file.read_text()
            assert "W @测试" in content
        finally:
            tools.memory_write.MEMORY_DIR = original_dir


class TestEdgeCases:
    """测试边界情况"""

    def test_content_stripping(self, tmp_path):
        """测试内容前后空格被去除"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            # 内容前后有空格
            result = memory_write("  内容  ", layer="bank", category="world", timestamp=False)
            assert "成功" in result

            world_file = bank_dir / "world.md"
            content = world_file.read_text().strip()
            # 应该没有前后空格
            assert content == "内容"
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_long_content_preview(self, tmp_path):
        """测试长内容的预览截断"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            # 超过100字符的内容
            long_content = "A" * 200
            result = memory_write(long_content, layer="bank", category="world", timestamp=False)
            assert "成功" in result
            assert "..." in result  # 预览被截断
        finally:
            tools.memory_write.MEMORY_DIR = original_dir

    def test_creates_bank_directory(self, tmp_path):
        """测试自动创建 bank 目录"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import tools.memory_write
        original_dir = tools.memory_write.MEMORY_DIR
        tools.memory_write.MEMORY_DIR = memory_dir

        try:
            # bank 目录不存在
            bank_dir = memory_dir / "bank"
            assert not bank_dir.exists()

            # 写入应该自动创建目录
            result = memory_write("内容", layer="bank", category="world")
            assert "成功" in result

            # 验证目录已创建
            assert bank_dir.exists()
            assert (bank_dir / "world.md").exists()
        finally:
            tools.memory_write.MEMORY_DIR = original_dir
