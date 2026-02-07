"""
配置管理系统

支持从 YAML 文件、环境变量加载配置，支持密钥管理
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

T = TypeVar('T', bound=BaseModel)


class DatabaseSecurityConfig(BaseModel):
    """数据库安全配置"""

    enabled: bool = Field(default=True, description="是否启用安全检查")
    allowed_statements: list[str] = Field(
        default_factory=lambda: ["SELECT", "WITH"],
        description="允许的 SQL 语句类型"
    )
    forbidden_keywords: list[str] = Field(
        default_factory=lambda: ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"],
        description="禁止的关键字"
    )
    query_timeout: int = Field(default=30, description="查询超时时间（秒）")
    max_rows: int = Field(default=10000, description="最大返回行数")


class DatabaseConnectionConfig(BaseModel):
    """单个数据库连接配置"""

    type: str = Field(default="sqlite", description="数据库类型 (sqlite, postgresql, clickhouse)")
    # SQLite 配置
    path: str = Field(default="./data/ba_agent.db", description="SQLite 数据库文件路径")
    # PostgreSQL/ClickHouse 配置
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, description="数据库端口")
    username: str = Field(default="", description="数据库用户名")
    password: str = Field(default="", description="数据库密码")
    database: str = Field(default="ba_agent", description="数据库名称")
    pool_size: int = Field(default=10, description="连接池大小")
    max_overflow: int = Field(default=20, description="最大溢出连接数")


class DatabaseCleanupConfig(BaseModel):
    """数据库清理配置"""

    enabled: bool = Field(default=True, description="是否启用自动清理")
    max_age_hours: float = Field(default=1.0, description="数据库文件最大保留时间（小时）")
    max_total_size_mb: float = Field(default=100.0, description="数据库目录最大总大小（MB）")
    cleanup_on_shutdown: bool = Field(default=True, description="关闭时是否清理所有数据库文件")
    exclude_files: list[str] = Field(
        default_factory=lambda: ["memory.db"],
        description="清理时排除的文件列表（默认保留 memory.db）"
    )


class DatabaseConfig(BaseModel):
    """数据库配置

    默认使用 SQLite（嵌入式数据库，无需外部服务器）
    可配置 PostgreSQL 或 ClickHouse 用于企业级部署
    """

    # 数据库类型
    type: str = Field(default="sqlite", description="数据库类型 (sqlite, postgresql, clickhouse)")

    # SQLite 配置（默认）
    path: str = Field(default="./data/ba_agent.db", description="SQLite 数据库文件路径")

    # PostgreSQL/ClickHouse 配置（可选）
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, description="数据库端口")
    username: str = Field(default="", description="数据库用户名")
    password: str = Field(default="", description="数据库密码")
    database: str = Field(default="ba_agent", description="数据库名称")
    pool_size: int = Field(default=10, description="连接池大小")
    max_overflow: int = Field(default=20, description="最大溢出连接数")

    # 多数据库连接配置
    connections: Dict[str, DatabaseConnectionConfig] = Field(
        default_factory=dict,
        description="多数据库连接配置"
    )

    # 安全配置
    security: DatabaseSecurityConfig = Field(
        default_factory=DatabaseSecurityConfig,
        description="数据库安全配置"
    )

    # 清理配置
    cleanup: DatabaseCleanupConfig = Field(
        default_factory=DatabaseCleanupConfig,
        description="数据库清理配置"
    )


class LLMConfig(BaseModel):
    """LLM 模型配置"""

    provider: str = Field(default="anthropic", description="LLM 提供商 (anthropic, openai, zhipuai, google)")
    model: str = Field(default="claude-sonnet-4-5-20250929", description="模型名称")
    api_key: str = Field(default="", description="API 密钥")
    base_url: Optional[str] = Field(default=None, description="API 基础 URL (例如: https://api.lingyaai.cn/v1/messages)")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="温度参数")
    max_tokens: int = Field(default=4096, description="最大生成 tokens")
    timeout: int = Field(default=120, description="请求超时时间（秒）")


class VectorStoreConfig(BaseModel):
    """向量数据库配置"""

    type: str = Field(default="chroma", description="向量数据库类型")
    persist_directory: str = Field(default="./data/vector_db", description="持久化目录")
    embedding_model: str = Field(default="text-embedding-ada-002", description="嵌入模型")
    collection_name: str = Field(default="ba_agent", description="集合名称")


class DockerConfig(BaseModel):
    """Docker 隔离环境配置"""

    enabled: bool = Field(default=True, description="是否启用 Docker 隔离")
    image: str = Field(default="python:3.12-slim", description="Docker 镜像")
    memory_limit: str = Field(default="512m", description="内存限制")
    cpu_limit: str = Field(default="1.0", description="CPU 限制")
    timeout: int = Field(default=300, description="执行超时时间（秒）")
    network_disabled: bool = Field(default=True, description="是否禁用网络")


class MemoryFlushConfig(BaseModel):
    """Memory Flush 配置"""

    enabled: bool = Field(default=True, description="是否启用 Memory Flush")
    soft_threshold_tokens: int = Field(default=4000, description="软阈值 token 数")
    reserve_tokens_floor: int = Field(default=2000, description="保留 token 数量")
    min_memory_count: int = Field(default=3, description="最少记忆数量")
    max_memory_age_hours: float = Field(default=24.0, description="记忆最大年龄（小时）")
    llm_model: str = Field(default="glm-4.7-flash", description="LLM 提取模型")
    llm_timeout: int = Field(default=30, description="LLM 超时（秒）")
    compaction_keep_recent: int = Field(default=10, description="压缩对话时保留最近的消息数量")


class MemorySearchChunkingConfig(BaseModel):
    """记忆搜索分块配置"""

    tokens: int = Field(default=400, description="文本分块 token 数")
    overlap: int = Field(default=80, description="重叠 token 数")


class MemorySearchQueryConfig(BaseModel):
    """记忆搜索查询配置"""

    max_results: int = Field(default=6, description="默认返回结果数")
    min_score: float = Field(default=0.35, description="最小相关性分数")


class MemorySearchHybridConfig(BaseModel):
    """记忆搜索混合配置"""

    enabled: bool = Field(default=True, description="是否启用混合搜索")
    vector_weight: float = Field(default=0.7, description="向量搜索权重")
    text_weight: float = Field(default=0.3, description="文本搜索权重")


class MemorySearchConfig(BaseModel):
    """Memory Search 配置"""

    enabled: bool = Field(default=True, description="是否启用记忆搜索")
    provider: str = Field(default="auto", description="embedding 提供商")
    model: str = Field(default="text-embedding-3-small", description="embedding 模型")
    fallback: str = Field(default="local", description="回退提供商")
    chunking: MemorySearchChunkingConfig = Field(
        default_factory=MemorySearchChunkingConfig,
        description="分块配置"
    )
    query: MemorySearchQueryConfig = Field(
        default_factory=MemorySearchQueryConfig,
        description="查询配置"
    )
    hybrid: MemorySearchHybridConfig = Field(
        default_factory=MemorySearchHybridConfig,
        description="混合搜索配置"
    )


class MemoryWatcherConfig(BaseModel):
    """Memory Watcher 配置"""

    enabled: bool = Field(default=False, description="是否启用文件监听（默认禁用）")
    watch_paths: list[str] = Field(
        default_factory=lambda: ["./memory"],
        description="监听的路径列表"
    )
    debounce_seconds: float = Field(default=2.0, description="防抖秒数")
    check_interval_seconds: float = Field(default=5.0, description="检查间隔秒数")


class MemoryIndexRotationConfig(BaseModel):
    """记忆索引轮换配置"""

    enabled: bool = Field(default=True, description="是否启用索引轮换")
    max_size_mb: float = Field(default=50.0, description="单个索引文件最大大小（MB）")
    index_prefix: str = Field(default="memory", description="索引文件前缀")
    index_dir: str = Field(default="memory/.index", description="索引目录")


class MemoryConfig(BaseModel):
    """记忆管理配置"""

    enabled: bool = Field(default=True, description="是否启用记忆管理")
    memory_dir: str = Field(default="./memory", description="记忆文件目录")
    daily_log_format: str = Field(default="%Y-%m-%d", description="每日日志文件名格式")
    max_context_tokens: int = Field(default=8000, description="最大上下文 tokens")
    flush: MemoryFlushConfig = Field(default_factory=MemoryFlushConfig, description="Memory Flush 配置")
    search: MemorySearchConfig = Field(default_factory=MemorySearchConfig, description="Memory Search 配置")
    watcher: MemoryWatcherConfig = Field(default_factory=MemoryWatcherConfig, description="Memory Watcher 配置")
    index_rotation: MemoryIndexRotationConfig = Field(
        default_factory=MemoryIndexRotationConfig,
        description="索引轮换配置"
    )


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
    file: Optional[str] = Field(default="./logs/ba_agent.log", description="日志文件路径")
    max_bytes: int = Field(default=10485760, description="日志文件最大大小（10MB）")
    backup_count: int = Field(default=5, description="日志备份数量")


class SecurityConfig(BaseModel):
    """安全配置"""

    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"], description="允许的主机")
    api_key_required: bool = Field(default=True, description="是否需要 API 密钥")
    rate_limit_enabled: bool = Field(default=True, description="是否启用速率限制")
    rate_limit_per_minute: int = Field(default=60, description="每分钟请求限制")
    command_whitelist: list[str] = Field(
        default_factory=lambda: ["ls", "cat", "echo", "grep", "head", "tail"],
        description="允许的命令列表"
    )


class APIConfig(BaseModel):
    """API 服务配置"""

    host: str = Field(default="0.0.0.0", description="API 服务主机")
    port: int = Field(default=8000, description="API 服务端口")
    workers: int = Field(default=1, description="工作进程数")
    reload: bool = Field(default=False, description="是否自动重载")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"], description="CORS 允许的源")


class Config(BaseModel):
    """BA-Agent 总配置"""

    # 环境配置
    environment: str = Field(default="development", description="运行环境 (development, production)")
    debug: bool = Field(default=True, description="调试模式")

    # 各模块配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """验证环境变量"""
        valid_envs = ["development", "production", "test"]
        if v not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v


class ConfigManager:
    """
    配置管理器

    支持从 YAML 文件加载配置，支持环境变量覆盖
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: YAML 配置文件路径，默认为 config/settings.yaml
        """
        self.config_path = config_path or self._find_config_file()
        self._config: Optional[Config] = None

    @staticmethod
    def _find_config_file() -> str:
        """
        查找配置文件

        按以下顺序查找：
        1. ./config/settings.yaml
        2. ./settings.yaml
        3. ~/.config/ba_agent/settings.yaml
        """
        possible_paths = [
            "./config/settings.yaml",
            "./settings.yaml",
            os.path.expanduser("~/.config/ba_agent/settings.yaml"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # 如果都没找到，使用默认路径
        return "./config/settings.yaml"

    def load_yaml(self) -> Dict[str, Any]:
        """
        从 YAML 文件加载配置

        Returns:
            配置字典
        """
        if not os.path.exists(self.config_path):
            return {}

        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _get_env_prefix(self, config_key: str) -> str:
        """
        获取环境变量前缀

        Args:
            config_key: 配置键（如 "database.host"）

        Returns:
            环境变量名（如 "BA_DATABASE_HOST"）
        """
        return f"BA_{config_key.upper().replace('.', '_')}"

    def _override_from_env(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        从环境变量覆盖配置

        支持嵌套配置，使用 __ 分隔层级，例如：
        BA_DATABASE__HOST=localhost
        BA_LLM__API_KEY=sk-xxx

        Args:
            config_dict: 原始配置字典

        Returns:
            覆盖后的配置字典
        """
        result = config_dict.copy()

        for env_key, env_value in os.environ.items():
            if env_key.startswith("BA_"):
                # 移除 BA_ 前缀
                key = env_key[3:]
                # 将 __ 替换为 .
                key = key.replace("__", ".").lower()
                # 按点分割路径
                parts = key.split(".")

                # 设置嵌套值
                current = result
                for i, part in enumerate(parts[:-1]):
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = self._parse_env_value(env_value)

        return result

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        """
        解析环境变量值

        Args:
            value: 环境变量值

        Returns:
            解析后的值
        """
        # 尝试解析为布尔值
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # 尝试解析为数字
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # 返回字符串
        return value

    def load(self) -> Config:
        """
        加载配置

        从 YAML 文件加载配置，并使用环境变量覆盖

        Returns:
            配置对象
        """
        if self._config is not None:
            return self._config

        # 加载 YAML 配置
        yaml_config = self.load_yaml()

        # 环境变量覆盖
        merged_config = self._override_from_env(yaml_config)

        # 创建配置对象
        self._config = Config(**merged_config)
        return self._config

    def reload(self) -> Config:
        """
        重新加载配置

        Returns:
            配置对象
        """
        self._config = None
        return self.load()

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        获取 API 密钥

        优先级：
        1. 环境变量 BA_{PROVIDER}_API_KEY
        2. 配置文件中的值

        Args:
            provider: 提供商名称 (anthropic, openai, zhipuai)

        Returns:
            API 密钥
        """
        # 首先检查环境变量
        env_key = f"BA_{provider.upper()}_API_KEY"
        api_key = os.environ.get(env_key)
        if api_key:
            return api_key

        # 然后检查配置
        config = self.load()
        return config.llm.api_key if config.llm.provider == provider else None

    def get_all_api_keys(self) -> Dict[str, str]:
        """
        获取所有配置的 API 密钥

        Returns:
            提供商 -> API 密钥的映射
        """
        keys = {}
        for provider in ["anthropic", "openai", "zhipuai"]:
            key = self.get_api_key(provider)
            if key:
                keys[provider] = key
        return keys

    def get_mcp_config(self) -> Dict[str, Any]:
        """
        获取 MCP 服务器配置

        Returns:
            MCP 配置字典，包含 api_key, available 状态等
        """
        return {
            "api_key": os.environ.get("ZAI_MCP_API_KEY", ""),
            "available": os.environ.get("MCP_AVAILABLE", "false").lower() == "true",
            "web_search_url": "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp",
            "web_reader_url": "https://open.bigmodel.cn/api/mcp/web_reader/mcp",
        }

    def save(self, path: Optional[str] = None) -> None:
        """
        保存当前配置到 YAML 文件

        Args:
            path: 保存路径，默认为原配置文件路径
        """
        save_path = path or self.config_path

        # 确保目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # 转换为字典并保存
        config_dict = self.load().model_dump(exclude_none=True)

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_dict, f, allow_unicode=True, default_flow_style=False)


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    获取全局配置对象

    Args:
        config_path: 可选的配置文件路径

    Returns:
        配置对象
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(config_path)

    return _config_manager.load()


def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器

    Returns:
        配置管理器
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager()

    return _config_manager


def reload_config() -> Config:
    """
    重新加载全局配置

    Returns:
        配置对象
    """
    global _config_manager

    if _config_manager is not None:
        return _config_manager.reload()

    return get_config()
