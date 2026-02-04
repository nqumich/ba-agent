#!/bin/bash

# PreToolUse Hook: 检查SQL注入
# 在查询数据库前检查SQL语句安全性

# 从 stdin 读取上下文
CONTEXT=$(cat)

# 提取工具参数
TOOL_ARGS=$(echo "$CONTEXT" | jq -r '.toolArgs // {}')

# 提取查询语句
QUERY=$(echo "$TOOL_ARGS" | jq -r '.query // ""')

# 检查查询类型（只允许 SELECT/WITH）
QUERY_UPPER=$(echo "$QUERY" | tr '[:lower:]' '[:upper:]')

# 允许的关键字开头
ALLOWED_PREFIXES=("SELECT" "WITH" "SHOW" "DESCRIBE" "EXPLAIN")

# 检查是否以允许的关键字开头
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
        # 发现危险关键字
        jq -n \
            --arg reason "Query contains dangerous keyword '$keyword'. Only SELECT/WITH queries are allowed." \
            '{block: true, reason: $reason}'
        exit 0
    fi
done

# 如果不是安全的查询，阻止执行
if [ "$IS_SAFE" = false ]; then
    jq -n \
        --arg reason "Query must start with SELECT, WITH, SHOW, DESCRIBE, or EXPLAIN" \
        '{block: true, reason: $reason}'
    exit 0
fi

# 允许执行
jq -n '{block: false}'
