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
from .flush_enhanced import (
    FileRefDetector,
    EnhancedMemoryFlush,
    create_enhanced_memory_flush
)
from .search_enhanced import (
    FileRefIndex,
    FileRefSearchResult,
    FileRefMemorySearcher,
    enhance_search_results_with_file_refs,
    format_search_results_with_file_refs,
    get_file_ref_index,
    create_file_ref_searcher
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
    # Enhanced flush with file reference support
    "FileRefDetector",
    "EnhancedMemoryFlush",
    "create_enhanced_memory_flush",
    # Enhanced search with file reference support
    "FileRefIndex",
    "FileRefSearchResult",
    "FileRefMemorySearcher",
    "enhance_search_results_with_file_refs",
    "format_search_results_with_file_refs",
    "get_file_ref_index",
    "create_file_ref_searcher",
]
