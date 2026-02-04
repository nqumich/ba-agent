#!/bin/bash

# PostToolUse Hook: 更新进度
# Skill 执行后更新 task_plan.md

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具名称
TOOL_NAME=$(echo "$CONTEXT" | jq -r '.toolName // ""')

# 提取工具参数
TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')

# 只在 invoke_skill 时更新
if [ "$TOOL_NAME" = "invoke_skill" ]; then
    # 提取 Skill 名称
    SKILL_NAME=$(echo "$TOOL_ARGS" | jq -r '.skill // ""')

    # 记录到 progress.md
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
    echo "" >> progress.md
    echo "### $TIMESTAMP - Skill 执行" >> progress.md
    echo "" >> progress.md
    echo "执行 Skill: **$SKILL_NAME**" >> progress.md
    echo "参数: \`$TOOL_ARGS\`" >> progress.md
    echo "结果: $(echo "$CONTEXT" | jq -r '.result // "Success"')" >> progress.md

    # 检查是否需要更新 task_plan.md (可以添加更复杂的逻辑)
    # 这里只是示例，实际可以根据 Skill 结果更新计划状态
fi

# 返回允许继续
jq -n '{block: false}'
