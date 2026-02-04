#!/bin/bash

# PostToolUse Hook: 记录活动并总结输出
# 统一处理所有工具：记录详细日志到progress.md，返回简洁摘要给用户

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具名称和参数
TOOL_NAME=$(echo "$CONTEXT" | jq -r '.toolName // ""')
TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')

# 提取执行结果
RESULT=$(echo "$CONTEXT" | jq -r '.result // ""')
ERROR=$(echo "$CONTEXT" | jq -r '.error // ""')

# 生成时间戳
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# ========== 错误检查（来自 summarize-output.sh）==========
# 检查是否有错误
if [ -n "$ERROR" ] && [ "$ERROR" != "null" ]; then
    # 有错误，只记录日志，不进行总结
    jq -n '{logged: true, summary: null}'
    exit 0
fi

# 检查结果中是否包含错误关键词
if echo "$RESULT" | grep -qiE "error|exception|failed|traceback"; then
    jq -n '{logged: true, summary: null}'
    exit 0
fi

# 提取输出长度
OUTPUT_LENGTH=${#RESULT}

# 初始化摘要变量
SUMMARY=""

# ========== 处理每个工具：记录日志 + 生成摘要 ==========
case "$TOOL_NAME" in
    database)
        # 提取参数
        QUERY=$(echo "$TOOL_ARGS" | jq -r '.query // ""')
        CONNECTION=$(echo "$TOOL_ARGS" | jq -r '.connection // "primary"')

        # 记录详细日志到 progress.md
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

        # 生成摘要
        ROW_COUNT=$(echo "$RESULT" | jq -r '.row_count // "N/A"' 2>/dev/null || echo "N/A")
        if [ "$ROW_COUNT" != "N/A" ] && [ "$ROW_COUNT" != "null" ]; then
            SUMMARY="数据库查询完成，返回 $ROW_COUNT 行结果"
        else
            SUMMARY="数据库查询完成"
        fi
        ;;

    execute_command)
        # 提取参数
        COMMAND=$(echo "$TOOL_ARGS" | jq -r '.command // ""')
        CMD_BASE=$(echo "$COMMAND" | awk '{print $1}')

        # 记录详细日志到 progress.md
        {
            echo ""
            echo "### 命令执行 ($TIMESTAMP)"
            echo ""
            echo "**命令**: \`$COMMAND\`"
            echo ""
        } >> progress.md

        # 生成摘要
        SUMMARY="命令 '$CMD_BASE' 执行完成"
        ;;

    file_reader)
        # 提取参数
        FILE_PATH=$(echo "$TOOL_ARGS" | jq -r '.file_path // ""')
        FILE_NAME=$(basename "$FILE_PATH")

        # 记录详细日志到 progress.md
        {
            echo ""
            echo "### 文件读取 ($TIMESTAMP)"
            echo ""
            echo "**文件**: \`$FILE_PATH\`"
            echo ""
        } >> progress.md

        # 生成摘要
        SUMMARY="已读取文件: $FILE_NAME"
        ;;

    python_sandbox)
        # 提取参数
        CODE=$(echo "$TOOL_ARGS" | jq -r '.code // ""')
        CODE_PREVIEW=$(echo "$CODE" | head -n 3)

        # 记录详细日志到 progress.md
        {
            echo ""
            echo "### Python执行 ($TIMESTAMP)"
            echo ""
            echo "**代码预览**:"
            echo ""
            echo '```python'
            echo "$CODE_PREVIEW"
            echo '```'
            echo ""
        } >> progress.md

        # 生成摘要（输出较短时不总结）
        if [ $OUTPUT_LENGTH -lt 100 ]; then
            jq -n '{logged: true, summary: null}'
            exit 0
        fi
        SUMMARY="Python代码执行完成，输出 ${OUTPUT_LENGTH} 字符"
        ;;

    skill_invoker)
        # 提取参数
        SKILL_NAME=$(echo "$TOOL_ARGS" | jq -r '.skill // ""')
        SKILL_ARGS=$(echo "$TOOL_ARGS" | jq -r '.args // ""')

        # 记录详细日志到 progress.md
        {
            echo ""
            echo "### Skill调用 ($TIMESTAMP)"
            echo ""
            echo "**Skill**: $SKILL_NAME"
            if [ -n "$SKILL_ARGS" ] && [ "$SKILL_ARGS" != "null" ]; then
                echo "**参数**: \`$SKILL_ARGS\`"
            fi
            echo ""
        } >> progress.md

        # 生成摘要
        SUMMARY="Skill '$SKILL_NAME' 执行完成"
        ;;

    skill_manager)
        # 提取参数
        ACTION=$(echo "$TOOL_ARGS" | jq -r '.action // ""')
        SOURCE=$(echo "$TOOL_ARGS" | jq -r '.source // ""')

        # 记录详细日志到 progress.md
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

        # 生成摘要
        SUMMARY="Skill $ACTION 完成"
        ;;

    vector_search)
        # 提取参数
        QUERY=$(echo "$TOOL_ARGS" | jq -r '.query // ""')
        TOP_K=$(echo "$TOOL_ARGS" | jq -r '.top_k // "5"')

        # 记录详细日志到 progress.md
        {
            echo ""
            echo "### 向量搜索 ($TIMESTAMP)"
            echo ""
            echo "**查询**: $QUERY"
            echo "**Top-K**: $TOP_K"
            echo ""
        } >> progress.md

        # 生成摘要
        SUMMARY="向量搜索完成，返回 Top-$TOP_K 结果"
        ;;

    web_search)
        # 提取参数
        QUERY=$(echo "$TOOL_ARGS" | jq -r '.query // ""')

        # 记录详细日志到 progress.md
        {
            echo ""
            echo "### Web搜索 ($TIMESTAMP)"
            echo ""
            echo "**查询**: $QUERY"
            echo ""
        } >> progress.md

        # 生成摘要
        RESULT_COUNT=$(echo "$RESULT" | jq -r '.results | length' 2>/dev/null || echo "0")
        SUMMARY="Web搜索完成，找到 $RESULT_COUNT 个结果"
        ;;

    web_reader)
        # 提取参数
        URL=$(echo "$TOOL_ARGS" | jq -r '.url // ""')

        # 记录详细日志到 progress.md
        {
            echo ""
            echo "### Web读取 ($TIMESTAMP)"
            echo ""
            echo "**URL**: $URL"
            echo ""
        } >> progress.md

        # 生成摘要
        if [ $OUTPUT_LENGTH -gt 500 ]; then
            WORD_COUNT=$((OUTPUT_LENGTH / 3))  # 粗略估计
            SUMMARY="网页内容读取完成，约 $WORD_COUNT 字"
        else
            SUMMARY="网页内容读取完成"
        fi
        ;;

    *)
        # 未知工具，记录基本日志
        {
            echo ""
            echo "### 工具调用 ($TIMESTAMP)"
            echo ""
            echo "**工具**: $TOOL_NAME"
            echo ""
        } >> progress.md

        # 生成摘要（输出较短时不总结）
        if [ $OUTPUT_LENGTH -lt 200 ]; then
            jq -n '{logged: true, summary: null}'
            exit 0
        fi
        SUMMARY="$TOOL_NAME 执行完成，输出 ${OUTPUT_LENGTH} 字符"
        ;;
esac

# 返回结果：既记录了日志，也生成了摘要
jq -n \
    --arg summary "$SUMMARY" \
    '{logged: true, summary: $summary}'
