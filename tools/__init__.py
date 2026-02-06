"""
BA-Agent 工具模块 (v2.1 - Pipeline Only)

提供 LangChain StructuredTool 封装的各种工具

v2.1 变更：
- 移除 unified_tool (旧装饰器)
- 保留 ToolOutputParser (简化版)
- 移除 ReActFormatter, TokenOptimizer (不再需要)
"""

from .execute_command import (
    ExecuteCommandInput,
    execute_command_impl,
    execute_command_tool,
)

from .python_sandbox import (
    PythonCodeInput,
    run_python_impl,
    run_python_tool,
    get_allowed_imports,
    ALLOWED_IMPORTS,
)

from .web_search import (
    WebSearchInput,
    web_search_impl,
    web_search_tool,
)

from .web_reader import (
    WebReaderInput,
    web_reader_impl,
    web_reader_tool,
)

from .file_reader import (
    FileReadInput,
    file_reader_impl,
    file_reader_tool,
    DEFAULT_ALLOWED_PATHS,
)

from .database import (
    DatabaseQueryInput,
    query_database_impl,
    query_database_tool,
)

from .vector_search import (
    VectorSearchInput,
    vector_search_impl,
    vector_search_tool,
    InMemoryVectorStore,
    ChromaDBVectorStore,
)

from .file_write import (
    FileWriteInput,
    file_write,
    file_write_tool,
)

from .base import (
    pipeline_tool,
    tool,
    ToolOutputParser,
)

__all__ = [
    "ExecuteCommandInput",
    "execute_command_impl",
    "execute_command_tool",
    "PythonCodeInput",
    "run_python_impl",
    "run_python_tool",
    "get_allowed_imports",
    "ALLOWED_IMPORTS",
    "WebSearchInput",
    "web_search_impl",
    "web_search_tool",
    "WebReaderInput",
    "web_reader_impl",
    "web_reader_tool",
    "FileReadInput",
    "file_reader_impl",
    "file_reader_tool",
    "DEFAULT_ALLOWED_PATHS",
    "DatabaseQueryInput",
    "query_database_impl",
    "query_database_tool",
    "VectorSearchInput",
    "vector_search_impl",
    "vector_search_tool",
    "InMemoryVectorStore",
    "ChromaDBVectorStore",
    # file_write
    "FileWriteInput",
    "file_write",
    "file_write_tool",
    # Base decorators and utilities
    "pipeline_tool",
    "tool",
    "ToolOutputParser",
]
