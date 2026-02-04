"""
Pytest 配置文件

设置测试环境
"""

import sys
from pathlib import Path


def pytest_configure(config):
    """
    Pytest 配置钩子

    在测试收集之前设置 Python 路径
    """
    # 添加项目根目录到 Python 路径（必须放在最前面，避免命名冲突）
    project_root = Path(__file__).parent.parent.resolve()
    project_root_str = str(project_root)

    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    # 确保 config 模块从项目根目录加载
    config_path = str(project_root / "config")
    if config_path not in sys.path:
        sys.path.insert(0, config_path)


# 向后兼容：也直接设置路径（pytest_configure 会更早执行）
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))
if str(project_root / "config") not in sys.path:
    sys.path.insert(0, str(project_root / "config"))
