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

### 自动清理机制（v3.1+）

**数据库文件默认启用自动清理**，清理策略：

1. **基于时间**: 删除超过 `max_age_hours` 的临时数据库文件（默认 24 小时）
2. **基于大小**: 如果数据库目录总大小超过 `max_total_size_mb`，删除最旧的文件（默认 500MB）
3. **排除保护**: 主要数据库文件（sqlite.db, memory.db）不会被删除

### 清理配置

**在 config/settings.yaml 中配置**：

```yaml
database:
  type: sqlite
  path: ./data/ba_agent.db
  cleanup:
    enabled: true                    # 是否启用自动清理
    max_age_hours: 24.0              # 数据库文件最大保留时间（小时）
    max_total_size_mb: 500.0         # 数据库目录最大总大小（MB）
    cleanup_on_shutdown: true        # 关闭时是否清理
    exclude_files:                   # 清理时排除的文件列表
      - sqlite.db
      - memory.db
```

**通过环境变量覆盖**：

```bash
export BA_DATABASE__CLEANUP__ENABLED=true
export BA_DATABASE__CLEANUP__MAX_AGE_HOURS=12.0
export BA_DATABASE__CLEANUP__MAX_TOTAL_SIZE_MB=200.0
```

### 保留数据（可选）

**如果需要长期保留数据**，可以禁用自动清理：

```yaml
database:
  cleanup:
    enabled: false                   # 禁用自动清理
    cleanup_on_shutdown: false       # 关闭时不清理
```

### 手动清理

**如果需要手动清理数据库**：

```python
from tools.database import _cleanup_database_files, _cleanup_old_databases

# 方案 1: 清理过期的数据库文件
deleted_count = _cleanup_database_files(
    exclude=["sqlite.db", "memory.db"],
    max_age_hours=24.0
)
print(f"已删除 {deleted_count} 个数据库文件")

# 方案 2: 完整的定期清理
result = _cleanup_old_databases(
    max_age_hours=24.0,
    max_total_size_mb=500.0,
    dry_run=False  # 设置为 True 可以仅模拟运行
)
print(f"删除了 {len(result['deleted_files'])} 个文件")
print(f"释放了 {result['deleted_size_bytes'] / 1024 / 1024:.2f}MB 空间")
```

**清理时机**：
- **开发环境**: 可定期清理或启用自动清理
- **生产环境**: 建议禁用自动清理，定期手动备份
- **隐私敏感数据**: 可设置较短的 `max_age_hours`（如 1 小时）

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
  cleanup:
    enabled: true
    max_age_hours: 24.0
    max_total_size_mb: 500.0
    cleanup_on_shutdown: true
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

# 清理配置
export BA_DATABASE__CLEANUP__ENABLED=true
export BA_DATABASE__CLEANUP__MAX_AGE_HOURS=12.0
export BA_DATABASE__CLEANUP__CLEANUP_ON_SHUTDOWN=true

# 使用 PostgreSQL
export BA_DATABASE_TYPE=postgresql
export BA_DATABASE_HOST=localhost
export BA_DATABASE_PORT=5432
```

## 定期清理机制

### 自动清理任务

**启动时自动启动**：
- API 服务启动时自动启动定期清理后台任务
- 默认清理间隔：`max_age_hours`（默认 24 小时）
- 清理策略：删除过期的临时数据库文件

**清理流程**：
```
应用启动
    ↓
启动定期清理任务（后台）
    ↓
每隔 N 小时检查一次
    ↓
    ├─→ 删除超过 max_age_hours 的文件
    ├─→ 检查总大小是否超过 max_total_size_mb
    │       ↓ 是
    │   删除最旧的文件直到大小满足要求
    ↓
重复...
    ↓
应用关闭 → 停止清理任务 → 执行最终清理
```

### 手动触发清理

**Python API**：
```python
from tools.database import _cleanup_old_databases

# 执行清理
result = _cleanup_old_databases(
    max_age_hours=24.0,
    max_total_size_mb=500.0
)

# 查看结果
print(f"删除的文件: {result['deleted_files']}")
print(f"释放的空间: {result['deleted_size_bytes'] / 1024 / 1024:.2f}MB")
print(f"清理前大小: {result['total_size_before_mb']:.2f}MB")
print(f"清理后大小: {result['total_size_after_mb']:.2f}MB")
```

## 会话管理

### 数据库生命周期

```
应用启动
    ↓
启动定期清理任务
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
