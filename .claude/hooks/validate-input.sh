#!/bin/bash

# UserPromptSubmit Hook: 验证输入

# Python JSON 辅助脚本路径
JSON_HELPER="$(dirname "$0")/json_helper.py"

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取用户输入
USER_INPUT=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".userPrompt" "")

# 基本验证
VALIDATION_ISSUES=""

# 检查空输入
if [ -z "$USER_INPUT" ] || [ "$USER_INPUT" = "null" ]; then
    VALIDATION_ISSUES="输入不能为空"
fi

# 检查输入长度
INPUT_LENGTH=${#USER_INPUT}
if [ $INPUT_LENGTH -lt 3 ]; then
    VALIDATION_ISSUES="输入太短（至少3个字符）"
fi

# 检查是否包含可疑的命令注入模式
if echo "$USER_INPUT" | grep -qE ";\s*(rm|dd|mkfs|format)"; then
    VALIDATION_ISSUES="输入包含危险系统命令"
fi

# 返回验证结果
if [ -n "$VALIDATION_ISSUES" ]; then
    python3 -c "import json; print(json.dumps({'valid': False, 'reason': '$VALIDATION_ISSUES'}, ensure_ascii=False))"
else
    python3 -c 'import json; print(json.dumps({"valid": True}))'
fi
