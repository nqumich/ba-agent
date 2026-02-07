"""
Pipeline Data Storage

Artifact-based file storage for large tool outputs.
Provides secure abstraction between LLM-visible artifact_id and real filesystem paths.

Design v2.0.1:
- artifact_id: Public safe identifier (e.g., "artifact_abc123")
- data_file: Private real path (never exposed to LLM)
- Sandbox validation: All access restricted to storage directory
- Automatic cleanup: Old files removed based on TTL
"""

import hashlib
import json
import os
import platform
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


def _get_default_storage_dir() -> Path:
    """
    获取默认的存储目录（跨平台）

    Returns:
        默认存储目录路径
    """
    # 检查环境变量
    env_dir = os.getenv("BA_STORAGE_DIR")
    if env_dir:
        base = Path(env_dir).expanduser().resolve()
        return base / "artifacts"

    # 根据平台选择用户本地目录
    system = platform.system()

    if system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support" / "ba-agent"
    elif system == "Windows":
        appdata = os.getenv("APPDATA", "")
        base = Path(appdata) / "ba-agent" if appdata else Path.home() / ".ba-agent"
    else:  # Linux 及其他
        xdg_data = os.getenv("XDG_DATA_HOME")
        base = Path(xdg_data) / "ba-agent" if xdg_data else Path.home() / ".local" / "share" / "ba-agent"

    return base / "artifacts"


class ArtifactMetadata(BaseModel):
    """Metadata for a stored artifact."""

    artifact_id: str
    filename: str
    created_at: float
    size_bytes: int
    hash: str
    tool_name: str
    summary: Optional[str] = None


class DataStorage:
    """
    Artifact-based file storage for tool outputs.

    Security Rules:
        1. NEVER expose real paths to LLM
        2. ALWAYS use artifact_id in observations
        3. ALL file access restricted to sandbox directory
        4. VALIDATE artifact_id format on retrieval
        5. NO path traversal allowed (sanitize all IDs)

    Storage Structure:
        storage_dir/
        ├── artifacts/
        │   ├── artifact_abc123.json
        │   └── artifact_def456.json
        └── metadata.json
    """

    # Default configuration
    DEFAULT_STORAGE_DIR = _get_default_storage_dir()
    DEFAULT_MAX_AGE_HOURS = 24
    DEFAULT_MAX_SIZE_MB = 1000

    # Artifact ID format (no path separators, non-guessable)
    ARTIFACT_PREFIX = "artifact_"
    ARTIFACT_HASH_LENGTH = 16

    def __init__(
        self,
        storage_dir: Optional[Union[str, Path]] = None,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
    ):
        """
        Initialize data storage.

        Args:
            storage_dir: Directory for artifact storage (default: user local directory)
            max_age_hours: Maximum age of artifacts before cleanup (hours)
            max_size_mb: Maximum total storage size before cleanup (MB)
        """
        self.storage_dir = Path(storage_dir or self.DEFAULT_STORAGE_DIR)
        self.max_age_hours = max_age_hours
        self.max_size_mb = max_size_mb

        # Create storage structure
        self.artifacts_dir = self.storage_dir / "artifacts"
        self.metadata_file = self.storage_dir / "metadata.json"

        # Initialize directories
        self._init_directories()

        # Load existing metadata
        self._metadata: Dict[str, ArtifactMetadata] = {}
        self._load_metadata()

    def _init_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _load_metadata(self) -> None:
        """Load artifact metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for artifact_id, meta in data.items():
                        self._metadata[artifact_id] = ArtifactMetadata(**meta)
            except Exception as e:
                # If metadata is corrupted, start fresh
                self._metadata = {}

    def _save_metadata(self) -> None:
        """Save artifact metadata to disk."""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            data = {
                artifact_id: meta.model_dump()
                for artifact_id, meta in self._metadata.items()
            }
            json.dump(data, f, indent=2)

    def _generate_artifact_id(self, data: Any, tool_name: str) -> str:
        """
        Generate a unique artifact ID.

        Format: artifact_{hash} where hash is first 16 chars of MD5
        Not guessable, no path separators, safe for LLM context.

        Args:
            data: Data to be stored
            tool_name: Tool name for prefix

        Returns:
            Artifact ID string
        """
        data_str = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.md5(data_str.encode()).hexdigest()
        return f"{self.ARTIFACT_PREFIX}{data_hash[:self.ARTIFACT_HASH_LENGTH]}"

    def _validate_artifact_id(self, artifact_id: str) -> bool:
        """
        Validate artifact ID format.

        Prevents path traversal attacks:
        - Must start with artifact_
        - Must contain only safe characters
        - No path separators

        Args:
            artifact_id: ID to validate

        Returns:
            True if valid format
        """
        if not artifact_id.startswith(self.ARTIFACT_PREFIX):
            return False

        # Check for path separators
        if "/" in artifact_id or "\\" in artifact_id:
            return False

        # Check for path traversal attempts
        if ".." in artifact_id:
            return False

        # Check length
        expected_len = len(self.ARTIFACT_PREFIX) + self.ARTIFACT_HASH_LENGTH
        if len(artifact_id) != expected_len:
            return False

        return True

    def store(
        self,
        data: Any,
        tool_name: str = "",
        summary: Optional[str] = None,
    ) -> tuple[str, str, ArtifactMetadata]:
        """
        Store data as artifact and return (artifact_id, observation, metadata).

        Args:
            data: Data to store (will be JSON serialized)
            tool_name: Name of the tool creating this artifact
            summary: Optional human-readable summary

        Returns:
            Tuple of (artifact_id, observation_text, metadata)

        Raises:
            ValueError: If data cannot be serialized
        """
        # Serialize data
        try:
            data_json = json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            raise ValueError(f"Cannot serialize data: {e}")

        # Calculate size and hash
        data_bytes = data_json.encode('utf-8')
        size_bytes = len(data_bytes)
        data_hash = hashlib.md5(data_bytes).hexdigest()

        # Generate artifact ID
        artifact_id = self._generate_artifact_id(data, tool_name)
        filename = f"{artifact_id}.json"

        # Check if already exists
        if artifact_id in self._metadata:
            existing = self._metadata[artifact_id]
            if existing.hash == data_hash:
                # Same data, return existing
                return artifact_id, self._format_observation(existing), existing

        # Write to file (within sandbox)
        file_path = self.artifacts_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(data_json)

        # Create metadata
        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            filename=filename,
            created_at=time.time(),
            size_bytes=size_bytes,
            hash=data_hash,
            tool_name=tool_name,
            summary=summary or self._generate_summary(data),
        )

        # Save metadata
        self._metadata[artifact_id] = metadata
        self._save_metadata()

        # Format observation (safe for LLM)
        observation = self._format_observation(metadata)

        return artifact_id, observation, metadata

    def retrieve(self, artifact_id: str) -> Optional[Any]:
        """
        Retrieve data by artifact ID.

        Args:
            artifact_id: Artifact ID to retrieve

        Returns:
            Stored data, or None if not found

        Raises:
            ValueError: If artifact_id format is invalid (path traversal attempt)
        """
        # Validate artifact ID format (security check)
        if not self._validate_artifact_id(artifact_id):
            raise ValueError(f"Invalid artifact_id format: {artifact_id}")

        # Check metadata
        if artifact_id not in self._metadata:
            return None

        metadata = self._metadata[artifact_id]
        file_path = self.artifacts_dir / metadata.filename

        # Security: Ensure file is within sandbox
        if not str(file_path.resolve()).startswith(str(self.artifacts_dir.resolve())):
            raise ValueError(f"Security violation: file path outside sandbox")

        # Read and return data
        if not file_path.exists():
            # Metadata exists but file doesn't, clean up
            del self._metadata[artifact_id]
            self._save_metadata()
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def delete(self, artifact_id: str) -> bool:
        """
        Delete an artifact.

        Args:
            artifact_id: Artifact ID to delete

        Returns:
            True if deleted, False if not found
        """
        # Validate artifact ID format
        if not self._validate_artifact_id(artifact_id):
            return False

        if artifact_id not in self._metadata:
            return False

        metadata = self._metadata[artifact_id]
        file_path = self.artifacts_dir / metadata.filename

        # Delete file
        if file_path.exists():
            file_path.unlink()

        # Remove metadata
        del self._metadata[artifact_id]
        self._save_metadata()

        return True

    def cleanup(self, max_age_hours: Optional[int] = None) -> int:
        """
        Clean up old artifacts.

        Args:
            max_age_hours: Maximum age in hours (default: from config)

        Returns:
            Number of artifacts deleted
        """
        max_age = max_age_hours or self.max_age_hours
        cutoff_time = time.time() - (max_age * 3600)

        to_delete = [
            artifact_id
            for artifact_id, meta in self._metadata.items()
            if meta.created_at < cutoff_time
        ]

        for artifact_id in to_delete:
            self.delete(artifact_id)

        return len(to_delete)

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        total_size = sum(meta.size_bytes for meta in self._metadata.values())
        artifact_count = len(self._metadata)

        return {
            "artifact_count": artifact_count,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "storage_dir": str(self.storage_dir),
            "max_age_hours": self.max_age_hours,
        }

    def list_artifacts(
        self,
        tool_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[ArtifactMetadata]:
        """
        List artifacts, optionally filtered by tool name.

        Args:
            tool_name: Filter by tool name (None = all)
            limit: Maximum number to return

        Returns:
            List of artifact metadata, sorted by creation time (newest first)
        """
        artifacts = list(self._metadata.values())

        if tool_name:
            artifacts = [a for a in artifacts if a.tool_name == tool_name]

        # Sort by creation time (newest first)
        artifacts.sort(key=lambda m: m.created_at, reverse=True)

        return artifacts[:limit]

    def _format_observation(self, metadata: ArtifactMetadata) -> str:
        """Format observation string for LLM (safe, no real paths)."""
        return f"""Data stored as artifact: {metadata.artifact_id}

Large dataset available for subsequent tool access.

To access this data, reference the artifact_id in your next tool call.
The system will securely retrieve the data for you.

Data summary: {metadata.summary or 'See artifact metadata'}
Size: {metadata.size_bytes:,} bytes"""

    def _generate_summary(self, data: Any) -> str:
        """Generate a summary of the data."""
        if isinstance(data, dict):
            return f"Dict with {len(data)} keys"
        elif isinstance(data, list):
            return f"List with {len(data)} items"
        elif isinstance(data, str):
            return f"String ({len(data)} chars)"
        elif isinstance(data, (int, float, bool)):
            return f"{type(data).__name__}: {data}"
        else:
            return type(data).__name__


# Global singleton instance
_global_storage: Optional[DataStorage] = None


def get_data_storage() -> DataStorage:
    """Get global data storage instance."""
    global _global_storage
    if _global_storage is None:
        _global_storage = DataStorage()
    return _global_storage


__all__ = [
    "ArtifactMetadata",
    "DataStorage",
    "get_data_storage",
]
