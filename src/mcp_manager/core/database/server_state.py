"""
Server State Database Management for MCP Manager

Implements the hybrid server state management architecture with:
- Fast config file access
- Persistent database cache with analytics
- Runtime memory cache
- Live status checking
"""

import sqlite3
import json
import asyncio
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ServerStatus(Enum):
    CONNECTED = "connected"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

class ServerType(Enum):
    NPM = "npm"
    DOCKER = "docker"
    DOCKER_DESKTOP = "docker-desktop"
    CUSTOM = "custom"

@dataclass
class ServerInfo:
    name: str
    server_type: ServerType
    command: str
    args: List[str]
    env: Dict[str, str]
    enabled: bool
    scope: str
    description: Optional[str] = None
    install_id: Optional[str] = None
    package: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class ServerStatusInfo:
    name: str
    status: ServerStatus
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    tool_count: Optional[int] = None
    checked_at: Optional[datetime] = None

@dataclass
class ConfigDrift:
    server_name: str
    config_hash: str
    live_hash: str
    differences: List[str]
    detected_at: datetime

class MCPServerStateManager:
    """
    Hybrid server state management with 3-tier architecture:
    1. Fast: Config file access (<50ms)
    2. Cached: Database with runtime cache (50-200ms)
    3. Live: Real-time status check (1-2s)
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or self._get_default_db_path()
        self.runtime_cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes default TTL
        self._initialize_database()
    
    def _get_default_db_path(self) -> Path:
        """Get the default database path."""
        # Check environment variable first for global database location
        env_path = os.getenv("MCP_MANAGER_DB_PATH")
        if env_path:
            db_path = Path(env_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return db_path
        
        # Try global locations first (for system-wide MCP server management)
        global_locations = [
            Path("/usr/local/share/mcp-manager"),
            Path("/opt/mcp-manager"), 
            Path("/var/lib/mcp-manager")
        ]
        
        for location in global_locations:
            try:
                location.mkdir(parents=True, exist_ok=True)
                # Test if we can write to this location
                test_file = location / ".write_test"
                test_file.touch()
                test_file.unlink()
                return location / "server_state.db"
            except (PermissionError, OSError):
                continue
        
        # Fallback to user config directory if no global location available
        config_dir = Path.home() / ".config" / "mcp-manager"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "server_state.db"
    
    def _initialize_database(self):
        """Initialize database with proper schema and WAL mode."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Enable WAL mode for concurrent access
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=memory")
                
                # Create tables from hybrid architecture schema
                self._create_tables(conn)
                
                logger.info(f"Initialized server state database at {self.db_path} with WAL mode")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _create_tables(self, conn: sqlite3.Connection):
        """Create database tables according to hybrid architecture spec."""
        
        # Server registry with current state
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_server_registry (
                name TEXT PRIMARY KEY,
                server_type TEXT NOT NULL,
                command TEXT NOT NULL,
                args TEXT NOT NULL, -- JSON array
                env TEXT NOT NULL,  -- JSON object
                enabled BOOLEAN NOT NULL,
                scope TEXT NOT NULL,
                config_hash TEXT NOT NULL, -- For drift detection
                description TEXT,
                install_id TEXT,
                package TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        
        # Connection status history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_connection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name TEXT NOT NULL,
                status TEXT NOT NULL, -- 'connected', 'failed', 'timeout'
                response_time_ms REAL,
                error_message TEXT,
                tool_count INTEGER,
                checked_at TIMESTAMP NOT NULL,
                FOREIGN KEY (server_name) REFERENCES mcp_server_registry(name)
            )
        """)
        
        # Usage analytics
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name TEXT NOT NULL,
                event_type TEXT NOT NULL, -- 'install', 'remove', 'enable', 'disable', 'health_check'
                event_data TEXT, -- JSON
                user_context TEXT, -- API key hash or user identifier
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (server_name) REFERENCES mcp_server_registry(name)
            )
        """)
        
        # Config drift detection
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_config_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_hash TEXT NOT NULL,
                config_content TEXT NOT NULL, -- JSON snapshot
                live_state_hash TEXT,
                drift_detected BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL
            )
        """)
        
        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_connection_history_server_time ON mcp_connection_history(server_name, checked_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_events_server_time ON mcp_usage_events(server_name, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_server_registry_type ON mcp_server_registry(server_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_server_registry_enabled ON mcp_server_registry(enabled)")
        
        conn.commit()
    
    # Fast Methods (Config Files Only) - <50ms target
    def list_servers_fast(self) -> List[ServerInfo]:
        """Ultra-fast config file access - <50ms target."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT name, server_type, command, args, env, enabled, scope, 
                           description, install_id, package, created_at, updated_at
                    FROM mcp_server_registry
                    ORDER BY name
                """)
                
                servers = []
                for row in cursor:
                    servers.append(ServerInfo(
                        name=row['name'],
                        server_type=ServerType(row['server_type']),
                        command=row['command'],
                        args=json.loads(row['args']),
                        env=json.loads(row['env']),
                        enabled=bool(row['enabled']),
                        scope=row['scope'],
                        description=row['description'],
                        install_id=row['install_id'],
                        package=row['package'],
                        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                    ))
                
                return servers
                
        except Exception as e:
            logger.error(f"Fast server list failed: {e}")
            return []
    
    def get_server_fast(self, name: str) -> Optional[ServerInfo]:
        """Fast config lookup for single server."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT name, server_type, command, args, env, enabled, scope,
                           description, install_id, package, created_at, updated_at
                    FROM mcp_server_registry
                    WHERE name = ?
                """, (name,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return ServerInfo(
                    name=row['name'],
                    server_type=ServerType(row['server_type']),
                    command=row['command'],
                    args=json.loads(row['args']),
                    env=json.loads(row['env']),
                    enabled=bool(row['enabled']),
                    scope=row['scope'],
                    description=row['description'],
                    install_id=row['install_id'],
                    package=row['package'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
                
        except Exception as e:
            logger.error(f"Fast server get failed for {name}: {e}")
            return None
    
    # Cached Methods (Database + Runtime Cache) - 50-200ms target
    async def list_servers_cached(self, max_age_seconds: int = 300) -> List[Dict[str, Any]]:
        """Fast cached access with optional live status - 50-200ms target."""
        cache_key = f"servers_with_status_{max_age_seconds}"
        
        # Check runtime cache first
        if cache_key in self.runtime_cache:
            cache_entry = self.runtime_cache[cache_key]
            if time.time() - cache_entry['timestamp'] < max_age_seconds:
                return cache_entry['data']
        
        # Get servers from database
        servers = self.list_servers_fast()
        
        # Add cached status information
        server_data = []
        for server in servers:
            status_info = await self._get_cached_status(server.name, max_age_seconds)
            server_dict = asdict(server)
            server_dict['status_info'] = asdict(status_info) if status_info else None
            server_data.append(server_dict)
        
        # Cache the result
        self.runtime_cache[cache_key] = {
            'data': server_data,
            'timestamp': time.time()
        }
        
        return server_data
    
    async def _get_cached_status(self, server_name: str, max_age_seconds: int) -> Optional[ServerStatusInfo]:
        """Get cached server status if available and recent."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
                
                cursor = conn.execute("""
                    SELECT server_name, status, response_time_ms, error_message, 
                           tool_count, checked_at
                    FROM mcp_connection_history
                    WHERE server_name = ? AND checked_at > ?
                    ORDER BY checked_at DESC
                    LIMIT 1
                """, (server_name, cutoff_time.isoformat()))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return ServerStatusInfo(
                    name=row['server_name'],
                    status=ServerStatus(row['status']),
                    response_time_ms=row['response_time_ms'],
                    error_message=row['error_message'],
                    tool_count=row['tool_count'],
                    checked_at=datetime.fromisoformat(row['checked_at'])
                )
                
        except Exception as e:
            logger.error(f"Failed to get cached status for {server_name}: {e}")
            return None
    
    # Server Management Methods
    def add_server(self, server_info: ServerInfo) -> bool:
        """Add or update a server in the registry."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                now = datetime.now(timezone.utc).isoformat()
                config_hash = self._calculate_config_hash(server_info)
                
                conn.execute("""
                    INSERT OR REPLACE INTO mcp_server_registry
                    (name, server_type, command, args, env, enabled, scope, config_hash,
                     description, install_id, package, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    server_info.name,
                    server_info.server_type.value,
                    server_info.command,
                    json.dumps(server_info.args),
                    json.dumps(server_info.env),
                    server_info.enabled,
                    server_info.scope,
                    config_hash,
                    server_info.description,
                    server_info.install_id,
                    server_info.package,
                    server_info.created_at.isoformat() if server_info.created_at else now,
                    now
                ))
                
                # Log the event
                self._log_usage_event(conn, server_info.name, "add", {"install_id": server_info.install_id})
                
                # Clear runtime cache
                self.runtime_cache.clear()
                
                logger.info(f"Added/updated server {server_info.name} in database")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add server {server_info.name}: {e}")
            return False
    
    def remove_server(self, name: str) -> bool:
        """Remove a server from the registry."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Log the event before removal
                self._log_usage_event(conn, name, "remove", {})
                
                # Remove from registry
                cursor = conn.execute("DELETE FROM mcp_server_registry WHERE name = ?", (name,))
                
                if cursor.rowcount > 0:
                    # Clear runtime cache
                    self.runtime_cache.clear()
                    logger.info(f"Removed server {name} from database")
                    return True
                else:
                    logger.warning(f"Server {name} not found for removal")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to remove server {name}: {e}")
            return False
    
    def update_server_status(self, name: str, enabled: bool) -> bool:
        """Update server enabled status."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                now = datetime.now(timezone.utc).isoformat()
                cursor = conn.execute("""
                    UPDATE mcp_server_registry 
                    SET enabled = ?, updated_at = ?
                    WHERE name = ?
                """, (enabled, now, name))
                
                if cursor.rowcount > 0:
                    event_type = "enable" if enabled else "disable"
                    self._log_usage_event(conn, name, event_type, {"enabled": enabled})
                    
                    # Clear runtime cache
                    self.runtime_cache.clear()
                    logger.info(f"Updated server {name} enabled status to {enabled}")
                    return True
                else:
                    logger.warning(f"Server {name} not found for status update")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to update server {name} status: {e}")
            return False
    
    def _calculate_config_hash(self, server_info: ServerInfo) -> str:
        """Calculate hash for config drift detection."""
        import hashlib
        config_data = {
            'command': server_info.command,
            'args': server_info.args,
            'env': server_info.env,
            'enabled': server_info.enabled
        }
        content = json.dumps(config_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _log_usage_event(self, conn: sqlite3.Connection, server_name: str, 
                        event_type: str, event_data: Dict[str, Any]):
        """Log a usage event."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO mcp_usage_events
                (server_name, event_type, event_data, user_context, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                server_name,
                event_type,
                json.dumps(event_data),
                "system",  # Can be enhanced with actual user context
                now
            ))
        except Exception as e:
            logger.error(f"Failed to log usage event: {e}")
    
    def clear_discovery_cache(self):
        """Clear previous discovery results."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM discovery_cache WHERE 1=1")
                conn.commit()
        except Exception:
            pass
    
    def store_discovery_result(self, number: int, result):
        """Store a discovery result with its number."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_cache (
                        number INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        package TEXT,
                        version TEXT,
                        description TEXT,
                        server_type TEXT NOT NULL,
                        install_command TEXT NOT NULL,
                        install_args TEXT
                    )
                """)
                
                conn.execute("""
                    INSERT OR REPLACE INTO discovery_cache 
                    (number, name, package, version, description, server_type, install_command, install_args)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    number,
                    result.name,
                    result.package,
                    result.version,
                    result.description,
                    result.server_type.value,
                    result.install_command,
                    json.dumps(result.install_args or [])
                ))
                conn.commit()
        except Exception:
            pass
    
    def get_discovery_result(self, number: int):
        """Get a discovery result by number."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("""
                    SELECT name, package, version, description, server_type, install_command, install_args
                    FROM discovery_cache 
                    WHERE number = ?
                """, (number,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'name': row[0],
                        'package': row[1],
                        'version': row[2],
                        'description': row[3],
                        'server_type': row[4],
                        'install_command': row[5],
                        'install_args': json.loads(row[6] or '[]')
                    }
                return None
        except Exception:
            return None

# Import fix for timedelta
from datetime import timedelta