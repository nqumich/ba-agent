#!/bin/bash

# UserPromptSubmit Hook: 验证输入
# 用户提交提示时验证

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取用户提示
PROMPT=$(echo "$CONTEXT" | jq -r '.prompt // ""')

# 检查提示长度
PROMPT_LENGTH=${#PROMPT}
MAX_PROMPT_LENGTH=50000

if [ $PROMPT_LENGTH -gt $MAX_PROMPT_LENGTH ]; then
    jq -n \
        --arg reason "Prompt too long (max $MAX_PROMPT_LENGTH characters)" \
        '{block: true, reason: $reason}'
    exit 0
fi

# 允许提交
jq -n '{block: false}'
