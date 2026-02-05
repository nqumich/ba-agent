"""
memory_search 工具测试
"""

import pytest
from pathlib import Path
from tools.memory_search import memory_search, _get_files_to_search, MEMORY_DIR


class TestMemorySearchInput:
    """测试 MemorySearchInput 验证"""

    def test_empty_query_raises_error(self):
        """测试空查询会抛出错误"""
        from pydantic import ValidationError
        from tools.memory_search import MemorySearchInput

        with pytest.raises(ValidationError):
            MemorySearchInput(query="")

    def test_invalid_memory_type_raises_error(self):
        """测试无效的 memory_type 会抛出错误"""
        from pydantic import ValidationError
        from tools.memory_search import MemorySearchInput

        with pytest.raises(ValidationError):
            MemorySearchInput(query="test", memory_type="invalid")

    def test_max_results_validation(self):
        """测试 max_results 验证"""
        from pydantic import ValidationError
        from tools.memory_search import MemorySearchInput

        # 太小
        with pytest.raises(ValidationError):
            MemorySearchInput(query="test", max_results=0)

        # 太大
        with pytest.raises(ValidationError):
            MemorySearchInput(query="test", max_results=101)

    def test_valid_input(self):
        """测试有效输入"""
        from tools.memory_search import MemorySearchInput

        input_obj = MemorySearchInput(
            query="Python",
            entities=["@Test"],
            memory_type="all",
            max_results=10
        )
        assert input_obj.query == "Python"
        assert input_obj.entities == ["@Test"]
        assert input_obj.memory_type == "all"
        assert input_obj.max_results == 10


class TestGetFilesToSearch:
    """测试 _get_files_to_search 函数"""

    def test_all_type_includes_long_term(self, tmp_path):
        """测试 all 类型包含长期记忆文件"""
        # 创建临时文件结构
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        (memory_dir / "MEMORY.md").write_text("# Memory\n")
        (memory_dir / "AGENTS.md").write_text("# Agents\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            files = _get_files_to_search("all", None)
            file_names = [f.name for f in files]
            assert "MEMORY.md" in file_names
            assert "AGENTS.md" in file_names
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_bank_type_filters_to_bank(self, tmp_path):
        """测试 bank 类型只搜索 bank 目录"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir()

        (memory_dir / "MEMORY.md").write_text("# Memory\n")
        (bank_dir / "world.md").write_text("# World\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            files = _get_files_to_search("bank", None)
            file_names = [f.name for f in files]
            assert "world.md" in file_names
            assert "MEMORY.md" not in file_names
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_since_days_filters_daily_logs(self, tmp_path):
        """测试 since_days 过滤每日日志"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        from datetime import date, timedelta
        today = date.today()

        # 创建今天的日志
        today_log = memory_dir / today.strftime("%Y-%m-%d.md")
        today_log.write_text("# Today\n")

        # 创建昨天的日志
        yesterday_log = memory_dir / (today - timedelta(days=1)).strftime("%Y-%m-%d.md")
        yesterday_log.write_text("# Yesterday\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            # 只搜索最近1天
            files = _get_files_to_search("daily", 1)
            file_names = [f.name for f in files]
            assert today.strftime("%Y-%m-%d.md") in file_names
            assert (today - timedelta(days=1)).strftime("%Y-%m-%d.md") not in file_names
        finally:
            tools.memory_search.MEMORY_DIR = original_dir


class TestMemorySearchFunction:
    """测试 memory_search 函数"""

    def test_search_keyword(self, tmp_path):
        """测试关键词搜索"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "MEMORY.md"
        test_file.write_text("# Python 装饰器\n\ndecorator 可以扩展功能\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            result = memory_search("decorator", memory_type="long_term")
            assert "decorator" in result
            assert "MEMORY.md" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_search_with_entities(self, tmp_path):
        """测试实体过滤"""
        memory_dir = tmp_path / "memory"
        bank_dir = memory_dir / "bank"
        bank_dir.mkdir(parents=True)

        test_file = bank_dir / "world.md"
        test_file.write_text("- W @Python: 装饰器\n- B @项目: 完成\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            # 搜索 @Python 实体
            result = memory_search("@Python", entities=["@Python"], memory_type="bank")
            assert "Python" in result
            assert "world.md" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_no_results_returns_message(self, tmp_path):
        """测试无结果时返回提示消息"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "MEMORY.md"
        test_file.write_text("# 不相关内容\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            result = memory_search("不存在的关键词xyz", memory_type="long_term")
            assert "未找到匹配" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_context_lines_parameter(self, tmp_path):
        """测试 context_lines 参数"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "MEMORY.md"
        test_file.write_text("第一行\n第二行\n匹配行\n第四行\n第五行\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            # 上下文行数=1
            result = memory_search("匹配行", context_lines=1, memory_type="long_term")
            # 应该包含匹配行和前后各1行
            assert "第二行" in result
            assert "匹配行" in result
            assert "第四行" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_max_results_limits_output(self, tmp_path):
        """测试 max_results 限制输出数量"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "MEMORY.md"
        test_file.write_text("\n".join([f"行{i}: 匹配内容" for i in range(10)]))

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            result = memory_search("匹配", max_results=3, memory_type="long_term")
            # 检查结果格式
            assert "找到 3 个匹配" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir


class TestMemorySearchTool:
    """测试 memory_search_tool 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        from tools.memory_search import memory_search_tool

        assert memory_search_tool.name == "memory_search"
        assert "搜索" in memory_search_tool.description
        assert memory_search_tool.args_schema is not None

    def test_tool_invocation(self, tmp_path):
        """测试工具调用"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "MEMORY.md"
        test_file.write_text("# 测试内容\n")

        import tools.memory_search
        from tools.memory_search import memory_search_tool
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            result = memory_search_tool.invoke({
                "query": "测试",
                "memory_type": "long_term"
            })
            assert "测试" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir


class TestRegexSupport:
    """测试正则表达式支持"""

    def test_regex_pattern(self, tmp_path):
        """测试正则表达式模式"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "MEMORY.md"
        test_file.write_text("Python decorator\ndecorator function\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            # 使用正则表达式
            result = memory_search(r"decorator.*\w+", memory_type="long_term")
            assert "decorator" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_invalid_regex_is_escaped(self, tmp_path):
        """测试无效正则被转义为字面字符串"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        test_file = memory_dir / "MEMORY.md"
        test_file.write_text("包含 [特殊] 字符\n")

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            # 无效的正则应该被转义
            result = memory_search("[特殊]", memory_type="long_term")
            assert "特殊" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_memory_directory(self, tmp_path):
        """测试空记忆目录"""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            result = memory_search("test", memory_type="long_term")
            assert "未找到匹配" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir

    def test_nonexistent_directory(self, tmp_path):
        """测试不存在的目录"""
        memory_dir = tmp_path / "nonexistent"

        import tools.memory_search
        original_dir = tools.memory_search.MEMORY_DIR
        tools.memory_search.MEMORY_DIR = memory_dir

        try:
            result = memory_search("test", memory_type="long_term")
            assert "未找到匹配" in result
        finally:
            tools.memory_search.MEMORY_DIR = original_dir
