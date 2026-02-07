"""
Context Manager Tests

测试上下文管理器的文件内容清理功能（v1.4.0 新增）
"""

import pytest
import json
from pathlib import Path

from backend.core.context_manager import ContextManager


class TestContextManagerFileCleaning:
    """测试文件内容清理功能"""

    def test_is_read_file_result_true(self):
        """测试识别 read_file 工具结果"""
        manager = ContextManager()

        # 正确的 tool_call_id 格式
        msg = {"tool_call_id": "call_read_file_abc123", "content": "file content"}
        assert manager._is_read_file_result(msg) is True

        msg = {"tool_call_id": "call_read_file_xyz", "content": "file content"}
        assert manager._is_read_file_result(msg) is True

    def test_is_read_file_result_false(self):
        """测试非 read_file 工具结果"""
        manager = ContextManager()

        # 其他 tool_call_id 格式
        msg = {"tool_call_id": "call_python_abc123", "content": "code result"}
        assert manager._is_read_file_result(msg) is False

        msg = {"tool_call_id": "call_query_xyz", "content": "query result"}
        assert manager._is_read_file_result(msg) is False

        # 没有 tool_call_id
        msg = {"role": "user", "content": "user message"}
        assert manager._is_read_file_result(msg) is False

    def test_parse_file_result_json_format(self):
        """测试解析 JSON 格式的文件结果"""
        manager = ContextManager()

        # JSON 格式
        content = json.dumps({
            "path": "/path/to/file.py",
            "content": "print('hello')",
            "metadata": {"language": "python"}
        })

        file_path, file_content, metadata = manager._parse_file_result(content)

        assert file_path == "/path/to/file.py"
        assert file_content == "print('hello')"
        assert metadata == {"language": "python"}

    def test_parse_file_result_text_format(self):
        """测试解析纯文本格式的文件结果"""
        manager = ContextManager()

        # 纯文本格式（包含文件路径标记）
        content = "[文件] /path/to/sales_analysis.py\nprint('hello')"

        file_path, file_content, metadata = manager._parse_file_result(content)

        assert file_path == "/path/to/sales_analysis.py"
        assert "print('hello')" in file_content
        assert metadata == {}

    def test_parse_file_result_no_path(self):
        """测试无法解析路径的文件结果"""
        manager = ContextManager()

        # 无法识别的格式
        content = "just some plain content without file markers"

        file_path, file_content, metadata = manager._parse_file_result(content)

        assert file_path is None
        assert file_content == "just some plain content without file markers"
        assert metadata == {}

    def test_format_size(self):
        """测试文件大小格式化"""
        manager = ContextManager()

        assert manager._format_size(100) == "100.0B"
        assert manager._format_size(1024) == "1.0KB"
        assert manager._format_size(1024 * 1024) == "1.0MB"
        assert manager._format_size(1024 * 1024 * 1024) == "1.0GB"

    def test_generate_code_summary_python(self):
        """测试生成 Python 代码文件梗概"""
        manager = ContextManager()

        code = """
def load_data():
    return data

def clean_data(data):
    return data

class DataProcessor:
    def process(self):
        pass
"""
        summary = manager._generate_code_summary("sales_analysis.py", ".py", code, {})

        assert "sales_analysis.py" in summary
        assert "py" in summary  # 文件扩展名
        assert "行" in summary
        assert "load_data" in summary
        assert "clean_data" in summary
        assert "DataProcessor" in summary

    def test_generate_code_summary_javascript(self):
        """测试生成 JavaScript 代码文件梗概"""
        manager = ContextManager()

        code = """
function loadData() {
    return data;
}

function processData(data) {
    return data;
}
"""
        summary = manager._generate_code_summary("chart.js", ".js", code, {})

        assert "chart.js" in summary
        # JavaScript 不使用 AST 解析，所以不会提取函数名
        # 但应该包含文件名和行数

    def test_generate_data_summary_csv(self):
        """测试生成 CSV 数据文件梗概"""
        manager = ContextManager()

        csv_content = """date,product,amount,region
2024-01-01,A,100,North
2024-01-02,B,200,South
2024-01-03,C,300,East"""

        summary = manager._generate_data_summary("sales.csv", ".csv", csv_content, {})

        assert "sales.csv" in summary
        assert "csv" in summary  # 文件扩展名
        assert "行" in summary
        assert "列:" in summary
        assert "date" in summary
        assert "product" in summary
        assert "amount" in summary

    def test_generate_json_summary_dict(self):
        """测试生成 JSON 字典文件梗概"""
        manager = ContextManager()

        json_content = json.dumps({
            "settings": {"theme": "dark"},
            "data": [1, 2, 3],
            "options": {"title": "Chart"}
        })

        summary = manager._generate_json_summary("config.json", json_content, {})

        assert "config.json" in summary
        assert "JSON" in summary
        assert "键:" in summary
        assert "settings" in summary or "data" in summary

    def test_generate_json_summary_array(self):
        """测试生成 JSON 数组文件梗概"""
        manager = ContextManager()

        json_content = json.dumps([1, 2, 3, 4, 5])

        summary = manager._generate_json_summary("data.json", json_content, {})

        assert "data.json" in summary
        assert "JSON" in summary
        assert "数组" in summary
        assert "5项" in summary

    def test_clean_file_contents_read_file_messages(self):
        """测试清理 read_file 工具返回的消息"""
        manager = ContextManager()

        messages = [
            {
                "role": "assistant",
                "tool_call_id": "call_read_file_abc123",
                "content": json.dumps({
                    "path": "sales_analysis.py",
                    "content": "def load_data():\n    pass\ndef clean_data():\n    pass"
                })
            },
            {
                "role": "user",
                "content": "继续分析"
            }
        ]

        cleaned = manager.clean_file_contents(messages)

        assert len(cleaned) == 2
        assert "[文件已读取]" in cleaned[0]["content"]
        assert "sales_analysis.py" in cleaned[0]["content"]
        assert cleaned[0].get("cleaned") is True
        assert cleaned[1]["content"] == "继续分析"

    def test_clean_file_contents_preserves_other_messages(self):
        """测试保留非 read_file 消息"""
        manager = ContextManager()

        messages = [
            {
                "role": "system",
                "content": "System prompt"
            },
            {
                "role": "user",
                "content": "User message"
            },
            {
                "role": "assistant",
                "tool_call_id": "call_python_xyz",
                "content": "Python execution result"
            }
        ]

        cleaned = manager.clean_file_contents(messages)

        assert len(cleaned) == 3
        assert cleaned[0]["content"] == "System prompt"
        assert cleaned[1]["content"] == "User message"
        assert cleaned[2]["content"] == "Python execution result"
        assert not any(msg.get("cleaned") for msg in cleaned)

    def test_clean_file_contents_mixed_messages(self):
        """测试混合消息的清理"""
        manager = ContextManager()

        messages = [
            {"role": "system", "content": "System prompt"},
            {
                "role": "assistant",
                "tool_call_id": "call_read_file_code1",
                "content": json.dumps({"path": "code.py", "content": "print('hello')"})
            },
            {"role": "user", "content": "Continue"},
            {
                "role": "assistant",
                "tool_call_id": "call_read_file_data1",
                "content": "[文件] data.csv\ncol1,col2\n1,2"
            },
            {"role": "assistant", "tool_call_id": "call_python_exec", "content": "Done"}
        ]

        cleaned = manager.clean_file_contents(messages)

        assert len(cleaned) == 5
        assert cleaned[0]["content"] == "System prompt"
        assert "[文件已读取]" in cleaned[1]["content"]
        assert "code.py" in cleaned[1]["content"]
        assert cleaned[1].get("cleaned") is True
        assert cleaned[2]["content"] == "Continue"
        assert "[文件已读取]" in cleaned[3]["content"]
        assert "data.csv" in cleaned[3]["content"]
        assert cleaned[3].get("cleaned") is True
        assert cleaned[4]["content"] == "Done"

    def test_build_context_no_longer_injects_code(self):
        """测试 build_context 不再自动注入代码"""
        manager = ContextManager()

        # 构建上下文，消息中包含 code_id 引用
        messages = manager.build_context(
            message="请使用 code_sales_analysis 进行分析",
            session_id="test_session"
        )

        # 检查没有注入 XML 代码块
        for msg in messages:
            assert "<!-- CODE_BLOCK:" not in msg.get("content", "")
            assert "<code language=" not in msg.get("content", "")

        # 确保用户消息被添加
        user_messages = [m for m in messages if m.get("role") == "user"]
        assert len(user_messages) == 1
        assert "code_sales_analysis" in user_messages[0]["content"]


class TestContextManagerOldMethodsRemoved:
    """测试旧方法已被移除"""

    def test_old_methods_do_not_exist(self):
        """测试旧方法已不存在"""
        manager = ContextManager()

        # 这些方法应该已被移除
        assert not hasattr(manager, "extract_code_references")
        assert not hasattr(manager, "inject_code_blocks")
        assert not hasattr(manager, "clean_code_blocks")
        assert not hasattr(manager, "format_code_block")
        assert not hasattr(manager, "has_code_blocks")
        assert not hasattr(manager, "_remove_code_blocks_from_text")

    def test_old_constants_do_not_exist(self):
        """测试旧常量已不存在"""
        manager = ContextManager()

        # 这些常量应该已被移除
        assert not hasattr(manager, "CODE_BLOCK_START")
        assert not hasattr(manager, "CODE_BLOCK_END")
        assert not hasattr(manager, "CODE_BLOCK_PATTERN")
