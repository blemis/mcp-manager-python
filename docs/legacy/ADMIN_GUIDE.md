# MCP Manager Admin Guide

**Version 2.0** | **Enterprise Administration & Architecture**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Key Concepts & Components](#key-concepts--components)
3. [Installation & Deployment](#installation--deployment)
4. [Configuration Management](#configuration-management)
5. [API Server Administration](#api-server-administration)
6. [Proxy Server Architecture](#proxy-server-architecture)
7. [Analytics & Monitoring System](#analytics--monitoring-system)
8. [Workflow Engine](#workflow-engine)
9. [Security & Authentication](#security--authentication)
10. [Performance Tuning](#performance-tuning)
11. [Troubleshooting & Diagnostics](#troubleshooting--diagnostics)
12. [Production Deployment](#production-deployment)
13. [Development & Extension](#development--extension)

---

## Architecture Overview

### System Architecture

MCP Manager follows a modular, enterprise-grade architecture designed for scalability, maintainability, and extensibility.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Manager v2.0 Architecture                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   CLI/TUI       │    │   REST API      │    │  Proxy       │ │
│  │   Interface     │    │   Server        │    │  Server      │ │
│  │                 │    │                 │    │              │ │
│  │ • Rich CLI      │    │ • JWT Auth      │    │ • Protocol   │ │
│  │ • Terminal UI   │    │ • Rate Limiting │    │   Translation│ │
│  │ • Commands      │    │ • Analytics API │    │ • Load       │ │
│  │                 │    │                 │    │   Balance    │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                      │      │
│           └───────────────────────┼──────────────────────┘      │
│                                   │                             │
│  ┌─────────────────────────────────┼─────────────────────────────┐ │
│  │              Core Engine        │                             │ │
│  │                                 ▼                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │ │
│  │  │  Discovery  │  │  Workflow   │  │  Analytics  │           │ │
│  │  │  Engine     │  │  Engine     │  │  Engine     │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  │ • NPM       │  │ • Task AI   │  │ • Usage     │           │ │
│  │  │ • Docker    │  │ • Suite     │  │   Tracking  │           │ │
│  │  │ • AI Cured  │  │   Manager   │  │ • Metrics   │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │ │
│  │                                                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │ │
│  │  │   Suite     │  │    Tool     │  │   Server    │           │ │
│  │  │  Manager    │  │  Registry   │  │  Manager    │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  │ • CRUD Ops  │  │ • Search    │  │ • Lifecycle │           │ │
│  │  │ • Members   │  │ • Index     │  │ • Health    │           │ │
│  │  │ • Config    │  │ • Database  │  │ • Config    │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                   │                             │
│  ┌─────────────────────────────────┼─────────────────────────────┐ │
│  │           Data Layer            ▼                             │ │
│  │                                                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │ │
│  │  │   SQLite    │  │    TOML     │  │   Claude    │           │ │
│  │  │  Database   │  │   Config    │  │  Interface  │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  │ • Tools     │  │ • Settings  │  │ • Config    │           │ │
│  │  │ • Analytics │  │ • Profiles  │  │   Sync      │           │ │
│  │  │ • Suites    │  │ • Override  │  │ • MCP List  │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
    ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
    │    User     │       │   Admin     │       │  External   │
    │ Interface   │       │   Tools     │       │ Systems     │
    └──────┬──────┘       └──────┬──────┘       └──────┬──────┘
           │                     │                     │
           ▼                     ▼                     ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  API Gateway Layer                          │
    │                                                             │
    │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
    │  │    CLI      │   │  REST API   │   │   Proxy     │      │
    │  │  Commands   │   │   Server    │   │   Server    │      │
    │  └─────────────┘   └─────────────┘   └─────────────┘      │
    └─────────────┬───────────────┬───────────────┬─────────────┘
                  │               │               │
                  ▼               ▼               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                 Business Logic Layer                        │
    │                                                             │
    │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
    │  │  Discovery  │   │  Workflow   │   │  Analytics  │      │
    │  │   Manager   │   │   Manager   │   │   Service   │      │
    │  └─────────────┘   └─────────────┘   └─────────────┘      │
    │                                                             │
    │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
    │  │   Suite     │   │    Tool     │   │   Server    │      │
    │  │  Manager    │   │  Registry   │   │  Manager    │      │
    │  └─────────────┘   └─────────────┘   └─────────────┘      │
    └─────────────┬───────────────┬───────────────┬─────────────┘
                  │               │               │
                  ▼               ▼               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                   Data Access Layer                         │
    │                                                             │
    │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
    │  │  Database   │   │ Config File │   │   Claude    │      │
    │  │   Manager   │   │   Manager   │   │  Interface  │      │
    │  └─────────────┘   └─────────────┘   └─────────────┘      │
    └─────────────────────────────────────────────────────────────┘
```

---

## Key Concepts & Components

### 1. Modular Architecture Principles

**Single Responsibility**: Each module has one clear, focused purpose:
- `discovery/` - Server discovery from multiple sources
- `analytics/` - Usage tracking and performance metrics  
- `workflows/` - Task-specific automation
- `suites/` - Server collection management
- `api/` - REST API server functionality
- `proxy/` - Protocol translation and proxying

**Separation of Concerns**: Clean boundaries between layers:
- **Presentation Layer**: CLI, TUI, API endpoints
- **Business Logic**: Core managers and services
- **Data Layer**: Database, configuration, external interfaces

**Dependency Inversion**: High-level modules don't depend on low-level modules:
```python
# Good: Depends on abstraction
class AnalyticsService:
    def __init__(self, database: DatabaseInterface):
        self.db = database
        
# Bad: Depends on concrete implementation  
class AnalyticsService:
    def __init__(self):
        self.db = SQLiteDatabase()  # Tight coupling
```

### 2. Database Schema Design

**Tool Registry Schema:**
```sql
CREATE TABLE tool_registry (
    canonical_name TEXT PRIMARY KEY,
    server_name TEXT NOT NULL,
    server_type TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    description TEXT,
    parameters JSON,
    category TEXT,
    is_available BOOLEAN DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 1.0,
    avg_response_time REAL,
    last_used TIMESTAMP,
    last_discovered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tool_server_name ON tool_registry(server_name);
CREATE INDEX idx_tool_category ON tool_registry(category);
CREATE INDEX idx_tool_available ON tool_registry(is_available);
```

**Analytics Schema:**
```sql
CREATE TABLE usage_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,
    session_id TEXT,
    tool_canonical_name TEXT,
    method_name TEXT,
    parameters_hash TEXT,
    success BOOLEAN,
    response_time_ms REAL,
    error_code TEXT,
    error_message TEXT,
    
    FOREIGN KEY (tool_canonical_name) REFERENCES tool_registry(canonical_name)
);

CREATE INDEX idx_usage_timestamp ON usage_analytics(timestamp);
CREATE INDEX idx_usage_tool ON usage_analytics(tool_canonical_name);
CREATE INDEX idx_usage_success ON usage_analytics(success);
```

**Suite Management Schema:**
```sql
CREATE TABLE server_suites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    created_by TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE suite_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suite_id TEXT,
    server_name TEXT,
    role TEXT DEFAULT 'member',
    priority INTEGER DEFAULT 50,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (suite_id) REFERENCES server_suites(id) ON DELETE CASCADE,
    UNIQUE (suite_id, server_name)
);
```

### 3. Configuration Architecture

**Hierarchical Configuration System:**

```toml
# System-wide configuration (/etc/mcp-manager/config.toml)
[system]
organization = "Enterprise Corp"
default_policies = "strict"
audit_required = true

[discovery]
allowed_sources = ["docker-desktop", "internal-registry"]
blocked_sources = ["docker-hub"]  # Security policy
quality_threshold = 9.0

[security]
require_authentication = true
api_rate_limit = 1000
session_timeout = 3600
```

```toml
# User configuration (~/.config/mcp-manager/config.toml)
[user]
preferred_interface = "tui"
auto_sync = true

[discovery]
quality_threshold = 7.0  # Override system default
cache_ttl = 1800

[workflows]
auto_activate_dev = true
default_category = "development"
```

```toml
# Project configuration (./.mcp-manager.toml)
[project]
name = "web-app"
team = "frontend"

[servers]
required = ["filesystem", "http-client", "database"]
optional = ["testing-tools"]

[workflows]
development = ["filesystem", "database", "testing-tools"]
production = ["filesystem", "database"]
```

### 4. Event System & Hooks

**Event-Driven Architecture:**

```python
class EventManager:
    """Central event management for MCP Manager."""
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}
    
    def emit(self, event: str, data: Any = None):
        """Emit event to all registered listeners."""
        for listener in self.listeners.get(event, []):
            try:
                listener(data)
            except Exception as e:
                logger.error(f"Event listener error: {e}")
    
    def on(self, event: str, callback: Callable):
        """Register event listener."""
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

# Usage examples
events.on('server.installed', lambda data: analytics.track_installation(data))
events.on('workflow.activated', lambda data: monitor.update_workflow_state(data))
events.on('suite.created', lambda data: audit.log_suite_creation(data))
```

---

## Installation & Deployment

### Development Installation

```bash
# Clone repository
git clone https://github.com/your-org/mcp-manager
cd mcp-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Start development server
python -m mcp_manager.cli.main status
```

### Production Installation

```bash
# Method 1: PyPI (when available)
pip install mcp-manager[production]

# Method 2: Docker
docker pull mcpmanager/mcp-manager:latest
docker run -d --name mcp-manager \
  -p 8000:8000 \
  -v /etc/mcp-manager:/config \
  -v /var/lib/mcp-manager:/data \
  mcpmanager/mcp-manager:latest

# Method 3: System package (when available)
sudo apt install mcp-manager  # Ubuntu/Debian
sudo yum install mcp-manager  # RHEL/CentOS
brew install mcp-manager       # macOS
```

### Service Installation

**Systemd Service (Linux):**

```ini
# /etc/systemd/system/mcp-manager.service
[Unit]
Description=MCP Manager Service
After=network.target
Wants=network.target

[Service]
Type=notify
User=mcp-manager
Group=mcp-manager
WorkingDirectory=/opt/mcp-manager
Environment="PATH=/opt/mcp-manager/venv/bin"
ExecStart=/opt/mcp-manager/venv/bin/mcp-manager api start --daemon
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

**macOS LaunchAgent:**

```xml
<!-- ~/Library/LaunchAgents/com.mcpmanager.service.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mcpmanager.service</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/mcp-manager</string>
        <string>api</string>
        <string>start</string>
        <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/mcp-manager.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/mcp-manager.error.log</string>
</dict>
</plist>
```

---

## Configuration Management

### Configuration Files

**System Configuration (`/etc/mcp-manager/config.toml`):**

```toml
[general]
organization = "Your Organization"
environment = "production"
debug = false

[api]
enabled = true
host = "0.0.0.0"
port = 8000
workers = 4
timeout = 30
max_requests_per_minute = 1000
max_requests_per_hour = 10000

[authentication]
method = "jwt"  # jwt, api_key, oauth
secret_key = "${MCP_JWT_SECRET}"
token_expiry = 86400  # 24 hours
require_authentication = true

[database]
url = "sqlite:///var/lib/mcp-manager/mcp-manager.db"
connection_pool_size = 10
query_timeout = 30

[logging]
level = "INFO"
format = "json"
file = "/var/log/mcp-manager/app.log"
max_size = "100MB"
backup_count = 10
access_log = "/var/log/mcp-manager/access.log"

[security]
allowed_origins = ["https://dashboard.company.com"]
trusted_proxies = ["192.168.1.0/24"]
rate_limiting = true
audit_logging = true
audit_file = "/var/log/mcp-manager/audit.log"

[discovery]
sources = ["docker-desktop", "npm", "internal-registry"]
cache_ttl = 3600
quality_threshold = 8.0
concurrent_requests = 10
timeout = 30

[monitoring]
enabled = true
metrics_port = 9090
health_check_interval = 60
alert_webhook = "https://alerts.company.com/webhook"

[backup]
enabled = true
schedule = "0 2 * * *"  # Daily at 2 AM
retention_days = 30
destination = "/backup/mcp-manager"
```

### Environment Variables

**Required Environment Variables:**

```bash
# Security
export MCP_JWT_SECRET="your-super-secure-jwt-secret-key"
export MCP_API_KEY_SALT="random-salt-for-api-keys"

# Database
export MCP_DATABASE_URL="postgresql://user:pass@localhost/mcp_manager"
export MCP_DATABASE_SSL_MODE="require"

# External Services
export MCP_CLAUDE_API_KEY="your-claude-api-key"
export MCP_NPM_REGISTRY_TOKEN="your-npm-token"

# Monitoring
export MCP_SENTRY_DSN="https://your-sentry-dsn"
export MCP_PROMETHEUS_GATEWAY="http://prometheus:9091"
```

**Optional Environment Variables:**

```bash
# Performance
export MCP_WORKER_COUNT="8"
export MCP_CONNECTION_POOL_SIZE="20"
export MCP_CACHE_SIZE="1000"

# Features
export MCP_ENABLE_API="true"
export MCP_ENABLE_PROXY="true"
export MCP_ENABLE_ANALYTICS="true"

# Development
export MCP_DEBUG="false"
export MCP_LOG_LEVEL="INFO"
export MCP_PROFILE="false"
```

### Configuration Validation

**Schema Validation:**

```python
from pydantic import BaseModel, validator
from typing import List, Optional

class APIConfig(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 4
    timeout: int = 30
    max_requests_per_minute: int = 1000
    
    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @validator('workers')
    def validate_workers(cls, v):
        if not 1 <= v <= 32:
            raise ValueError('Workers must be between 1 and 32')
        return v

class Config(BaseModel):
    general: GeneralConfig
    api: APIConfig
    database: DatabaseConfig
    security: SecurityConfig
    
    class Config:
        validate_assignment = True
        extra = "forbid"  # Prevent unknown configuration keys
```

---

## API Server Administration

### API Architecture

**FastAPI Application Structure:**

```python
# src/mcp_manager/api/server.py
class APIServer:
    """Main API server with middleware stack."""
    
    def __init__(self, config: Config):
        self.config = config
        self.app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        app = FastAPI(
            title="MCP Manager API",
            description="Enterprise MCP Server Management API",
            version="2.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add middleware in correct order
        self._add_middleware(app)
        self._add_routes(app)
        
        return app
    
    def _add_middleware(self, app: FastAPI):
        # Security middleware (outermost)
        app.add_middleware(SecurityMiddleware)
        
        # Authentication middleware
        app.add_middleware(AuthenticationMiddleware)
        
        # Rate limiting middleware
        app.add_middleware(RateLimitMiddleware)
        
        # Request logging middleware
        app.add_middleware(RequestLoggingMiddleware)
        
        # Error handling middleware (innermost)
        app.add_middleware(ErrorHandlingMiddleware)
```

### Authentication & Authorization

**JWT Token Management:**

```python
class AuthenticationManager:
    """JWT and API key authentication manager."""
    
    def create_jwt_token(self, user_id: str, scopes: List[str]) -> str:
        """Create JWT token with specified scopes."""
        payload = {
            'user_id': user_id,
            'scopes': scopes,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(seconds=self.token_expiry)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_jwt_token(self, token: str) -> Optional[Dict]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token")
            return None
```

**Scope-Based Authorization:**

```python
PERMISSION_SCOPES = {
    'analytics:read': 'Read analytics data',
    'analytics:write': 'Modify analytics settings',
    'analytics:export': 'Export analytics data',
    'tools:read': 'Search and list tools',
    'tools:write': 'Modify tool registry',
    'servers:read': 'List MCP servers',
    'servers:write': 'Manage MCP servers',
    'admin:full': 'Full administrative access',
    'proxy:read': 'View proxy status',
    'proxy:write': 'Configure proxy servers'
}

def check_permission(user_scopes: List[str], required_scope: str) -> bool:
    """Check if user has required permission scope."""
    if 'admin:full' in user_scopes:
        return True
    return required_scope in user_scopes
```

### Rate Limiting

**Implementation:**

```python
class RateLimitMiddleware:
    """Rate limiting middleware with per-user limits."""
    
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.rpm_limit = requests_per_minute
        self.rph_limit = requests_per_hour
        self.redis_client = redis.Redis()  # Or in-memory store
    
    async def __call__(self, request: Request, call_next):
        client_id = self._get_client_id(request)
        
        # Check rate limits
        if not self._check_rate_limit(client_id):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"}
            )
        
        # Update rate limit counters
        self._update_rate_limit(client_id)
        
        response = await call_next(request)
        return response
```

### API Monitoring

**Metrics Collection:**

```python
from prometheus_client import Counter, Histogram, Gauge

# API Metrics
REQUEST_COUNT = Counter('mcp_api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('mcp_api_request_duration_seconds', 'API request duration')
ACTIVE_CONNECTIONS = Gauge('mcp_api_active_connections', 'Active API connections')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_DURATION.observe(time.time() - start_time)
    
    return response
```

---

## Proxy Server Architecture

### Proxy Components

**Core Proxy Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                       MCP Proxy Server                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   HTTP Server   │    │   WebSocket     │    │  Protocol    │ │
│  │                 │    │   Handler       │    │  Translator  │ │
│  │ • REST API      │    │                 │    │              │ │
│  │ • Middleware    │    │ • Real-time     │    │ • MCP v1/v2  │ │
│  │ • CORS          │    │ • Bidirectional │    │ • Legacy     │ │
│  │                 │    │                 │    │ • Auto-detect│ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                      │      │
│           └───────────────────────┼──────────────────────┘      │
│                                   │                             │
│  ┌─────────────────────────────────┼─────────────────────────────┐ │
│  │             Proxy Manager       ▼                             │ │
│  │                                                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │ │
│  │  │   Request   │  │    Load     │  │   Health    │           │ │
│  │  │   Router    │  │  Balancer   │  │  Monitor    │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  │ • Rules     │  │ • Round     │  │ • Heartbeat │           │ │
│  │  │ • Patterns  │  │   Robin     │  │ • Status    │           │ │
│  │  │ • Fallback  │  │ • Weighted  │  │ • Recovery  │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                   │                             │
│  ┌─────────────────────────────────┼─────────────────────────────┐ │
│  │          Backend Servers        ▼                             │ │
│  │                                                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │ │
│  │  │   Server A  │  │   Server B  │  │   Server C  │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  │ • MCP v1    │  │ • MCP v2    │  │ • Legacy    │           │ │
│  │  │ • Tools     │  │ • Enhanced  │  │ • Simple    │           │ │
│  │  │ • Resources │  │ • Metadata  │  │ • Basic     │           │ │
│  │  │             │  │             │  │             │           │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Protocol Translation

**MCP Protocol Versions:**

```python
class ProtocolTranslator:
    """Translates between different MCP protocol versions."""
    
    def translate_request(self, request: ProxyRequest, 
                         target_protocol: ProtocolVersion) -> Dict[str, Any]:
        """Translate request to target protocol format."""
        
        if target_protocol == ProtocolVersion.MCP_V1:
            return {
                "jsonrpc": "2.0",
                "method": request.method,
                "params": request.params or {},
                "id": request.id or self._generate_id()
            }
        
        elif target_protocol == ProtocolVersion.MCP_V2:
            return {
                "jsonrpc": "2.0",
                "method": request.method,
                "params": request.params or {},
                "id": request.id or self._generate_id(),
                "meta": {
                    "version": "2.0",
                    "client": "mcp-manager-proxy",
                    "capabilities": self._get_capabilities(),
                    "context": {
                        "user_id": request.user_id,
                        "session_id": request.session_id
                    }
                }
            }
        
        elif target_protocol == ProtocolVersion.LEGACY:
            # Legacy format without JSON-RPC wrapper
            return {
                "method": request.method,
                "params": request.params or {},
                "id": request.id or self._generate_id()
            }
```

### Load Balancing Strategies

**Round Robin:**

```python
class RoundRobinBalancer:
    """Simple round-robin load balancing."""
    
    def __init__(self):
        self.current_index = 0
        self.lock = asyncio.Lock()
    
    async def select_server(self, servers: List[str]) -> str:
        """Select next server in round-robin fashion."""
        async with self.lock:
            if not servers:
                raise NoAvailableServersError()
            
            server = servers[self.current_index % len(servers)]
            self.current_index += 1
            return server
```

**Weighted Round Robin:**

```python
class WeightedRoundRobinBalancer:
    """Weighted round-robin load balancing."""
    
    def __init__(self):
        self.current_weights = {}
        self.lock = asyncio.Lock()
    
    async def select_server(self, server_configs: List[ProxyServerConfig]) -> str:
        """Select server based on weights."""
        async with self.lock:
            if not server_configs:
                raise NoAvailableServersError()
            
            # Find server with highest current weight
            best_server = None
            best_weight = -1
            
            for config in server_configs:
                current = self.current_weights.get(config.name, config.weight)
                if current > best_weight:
                    best_weight = current
                    best_server = config
            
            # Decrease current weight and reset if needed
            self.current_weights[best_server.name] = best_weight - 1
            if best_weight <= 0:
                self.current_weights[best_server.name] = best_server.weight
            
            return best_server.name
```

### Health Monitoring

**Server Health Checks:**

```python
class HealthMonitor:
    """Monitors health of backend MCP servers."""
    
    async def check_server_health(self, server_config: ProxyServerConfig) -> ServerHealth:
        """Perform health check on single server."""
        start_time = time.time()
        
        try:
            # Send health check request
            health_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "health_check",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mcp-manager-proxy",
                        "version": "2.0.0"
                    }
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    server_config.url,
                    json=health_request,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        response_data = await response.json()
                        response_time = (time.time() - start_time) * 1000
                        
                        return ServerHealth(
                            name=server_config.name,
                            status=ServerStatus.ONLINE,
                            last_check=datetime.utcnow(),
                            response_time_ms=response_time,
                            consecutive_failures=0
                        )
                    else:
                        raise aiohttp.ClientError(f"HTTP {response.status}")
                        
        except Exception as e:
            return ServerHealth(
                name=server_config.name,
                status=ServerStatus.ERROR,
                last_check=datetime.utcnow(),
                error_message=str(e),
                consecutive_failures=self._get_failure_count(server_config.name) + 1
            )
```

---

## Analytics & Monitoring System

### Analytics Architecture

**Data Flow:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Analytics Data Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │     Data        │    │     Data        │    │    Query     │ │
│  │   Collection    │    │   Processing    │    │   Engine     │ │
│  │                 │    │                 │    │              │ │
│  │ • Tool Usage    │───▶│ • Aggregation   │───▶│ • SQL Query  │ │
│  │ • Performance   │    │ • Metrics       │    │ • Analytics  │ │
│  │ • Errors        │    │ • Trends        │    │ • Reporting  │ │
│  │ • API Calls     │    │ • Patterns      │    │              │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                      │      │
│           │                       ▼                      ▼      │
│           │              ┌─────────────────┐    ┌──────────────┐ │
│           │              │    Database     │    │  Dashboard   │ │
│           │              │                 │    │              │ │
│           │              │ • Time Series   │    │ • Web UI     │ │
│           │              │ • Indexes       │    │ • Charts     │ │
│           │              │ • Partitions    │    │ • Export     │ │
│           │              │                 │    │              │ │
│           │              └─────────────────┘    └──────────────┘ │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   Event Stream                              │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │   Kafka     │  │   Redis     │  │  WebSocket  │         │ │
│  │  │  (Buffer)   │  │  (Cache)    │  │ (Real-time) │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Usage Analytics Implementation

**Data Collection:**

```python
class AnalyticsCollector:
    """Collects usage data from various sources."""
    
    def __init__(self, database: DatabaseManager):
        self.db = database
        self.buffer = []
        self.buffer_size = 1000
        self.flush_interval = 60  # seconds
    
    async def track_tool_usage(self, tool_call: ToolCall):
        """Track individual tool usage."""
        usage_data = {
            'timestamp': datetime.utcnow(),
            'user_id': tool_call.user_id,
            'session_id': tool_call.session_id,
            'tool_canonical_name': tool_call.canonical_name,
            'method_name': tool_call.method,
            'parameters_hash': self._hash_parameters(tool_call.parameters),
            'success': tool_call.success,
            'response_time_ms': tool_call.response_time_ms,
            'error_code': tool_call.error_code,
            'error_message': tool_call.error_message
        }
        
        # Add to buffer
        self.buffer.append(usage_data)
        
        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Flush buffered data to database."""
        if not self.buffer:
            return
        
        try:
            await self.db.insert_batch('usage_analytics', self.buffer)
            logger.info(f"Flushed {len(self.buffer)} analytics records")
            self.buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush analytics buffer: {e}")
```

**Query Engine:**

```python
class AnalyticsQueryProcessor:
    """Processes analytics queries with caching and optimization."""
    
    def __init__(self, database: DatabaseManager):
        self.db = database
        self.cache = TTLCache(maxsize=1000, ttl=300)  # 5-minute cache
    
    async def get_usage_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get usage summary for specified period."""
        cache_key = f"usage_summary_{days}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Execute optimized queries
        async with self.db.get_connection() as conn:
            # Total metrics
            total_query = """
                SELECT 
                    COUNT(*) as total_queries,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT tool_canonical_name) as active_tools,
                    AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100 as success_rate,
                    AVG(response_time_ms) as avg_response_time
                FROM usage_analytics 
                WHERE timestamp BETWEEN ? AND ?
            """
            
            cursor = await conn.execute(total_query, (start_date, end_date))
            total_metrics = await cursor.fetchone()
            
            # Top tools
            tools_query = """
                SELECT 
                    tool_canonical_name,
                    COUNT(*) as usage_count,
                    AVG(response_time_ms) as avg_response_time
                FROM usage_analytics 
                WHERE timestamp BETWEEN ? AND ? AND success = 1
                GROUP BY tool_canonical_name
                ORDER BY usage_count DESC
                LIMIT 10
            """
            
            cursor = await conn.execute(tools_query, (start_date, end_date))
            top_tools = await cursor.fetchall()
            
            result = {
                'total_queries': total_metrics[0],
                'unique_users': total_metrics[1],
                'active_tools': total_metrics[2],
                'success_rate': round(total_metrics[3] or 0, 1),
                'avg_response_time': round(total_metrics[4] or 0, 2),
                'top_tools': [
                    {
                        'name': tool[0],
                        'usage_count': tool[1],
                        'avg_response_time': round(tool[2] or 0, 2)
                    }
                    for tool in top_tools
                ]
            }
            
            # Cache result
            self.cache[cache_key] = result
            return result
```

### Performance Metrics

**Real-time Metrics:**

```python
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

class MetricsCollector:
    """Prometheus metrics collector for MCP Manager."""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # Tool usage metrics
        self.tool_calls_total = Counter(
            'mcp_tool_calls_total',
            'Total tool calls',
            ['tool_name', 'server_name', 'status'],
            registry=self.registry
        )
        
        self.tool_response_time = Histogram(
            'mcp_tool_response_time_seconds',
            'Tool response time',
            ['tool_name', 'server_name'],
            registry=self.registry
        )
        
        # Server metrics
        self.active_servers = Gauge(
            'mcp_active_servers',
            'Number of active MCP servers',
            registry=self.registry
        )
        
        self.server_health_status = Gauge(
            'mcp_server_health_status',
            'Server health status (1=healthy, 0=unhealthy)',
            ['server_name'],
            registry=self.registry
        )
        
        # Workflow metrics
        self.active_workflows = Gauge(
            'mcp_active_workflows',
            'Number of active workflows',
            registry=self.registry
        )
        
        self.workflow_switches = Counter(
            'mcp_workflow_switches_total',
            'Total workflow switches',
            ['from_workflow', 'to_workflow'],
            registry=self.registry
        )
    
    def record_tool_call(self, tool_name: str, server_name: str, 
                        response_time: float, success: bool):
        """Record tool call metrics."""
        status = 'success' if success else 'error'
        
        self.tool_calls_total.labels(
            tool_name=tool_name,
            server_name=server_name,
            status=status
        ).inc()
        
        if success:
            self.tool_response_time.labels(
                tool_name=tool_name,
                server_name=server_name
            ).observe(response_time)
```

---

## Workflow Engine

### Workflow Architecture

**Workflow State Machine:**

```
┌─────────────────────────────────────────────────────────────────┐
│                      Workflow States                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐     create      ┌─────────────┐               │
│   │             │ ───────────────▶ │             │               │
│   │   NONE      │                  │  DEFINED    │               │
│   │             │ ◀─────────────── │             │               │
│   └─────────────┘     delete       └─────────┬───┘               │
│                                               │                   │
│                                               │ activate          │
│                                               ▼                   │
│   ┌─────────────┐   deactivate   ┌─────────────┐                 │
│   │             │ ◀───────────── │             │                 │
│   │  INACTIVE   │                │   ACTIVE    │                 │
│   │             │ ──────────────▶ │             │                 │
│   └─────────────┘   activate      └─────┬───────┘                 │
│                                         │                         │
│                                         │ switch                  │
│                                         ▼                         │
│                                 ┌─────────────┐                   │
│                                 │             │                   │
│                                 │ SWITCHING   │                   │
│                                 │             │                   │
│                                 └─────┬───────┘                   │
│                                       │                           │
│                                       │ complete                  │
│                                       ▼                           │
│                                 ┌─────────────┐                   │
│                                 │             │                   │
│                                 │   ACTIVE    │                   │
│                                 │  (new)      │                   │
│                                 │             │                   │
│                                 └─────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### AI-Driven Recommendations

**Task Classification:**

```python
class TaskClassifier:
    """AI-powered task classification for workflow recommendations."""
    
    def __init__(self, model_provider: LLMProvider):
        self.model = model_provider
        self.classification_cache = TTLCache(maxsize=500, ttl=3600)
    
    async def classify_task(self, task_description: str) -> TaskCategory:
        """Classify task and recommend category."""
        
        if task_description in self.classification_cache:
            return self.classification_cache[task_description]
        
        # Prepare classification prompt
        prompt = f"""
        Classify the following task into one of these categories:
        - development: Software development, coding, debugging
        - data_analysis: Data science, analytics, reporting
        - content_creation: Writing, documentation, content generation
        - system_administration: DevOps, deployment, infrastructure
        - research: Investigation, learning, exploration
        - testing: QA, testing, validation
        - design: UI/UX design, prototyping
        
        Task: "{task_description}"
        
        Respond with only the category name.
        """
        
        try:
            response = await self.model.generate(prompt)
            category = TaskCategory(response.strip().lower())
            
            # Cache result
            self.classification_cache[task_description] = category
            return category
            
        except Exception as e:
            logger.error(f"Task classification failed: {e}")
            return TaskCategory.DEVELOPMENT  # Default fallback
```

**Workflow Recommendation Engine:**

```python
class WorkflowRecommendationEngine:
    """AI-powered workflow recommendations."""
    
    def __init__(self, analytics: AnalyticsService, classifier: TaskClassifier):
        self.analytics = analytics
        self.classifier = classifier
    
    async def recommend_workflow(self, 
                               task_description: str,
                               user_id: Optional[str] = None) -> List[WorkflowRecommendation]:
        """Generate workflow recommendations for task."""
        
        # Classify the task
        task_category = await self.classifier.classify_task(task_description)
        
        # Get user's historical preferences
        user_preferences = await self._get_user_preferences(user_id)
        
        # Get workflows for category
        candidate_workflows = await self._get_workflows_by_category(task_category)
        
        # Score workflows
        recommendations = []
        for workflow in candidate_workflows:
            score = await self._score_workflow(workflow, task_description, user_preferences)
            
            recommendations.append(WorkflowRecommendation(
                workflow=workflow,
                score=score,
                reasoning=await self._generate_reasoning(workflow, task_description)
            ))
        
        # Sort by score and return top recommendations
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations[:5]
    
    async def _score_workflow(self, 
                             workflow: WorkflowConfig,
                             task_description: str,
                             user_preferences: Dict) -> float:
        """Score workflow relevance for task."""
        
        # Base score from workflow priority
        score = workflow.priority / 100.0
        
        # Boost for user preferences
        if workflow.name in user_preferences.get('preferred_workflows', []):
            score += 0.3
        
        # Boost for successful historical usage
        usage_stats = await self.analytics.get_workflow_stats(workflow.name)
        if usage_stats['success_rate'] > 0.9:
            score += 0.2
        
        # Boost for recent usage
        if usage_stats['last_used_days'] < 7:
            score += 0.1
        
        # AI-based relevance score
        relevance = await self._calculate_ai_relevance(workflow, task_description)
        score += relevance * 0.4
        
        return min(score, 1.0)  # Cap at 1.0
```

### Workflow Automation

**Activation Manager:**

```python
class ActivationManager:
    """Manages workflow activation and server configuration changes."""
    
    def __init__(self, server_manager: ServerManager, suite_manager: SuiteManager):
        self.server_manager = server_manager
        self.suite_manager = suite_manager
        self.activation_history = []
    
    async def activate_workflow(self, 
                              workflow: WorkflowConfig,
                              current_workflow: Optional[WorkflowConfig] = None) -> bool:
        """Activate workflow with server configuration changes."""
        
        try:
            # Start activation transaction
            async with self._activation_transaction():
                
                # Deactivate current workflow if exists
                if current_workflow:
                    await self._deactivate_workflow_servers(current_workflow)
                
                # Get servers from workflow suites
                servers_to_activate = await self._resolve_workflow_servers(workflow)
                
                # Activate servers
                activation_results = []
                for server_name in servers_to_activate:
                    try:
                        success = await self.server_manager.enable_server(server_name)
                        activation_results.append((server_name, success))
                        
                        if success:
                            logger.info(f"Activated server '{server_name}' for workflow '{workflow.name}'")
                        else:
                            logger.warning(f"Failed to activate server '{server_name}'")
                            
                    except Exception as e:
                        logger.error(f"Error activating server '{server_name}': {e}")
                        activation_results.append((server_name, False))
                
                # Check if activation was successful
                successful_activations = sum(1 for _, success in activation_results if success)
                total_servers = len(servers_to_activate)
                
                if successful_activations == 0:
                    raise WorkflowActivationError("No servers could be activated")
                
                # Update workflow state
                workflow.last_used = datetime.utcnow()
                workflow.activation_count += 1
                
                # Record activation history
                self.activation_history.append(WorkflowActivation(
                    workflow_name=workflow.name,
                    timestamp=datetime.utcnow(),
                    servers_activated=successful_activations,
                    total_servers=total_servers,
                    success=successful_activations == total_servers
                ))
                
                logger.info(f"Workflow '{workflow.name}' activated successfully "
                           f"({successful_activations}/{total_servers} servers)")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to activate workflow '{workflow.name}': {e}")
            return False
```

---

## Security & Authentication

### Authentication Methods

**JWT Authentication:**

```python
class JWTAuthenticator:
    """JWT token-based authentication."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry = 86400  # 24 hours
    
    def create_token(self, user_id: str, scopes: List[str]) -> str:
        """Create JWT token."""
        payload = {
            'sub': user_id,
            'scopes': scopes,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(seconds=self.token_expiry),
            'jti': str(uuid.uuid4())  # Unique token ID
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token blacklist
            if self._is_token_blacklisted(payload.get('jti')):
                return None
            
            return TokenPayload(
                user_id=payload['sub'],
                scopes=payload['scopes'],
                issued_at=datetime.fromtimestamp(payload['iat']),
                expires_at=datetime.fromtimestamp(payload['exp']),
                token_id=payload['jti']
            )
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
```

**API Key Authentication:**

```python
class APIKeyManager:
    """API key management with secure storage."""
    
    def __init__(self, database: DatabaseManager, salt: str):
        self.db = database
        self.salt = salt
    
    def create_api_key(self, 
                      name: str,
                      scopes: List[str],
                      expires_days: Optional[int] = None) -> APIKey:
        """Create new API key."""
        
        # Generate secure random key
        raw_key = self._generate_secure_key()
        key_hash = self._hash_key(raw_key)
        
        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        # Create API key record
        api_key = APIKey(
            key_id=str(uuid.uuid4()),
            name=name,
            key_hash=key_hash,
            scopes=scopes,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True
        )
        
        # Store in database
        self.db.insert('api_keys', api_key.dict(exclude={'raw_key'}))
        
        # Return with raw key (only time it's visible)
        api_key.raw_key = raw_key
        return api_key
    
    def validate_api_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate API key and return details."""
        key_hash = self._hash_key(raw_key)
        
        # Query database
        query = """
            SELECT * FROM api_keys 
            WHERE key_hash = ? AND is_active = 1
            AND (expires_at IS NULL OR expires_at > ?)
        """
        
        result = self.db.query_one(query, (key_hash, datetime.utcnow()))
        
        if result:
            return APIKey(**result)
        return None
    
    def _generate_secure_key(self) -> str:
        """Generate cryptographically secure API key."""
        return secrets.token_urlsafe(32)
    
    def _hash_key(self, raw_key: str) -> str:
        """Hash API key with salt."""
        return hashlib.pbkdf2_hmac(
            'sha256',
            raw_key.encode('utf-8'),
            self.salt.encode('utf-8'),
            100000  # iterations
        ).hex()
```

### Authorization & Permissions

**Role-Based Access Control:**

```python
class RBACManager:
    """Role-based access control manager."""
    
    ROLES = {
        'viewer': {
            'description': 'Read-only access to most resources',
            'permissions': [
                'analytics:read',
                'tools:read',
                'servers:read',
                'workflows:read',
                'suites:read'
            ]
        },
        'operator': {
            'description': 'Can manage servers and workflows',
            'permissions': [
                'analytics:read',
                'tools:read', 'tools:write',
                'servers:read', 'servers:write',
                'workflows:read', 'workflows:write',
                'suites:read', 'suites:write'
            ]
        },
        'admin': {
            'description': 'Full administrative access',
            'permissions': [
                'analytics:read', 'analytics:write', 'analytics:export',
                'tools:read', 'tools:write',
                'servers:read', 'servers:write',
                'workflows:read', 'workflows:write',
                'suites:read', 'suites:write',
                'proxy:read', 'proxy:write',
                'admin:full'
            ]
        }
    }
    
    def check_permission(self, user_scopes: List[str], required_permission: str) -> bool:
        """Check if user has required permission."""
        
        # Admin override
        if 'admin:full' in user_scopes:
            return True
        
        # Direct permission check
        if required_permission in user_scopes:
            return True
        
        # Role-based permission check
        for scope in user_scopes:
            if scope.startswith('role:'):
                role_name = scope[5:]  # Remove 'role:' prefix
                role = self.ROLES.get(role_name)
                if role and required_permission in role['permissions']:
                    return True
        
        return False
```

### Security Middleware

**Rate Limiting:**

```python
class RateLimitMiddleware:
    """Advanced rate limiting with different strategies."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.redis_client = redis.Redis()
        
    async def __call__(self, request: Request, call_next):
        client_id = self._get_client_id(request)
        
        # Check different rate limit types
        limits_to_check = [
            ('per_minute', 60, self.config.requests_per_minute),
            ('per_hour', 3600, self.config.requests_per_hour),
            ('per_day', 86400, self.config.requests_per_day)
        ]
        
        for limit_type, window, max_requests in limits_to_check:
            if not await self._check_limit(client_id, limit_type, window, max_requests):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "limit_type": limit_type,
                        "retry_after": window
                    },
                    headers={"Retry-After": str(window)}
                )
        
        # Update counters
        await self._update_counters(client_id)
        
        response = await call_next(request)
        return response
    
    async def _check_limit(self, client_id: str, limit_type: str, 
                          window: int, max_requests: int) -> bool:
        """Check if client is within rate limit."""
        key = f"rate_limit:{client_id}:{limit_type}"
        
        # Use sliding window algorithm
        now = time.time()
        pipeline = self.redis_client.pipeline()
        
        # Remove old entries
        pipeline.zremrangebyscore(key, 0, now - window)
        
        # Count current entries
        pipeline.zcard(key)
        
        # Add current request
        pipeline.zadd(key, {str(now): now})
        
        # Set expiration
        pipeline.expire(key, window)
        
        results = pipeline.execute()
        current_count = results[1]
        
        return current_count < max_requests
```

---

## Performance Tuning

### Database Optimization

**Connection Pooling:**

```python
class DatabaseManager:
    """Optimized database manager with connection pooling."""
    
    def __init__(self, database_url: str, pool_size: int = 10):
        self.database_url = database_url
        self.pool_size = pool_size
        self.pool = None
    
    async def initialize(self):
        """Initialize connection pool."""
        self.pool = await aiopg.create_pool(
            self.database_url,
            minsize=1,
            maxsize=self.pool_size,
            timeout=30,
            command_timeout=30
        )
    
    async def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query with connection from pool."""
        async with self.pool.acquire() as conn:
            async with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                await cursor.execute(query, params)
                
                if cursor.description:
                    return await cursor.fetchall()
                return []
    
    async def execute_batch(self, query: str, params_list: List[tuple]):
        """Execute batch insert/update with transaction."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                async with conn.cursor() as cursor:
                    await cursor.executemany(query, params_list)
```

**Query Optimization:**

```sql
-- Optimized analytics queries with proper indexing

-- Index for timestamp-based queries
CREATE INDEX CONCURRENTLY idx_usage_analytics_timestamp_tool 
ON usage_analytics(timestamp, tool_canonical_name);

-- Index for user-based queries  
CREATE INDEX CONCURRENTLY idx_usage_analytics_user_timestamp
ON usage_analytics(user_id, timestamp) 
WHERE user_id IS NOT NULL;

-- Partial index for successful operations only
CREATE INDEX CONCURRENTLY idx_usage_analytics_success
ON usage_analytics(tool_canonical_name, timestamp)
WHERE success = true;

-- Optimized usage summary query
WITH daily_stats AS (
    SELECT 
        DATE_TRUNC('day', timestamp) as day,
        COUNT(*) as daily_requests,
        COUNT(DISTINCT user_id) as daily_users,
        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) * 100 as daily_success_rate
    FROM usage_analytics 
    WHERE timestamp >= NOW() - INTERVAL '30 days'
    GROUP BY DATE_TRUNC('day', timestamp)
)
SELECT 
    SUM(daily_requests) as total_requests,
    MAX(daily_users) as peak_daily_users,
    AVG(daily_success_rate) as avg_success_rate
FROM daily_stats;
```

### Caching Strategy

**Multi-Level Caching:**

```python
class CacheManager:
    """Multi-level caching with Redis and in-memory tiers."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.memory_cache = TTLCache(maxsize=1000, ttl=300)  # 5-minute TTL
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'redis_hits': 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (memory first, then Redis)."""
        
        # Check memory cache first
        if key in self.memory_cache:
            self.cache_stats['hits'] += 1
            self.cache_stats['memory_hits'] += 1
            return self.memory_cache[key]
        
        # Check Redis cache
        try:
            value = await self.redis.get(key)
            if value:
                # Deserialize and store in memory cache
                deserialized_value = pickle.loads(value)
                self.memory_cache[key] = deserialized_value
                
                self.cache_stats['hits'] += 1
                self.cache_stats['redis_hits'] += 1
                return deserialized_value
                
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")
        
        # Cache miss
        self.cache_stats['misses'] += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in both cache tiers."""
        
        # Store in memory cache
        self.memory_cache[key] = value
        
        # Store in Redis cache
        try:
            serialized_value = pickle.dumps(value)
            await self.redis.setex(key, ttl, serialized_value)
        except Exception as e:
            logger.warning(f"Redis cache set error: {e}")
```

### Async Processing

**Background Task Queue:**

```python
class TaskQueue:
    """Async task queue for background processing."""
    
    def __init__(self, max_workers: int = 10):
        self.queue = asyncio.Queue()
        self.workers = []
        self.max_workers = max_workers
        self.running = False
        
    async def start(self):
        """Start background workers."""
        self.running = True
        
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_workers} background workers")
    
    async def stop(self):
        """Stop background workers."""
        self.running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("Stopped all background workers")
    
    async def enqueue(self, task: BackgroundTask):
        """Add task to queue."""
        await self.queue.put(task)
    
    async def _worker(self, worker_name: str):
        """Background worker that processes tasks."""
        logger.info(f"Background worker {worker_name} started")
        
        while self.running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                # Process task
                start_time = time.time()
                try:
                    await task.execute()
                    processing_time = time.time() - start_time
                    logger.debug(f"Worker {worker_name} completed task {task.id} in {processing_time:.2f}s")
                    
                except Exception as e:
                    logger.error(f"Worker {worker_name} task {task.id} failed: {e}")
                    
                finally:
                    self.queue.task_done()
                    
            except asyncio.TimeoutError:
                # No task available, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
```

---

## Troubleshooting & Diagnostics

### Diagnostic Tools

**System Health Checker:**

```python
class SystemDiagnostics:
    """Comprehensive system health and diagnostics."""
    
    def __init__(self):
        self.checks = [
            self._check_database,
            self._check_claude_integration,
            self._check_server_health,
            self._check_disk_space,
            self._check_memory_usage,
            self._check_network_connectivity
        ]
    
    async def run_full_diagnostic(self) -> DiagnosticReport:
        """Run all diagnostic checks."""
        report = DiagnosticReport(
            timestamp=datetime.utcnow(),
            checks=[]
        )
        
        for check in self.checks:
            try:
                check_result = await check()
                report.checks.append(check_result)
            except Exception as e:
                report.checks.append(DiagnosticCheck(
                    name=check.__name__,
                    status=CheckStatus.ERROR,
                    message=f"Diagnostic check failed: {e}",
                    details={"exception": str(e)}
                ))
        
        # Calculate overall health
        report.overall_status = self._calculate_overall_status(report.checks)
        
        return report
    
    async def _check_database(self) -> DiagnosticCheck:
        """Check database connectivity and performance."""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            db = DatabaseManager()
            await db.execute_query("SELECT 1")
            
            # Test query performance
            await db.execute_query("""
                SELECT COUNT(*) FROM usage_analytics 
                WHERE timestamp > NOW() - INTERVAL '1 day'
            """)
            
            query_time = (time.time() - start_time) * 1000
            
            status = CheckStatus.HEALTHY
            message = f"Database responsive ({query_time:.2f}ms)"
            
            if query_time > 1000:  # Slow queries
                status = CheckStatus.WARNING
                message = f"Database slow ({query_time:.2f}ms)"
            
            return DiagnosticCheck(
                name="database",
                status=status,
                message=message,
                details={
                    "query_time_ms": query_time,
                    "connection_pool": "healthy"
                }
            )
            
        except Exception as e:
            return DiagnosticCheck(
                name="database",
                status=CheckStatus.ERROR,
                message=f"Database error: {e}",
                details={"exception": str(e)}
            )
    
    async def _check_claude_integration(self) -> DiagnosticCheck:
        """Check Claude Code integration."""
        try:
            # Test claude command availability
            result = subprocess.run(['claude', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return DiagnosticCheck(
                    name="claude_integration",
                    status=CheckStatus.ERROR,
                    message="Claude CLI not available",
                    details={"error": result.stderr}
                )
            
            # Test MCP listing
            result = subprocess.run(['claude', 'mcp', 'list'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                servers = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
                return DiagnosticCheck(
                    name="claude_integration",
                    status=CheckStatus.HEALTHY,
                    message=f"Claude integration working ({servers} servers)",
                    details={
                        "claude_version": result.stdout.strip(),
                        "server_count": servers
                    }
                )
            else:
                return DiagnosticCheck(
                    name="claude_integration",
                    status=CheckStatus.WARNING,
                    message="Claude MCP command failed",
                    details={"error": result.stderr}
                )
                
        except Exception as e:
            return DiagnosticCheck(
                name="claude_integration",
                status=CheckStatus.ERROR,
                message=f"Claude integration error: {e}",
                details={"exception": str(e)}
            )
```

### Log Analysis Tools

**Log Analyzer:**

```python
class LogAnalyzer:
    """Analyze logs for common issues and patterns."""
    
    def __init__(self, log_file_path: str):
        self.log_file = Path(log_file_path)
        self.patterns = {
            'errors': [
                r'ERROR.*?(?P<error_msg>.*)',
                r'CRITICAL.*?(?P<error_msg>.*)',
                r'Failed to.*?(?P<error_msg>.*)'
            ],
            'performance': [
                r'slow query.*?(?P<duration>\d+)ms',
                r'request timeout.*?(?P<timeout>\d+)s',
                r'high memory usage.*?(?P<memory>\d+)%'
            ],
            'authentication': [
                r'authentication failed.*?(?P<user>.*)',
                r'invalid token.*?(?P<token>.*)',
                r'rate limit exceeded.*?(?P<client>.*)'
            ]
        }
    
    def analyze_recent_logs(self, lines: int = 1000) -> LogAnalysisReport:
        """Analyze recent log entries."""
        
        if not self.log_file.exists():
            return LogAnalysisReport(
                error="Log file not found",
                analyzed_lines=0
            )
        
        issues = []
        line_count = 0
        
        try:
            # Read last N lines efficiently
            with open(self.log_file, 'r') as f:
                # Get file size
                f.seek(0, 2)
                file_size = f.tell()
                
                # Read from end
                lines_found = []
                buffer = ""
                f.seek(max(0, file_size - 8192))  # Start 8KB from end
                
                for line in f:
                    lines_found.append(line.strip())
                
                # Keep only last N lines
                recent_lines = lines_found[-lines:]
                line_count = len(recent_lines)
                
                # Analyze each line
                for line_num, line in enumerate(recent_lines):
                    for category, patterns in self.patterns.items():
                        for pattern in patterns:
                            match = re.search(pattern, line, re.IGNORECASE)
                            if match:
                                issues.append(LogIssue(
                                    line_number=line_num + 1,
                                    category=category,
                                    message=line,
                                    details=match.groupdict(),
                                    timestamp=self._extract_timestamp(line)
                                ))
        
        except Exception as e:
            return LogAnalysisReport(
                error=f"Failed to analyze logs: {e}",
                analyzed_lines=0
            )
        
        # Generate summary
        summary = self._generate_summary(issues)
        
        return LogAnalysisReport(
            analyzed_lines=line_count,
            issues=issues,
            summary=summary,
            recommendations=self._generate_recommendations(issues)
        )
```

### Performance Profiling

**Performance Profiler:**

```python
class PerformanceProfiler:
    """Profile application performance and identify bottlenecks."""
    
    def __init__(self):
        self.profiles = {}
        self.active_profiles = {}
    
    def start_profile(self, profile_name: str):
        """Start performance profiling."""
        
        # CPU profiling
        cpu_profiler = cProfile.Profile()
        cpu_profiler.enable()
        
        # Memory profiling
        memory_profiler = tracemalloc.start()
        
        self.active_profiles[profile_name] = {
            'cpu': cpu_profiler,
            'memory': memory_profiler,
            'start_time': time.time(),
            'start_memory': psutil.Process().memory_info().rss
        }
        
        logger.info(f"Started profiling: {profile_name}")
    
    def stop_profile(self, profile_name: str) -> PerformanceProfile:
        """Stop profiling and generate report."""
        
        if profile_name not in self.active_profiles:
            raise ValueError(f"No active profile: {profile_name}")
        
        profile_data = self.active_profiles[profile_name]
        
        # Stop CPU profiling
        cpu_profiler = profile_data['cpu']
        cpu_profiler.disable()
        
        # Stop memory profiling
        tracemalloc.stop()
        
        # Calculate metrics
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss
        
        duration = end_time - profile_data['start_time']
        memory_delta = end_memory - profile_data['start_memory']
        
        # Generate CPU profile stats
        cpu_stats = io.StringIO()
        ps = pstats.Stats(cpu_profiler, stream=cpu_stats)
        ps.sort_stats('cumulative').print_stats(20)
        
        # Create performance report
        performance_profile = PerformanceProfile(
            name=profile_name,
            duration_seconds=duration,
            memory_delta_bytes=memory_delta,
            cpu_profile=cpu_stats.getvalue(),
            timestamp=datetime.utcnow()
        )
        
        # Store profile
        self.profiles[profile_name] = performance_profile
        
        # Cleanup
        del self.active_profiles[profile_name]
        
        logger.info(f"Completed profiling: {profile_name} "
                   f"(duration: {duration:.2f}s, memory: {memory_delta/1024/1024:.2f}MB)")
        
        return performance_profile
```

---

## Production Deployment

### Docker Deployment

**Dockerfile:**

```dockerfile
# Multi-stage Dockerfile for production deployment
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt requirements-prod.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY . .

# Install application
RUN pip install -e .

# Production stage
FROM python:3.11-slim as production

# Create non-root user
RUN groupadd -r mcpmanager && useradd -r -g mcpmanager mcpmanager

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Create data directories
RUN mkdir -p /data /config /logs && \
    chown -R mcpmanager:mcpmanager /data /config /logs /app

# Switch to non-root user
USER mcpmanager

# Expose ports
EXPOSE 8000 3001 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["mcp-manager", "api", "start", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose:**

```yaml
# docker-compose.yml for production deployment
version: '3.8'

services:
  mcp-manager-api:
    build: .
    container_name: mcp-manager-api
    restart: unless-stopped
    environment:
      - MCP_CONFIG_PATH=/config/config.toml
      - MCP_DATABASE_URL=postgresql://mcpuser:${POSTGRES_PASSWORD}@postgres:5432/mcpmanager
      - MCP_REDIS_URL=redis://redis:6379/0
      - MCP_JWT_SECRET=${JWT_SECRET}
      - MCP_LOG_LEVEL=INFO
    ports:
      - "8000:8000"
    volumes:
      - ./config:/config:ro
      - mcp-data:/data
      - mcp-logs:/logs
    depends_on:
      - postgres
      - redis
    networks:
      - mcp-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  mcp-manager-proxy:
    build: .
    container_name: mcp-manager-proxy
    restart: unless-stopped
    command: ["mcp-manager", "proxy", "start", "--host", "0.0.0.0", "--port", "3001", "--config", "/config/proxy.json"]
    environment:
      - MCP_CONFIG_PATH=/config/config.toml
      - MCP_LOG_LEVEL=INFO
    ports:
      - "3001:3001"
    volumes:
      - ./config:/config:ro
      - mcp-logs:/logs
    networks:
      - mcp-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:15-alpine
    container_name: mcp-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=mcpmanager
      - POSTGRES_USER=mcpuser
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d:ro
    networks:
      - mcp-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mcpuser -d mcpmanager"]
      interval: 30s
      timeout: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: mcp-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis-data:/data
    networks:
      - mcp-network
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: mcp-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - mcp-logs:/var/log/nginx
    depends_on:
      - mcp-manager-api
      - mcp-manager-proxy
    networks:
      - mcp-network

  prometheus:
    image: prom/prometheus:latest
    container_name: mcp-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - mcp-network

  grafana:
    image: grafana/grafana:latest
    container_name: mcp-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
    networks:
      - mcp-network

volumes:
  mcp-data:
  mcp-logs:
  postgres-data:
  redis-data:
  prometheus-data:
  grafana-data:

networks:
  mcp-network:
    driver: bridge
```

### Kubernetes Deployment

**Kubernetes Manifests:**

```yaml
# mcp-manager-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mcp-manager
  labels:
    name: mcp-manager

---
# mcp-manager-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-manager-config
  namespace: mcp-manager
data:
  config.toml: |
    [general]
    environment = "production"
    debug = false

    [api]
    enabled = true
    host = "0.0.0.0"
    port = 8000
    workers = 4

    [database]
    url = "postgresql://mcpuser:${POSTGRES_PASSWORD}@postgres:5432/mcpmanager"

    [security]
    rate_limiting = true
    audit_logging = true

---
# mcp-manager-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-manager-api
  namespace: mcp-manager
  labels:
    app: mcp-manager-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-manager-api
  template:
    metadata:
      labels:
        app: mcp-manager-api
    spec:
      containers:
      - name: mcp-manager-api
        image: mcpmanager/mcp-manager:latest
        ports:
        - containerPort: 8000
        env:
        - name: MCP_CONFIG_PATH
          value: "/config/config.toml"
        - name: MCP_JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: mcp-manager-secrets
              key: jwt-secret
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mcp-manager-secrets
              key: postgres-password
        volumeMounts:
        - name: config
          mountPath: /config
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: mcp-manager-config

---
# mcp-manager-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: mcp-manager-api
  namespace: mcp-manager
spec:
  selector:
    app: mcp-manager-api
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  type: ClusterIP

---
# mcp-manager-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-manager-ingress
  namespace: mcp-manager
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - mcp.yourdomain.com
    secretName: mcp-manager-tls
  rules:
  - host: mcp.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mcp-manager-api
            port:
              number: 8000
```

### Monitoring & Alerting

**Prometheus Configuration:**

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "mcp_manager_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'mcp-manager-api'
    static_configs:
      - targets: ['mcp-manager-api:9090']
    metrics_path: /metrics
    scrape_interval: 30s

  - job_name: 'mcp-manager-proxy'
    static_configs:
      - targets: ['mcp-manager-proxy:9091']
    metrics_path: /metrics
    scrape_interval: 30s
```

**Alert Rules:**

```yaml
# mcp_manager_rules.yml
groups:
- name: mcp_manager_alerts
  rules:
  - alert: MCPManagerAPIDown
    expr: up{job="mcp-manager-api"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "MCP Manager API is down"
      description: "MCP Manager API has been down for more than 2 minutes."

  - alert: HighErrorRate
    expr: rate(mcp_api_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} requests per second."

  - alert: HighResponseTime
    expr: histogram_quantile(0.95, rate(mcp_api_request_duration_seconds_bucket[5m])) > 2
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High response time"
      description: "95th percentile response time is {{ $value }} seconds."

  - alert: DatabaseConnectionsFull
    expr: mcp_database_connections_active / mcp_database_connections_max > 0.9
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Database connection pool nearly full"
      description: "Database connection pool is {{ $value | humanizePercentage }} full."
```

---

## Development & Extension

### Plugin Architecture

**Plugin Interface:**

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class MCPManagerPlugin(ABC):
    """Base class for MCP Manager plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize plugin with configuration."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass

class DiscoveryPlugin(MCPManagerPlugin):
    """Plugin for custom server discovery sources."""
    
    @abstractmethod
    async def discover_servers(self, query: str = "") -> List[Dict[str, Any]]:
        """Discover servers from custom source."""
        pass
    
    @abstractmethod
    def get_source_info(self) -> Dict[str, str]:
        """Get information about the discovery source."""
        pass

class AnalyticsPlugin(MCPManagerPlugin):
    """Plugin for custom analytics and metrics."""
    
    @abstractmethod
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect custom metrics."""
        pass
    
    @abstractmethod
    async def generate_report(self, timeframe: str) -> Dict[str, Any]:
        """Generate custom analytics report."""
        pass
```

**Example Plugin Implementation:**

```python
class GitHubDiscoveryPlugin(DiscoveryPlugin):
    """Discover MCP servers from GitHub repositories."""
    
    @property
    def name(self) -> str:
        return "github-discovery"
    
    @property  
    def version(self) -> str:
        return "1.0.0"
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize GitHub API client."""
        self.github_token = config.get("github_token")
        self.search_topics = config.get("search_topics", ["mcp-server", "model-context-protocol"])
        self.client = aiohttp.ClientSession(
            headers={"Authorization": f"token {self.github_token}"}
        )
    
    async def cleanup(self) -> None:
        """Cleanup HTTP client."""
        if self.client:
            await self.client.close()
    
    async def discover_servers(self, query: str = "") -> List[Dict[str, Any]]:
        """Discover MCP servers from GitHub."""
        servers = []
        
        for topic in self.search_topics:
            search_query = f"topic:{topic}"
            if query:
                search_query += f" {query}"
            
            # Search GitHub repositories
            async with self.client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": search_query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 50
                }
            ) as response:
                data = await response.json()
                
                for repo in data.get("items", []):
                    # Parse repository information
                    server = await self._parse_repository(repo)
                    if server:
                        servers.append(server)
        
        return servers
    
    async def _parse_repository(self, repo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse GitHub repository into server format."""
        
        # Check for package.json or Dockerfile
        has_package = await self._check_file_exists(repo["full_name"], "package.json")
        has_dockerfile = await self._check_file_exists(repo["full_name"], "Dockerfile")
        
        if not (has_package or has_dockerfile):
            return None
        
        return {
            "install_id": f"github-{repo['name']}",
            "name": repo["name"],
            "type": "docker" if has_dockerfile else "npm",
            "description": repo["description"] or "MCP server from GitHub",
            "source": "github",
            "url": repo["html_url"],
            "clone_url": repo["clone_url"],
            "stars": repo["stargazers_count"],
            "quality_score": min(10.0, repo["stargazers_count"] / 10.0),
            "last_updated": repo["updated_at"],
            "language": repo["language"],
            "topics": repo.get("topics", [])
        }
```

### Custom CLI Commands

**Command Plugin System:**

```python
class CLICommandPlugin(MCPManagerPlugin):
    """Plugin for adding custom CLI commands."""
    
    @abstractmethod
    def get_commands(self) -> List[click.Command]:
        """Return list of Click commands to add."""
        pass

class CustomToolsPlugin(CLICommandPlugin):
    """Example plugin adding custom tool management commands."""
    
    @property
    def name(self) -> str:
        return "custom-tools"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize plugin."""
        self.tools_directory = Path(config.get("tools_directory", "./custom-tools"))
        self.tools_directory.mkdir(exist_ok=True)
    
    async def cleanup(self) -> None:
        """Cleanup plugin."""
        pass
    
    def get_commands(self) -> List[click.Command]:
        """Return custom commands."""
        return [self._create_tool_command()]
    
    def _create_tool_command(self) -> click.Group:
        """Create custom tool management command group."""
        
        @click.group("custom-tools")
        def custom_tools():
            """Manage custom MCP tools."""
            pass
        
        @custom_tools.command("create")
        @click.argument("tool_name")
        @click.option("--template", help="Tool template to use")
        def create_tool(tool_name: str, template: Optional[str]):
            """Create a new custom MCP tool."""
            
            template_content = self._get_template(template or "basic")
            tool_file = self.tools_directory / f"{tool_name}.py"
            
            with open(tool_file, 'w') as f:
                f.write(template_content.format(tool_name=tool_name))
            
            click.echo(f"Created custom tool: {tool_file}")
        
        @custom_tools.command("list")
        def list_tools():
            """List custom tools."""
            tools = list(self.tools_directory.glob("*.py"))
            
            if tools:
                click.echo("Custom tools:")
                for tool in tools:
                    click.echo(f"  - {tool.stem}")
            else:
                click.echo("No custom tools found")
        
        return custom_tools
```

### API Extensions

**Custom API Endpoints:**

```python
class APIExtensionPlugin(MCPManagerPlugin):
    """Plugin for adding custom API endpoints."""
    
    @abstractmethod
    def get_routes(self) -> List[Tuple[str, str, Callable]]:
        """Return list of (method, path, handler) tuples."""
        pass
    
    @abstractmethod
    def get_middleware(self) -> List[Callable]:
        """Return list of middleware functions."""
        pass

class CustomAnalyticsPlugin(APIExtensionPlugin):
    """Plugin adding custom analytics endpoints."""
    
    @property
    def name(self) -> str:
        return "custom-analytics"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize plugin."""
        self.analytics_db = AnalyticsDatabase(config["analytics_db_url"])
    
    async def cleanup(self) -> None:
        """Cleanup plugin."""
        await self.analytics_db.close()
    
    def get_routes(self) -> List[Tuple[str, str, Callable]]:
        """Return custom API routes."""
        return [
            ("GET", "/custom/analytics/heatmap", self._get_usage_heatmap),
            ("GET", "/custom/analytics/trends", self._get_usage_trends),
            ("POST", "/custom/analytics/export", self._export_custom_data)
        ]
    
    def get_middleware(self) -> List[Callable]:
        """Return middleware functions."""
        return [self._analytics_middleware]
    
    async def _get_usage_heatmap(self, request: Request) -> Response:
        """Get usage heatmap data."""
        
        # Extract parameters
        days = int(request.query_params.get("days", 30))
        granularity = request.query_params.get("granularity", "hour")
        
        # Query analytics database
        heatmap_data = await self.analytics_db.get_usage_heatmap(days, granularity)
        
        return JSONResponse({
            "success": True,
            "data": heatmap_data,
            "metadata": {
                "days": days,
                "granularity": granularity,
                "generated_at": datetime.utcnow().isoformat()
            }
        })
    
    async def _analytics_middleware(self, request: Request, call_next):
        """Custom analytics middleware."""
        
        # Track API usage
        start_time = time.time()
        
        response = await call_next(request)
        
        # Record metrics
        processing_time = time.time() - start_time
        await self.analytics_db.record_api_usage(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            processing_time=processing_time
        )
        
        return response
```

---

**🎉 Complete Admin Guide for MCP Manager v2.0**

This comprehensive admin guide covers all aspects of MCP Manager administration, from basic concepts to advanced deployment scenarios. The guide provides:

- **Architectural Understanding** - Deep dive into system design and components
- **Configuration Management** - Complete configuration reference and best practices
- **Security Implementation** - Authentication, authorization, and security hardening
- **Performance Optimization** - Database tuning, caching, and async processing
- **Production Deployment** - Docker, Kubernetes, and monitoring setup
- **Troubleshooting Tools** - Diagnostics, log analysis, and performance profiling
- **Extensibility** - Plugin system and custom development

For user-facing features and day-to-day usage, refer to the [User Guide](USER_GUIDE.md).

*This admin guide covers all administrative aspects of MCP Manager v2.0. For the latest updates and community contributions, visit the project repository.*