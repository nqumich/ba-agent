#!/bin/bash

# PreToolUse Hook: 工具参数变更提醒
# 当修改工具相关文件时，提醒同步更新 docs/response-flow.md 和 docs/prompts.md

# Python JSON 辅助脚本路径
JSON_HELPER="$(dirname "$0")/json_helper.py"

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具名称和参数
TOOL_NAME=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".toolName" "")
TOOL_ARGS=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".toolArgs" "")

# 需要同步更新的文件
PROMPTS_FILE="docs/prompts.md"
RESPONSE_FLOW_FILE="docs/response-flow.md"

# 检查结果
REMINDER_MESSAGE=""

case "$TOOL_NAME" in
    edit_file)
        FILE_PATH=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".file_path" "")

        # 检查是否修改了包含工具定义的文件
        if [[ "$FILE_PATH" == *"$PROMPTS_FILE"* ]]; then
            # 检查是否修改了工具相关部分
            if echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".old_string" "" 2>/dev/null | grep -qiE "tool|参数|argument|run_python|file_reader|query_database|web_search|web_reader"; then
                REMINDER_MESSAGE="检测到修改 $PROMPTS_FILE 中的工具参数定义，请确保同步更新 $RESPONSE_FLOW_FILE 的「工具调用参数规范」章节。"
            fi
        fi

        if [[ "$FILE_PATH" == *"$RESPONSE_FLOW_FILE"* ]]; then
            if echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".old_string" "" 2>/dev/null | grep -qiE "工具|参数|tool|argument"; then
                REMINDER_MESSAGE="检测到修改 $RESPONSE_FLOW_FILE 中的工具参数定义，请确保同步更新 $PROMPTS_FILE 的「工具使用指南」章节。"
            fi
        fi
        ;;

    write_file)
        FILE_PATH=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".file_path" "")

        # 新写文件如果是工具相关文件，也需要提醒
        if [[ "$FILE_PATH" == *"$PROMPTS_FILE"* ]] || [[ "$FILE_PATH" == *"$RESPONSE_FLOW_FILE"* ]]; then
            REMINDER_MESSAGE="正在重写工具相关文档，请确保 $PROMPTS_FILE 和 $RESPONSE_FLOW_FILE 中的工具参数定义保持一致。"
        fi
        ;;
esac

# 返回结果
if [ -n "$REMINDER_MESSAGE" ]; then
    # 显示提醒消息，但仍允许操作
    python3 -c "import json; print(json.dumps({'allowed': True, 'message': '$REMINDER_MESSAGE'}, ensure_ascii=False))"
else
    # 无需提醒
    python3 -c 'import json; print(json.dumps({"allowed": True}))'
fi
