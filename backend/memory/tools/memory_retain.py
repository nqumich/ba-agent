"""
记忆格式化工具 - Retain 格式

提供便捷的方式将内容格式化为 Retain 结构化格式
参考 clawdbot 的 Retain 格式: W/B/O(c=)/S @entity
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from langchain_core.tools import StructuredTool

from backend.memory.flush import RetainFormatter


class MemoryRetainInput(BaseModel):
    """记忆格式化工具的输入参数"""

    content: str = Field(
        description="要格式化的内容"
    )
    retain_type: str = Field(
        description="Retain 类型: W (工作/世界事实), B (传记), O (观点), S (总结)"
    )
    entity: Optional[str] = Field(
        default=None,
        description="关联实体 (可选)，例如 @数据团队, @用户名"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="置信度 (0-1)，仅用于 O 类型，默认 0.5"
    )

    @field_validator('retain_type')
    @classmethod
    def validate_retain_type(cls, v: str) -> str:
        """验证 Retain 类型"""
        valid_types = ['W', 'B', 'O', 'S', 'w', 'b', 'o', 's']
        v = v.upper()
        if v not in ['W', 'B', 'O', 'S']:
            raise ValueError(f"retain_type 必须是: W, B, O, S")
        return v

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        """验证置信度"""
        if v is not None:
            if v < 0 or v > 1:
                raise ValueError("confidence 必须在 0-1 之间")
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容"""
        v = v.strip()
        if not v:
            raise ValueError("content 不能为空")
        if len(v) > 5000:
            raise ValueError("content 长度不能超过 5000 字符")
        return v


def memory_retain(
    content: str,
    retain_type: str,
    entity: Optional[str] = None,
    confidence: Optional[float] = None
) -> str:
    """
    将内容格式化为 Retain 结构化格式

    Args:
        content: 要格式化的内容
        retain_type: Retain 类型 (W/B/O/S)
            - W: 世界事实 (World Facts) - 工作记录、技术决策、项目状态
            - B: 传记 (Biography) - 用户信息、偏好、经历
            - O: 观点 (Opinion) - 带置信度的观点和判断
            - S: 总结 (Summary) - 会议总结、对话摘要
        entity: 关联实体 (可选)，例如 "数据团队", "张三"
        confidence: 置信度 (0-1)，仅用于 O 类型

    Returns:
        格式化后的 Retain 字符串

    Examples:
        >>> memory_retain("完成 GMV 异常检测功能", "W", "数据团队")
        "W @数据团队: 完成 GMV 异常检测功能"

        >>> memory_retain("用户偏好 Markdown 格式的报告", "B", "张三")
        "B @张三: 用户偏好 Markdown 格式的报告"

        >>> memory_retain("安全库存应保持 7 天以上", "O", "库存管理", 0.9)
        "O(c=0.9) @库存管理: 安全库存应保持 7 天以上"

        >>> memory_retain("讨论了 Q1 季度规划", "S")
        "S: 讨论了 Q1 季度规划"
    """
    # 标准化类型
    retain_type = retain_type.upper()

    # 根据类型调用相应的格式化方法
    if retain_type == "W":
        return RetainFormatter.format_world(content, entity)
    elif retain_type == "B":
        return RetainFormatter.format_bio(content, entity)
    elif retain_type == "O":
        conf = confidence if confidence is not None else 0.5
        return RetainFormatter.format_opinion(content, conf, entity)
    elif retain_type == "S":
        return RetainFormatter.format_summary(content, entity)
    else:
        # 不应该到达这里，因为 validator 已经检查过了
        raise ValueError(f"Unknown retain_type: {retain_type}")


def memory_retain_parse(formatted: str) -> dict:
    """
    解析 Retain 格式字符串

    Args:
        formatted: Retain 格式字符串，如 "W @entity: content" 或 "O(c=0.8) @entity: content"

    Returns:
        解析后的字典，包含 type, entity, content, confidence

    Examples:
        >>> memory_retain_parse("W @数据团队: 完成 GMV 异常检测功能")
        {"type": "W", "entity": "数据团队", "content": "完成 GMV 异常检测功能", "confidence": None}

        >>> memory_retain_parse("O(c=0.9) @库存管理: 安全库存应保持 7 天以上")
        {"type": "O", "entity": "库存管理", "content": "安全库存应保持 7 天以上", "confidence": 0.9}
    """
    result = RetainFormatter.parse_retain(formatted)
    if result is None:
        return {
            "error": f"无法解析 Retain 格式: {formatted}",
            "original": formatted
        }
    return result


# 创建格式化工具
memory_retain_tool = StructuredTool.from_function(
    func=memory_retain,
    name="memory_retain",
    description="""
将内容格式化为 Retain 结构化记忆格式。

**Retain 类型**:
- W (World Facts): 工作记录、技术决策、项目状态
- B (Biography): 用户信息、偏好、经历
- O (Opinion): 带置信度的观点和判断 (需要 confidence 参数)
- S (Summary): 会议总结、对话摘要

**参数**:
- content: 要格式化的内容 (必需)
- retain_type: Retain 类型 (必需，W/B/O/S)
- entity: 关联实体 (可选)，例如 "数据团队", "张三"
- confidence: 置信度 0-1 (可选，仅用于 O 类型，默认 0.5)

**示例**:
- 工作记录: memory_retain("完成 GMV 异常检测功能", "W", "数据团队")
- 用户偏好: memory_retain("用户偏好 Markdown 格式的报告", "B", "张三")
- 观点判断: memory_retain("安全库存应保持 7 天以上", "O", "库存管理", 0.9)
- 会议总结: memory_retain("讨论了 Q1 季度规划", "S")

**返回**: 格式化后的 Retain 字符串，可配合 memory_write 使用
""",
    args_schema=MemoryRetainInput
)

# 创建解析工具
memory_retain_parse_tool = StructuredTool.from_function(
    func=memory_retain_parse,
    name="memory_retain_parse",
    description="""
解析 Retain 格式字符串，提取其结构化信息。

**参数**:
- formatted: Retain 格式字符串，如 "W @entity: content" 或 "O(c=0.8) @entity: content"

**返回**:
包含 type, entity, content, confidence 的字典

**示例**:
- memory_retain_parse("W @数据团队: 完成 GMV 异常检测功能")
  → {"type": "W", "entity": "数据团队", "content": "完成 GMV 异常检测功能", "confidence": None}
- memory_retain_parse("O(c=0.9) @库存管理: 安全库存应保持 7 天以上")
  → {"type": "O", "entity": "库存管理", "content": "安全库存应保持 7 天以上", "confidence": 0.9}

**用途**: 验证 Retain 格式是否正确，或提取结构化信息
""",
    args_schema=None  # 使用单个字符串参数，不需要 schema
)
