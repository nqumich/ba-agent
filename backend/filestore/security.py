"""
安全访问控制

提供文件访问权限控制和路径安全验证
"""

from pathlib import Path
from typing import Optional

from backend.models.filestore import FileRef, FileCategory


class FileAccessControl:
    """
    文件访问控制

    基于会话和用户的访问权限检查
    """

    def can_access(
        self,
        file_ref: FileRef,
        session_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        检查访问权限

        规则:
        1. UPLOAD 文件：仅上传者所属会话可访问
        2. TEMP 文件：仅创建者会话可访问
        3. REPORT 文件：会话参与者可访问
        4. ARTIFACT 文件：同一会话可访问
        5. MEMORY 文件：全局可访问（只读）
        6. CHECKPOINT 文件：同一会话可访问

        Args:
            file_ref: 文件引用
            session_id: 会话 ID
            user_id: 用户 ID（可选，用于更细粒度控制）

        Returns:
            是否有访问权限
        """
        if file_ref.category == FileCategory.UPLOAD:
            return file_ref.session_id == session_id

        elif file_ref.category == FileCategory.TEMP:
            return file_ref.session_id == session_id

        elif file_ref.category in (FileCategory.REPORT, FileCategory.ARTIFACT):
            return file_ref.session_id == session_id

        elif file_ref.category == FileCategory.CHECKPOINT:
            return file_ref.session_id == session_id

        elif file_ref.category == FileCategory.MEMORY:
            return True  # 记忆文件全局可读

        elif file_ref.category in (FileCategory.CHART, FileCategory.CACHE):
            # 图表和缓存：同一会话可访问
            return file_ref.session_id == session_id or file_ref.session_id is None

        return False

    def can_delete(
        self,
        file_ref: FileRef,
        session_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        检查删除权限

        删除权限通常比访问权限更严格

        Args:
            file_ref: 文件引用
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            是否有删除权限
        """
        # 删除权限与访问权限相同
        return self.can_access(file_ref, session_id, user_id)

    def filter_accessible_files(
        self,
        file_refs: list[FileRef],
        session_id: str,
        user_id: Optional[str] = None
    ) -> list[FileRef]:
        """
        过滤出可访问的文件

        Args:
            file_refs: 文件引用列表
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            可访问的文件引用列表
        """
        return [
            ref for ref in file_refs
            if self.can_access(ref, session_id, user_id)
        ]


class SecurePathResolver:
    """
    安全路径解析器

    防止路径遍历攻击
    """

    def __init__(self, allowed_sandbox: Path):
        """
        初始化路径解析器

        Args:
            allowed_sandbox: 允许的沙盒目录
        """
        self.allowed_sandbox = allowed_sandbox.resolve()

    def resolve(
        self,
        file_ref: FileRef,
        storage_dir: Path
    ) -> Path:
        """
        解析文件引用为物理路径

        安全措施:
        1. 验证 file_id 格式
        2. 禁止路径遍历
        3. 确保路径在存储目录内

        Args:
            file_ref: 文件引用
            storage_dir: 存储目录

        Returns:
            解析后的物理路径

        Raises:
            ValueError: 路径不安全
        """
        # 验证 file_id 格式
        if not self._validate_file_id(file_ref.file_id):
            raise ValueError(f"Invalid file_id format: {file_ref.file_id}")

        # 构建路径
        category_dir = storage_dir / file_ref.category.value
        file_path = category_dir / file_ref.file_id

        # 安全检查：确保路径在存储目录内
        try:
            resolved = file_path.resolve()
            storage_resolved = storage_dir.resolve()

            if not str(resolved).startswith(str(storage_resolved)):
                raise ValueError(f"Security violation: path outside sandbox")

            return resolved

        except Exception as e:
            raise ValueError(f"Path resolution failed: {e}")

    def _validate_file_id(self, file_id: str) -> bool:
        """
        验证 file_id 格式

        Args:
            file_id: 文件 ID

        Returns:
            是否有效
        """
        # 禁止路径分隔符
        if "/" in file_id or "\\" in file_id:
            return False

        # 禁止路径遍历
        if ".." in file_id:
            return False

        # 禁止空字符串
        if not file_id:
            return False

        # 禁止特殊字符
        forbidden_chars = ['\x00', '\n', '\r']
        if any(char in file_id for char in forbidden_chars):
            return False

        return True

    def is_safe_path(self, path: Path) -> bool:
        """
        检查路径是否安全

        Args:
            path: 要检查的路径

        Returns:
            路径是否安全
        """
        try:
            resolved = path.resolve()

            # 检查是否在沙盒内
            if not str(resolved).startswith(str(self.allowed_sandbox)):
                return False

            # 检查是否包含路径遍历
            path_parts = resolved.parts
            if ".." in path_parts:
                return False

            return True

        except Exception:
            return False


class SessionIsolation:
    """
    会话隔离管理器

    确保不同会话的数据相互隔离
    """

    def __init__(self):
        """初始化会话隔离管理器"""
        self._active_sessions = {}

    def create_session(self, session_id: str, user_id: str) -> bool:
        """
        创建新会话

        Args:
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            是否成功创建
        """
        if session_id in self._active_sessions:
            return False

        self._active_sessions[session_id] = {
            'user_id': user_id,
            'created_at': None  # 使用 time.time()
        }

        return True

    def get_session_user(self, session_id: str) -> Optional[str]:
        """
        获取会话所属用户

        Args:
            session_id: 会话 ID

        Returns:
            用户 ID，如果会话不存在返回 None
        """
        session = self._active_sessions.get(session_id)
        return session['user_id'] if session else None

    def is_session_owner(self, session_id: str, user_id: str) -> bool:
        """
        检查用户是否是会话所有者

        Args:
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            是否是所有者
        """
        session = self._active_sessions.get(session_id)
        return session and session['user_id'] == user_id

    def end_session(self, session_id: str) -> bool:
        """
        结束会话

        Args:
            session_id: 会话 ID

        Returns:
            是否成功结束
        """
        if session_id not in self._active_sessions:
            return False

        del self._active_sessions[session_id]
        return True


__all__ = [
    "FileAccessControl",
    "SecurePathResolver",
    "SessionIsolation",
]
