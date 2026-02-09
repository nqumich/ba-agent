"""
Memory Store - 记忆文件存储

三层架构 (daily/context/knowledge)，支持文件引用
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import date, datetime

from backend.models.filestore import (
    FileRef,
    FileCategory,
    FileMetadata,
    MemoryRef,
    MemoryContent,
    MemoryLayer,
)
from backend.filestore.base import WriteableStore


class MemoryStore(WriteableStore):
    """
    记忆文件存储

    特性:
    - 保留 Markdown 格式
    - 支持文件引用
    - 三层架构 (daily/context/knowledge)
    """

    def __init__(self, storage_dir: Path):
        """
        初始化 MemoryStore

        Args:
            storage_dir: 存储目录
        """
        super().__init__(storage_dir)

        # 创建三层目录结构
        self.daily_dir = storage_dir / "daily"
        self.context_dir = storage_dir / "context"
        self.knowledge_dir = storage_dir / "knowledge"

        for dir_path in [self.daily_dir, self.context_dir, self.knowledge_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def write_daily_memory(
        self,
        content: str,
        target_date: Optional[date] = None,
        file_refs: Optional[List[FileRef]] = None,
        append: bool = True
    ) -> MemoryRef:
        """
        写入每日记忆

        Args:
            content: 记忆内容（Markdown 格式）
            target_date: 目标日期（默认为今天）
            file_refs: 关联的文件引用列表
            append: 是否追加到现有文件

        Returns:
            MemoryRef: 记忆文件引用
        """
        target_date = target_date or date.today()
        file_path = self.daily_dir / f"{target_date.isoformat()}.md"

        # 添加文件引用块
        if file_refs:
            content = self._append_file_refs_block(content, file_refs)

        # 写入文件
        if append and file_path.exists():
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n{content}")
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return MemoryRef(
            file_id=file_path.stem,
            layer=MemoryLayer.DAILY,
            path=file_path,
            created_at=datetime.now().timestamp(),
            file_refs=file_refs or []
        )

    def write_context_memory(
        self,
        name: str,
        content: str,
        file_refs: Optional[List[FileRef]] = None,
        overwrite: bool = True
    ) -> MemoryRef:
        """
        写入上下文记忆

        Args:
            name: 记忆名称（文件名，不含扩展名）
            content: 记忆内容
            file_refs: 关联的文件引用列表
            overwrite: 是否覆盖现有文件

        Returns:
            MemoryRef: 记忆文件引用
        """
        file_path = self.context_dir / f"{name}.md"

        if file_refs:
            content = self._append_file_refs_block(content, file_refs)

        mode = 'w' if overwrite else 'a'
        with open(file_path, mode, encoding='utf-8') as f:
            if overwrite or not file_path.exists():
                f.write(content)
            else:
                f.write(f"\n\n{content}")

        return MemoryRef(
            file_id=name,
            layer=MemoryLayer.CONTEXT,
            path=file_path,
            created_at=datetime.now().timestamp(),
            file_refs=file_refs or []
        )

    def write_knowledge_memory(
        self,
        category: str,
        name: str,
        content: str,
        file_refs: Optional[List[FileRef]] = None
    ) -> MemoryRef:
        """
        写入知识记忆

        Args:
            category: 知识类别（如 world, experience, opinions）
            name: 记忆名称
            content: 记忆内容
            file_refs: 关联的文件引用列表

        Returns:
            MemoryRef: 记忆文件引用
        """
        category_dir = self.knowledge_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        file_path = category_dir / f"{name}.md"

        if file_refs:
            content = self._append_file_refs_block(content, file_refs)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return MemoryRef(
            file_id=f"{category}/{name}",
            layer=MemoryLayer.KNOWLEDGE,
            path=file_path,
            created_at=datetime.now().timestamp(),
            file_refs=file_refs or []
        )

    def get_memory(self, memory_ref: MemoryRef) -> MemoryContent:
        """
        获取记忆内容

        Args:
            memory_ref: 记忆文件引用

        Returns:
            MemoryContent: 记忆内容
        """
        content = self._read_file(memory_ref.path)
        file_refs = self._extract_file_refs(content)

        return MemoryContent(
            content=content,
            file_refs=file_refs,
            metadata={}
        )

    def get_daily_memory(self, target_date: date) -> Optional[MemoryContent]:
        """
        获取指定日期的每日记忆

        Args:
            target_date: 目标日期

        Returns:
            MemoryContent，如果不存在返回 None
        """
        file_path = self.daily_dir / f"{target_date.isoformat()}.md"

        if not file_path.exists():
            return None

        memory_ref = MemoryRef(
            file_id=file_path.stem,
            layer=MemoryLayer.DAILY,
            path=file_path,
            created_at=datetime.now().timestamp()
        )

        return self.get_memory(memory_ref)

    def get_context_memory(self, name: str) -> Optional[MemoryContent]:
        """
        获取上下文记忆

        Args:
            name: 记忆名称

        Returns:
            MemoryContent，如果不存在返回 None
        """
        file_path = self.context_dir / f"{name}.md"

        if not file_path.exists():
            return None

        memory_ref = MemoryRef(
            file_id=name,
            layer=MemoryLayer.CONTEXT,
            path=file_path,
            created_at=datetime.now().timestamp()
        )

        return self.get_memory(memory_ref)

    def list_daily_memories(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: Optional[int] = None
    ) -> List[MemoryRef]:
        """
        列出每日记忆

        Args:
            date_from: 起始日期
            date_to: 结束日期
            limit: 返回数量限制

        Returns:
            MemoryRef 列表
        """
        memories = []

        for file_path in sorted(self.daily_dir.glob("*.md"), reverse=True):
            try:
                file_date = date.fromisoformat(file_path.stem)

                if date_from and file_date < date_from:
                    continue
                if date_to and file_date > date_to:
                    continue

                # 读取文件引用
                content = self._read_file(file_path)
                file_refs = self._extract_file_refs(content)

                memories.append(MemoryRef(
                    file_id=file_path.stem,
                    layer=MemoryLayer.DAILY,
                    path=file_path,
                    created_at=file_path.stat().st_ctime,
                    file_refs=file_refs
                ))

                if limit and len(memories) >= limit:
                    break
            except Exception:
                continue

        return memories

    def list_context_memories(self) -> List[MemoryRef]:
        """
        列出上下文记忆

        Returns:
            MemoryRef 列表
        """
        memories = []

        for file_path in self.context_dir.glob("*.md"):
            content = self._read_file(file_path)
            file_refs = self._extract_file_refs(content)

            memories.append(MemoryRef(
                file_id=file_path.stem,
                layer=MemoryLayer.CONTEXT,
                path=file_path,
                created_at=file_path.stat().st_ctime,
                file_refs=file_refs
            ))

        return sorted(memories, key=lambda m: m.created_at, reverse=True)

    # ========== BaseStore 接口实现 ==========

    def store(self, content: bytes, **metadata) -> FileRef:
        """
        存储（用于 BaseStore 兼容）

        Args:
            content: 文件内容
            **metadata: 元数据

        Returns:
            FileRef: 文件引用
        """
        text_content = content.decode('utf-8')
        layer = metadata.get('layer', MemoryLayer.DAILY)

        if layer == MemoryLayer.DAILY:
            mem_ref = self.write_daily_memory(text_content, append=False)
        elif layer == MemoryLayer.CONTEXT:
            name = metadata.get('name', 'memory')
            mem_ref = self.write_context_memory(name, text_content)
        else:
            # 默认使用 daily
            mem_ref = self.write_daily_memory(text_content, append=False)

        return FileRef(
            file_id=mem_ref.file_id,
            category=FileCategory.MEMORY,
            metadata={'memory_ref': mem_ref}
        )

    def retrieve(self, file_ref: FileRef) -> Optional[bytes]:
        """
        检索

        Args:
            file_ref: 文件引用

        Returns:
            文件内容
        """
        memory_ref = file_ref.metadata.get('memory_ref')
        if not memory_ref:
            return None

        content = self._read_file(memory_ref.path)
        return content.encode('utf-8') if content else None

    def delete(self, file_ref: FileRef) -> bool:
        """
        删除

        Args:
            file_ref: 文件引用

        Returns:
            是否成功删除
        """
        memory_ref = file_ref.metadata.get('memory_ref')
        if not memory_ref:
            return False

        if memory_ref.path.exists():
            memory_ref.path.unlink()
            return True

        return False

    def exists(self, file_ref: FileRef) -> bool:
        """
        检查是否存在

        Args:
            file_ref: 文件引用

        Returns:
            文件是否存在
        """
        memory_ref = file_ref.metadata.get('memory_ref')
        if not memory_ref:
            return False

        return memory_ref.path.exists()

    def list_files(self, layer: Optional[MemoryLayer] = None, **filters) -> List[FileMetadata]:
        """
        列出文件

        Args:
            layer: 记忆层级
            **filters: 其他过滤条件

        Returns:
            文件元数据列表
        """
        if layer == MemoryLayer.DAILY:
            dir_path = self.daily_dir
        elif layer == MemoryLayer.CONTEXT:
            dir_path = self.context_dir
        elif layer == MemoryLayer.KNOWLEDGE:
            dir_path = self.knowledge_dir
        else:
            dir_path = self.daily_dir

        results = []
        for file_path in dir_path.rglob("*.md"):
            stat = file_path.stat()
            results.append(FileMetadata(
                file_ref=FileRef(
                    file_id=file_path.stem,
                    category=FileCategory.MEMORY,
                    size_bytes=stat.st_size,
                    created_at=stat.st_ctime
                ),
                filename=file_path.name,
                created_at=datetime.fromtimestamp(stat.st_ctime)
            ))

        return results

    # ========== 内部方法 ==========

    def _read_file(self, file_path: Path) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容，如果读取失败返回空字符串
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ""

    def _append_file_refs_block(
        self,
        content: str,
        file_refs: List[FileRef]
    ) -> str:
        """
        在内容末尾添加文件引用块

        Args:
            content: 原始内容
            file_refs: 文件引用列表

        Returns:
            包含文件引用块的内容
        """
        if not file_refs:
            return content

        refs_block = "\n\n**关联文件**:\n"
        for ref in file_refs:
            refs_block += f"- `{ref.category.value}:{ref.file_id}`\n"

        return content + refs_block

    def _extract_file_refs(self, content: str) -> List[FileRef]:
        """
        从内容中提取文件引用

        Args:
            content: 内容文本

        Returns:
            FileRef 列表
        """
        # 匹配 `category:file_id` 格式
        pattern = r'`(\w+):([a-zA-Z0-9_:.-]+)`'
        refs = []

        for match in re.finditer(pattern, content):
            try:
                category = FileCategory(match.group(1))
                refs.append(FileRef(
                    file_id=match.group(2),
                    category=category
                ))
            except ValueError:
                # 无效的类别，跳过
                continue

        return refs


__all__ = [
    "MemoryStore",
]
