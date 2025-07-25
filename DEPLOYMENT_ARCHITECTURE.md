# MCP Manager Deployment Architecture Options

## Overview
This document outlines deployment architecture decisions for the MCP Manager based on different deployment environments.

## Database Schema (Option 3 - Hybrid Approach)
The core schema remains consistent across all deployment options:

```sql
-- Master server registry (single source of truth)
CREATE TABLE mcp_server_registry (
    server_name TEXT PRIMARY KEY, -- Use name as natural key
    description TEXT,
    server_type TEXT,              -- npm, docker-desktop, custom
    install_command TEXT,
    package_name TEXT,
    discovery_metadata TEXT,       -- JSON with all discovery data
    last_discovered TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Suites
CREATE TABLE mcp_suites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lightweight memberships (reference by name)
CREATE TABLE suite_memberships (
    suite_id TEXT REFERENCES mcp_suites(id) ON DELETE CASCADE,
    server_name TEXT REFERENCES mcp_server_registry(server_name) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',    -- primary, secondary, optional, member
    priority INTEGER DEFAULT 50,   -- 1-100, higher = more important
    suite_specific_config TEXT,    -- JSON overrides
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (suite_id, server_name)
);

-- Test scenarios reference suites
CREATE TABLE test_scenarios (
    id TEXT PRIMARY KEY,
    suite_id TEXT REFERENCES mcp_suites(id),
    scenario_json TEXT,
    category TEXT
    -- ... other fields
);
```

## Deployment Options

### 1. Local Development
**Database**: SQLite with WAL mode
**Justification**: Simple, fast, no external dependencies
**Configuration**:
```python
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
```

### 2. Docker Environment
**Database**: PostgreSQL (container-native)
**Justification**: Multi-container access, network-based, scalable
**Architecture**:
```yaml
services:
  postgres:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  mcp-manager:
    depends_on: [postgres]
    environment:
      DATABASE_URL: postgres://user:pass@postgres:5432/mcp_manager
  
  test-runner:
    depends_on: [postgres, mcp-manager]
    environment:
      DATABASE_URL: postgres://user:pass@postgres:5432/mcp_manager
```

### 3. Cloud Service (AWS/GCP/Azure)
**Database**: Managed PostgreSQL (RDS/Cloud SQL/Azure Database)
**Justification**: High availability, automated backups, scaling
**Considerations**:
- Use connection pooling (PgBouncer)
- Configure read replicas for test runners
- Implement proper IAM/security groups

### 4. VPS Deployment (RECOMMENDED FOR NOW)
**Database**: SQLite with WAL mode
**Justification**: Cost-effective, simple, performant for single-instance
**Architecture**:
```bash
/opt/mcp-manager/
├── app/                 # Python application
├── data/               
│   ├── mcp_data.db     # SQLite database with WAL
│   └── backups/        # Automated backups
├── config/
├── logs/
└── docker-compose.yml  # Optional containerization
```

**VPS Specifications**:
- **Minimum**: 2GB RAM, 1 vCPU, 20GB disk
- **Recommended**: 4GB RAM, 2 vCPU, 40GB disk
- **Providers**: DigitalOcean (~$24/month), Linode, Vultr, Hetzner

**VPS SQLite Optimization**:
```python
# VPS-optimized SQLite configuration
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL; 
PRAGMA cache_size = 10000;      # 40MB cache
PRAGMA temp_store = memory;
PRAGMA mmap_size = 134217728;   # 128MB memory-mapped
```

## Data Flow Architecture

### Core Flow
1. **Input**: AI or user provides list of MCP server names
2. **Discovery**: System uses discovery to get real server info (name, description, commands, env vars, etc.)
3. **DB Storage**: All server information stored in `mcp_server_registry`
4. **Suite Creation**: Suite created with `suite_memberships` referencing stored servers
5. **Category Assignment**: Suite assigned to test category
6. **Test Execution**: JSON test scenarios pull suite info → load MCPs → run tests

### Key Queries
```sql
-- Get suite with all server details (primary query)
SELECT s.name as suite_name, 
       r.server_name, r.description, r.install_command,
       m.role, m.priority, r.discovery_metadata
FROM mcp_suites s
JOIN suite_memberships m ON s.id = m.suite_id  
JOIN mcp_server_registry r ON m.server_name = r.server_name
WHERE s.id = ?
ORDER BY m.priority DESC;

-- Get all suites using a specific server
SELECT s.name, m.role 
FROM mcp_suites s
JOIN suite_memberships m ON s.id = m.suite_id
WHERE m.server_name = ?;
```

## Migration Strategy

1. **Phase 1**: Implement SQLite + WAL for local development
2. **Phase 2**: Deploy to VPS with same SQLite schema
3. **Phase 3**: If scaling needed, migrate to PostgreSQL with identical schema
4. **Phase 4**: Move to managed cloud services if required

## Current Decision: SQLite + WAL Mode

**Rationale**:
- Single VPS deployment target
- Small dataset (hundreds of servers, dozens of suites)
- Read-heavy workload with infrequent writes
- Cost-effective ($24/month VPS vs $50+ managed DB)
- Simple deployment and backup strategy
- Excellent performance for use case

**Implementation Notes**:
- Use `aiosqlite` for async Python access
- Enable WAL mode for concurrent reads during writes
- Implement automated backups to cloud storage
- Monitor database size and performance metrics
- Plan PostgreSQL migration path if needed

## Future Considerations

- **Scaling Trigger**: If concurrent users > 50 or data > 1GB
- **High Availability**: Move to PostgreSQL with read replicas
- **Global Distribution**: Consider distributed databases (CockroachDB)
- **Analytics**: Add data warehouse for test analytics (ClickHouse/BigQuery)

---
*Last Updated: 2025-07-25*
*Next Review: When scaling requirements change*