"""
向量检索工具单元测试 (v2.1 - Pipeline Only)
"""

import pytest
from pydantic import ValidationError

from tools.vector_search import (
    VectorSearchInput,
    vector_search_impl,
    vector_search_tool,
    InMemoryVectorStore,
    ChromaDBVectorStore,
)

# Pipeline v2.1 模型
from backend.models.pipeline import ToolExecutionResult, OutputLevel


class TestVectorSearchInput:
    """测试 VectorSearchInput 模型"""

    def test_basic_search(self):
        """测试基本搜索输入"""
        input_data = VectorSearchInput(
            query="什么是 GMV"
        )
        assert input_data.query == "什么是 GMV"
        assert input_data.collection == "ba_agent"
        assert input_data.max_results == 5

    def test_custom_collection(self):
        """测试自定义集合名称"""
        input_data = VectorSearchInput(
            query="test",
            collection="my_collection"
        )
        assert input_data.collection == "my_collection"

    def test_max_results_custom(self):
        """测试自定义最大结果数"""
        input_data = VectorSearchInput(
            query="test",
            max_results=10
        )
        assert input_data.max_results == 10

    def test_min_score(self):
        """测试最小分数"""
        input_data = VectorSearchInput(
            query="test",
            min_score=0.5
        )
        assert input_data.min_score == 0.5

    def test_filter_metadata(self):
        """测试元数据过滤"""
        input_data = VectorSearchInput(
            query="test",
            filter_metadata={"type": "metric", "category": "sales"}
        )
        assert input_data.filter_metadata == {"type": "metric", "category": "sales"}

    def test_response_format_brief(self):
        """测试简洁响应格式"""
        input_data = VectorSearchInput(
            query="test",
            response_format="brief"
        )
        assert input_data.response_format == "brief"

    def test_response_format_full(self):
        """测试详细响应格式"""
        input_data = VectorSearchInput(
            query="test",
            response_format="full"
        )
        assert input_data.response_format == "full"

    def test_empty_query(self):
        """测试空查询"""
        with pytest.raises(ValidationError):
            VectorSearchInput(query="")

    def test_empty_collection(self):
        """测试空集合名称"""
        with pytest.raises(ValidationError):
            VectorSearchInput(query="test", collection="")

    def test_invalid_collection_name(self):
        """测试无效集合名称（包含非法字符）"""
        with pytest.raises(ValidationError, match="只能包含"):
            VectorSearchInput(query="test", collection="test collection!")

    def test_max_results_exceeds_limit(self):
        """测试超过最大结果数限制"""
        with pytest.raises(ValidationError):
            VectorSearchInput(query="test", max_results=51)

    def test_max_results_below_minimum(self):
        """测试低于最小结果数"""
        with pytest.raises(ValidationError):
            VectorSearchInput(query="test", max_results=0)

    def test_min_score_exceeds_maximum(self):
        """测试超过最大分数"""
        with pytest.raises(ValidationError):
            VectorSearchInput(query="test", min_score=1.1)

    def test_min_score_below_minimum(self):
        """测试低于最小分数"""
        with pytest.raises(ValidationError):
            VectorSearchInput(query="test", min_score=-0.1)


class TestInMemoryVectorStore:
    """测试内存向量存储"""

    def test_initialization(self):
        """测试初始化"""
        store = InMemoryVectorStore()
        assert len(store.documents) > 0
        assert "metric_gmv" in store.documents

    def test_sample_data_exists(self):
        """测试示例数据存在"""
        store = InMemoryVectorStore()
        # 检查指标
        assert "metric_gmv" in store.documents
        assert "metric_conversion_rate" in store.documents
        # 检查维度
        assert "dim_category" in store.documents
        assert "dim_channel" in store.documents

    def test_search_basic(self):
        """测试基本搜索"""
        store = InMemoryVectorStore()
        results = store.search("GMV")
        assert len(results) > 0

    def test_search_with_max_results(self):
        """测试限制结果数"""
        store = InMemoryVectorStore()
        results = store.search("销售额", max_results=2)
        assert len(results) <= 2

    def test_search_with_min_score(self):
        """测试最小分数过滤"""
        store = InMemoryVectorStore()
        results = store.search("GMV", min_score=0.9)
        # 只有高分数的结果
        for r in results:
            assert r["score"] >= 0.9

    def test_search_with_filter_metadata_type(self):
        """测试元数据过滤（按类型）"""
        store = InMemoryVectorStore()
        results = store.search("test", filter_metadata={"type": "metric"})
        for r in results:
            assert r.get("metadata", {}).get("type") == "metric"

    def test_add_documents(self):
        """测试添加文档"""
        store = InMemoryVectorStore()
        original_count = len(store.documents)

        new_docs = [
            {
                "id": "test_doc_1",
                "text": "测试文档内容",
                "metadata": {"type": "test"}
            }
        ]
        store.add_documents(new_docs)

        assert len(store.documents) == original_count + 1
        assert "test_doc_1" in store.documents


class TestVectorSearchImpl:
    """测试向量搜索实现函数"""

    def test_basic_search_execution(self):
        """测试基本搜索执行"""
        result = vector_search_impl(query="什么是 GMV")

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert len(result.observation) > 0

    def test_search_with_custom_collection(self):
        """测试自定义集合搜索"""
        result = vector_search_impl(
            query="test",
            collection="custom_collection"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_search_with_max_results(self):
        """测试限制结果数"""
        result = vector_search_impl(
            query="GMV",
            max_results=2
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_brief_response_format(self):
        """测试简洁响应格式"""
        result = vector_search_impl(
            query="GMV",
            response_format="brief"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success
        assert result.output_level == OutputLevel.BRIEF

    def test_standard_response_format(self):
        """测试标准响应格式"""
        result = vector_search_impl(
            query="GMV",
            response_format="standard"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_full_response_format(self):
        """测试详细响应格式"""
        result = vector_search_impl(
            query="GMV",
            response_format="full"
        )

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_telemetry_collected(self):
        """测试遥测数据收集"""
        result = vector_search_impl(query="test")

        assert isinstance(result, ToolExecutionResult)
        assert result.tool_name == "search_knowledge"
        assert result.duration_ms >= 0


class TestVectorSearchTool:
    """测试 LangChain 工具"""

    def test_tool_metadata(self):
        """测试工具元数据"""
        assert vector_search_tool.name == "search_knowledge"
        assert "搜索" in vector_search_tool.description or "search" in vector_search_tool.description.lower()

    def test_tool_is_structured_tool(self):
        """测试工具是 StructuredTool 实例"""
        from langchain_core.tools import StructuredTool
        assert isinstance(vector_search_tool, StructuredTool)

    def test_tool_args_schema(self):
        """测试工具参数模式"""
        assert vector_search_tool.args_schema == VectorSearchInput

    def test_tool_invocation(self):
        """测试工具调用"""
        result = vector_search_tool.invoke({
            "query": "什么是 GMV"
        })

        assert isinstance(result, ToolExecutionResult)
        assert result.success

    def test_tool_with_max_results(self):
        """测试工具带最大结果数参数"""
        result = vector_search_tool.invoke({
            "query": "GMV",
            "max_results": 3
        })

        assert isinstance(result, ToolExecutionResult)
        assert result.success
