"""
嵌入提供商测试
"""

import os
import sqlite3
import pytest
from typing import List
from unittest.mock import Mock, patch, MagicMock

from backend.memory.embedding import (
    EmbeddingProvider,
    ZhipuEmbeddingProvider,
    OpenAIEmbeddingProvider,
    LocalEmbeddingProvider,
    FallbackEmbeddingProvider,
    create_embedding_provider,
    HAS_ZHIPU,
    HAS_OPENAI
)


class TestEmbeddingProvider:
    """测试嵌入提供商基类"""

    def test_compute_hash(self):
        """测试 hash 计算"""
        provider = MockProvider(model="test")
        hash1 = provider._compute_hash("test text")
        hash2 = provider._compute_hash("test text")
        hash3 = provider._compute_hash("different text")

        assert hash1 == hash2
        assert hash1 != hash3

    def test_serialize_parse_embedding(self):
        """测试嵌入向量序列化和解析"""
        provider = MockProvider(model="test")
        embedding = [0.1, 0.2, 0.3, -0.4]

        serialized = provider._serialize_embedding(embedding)
        assert serialized == "0.1,0.2,0.3,-0.4"

        parsed = provider._parse_embedding(serialized)
        assert parsed == embedding

    def test_encode_empty_list(self):
        """测试编码空列表"""
        provider = MockProvider(model="test")
        result = provider.encode([])
        assert result == []

    def test_encode_single_text(self):
        """测试编码单个文本"""
        provider = MockProvider(model="test")
        embedding = provider.encode_single("test text")

        assert len(embedding) == 3  # Mock 返回 3 维
        assert all(isinstance(x, float) for x in embedding)

    def test_cache_storage(self, tmp_path):
        """测试缓存存储"""
        db_path = tmp_path / "cache.db"
        db = sqlite3.connect(db_path)

        # 创建 schema
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

        provider = MockProvider(model="test", cache_db=db)
        texts = ["text1", "text2"]

        # 第一次编码
        result1 = provider.encode(texts)
        assert len(result1) == 2

        # 验证缓存已保存
        cursor = db.execute("SELECT COUNT(*) FROM embedding_cache")
        count = cursor.fetchone()[0]
        assert count == 2

        db.close()

    def test_cache_hit(self, tmp_path):
        """测试缓存命中"""
        db_path = tmp_path / "cache.db"
        db = sqlite3.connect(db_path)

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

        # 预先填充缓存
        provider = MockProvider(model="test", cache_db=db)
        text = "cached text"
        embedding = [1.0, 2.0, 3.0]

        db.execute("""
            INSERT INTO embedding_cache (provider, model, content_hash, embedding, dims, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (provider._provider_name, provider.model, provider._compute_hash(text),
              provider._serialize_embedding(embedding), len(embedding), 1000))
        db.commit()

        # 应该从缓存读取
        result = provider.encode([text])
        assert len(result) == 1
        assert result[0] == embedding

        # 确保没有调用实际的编码方法
        assert provider.encode_call_count == 0

        db.close()


class TestZhipuEmbeddingProvider:
    """测试智谱嵌入提供商"""

    @pytest.mark.skipif(not HAS_ZHIPU, reason="zhipuai not installed")
    def test_init_without_api_key(self):
        """测试无 API 密钥初始化"""
        with patch.dict(os.environ, {"ZHIPUAI_API_KEY": ""}):
            with pytest.raises(ValueError, match="API key"):
                provider = ZhipuEmbeddingProvider(api_key=None)
                _ = provider.client

    @pytest.mark.skipif(not HAS_ZHIPU, reason="zhipuai not installed")
    def test_encode_batch_success(self):
        """测试成功编码批次"""
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2, 0.3]),
            Mock(embedding=[0.4, 0.5, 0.6])
        ]

        with patch.object(ZhipuEmbeddingProvider, "client", create=True):
            provider = ZhipuEmbeddingProvider(api_key="test-key")
            provider.client.embeddings.create = Mock(return_value=mock_response)

            result = provider._encode_batch(["text1", "text2"])
            assert len(result) == 2
            assert result[0] == [0.1, 0.2, 0.3]
            assert result[1] == [0.4, 0.5, 0.6]

    @pytest.mark.skipif(not HAS_ZHIPU, reason="zhipuai not installed")
    def test_encode_batch_failure(self):
        """测试编码失败"""
        with patch.object(ZhipuEmbeddingProvider, "client", create=True):
            provider = ZhipuEmbeddingProvider(api_key="test-key")
            provider.client.embeddings.create = Mock(side_effect=Exception("API Error"))

            with pytest.raises(RuntimeError, match="ZhipuAI embedding failed"):
                provider._encode_batch(["text"])


class TestOpenAIEmbeddingProvider:
    """测试 OpenAI 嵌入提供商"""

    @pytest.mark.skipif(not HAS_OPENAI, reason="openai not installed")
    def test_init_without_api_key(self):
        """测试无 API 密钥初始化"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with pytest.raises(ValueError, match="API key"):
                provider = OpenAIEmbeddingProvider(api_key=None)
                _ = provider.client

    @pytest.mark.skipif(not HAS_OPENAI, reason="openai not installed")
    def test_encode_batch_success(self):
        """测试成功编码批次"""
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2, 0.3]),
            Mock(embedding=[0.4, 0.5, 0.6])
        ]

        with patch.object(OpenAIEmbeddingProvider, "client", create=True):
            provider = OpenAIEmbeddingProvider(api_key="test-key")
            provider.client.embeddings.create = Mock(return_value=mock_response)

            result = provider._encode_batch(["text1", "text2"])
            assert len(result) == 2
            assert result[0] == [0.1, 0.2, 0.3]
            assert result[1] == [0.4, 0.5, 0.6]

    @pytest.mark.skipif(not HAS_OPENAI, reason="openai not installed")
    def test_custom_base_url(self):
        """测试自定义基础 URL"""
        provider = OpenAIEmbeddingProvider(
            api_key="test-key",
            base_url="https://custom.api/v1"
        )
        assert provider.base_url == "https://custom.api/v1"


class TestLocalEmbeddingProvider:
    """测试本地嵌入提供商"""

    def test_init_without_sentence_transformers(self):
        """测试没有 sentence-transformers"""
        with patch("backend.memory.embedding.HAS_NUMPY", True):
            # 创建一个会抛出 ImportError 的 mock
            def mock_import(name, *args, **kwargs):
                if "sentence_transformers" in name:
                    raise ImportError("sentence-transformers not found")
                return __import__(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                provider = LocalEmbeddingProvider(model="test-model")
                with pytest.raises(ImportError, match="sentence-transformers"):
                    _ = provider.st_model

    def test_encode_batch_mock(self):
        """测试编码批次（模拟）"""
        provider = LocalEmbeddingProvider(model="test-model")

        # Mock model - 返回带有 tolist() 方法的对象
        mock_result = Mock()
        mock_result.tolist = Mock(return_value=[[0.1, 0.2], [0.3, 0.4]])

        mock_model = Mock()
        mock_model.encode = Mock(return_value=mock_result)
        provider._st_model = mock_model

        result = provider._encode_batch(["text1", "text2"])
        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]


class TestFallbackEmbeddingProvider:
    """测试回退嵌入提供商"""

    def test_fallback_to_second_provider(self):
        """测试回退到第二个提供商"""
        provider1 = MockProvider(model="test1", fail=True)
        provider2 = MockProvider(model="test2")

        fallback = FallbackEmbeddingProvider(providers=[provider1, provider2])
        result = fallback._encode_batch(["text"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

    def test_all_providers_fail(self):
        """测试所有提供商失败"""
        provider1 = MockProvider(model="test1", fail=True)
        provider2 = MockProvider(model="test2", fail=True)

        fallback = FallbackEmbeddingProvider(providers=[provider1, provider2])

        with pytest.raises(RuntimeError, match="All embedding providers failed"):
            fallback._encode_batch(["text"])


class TestCreateEmbeddingProvider:
    """测试创建嵌入提供商工厂函数"""

    def test_create_zhipu_provider(self):
        """测试创建智谱提供商"""
        with patch("backend.memory.embedding.HAS_ZHIPU", True):
            provider = create_embedding_provider(
                provider="zhipu",
                model="embedding-3",
                api_key="test-key"
            )
            assert isinstance(provider, ZhipuEmbeddingProvider)

    def test_create_openai_provider(self):
        """测试创建 OpenAI 提供商"""
        with patch("backend.memory.embedding.HAS_OPENAI", True):
            provider = create_embedding_provider(
                provider="openai",
                model="text-embedding-3-small",
                api_key="test-key"
            )
            assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_create_local_provider(self):
        """测试创建本地提供商"""
        provider = create_embedding_provider(provider="local")
        assert isinstance(provider, LocalEmbeddingProvider)

    def test_create_auto_with_zhipu_available(self):
        """测试自动选择（智谱可用）"""
        with patch("backend.memory.embedding.HAS_ZHIPU", True):
            with patch.dict(os.environ, {"ZHIPUAI_API_KEY": "test-key"}):
                provider = create_embedding_provider(provider="auto")
                assert isinstance(provider, ZhipuEmbeddingProvider)

    def test_create_auto_local_fallback(self):
        """测试自动选择回退到本地"""
        with patch("backend.memory.embedding.HAS_ZHIPU", False):
            with patch("backend.memory.embedding.HAS_OPENAI", False):
                provider = create_embedding_provider(provider="auto")
                assert isinstance(provider, LocalEmbeddingProvider)

    def test_create_unknown_provider(self):
        """测试创建未知提供商"""
        with pytest.raises(ValueError, match="Unknown provider"):
            create_embedding_provider(provider="unknown")


class TestIntegration:
    """集成测试"""

    def test_end_to_end_workflow(self, tmp_path):
        """测试端到端工作流"""
        # 创建缓存数据库
        db_path = tmp_path / "cache.db"
        db = sqlite3.connect(db_path)
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

        # 创建提供商
        provider = MockProvider(model="test", cache_db=db)

        # 第一次编码
        texts = ["hello world", "test text"]
        result1 = provider.encode(texts)
        assert len(result1) == 2
        assert all(len(emb) == 3 for emb in result1)

        # 第二次编码相同文本（应该从缓存读取）
        result2 = provider.encode(texts)
        assert result2 == result1
        assert provider.encode_call_count == 1  # 只调用了一次

        # 获取维度
        dims = provider.get_dims()
        assert dims == 3

        db.close()


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_embedding_string(self):
        """测试空嵌入字符串"""
        provider = MockProvider(model="test")
        result = provider._parse_embedding("")
        assert result == []

    def test_malformed_embedding_string(self):
        """测试格式错误的嵌入字符串"""
        provider = MockProvider(model="test")
        # 格式错误时应该返回空列表
        result = provider._parse_embedding("0.1,0.2,abc,0.3")
        assert result == []

    def test_unicode_text(self):
        """测试 Unicode 文本"""
        provider = MockProvider(model="test")
        text = "中文内容 Emoji 😊 特殊符号 αβγ"
        embedding = provider.encode_single(text)
        assert len(embedding) == 3

    def test_very_long_text(self):
        """测试非常长的文本"""
        provider = MockProvider(model="test")
        text = "word " * 10000  # 长文本
        embedding = provider.encode_single(text)
        assert len(embedding) == 3

    def test_batch_processing(self):
        """测试批处理"""
        provider = MockProvider(model="test", batch_size=2)
        texts = ["text1", "text2", "text3", "text4", "text5"]

        result = provider.encode(texts)
        assert len(result) == 5
        # batch_size=2，应该有 3 次编码调用
        assert provider.encode_call_count == 3


# Mock provider for testing
class MockProvider(EmbeddingProvider):
    """模拟提供商用于测试"""

    def __init__(self, model: str, cache_db=None, batch_size: int = 100, fail: bool = False):
        super().__init__(model=model, cache_db=cache_db, batch_size=batch_size)
        self.encode_call_count = 0
        self.fail = fail

    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """模拟编码"""
        self.encode_call_count += 1

        if self.fail:
            raise RuntimeError("Mock provider failed")

        # 返回固定 3 维向量
        return [[0.1, 0.2, 0.3] for _ in texts]
