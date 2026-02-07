"""
记忆索引数据库 Schema 定义

基于 clawdbot 的 memory schema 设计

支持索引轮换：当索引文件超过一定大小时，自动创建新的索引文件
"""

from pathlib import Path
from typing import Optional


# 数据库文件路径
DEFAULT_INDEX_PATH = "memory/.index/memory.db"

# 索引轮换相关
DEFAULT_MAX_INDEX_SIZE_MB = 50.0  # 单个索引文件最大大小（MB）


def get_default_index_path() -> Path:
    """
    获取默认索引路径（兼容旧代码）

    Returns:
        Path: 默认索引路径
    """
    # 尝试使用索引轮换管理器获取当前索引
    try:
        from .index_rotation import get_current_index_path
        return get_current_index_path()
    except Exception:
        # 回退到默认路径
        return Path(DEFAULT_INDEX_PATH)


def ensure_memory_index_schema(
    db,
    fts_table: str = "chunks_fts",
    fts_enabled: bool = True
) -> dict:
    """
    确保记忆索引数据库的 Schema 已创建

    Args:
        db: sqlite3 数据库连接
        fts_table: FTS5 表名
        fts_enabled: 是否启用 FTS5

    Returns:
        dict: 包含 fts_available 和 fts_error (如果失败) 的字典
    """
    # 创建 meta 表（存储元数据）
    db.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    # 创建 files 表（文件元数据）
    db.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            source TEXT NOT NULL DEFAULT 'memory',
            hash TEXT NOT NULL,
            mtime INTEGER NOT NULL,
            size INTEGER NOT NULL
        );
    """)

    # 创建 chunks 表（文本块）
    db.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'memory',
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            hash TEXT NOT NULL,
            text TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (path) REFERENCES files(path) ON DELETE CASCADE
        );
    """)

    # 创建 embedding_cache 表（向量缓存）
    db.execute("""
        CREATE TABLE IF NOT EXISTS embedding_cache (
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding TEXT NOT NULL,
            dims INTEGER,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (provider, model, content_hash)
        );
    """)

    # 创建索引
    db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_updated_at ON chunks(updated_at);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_embedding_cache_updated_at ON embedding_cache(updated_at);")

    # 创建 FTS5 全文搜索表
    fts_available = False
    fts_error = None

    if fts_enabled:
        try:
            db.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table} USING fts5(
                    text,
                    id UNINDEXED,
                    path UNINDEXED,
                    source UNINDEXED,
                    start_line UNINDEXED,
                    end_line UNINDEXED
                );
            """)
            fts_available = True
        except Exception as e:
            fts_available = False
            fts_error = str(e)

    # 确保必要的列存在（用于版本升级）
    _ensure_column(db, "files", "source", "TEXT NOT NULL DEFAULT 'memory'")
    _ensure_column(db, "chunks", "source", "TEXT NOT NULL DEFAULT 'memory'")

    return {
        "fts_available": fts_available,
        "fts_error": fts_error
    }


def _ensure_column(db, table: str, column: str, definition: str) -> None:
    """确保表中存在指定的列"""
    try:
        # 检查列是否已存在
        cursor = db.execute(f"PRAGMA table_info({table})")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if column not in existing_columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except Exception:
        # 如果出错，忽略（可能列已存在或其他问题）
        pass


def get_index_db_path(agent_id: Optional[str] = None, base_path: Optional[str] = None) -> Path:
    """
    获取索引数据库文件路径

    Args:
        agent_id: Agent ID（用于多 Agent 场景）
        base_path: 基础路径（默认使用 DEFAULT_INDEX_PATH）

    Returns:
        Path: 数据库文件路径
    """
    if base_path:
        path = Path(base_path)
    else:
        path = Path(DEFAULT_INDEX_PATH)

    # 如果路径包含 {agentId} 占位符，替换它
    if agent_id and "{agentId}" in str(path):
        path = Path(str(path).replace("{agentId}", agent_id))

    # 确保父目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    return path


def open_index_db(path: Optional[Path] = None, **kwargs) -> 'sqlite3.Connection':
    """
    打开索引数据库连接

    Args:
        path: 数据库文件路径，为 None 时使用默认路径
        **kwargs: 传递给 sqlite3.connect 的参数

    Returns:
        sqlite3.Connection: 数据库连接
    """
    import sqlite3

    if path is None:
        path = get_index_db_path()

    return sqlite3.connect(path, **kwargs)
