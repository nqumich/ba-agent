"""
向量检索工具 (v2.1 - Pipeline Support)

使用 ChromaDB 进行语义搜索，支持指标/维度定义检索
提供内存回退方案当 ChromaDB 不可用时

新特性：
- 支持 ToolExecutionResult (Pipeline v2.0.1)
- 保持与旧 ToolOutput 的兼容性
"""

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

from config import get_config

# 旧模型 (保持兼容)
from backend.models.tool_output import ToolOutput, ToolTelemetry, ResponseFormat

# 新模型 (Pipeline v2.0.1)
from backend.models.pipeline import (
    OutputLevel,
    ToolExecutionResult,
    ToolCachePolicy,
)

# 兼容层
from backend.models.compat import (
    response_format_to_output_level,
    execution_result_to_tool_output,
)


# 尝试导入 ChromaDB，如果失败则使用内存回退
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class VectorSearchInput(BaseModel):
    """向量检索工具的输入参数"""

    query: str = Field(
        ...,
        description="搜索查询文本",
        min_length=1
    )
    collection: Optional[str] = Field(
        default="ba_agent",
        description="集合名称（默认: ba_agent）"
    )
    max_results: Optional[int] = Field(
        default=5,
        ge=1,
        le=50,
        description="最大返回结果数（范围 1-50）"
    )
    min_score: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="最小相似度分数（范围 0-1）"
    )
    filter_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="元数据过滤条件（例如: {\"category\": \"metric\"}）"
    )
    # 新：支持 OutputLevel 字符串
    response_format: Optional[str] = Field(
        default="standard",
        description="响应格式: concise/brief, standard, detailed/full"
    )

    @field_validator('collection')
    @classmethod
    def validate_collection(cls, v: str) -> str:
        """验证集合名称"""
        if not v or not v.strip():
            raise ValueError("集合名称不能为空")
        # 只允许字母、数字、下划线和短横线
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                "集合名称只能包含字母、数字、下划线和短横线"
            )
        return v


class InMemoryVectorStore:
    """
    内存向量存储（回退方案）

    当 ChromaDB 不可用时使用简单的关键词匹配
    """

    def __init__(self):
        self.documents: Dict[str, Dict[str, Any]] = {}
        self._init_sample_data()

    def _init_sample_data(self):
        """初始化示例数据"""
        # 业务指标定义
        self.documents["metric_gmv"] = {
            "id": "metric_gmv",
            "text": "GMV (Gross Merchandise Value) 商品交易总额，指在特定时间范围内平台上所有交易的总金额",
            "metadata": {
                "type": "metric",
                "category": "sales",
                "name": "GMV",
                "formula": "SUM(order_amount)"
            }
        }
        self.documents["metric_gmv_growth"] = {
            "id": "metric_gmv_growth",
            "text": "GMV 增长率，指当前时期 GMV 相对于上期 GMV 的增长百分比",
            "metadata": {
                "type": "metric",
                "category": "sales",
                "name": "GMV 增长率",
                "formula": "(当前GMV - 上期GMV) / 上期GMV * 100%"
            }
        }
        self.documents["metric_conversion_rate"] = {
            "id": "metric_conversion_rate",
            "text": "转化率 (Conversion Rate)，指访问者转化为购买者的比例",
            "metadata": {
                "type": "metric",
                "category": "marketing",
                "name": "转化率",
                "formula": "购买用户数 / 访问用户数 * 100%"
            }
        }
        self.documents["metric_aov"] = {
            "id": "metric_aov",
            "text": "AOV (Average Order Value) 平均订单金额，指每个订单的平均金额",
            "metadata": {
                "type": "metric",
                "category": "sales",
                "name": "AOV",
                "formula": "总GMV / 订单数"
            }
        }
        self.documents["metric_roas"] = {
            "id": "metric_roas",
            "text": "ROAS (Return on Ad Spend) 广告投资回报率，指广告投入带来的收入与广告成本的比值",
            "metadata": {
                "type": "metric",
                "category": "marketing",
                "name": "ROAS",
                "formula": "广告收入 / 广告成本"
            }
        }

        # 维度定义
        self.documents["dim_category"] = {
            "id": "dim_category",
            "text": "品类 (Category)，商品的分类维度，如电子产品、服装、家居等",
            "metadata": {
                "type": "dimension",
                "category": "product",
                "name": "品类"
            }
        }
        self.documents["dim_channel"] = {
            "id": "dim_channel",
            "text": "渠道 (Channel)，销售渠道维度，如直营、分销、电商平台等",
            "metadata": {
                "type": "dimension",
                "category": "sales",
                "name": "渠道"
            }
        }
        self.documents["dim_region"] = {
            "id": "dim_region",
            "text": "地区 (Region)，地理区域维度，如华东、华南、华北等",
            "metadata": {
                "type": "dimension",
                "category": "geography",
                "name": "地区"
            }
        }

    def search(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        简单的关键词搜索（回退方案）

        Args:
            query: 搜索查询
            max_results: 最大结果数
            min_score: 最小分数（这里作为简单的匹配度阈值）
            filter_metadata: 元数据过滤

        Returns:
            搜索结果列表
        """
        results = []
        query_lower = query.lower()

        for doc_id, doc in self.documents.items():
            # 应用元数据过滤
            if filter_metadata:
                match = True
                for key, value in filter_metadata.items():
                    if doc.get("metadata", {}).get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            # 简单的关键词匹配打分
            text = doc.get("text", "").lower()
            metadata = doc.get("metadata", {})

            score = 0.0
            # 完全匹配
            if query_lower in text:
                score = 0.8
            # 部分匹配（关键词）
            query_words = query_lower.split()
            for word in query_words:
                if word in text:
                    score += 0.1
            # 名称匹配
            name = metadata.get("name", "").lower()
            if query_lower in name:
                score = min(score + 0.2, 1.0)

            # 确保分数在 0-1 之间
            score = max(0.0, min(score, 1.0))

            if score >= min_score:
                results.append({
                    "id": doc_id,
                    "text": doc.get("text", ""),
                    "metadata": metadata,
                    "score": score
                })

        # 按分数排序并限制结果数
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """添加文档到内存存储"""
        for doc in documents:
            doc_id = doc.get("id", f"doc_{len(self.documents)}")
            self.documents[doc_id] = doc


class ChromaDBVectorStore:
    """
    ChromaDB 向量存储

    使用 ChromaDB 进行语义搜索
    """

    def __init__(self, persist_directory: str, collection_name: str):
        if not CHROMADB_AVAILABLE:
            raise RuntimeError("ChromaDB 不可用，请安装: pip install chromadb")

        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self._init_client()
        self._init_collection()

    def _init_client(self):
        """初始化 ChromaDB 客户端"""
        # 确保持久化目录存在
        os.makedirs(self.persist_directory, exist_ok=True)

        # 创建客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

    def _init_collection(self):
        """初始化或获取集合"""
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name
            )
        except Exception:
            # 集合不存在，创建新集合并添加示例数据
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "BA-Agent 知识库"}
            )
            self._add_sample_data()

    def _add_sample_data(self):
        """添加示例数据到集合"""
        # 注意：这里需要 embeddings。在实际环境中应该使用真实的 embedding 模型
        # 为了测试，我们使用简单的伪 embeddings
        sample_docs = InMemoryVectorStore()
        documents = list(sample_docs.documents.values())

        if not documents:
            return

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        # 简单的伪 embeddings（实际应该使用 embedding 模型）
        embeddings = [[0.1] * 384 for _ in documents]

        try:
            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings
            )
        except Exception as e:
            # ChromaDB 可能没有初始化，跳过
            pass

    def search(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        使用 ChromaDB 进行语义搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            min_score: 最小分数（这里作为阈值）
            filter_metadata: 元数据过滤

        Returns:
            搜索结果列表
        """
        try:
            # 构建查询过滤器
            where = filter_metadata if filter_metadata else None

            # 简单的伪 embedding（实际应该使用 embedding 模型）
            query_embedding = [0.1] * 384

            # 执行查询
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results,
                where=where
            )

            # 格式化结果
            formatted_results = []
            if results and results.get("ids"):
                for i, doc_id in enumerate(results["ids"][0]):
                    # 计算距离（这里简化为固定分数，实际应该用 embedding 距离）
                    distance = results.get("distances", [[0] * len(results["ids"][0])])[0][i]
                    score = 1.0 - min(distance, 1.0)  # 转换为相似度分数

                    if score >= min_score:
                        formatted_results.append({
                            "id": doc_id,
                            "text": results["documents"][0][i] if results.get("documents") else "",
                            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                            "score": score
                        })

            return formatted_results

        except Exception as e:
            # 如果 ChromaDB 查询失败，回退到内存搜索
            fallback = InMemoryVectorStore()
            return fallback.search(query, max_results, min_score, filter_metadata)


def _get_vector_store(collection_name: str) -> Union[ChromaDBVectorStore, InMemoryVectorStore]:
    """
    获取向量存储实例

    优先使用 ChromaDB，如果不可用则使用内存存储
    """
    config = get_config()
    persist_dir = config.vector_store.persist_directory

    if CHROMADB_AVAILABLE:
        try:
            return ChromaDBVectorStore(persist_dir, collection_name)
        except Exception:
            pass

    # 回退到内存存储
    return InMemoryVectorStore()


def _parse_response_format(format_str: str) -> tuple[Union[ResponseFormat, OutputLevel], str]:
    """
    解析响应格式字符串

    支持：
    - 旧格式: concise, standard, detailed, raw
    - 新格式: brief, standard, full

    Returns:
        (format_enum, format_type) - format_type 是 'old' 或 'new'
    """
    format_lower = format_str.lower()

    # 新格式 (OutputLevel)
    if format_lower in ("brief", "full"):
        return OutputLevel(format_lower), "new"

    # 旧格式 (ResponseFormat)
    if format_lower in ("concise", "standard", "detailed", "raw"):
        return ResponseFormat(format_lower), "old"

    # 默认
    return ResponseFormat.STANDARD, "old"


def vector_search_impl(
    query: str,
    collection: str = "ba_agent",
    max_results: int = 5,
    min_score: float = 0.0,
    filter_metadata: Optional[Dict[str, Any]] = None,
    response_format: str = "standard",
    use_pipeline: bool = False,
) -> Union[str, ToolExecutionResult]:
    """
    向量检索的实现函数

    Args:
        query: 搜索查询文本
        collection: 集合名称
        max_results: 最大返回结果数
        min_score: 最小相似度分数
        filter_metadata: 元数据过滤条件
        response_format: 响应格式
        use_pipeline: 是否使用新 Pipeline 模型 (默认 False 保持兼容)

    Returns:
        搜索结果（JSON 字符串或 ToolExecutionResult）
    """
    start_time = time.time()

    # 解析响应格式
    format_enum, format_type = _parse_response_format(response_format)

    try:
        # 获取向量存储
        vector_store = _get_vector_store(collection)

        # 执行搜索
        search_results = vector_store.search(
            query=query,
            max_results=max_results,
            min_score=min_score,
            filter_metadata=filter_metadata
        )

        duration_ms = (time.time() - start_time) * 1000

        # 格式化结果
        result_count = len(search_results)
        summary = f"找到 {result_count} 个相关结果"

        if result_count > 0:
            top_result = search_results[0]
            summary += f"，最高相似度: {top_result['score']:.2f}"

            # 获取结果类型信息
            result_types = set()
            for r in search_results:
                metadata = r.get("metadata", {})
                doc_type = metadata.get("type", "unknown")
                result_types.add(doc_type)

            if result_types:
                summary += f"，类型: {', '.join(sorted(result_types))}"

        # 根据是否使用 Pipeline 返回不同格式
        if use_pipeline:
            # 新格式：ToolExecutionResult
            import uuid
            tool_call_id = f"call_search_knowledge_{uuid.uuid4().hex[:12]}"

            # 转换 OutputLevel
            if format_type == "new":
                output_level = format_enum
            else:
                output_level = response_format_to_output_level(format_enum)

            result_data = {
                "query": query,
                "collection": collection,
                "results": search_results,
                "result_count": result_count
            }

            result = ToolExecutionResult.from_raw_data(
                tool_call_id=tool_call_id,
                raw_data=result_data,
                output_level=output_level,
                tool_name="search_knowledge",
                cache_policy=ToolCachePolicy.TTL_SHORT,  # 搜索结果可短时缓存
            )
            result.observation = summary if output_level == OutputLevel.BRIEF else result.observation
            result.duration_ms = duration_ms

            return result
        else:
            # 旧格式：ToolOutput
            telemetry = ToolTelemetry(tool_name="search_knowledge")
            telemetry.latency_ms = duration_ms
            telemetry.success = True

            # 构建观察结果（ReAct 格式）
            observation = f"Observation: {summary}\nStatus: Success"

            # 构建输出
            output = ToolOutput(
                result={
                    "query": query,
                    "collection": collection,
                    "results": search_results,
                    "result_count": result_count
                } if format_enum != ResponseFormat.CONCISE else None,
                summary=summary,
                observation=observation,
                telemetry=telemetry,
                response_format=ResponseFormat(format_enum)
            )

            return output.model_dump_json()

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000

        if use_pipeline:
            # 新格式错误结果
            import uuid
            tool_call_id = f"call_search_knowledge_{uuid.uuid4().hex[:12]}"
            return ToolExecutionResult.create_error(
                tool_call_id=tool_call_id,
                error_message=str(e),
                error_type=type(e).__name__,
                tool_name="search_knowledge",
            ).with_duration(duration_ms)
        else:
            # 旧格式错误结果
            telemetry = ToolTelemetry(tool_name="search_knowledge")
            telemetry.latency_ms = duration_ms
            telemetry.success = False
            telemetry.error_code = type(e).__name__
            telemetry.error_message = str(e)

            output = ToolOutput(
                summary=f"搜索失败: {str(e)}",
                observation=f"Observation: 搜索失败 - {str(e)}\nStatus: Error",
                telemetry=telemetry,
                response_format=ResponseFormat(format_enum)
            )

            return output.model_dump_json()


# 创建 LangChain 工具（保持兼容）
vector_search_tool = StructuredTool.from_function(
    func=vector_search_impl,
    name="search_knowledge",
    description="""
执行向量搜索，从知识库中检索相关的指标定义、维度说明等文档。

支持的操作：
- 语义搜索：根据查询内容查找相关文档
- 元数据过滤：按类型（metric/dimension）、类别等过滤
- 相似度控制：设置最小相似度阈值

知识库内容：
- 业务指标定义（GMV、转化率、ROAS 等）
- 维度说明（品类、渠道、地区等）
- 业务术语解释

使用场景：
- 查询指标定义: "什么是 GMV?"
- 查询维度说明: "品类维度是什么?"
- 搜索相关概念: "广告相关指标"

响应格式：
- concise/brief: 仅摘要
- standard: 摘要 + 结果
- detailed/full: 完整信息

参数说明：
- query: 搜索查询文本
- collection: 集合名称（默认: ba_agent）
- max_results: 最大返回结果数（1-50）
- min_score: 最小相似度分数（0-1）
- filter_metadata: 元数据过滤，例如 {"type": "metric", "category": "sales"}
""",
    args_schema=VectorSearchInput
)


__all__ = [
    "VectorSearchInput",
    "vector_search_impl",
    "vector_search_tool",
    "InMemoryVectorStore",
    "ChromaDBVectorStore",
]
