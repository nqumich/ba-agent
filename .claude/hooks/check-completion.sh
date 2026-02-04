#!/bin/bash

# Stop Hook: 检查完成度
# 会话结束时检查任务完成状态

# 读取 task_plan.md
if [ -f "task_plan.md" ]; then
    # 统计未完成的任务
    UNDONE=$(grep -c "^\- \[ \]" task_plan.md || echo "0")
    TOTAL=$(grep -c "^\- \[" task_plan.md || echo "0")

    if [ "$UNDONE" -gt 0 ]; then
        # 有未完成的任务
        PERCENT=$(( ($TOTAL - $UNDONE) * 100 / $TOTAL ))
        echo "# 任务完成度检查

总任务数: $TOTAL
已完成: $(($TOTAL - $UNDONE))
未完成: $UNDONE
完成度: ${PERCENT}%

## 未完成的任务:
$(grep "^\- \[ \]" task_plan.md)

---

建议: 请继续完成未完成的任务，或更新 task_plan.md 调整计划。
" > .claude/stop-message.txt

        # 不阻止结束，但记录警告
        jq -n \
            --arg warning "$UNDONE tasks remaining" \
            '{block: false, warning: $warning}'
    else
        # 所有任务完成
        jq -n '{block: false, message: "All tasks completed!"}'
    fi
else
    # 没有 task_plan.md，不检查
    jq -n '{block: false}'
fi
