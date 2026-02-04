#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MAX_ITERATIONS=${1:-50}

echo "🚀 Starting BA-Agent Ralph Loop"
echo "📁 Project root: $PROJECT_ROOT"
echo "🔄 Max iterations: $MAX_ITERATIONS"
echo ""

cd "$PROJECT_ROOT"

for i in $(seq 1 $MAX_ITERATIONS); do
  echo "═══ Iteration $i ═══"

  # 读取当前进度
  if [ -f "scripts/ralph/progress.txt" ]; then
    echo "📊 Progress:"
    head -20 "scripts/ralph/progress.txt"
    echo ""
  fi

  # 读取当前任务状态
  python3 -c "
import json
import sys
sys.path.insert(0, '.')

try:
    with open('scripts/ralph/prd.json', 'r', encoding='utf-8') as f:
        prd = json.load(f)

    pending = [s for s in prd['userStories'] if not s.get('passes', False)]
    completed = [s for s in prd['userStories'] if s.get('passes', False)]

    print(f'📋 Pending tasks: {len(pending)}')
    print(f'✅ Completed tasks: {len(completed)}')

    if pending:
        print('🔜 Next task (priority {}): {}'.format(
            '1' if pending[0]['priority'] == 1 else '2' if pending[0]['priority'] == 2 else '3',
            pending[0]['id']
        ))
        print('   Title:', pending[0]['title'])
    else:
        print('✅ All tasks completed!')
        sys.exit(0)

except Exception as e:
    print(f'❌ Error reading PRD: {e}')
    sys.exit(1)
"

  echo ""

  # 执行 Claude Code (假设已配置)
  OUTPUT=$(cat scripts/ralph/prompt.md | claude --continue 2>&1) || true

  # 显示输出
  echo "$OUTPUT"
  echo ""

  # 检查是否完成
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo "✅ All tasks completed!"
    exit 0
  fi

  # 检查是否有致命错误
  if echo "$OUTPUT" | grep -q "FATAL ERROR"; then
    echo "❌ Fatal error encountered, stopping"
    exit 1
  fi

  sleep 2
done

echo "⚠️  Max iterations reached"
exit 1
