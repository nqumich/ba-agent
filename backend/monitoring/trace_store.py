"""
Trace Store - Persistent storage for traces and metrics

Design principles:
- Uses FileStore for persistence (ARTIFACT category)
- JSON format for traces
- JSONL format for metrics (aggregatable)
- SQLite indexing for fast queries
- TTL-based cleanup (7 days default)
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterator

from backend.monitoring.execution_tracer import Trace
from backend.monitoring.metrics_collector import AgentMetrics


class TraceIndex:
    """
    SQLite index for fast trace lookups

    Enables efficient querying by:
    - conversation_id
    - session_id
    - time range
    - status
    """

    def __init__(self, db_path: Path):
        """
        Initialize trace index

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL,
                duration_ms REAL,
                status TEXT,
                file_path TEXT,
                created_at REAL NOT NULL,

                -- Indexed fields
                model TEXT,
                total_tokens INTEGER,
                tool_calls_count INTEGER
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation
            ON traces(conversation_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session
            ON traces(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_start_time
            ON traces(start_time)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at
            ON traces(created_at)
        """)
        conn.commit()

    def insert_trace(
        self,
        trace_id: str,
        conversation_id: str,
        session_id: str,
        start_time: float,
        end_time: Optional[float],
        duration_ms: Optional[float],
        status: str,
        file_path: str,
        model: Optional[str] = None,
        total_tokens: int = 0,
        tool_calls_count: int = 0
    ) -> None:
        """Insert trace record into index"""
        conn = self._get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO traces
            (trace_id, conversation_id, session_id, start_time, end_time,
             duration_ms, status, file_path, created_at, model, total_tokens, tool_calls_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace_id, conversation_id, session_id, start_time, end_time,
            duration_ms, status, file_path, datetime.now().timestamp(),
            model, total_tokens, tool_calls_count
        ))
        conn.commit()

    def query_by_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Query traces by conversation ID"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM traces
            WHERE conversation_id = ?
            ORDER BY start_time DESC
        """, (conversation_id,))
        return [dict(row) for row in cursor.fetchall()]

    def query_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Query traces by session ID"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM traces
            WHERE session_id = ?
            ORDER BY start_time DESC
        """, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    def query_by_time_range(
        self,
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """Query traces by time range"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM traces
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time DESC
        """, (start_time, end_time))
        return [dict(row) for row in cursor.fetchall()]

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent traces"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM traces
            ORDER BY start_time DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def cleanup_old(self, days: int = 7) -> int:
        """Remove traces older than specified days"""
        cutoff = (datetime.now() - timedelta(days=days)).timestamp()
        conn = self._get_connection()
        cursor = conn.execute("""
            DELETE FROM traces
            WHERE created_at < ?
        """, (cutoff,))
        count = cursor.rowcount
        conn.commit()
        return count


class MetricsIndex:
    """
    SQLite index for metrics lookups

    Similar to TraceIndex but for aggregated metrics.
    """

    def __init__(self, db_path: Path):
        """Initialize metrics index"""
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                total_tokens INTEGER,
                total_duration_ms REAL,
                tool_calls_count INTEGER,
                estimated_cost_usd REAL,
                model TEXT,
                file_path TEXT,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_conversation
            ON metrics(conversation_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
            ON metrics(timestamp)
        """)
        conn.commit()

    def insert_metrics(
        self,
        conversation_id: str,
        session_id: str,
        timestamp: float,
        total_tokens: int,
        total_duration_ms: float,
        tool_calls_count: int,
        estimated_cost_usd: float,
        model: Optional[str],
        file_path: str
    ) -> None:
        """Insert metrics record"""
        conn = self._get_connection()
        conn.execute("""
            INSERT INTO metrics
            (conversation_id, session_id, timestamp, total_tokens, total_duration_ms,
             tool_calls_count, estimated_cost_usd, model, file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation_id, session_id, timestamp, total_tokens, total_duration_ms,
            tool_calls_count, estimated_cost_usd, model, file_path, datetime.now().timestamp()
        ))
        conn.commit()

    def get_metrics_by_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all metrics for a conversation"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM metrics
            WHERE conversation_id = ?
            ORDER BY timestamp DESC
        """, (conversation_id,))
        return [dict(row) for row in cursor.fetchall()]


class TraceStore:
    """
    Trace Store - persistent storage for execution traces

    Features:
    - File-based storage using FileStore
    - SQLite indexing for fast queries
    - Automatic cleanup of old traces
    - JSON serialization for traces
    """

    DEFAULT_TTL_DAYS = 7

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        ttl_days: int = DEFAULT_TTL_DAYS
    ):
        """
        Initialize TraceStore

        Args:
            storage_dir: Base directory for storage
            ttl_days: Time-to-live for traces in days
        """
        from backend.api.state import get_app_state

        # Try to get FileStore from app state
        app_state = get_app_state()
        self.file_store = app_state.get("file_store") if app_state else None

        # Set storage directory
        if storage_dir is None and self.file_store:
            storage_dir = self.file_store.storage_dir / "traces"
        elif storage_dir is None:
            storage_dir = Path("/var/lib/ba-agent/traces")

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize index
        index_path = self.storage_dir / "trace_index.db"
        self.index = TraceIndex(index_path)

        self.ttl_days = ttl_days

    def save_trace(
        self,
        trace: Trace,
        metrics: Optional[AgentMetrics] = None
    ) -> str:
        """
        Save trace to storage

        Args:
            trace: Trace object to save
            metrics: Optional associated metrics

        Returns:
            File path where trace was saved
        """
        # Create trace filename
        timestamp = datetime.fromtimestamp(trace.start_time).strftime("%Y%m%d_%H%M%S")
        filename = f"trace_{trace.conversation_id}_{timestamp}.json"
        file_path = self.storage_dir / filename

        # Serialize trace to JSON
        trace_dict = trace.to_dict()

        # Add metrics if provided
        if metrics:
            trace_dict["metrics"] = metrics.to_dict()

        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(trace_dict, f, indent=2, ensure_ascii=False)

        # Update index
        model = metrics.primary_model if metrics else None
        total_tokens = metrics.total_tokens if metrics else 0
        tool_calls = metrics.tool_calls_count if metrics else 0

        self.index.insert_trace(
            trace_id=trace.trace_id,
            conversation_id=trace.conversation_id,
            session_id=trace.session_id,
            start_time=trace.start_time,
            end_time=trace.end_time,
            duration_ms=trace.total_duration_ms,
            status=trace.root_span.status.value if trace.root_span else "unknown",
            file_path=str(file_path),
            model=model,
            total_tokens=total_tokens,
            tool_calls_count=tool_calls
        )

        # Also store in FileStore if available
        if self.file_store:
            try:
                from backend.models.filestore import FileCategory
                import json
                content = json.dumps(trace_dict).encode('utf-8')
                self.file_store.store_file(
                    content=content,
                    category=FileCategory.ARTIFACT,
                    session_id=trace.session_id,
                    file_type="trace",
                    conversation_id=trace.conversation_id
                )
            except Exception:
                pass  # Fall back to file storage only

        return str(file_path)

    def load_trace(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Load trace for a conversation

        Args:
            conversation_id: Conversation identifier

        Returns:
            Trace dictionary or None if not found
        """
        # Query index
        records = self.index.query_by_conversation(conversation_id)
        if not records:
            return None

        # Load most recent trace
        record = records[0]
        file_path = Path(record["file_path"])

        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_conversations(
        self,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List conversations with traces

        Args:
            session_id: Filter by session (optional)
            limit: Maximum results

        Returns:
            List of conversation summaries
        """
        if session_id:
            records = self.index.query_by_session(session_id)
        else:
            records = self.index.get_recent(limit)

        # Group by conversation_id
        conversations: Dict[str, Dict[str, Any]] = {}
        for record in records:
            conv_id = record["conversation_id"]
            if conv_id not in conversations:
                conversations[conv_id] = {
                    "conversation_id": conv_id,
                    "session_id": record["session_id"],
                    "start_time": record["start_time"],
                    "total_duration_ms": 0,
                    "trace_count": 0,
                    "total_tokens": 0,
                    "tool_calls": 0,
                }

            conv = conversations[conv_id]
            conv["total_duration_ms"] = max(conv["total_duration_ms"], record["duration_ms"] or 0)
            conv["trace_count"] += 1
            conv["total_tokens"] += record.get("total_tokens", 0)
            conv["tool_calls"] += record.get("tool_calls_count", 0)

        return list(conversations.values())[:limit]

    def cleanup_old_traces(self, days: Optional[int] = None) -> int:
        """
        Remove traces older than specified days

        Args:
            days: Days to keep (uses TTL if not specified)

        Returns:
            Number of traces removed
        """
        ttl = days or self.ttl_days
        return self.index.cleanup_old(ttl)


class MetricsStore:
    """
    Metrics Store - persistent storage for aggregated metrics

    Similar to TraceStore but for metrics data.
    Uses JSONL format for efficient appending.
    """

    DEFAULT_TTL_DAYS = 30

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        ttl_days: int = DEFAULT_TTL_DAYS
    ):
        """
        Initialize MetricsStore

        Args:
            storage_dir: Base directory for storage
            ttl_days: Time-to-live for metrics in days
        """
        from backend.api.state import get_app_state

        # Try to get FileStore from app state
        app_state = get_app_state()
        self.file_store = app_state.get("file_store") if app_state else None

        # Set storage directory
        if storage_dir is None and self.file_store:
            storage_dir = self.file_store.storage_dir / "metrics"
        elif storage_dir is None:
            storage_dir = Path("/var/lib/ba-agent/metrics")

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize index
        index_path = self.storage_dir / "metrics_index.db"
        self.index = MetricsIndex(index_path)

        self.ttl_days = ttl_days

    def save_metrics(self, metrics: AgentMetrics) -> str:
        """
        Save metrics to storage

        Args:
            metrics: AgentMetrics object to save

        Returns:
            File path where metrics were saved
        """
        # Create metrics filename (JSONL format by session/date)
        date_str = datetime.fromtimestamp(metrics.timestamp).strftime("%Y%m%d")
        filename = f"metrics_{metrics.session_id}_{date_str}.jsonl"
        file_path = self.storage_dir / filename

        # Serialize metrics to JSON line
        metrics_dict = metrics.to_dict()
        json_line = json.dumps(metrics_dict, ensure_ascii=False)

        # Append to file
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json_line + '\n')

        # Update index
        self.index.insert_metrics(
            conversation_id=metrics.conversation_id,
            session_id=metrics.session_id,
            timestamp=metrics.timestamp,
            total_tokens=metrics.total_tokens,
            total_duration_ms=metrics.total_duration_ms,
            tool_calls_count=metrics.tool_calls_count,
            estimated_cost_usd=metrics.estimated_cost_usd,
            model=metrics.primary_model,
            file_path=str(file_path)
        )

        return str(file_path)

    def get_metrics(
        self,
        conversation_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get metrics for a conversation

        Args:
            conversation_id: Conversation identifier
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of metrics dictionaries
        """
        records = self.index.get_metrics_by_conversation(conversation_id)

        # Apply time filters
        if start_time is not None:
            records = [r for r in records if r["timestamp"] >= start_time]
        if end_time is not None:
            records = [r for r in records if r["timestamp"] <= end_time]

        # Load full metrics from files
        results = []
        for record in records:
            file_path = Path(record["file_path"])
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            if data.get("conversation_id") == conversation_id:
                                results.append(data)
                        except json.JSONDecodeError:
                            continue

        return results

    def get_aggregated_metrics(
        self,
        session_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics across conversations

        Args:
            session_id: Filter by session
            start_time: Start time filter
            end_time: End time filter

        Returns:
            Aggregated metrics summary
        """
        # Query from index
        if start_time and end_time:
            records = []
            # Would need time range query in index
        else:
            records = self.index.get_metrics_by_conversation("")  # Get all

        # Apply filters
        if session_id:
            records = [r for r in records if r["session_id"] == session_id]

        # Aggregate
        total = {
            "total_conversations": len(set(r["conversation_id"] for r in records)),
            "total_tokens": sum(r.get("total_tokens", 0) for r in records),
            "total_duration_ms": sum(r.get("total_duration_ms", 0) for r in records),
            "total_tool_calls": sum(r.get("tool_calls_count", 0) for r in records),
            "total_cost_usd": sum(r.get("estimated_cost_usd", 0) for r in records),
            "avg_tokens_per_conv": 0,
            "avg_duration_ms_per_conv": 0,
        }

        if total["total_conversations"] > 0:
            total["avg_tokens_per_conv"] = total["total_tokens"] / total["total_conversations"]
            total["avg_duration_ms_per_conv"] = total["total_duration_ms"] / total["total_conversations"]

        return total


# Global singleton instances
_trace_store: Optional[TraceStore] = None
_metrics_store: Optional[MetricsStore] = None


def get_trace_store() -> TraceStore:
    """Get global TraceStore instance"""
    global _trace_store
    if _trace_store is None:
        _trace_store = TraceStore()
    return _trace_store


def get_metrics_store() -> MetricsStore:
    """Get global MetricsStore instance"""
    global _metrics_store
    if _metrics_store is None:
        _metrics_store = MetricsStore()
    return _metrics_store


__all__ = [
    "TraceIndex",
    "MetricsIndex",
    "TraceStore",
    "MetricsStore",
    "get_trace_store",
    "get_metrics_store",
]
