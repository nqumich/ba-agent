#!/bin/bash

# PreToolUse Hook: 统一安全检查
# 检查命令权限、SQL注入、Skill安装来源

# Python JSON 辅助脚本路径
JSON_HELPER="$(dirname "$0")/json_helper.py"

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具名称和参数
TOOL_NAME=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".toolName" "")
TOOL_ARGS=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".toolArgs" "{}")

# 安全检查结果
SECURITY_ISSUES=""

case "$TOOL_NAME" in
    execute_command)
        COMMAND=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".command" "")

        # 命令白名单检查
        ALLOWED_COMMANDS="ls cat echo grep head tail wc find pwd date"
        CMD_BASE=$(echo "$COMMAND" | awk '{print $1}')

        if ! echo " $ALLOWED_COMMANDS " | grep -q " $CMD_BASE "; then
            SECURITY_ISSUES="命令 '$CMD_BASE' 不在白名单中"
        fi
        ;;

    database)
        QUERY=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".query" "")

        # SQL 注入检查 - 只允许 SELECT 和 WITH
        QUERY_UPPER=$(echo "$QUERY" | tr '[:lower:]' '[:upper:]')

        # 检查危险关键字
        DANGEROUS_KEYWORDS="DROP DELETE UPDATE INSERT ALTER CREATE TRUNCATE GRANT REVOKE EXEC"
        for keyword in $DANGEROUS_KEYWORDS; do
            if echo "$QUERY_UPPER" | grep -qE "$keyword"; then
                SECURITY_ISSUES="SQL 查询包含危险关键字: $keyword"
                break
            fi
        done

        # 如果没有危险关键字，检查是否以 SELECT 或 WITH 开头
        if [ -z "$SECURITY_ISSUES" ]; then
            if ! echo "$QUERY_UPPER" | grep -qE "^(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)"; then
                SECURITY_ISSUES="SQL 查询必须以 SELECT、WITH、SHOW 等开头"
            fi
        fi
        ;;

    skill_manager)
        ACTION=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".action" "")

        if [ "$ACTION" = "install" ]; then
            SOURCE=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".source" "")

            # 检查 Skill 来源
            if echo "$SOURCE" | grep -qE "^(http|https)://"; then
                # HTTP URL - 检查是否为可信来源
                if ! echo "$SOURCE" | grep -qE "github\.com|gitlab\.com|bitbucket\.org"; then
                    SECURITY_ISSUES=" Skill 安装来源不是可信的 Git 托管平台: $SOURCE"
                fi
            elif echo "$SOURCE" | grep -qE "\\.zip$"; then
                # ZIP 文件 - 检查路径
                if echo "$SOURCE" | grep -qE "\.\./|\${HOME}|~"; then
                    SECURITY_ISSUES="ZIP 文件路径包含可疑的路径遍历"
                fi
            fi
        fi
        ;;

    python_sandbox)
        CODE=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".code" "")

        # Python 代码安全检查
        DANGEROUS_IMPORTS="os\. subprocess\. exec\. eval\\. open\\. __import__"
        for imp in $DANGEROUS_IMPORTS; do
            if echo "$CODE" | grep -qE "$imp"; then
                SECURITY_ISSUES="Python 代码包含危险导入: $imp"
                break
            fi
        done

        # 如果没有危险导入，检查文件写入操作
        if [ -z "$SECURITY_ISSUES" ]; then
            if echo "$CODE" | grep -qE "open\([^)]*['\"]w"; then
                SECURITY_ISSUES="Python 代码包含文件写入操作"
            fi
        fi
        ;;
esac

# 返回检查结果
if [ -n "$SECURITY_ISSUES" ]; then
    # 有安全问题，返回错误
    python3 -c "import json; print(json.dumps({'allowed': False, 'reason': '$SECURITY_ISSUES'}, ensure_ascii=False))"
else
    # 安全检查通过
    python3 -c 'import json; print(json.dumps({"allowed": True}))'
fi
