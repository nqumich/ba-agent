"""
Excel 处理服务测试

测试 ExcelProcessor 和 ExcelValidator
"""

import pytest
import io
from pathlib import Path

import pandas as pd

from backend.api.services.excel_processor import (
    ExcelProcessor,
    ExcelValidator,
    create_excel_processor,
    create_excel_validator
)


@pytest.fixture
def sample_excel_content():
    """创建示例 Excel 内容"""
    # 创建示例 DataFrame
    data = {
        "date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
        "gmv": [10000, 12000, 15000, 13000, 18000],
        "orders": [50, 60, 75, 65, 90],
        "conversion_rate": [0.05, 0.06, 0.075, 0.065, 0.09]
    }
    df = pd.DataFrame(data)

    # 写入 Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sales")

    output.seek(0)
    return output.read()


@pytest.fixture
def sample_excel_multiple_sheets():
    """创建多工作表 Excel"""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1
        df1 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        df1.to_excel(writer, index=False, sheet_name="Sheet1")

        # Sheet 2
        df2 = pd.DataFrame({"x": [10, 20], "y": [30, 40]})
        df2.to_excel(writer, index=False, sheet_name="Sheet2")

    output.seek(0)
    return output.read()


class TestExcelProcessor:
    """测试 Excel 处理器"""

    def test_init(self):
        """测试初始化"""
        processor = ExcelProcessor()
        assert processor is not None
        assert processor.pd is not None

    def test_is_supported(self):
        """测试文件格式支持检查"""
        processor = ExcelProcessor()

        assert processor.is_supported("test.xlsx") is True
        assert processor.is_supported("test.xls") is True
        assert processor.is_supported("test.csv") is False
        assert processor.is_supported("test.json") is False
        assert processor.is_supported("test.txt") is False

    def test_validate_size(self):
        """测试文件大小验证"""
        processor = ExcelProcessor()

        # 小文件
        small_content = b"x" * 100
        assert processor.validate_size(small_content) is True

        # 刚好在限制内
        limit_content = b"x" * (50 * 1024 * 1024)
        assert processor.validate_size(limit_content) is True

        # 超过限制
        large_content = b"x" * (50 * 1024 * 1024 + 1)
        assert processor.validate_size(large_content) is False

    def test_parse_metadata(self, sample_excel_content):
        """测试解析元数据"""
        processor = ExcelProcessor()
        metadata = processor.parse_metadata(sample_excel_content, "test.xlsx")

        assert metadata["format"] == "excel"
        assert "Sales" in metadata["sheets"]
        assert metadata["total_rows"] == 5
        assert len(metadata["columns"]) == 4
        assert "date" in metadata["columns"]
        assert "gmv" in metadata["columns"]
        assert len(metadata["preview"]) == 5

    def test_get_sheet_names(self, sample_excel_multiple_sheets):
        """测试获取工作表名称"""
        processor = ExcelProcessor()
        sheets = processor.get_sheet_names(sample_excel_multiple_sheets)

        assert len(sheets) == 2
        assert "Sheet1" in sheets
        assert "Sheet2" in sheets

    def test_read_sheet(self, sample_excel_content):
        """测试读取工作表"""
        processor = ExcelProcessor()
        result = processor.read_sheet(sample_excel_content, sheet_name=0)

        assert result["success"] is True
        assert result["rows"] == 5
        assert len(result["columns"]) == 4
        assert len(result["data"]) == 5

    def test_read_sheet_with_nrows(self, sample_excel_content):
        """测试读取限制行数"""
        processor = ExcelProcessor()
        result = processor.read_sheet(sample_excel_content, sheet_name=0, nrows=2)

        assert result["success"] is True
        assert result["rows"] == 2
        assert len(result["data"]) == 2

    def test_to_dataframe(self, sample_excel_content):
        """测试转换为 DataFrame"""
        processor = ExcelProcessor()
        df = processor.to_dataframe(sample_excel_content, sheet_name=0)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert list(df.columns) == ["date", "gmv", "orders", "conversion_rate"]

    def test_validate_data(self, sample_excel_content):
        """测试数据验证"""
        processor = ExcelProcessor()
        result = processor.validate_data(sample_excel_content)

        assert result["valid"] is True
        assert result["info"]["sheet_count"] == 1
        assert len(result["errors"]) == 0


class TestExcelValidator:
    """测试 Excel 验证器"""

    def test_init(self):
        """测试初始化"""
        validator = ExcelValidator()
        assert validator is not None
        assert validator.processor is not None

    def test_init_custom_size(self):
        """测试自定义最大大小"""
        validator = ExcelValidator(max_size=1024)
        assert validator.max_size == 1024

    def test_validate_upload_success(self, sample_excel_content):
        """测试验证成功"""
        validator = ExcelValidator()
        result = validator.validate_upload("test.xlsx", sample_excel_content)

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["metadata"]["format"] == "excel"

    def test_validate_upload_invalid_filename(self):
        """测试无效文件名"""
        validator = ExcelValidator()
        result = validator.validate_upload("", b"some content")

        assert result["valid"] is False
        assert "文件名不能为空" in result["errors"]

    def test_validate_upload_unsupported_format(self):
        """测试不支持的格式"""
        validator = ExcelValidator()
        result = validator.validate_upload("test.csv", b"some content")

        assert result["valid"] is False
        assert "不支持的文件格式" in result["errors"][0]

    def test_validate_upload_too_large(self):
        """测试文件过大"""
        # 直接测试 validate_size 方法
        processor = ExcelProcessor()
        large_content = b"x" * (ExcelProcessor.MAX_FILE_SIZE + 1)
        assert processor.validate_size(large_content) is False


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_create_excel_processor(self):
        """测试创建处理器"""
        processor = create_excel_processor()
        assert isinstance(processor, ExcelProcessor)

    def test_create_excel_validator(self):
        """测试创建验证器"""
        validator = create_excel_validator()
        assert isinstance(validator, ExcelValidator)

    def test_create_excel_validator_custom_size(self):
        """测试创建自定义大小验证器"""
        validator = create_excel_validator(max_size=2048)
        assert isinstance(validator, ExcelValidator)
        assert validator.max_size == 2048
