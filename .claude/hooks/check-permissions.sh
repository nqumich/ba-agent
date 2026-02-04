#!/bin/bash

# PreToolUse Hook: 检查执行权限
# 在执行命令或 Python 代码前检查权限

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具名称
TOOL_NAME=$(echo "$CONTEXT" | jq -r '.toolName // ""')

# 提取工具参数
TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')

# 权限检查逻辑
case "$TOOL_NAME" in
    execute_command)
        # 提取要执行的命令
        COMMAND=$(echo "$TOOL_ARGS" | jq -r '.command // ""')

        # 检查命令白名单
        ALLOWED_COMMANDS=("ls" "cat" "grep" "find" "head" "tail" "wc" "sort" "uniq")
        CMD_BASE=$(echo "$COMMAND" | awk '{print $1}')

        if [[ ! " ${ALLOWED_COMMANDS[@]} " =~ " ${CMD_BASE} " ]]; then
            # 命令不在白名单中
            jq -n \
                --arg reason "Command '$CMD_BASE' is not in the allowed list" \
                '{block: true, reason: $reason}'
            exit 0
        fi
        ;;

    run_python)
        # Python 代码执行总是允许的 (Docker 隔离)
        # 但可以检查代码长度限制
        CODE=$(echo "$TOOL_ARGS" | jq -r '.code // ""')
        CODE_LENGTH=${#CODE}

        MAX_CODE_LENGTH=10000
        if [ $CODE_LENGTH -gt $MAX_CODE_LENGTH ]; then
            jq -n \
                --arg reason "Python code too long (max $MAX_CODE_LENGTH characters)" \
                '{block: true, reason: $reason}'
            exit 0
        fi
        ;;
esac

# 允许执行
jq -n '{block: false}'
