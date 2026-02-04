#!/bin/bash

# Stop Hook: 保存会话摘要
# 会话结束时保存到memory/

# 生成时间戳
TIMESTAMP=$(date '+%Y-%m-%d')
TIME=$(date '+%H:%M:%S')

# 检查今天的memory文件是否存在
MEMORY_FILE="memory/$TIMESTAMP.md"

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

jq -n '{saved: true, file: "'"$MEMORY_FILE"'"'
