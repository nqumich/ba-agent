"""
Memory Retain 工具测试
"""

import pytest
from tools.memory_retain import (
    memory_retain,
    memory_retain_parse,
    MemoryRetainInput,
)


class TestMemoryRetainInput:
    """测试 MemoryRetainInput 输入验证"""

    def test_valid_input_with_entity(self):
        """测试有效输入（带实体）"""
        input_data = MemoryRetainInput(
            content="完成 GMV 异常检测功能",
            retain_type="W",
            entity="数据团队"
        )
        assert input_data.content == "完成 GMV 异常检测功能"
        assert input_data.retain_type == "W"
        assert input_data.entity == "数据团队"
        assert input_data.confidence is None

    def test_valid_input_without_entity(self):
        """测试有效输入（不带实体）"""
        input_data = MemoryRetainInput(
            content="讨论了 Q1 季度规划",
            retain_type="S"
        )
        assert input_data.content == "讨论了 Q1 季度规划"
        assert input_data.retain_type == "S"
        assert input_data.entity is None

    def test_valid_input_opinion_with_confidence(self):
        """测试观点输入（带置信度）"""
        input_data = MemoryRetainInput(
            content="安全库存应保持 7 天以上",
            retain_type="O",
            entity="库存管理",
            confidence=0.9
        )
        assert input_data.content == "安全库存应保持 7 天以上"
        assert input_data.retain_type == "O"
        assert input_data.confidence == 0.9

    def test_retain_type_case_insensitive(self):
        """测试类型大小写不敏感"""
        input_data = MemoryRetainInput(
            content="test",
            retain_type="w"  # 小写
        )
        assert input_data.retain_type == "W"  # 应该转为大写

    def test_content_validation_empty(self):
        """测试空内容验证"""
        with pytest.raises(ValueError, match="content 不能为空"):
            MemoryRetainInput(content="   ", retain_type="W")

    def test_content_validation_too_long(self):
        """测试内容过长验证"""
        long_content = "a" * 5001
        with pytest.raises(ValueError, match="content 长度不能超过 5000"):
            MemoryRetainInput(content=long_content, retain_type="W")

    def test_retain_type_validation_invalid(self):
        """测试无效类型验证"""
        with pytest.raises(ValueError, match="retain_type 必须是"):
            MemoryRetainInput(content="test", retain_type="X")

    def test_confidence_validation_out_of_range(self):
        """测试置信度超出范围"""
        with pytest.raises(ValueError, match="confidence 必须在 0-1 之间"):
            MemoryRetainInput(content="test", retain_type="O", confidence=1.5)

        with pytest.raises(ValueError, match="confidence 必须在 0-1 之间"):
            MemoryRetainInput(content="test", retain_type="O", confidence=-0.1)

    def test_confidence_validation_valid(self):
        """测试有效置信度边界值"""
        input_data = MemoryRetainInput(
            content="test",
            retain_type="O",
            confidence=0.0
        )
        assert input_data.confidence == 0.0

        input_data = MemoryRetainInput(
            content="test",
            retain_type="O",
            confidence=1.0
        )
        assert input_data.confidence == 1.0


class TestMemoryRetain:
    """测试 memory_retain 函数"""

    def test_format_world_with_entity(self):
        """测试格式化世界事实（带实体）"""
        result = memory_retain("完成 GMV 异常检测功能", "W", "数据团队")
        assert result == "W @数据团队: 完成 GMV 异常检测功能"

    def test_format_world_without_entity(self):
        """测试格式化世界事实（不带实体）"""
        result = memory_retain("今天完成了数据分析", "W")
        assert result == "W: 今天完成了数据分析"

    def test_format_bio_with_entity(self):
        """测试格式化传记（带实体）"""
        result = memory_retain("用户偏好 Markdown 格式的报告", "B", "张三")
        assert result == "B @张三: 用户偏好 Markdown 格式的报告"

    def test_format_bio_without_entity(self):
        """测试格式化传记（不带实体）"""
        result = memory_retain("用户是技术背景", "B")
        assert result == "B: 用户是技术背景"

    def test_format_opinion_with_confidence_and_entity(self):
        """测试格式化观点（带置信度和实体）"""
        result = memory_retain("安全库存应保持 7 天以上", "O", "库存管理", 0.9)
        assert result == "O(c=0.9) @库存管理: 安全库存应保持 7 天以上"

    def test_format_opinion_with_confidence_no_entity(self):
        """测试格式化观点（带置信度，不带实体）"""
        result = memory_retain("这是一个不错的方案", "O", confidence=0.8)
        assert result == "O(c=0.8): 这是一个不错的方案"

    def test_format_opinion_default_confidence(self):
        """测试观点默认置信度"""
        result = memory_retain("需要进一步验证", "O", "算法")
        # RetainFormatter 不显示默认置信度 0.5
        assert result == "O @算法: 需要进一步验证"

    def test_format_opinion_confidence_zero(self):
        """测试观点置信度为 0"""
        result = memory_retain("不太确定", "O", confidence=0.0)
        assert result == "O(c=0.0): 不太确定"

    def test_format_summary_with_entity(self):
        """测试格式化总结（带实体）"""
        result = memory_retain("讨论了 Q1 季度规划", "S", "团队会议")
        assert result == "S @团队会议: 讨论了 Q1 季度规划"

    def test_format_summary_without_entity(self):
        """测试格式化总结（不带实体）"""
        result = memory_retain("完成了本周工作", "S")
        assert result == "S: 完成了本周工作"

    def test_type_case_insensitive(self):
        """测试类型大小写不敏感"""
        result1 = memory_retain("test", "w")
        result2 = memory_retain("test", "W")
        assert result1 == result2

    def test_unicode_content(self):
        """测试 Unicode 内容"""
        result = memory_retain("中文测试 🎉", "W", "测试")
        assert result == "W @测试: 中文测试 🎉"

    def test_content_trim(self):
        """测试内容保留原样（直接调用函数不 trim，通过 Pydantic 才会 trim）"""
        result = memory_retain("  测试内容  ", "W")
        # 直接调用 memory_retain 函数时，内容不会被 trim
        assert result == "W:   测试内容  "

    def test_invalid_type(self):
        """测试无效类型"""
        with pytest.raises(ValueError):
            memory_retain("test", "X")


class TestMemoryRetainParse:
    """测试 memory_retain_parse 函数"""

    def test_parse_world_with_entity(self):
        """测试解析世界事实（带实体）"""
        result = memory_retain_parse("W @数据团队: 完成 GMV 异常检测功能")
        assert result["type"] == "W"
        assert result["entity"] == "数据团队"
        assert result["content"] == "完成 GMV 异常检测功能"
        assert result["confidence"] is None

    def test_parse_world_without_entity(self):
        """测试解析世界事实（不带实体）"""
        result = memory_retain_parse("W: 今天完成了数据分析")
        assert result["type"] == "W"
        assert result["entity"] is None
        assert result["content"] == "今天完成了数据分析"
        assert result["confidence"] is None

    def test_parse_opinion_with_confidence_and_entity(self):
        """测试解析观点（带置信度和实体）"""
        result = memory_retain_parse("O(c=0.9) @库存管理: 安全库存应保持 7 天以上")
        assert result["type"] == "O"
        assert result["entity"] == "库存管理"
        assert result["content"] == "安全库存应保持 7 天以上"
        assert result["confidence"] == 0.9

    def test_parse_opinion_with_confidence_no_entity(self):
        """测试解析观点（带置信度，不带实体）"""
        result = memory_retain_parse("O(c=0.8): 这是一个不错的方案")
        assert result["type"] == "O"
        assert result["entity"] is None
        assert result["content"] == "这是一个不错的方案"
        assert result["confidence"] == 0.8

    def test_parse_opinion_default_confidence(self):
        """测试解析观点（默认置信度，无 c= 标记）"""
        result = memory_retain_parse("O @算法: 需要进一步验证")
        assert result["type"] == "O"
        assert result["entity"] == "算法"
        assert result["content"] == "需要进一步验证"
        # 无 c= 标记时，confidence 为 None
        assert result["confidence"] is None

    def test_parse_bio_with_entity(self):
        """测试解析传记（带实体）"""
        result = memory_retain_parse("B @张三: 用户偏好 Markdown 格式的报告")
        assert result["type"] == "B"
        assert result["entity"] == "张三"
        assert result["content"] == "用户偏好 Markdown 格式的报告"

    def test_parse_summary_with_entity(self):
        """测试解析总结（带实体）"""
        result = memory_retain_parse("S @团队会议: 讨论了 Q1 季度规划")
        assert result["type"] == "S"
        assert result["entity"] == "团队会议"
        assert result["content"] == "讨论了 Q1 季度规划"

    def test_parse_invalid_format(self):
        """测试解析无效格式"""
        result = memory_retain_parse("这不是 Retain 格式")
        assert "error" in result
        assert "original" in result

    def test_roundtrip_world(self):
        """测试 W 格式往返转换"""
        original = "测试内容"
        formatted = memory_retain(original, "W", "测试")
        parsed = memory_retain_parse(formatted)
        assert parsed["type"] == "W"
        assert parsed["entity"] == "测试"
        assert parsed["content"] == original

    def test_roundtrip_opinion(self):
        """测试 O 格式往返转换"""
        original = "这是一个观点"
        formatted = memory_retain(original, "O", "主题", 0.75)
        parsed = memory_retain_parse(formatted)
        assert parsed["type"] == "O"
        assert parsed["entity"] == "主题"
        assert parsed["content"] == original
        # 置信度被格式化为一位小数: 0.75 -> 0.8
        assert parsed["confidence"] == 0.8


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_entity_string(self):
        """测试空实体字符串"""
        result = memory_retain("test", "W", "")
        # 空字符串被当作没有实体
        assert result == "W: test"

    def test_very_long_content(self):
        """测试接近最大长度限制的内容"""
        long_content = "a" * 5000
        result = memory_retain(long_content, "W")
        assert long_content in result

    def test_special_characters_in_entity(self):
        """测试实体中的特殊字符"""
        result = memory_retain("test", "W", "数据-团队_2025")
        assert "数据-团队_2025" in result

    def test_multiline_content(self):
        """测试多行内容"""
        content = "第一行\n第二行\n第三行"
        result = memory_retain(content, "W")
        assert "第一行" in result
        assert "第二行" in result
        assert "第三行" in result

    def test_confidence_with_decimals(self):
        """测试带小数的置信度"""
        result = memory_retain("test", "O", confidence=0.333)
        assert "0.3" in result  # 格式化为一位小数
