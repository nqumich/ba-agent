#!/bin/bash

# PreToolUse Hook: 检查Skill安装权限
# 在安装外部Skill前验证来源和安全性

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具参数
TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')

# 提取操作类型
ACTION=$(echo "$TOOL_ARGS" | jq -r '.action // ""')

# 只对 install 操作进行检查
if [ "$ACTION" != "install" ]; then
    jq -n '{block: false}'
    exit 0
fi

# 提取来源
SOURCE=$(echo "$TOOL_ARGS" | jq -r '.source // ""')

# 检查来源类型
if [[ -z "$SOURCE" ]]; then
    jq -n \
        --arg reason "Skill install requires a source parameter" \
        '{block: true, reason: $reason}'
    exit 0
fi

# 检查来源安全性
case "$SOURCE" in
    *.git|github:*)
        # GitHub 来源 - 允许
        ;;
    http://*|https://*)
        # URL 来源 - 检查是否为已知安全域名
        if [[ "$SOURCE" != *"github.com"* ]]; then
            jq -n \
                --arg reason "Only GitHub URLs are currently supported for Skill installation" \
                '{block: true, reason: $reason}'
            exit 0
        fi
        ;;
    /*)
        # 本地绝对路径 - 允许但需要检查
        if [ ! -d "$SOURCE" ] && [ ! -f "$SOURCE" ]; then
            jq -n \
                --arg reason "Local source path does not exist: $SOURCE" \
                '{block: true, reason: $reason}'
            exit 0
        fi
        ;;
    *)
        # 相对路径或其他格式
        ;;
esac

# 允许执行
jq -n '{block: false}'
