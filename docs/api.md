# BA-Agent API 文档

> **Version**: v2.3.0
> **Base URL**: `http://localhost:8000`
> **Last Updated**: 2026-02-08

BA-Agent REST API 提供文件管理、Agent 交互、Skills 管理、用户认证等功能。

---

## 认证

API 使用 JWT (JSON Web Token) 进行认证。除健康检查和登录端点外，所有端点都需要认证。

### 获取访问令牌

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

**响应**:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "user_id": "u_001",
    "username": "admin",
    "email": "admin@ba-agent.local",
    "role": "admin",
    "permissions": ["read", "write", "delete", "admin"]
  }
}
```

### 使用令牌

在请求头中添加 `Authorization`:

```http
Authorization: Bearer <access_token>
```

### 刷新令牌

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "<refresh_token>"
}
```

---

## 健康检查

### GET /api/v1/health

检查服务健康状态。

**响应**:

```json
{
  "status": "healthy",
  "version": "2.2.0",
  "timestamp": "2026-02-07T12:00:00Z"
}
```

---

## 认证端点

### POST /api/v1/auth/login

用户登录，获取访问令牌。

**请求体**:

```json
{
  "username": "string",
  "password": "string"
}
```

### POST /api/v1/auth/refresh

刷新访问令牌。

**请求体**:

```json
{
  "refresh_token": "string"
}
```

### GET /api/v1/auth/me

获取当前用户信息。

**需要认证**: ✅

### POST /api/v1/auth/logout

用户登出。

**需要认证**: ✅

---

## 文件管理

所有文件管理端点都需要认证。

### POST /api/v1/files/upload

上传文件。

**需要认证**: ✅

**支持格式**: `.xlsx`, `.xls`, `.csv`, `.json`

**请求**: `multipart/form-data`

```bash
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@data.xlsx" \
  -F "session_id=session_123"
```

### GET /api/v1/files

列出文件。

**需要认证**: ✅

**查询参数**:
- `category`: 文件类别 (可选)
- `session_id`: 会话 ID (可选)
- `limit`: 最大返回数量 (默认 100)

### GET /api/v1/files/{file_id}/metadata

获取文件元数据。

**需要认证**: ✅

### GET /api/v1/files/{file_id}/download

下载文件。

**需要认证**: ✅

### DELETE /api/v1/files/{file_id}

删除文件。

**需要认证**: ✅

---

## Agent 交互

### POST /api/v1/agent/query

向 Agent 发送查询。

**需要认证**: ✅

**请求体**:

```json
{
  "message": "string",
  "model": "string (optional)",
  "api_key": "string (optional)",
  "conversation_id": "string (optional)",
  "file_context": "object (optional)",
  "session_id": "string (optional)",
  "user_id": "string (optional)"
}
```

**响应**:

```json
{
  "success": true,
  "data": {
    "response": "Agent 响应内容（包含 HTML/图表）",
    "conversation_id": "conv_123",
    "duration_ms": 1234,
    "tool_calls": [],
    "artifacts": [],
    "metadata": {
      "action_type": "tool_call | complete",
      "current_round": 1,
      "task_analysis": "思维链分析",
      "execution_plan": "执行计划",
      "status": "processing | complete",
      "contains_html": true,
      "recommended_questions": ["问题1", "问题2"],
      "download_links": ["file.xlsx"]
    }
  }
}
```

**响应格式说明**:

- `action_type`: `tool_call` 表示正在处理，`complete` 表示完成
- `contains_html`: 响应是否包含 HTML/ECharts 代码
- `recommended_questions`: 推荐的后续问题（仅 complete 时）
- `download_links`: 可下载的文件列表（仅 complete 时）

### POST /api/v1/agent/conversation/start

开始新对话。

**需要认证**: ✅

### GET /api/v1/agent/conversation/{id}/history

获取对话历史。

**需要认证**: ✅

### DELETE /api/v1/agent/conversation/{id}

结束对话。

**需要认证**: ✅

### GET /api/v1/agent/status

获取 Agent 服务状态。

**需要认证**: ✅

---

## Skills 管理

### GET /api/v1/skills

获取所有 Skills 列表。

### GET /api/v1/skills/categories

获取 Skill 类别。

### GET /api/v1/skills/{name}

获取 Skill 详情。

### GET /api/v1/skills/{name}/config

获取 Skill 配置。

**需要认证**: ✅

### PUT /api/v1/skills/{name}/config

更新 Skill 配置。

**需要认证**: ✅

### POST /api/v1/skills/activate

激活 Skill。

**需要认证**: ✅

### POST /api/v1/skills/install

安装外部 Skill。

**需要认证**: ✅

### DELETE /api/v1/skills/{name}

卸载 Skill。

**需要认证**: ✅

### GET /api/v1/skills/status/overview

获取 Skills 系统状态。

---

## 错误响应

所有错误响应遵循统一格式：

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": {}
  }
}
```

### 常见错误代码

| 状态码 | 错误代码 | 说明 |
|--------|----------|------|
| 401 | UNAUTHORIZED | 未认证或令牌无效 |
| 401 | TOKEN_EXPIRED | 令牌已过期 |
| 403 | FORBIDDEN | 权限不足 |
| 404 | NOT_FOUND | 资源未找到 |
| 429 | RATE_LIMIT_EXCEEDED | 请求过于频繁 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

---

## 速率限制

API 实施速率限制以防止滥用：

- **IP 级别**: 默认 60 请求/分钟
- **用户级别**: 默认 120 请求/分钟
- **排除路径**: `/api/v1/health`, `/api/v1/auth/login`

速率限制响应头：

```http
X-RateLimit-IP-Limit: 60
X-RateLimit-IP-Remaining: 45
X-RateLimit-User-Limit: 120
```

超过限制时返回 429 状态码：

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "请求过于频繁，请稍后再试",
    "retry_after": 30
  }
}
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BA_JWT_SECRET_KEY` | JWT 密钥 | ba-agent-secret-key-change-in-production |
| `BA_JWT_EXPIRE_MINUTES` | 访问令牌过期时间（分钟） | 60 |
| `BA_JWT_REFRESH_DAYS` | 刷新令牌过期时间（天） | 7 |
| `BA_RATE_LIMIT_IP_PER_MINUTE` | IP 速率限制 | 60 |
| `BA_RATE_LIMIT_USER_PER_MINUTE` | 用户速率限制 | 120 |

---

## 默认用户

| 用户名 | 密码 | 角色 | 权限 |
|--------|------|------|------|
| admin | admin123 | admin | read, write, delete, admin |
| user | user123 | user | read, write |

⚠️ **生产环境必须修改默认密码！**

---

## 内部架构 (v2.3.0)

### 上下文协调机制

**ContextCoordinator** 是 v2.3.0 新增的协调层，负责统一协调 LangGraph、ContextManager 和 Memory Flush 的交互。

**核心功能**：
- 准备发送给 LLM 的消息列表
- 协调文件清理和上下文构建
- 确保系统提示在第一位
- 保持消息顺序

**文件清理统一入口**：
- 所有文件内容清理通过 `ContextCoordinator.prepare_messages()`
- 委托给 `ContextManager.clean_langchain_messages()` 执行
- 清理超过 2000 字符的文件内容，替换为梗概

### 相关文件

| 文件 | 说明 |
|------|------|
| backend/api/services/ba_agent.py | BAAgentService 服务类 |
| backend/agents/agent.py | BAAgent 主实现 |
| backend/core/context_coordinator.py | 上下文协调器 (v2.3.0 新增) |
| backend/core/context_manager.py | 上下文管理器 |
| docs/context-management.md | 上下文管理详细文档 |
| docs/response-flow.md | 响应格式流转文档 |

---
