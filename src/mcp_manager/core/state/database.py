"""
Database layer for hybrid server state management.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from mcp_manager.utils.logging import get_logger
from .models import ServerStatus, ServerAnalytics, UsageEvent, ConnectionStatus

logger = get_logger(__name__)


class StateDatabase:
    """SQLite database for persistent server state and analytics."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database with WAL mode for concurrent access."""
        if db_path is None:
            from mcp_manager.utils.config import get_config_dir
            config_dir = get_config_dir()
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = config_dir / "server_state.db"
        
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            # Enable WAL mode for concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            
            # Server registry table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_server_registry (
                    name TEXT PRIMARY KEY,
                    server_type TEXT NOT NULL,
                    command TEXT NOT NULL,
                    args TEXT NOT NULL,
                    env TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    scope TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            
            # Connection status history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_connection_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_time_ms INTEGER,
                    error_message TEXT,
                    tool_count INTEGER,
                    checked_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (server_name) REFERENCES mcp_server_registry(name)
                )
            """)
            
            # Usage events
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    user_context TEXT,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (server_name) REFERENCES mcp_server_registry(name)
                )
            """)
            
            # Config snapshots for drift detection
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_config_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_hash TEXT NOT NULL,
                    config_content TEXT NOT NULL,
                    live_state_hash TEXT,
                    drift_detected BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP NOT NULL
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_connection_history_server_time ON mcp_connection_history(server_name, checked_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_events_server_time ON mcp_usage_events(server_name, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_config_snapshots_time ON mcp_config_snapshots(created_at)")
            
            conn.commit()
            logger.debug("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper locking."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
    
    async def record_status_check(self, server_name: str, status: ServerStatus):
        """Record a server status check."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO mcp_connection_history 
                    (server_name, status, response_time_ms, error_message, tool_count, checked_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    server_name,
                    status.status.value,
                    status.response_time_ms,
                    status.error_message,
                    status.tool_count,
                    status.checked_at.isoformat()
                ))
                conn.commit()
                logger.debug(f"Recorded status check for {server_name}: {status.status.value}")
        except Exception as e:
            logger.error(f"Failed to record status check for {server_name}: {e}")
    
    async def get_latest_status(self, server_name: str) -> Optional[ServerStatus]:
        """Get the most recent status for a server."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT status, response_time_ms, error_message, tool_count, checked_at
                    FROM mcp_connection_history 
                    WHERE server_name = ?
                    ORDER BY checked_at DESC
                    LIMIT 1
                """, (server_name,))
                
                row = cursor.fetchone()
                if row:
                    return ServerStatus(
                        server_name=server_name,
                        status=ConnectionStatus(row['status']),
                        response_time_ms=row['response_time_ms'],
                        error_message=row['error_message'],
                        tool_count=row['tool_count'],
                        checked_at=datetime.fromisoformat(row['checked_at'])
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get latest status for {server_name}: {e}")
            return None
    
    async def get_servers_with_recent_status(self, max_age_seconds: int = 300) -> Dict[str, ServerStatus]:
        """Get servers with status checks within the specified age."""
        try:
            cutoff_time = datetime.now() - timedelta(seconds=max_age_seconds)
            
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT DISTINCT server_name FROM (
                        SELECT server_name, checked_at,
                               ROW_NUMBER() OVER (PARTITION BY server_name ORDER BY checked_at DESC) as rn
                        FROM mcp_connection_history 
                        WHERE checked_at > ?
                    ) WHERE rn = 1
                """, (cutoff_time.isoformat(),))
                
                servers = {}
                for row in cursor.fetchall():
                    server_name = row['server_name']
                    status = await self.get_latest_status(server_name)
                    if status:
                        servers[server_name] = status
                
                return servers
        except Exception as e:
            logger.error(f"Failed to get servers with recent status: {e}")
            return {}
    
    async def record_usage_event(self, event: UsageEvent):
        """Record a usage event."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO mcp_usage_events 
                    (server_name, event_type, event_data, user_context, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    event.server_name,
                    event.event_type,
                    json.dumps(event.event_data),
                    event.user_context,
                    event.created_at.isoformat()
                ))
                conn.commit()
                logger.debug(f"Recorded usage event for {event.server_name}: {event.event_type}")
        except Exception as e:
            logger.error(f"Failed to record usage event: {e}")
    
    async def get_server_analytics(self, server_name: str) -> Optional[ServerAnalytics]:
        """Get comprehensive analytics for a server."""
        try:
            with self.get_connection() as conn:
                # Get connection statistics
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_checks,
                        AVG(CASE WHEN status = 'connected' THEN 1.0 ELSE 0.0 END) as success_rate,
                        AVG(response_time_ms) as avg_response_time,
                        MAX(CASE WHEN status = 'connected' THEN checked_at END) as last_success,
                        MAX(CASE WHEN status != 'connected' THEN checked_at END) as last_failure
                    FROM mcp_connection_history 
                    WHERE server_name = ?
                """, (server_name,))
                
                conn_stats = cursor.fetchone()
                if not conn_stats or conn_stats['total_checks'] == 0:
                    return None
                
                # Get usage events
                cursor = conn.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM mcp_usage_events 
                    WHERE server_name = ?
                    GROUP BY event_type
                """, (server_name,))
                
                usage_counts = dict(cursor.fetchall())
                
                # Get recent usage events
                cursor = conn.execute("""
                    SELECT event_type, event_data, created_at
                    FROM mcp_usage_events 
                    WHERE server_name = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (server_name,))
                
                usage_events = []
                for row in cursor.fetchall():
                    usage_events.append({
                        'event_type': row['event_type'],
                        'event_data': json.loads(row['event_data']) if row['event_data'] else {},
                        'created_at': row['created_at']
                    })
                
                return ServerAnalytics(
                    server_name=server_name,
                    total_checks=conn_stats['total_checks'],
                    success_rate=conn_stats['success_rate'] or 0.0,
                    avg_response_time_ms=conn_stats['avg_response_time'],
                    last_success=datetime.fromisoformat(conn_stats['last_success']) if conn_stats['last_success'] else None,
                    last_failure=datetime.fromisoformat(conn_stats['last_failure']) if conn_stats['last_failure'] else None,
                    install_count=usage_counts.get('install', 0),
                    remove_count=usage_counts.get('remove', 0),
                    usage_events=usage_events
                )
                
        except Exception as e:
            logger.error(f"Failed to get analytics for {server_name}: {e}")
            return None
    
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old historical data."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM mcp_connection_history 
                    WHERE checked_at < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_history = cursor.rowcount
                
                cursor = conn.execute("""
                    DELETE FROM mcp_usage_events 
                    WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_events = cursor.rowcount
                
                cursor = conn.execute("""
                    DELETE FROM mcp_config_snapshots 
                    WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_snapshots = cursor.rowcount
                
                conn.commit()
                
                logger.info(f"Cleaned up old data: {deleted_history} history records, {deleted_events} events, {deleted_snapshots} snapshots")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")