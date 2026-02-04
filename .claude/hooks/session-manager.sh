#!/bin/bash

# Session Manager Hook: 统一会话管理和进度跟踪
# 整合会话摘要保存、完成度检查、Skill执行进度更新

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取事件类型
EVENT=$(echo "$CONTEXT" | jq -r '.eventName // ""')

case "$EVENT" in
    PostToolUse)
        # PostToolUse: 更新 skill_invoker 执行进度
        TOOL_NAME=$(echo "$CONTEXT" | jq -r '.toolName // ""')

        if [ "$TOOL_NAME" = "skill_invoker" ]; then
            TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')
            SKILL_NAME=$(echo "$TOOL_ARGS" | jq -r '.skill // ""')
            TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

            # 记录 Skill 执行到 progress.md
            {
                echo ""
                echo "### $TIMESTAMP - Skill 执行结果"
                echo ""
                echo "执行 Skill: **$SKILL_NAME**"
                echo "参数: \`$TOOL_ARGS\`"
                echo "结果: $(echo "$CONTEXT" | jq -r '.result // "Success"')"
                echo ""
            } >> progress.md

            # 可选: 根据 Skill 结果更新 task_plan.md
            # 这里可以添加更复杂的逻辑来自动更新计划状态
        fi
        jq -n '{tracked: true}'
        ;;

    Stop)
        # Stop: 会话结束 - 保存会话摘要并检查完成度
        TIMESTAMP=$(date '+%Y-%m-%d')
        TIME=$(date '+%H:%M:%S')
        MEMORY_FILE="memory/$TIMESTAMP.md"

        # 检查今天的memory文件是否存在
        if [ ! -f "$MEMORY_FILE" ]; then
            # 创建今日memory文件
            cat > "$MEMORY_FILE" << EOF
# 会话记录 - $TIMESTAMP

## 会话时间

- **开始**: $TIME
- **结束**: (待会话结束更新)

## 工作内容

### 完成的任务

-

### 重要发现

-

### 待解决问题

-

EOF
        fi

        # 更新会话摘要
        {
            echo ""
            echo "## 会话结束 - $TIME"
            echo ""
            echo "会话已正常结束。"
            echo ""
        } >> "$MEMORY_FILE"

        # 检查 task_plan.md 完成度
        if [ -f "task_plan.md" ]; then
            UNDONE=$(grep -c "^\- \[ \]" task_plan.md || echo "0")
            TOTAL=$(grep -c "^\- \[" task_plan.md || echo "0")

            if [ "$UNDONE" -gt 0 ]; then
                PERCENT=$(( ($TOTAL - $UNDONE) * 100 / $TOTAL ))

                # 追加完成度检查结果
                {
                    echo ""
                    echo "### 任务完成度检查"
                    echo ""
                    echo "总任务数: $TOTAL"
                    echo "已完成: $(($TOTAL - $UNDONE))"
                    echo "未完成: $UNDONE"
                    echo "完成度: ${PERCENT}%"
                    echo ""
                    echo "## 未完成的任务:"
                    grep "^\- \[ \]" task_plan.md
                    echo ""
                    echo "---"
                    echo ""
                    echo "建议: 请继续完成未完成的任务，或更新 task_plan.md 调整计划。"
                } >> "$MEMORY_FILE"

                # 同时输出到 stop-message.txt 供 Claude CLI 显示
                mkdir -p .claude
                {
                    echo "# 任务完成度检查"
                    echo ""
                    echo "总任务数: $TOTAL"
                    echo "已完成: $(($TOTAL - $UNDONE))"
                    echo "未完成: $UNDONE"
                    echo "完成度: ${PERCENT}%"
                    echo ""
                    echo "## 未完成的任务:"
                    grep "^\- \[ \]" task_plan.md
                    echo ""
                    echo "---"
                    echo ""
                    echo "建议: 请继续完成未完成的任务，或更新 task_plan.md 调整计划。"
                } > .claude/stop-message.txt

                jq -n \
                    --arg warning "$UNDONE tasks remaining" \
                    '{saved: true, file: "'"$MEMORY_FILE"'", warning: $warning}'
            else
                jq -n '{saved: true, file: "'"$MEMORY_FILE"'", message: "All tasks completed!"}'
            fi
        else
            jq -n '{saved: true, file: "'"$MEMORY_FILE"'"}'
        fi
        ;;
esac
