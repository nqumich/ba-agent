#!/bin/bash
# 检查后端是否返回 200，并打印响应（用于排查 500 问题）
set -e
echo "请求 http://127.0.0.1:8000/api/v1/chat ..."
code=$(curl -s -o /tmp/ba_chat_resp.txt -w "%{http_code}" -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}')
echo "HTTP 状态码: $code"
echo "响应内容:"
cat /tmp/ba_chat_resp.txt
echo ""
if [ "$code" = "200" ]; then
  echo "正常：后端返回 200。若前端仍显示 500，请检查前端是否通过 Vite 代理访问（不要直接请求其他地址）。"
else
  echo "异常：后端返回了 $code。请确认已重启后端：pkill -f uvicorn; ./venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
fi
