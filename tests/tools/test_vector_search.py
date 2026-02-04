"""
向量检索工具单元测试
"""

import pytest
from pydantic import ValidationError

from tools.vector_search import (
    VectorSearchInput,
    vector_search_impl,
    vector_search_tool,
    InMemoryVectorStore,
    ChromaDBVectorStore,
    _get_vector_store,
)


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

    def test_max_results_boundary(self):
        """测试边界值"""
        input_data = VectorSearchInput(
            query="test",
            max_results=50
        )
        assert input_data.max_results == 50

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

    def test_response_format_concise(self):
        """测试简洁响应格式"""
        input_data = VectorSearchInput(
            query="test",
            response_format="concise"
        )
        assert input_data.response_format == "concise"

    def test_response_format_detailed(self):
        """测试详细响应格式"""
        input_data = VectorSearchInput(
            query="test",
            response_format="detailed"
        )
        assert input_data.response_format == "detailed"

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
        assert any("GMV" in r["text"] or r.get("metadata", {}).get("name") == "GMV" for r in results)

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

    def test_search_with_filter_metadata_category(self):
        """测试元数据过滤（按类别）"""
        store = InMemoryVectorStore()
        results = store.search("test", filter_metadata={"category": "sales"})
        for r in results:
            assert r.get("metadata", {}).get("category") == "sales"

    def test_search_with_filter_metadata_multiple(self):
        """测试多条件元数据过滤"""
        store = InMemoryVectorStore()
        results = store.search(
            "test",
            filter_metadata={"type": "metric", "category": "sales"}
        )
        for r in results:
            metadata = r.get("metadata", {})
            assert metadata.get("type") == "metric"
            assert metadata.get("category") == "sales"

    def test_search_results_sorted_by_score(self):
        """测试结果按分数排序"""
        store = InMemoryVectorStore()
        results = store.search("GMV 商品")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_score_range(self):
        """测试分数在有效范围内"""
        store = InMemoryVectorStore()
        results = store.search("test")
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_search_result_structure(self):
        """测试结果结构"""
        store = InMemoryVectorStore()
        results = store.search("GMV")
        if results:
            result = results[0]
            assert "id" in result
            assert "text" in result
            assert "metadata" in result
            assert "score" in result

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

    def test_search_includes_added_document(self):
        """测试搜索包含新添加的文档"""
        store = InMemoryVectorStore()

        store.add_documents([
            {
                "id": "test_doc_unique",
                "text": "unique_test_content_xyz",
                "metadata": {"type": "test"}
            }
        ])

        results = store.search("unique_test_content_xyz")
        assert any(r["id"] == "test_doc_unique" for r in results)


class TestChromaDBVectorStore:
    """测试 ChromaDB 向量存储"""

    def test_initialization_when_chromadb_unavailable(self):
        """测试 ChromaDB 不可用时的行为"""
        # 这个测试假设 ChromaDB 可能不可用
        # 如果可用，测试会尝试创建实例
        try:
            from tools.vector_search import CHROMADB_AVAILABLE
            if not CHROMADB_AVAILABLE:
                with pytest.raises(RuntimeError, match="ChromaDB 不可用"):
                    ChromaDBVectorStore("/tmp/test", "test_collection")
        except ImportError:
            pass


class TestGetVectorStore:
    """测试获取向量存储"""

    def test_returns_instance(self):
        """测试返回实例"""
        store = _get_vector_store("test_collection")
        assert store is not None

    def test_returns_in_memory_when_chromadb_unavailable(self):
        """测试 ChromaDB 不可用时返回内存存储"""
        from tools.vector_search import CHROMADB_AVAILABLE
        store = _get_vector_store("test_collection")

        if not CHROMADB_AVAILABLE:
            assert isinstance(store, InMemoryVectorStore)


class TestVectorSearchImpl:
    """测试向量搜索实现函数"""

    def test_basic_search_execution(self):
        """测试基本搜索执行"""
        result_json = vector_search_impl(query="什么是 GMV")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert "成功" in result.summary or "找到" in result.summary
        assert result.result is not None

    def test_search_with_custom_collection(self):
        """测试自定义集合搜索"""
        result_json = vector_search_impl(
            query="test",
            collection="custom_collection"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_search_with_max_results(self):
        """测试限制结果数"""
        result_json = vector_search_impl(
            query="GMV",
            max_results=2
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        if result.result:
            assert result.result["result_count"] <= 2

    def test_search_with_min_score(self):
        """测试最小分数过滤"""
        result_json = vector_search_impl(
            query="test",
            min_score=0.9
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_search_with_filter_metadata(self):
        """测试元数据过滤"""
        result_json = vector_search_impl(
            query="test",
            filter_metadata={"type": "metric"}
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_concise_response_format(self):
        """测试简洁响应格式"""
        result_json = vector_search_impl(
            query="GMV",
            response_format="concise"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        # Concise 格式可能不返回详细结果
        assert "成功" in result.summary or "找到" in result.summary

    def test_standard_response_format(self):
        """测试标准响应格式"""
        result_json = vector_search_impl(
            query="GMV",
            response_format="standard"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        assert result.result is not None

    def test_detailed_response_format(self):
        """测试详细响应格式"""
        result_json = vector_search_impl(
            query="GMV",
            response_format="detailed"
        )
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_observation_format(self):
        """测试 Observation 格式"""
        result_json = vector_search_impl(query="GMV")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert "Observation:" in result.observation
        assert "Status:" in result.observation

    def test_telemetry_collected(self):
        """测试遥测数据收集"""
        result_json = vector_search_impl(query="test")
        result = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput.model_validate_json(result_json)

        assert result.telemetry.tool_name == "search_knowledge"
        assert result.telemetry.latency_ms >= 0


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

        # 结果应该是 JSON 字符串
        assert isinstance(result, str)
        # 可以解析为 ToolOutput
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success

    def test_tool_with_max_results(self):
        """测试工具带最大结果数参数"""
        result = vector_search_tool.invoke({
            "query": "GMV",
            "max_results": 3
        })

        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success

    def test_tool_with_filter_metadata(self):
        """测试工具带元数据过滤参数"""
        result = vector_search_tool.invoke({
            "query": "test",
            "filter_metadata": {"type": "metric"}
        })

        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        output = ToolOutput.model_validate_json(result)
        assert output.telemetry.success


class TestVectorSearchIntegration:
    """集成测试"""

    def test_full_search_workflow(self):
        """测试完整搜索工作流"""
        # 1. 创建输入
        input_data = VectorSearchInput(
            query="GMV 增长率",
            max_results=5,
            min_score=0.0,
            response_format="standard"
        )

        # 2. 执行搜索
        result_json = vector_search_impl(
            query=input_data.query,
            max_results=input_data.max_results,
            min_score=input_data.min_score,
            response_format=input_data.response_format
        )

        # 3. 解析结果
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        result = ToolOutput.model_validate_json(result_json)

        # 4. 验证
        assert result.telemetry.success
        assert "成功" in result.summary or "找到" in result.summary
        assert result.result is not None
        assert "results" in result.result
        assert "result_count" in result.result

    def test_search_metric_definitions(self):
        """测试搜索指标定义"""
        result_json = vector_search_impl(
            query="转化率是什么",
            filter_metadata={"type": "metric"}
        )
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success
        if result.result and result.result["results"]:
            # 验证返回的是指标类型
            for r in result.result["results"]:
                assert r.get("metadata", {}).get("type") == "metric"

    def test_search_dimension_definitions(self):
        """测试搜索维度定义"""
        result_json = vector_search_impl(
            query="品类维度",
            filter_metadata={"type": "dimension"}
        )
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput
        result = ToolOutput.model_validate_json(result_json)

        assert result.telemetry.success

    def test_multiple_searches_same_collection(self):
        """测试在同一集合中执行多次搜索"""
        ToolOutput = __import__("backend.models.tool_output", fromlist=["ToolOutput"]).ToolOutput

        # 第一次搜索
        result1 = ToolOutput.model_validate_json(
            vector_search_impl(query="GMV")
        )
        assert result1.telemetry.success

        # 第二次搜索
        result2 = ToolOutput.model_validate_json(
            vector_search_impl(query="转化率")
        )
        assert result2.telemetry.success
