"""
Tools 测试配置
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

# 确保 config 模块从项目根目录加载
if str(project_root / "config") not in sys.path:
    sys.path.insert(0, str(project_root / "config"))
