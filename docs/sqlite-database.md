# SQLite 数据库管理指南

## 概述

ba-agent 使用 SQLite 作为默认数据库，**无需外部数据库服务器**。

## 数据库文件位置

```
ba-agent/
├── data/
│   ├── sqlite.db           # 默认 SQLite 数据库
│   ├── memory.db          # 记忆索引数据库
│   └── {connection}.db     # 其他连接的数据库文件
```

## 连接管理

### 自动连接
- SQLite 连接在首次查询时自动创建
- 连接在应用程序生命周期内保持打开
- 应用关闭时自动清理

### 手动清理
```python
from tools.database import _close_connections
_close_connections()  # 关闭所有连接
```

## 数据持久化策略

### 保留数据（推荐）

**数据库文件默认保留**，原因：

1. **性能优化**: 避免每次会话重新索引
2. **跨会话查询**: 可查询历史数据
3. **向量索引**: 保留已计算的向量嵌入

### 清理选项

**如果需要清理数据库**：

```python
import os
from pathlib import Path

# 方案 1: 清理所有数据库
data_dir = Path("./data")
for db_file in data_dir.glob("*.db"):
    db_file.unlink()
    print(f"已删除: {db_file}")

# 方案 2: 清理特定数据库
Path("./data/sqlite.db").unlink()  # 删除默认数据库
```

**清理时机**：
- **开发环境**: 可定期清理
- **生产环境**: 应保留数据库文件
- **隐私敏感数据**: 会话结束后立即清理

## sqlite-vec 向量搜索

### 可选加速

ba-agent 支持 `sqlite-vec` 扩展用于加速向量搜索：

```bash
pip install sqlite-vec
```

### Fallback 机制

- **有 sqlite-vec**: 使用原生向量搜索（快速）
- **无 sqlite-vec**: 使用纯 Python 实现（兼容）

### 检查状态

```python
try:
    import sqlite_vec
    print("sqlite-vec 可用")
except ImportError:
    print("sqlite-vec 不可用，使用纯 Python 实现")
```

## 数据库配置

### 默认配置 (config.py)

```python
database:
  type: "sqlite"           # 默认使用 SQLite
  path: "./data/ba_agent.db"  # 数据库文件路径
```

### PostgreSQL 配置（可选）

```python
database:
  type: "postgresql"
  host: "localhost"
  port: 5432
  username: "postgres"
  password: ""
  database: "ba_agent"
```

### 环境变量覆盖

```bash
# 使用 SQLite（默认）
export BA_DATABASE_TYPE=sqlite
export BA_DATABASE_PATH=./data/custom.db

# 使用 PostgreSQL
export BA_DATABASE_TYPE=postgresql
export BA_DATABASE_HOST=localhost
export BA_DATABASE_PORT=5432
```

## 会话管理

### 数据库生命周期

```
应用启动
    ↓
首次查询 → 创建 SQLite 连接 → 创建/打开数据库文件
    ↓
应用运行期间 → 保持连接打开 → 可重复查询
    ↓
应用关闭 → 关闭所有连接 → 数据文件保留在磁盘
```

### 跨会话数据

```
会话 1: 创建表 → 插入数据 → 关闭应用
    ↓
    ↓ (数据库文件保留)
    ↓
会话 2: 启动应用 → 打开数据库 → 可查询会话1的数据
```

## 故障排查

### 数据库锁定

**错误**: `database is locked`

**原因**: 多个进程同时写入

**解决**:
```python
# 增加超时时间
conn = sqlite3.connect(db_path, timeout=30.0)
```

### 文件权限

**错误**: `attempt to write a readonly database`

**解决**:
```bash
chmod 644 ./data/sqlite.db
```

### 目录不存在

**错误**: `no such table`

**解决**:
```python
from pathlib import Path
Path("./data").mkdir(exist_ok=True)
```
