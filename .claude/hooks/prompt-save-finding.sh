#!/bin/bash

# PostToolUse Hook: 提示保存发现
# 每5次工具调用后提示保存重要发现

# Python JSON 辅助脚本路径
JSON_HELPER="$(dirname "$0")/json_helper.py"

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取调用计数（从 hook 的 count 属性获取）
# 注意：这个值由 Claude CLI 传入，表示当前是第几次触发
COUNT=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".count" "0")

# 提取最近的工具名称
TOOL_NAME=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".toolName" "")

# 每5次提示一次
if [ $((COUNT % 5)) -eq 0 ]; then
    # 生成提示消息
    MESSAGE="📝 **提示**: 你已经执行了 $COUNT 次工具调用。如果有重要的发现或决策，建议保存到 progress.md 或 MEMORY.md。"

    # 返回消息
    python3 -c "import json; print(json.dumps({'prompt': '$MESSAGE'}, ensure_ascii=False))"
else
    python3 -c 'import json; print(json.dumps({}))'
fi
