"""
测试数据模型的类型验证和序列化

US-002: 核心数据模型定义 (Pydantic)
"""

import pytest
from datetime import datetime, date
from pydantic import ValidationError

from backend.models.base import TimestampMixin, MetadataMixin, IDMixin, BaseSchema
from backend.models.query import Query, QueryContext, QueryResult, DataSource, DataPoint
from backend.models.tool import ToolInput, ToolOutput, ToolConfig, ToolCall
from backend.models.skill import SkillParameter, SkillConfig, SkillInput, SkillResult, SkillManifest
from backend.models.analysis import (
    Anomaly, AnomalyType, AnomalySeverity,
    Attribution, AttributionType, AttributionFactor,
    Insight, InsightType
)
from backend.models.report import (
    Report, ReportType, ReportFormat, ChartType,
    ReportSection, ChartConfig, MetricSummary, ReportRequest
)
from backend.models.agent import (
    Message, MessageRole, MessageType,
    AgentState, Conversation, AgentTask, AgentConfig
)
from backend.models.memory import (
    MemoryEntry, MemoryKind, MemoryLevel,
    DailyLog, LongTermMemory, ContextBootstrap,
    MemorySearchQuery, MemorySearchResult, MemoryWriteRequest, WorkingMemory
)


class TestBaseModels:
    """测试基础模型类"""

    def test_id_mixin_generates_id(self):
        """测试 IDMixin 自动生成 ID"""
        class TestModel(IDMixin):
            pass

        model = TestModel()
        assert model.id is not None
        assert len(model.id) > 0
        assert isinstance(model.id, str)

    def test_timestamp_mixin_generates_timestamps(self):
        """测试 TimestampMixin 自动生成时间戳"""
        class TestModel(TimestampMixin):
            pass

        model = TestModel()
        assert model.created_at is not None
        assert model.updated_at is not None
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)

    def test_base_schema_has_all_fields(self):
        """测试 BaseSchema 包含所有字段"""
        model = BaseSchema()
        assert model.id is not None
        assert model.created_at is not None
        assert model.updated_at is not None
        assert isinstance(model.metadata, dict)


class TestQueryModels:
    """测试查询相关模型"""

    def test_query_validation(self):
        """测试 Query 模型验证"""
        query = Query(
            id="query-001",
            user_id="user-001",
            conversation_id="conv-001",
            text="昨天的GMV异常下降了，帮我分析原因",
            intent="anomaly_detection",
            entities={"date": "2025-02-03", "metric": "GMV"}
        )
        assert query.id == "query-001"
        assert query.text == "昨天的GMV异常下降了，帮我分析原因"
        assert query.intent == "anomaly_detection"
        assert query.entities["metric"] == "GMV"

    def test_query_result_serialization(self):
        """测试 QueryResult 序列化"""
        result = QueryResult(
            id="result-001",
            query_id="query-001",
            data=[
                DataPoint(
                    dimension={"date": "2025-02-03"},
                    metric="GMV",
                    value=15000.0,
                    timestamp=datetime(2025, 2, 3)
                )
            ],
            sources=[
                DataSource(
                    type="database",
                    name="production_db",
                    query="SELECT * FROM sales"
                )
            ],
            status="success",
            execution_time=0.5
        )
        serialized = result.model_dump()
        assert serialized["id"] == "result-001"
        assert serialized["status"] == "success"
        assert len(serialized["data"]) == 1
        assert serialized["data"][0]["value"] == 15000.0


class TestToolModels:
    """测试工具相关模型"""

    def test_tool_input_validation(self):
        """测试 ToolInput 验证"""
        input = ToolInput(
            tool_name="query_database",
            parameters={
                "sql": "SELECT * FROM sales LIMIT 10",
                "database": "production"
            }
        )
        assert input.tool_name == "query_database"
        assert input.parameters["sql"] == "SELECT * FROM sales LIMIT 10"

    def test_tool_config_constraints(self):
        """测试 ToolConfig 约束"""
        config = ToolConfig(
            name="query_database",
            description="查询数据库",
            timeout=60,
            max_retries=3,
            required_params=["sql"],
            allowed_params=["sql", "database"]
        )
        assert config.timeout == 60
        assert config.max_retries == 3
        assert "sql" in config.required_params


class TestSkillModels:
    """测试 Skill 相关模型"""

    def test_skill_config_validation(self):
        """测试 SkillConfig 验证"""
        skill = SkillConfig(
            id="skill-001",
            name="anomaly_detection",
            description="异动检测 Skill",
            category="analysis",
            entrypoint="skills.anomaly_detection.main",
            function="detect",
            parameters=[
                SkillParameter(
                    name="data",
                    type="object",
                    description="要检测的数据",
                    required=True
                )
            ]
        )
        assert skill.name == "anomaly_detection"
        assert skill.category == "analysis"
        assert len(skill.parameters) == 1
        assert skill.parameters[0].required is True

    def test_skill_manifest_search(self):
        """测试 SkillManifest 搜索"""
        manifest = SkillManifest(
            skills=[
                SkillConfig(
                    id="skill-001",
                    name="anomaly_detection",
                    description="异动检测",
                    category="analysis",
                    entrypoint="skills.main",
                    function="detect",
                    parameters=[]
                ),
                SkillConfig(
                    id="skill-002",
                    name="report_gen",
                    description="报告生成",
                    category="reporting",
                    entrypoint="skills.main",
                    function="generate",
                    parameters=[]
                )
            ]
        )
        skill = manifest.get_skill("anomaly_detection")
        assert skill is not None
        assert skill.name == "anomaly_detection"

        analysis_skills = manifest.get_skills_by_category("analysis")
        assert len(analysis_skills) == 1


class TestAnalysisModels:
    """测试业务分析模型"""

    def test_anomaly_validation(self):
        """测试 Anomaly 验证"""
        anomaly = Anomaly(
            id="anomaly-001",
            metric="GMV",
            anomaly_type=AnomalyType.DROP,
            severity=AnomalySeverity.HIGH,
            baseline=15000.0,
            actual=10500.0,
            deviation=-30.0,
            confidence=0.95,
            timestamp=datetime(2025, 2, 3),
            dimensions={"region": "华东", "category": "electronics"}
        )
        assert anomaly.metric == "GMV"
        assert anomaly.anomaly_type == AnomalyType.DROP
        assert anomaly.severity == AnomalySeverity.HIGH
        assert anomaly.deviation == -30.0

    def test_attribution_factors(self):
        """测试 Attribution 因子"""
        attribution = Attribution(
            id="attr-001",
            metric="GMV",
            change=-4500.0,
            change_percent=-30.0,
            baseline=15000.0,
            actual=10500.0,
            period_start=datetime(2025, 2, 3),
            period_end=datetime(2025, 2, 3, 23, 59, 59),
            factors=[
                AttributionFactor(
                    factor="electronics品类下降",
                    type=AttributionType.DIMENSION,
                    contribution=-22.0,
                    confidence=0.95
                )
            ],
            top_factor="electronics品类下降",
            explanation="GMV下降30%主要由electronics品类下降导致"
        )
        assert attribution.change == -4500.0
        assert len(attribution.factors) == 1
        assert attribution.factors[0].contribution == -22.0

    def test_insight_type_validation(self):
        """测试 Insight 类型验证"""
        insight = Insight(
            id="insight-001",
            type=InsightType.OPPORTUNITY,
            title="用户增长趋势",
            description="新用户增长呈上升趋势",
            metric="新用户数",
            value=1500.0,
            impact="high",
            confidence=0.85,
            period_start=datetime(2025, 2, 1),
            period_end=datetime(2025, 2, 3)
        )
        assert insight.type == InsightType.OPPORTUNITY
        assert insight.impact == "high"


class TestReportModels:
    """测试报告相关模型"""

    def test_report_validation(self):
        """测试 Report 验证"""
        report = Report(
            id="report-001",
            type=ReportType.DAILY,
            format=ReportFormat.PDF,
            title="每日业务分析报告",
            period_start=datetime(2025, 2, 4),
            period_end=datetime(2025, 2, 4, 23, 59, 59),
            metrics=[
                MetricSummary(
                    name="GMV",
                    current_value=15000.0,
                    previous_value=14500.0,
                    change=500.0,
                    change_percent=3.45,
                    trend="up"
                )
            ]
        )
        assert report.type == ReportType.DAILY
        assert report.format == ReportFormat.PDF
        assert len(report.metrics) == 1
        assert report.metrics[0].trend == "up"

    def test_chart_config_validation(self):
        """测试 ChartConfig 验证"""
        chart = ChartConfig(
            id="chart-001",
            title="GMV 趋势图",
            type=ChartType.LINE,
            data={
                "xAxis": ["2025-02-01", "2025-02-02", "2025-02-03"],
                "yAxis": [14500, 15000, 10500]
            },
            options={"title": {"text": "GMV 趋势"}}
        )
        assert chart.type == ChartType.LINE
        assert chart.data["xAxis"][0] == "2025-02-01"


class TestAgentModels:
    """测试 Agent 相关模型"""

    def test_message_validation(self):
        """测试 Message 验证"""
        message = Message(
            id="msg-001",
            role=MessageRole.ASSISTANT,
            type=MessageType.TOOL_CALL,
            content="让我查询一下数据库",
            tool_calls=[
                {
                    "tool": "query_database",
                    "parameters": {"sql": "SELECT * FROM sales"}
                }
            ]
        )
        assert message.role == MessageRole.ASSISTANT
        assert message.type == MessageType.TOOL_CALL
        assert len(message.tool_calls) == 1

    def test_conversation_state(self):
        """测试 Conversation 状态"""
        conv = Conversation(
            id="conv-001",
            user_id="user-001",
            title="GMV 异常分析",
            state=AgentState.THINKING,
            messages=[],
            context={"current_task": "anomaly_detection"}
        )
        assert conv.state == AgentState.THINKING
        assert conv.context["current_task"] == "anomaly_detection"

    def test_agent_config_validation(self):
        """测试 AgentConfig 验证"""
        config = AgentConfig(
            name="BA-Agent",
            model="claude-3-5-sonnet-20241022",
            temperature=0.7,
            max_tokens=4096,
            system_prompt="你是一个专业的商业分析助手",
            tools=["query_database", "invoke_skill"],
            memory_enabled=True,
            hooks_enabled=True
        )
        assert config.name == "BA-Agent"
        assert config.temperature == 0.7
        assert config.memory_enabled is True


class TestMemoryModels:
    """测试记忆相关模型"""

    def test_memory_entry_validation(self):
        """测试 MemoryEntry 验证"""
        entry = MemoryEntry(
            id="mem-001",
            level=MemoryLevel.LAYER_1,
            kind=MemoryKind.DAILY,
            content="# 2025-02-04 工作日志",
            source="task-002",
            tags=["US-002", "models"],
            importance=0.8
        )
        assert entry.level == MemoryLevel.LAYER_1
        assert entry.kind == MemoryKind.DAILY
        assert entry.importance == 0.8

    def test_daily_log_validation(self):
        """测试 DailyLog 验证"""
        log = DailyLog(
            id="log-20250204",
            level=MemoryLevel.LAYER_1,
            kind=MemoryKind.DAILY,
            content="# 工作日志",
            source="manual",
            log_date=date(2025, 2, 4),
            tasks_completed=["US-002"],
            findings=["Pydantic 模型验证需要添加测试"],
            decisions=["使用 Pydantic v2"],
            next_steps=["添加模型验证测试"]
        )
        assert log.log_date == date(2025, 2, 4)
        assert len(log.tasks_completed) == 1
        assert "US-002" in log.tasks_completed

    def test_memory_search_query(self):
        """测试 MemorySearchQuery 验证"""
        query = MemorySearchQuery(
            query="用户偏好的报告格式",
            kind=MemoryKind.LONG_TERM,
            limit=5
        )
        assert query.query == "用户偏好的报告格式"
        assert query.kind == MemoryKind.LONG_TERM
        assert query.limit == 5

    def test_working_memory_validation(self):
        """测试 WorkingMemory 验证"""
        working = WorkingMemory(
            conversation_id="conv-001",
            context={"current_metric": "GMV"},
            active_task="task-001",
            recent_tools=["query_database", "detect_anomaly"],
            attention_focus=["task_plan.md", "US-002"],
            step_count=3
        )
        assert working.conversation_id == "conv-001"
        assert working.step_count == 3
        assert "task_plan.md" in working.attention_focus


class TestModelSerialization:
    """测试模型序列化和反序列化"""

    def test_query_json_serialization(self):
        """测试 Query JSON 序列化"""
        query = Query(
            id="query-001",
            user_id="user-001",
            conversation_id="conv-001",
            text="测试查询"
        )
        json_str = query.model_dump_json()
        assert '"id":"query-001"' in json_str
        assert '"text":"测试查询"' in json_str

        # 反序列化
        restored = Query.model_validate_json(json_str)
        assert restored.id == query.id
        assert restored.text == query.text

    def test_anomaly_json_serialization(self):
        """测试 Anomaly JSON 序列化"""
        anomaly = Anomaly(
            id="anomaly-001",
            metric="GMV",
            anomaly_type=AnomalyType.DROP,
            severity=AnomalySeverity.HIGH,
            baseline=15000.0,
            actual=10500.0,
            deviation=-30.0,
            timestamp=datetime(2025, 2, 3)
        )
        json_str = anomaly.model_dump_json()
        assert '"metric":"GMV"' in json_str
        assert '"deviation":-30.0' in json_str

    def test_report_dict_serialization(self):
        """测试 Report 字典序列化"""
        report = Report(
            id="report-001",
            type=ReportType.DAILY,
            title="测试报告",
            period_start=datetime(2025, 2, 4),
            period_end=datetime(2025, 2, 4)
        )
        data_dict = report.model_dump()
        assert data_dict["id"] == "report-001"
        assert data_dict["type"] == "daily"


class TestValidationErrorHandling:
    """测试验证错误处理"""

    def test_anomaly_confidence_out_of_range(self):
        """测试 Anomaly confidence 超出范围"""
        with pytest.raises(ValidationError):
            Anomaly(
                id="anomaly-001",
                metric="GMV",
                anomaly_type=AnomalyType.DROP,
                severity=AnomalySeverity.HIGH,
                baseline=15000.0,
                actual=10500.0,
                deviation=-30.0,
                confidence=1.5,  # 超出范围 [0, 1]
                timestamp=datetime(2025, 2, 3)
            )

    def test_metric_summary_importance_validation(self):
        """测试 Field 验证（如果有的话）"""
        summary = MetricSummary(
            name="GMV",
            current_value=15000.0,
            trend="up"
        )
        # 应该成功创建
        assert summary.name == "GMV"

    def test_required_field_missing(self):
        """测试必需字段缺失"""
        with pytest.raises(ValidationError):
            Query(
                id="query-001",
                user_id="user-001",
                conversation_id="conv-001"
                # text 字段缺失，应该报错
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
