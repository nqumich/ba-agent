#!/bin/bash

# PostToolUse Hook: 记录活动
# 统一记录各种工具活动到progress.md

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具名称
TOOL_NAME=$(echo "$CONTEXT" | jq -r '.toolName // ""')

# 提取工具参数
TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')

# 生成时间戳
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 根据工具类型记录不同内容
case "$TOOL_NAME" in
    database)
        # 数据库查询
        QUERY=$(echo "$TOOL_ARGS" | jq -r '.query // ""')
        CONNECTION=$(echo "$TOOL_ARGS" | jq -r '.connection // "primary"')
        {
            echo ""
            echo "### 数据库查询 ($TIMESTAMP)"
            echo ""
            echo "**连接**: $CONNECTION"
            echo ""
            echo '```sql'
            echo "$QUERY"
            echo '```'
            echo ""
        } >> progress.md
        ;;

    web_search)
        # Web搜索
        QUERY=$(echo "$TOOL_ARGS" | jq -r '.query // ""')
        {
            echo ""
            echo "### Web搜索 ($TIMESTAMP)"
            echo ""
            echo "**查询**: $QUERY"
            echo ""
        } >> progress.md
        ;;

    web_reader)
        # Web读取
        URL=$(echo "$TOOL_ARGS" | jq -r '.url // ""')
        {
            echo ""
            echo "### Web读取 ($TIMESTAMP)"
            echo ""
            echo "**URL**: $URL"
            echo ""
        } >> progress.md
        ;;

    skill_manager)
        # Skill包管理
        ACTION=$(echo "$TOOL_ARGS" | jq -r '.action // ""')
        SOURCE=$(echo "$TOOL_ARGS" | jq -r '.source // ""')
        {
            echo ""
            echo "### Skill管理 ($TIMESTAMP)"
            echo ""
            echo "**操作**: $ACTION"
            if [ -n "$SOURCE" ]; then
                echo "**来源**: $SOURCE"
            fi
            echo ""
        } >> progress.md
        ;;
esac

jq -n '{logged: true}'
