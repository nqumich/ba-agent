"""
配置管理系统单元测试

US-003: 配置管理系统
"""

import os
import pytest
import tempfile
import yaml
from pathlib import Path

from config import (
    Config,
    ConfigManager,
    DatabaseConfig,
    LLMConfig,
    VectorStoreConfig,
    DockerConfig,
    MemoryConfig,
    LoggingConfig,
    SecurityConfig,
    APIConfig,
    get_config,
    get_config_manager,
    reload_config,
)


class TestDatabaseConfig:
    """测试数据库配置"""

    def test_default_values(self):
        """测试默认值"""
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "ba_agent"
        assert config.pool_size == 10

    def test_custom_values(self):
        """测试自定义值"""
        config = DatabaseConfig(
            host="example.com",
            port=3306,
            username="admin",
            password="secret",
            database="test_db"
        )
        assert config.host == "example.com"
        assert config.port == 3306
        assert config.database == "test_db"


class TestLLMConfig:
    """测试 LLM 配置"""

    def test_default_values(self):
        """测试默认值"""
        config = LLMConfig()
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-5-20250929"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_temperature_validation(self):
        """测试温度参数验证"""
        # 有效值
        LLMConfig(temperature=0.0)
        LLMConfig(temperature=0.5)
        LLMConfig(temperature=1.0)

        # 无效值
        with pytest.raises(ValueError):
            LLMConfig(temperature=-0.1)
        with pytest.raises(ValueError):
            LLMConfig(temperature=1.1)


class TestDockerConfig:
    """测试 Docker 配置"""

    def test_default_values(self):
        """测试默认值"""
        config = DockerConfig()
        assert config.enabled is True
        assert config.image == "python:3.12-slim"
        assert config.memory_limit == "512m"
        assert config.network_disabled is True


class TestMemoryConfig:
    """测试记忆管理配置"""

    def test_default_values(self):
        """测试默认值"""
        config = MemoryConfig()
        assert config.enabled is True
        assert config.memory_dir == "./memory"
        assert config.max_context_tokens == 8000


class TestSecurityConfig:
    """测试安全配置"""

    def test_default_values(self):
        """测试默认值"""
        config = SecurityConfig()
        assert "localhost" in config.allowed_hosts
        assert "127.0.0.1" in config.allowed_hosts
        assert config.api_key_required is True
        assert config.rate_limit_enabled is True
        assert "ls" in config.command_whitelist


class TestAPIConfig:
    """测试 API 配置"""

    def test_default_values(self):
        """测试默认值"""
        config = APIConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.workers == 1
        assert "http://localhost:3000" in config.cors_origins


class TestConfig:
    """测试总配置"""

    def test_default_values(self):
        """测试默认值"""
        config = Config()
        assert config.environment == "development"
        assert config.debug is True
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.docker, DockerConfig)

    def test_environment_validation(self):
        """测试环境变量验证"""
        # 有效值
        Config(environment="development")
        Config(environment="production")
        Config(environment="test")

        # 无效值
        with pytest.raises(ValueError):
            Config(environment="invalid")

    def test_config_serialization(self):
        """测试配置序列化"""
        config = Config(
            environment="production",
            debug=False,
            llm=LLMConfig(provider="openai", model="gpt-4")
        )
        data = config.model_dump()
        assert data["environment"] == "production"
        assert data["debug"] is False
        assert data["llm"]["provider"] == "openai"

    def test_config_from_dict(self):
        """测试从字典创建配置"""
        data = {
            "environment": "production",
            "debug": False,
            "llm": {
                "provider": "openai",
                "model": "gpt-4"
            }
        }
        config = Config(**data)
        assert config.environment == "production"
        assert config.llm.provider == "openai"


class TestConfigManager:
    """测试配置管理器"""

    def test_find_config_file(self, tmp_path):
        """测试查找配置文件"""
        # 创建临时配置文件
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("# test config")

        manager = ConfigManager(str(config_file))
        assert manager.config_path == str(config_file)

    def test_load_yaml(self, tmp_path):
        """测试加载 YAML 配置"""
        config_file = tmp_path / "settings.yaml"
        config_data = {
            "environment": "production",
            "debug": False,
            "llm": {
                "provider": "openai",
                "model": "gpt-4"
            }
        }
        config_file.write_text(yaml.dump(config_data))

        manager = ConfigManager(str(config_file))
        loaded = manager.load_yaml()
        assert loaded["environment"] == "production"
        assert loaded["llm"]["provider"] == "openai"

    def test_load_yaml_nonexistent(self):
        """测试加载不存在的配置文件"""
        manager = ConfigManager("/nonexistent/config.yaml")
        loaded = manager.load_yaml()
        assert loaded == {}

    def test_parse_env_value(self):
        """测试解析环境变量值"""
        manager = ConfigManager()

        # 布尔值
        assert manager._parse_env_value("true") is True
        assert manager._parse_env_value("TRUE") is True
        assert manager._parse_env_value("1") is True
        assert manager._parse_env_value("false") is False
        assert manager._parse_env_value("0") is False

        # 数字
        assert manager._parse_env_value("123") == 123
        assert manager._parse_env_value("12.34") == 12.34

        # 字符串
        assert manager._parse_env_value("hello") == "hello"

    def test_override_from_env(self, tmp_path, monkeypatch):
        """测试环境变量覆盖"""
        # 创建基础配置文件
        config_file = tmp_path / "settings.yaml"
        config_data = {
            "environment": "development",
            "llm": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-5-20250929"
            }
        }
        config_file.write_text(yaml.dump(config_data))

        # 设置环境变量
        monkeypatch.setenv("BA_ENVIRONMENT", "production")
        monkeypatch.setenv("BA_LLM__PROVIDER", "openai")
        monkeypatch.setenv("BA_DEBUG", "false")
        monkeypatch.setenv("BA_LLM__TEMPERATURE", "0.5")

        manager = ConfigManager(str(config_file))
        merged = manager._override_from_env(config_data)

        assert merged["environment"] == "production"
        assert merged["llm"]["provider"] == "openai"
        assert merged["debug"] is False
        assert merged["llm"]["temperature"] == 0.5

    def test_load_config(self, tmp_path):
        """测试加载配置"""
        config_file = tmp_path / "settings.yaml"
        config_data = {
            "environment": "production",
            "debug": False,
            "database": {
                "host": "db.example.com",
                "port": 3306
            }
        }
        config_file.write_text(yaml.dump(config_data))

        manager = ConfigManager(str(config_file))
        config = manager.load()

        assert config.environment == "production"
        assert config.debug is False
        assert config.database.host == "db.example.com"
        assert config.database.port == 3306

    def test_load_config_caching(self, tmp_path):
        """测试配置缓存"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("environment: production")

        manager = ConfigManager(str(config_file))
        config1 = manager.load()
        config2 = manager.load()

        # 应该返回同一个对象
        assert config1 is config2

    def test_reload_config(self, tmp_path):
        """测试重新加载配置"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("environment: production")

        manager = ConfigManager(str(config_file))
        config1 = manager.load()

        # 修改配置文件
        config_file.write_text("environment: development")

        # 重新加载
        config2 = manager.reload()

        assert config1.environment == "production"
        assert config2.environment == "development"

    def test_get_api_key(self, tmp_path, monkeypatch):
        """测试获取 API 密钥"""
        config_file = tmp_path / "settings.yaml"
        config_data = {
            "llm": {
                "provider": "anthropic",
                "api_key": "config-key"
            }
        }
        config_file.write_text(yaml.dump(config_data))

        manager = ConfigManager(str(config_file))

        # 优先使用环境变量
        monkeypatch.setenv("BA_ANTHROPIC_API_KEY", "env-key")
        assert manager.get_api_key("anthropic") == "env-key"

        # 环境变量不存在时使用配置文件
        monkeypatch.delenv("BA_ANTHROPIC_API_KEY")
        # 重新加载以清除缓存
        manager._config = None
        assert manager.get_api_key("anthropic") == "config-key"

    def test_get_all_api_keys(self, tmp_path, monkeypatch):
        """测试获取所有 API 密钥"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("")

        manager = ConfigManager(str(config_file))

        monkeypatch.setenv("BA_ANTHROPIC_API_KEY", "anthropic-key")
        monkeypatch.setenv("BA_OPENAI_API_KEY", "openai-key")

        keys = manager.get_all_api_keys()
        assert keys["anthropic"] == "anthropic-key"
        assert keys["openai"] == "openai-key"

    def test_save_config(self, tmp_path):
        """测试保存配置"""
        config_file = tmp_path / "settings.yaml"

        manager = ConfigManager(str(config_file))
        manager._config = Config(
            environment="production",
            debug=False,
            llm=LLMConfig(provider="openai")
        )
        manager.save()

        # 验证保存的文件
        with open(config_file) as f:
            saved_data = yaml.safe_load(f)

        assert saved_data["environment"] == "production"
        assert saved_data["llm"]["provider"] == "openai"


class TestGlobalConfig:
    """测试全局配置函数"""

    def test_get_config(self):
        """测试获取全局配置"""
        config = get_config()
        assert isinstance(config, Config)

    def test_get_config_manager(self):
        """测试获取全局配置管理器"""
        manager = get_config_manager()
        assert isinstance(manager, ConfigManager)

    def test_config_manager_singleton(self):
        """测试配置管理器单例"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        assert manager1 is manager2

    def test_reload_global_config(self):
        """测试重新加载全局配置"""
        config1 = get_config()
        config2 = reload_config()
        # 应该返回新的配置对象
        assert config1 is not config2


class TestEnvironmentOverrides:
    """测试环境变量覆盖"""

    def test_full_override_flow(self, tmp_path, monkeypatch):
        """测试完整的环境变量覆盖流程"""
        # 创建配置文件
        config_file = tmp_path / "settings.yaml"
        config_data = {
            "environment": "development",
            "debug": True,
            "llm": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
                "temperature": 0.7
            },
            "database": {
                "host": "localhost",
                "port": 5432
            }
        }
        config_file.write_text(yaml.dump(config_data))

        # 设置环境变量覆盖
        monkeypatch.setenv("BA_ENVIRONMENT", "production")
        monkeypatch.setenv("BA_DEBUG", "false")
        monkeypatch.setenv("BA_LLM__PROVIDER", "openai")
        monkeypatch.setenv("BA_LLM__MODEL", "gpt-4")
        monkeypatch.setenv("BA_DATABASE__HOST", "db.example.com")
        monkeypatch.setenv("BA_DATABASE__PORT", "3306")

        # 加载配置
        manager = ConfigManager(str(config_file))
        config = manager.load()

        # 验证覆盖
        assert config.environment == "production"
        assert config.debug is False
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"
        assert config.database.host == "db.example.com"
        assert config.database.port == 3306


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
