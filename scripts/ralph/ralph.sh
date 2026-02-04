#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MAX_ITERATIONS=${1:-50}

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Starting BA-Agent Ralph Loop"
echo "📁 Project root: $PROJECT_ROOT"
echo "🔄 Max iterations: $MAX_ITERATIONS"
echo ""

cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if claude CLI is available
if ! command -v claude &> /dev/null; then
    echo -e "${RED}❌ Claude CLI not found!${NC}"
    echo "Please install Claude Code CLI first"
    exit 1
fi

# Install dependencies if not already installed
if ! python -c "import langchain" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Installing dependencies...${NC}"
    pip install -q -r requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
fi

echo -e "${GREEN}✅ Environment ready${NC}"
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
  echo "═══ Iteration $i ═══"

  # 读取当前进度
  if [ -f "scripts/ralph/progress.txt" ]; then
    echo "📊 Progress:"
    head -20 "scripts/ralph/progress.txt"
    echo ""
  fi

  # 读取当前任务状态 (使用 venv 中的 python)
  python -c "
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

  # 执行 Claude Code
  OUTPUT=$(cat scripts/ralph/prompt.md | claude --continue 2>&1) || true

  # 显示输出
  echo "$OUTPUT"
  echo ""

  # 检查是否完成
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo -e "${GREEN}✅ All tasks completed!${NC}"
    exit 0
  fi

  # 检查是否有致命错误
  if echo "$OUTPUT" | grep -q "FATAL ERROR"; then
    echo -e "${RED}❌ Fatal error encountered, stopping${NC}"
    exit 1
  fi

  # 检查是否有新的提交需要推送
  if git diff --quiet origin/master..master 2>/dev/null; then
    :
  else
    echo -e "${YELLOW}📤 Pushing changes to remote...${NC}"
    git push origin master || echo -e "${YELLOW}⚠️  Git push failed, continuing...${NC}"
  fi

  sleep 2
done

echo -e "${YELLOW}⚠️  Max iterations reached${NC}"
exit 1
