#!/bin/bash

# Session Manager Hook: 统一会话管理和进度跟踪
# 整合会话摘要保存、完成度检查、Skill执行进度更新

# Python JSON 辅助脚本路径
JSON_HELPER="$(dirname "$0")/json_helper.py"

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取事件类型
EVENT=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".eventName" "")

case "$EVENT" in
    PostToolUse)
        # PostToolUse: 更新 skill_invoker 执行进度
        TOOL_NAME=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".toolName" "")

        if [ "$TOOL_NAME" = "skill_invoker" ]; then
            TOOL_ARGS=$(echo "$CONTEXT" | python3 "$JSON_HELPER" ".toolArgs" "{}")
            SKILL_NAME=$(echo "$TOOL_ARGS" | python3 "$JSON_HELPER" ".skill" "")
            TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

            # 记录 Skill 执行到 progress.md
            {
                echo ""
                echo "### $TIMESTAMP - Skill 执行结果"
                echo ""
                echo "执行 Skill: **$SKILL_NAME**"
                echo "参数: \`$TOOL_ARGS\`"
                echo "结果: $(echo "$CONTEXT" | python3 "$JSON_HELPER" ".result" "Success" "")"
                echo ""
            } >> progress.md
        fi
        python3 -c 'import json; print(json.dumps({"tracked": True}))'
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

        # 显示会话结束检查清单
        CHECKLIST_FILE="$HOME/.ba-agent-dev/SESSION_CHECKLIST.md"
        if [ -f "$CHECKLIST_FILE" ]; then
            mkdir -p .claude
            {
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "📋 会话结束检查清单"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
                head -50 "$CHECKLIST_FILE"
                echo ""
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo ""
                echo "💡 快速检查命令:"
                echo "  pytest -q --tb=no              # 运行测试"
                echo "  git status                     # 查看变更"
                echo "  cat ~/.ba-agent-dev/SESSION_CHECKLIST.md  # 查看完整清单"
                echo ""
            } > .claude/stop-message.txt
        fi

        # 检查 task_plan.md 完成度
        if [ -f "task_plan.md" ]; then
            UNDONE=$(grep -c "^\- \[ \]" task_plan.md 2>/dev/null || echo "0")
            TOTAL=$(grep -c "^\- \[" task_plan.md 2>/dev/null || echo "0")

            if [ "$UNDONE" -gt 0 ] && [ "$TOTAL" -gt 0 ]; then
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

                # 同时追加到 stop-message.txt
                {
                    echo ""
                    echo "# 任务完成度检查"
                    echo ""
                    echo "总任务数: $TOTAL"
                    echo "已完成: $(($TOTAL - $UNDONE))"
                    echo "未完成: $UNDONE"
                    echo "完成度: ${PERCENT}%"
                    echo ""
                    echo "## 未完成的任务:"
                    grep "^\- \[ \]" task_plan.md | head -10
                    if [ $(grep -c "^\- \[ \]" task_plan.md) -gt 10 ]; then
                        echo ""
                        echo "... (还有 $((UNDONE - 10)) 个未完成任务)"
                    fi
                    echo ""
                    echo "---"
                    echo ""
                } >> .claude/stop-message.txt

                python3 -c "import json; print(json.dumps({'saved': True, 'file': '$MEMORY_FILE', 'warning': '$UNDONE tasks remaining'}, ensure_ascii=False))"
            else
                {
                    echo ""
                    echo "✅ 所有任务已完成！"
                    echo ""
                } >> .claude/stop-message.txt
                python3 -c "import json; print(json.dumps({'saved': True, 'file': '$MEMORY_FILE', 'message': 'All tasks completed!'}, ensure_ascii=False))"
            fi
        else
            python3 -c "import json; print(json.dumps({'saved': True, 'file': '$MEMORY_FILE'}, ensure_ascii=False))"
        fi
        ;;
esac
