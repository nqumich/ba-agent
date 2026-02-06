"""
FastAPI 应用入口。

说明：
- Dockerfile 默认启动命令为：uvicorn backend.main:app
- 本文件提供：
  - GET /         简单 Web UI（输入框）
  - GET /health   健康检查（docker-compose healthcheck）
  - POST /api/chat 调用 BAAgent 并返回结果
"""

from __future__ import annotations

import threading
from typing import Optional, Dict, Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.agents.agent import create_agent, BAAgent
from config import get_config


app = FastAPI(title="BA-Agent", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入")
    conversation_id: Optional[str] = Field(default=None, description="会话 ID（多轮对话复用）")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.on_event("startup")
def _startup() -> None:
    # 创建单例 agent，避免每次请求都重新加载 skills / memory 等。
    app.state.agent = create_agent()
    app.state.agent_lock = threading.Lock()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    cfg = get_config()
    provider = (cfg.llm.provider or "").strip().lower()
    model = cfg.llm.model

    # 最小可用页面：一个输入框 + 输出区域
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>BA-Agent</title>
    <style>
      body {{
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
        margin: 0;
        background: #0b1220;
        color: #e5e7eb;
      }}
      .wrap {{
        max-width: 900px;
        margin: 0 auto;
        padding: 28px 18px 40px;
      }}
      .card {{
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 10px 30px rgba(0,0,0,.35);
      }}
      h1 {{
        font-size: 20px;
        margin: 0 0 8px;
      }}
      .meta {{
        font-size: 12px;
        color: #9ca3af;
        margin-bottom: 16px;
      }}
      .row {{
        display: flex;
        gap: 10px;
      }}
      input {{
        flex: 1;
        padding: 12px 12px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(0,0,0,0.25);
        color: #e5e7eb;
        outline: none;
      }}
      button {{
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(99,102,241,0.9);
        color: white;
        cursor: pointer;
      }}
      button:disabled {{
        opacity: .55;
        cursor: not-allowed;
      }}
      pre {{
        white-space: pre-wrap;
        word-break: break-word;
        background: rgba(0,0,0,0.25);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 12px;
        padding: 12px;
        margin: 14px 0 0;
        min-height: 220px;
      }}
      .hint {{
        margin-top: 10px;
        font-size: 12px;
        color: #9ca3af;
      }}
      a {{ color: #93c5fd; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h1>BA-Agent（Web Demo）</h1>
        <div class="meta">provider: <b>{provider}</b> · model: <b>{model}</b></div>
        <div class="row">
          <input id="msg" placeholder="在这里输入一句话，比如：你好" />
          <button id="send">发送</button>
        </div>
        <pre id="out">准备就绪。请输入内容并点击发送。</pre>
        <div class="hint">
          - 接口：<code>POST /api/chat</code> · 健康检查：<code>/health</code> · Swagger：<a href="/docs">/docs</a>
        </div>
      </div>
    </div>
    <script>
      const $msg = document.getElementById('msg');
      const $send = document.getElementById('send');
      const $out = document.getElementById('out');
      let conversationId = null;

      function append(text) {{
        $out.textContent = ($out.textContent || '') + "\\n\\n" + text;
      }}

      async function send() {{
        const message = ($msg.value || '').trim();
        if (!message) return;
        $send.disabled = true;
        append("你： " + message);
        $msg.value = '';

        try {{
          const resp = await fetch('/api/chat', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ message, conversation_id: conversationId }})
          }});
          const data = await resp.json();
          if (!resp.ok) {{
            append("系统错误： " + (data.detail || JSON.stringify(data)));
            return;
          }}
          conversationId = data.conversation_id || conversationId;
          append("BA-Agent： " + (data.response || ''));
        }} catch (e) {{
          append("网络错误： " + (e && e.message ? e.message : String(e)));
        }} finally {{
          $send.disabled = false;
        }}
      }}

      $send.addEventListener('click', send);
      $msg.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter') send();
      }});
    </script>
  </body>
</html>
"""


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> Dict[str, Any]:
    agent: BAAgent = app.state.agent
    lock: threading.Lock = app.state.agent_lock

    def _invoke() -> Dict[str, Any]:
        with lock:
            return agent.invoke(payload.message, conversation_id=payload.conversation_id)

    result = await run_in_threadpool(_invoke)
    # agent.invoke 自己会返回 success/error 字段；这里统一为 200，交由前端展示。
    return result

