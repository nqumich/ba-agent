"""
向量嵌入提供商

支持多种 embedding API 和本地回退方案
"""

import hashlib
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from zhipuai import ZhipuAI
    HAS_ZHIPU = True
except ImportError:
    HAS_ZHIPU = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class EmbeddingProvider(ABC):
    """嵌入提供商抽象基类"""

    def __init__(
        self,
        model: str,
        cache_db=None,
        batch_size: int = 100,
        request_timeout: float = 30.0
    ):
        """
        初始化嵌入提供商

        Args:
            model: 模型名称
            cache_db: SQLite 缓存数据库连接 (可选)
            batch_size: 批处理大小
            request_timeout: 请求超时时间（秒）
        """
        self.model = model
        self.cache_db = cache_db
        self.batch_size = batch_size
        self.request_timeout = request_timeout
        self._provider_name = self.__class__.__name__.replace("EmbeddingProvider", "").lower()

    @abstractmethod
    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        编码一批文本（子类实现）

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        编码文本为嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        # 检查缓存
        if self.cache_db:
            cached_results = self._get_from_cache(texts)
            if cached_results:
                return cached_results

        # 批处理编码
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = self._encode_batch(batch)
            all_embeddings.extend(embeddings)

            # 缓存结果
            if self.cache_db:
                self._save_to_cache(batch, embeddings)

        return all_embeddings

    def encode_single(self, text: str) -> List[float]:
        """
        编码单个文本

        Args:
            text: 文本内容

        Returns:
            嵌入向量
        """
        result = self.encode([text])
        return result[0] if result else []

    def _compute_hash(self, text: str) -> str:
        """计算文本 hash"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_from_cache(self, texts: List[str]) -> Optional[List[List[float]]]:
        """从缓存获取嵌入"""
        if not self.cache_db:
            return None

        try:
            hashes = [self._compute_hash(text) for text in texts]
            placeholders = ', '.join(['?'] * len(hashes))

            cursor = self.cache_db.execute(f"""
                SELECT content_hash, embedding
                FROM embedding_cache
                WHERE provider = ? AND model = ? AND content_hash IN ({placeholders})
            """, [self._provider_name, self.model] + hashes)

            cached = {row[0]: row[1] for row in cursor.fetchall()}

            # 检查是否全部命中
            if all(h in cached for h in hashes):
                # 解析缓存的嵌入向量
                return [self._parse_embedding(cached[h]) for h in hashes]

        except Exception:
            pass

        return None

    def _save_to_cache(self, texts: List[str], embeddings: List[List[float]]) -> None:
        """保存嵌入到缓存"""
        if not self.cache_db:
            return

        try:
            now = int(time.time())
            for text, embedding in zip(texts, embeddings):
                content_hash = self._compute_hash(text)
                embedding_str = self._serialize_embedding(embedding)

                self.cache_db.execute("""
                    INSERT OR REPLACE INTO embedding_cache
                    (provider, model, content_hash, embedding, dims, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self._provider_name,
                    self.model,
                    content_hash,
                    embedding_str,
                    len(embedding),
                    now
                ))
            self.cache_db.commit()

        except Exception:
            pass

    def _serialize_embedding(self, embedding: List[float]) -> str:
        """序列化嵌入向量为字符串"""
        return ','.join(str(x) for x in embedding)

    def _parse_embedding(self, embedding_str: str) -> List[float]:
        """解析嵌入向量字符串"""
        if not embedding_str:
            return []
        try:
            return [float(x) for x in embedding_str.split(',')]
        except ValueError:
            # 如果格式错误，返回空列表
            return []

    def get_dims(self) -> Optional[int]:
        """获取嵌入维度"""
        # 编码一个测试文本获取维度
        test_embedding = self.encode_single("test")
        return len(test_embedding) if test_embedding else None


class ZhipuEmbeddingProvider(EmbeddingProvider):
    """
    智谱 AI (GLM) 嵌入提供商

    使用智谱 AI 的 embedding API
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "embedding-3",
        **kwargs
    ):
        """
        初始化智谱嵌入提供商

        Args:
            api_key: API 密钥
            model: 模型名称 (embedding-2, embedding-3)
            **kwargs: 其他参数传递给基类
        """
        super().__init__(model=model, **kwargs)

        if not HAS_ZHIPU:
            raise ImportError("zhipuai package is required. Install with: pip install zhipuai")

        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        """懒加载客户端"""
        if self._client is None:
            import os
            key = self.api_key or os.getenv("ZHIPUAI_API_KEY")
            if not key:
                raise ValueError("ZhipuAI API key is required. Set ZHIPUAI_API_KEY environment variable.")
            self._client = ZhipuAI(api_key=key)
        return self._client

    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """调用智谱 API 编码"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )

            embeddings = [item.embedding for item in response.data]
            return embeddings

        except Exception as e:
            raise RuntimeError(f"ZhipuAI embedding failed: {e}")


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI 嵌入提供商

    使用 OpenAI 的 embedding API
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
        **kwargs
    ):
        """
        初始化 OpenAI 嵌入提供商

        Args:
            api_key: API 密钥
            base_url: API 基础 URL (用于兼容其他 OpenAI 兼容 API)
            model: 模型名称 (text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002)
            **kwargs: 其他参数传递给基类
        """
        super().__init__(model=model, **kwargs)

        if not HAS_OPENAI:
            raise ImportError("openai package is required. Install with: pip install openai")

        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    @property
    def client(self):
        """懒加载客户端"""
        if self._client is None:
            import os
            key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

            client_kwargs = {"api_key": key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url

            self._client = OpenAI(**client_kwargs)
        return self._client

    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """调用 OpenAI API 编码"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )

            # 按 index 排序确保顺序正确
            embeddings = [item.embedding for item in response.data]
            return embeddings

        except Exception as e:
            raise RuntimeError(f"OpenAI embedding failed: {e}")


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    本地嵌入提供商

    使用 sentence-transformers 进行本地嵌入
    作为远程 API 的回退方案
    """

    def __init__(
        self,
        model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        device: Optional[str] = None,
        **kwargs
    ):
        """
        初始化本地嵌入提供商

        Args:
            model: 模型名称或路径
            device: 设备 (cpu, cuda, mps)
            **kwargs: 其他参数传递给基类
        """
        # 使用 _model_name 存储模型名称，避免与 property 冲突
        self._model_name = model
        self.device = device
        self._st_model = None

        # 传递父类需要的模型名称
        super().__init__(model=model, **kwargs)

        if not HAS_NUMPY:
            raise ImportError("numpy is required. Install with: pip install numpy")

    @property
    def st_model(self):
        """懒加载模型"""
        if self._st_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install sentence-transformers"
                )

            # 自动选择设备
            device = self.device
            if device is None:
                if HAS_NUMPY:
                    import torch
                    device = "mps" if torch.backends.mps.is_available() else "cpu"

            self._st_model = SentenceTransformer(self._model_name, device=device)
        return self._st_model

    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型编码"""
        try:
            embeddings = self.st_model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False
            )

            # 转换为列表格式
            return embeddings.tolist()

        except Exception as e:
            raise RuntimeError(f"Local embedding failed: {e}")


class FallbackEmbeddingProvider(EmbeddingProvider):
    """
    回退嵌入提供商

    依次尝试多个提供商，直到成功
    """

    def __init__(
        self,
        providers: List[EmbeddingProvider],
        **kwargs
    ):
        """
        初始化回退嵌入提供商

        Args:
            providers: 提供商列表（按优先级排序）
            **kwargs: 其他参数传递给基类
        """
        # 使用第一个提供商的模型名称
        super().__init__(model=providers[0].model, **kwargs)
        self.providers = providers

    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """依次尝试每个提供商"""
        last_error = None

        for provider in self.providers:
            try:
                return provider._encode_batch(texts)
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"All embedding providers failed. Last error: {last_error}")


def create_embedding_provider(
    provider: str = "auto",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    cache_db=None,
    **kwargs
) -> EmbeddingProvider:
    """
    创建嵌入提供商

    Args:
        provider: 提供商名称 (auto, zhipu, openai, local)
        model: 模型名称
        api_key: API 密钥
        cache_db: 缓存数据库连接
        **kwargs: 其他参数

    Returns:
        嵌入提供商实例
    """
    if provider == "auto":
        # 自动选择：zhipu > openai > local
        if HAS_ZHIPU and (api_key or __import__("os").getenv("ZHIPUAI_API_KEY")):
            provider = "zhipu"
        elif HAS_OPENAI and (api_key or __import__("os").getenv("OPENAI_API_KEY")):
            provider = "openai"
        else:
            provider = "local"

    if provider == "zhipu":
        if model is None:
            model = "embedding-3"
        return ZhipuEmbeddingProvider(api_key=api_key, model=model, cache_db=cache_db, **kwargs)

    elif provider == "openai":
        if model is None:
            model = "text-embedding-3-small"
        return OpenAIEmbeddingProvider(api_key=api_key, model=model, cache_db=cache_db, **kwargs)

    elif provider == "local":
        if model is None:
            model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        return LocalEmbeddingProvider(model=model, cache_db=cache_db, **kwargs)

    else:
        raise ValueError(f"Unknown provider: {provider}. Choose from: auto, zhipu, openai, local")
