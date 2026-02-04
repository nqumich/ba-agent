# MCP 服务器配置指南

## 概述

BA-Agent 使用 Z.ai (智谱) 提供的 MCP (Model Context Protocol) 服务来实现 Web 搜索和网页读取功能。

## MCP 服务说明

### Web Search Prime
- **功能**: 执行实时网络搜索
- **MCP 工具名**: `mcp__web-search-prime__webSearchPrime`
- **项目工具**: `web_search` (tools/web_search.py)

### Web Reader
- **功能**: 读取网页内容并转换为 Markdown
- **MCP 工具名**: `mcp__web_reader__webReader`
- **项目工具**: `web_reader` (tools/web_reader.py)

## 配置步骤

### 1. 获取 Z.ai API Key

1. 访问 [Z.ai 开放平台](https://open.bigmodel.cn/usercenter/apikeys)
2. 注册/登录账号
3. 创建新的 API Key
4. 复制 API Key

### 2. 配置环境变量

在项目根目录创建 `.env` 文件（或编辑现有的）：

```bash
# Z.ai MCP API Key
ZAI_MCP_API_KEY=your_zai_mcp_api_key_here

# 启用 MCP 环境（可选，用于测试）
MCP_AVAILABLE=true
```

### 3. 配置 Claude Code MCP

如果你使用 Claude Code，需要添加 MCP 服务器配置：

```bash
# 添加 Web Search Prime
claude mcp add -s user -t http web-search-prime \
  https://open.bigmodel.cn/api/mcp/web_search_prime/mcp \
  --header "Authorization: Bearer ${ZAI_MCP_API_KEY}"

# 添加 Web Reader
claude mcp add -s user -t http web-reader \
  https://open.bigmodel.cn/api/mcp/web_reader/mcp \
  --header "Authorization: Bearer ${ZAI_MCP_API_KEY}"
```

### 4. 验证配置

运行测试以验证 MCP 配置：

```bash
# 设置环境变量后运行测试
export MCP_AVAILABLE=true
pytest tests/tools/test_web_search.py::TestWebSearchIntegration -v
pytest tests/tools/test_web_reader.py::TestWebReaderIntegration -v
```

## API Key 安全说明

⚠️ **重要安全提示**:

1. **不要提交 API Key 到 Git**: `.env` 文件已在 `.gitignore` 中
2. **个人使用**: 每个用户应配置自己的 API Key
3. **默认 Key**: 项目开发者的默认 Key (`73231d06783c49dc8cffe93f5af84b76.TMoZVZLnUiAnKIFd`) 仅限开发者个人使用
4. **生产环境**: 生产部署时应使用环境变量或密钥管理服务

## 测试模式

### Mock 模式（默认）
当 `MCP_AVAILABLE` 未设置或为 `false` 时，工具使用模拟实现：
- web_search: 返回模拟搜索结果
- web_reader: 返回模拟网页内容

适用于：
- 单元测试
- 开发环境（无需网络）
- CI/CD 流水线

### Real 模式
当 `MCP_AVAILABLE=true` 时，工具调用真实的 MCP 服务：
- web_search: 执行真实的网络搜索
- web_reader: 读取真实的网页内容

适用于：
- 集成测试
- 生产环境
- 实际使用场景

## 测试覆盖率

| 模式 | 测试数 | 通过 | 跳过 |
|------|--------|------|------|
| Mock 模式 (默认) | 475 | 469 | 6 |
| Real 模式 (MCP_AVAILABLE=true) | 475 | 475 | 0 |

## 故障排除

### 问题 1: MCP 测试被跳过
**症状**: 测试显示 "SKIPPED - 需要 MCP 环境"

**解决**:
```bash
export MCP_AVAILABLE=true
pytest tests/tools/test_web_search.py::TestWebSearchIntegration -v
```

### 问题 2: API Key 无效
**症状**: 403 或 401 错误

**解决**:
1. 检查 API Key 是否正确
2. 确认 API Key 已启用
3. 检查账户余额/配额

### 问题 3: 网络连接失败
**症状**: 超时或连接错误

**解决**:
1. 检查网络连接
2. 确认可以访问 `open.bigmodel.cn`
3. 检查防火墙设置

## 相关文档

- [Z.ai 开放平台文档](https://open.bigmodel.cn/dev/api)
- [MCP 协议规范](https://modelcontextprotocol.io)
- [项目工具文档](../README.md#工具说明)
