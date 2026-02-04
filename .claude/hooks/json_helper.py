#!/usr/bin/env python3
"""
JSON 处理辅助脚本 - 替代 jq 用于 Claude CLI hooks
从 stdin 读取 JSON，支持字段提取和条件判断
"""

import sys
import json
from typing import Any, Optional

def main():
    if len(sys.argv) < 2:
        print("Usage: json_helper.py <field> [default]", file=sys.stderr)
        sys.exit(1)

    # 读取 stdin JSON
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    # 获取请求的字段
    field = sys.argv[1]
    default_value = sys.argv[2] if len(sys.argv) > 2 else ""

    # 支持嵌套字段 (如 .toolName, .toolArgs.skill)
    result = get_nested_value(data, field, default_value)

    # 输出结果
    if result is None:
        print(default_value)
    elif isinstance(result, bool):
        print("true" if result else "false")
    elif isinstance(result, (list, dict)):
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result)

def get_nested_value(data: Any, path: str, default: Any = "") -> Any:
    """获取嵌套字段的值"""
    if not path or path == ".":
        return data

    # 移除前导点
    path = path.lstrip(".")

    # 分割路径
    parts = path.split(".")
    result = data

    for part in parts:
        if isinstance(result, dict):
            result = result.get(part)
            if result is None:
                return default
        elif isinstance(result, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(result):
                result = result[idx]
            else:
                return default
        else:
            return default

    return result if result is not None else default

if __name__ == "__main__":
    main()
