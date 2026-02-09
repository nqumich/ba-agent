"""
API 应用状态管理

提供全局状态访问，避免循环导入
"""

from typing import Dict, Any

# 全局状态
_global_state: Dict[str, Any] = {}


def get_app_state() -> Dict[str, Any]:
    """获取应用状态"""
    return _global_state


def set_app_state(key: str, value: Any) -> None:
    """设置应用状态"""
    _global_state[key] = value


__all__ = ["get_app_state", "set_app_state"]
