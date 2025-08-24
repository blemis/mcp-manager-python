# Hybrid Server State Management Architecture

**Created**: 2025-07-25 17:35:00 UTC  
**Author**: Claude Code AI Assistant  
**Version**: 1.0  

## Overview

This document outlines the hybrid approach for managing MCP server state that combines fast config file access, persistent database storage, and runtime caching for optimal performance and rich analytics.

## Current Architecture Issues

### 1. **Performance Bottleneck**
- `list_servers()` calls `claude mcp list` which is slow (1-2 seconds)
- No fast access method for basic server information
- Suite operations become sluggish with many server checks

### 2. **Limited State Tracking** 
- No historical data about server usage
- No connection health history
- No analytics or usage patterns
- No detection of config drift

### 3. **Inconsistent Methods**
- `list_servers_fast()` was missing (now fixed to read config files)
- `list_servers()` does full live status check
- No middle ground for cached live data

## Proposed Hybrid Architecture

### Components

```python
class MCPServerStateManager:
    def __init__(self):
        self.config_reader = ConfigReader()      # Fast config file access
        self.db_cache = DatabaseCache()          # Persistent cache & analytics  
        self.runtime_cache = RuntimeCache()      # In-memory session cache
        self.live_checker = LiveStatusChecker()  # claude mcp list interface
```

### Storage Layers

#### 1. **Config Files (Source of Truth)**
- **Purpose**: Authoritative source for Claude Code server configuration
- **Files**: `~/.claude.json`, `~/.config/claude-code/mcp-servers.json`, `./.mcp.json`
- **Access**: Direct file system reads
- **Speed**: <50ms
- **Data**: Server definitions, commands, enabled/disabled state

#### 2. **Database Cache (Persistent State)**
- **Purpose**: Historical data, analytics, connection health tracking
- **Storage**: SQLite database with WAL mode
- **Speed**: 50-200ms
- **Data**: 
  - Server connection history
  - Usage analytics and patterns
  - Health check results over time
  - Config change history
  - User behavior analytics

#### 3. **Runtime Cache (Session Memory)**
- **Purpose**: Ultra-fast access for current session
- **Storage**: In-memory Python dictionaries
- **Speed**: <10ms
- **Data**: 
  - Recently accessed server info
  - Last known live status
  - Session-specific state

#### 4. **Live Status (Real-time)**
- **Purpose**: Current connection health from Claude Code
- **Source**: `claude mcp list` command
- **Speed**: 1-2 seconds
- **Data**: Current connection status, tool availability

### API Design

```python
class MCPServerStateManager:
    
    # Fast Methods (Config Files Only)
    def list_servers_fast(self) -> List[Server]:
        """Ultra-fast config file access - <50ms"""
        return self.config_reader.get_servers()
    
    def get_server_fast(self, name: str) -> Optional[Server]:
        """Fast config lookup for single server"""
        return self.config_reader.get_server(name)
    
    # Cached Methods (Database + Runtime Cache)
    async def list_servers_cached(self, max_age_seconds: int = 300) -> List[ServerState]:
        """Fast cached access with optional live status - 50-200ms"""
        return await self.db_cache.get_servers_with_status(max_age_seconds)
    
    async def get_server_status_cached(self, name: str) -> Optional[ServerStatus]:
        """Get cached connection status"""
        return await self.db_cache.get_server_status(name)
    
    # Live Methods (Real-time Status)
    async def list_servers_live(self) -> List[ServerState]:
        """Full live status check - 1-2 seconds"""
        live_status = await self.live_checker.get_all_status()
        await self.db_cache.update_status_history(live_status)
        return live_status
    
    async def get_server_live_status(self, name: str) -> Optional[ServerStatus]:
        """Live status check for single server"""
        status = await self.live_checker.get_server_status(name)
        await self.db_cache.record_status_check(name, status)
        return status
    
    # Analytics Methods (Database)
    async def get_server_analytics(self, name: str) -> ServerAnalytics:
        """Historical usage and health analytics"""
        return await self.db_cache.get_analytics(name)
    
    async def get_usage_patterns(self) -> Dict[str, Any]:
        """System-wide usage patterns"""
        return await self.db_cache.get_usage_patterns()
    
    # Sync Methods (Config Drift Detection)
    async def detect_config_drift(self) -> List[ConfigDrift]:
        """Detect differences between config and live state"""
        config_servers = self.list_servers_fast()
        live_servers = await self.list_servers_live()
        return self._compare_states(config_servers, live_servers)
```

### Database Schema

```sql
-- Server registry with current state
CREATE TABLE mcp_server_registry (
    name TEXT PRIMARY KEY,
    server_type TEXT NOT NULL,
    command TEXT NOT NULL,
    args TEXT NOT NULL, -- JSON array
    env TEXT NOT NULL,  -- JSON object
    enabled BOOLEAN NOT NULL,
    scope TEXT NOT NULL,
    config_hash TEXT NOT NULL, -- For drift detection
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Connection status history
CREATE TABLE mcp_connection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_name TEXT NOT NULL,
    status TEXT NOT NULL, -- 'connected', 'failed', 'timeout'
    response_time_ms INTEGER,
    error_message TEXT,
    tool_count INTEGER,
    checked_at TIMESTAMP NOT NULL,
    FOREIGN KEY (server_name) REFERENCES mcp_server_registry(name)
);

-- Usage analytics
CREATE TABLE mcp_usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_name TEXT NOT NULL,
    event_type TEXT NOT NULL, -- 'install', 'remove', 'enable', 'disable', 'health_check'
    event_data TEXT, -- JSON
    user_context TEXT, -- API key hash or user identifier
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (server_name) REFERENCES mcp_server_registry(name)
);

-- Config drift detection
CREATE TABLE mcp_config_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_hash TEXT NOT NULL,
    config_content TEXT NOT NULL, -- JSON snapshot
    live_state_hash TEXT,
    drift_detected BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL
);
```

## Implementation Benefits

### 1. **Performance Optimization**
- `list_servers_fast()`: <50ms for UI operations
- `list_servers_cached()`: 50-200ms with recent status
- `list_servers_live()`: 1-2s only when fresh data needed

### 2. **Rich Analytics**
- Track server popularity and usage patterns
- Monitor connection health over time
- Detect configuration drift
- User behavior insights

### 3. **Multi-User Support**
- Support different API keys/users
- Per-user analytics and preferences
- Shared vs personal server configurations

### 4. **Offline Capability**
- Config file access works offline
- Cached status provides last-known state
- Graceful degradation when Claude Code unavailable

### 5. **Operational Intelligence**
- Which servers are most reliable?
- What are usage patterns by time of day?
- Which configurations cause issues?
- Proactive health monitoring

## Migration Path

### Phase 1: Core Implementation
1. Create `MCPServerStateManager` class
2. Implement database schema and migrations
3. Add fast/cached/live method variants
4. Update existing `list_servers_fast()` to use new system

### Phase 2: Integration
1. Update CLI commands to use appropriate speed tier
2. Add caching layer to frequently-used operations
3. Implement background status refresh
4. Add config drift detection

### Phase 3: Analytics
1. Add usage event tracking
2. Implement analytics dashboard
3. Add health monitoring alerts
4. Create usage reports

## Technical Considerations

### 1. **Cache Invalidation**
- File system watchers for config changes
- TTL-based expiration for status cache
- Smart refresh triggers

### 2. **Concurrency**
- SQLite WAL mode for concurrent access
- Async/await for non-blocking operations  
- Connection pooling for database access

### 3. **Error Handling**
- Graceful fallback from live → cached → config
- Retry logic for transient failures
- Circuit breaker for consistently failing servers

### 4. **Privacy**
- Hash sensitive data (API keys, user info)
- Optional analytics opt-out
- Local-only storage by default

## Implementation Timeline

- **Week 1**: Core architecture and database setup
- **Week 2**: Fast/cached/live method implementation
- **Week 3**: CLI integration and testing
- **Week 4**: Analytics and monitoring features

This hybrid approach provides the best of all worlds: fast config access, rich historical data, and real-time status when needed.