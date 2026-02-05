"""
Memory Flush - 自动记忆持久化

当会话接近上下文限制时自动保存记忆到磁盘
"""

import json
import logging
import time
import re
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

try:
    from token_monitor import TokenMonitor
    HAS_TOKEN_MONITOR = True
except ImportError:
    HAS_TOKEN_MONITOR = False

try:
    from zhipuai import ZhipuAI
    HAS_ZHIPU = True
except ImportError:
    HAS_ZHIPU = False


class RetainFormatter:
    """
    Retain 格式化器

    将对话内容格式化为结构化的 Retain 格式
    参考 clawdbot 的 Retain 格式: W/B/O(c=)/S @entity
    """

    # 世界事实 (World Facts)
    WORLD_PREFIX = "W"

    # 传记 (Biography)
    BIO_PREFIX = "B"

    # 观点 (Opinion with confidence)
    OPINION_PREFIX = "O"

    # 总结 (Summary)
    SUMMARY_PREFIX = "S"

    @staticmethod
    def format_world(fact: str, entity: Optional[str] = None) -> str:
        """
        格式化世界事实

        Args:
            fact: 事实描述
            entity: 关联实体 (可选)

        Returns:
            格式化字符串，如 "W @entity: fact" 或 "W: fact"
        """
        if entity:
            return f"{RetainFormatter.WORLD_PREFIX} @{entity}: {fact}"
        return f"{RetainFormatter.WORLD_PREFIX}: {fact}"

    @staticmethod
    def format_bio(fact: str, entity: Optional[str] = None) -> str:
        """
        格式化传记信息

        Args:
            fact: 传记事实
            entity: 关联实体 (可选)

        Returns:
            格式化字符串
        """
        if entity:
            return f"{RetainFormatter.BIO_PREFIX} @{entity}: {fact}"
        return f"{RetainFormatter.BIO_PREFIX}: {fact}"

    @staticmethod
    def format_opinion(
        opinion: str,
        confidence: float = 0.5,
        entity: Optional[str] = None
    ) -> str:
        """
        格式化观点

        Args:
            opinion: 观点描述
            confidence: 置信度 (0-1)
            entity: 关联实体 (可选)

        Returns:
            格式化字符串，如 "O(c=0.8) @entity: opinion"
        """
        conf_str = f"(c={confidence:.1f})" if confidence != 0.5 else ""
        if entity:
            return f"{RetainFormatter.OPINION_PREFIX}{conf_str} @{entity}: {opinion}"
        return f"{RetainFormatter.OPINION_PREFIX}{conf_str}: {opinion}"

    @staticmethod
    def format_summary(summary: str, entity: Optional[str] = None) -> str:
        """
        格式化总结

        Args:
            summary: 总结内容
            entity: 关联实体 (可选)

        Returns:
            格式化字符串
        """
        if entity:
            return f"{RetainFormatter.SUMMARY_PREFIX} @{entity}: {summary}"
        return f"{RetainFormatter.SUMMARY_PREFIX}: {summary}"

    @staticmethod
    def parse_retain(line: str) -> Optional[Dict[str, Any]]:
        """
        解析 Retain 格式行

        Args:
            line: Retain 格式字符串

        Returns:
            解析后的字典，包含 type, entity, content, confidence
        """
        line = line.strip()

        # 检查 @entity 格式
        if " @" in line and ": " in line:
            # TYPE @entity: content 或 O(c=X) @entity: content
            at_pos = line.find(" @")
            colon_pos = line.find(": ", at_pos)

            if at_pos > 0 and colon_pos > at_pos:
                prefix = line[:at_pos].strip()
                entity = line[at_pos + 2:colon_pos].strip()
                content = line[colon_pos + 2:].strip()

                # 解析前缀 (TYPE 或 TYPE(c=X))
                result = RetainFormatter._parse_prefix(prefix)
                if result:
                    result["entity"] = entity
                    result["content"] = content
                    return result

        # 无 @entity 格式: TYPE: content 或 TYPE(c=X): content
        if ": " in line:
            colon_pos = line.find(": ")
            prefix = line[:colon_pos].strip()
            content = line[colon_pos + 2:].strip()

            result = RetainFormatter._parse_prefix(prefix)
            if result:
                result["entity"] = None
                result["content"] = content
                return result

        return None

    @staticmethod
    def _parse_prefix(prefix: str) -> Optional[Dict[str, Any]]:
        """解析前缀部分 (TYPE 或 TYPE(c=X))"""
        # 匹配 O(c=X) 格式
        o_match = re.match(r'^O\((c=(\d+\.?\d*))\)$', prefix)
        if o_match:
            confidence_str = o_match.group(2)
            try:
                confidence = float(confidence_str)
            except ValueError:
                confidence = 0.5
            return {
                "type": "O",
                "entity": None,
                "content": None,
                "confidence": confidence
            }

        # 匹配 W, B, S 格式
        if prefix in ["W", "B", "S"]:
            return {
                "type": prefix,
                "entity": None,
                "content": None,
                "confidence": None
            }

        # 匹配 O: 格式（无置信度）
        if prefix == "O":
            return {
                "type": "O",
                "entity": None,
                "content": None,
                "confidence": None
            }

        return None


class MemoryExtractor:
    """
    记忆提取器

    从对话消息中提取重要信息并格式化为 Retain 格式
    优先使用 LLM (GLM-4.7)，失败时回退到正则表达式模式
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "glm-4.7-flash",
        use_llm: bool = True,
        llm_timeout: int = 30
    ):
        """
        初始化提取器

        Args:
            api_key: ZhipuAI API 密钥（可选，默认从环境变量读取）
            model: 模型名称（默认 glm-4.7-flash）
            use_llm: 是否使用 LLM（默认 True）
            llm_timeout: LLM 请求超时时间（秒）
        """
        self.api_key = api_key
        self.model = model
        self.use_llm = use_llm and HAS_ZHIPU
        self.llm_timeout = llm_timeout
        self._client = None

        # 关键词模式（作为 LLM 失败时的降级方案）
        self.patterns = {
            "world": [
                r"(?:记住|note|remember)\s*[：:]\s*(.+?)(?:\.|$|\n)",
                r"(.+?)是(.+?)(?:\.|$|\n)",  # X 是 Y
            ],
            "bio": [
                r"(?:我|用户)\s*(?:喜欢|偏好|习惯|爱好)\s*(.+?)(?:\.|$|\n)",
                r"(?:用户|user)\s*说\s*[：:]\s*(.+?)(?:\.|$|\n)",
            ],
            "opinion": [
                r"(?:认为|觉得|看来|建议|推荐)\s*(.+?)(?:\.|$|\n)",
            ]
        }

    @property
    def client(self):
        """懒加载 ZhipuAI 客户端"""
        if self._client is None:
            import os
            key = self.api_key or os.getenv("ZHIPUAI_API_KEY")
            if not key:
                raise ValueError("ZhipuAI API key is required. Set ZHIPUAI_API_KEY environment variable.")
            self._client = ZhipuAI(api_key=key)
        return self._client

    def extract_from_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[str]:
        """
        从消息列表中提取记忆

        Args:
            messages: 消息列表，每个消息包含 role 和 content

        Returns:
            提取的 Retain 格式记忆列表
        """
        # 过滤空消息
        valid_messages = [m for m in messages if m.get("content")]

        if not valid_messages:
            return []

        # 优先使用 LLM 提取
        if self.use_llm:
            try:
                logger.debug(f"使用 LLM 提取记忆，消息数: {len(valid_messages)}")
                memories = self._extract_with_llm(valid_messages)
                if memories:
                    logger.info(f"LLM 提取到 {len(memories)} 条记忆")
                    return memories
            except Exception as e:
                logger.warning(f"LLM 提取失败，回退到正则表达式: {e}")

        # 回退到正则表达式提取
        memories = self._extract_with_regex(valid_messages)
        if memories:
            logger.info(f"正则表达式提取到 {len(memories)} 条记忆")
        return memories

    def _extract_with_llm(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        使用 LLM 提取记忆

        Args:
            messages: 消息列表

        Returns:
            提取的 Retain 格式记忆列表
        """
        # 构建对话上下文
        conversation = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                conversation.append(f"用户: {content}")
            elif role == "assistant":
                conversation.append(f"助手: {content}")

        conversation_text = "\n".join(conversation)

        # 构建 LLM 提示词
        system_prompt = """你是一个专业的记忆提取助手。你的任务是从对话中提取重要信息，并将其格式化为 Retain 格式。

Retain 格式说明：
- W @entity: fact - 世界事实 (World Facts)
  例如: W @Python: Python 是一种编程语言
  例如: W: 地球绕太阳公转

- B @entity: fact - 传记信息 (Biography)
  例如: B @Alice: Alice 是一名软件工程师
  例如: B: 用户喜欢喝咖啡

- O(c=X) @entity: opinion - 观点 (Opinion)
  例如: O(c=0.8) @React: React 是高效的前端框架
  例如: O(c=0.6): 我认为这个方案可行

- S @entity: summary - 总结 (Summary)
  例如: S @Session1: 我们讨论了记忆系统的设计
  例如: S: 会议完成了既定目标

规则：
1. 只提取真正重要的、值得长期保存的信息
2. 每行一个记忆，使用 Retain 格式
3. 如果没有明确的实体，可以省略 @entity 部分
4. 观点需要有明确的置信度 c=0.0-1.0，默认 0.7
5. 返回纯文本，每行一个记忆，不要有额外的解释
6. 如果对话中没有值得保存的信息，返回空行

请分析以下对话，提取重要的记忆："""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": conversation_text}
                ],
                temperature=0.3,
                max_tokens=2000,
                timeout=self.llm_timeout
            )

            result_text = response.choices[0].message.content.strip()

            # 解析 LLM 返回的结果
            memories = []
            for line in result_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('```'):
                    # 验证是否是有效的 Retain 格式
                    parsed = RetainFormatter.parse_retain(line)
                    if parsed:
                        memories.append(line)
                    elif line.startswith(('W:', 'B:', 'O:', 'S:', 'W @', 'B @', 'O(', 'S @')):
                        # 看起来像 Retain 格式但解析失败，直接添加
                        memories.append(line)

            return memories

        except Exception as e:
            # LLM 调用失败，抛出异常让上层回退到正则表达式
            raise RuntimeError(f"LLM extraction failed: {e}")

    def _extract_with_regex(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        使用正则表达式提取记忆（降级方案）

        Args:
            messages: 消息列表

        Returns:
            提取的 Retain 格式记忆列表
        """
        memories = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if not content:
                continue

            # 从用户消息中提取
            if role == "user":
                extracted = self._extract_from_content(content)
                memories.extend(extracted)

            # 从助手响应中提取总结
            elif role == "assistant":
                summary = self._extract_summary(content)
                if summary:
                    memories.append(summary)

        return memories

    def _extract_from_content(self, content: str) -> List[str]:
        """从内容中提取记忆"""
        memories = []

        # 检测世界事实
        for pattern in self.patterns["world"]:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                fact = match.group(1).strip()
                if len(fact) > 5:  # 过滤太短的内容
                    memories.append(RetainFormatter.format_world(fact))

        # 检测传记信息
        for pattern in self.patterns["bio"]:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                fact = match.group(1).strip()
                if len(fact) > 5:
                    memories.append(RetainFormatter.format_bio(fact))

        # 检测观点
        for pattern in self.patterns["opinion"]:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                opinion = match.group(1).strip()
                if len(opinion) > 5:
                    memories.append(RetainFormatter.format_opinion(opinion, confidence=0.7))

        return memories

    def _extract_summary(self, content: str) -> Optional[str]:
        """从助手响应中提取总结"""
        # 检测总结性语句
        summary_patterns = [
            r"(?:总结|概括|综上)(?:来说)?[：:]\s*(.+?)(?:\.|$|\n)",
            r"总之[：:]\s*(.+?)(?:\.|$|\n)",
        ]

        for pattern in summary_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                summary = match.group(1).strip()
                if len(summary) > 10:
                    return RetainFormatter.format_summary(summary)

        return None


class MemoryFlushConfig:
    """Memory Flush 配置"""

    def __init__(
        self,
        soft_threshold: int = 4000,
        reserve: int = 2000,
        flush_callback: Optional[Callable[[List[str]], None]] = None,
        min_memory_count: int = 3,
        max_memory_age_hours: float = 24.0
    ):
        """
        初始化配置

        Args:
            soft_threshold: 软阈值 (token 数)，达到此值开始考虑 flush
            reserve: 保留的 token 数量
            flush_callback: Flush 回调函数，接收提取的记忆列表
            min_memory_count: 最少记忆数量，低于此数量不 flush
            max_memory_age_hours: 记忆最大年龄（小时），超过此年龄的会话不 flush
        """
        self.soft_threshold = soft_threshold
        self.reserve = reserve
        self.flush_callback = flush_callback
        self.min_memory_count = min_memory_count
        self.max_memory_age_hours = max_memory_age_hours

    @property
    def hard_threshold(self) -> int:
        """硬阈值 = 软阈值 + 保留量"""
        return self.soft_threshold + self.reserve


class MemoryFlush:
    """
    Memory Flush 监控器

    监控会话 token 使用，在接近限制时自动保存记忆
    """

    def __init__(
        self,
        config: Optional[MemoryFlushConfig] = None,
        memory_path: Optional[Path] = None,
        extractor: Optional[MemoryExtractor] = None
    ):
        """
        初始化 Memory Flush 监控器

        Args:
            config: Flush 配置
            memory_path: 记忆文件路径
            extractor: 记忆提取器（可选，默认创建新实例）
        """
        self.config = config or MemoryFlushConfig()
        self.memory_path = memory_path or Path("memory")

        # 会话状态
        self.session_start = time.time()
        self.message_count = 0
        self.total_tokens = 0
        self.last_flush_tokens = 0

        # 记忆提取器
        self.extractor = extractor or MemoryExtractor()

        # 消息缓存 (用于提取记忆)
        self.message_buffer: List[Dict[str, Any]] = []

    def update_token_count(self, tokens: int) -> None:
        """
        更新 token 计数

        Args:
            tokens: 当前使用的 token 数
        """
        self.total_tokens = tokens

    def add_message(self, role: str, content: str) -> None:
        """
        添加消息到缓存

        Args:
            role: 消息角色 (user/assistant/system)
            content: 消息内容
        """
        self.message_count += 1
        self.message_buffer.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

    def check_and_flush(
        self,
        current_tokens: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        检查是否需要 flush 并执行

        Args:
            current_tokens: 当前使用的 token 数
            force: 是否强制 flush

        Returns:
            Flush 结果字典
        """
        self.update_token_count(current_tokens)

        result = {
            "flushed": False,
            "memories_extracted": 0,
            "memories_written": 0,
            "reason": None,
            "error": None
        }

        # 检查是否需要 flush
        should_flush = force or self._should_flush(current_tokens)

        if should_flush:
            try:
                logger.info(f"Memory Flush 触发: tokens={current_tokens}, force={force}")
                # 提取记忆
                memories = self.extractor.extract_from_messages(self.message_buffer)

                # 过滤条件（强制 flush 时跳过 min_memory_count 检查）
                session_age = (time.time() - self.session_start) / 3600  # 小时

                if force or (len(memories) >= self.config.min_memory_count and session_age <= self.config.max_memory_age_hours):
                    # 执行 flush
                    memories_written = self._flush_memories(memories)

                    result["flushed"] = True
                    result["memories_extracted"] = len(memories)
                    result["memories_written"] = memories_written
                    result["reason"] = self._get_flush_reason(current_tokens)

                    logger.info(
                        f"Memory Flush 完成: 提取={len(memories)}, 写入={memories_written}, "
                        f"原因={result['reason']}"
                    )

                    # 清空缓存
                    self.message_buffer.clear()
                    self.last_flush_tokens = current_tokens
                else:
                    logger.debug(
                        f"Memory Flush 跳过: 记忆数不足 ({len(memories)} < {self.config.min_memory_count}) "
                        f"或会话年龄过长 ({session_age:.1f}h > {self.config.max_memory_age_hours}h)"
                    )

            except Exception as e:
                result["error"] = str(e)
                logger.error(f"Memory Flush 失败: {e}")

        return result

    def _should_flush(self, current_tokens: int) -> bool:
        """判断是否应该 flush"""
        # 检查硬阈值
        if current_tokens >= self.config.hard_threshold:
            return True

        # 检查软阈值且有足够的消息
        if current_tokens >= self.config.soft_threshold:
            # 距离上次 flush 有足够的增量
            delta = current_tokens - self.last_flush_tokens
            if delta >= self.config.reserve:
                return True

        return False

    def _get_flush_reason(self, current_tokens: int) -> str:
        """获取 flush 原因"""
        if current_tokens >= self.config.hard_threshold:
            return f"硬阈值触发 ({current_tokens} >= {self.config.hard_threshold})"
        elif current_tokens >= self.config.soft_threshold:
            return f"软阈值触发 ({current_tokens} >= {self.config.soft_threshold})"
        else:
            return "强制触发"

    def _flush_memories(self, memories: List[str]) -> int:
        """
        Flush 记忆到存储

        Args:
            memories: 记忆列表

        Returns:
            写入的记忆数量
        """
        written = 0

        # 使用回调函数
        if self.config.flush_callback:
            try:
                self.config.flush_callback(memories)
                written = len(memories)
            except Exception:
                # 回调失败，回退到文件写入
                pass

        # 回退到文件写入
        if written == 0:
            written = self._write_to_file(memories)

        return written

    def _write_to_file(self, memories: List[str]) -> int:
        """写入记忆到文件"""
        try:
            # 确保目录存在
            self.memory_path.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"{date_str}.md"
            file_path = self.memory_path / filename

            logger.debug(f"写入记忆到文件: {file_path}")

            # 追加写入
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n## Memory Flush ({datetime.now().strftime('%H:%M:%S')})\n\n")

                for memory in memories:
                    f.write(f"- {memory}\n")

                f.write("\n")

            logger.info(f"记忆已写入: {filename} ({len(memories)} 条)")
            return len(memories)

        except Exception as e:
            logger.error(f"写入记忆文件失败: {e}")
            return 0

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        session_age = time.time() - self.session_start

        return {
            "session_start": datetime.fromtimestamp(self.session_start).isoformat(),
            "session_age_seconds": session_age,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "last_flush_tokens": self.last_flush_tokens,
            "buffer_size": len(self.message_buffer),
            "config": {
                "soft_threshold": self.config.soft_threshold,
                "hard_threshold": self.config.hard_threshold,
                "reserve": self.config.reserve,
                "min_memory_count": self.config.min_memory_count,
            },
            "extractor": {
                "use_llm": self.extractor.use_llm,
                "model": self.extractor.model if self.extractor.use_llm else None
            }
        }

    def reset(self) -> None:
        """重置会话状态"""
        self.session_start = time.time()
        self.message_count = 0
        self.total_tokens = 0
        self.last_flush_tokens = 0
        self.message_buffer.clear()
