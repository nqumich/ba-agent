"""
文件系统配置加载器

从 YAML 文件加载文件系统配置
支持跨平台存储路径
"""

import os
from pathlib import Path
from typing import Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from backend.models.filestore import FileStoreConfig

# 导入存储配置模块
try:
    from backend.storage.config import get_storage_dir
    STORAGE_MODULE_AVAILABLE = True
except ImportError:
    STORAGE_MODULE_AVAILABLE = False


class FileStoreConfigLoader:
    """
    文件系统配置加载器

    支持从 YAML 文件加载配置，如果 yaml 不可用则使用默认配置
    """

    DEFAULT_CONFIG_PATH = Path("config/filestore.yaml")

    @classmethod
    def load(
        cls,
        config_path: Optional[Path] = None
    ) -> FileStoreConfig:
        """
        加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            FileStoreConfig 配置对象
        """
        if config_path is None:
            config_path = cls.DEFAULT_CONFIG_PATH

        if not YAML_AVAILABLE:
            return cls._get_default_config()

        if not config_path.exists():
            return cls._get_default_config()

        try:
            return cls._load_from_yaml(config_path)
        except Exception as e:
            # 配置文件损坏，使用默认配置
            return cls._get_default_config()

    @classmethod
    def _load_from_yaml(cls, config_path: Path) -> FileStoreConfig:
        """从 YAML 文件加载配置"""
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        if 'filestore' not in data:
            return cls._get_default_config()

        config_data = data['filestore']

        # 转换路径 - 支持环境变量和 ~ 展开
        base_dir_str = config_data.get('base_dir', '~/.local/share/ba-agent')

        # 检查环境变量
        env_dir = os.getenv("BA_STORAGE_DIR")
        if env_dir:
            base_dir_str = env_dir

        # 展开路径
        base_dir = Path(base_dir_str).expanduser().resolve()

        # 如果使用存储配置模块，让它处理默认路径
        if STORAGE_MODULE_AVAILABLE and base_dir_str == "~/.local/share/ba-agent":
            base_dir = get_storage_dir()

        # 提取 TTL 配置
        ttl_config = {}
        categories = config_data.get('categories', {})
        for category_name, category_config in categories.items():
            ttl_hours = category_config.get('ttl_hours', 24)
            ttl_config[category_name] = ttl_hours

        # 提取文件大小限制
        max_file_sizes = {}
        for category_name, category_config in categories.items():
            max_size_mb = category_config.get('max_size_mb', 100)
            max_file_sizes[category_name] = max_size_mb * 1024 * 1024

        return FileStoreConfig(
            base_dir=base_dir,
            max_total_size_gb=config_data.get('max_total_size_gb', 10),
            cleanup_interval_hours=config_data.get('cleanup_interval_hours', 1),
            cleanup_threshold_percent=config_data.get('cleanup_threshold_percent', 90.0),
            ttl_config=ttl_config,
            max_file_sizes=max_file_sizes
        )

    @classmethod
    def _get_default_config(cls) -> FileStoreConfig:
        """获取默认配置"""
        # 使用跨平台默认目录
        if STORAGE_MODULE_AVAILABLE:
            base_dir = get_storage_dir()
        else:
            # 回退方案
            import platform
            if platform.system() == "Darwin":  # macOS
                base_dir = Path.home() / "Library" / "Application Support" / "ba-agent"
            elif platform.system() == "Windows":
                appdata = os.getenv("APPDATA", "")
                base_dir = Path(appdata) / "ba-agent" if appdata else Path.home() / ".ba-agent"
            else:  # Linux
                xdg_data = os.getenv("XDG_DATA_HOME")
                base_dir = Path(xdg_data) / "ba-agent" if xdg_data else Path.home() / ".local" / "share" / "ba-agent"

        return FileStoreConfig(base_dir=base_dir)

    @classmethod
    def save_default_config(cls, output_path: Optional[Path] = None) -> None:
        """
        保存默认配置到文件

        Args:
            output_path: 输出文件路径
        """
        if not YAML_AVAILABLE:
            raise RuntimeError("yaml module not available")

        if output_path is None:
            output_path = cls.DEFAULT_CONFIG_PATH

        # 创建默认配置
        # 使用跨平台默认路径
        if STORAGE_MODULE_AVAILABLE:
            default_base_dir = str(get_storage_dir())
        else:
            default_base_dir = '~/.local/share/ba-agent'  # 将在运行时解析

        default_config = {
            'filestore': {
                'base_dir': default_base_dir,
                'max_total_size_gb': 10,
                'cleanup_interval_hours': 1,
                'cleanup_threshold_percent': 90,
                'categories': {
                    'artifact': {
                        'dir': 'artifacts',
                        'max_size_mb': 100,
                        'ttl_hours': 24
                    },
                    'upload': {
                        'dir': 'uploads',
                        'max_size_mb': 50,
                        'ttl_hours': 168
                    },
                    'report': {
                        'dir': 'reports',
                        'max_size_mb': 50,
                        'ttl_hours': 720
                    },
                    'chart': {
                        'dir': 'charts',
                        'max_size_mb': 10,
                        'ttl_hours': 168
                    },
                    'cache': {
                        'dir': 'cache',
                        'max_size_mb': 10,
                        'ttl_hours': 1
                    },
                    'temp': {
                        'dir': 'temp',
                        'max_size_mb': 50,
                        'ttl_hours': 0
                    },
                    'memory': {
                        'dir': 'memory',
                        'ttl_hours': 8760
                    },
                    'checkpoint': {
                        'dir': 'temp/checkpoints',
                        'ttl_hours': 24
                    }
                }
            }
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)


__all__ = [
    "FileStoreConfigLoader",
]
