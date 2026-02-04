#!/bin/bash

# PostToolUse Hook: 提示保存发现
# 每N次工具调用后提示保存重要发现

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具调用计数（如果有的话）
CALL_COUNT=$(echo "$CONTEXT" | jq -r '.callCount // "1"')

# 每5次提示一次
if [ $((CALL_COUNT % 5)) -eq 0 ]; then
    jq -n \
        --arg message "💡 提示: 已完成 $CALL_COUNT 次工具调用。如果有重要的发现或学习，请考虑保存到 findings.md 或 memory/ 目录中。" \
        '{prompt: $message}'
else
    jq -n '{prompt: null}'
fi
