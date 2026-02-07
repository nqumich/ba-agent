"""
Excel 处理服务

提供 Excel 文件解析、验证、元数据提取等功能
"""

import io
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ExcelProcessor:
    """Excel 文件处理器"""

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {".xlsx", ".xls"}

    # 最大文件大小 (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024

    def __init__(self):
        """初始化 Excel 处理器"""
        self._check_dependencies()

    def _check_dependencies(self):
        """检查依赖是否安装"""
        try:
            import pandas as pd
            self.pd = pd
        except ImportError:
            raise ImportError(
                "pandas 未安装，请运行: pip install pandas openpyxl"
            )

    def is_supported(self, filename: str) -> bool:
        """
        检查文件是否支持

        Args:
            filename: 文件名

        Returns:
            是否支持
        """
        ext = Path(filename).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS

    def validate_size(self, content: bytes) -> bool:
        """
        验证文件大小

        Args:
            content: 文件内容

        Returns:
            是否有效
        """
        return len(content) <= self.MAX_FILE_SIZE

    def parse_metadata(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        解析 Excel 文件元数据

        Args:
            content: 文件内容
            filename: 文件名

        Returns:
            元数据字典
        """
        metadata = {
            "format": "excel",
            "filename": filename,
            "size_bytes": len(content),
            "sheets": [],
            "total_rows": 0,
            "columns": [],
            "data_types": {},
            "preview": [],
            "parse_errors": []
        }

        try:
            with io.BytesIO(content) as bio:
                excel_file = self.pd.ExcelFile(bio)
                metadata["sheets"] = excel_file.sheet_names

                # 读取第一个 sheet 的基本信息
                df = self.pd.read_excel(bio, sheet_name=0, nrows=1000)

                metadata["total_rows"] = len(df)
                metadata["columns"] = df.columns.tolist()

                # 数据类型
                metadata["data_types"] = {
                    col: str(dtype) for col, dtype in df.dtypes.items()
                }

                # 预览前 5 行
                preview_df = df.head(5)
                metadata["preview"] = preview_df.to_dict(orient="records")

                # 检查空值
                null_counts = df.isnull().sum().to_dict()
                metadata["null_counts"] = {
                    k: v for k, v in null_counts.items() if v > 0
                }

                logger.info(f"Excel 元数据解析成功: {filename}, sheets={len(metadata['sheets'])}, rows={metadata['total_rows']}")

        except Exception as e:
            logger.error(f"Excel 元数据解析失败: {e}", exc_info=True)
            metadata["parse_errors"].append(str(e))

        return metadata

    def read_sheet(
        self,
        content: bytes,
        sheet_name: Union[str, int] = 0,
        nrows: Optional[int] = None,
        skiprows: int = 0
    ) -> Dict[str, Any]:
        """
        读取 Excel 工作表

        Args:
            content: 文件内容
            sheet_name: 工作表名称或索引
            nrows: 最大读取行数
            skiprows: 跳过的行数

        Returns:
            读取结果
        """
        result = {
            "success": False,
            "sheet": sheet_name,
            "data": [],
            "rows": 0,
            "columns": [],
            "error": None
        }

        try:
            with io.BytesIO(content) as bio:
                df = self.pd.read_excel(
                    bio,
                    sheet_name=sheet_name,
                    nrows=nrows,
                    skiprows=skiprows
                )

                result["success"] = True
                result["rows"] = len(df)
                result["columns"] = df.columns.tolist()
                result["data"] = df.to_dict(orient='records')

                logger.info(f"Excel 读取成功: sheet={sheet_name}, rows={len(df)}")

        except Exception as e:
            logger.error(f"Excel 读取失败: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    def get_sheet_names(self, content: bytes) -> List[str]:
        """
        获取所有工作表名称

        Args:
            content: 文件内容

        Returns:
            工作表名称列表
        """
        try:
            with io.BytesIO(content) as bio:
                excel_file = self.pd.ExcelFile(bio)
                return excel_file.sheet_names
        except Exception as e:
            logger.error(f"获取工作表名称失败: {e}")
            return []

    def to_dataframe(
        self,
        content: bytes,
        sheet_name: Union[str, int] = 0,
        **kwargs
    ):
        """
        将 Excel 转换为 DataFrame

        Args:
            content: 文件内容
            sheet_name: 工作表名称或索引
            **kwargs: 传递给 pd.read_excel 的参数

        Returns:
            pandas.DataFrame
        """
        with io.BytesIO(content) as bio:
            return self.pd.read_excel(bio, sheet_name=sheet_name, **kwargs)

    def validate_data(self, content: bytes) -> Dict[str, Any]:
        """
        验证 Excel 数据

        Args:
            content: 文件内容

        Returns:
            验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {}
        }

        try:
            sheet_names = self.get_sheet_names(content)
            result["info"]["sheet_count"] = len(sheet_names)

            # 检查每个 sheet
            for sheet_name in sheet_names:
                sheet_data = self.read_sheet(content, sheet_name, nrows=100)

                if not sheet_data["success"]:
                    result["valid"] = False
                    result["errors"].append(f"工作表 '{sheet_name}' 读取失败: {sheet_data['error']}")
                    continue

                # 检查空行
                if sheet_data["rows"] == 0:
                    result["warnings"].append(f"工作表 '{sheet_name}' 为空")

                # 检查列数
                col_count = len(sheet_data["columns"])
                if col_count == 0:
                    result["warnings"].append(f"工作表 '{sheet_name}' 没有列")

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"验证失败: {str(e)}")

        return result


class ExcelValidator:
    """Excel 文件验证器"""

    def __init__(self, max_size: int = ExcelProcessor.MAX_FILE_SIZE):
        """
        初始化验证器

        Args:
            max_size: 最大文件大小（字节）
        """
        self.max_size = max_size
        self.processor = ExcelProcessor()

    def validate_upload(
        self,
        filename: str,
        content: bytes
    ) -> Dict[str, Any]:
        """
        验证上传的 Excel 文件

        Args:
            filename: 文件名
            content: 文件内容

        Returns:
            验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "metadata": {}
        }

        # 检查文件名
        if not filename:
            result["valid"] = False
            result["errors"].append("文件名不能为空")
            return result

        # 检查扩展名
        if not self.processor.is_supported(filename):
            result["valid"] = False
            result["errors"].append(
                f"不支持的文件格式。支持的格式: {', '.join(ExcelProcessor.SUPPORTED_EXTENSIONS)}"
            )
            return result

        # 检查文件大小（在解析元数据之前检查）
        if len(content) > self.max_size:
            result["valid"] = False
            result["errors"].append(
                f"文件过大。最大支持 {self.max_size // (1024*1024)}MB"
            )
            return result

        # 解析元数据
        metadata = self.processor.parse_metadata(content, filename)

        if metadata.get("parse_errors"):
            result["warnings"].extend(metadata["parse_errors"])

        # 检查是否为空
        if metadata.get("total_rows", 0) == 0:
            result["warnings"].append("Excel 文件没有数据")

        result["metadata"] = metadata

        return result


# 便捷函数
def create_excel_processor() -> ExcelProcessor:
    """创建 Excel 处理器"""
    return ExcelProcessor()


def create_excel_validator(max_size: int = ExcelProcessor.MAX_FILE_SIZE) -> ExcelValidator:
    """创建 Excel 验证器"""
    return ExcelValidator(max_size=max_size)


__all__ = [
    "ExcelProcessor",
    "ExcelValidator",
    "create_excel_processor",
    "create_excel_validator",
]
