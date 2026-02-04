#!/bin/bash

# PreToolUse Hook: 统一安全检查
# 整合权限、SQL注入、Skill安装验证

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具名称
TOOL_NAME=$(echo "$CONTEXT" | jq -r '.toolName // ""')

# 提取工具参数
TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')

# 根据工具类型执行相应的安全检查
case "$TOOL_NAME" in
    execute_command)
        # 提取要执行的命令
        COMMAND=$(echo "$TOOL_ARGS" | jq -r '.command // ""')

        # 检查命令白名单
        ALLOWED_COMMANDS=("ls" "cat" "grep" "find" "head" "tail" "wc" "sort" "uniq")
        CMD_BASE=$(echo "$COMMAND" | awk '{print $1}')

        if [[ ! " ${ALLOWED_COMMANDS[@]} " =~ " ${CMD_BASE} " ]]; then
            jq -n \
                --arg reason "Command '$CMD_BASE' is not in the allowed list" \
                '{block: true, reason: $reason}'
            exit 0
        fi
        ;;

    python_sandbox)
        # Python 代码执行总是允许的 (Docker 隔离)
        # 检查代码长度限制
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

    database)
        # SQL 注入检查
        QUERY=$(echo "$TOOL_ARGS" | jq -r '.query // ""')
        QUERY_UPPER=$(echo "$QUERY" | tr '[:lower:]' '[:upper:]')

        # 允许的关键字开头
        ALLOWED_PREFIXES=("SELECT" "WITH" "SHOW" "DESCRIBE" "EXPLAIN")
        IS_SAFE=false

        for prefix in "${ALLOWED_PREFIXES[@]}"; do
            if [[ "$QUERY_UPPER" == "$prefix"* ]]; then
                IS_SAFE=true
                break
            fi
        done

        # 检查危险关键字
        DANGEROUS_KEYWORDS=("DROP" "DELETE" "UPDATE" "INSERT" "CREATE" "ALTER" "GRANT" "REVOKE" "TRUNCATE")

        for keyword in "${DANGEROUS_KEYWORDS[@]}"; do
            if [[ "$QUERY_UPPER" == *"$keyword"* ]]; then
                jq -n \
                    --arg reason "Query contains dangerous keyword '$keyword'. Only SELECT/WITH queries are allowed." \
                    '{block: true, reason: $reason}'
                exit 0
            fi
        done

        if [ "$IS_SAFE" = false ]; then
            jq -n \
                --arg reason "Query must start with SELECT, WITH, SHOW, DESCRIBE, or EXPLAIN" \
                '{block: true, reason: $reason}'
            exit 0
        fi
        ;;

    skill_manager)
        # Skill 安装检查
        ACTION=$(echo "$TOOL_ARGS" | jq -r '.action // ""')

        # 只对 install 操作进行检查
        if [ "$ACTION" != "install" ]; then
            jq -n '{block: false}'
            exit 0
        fi

        SOURCE=$(echo "$TOOL_ARGS" | jq -r '.source // ""')

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
                # URL 来源 - 只允许 GitHub
                if [[ "$SOURCE" != *"github.com"* ]]; then
                    jq -n \
                        --arg reason "Only GitHub URLs are currently supported for Skill installation" \
                        '{block: true, reason: $reason}'
                    exit 0
                fi
                ;;
            /*)
                # 本地路径 - 检查是否存在
                if [ ! -d "$SOURCE" ] && [ ! -f "$SOURCE" ]; then
                    jq -n \
                        --arg reason "Local source path does not exist: $SOURCE" \
                        '{block: true, reason: $reason}'
                    exit 0
                fi
                ;;
        esac
        ;;
esac

# 允许执行
jq -n '{block: false}'
