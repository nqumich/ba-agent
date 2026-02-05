"""
记忆索引系统

提供 SQLite FTS5 全文搜索索引功能
"""

from .schema import (
    ensure_memory_index_schema,
    get_index_db_path,
    open_index_db,
    DEFAULT_INDEX_PATH
)
from .index import MemoryIndexer, MemoryWatcher
from .embedding import (
    EmbeddingProvider,
    ZhipuEmbeddingProvider,
    OpenAIEmbeddingProvider,
    LocalEmbeddingProvider,
    FallbackEmbeddingProvider,
    create_embedding_provider
)
from .vector_search import (
    cosine_similarity,
    normalize_scores,
    combine_scores,
    VectorSearchEngine,
    HybridSearchEngine
)
from .flush import (
    RetainFormatter,
    MemoryExtractor,
    MemoryFlushConfig,
    MemoryFlush
)

__all__ = [
    "ensure_memory_index_schema",
    "get_index_db_path",
    "open_index_db",
    "DEFAULT_INDEX_PATH",
    "MemoryIndexer",
    "MemoryWatcher",
    "EmbeddingProvider",
    "ZhipuEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "LocalEmbeddingProvider",
    "FallbackEmbeddingProvider",
    "create_embedding_provider",
    "cosine_similarity",
    "normalize_scores",
    "combine_scores",
    "VectorSearchEngine",
    "HybridSearchEngine",
    "RetainFormatter",
    "MemoryExtractor",
    "MemoryFlushConfig",
    "MemoryFlush",
]
