#!/bin/bash

# PostToolUse Hook: 总结Python输出
# Python执行后自动总结结果

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具结果
RESULT=$(echo "$CONTEXT" | jq -r '.result // ""')

# 检查是否有错误
if echo "$RESULT" | grep -qi "error"; then
    # 有错误，不总结
    jq -n '{summary: null}'
    exit 0
fi

# 提取输出长度
OUTPUT_LENGTH=${#RESULT}

# 只有输出较长时才生成总结
if [ $OUTPUT_LENGTH -lt 100 ]; then
    jq -n '{summary: null}'
    exit 0
fi

# 生成简单的总结提示
SUMMARY="Python代码执行完成，输出 ${OUTPUT_LENGTH} 字符"

jq -n \
    --arg summary "$SUMMARY" \
    '{summary: $summary}'
