# MCP Manager CLI Reference

Complete documentation for all CLI commands, subcommands, and API endpoints.

## Table of Contents

1. [Core Commands](#core-commands)
2. [Discovery Commands](#discovery-commands)
3. [Suite Management](#suite-management)
4. [AI/Analytics Commands](#aianalytics-commands)
5. [System Commands](#system-commands)
6. [TUI/Interface Commands](#tuiinterface-commands)
7. [Monitoring Commands](#monitoring-commands)
8. [API Commands](#api-commands)
9. [Advanced/Workflow Commands](#advancedworkflow-commands)
10. [Test Admin Commands](#test-admin-commands)
11. [API Endpoints](#api-endpoints)

---

## Core Commands

### `mcp-manager`
Main CLI entry point. When called without arguments, launches interactive menu.

**Options:**
- `--debug, -d`: Enable debug logging
- `--verbose, -v`: Enable verbose output
- `--config-dir`: Configuration directory path
- `--menu, -m`: Launch interactive menu
- `--version`: Show version information

**Example:**
```bash
mcp-manager --debug --menu
```

### `mcp-manager list`
List configured MCP servers.

**Options:**
- `--scope, -s`: Filter by scope (`user`, `project`)
- `--output-format, -o`: Output format (`table`, `json`)

**Examples:**
```bash
mcp-manager list
mcp-manager list --scope user --output-format json
```

### `mcp-manager add`
Add a new MCP server.

**Options:**
- `--type`: Server type (custom, npm, docker_desktop, docker_hub)
- `--command, -c`: Server command
- `--args, -a`: Command arguments (multiple)
- `--env, -e`: Environment variables as KEY=VALUE (multiple)
- `--scope`: Installation scope (user, project)
- `--working-dir`: Working directory for the server
- `--description`: Server description

**Examples:**
```bash
mcp-manager add my-server --type custom --command "node" --args "server.js" --scope user
mcp-manager add filesystem --type npm --command "npx" --args "@modelcontextprotocol/server-filesystem" --args "/path/to/directory"
```

### `mcp-manager remove`
Remove an MCP server.

**Options:**
- `--scope`: Server scope
- `--force, -f`: Skip confirmation prompt

**Examples:**
```bash
mcp-manager remove my-server
mcp-manager remove filesystem --force
```

### `mcp-manager enable`
Enable an MCP server.

**Example:**
```bash
mcp-manager enable filesystem
```

### `mcp-manager disable`
Disable an MCP server.

**Example:**
```bash
mcp-manager disable filesystem
```

### `mcp-manager nuke`
Remove ALL MCP servers (nuclear option) - Fast config reset.

**Options:**
- `--force, -f`: Skip confirmation prompt

**Example:**
```bash
mcp-manager nuke --force
```

---

## Discovery Commands

### `mcp-manager discover`
Discover available MCP servers from multiple sources.

**Options:**
- `--query, -q`: Search query
- `--type, -t`: Filter by server type
- `--limit, -l`: Limit number of results
- `--update-catalog`: Update discovery catalogs
- `--format`: Output format (table, json)

**Examples:**
```bash
mcp-manager discover
mcp-manager discover --query filesystem --limit 5
mcp-manager discover --type npm --update-catalog
```

### `mcp-manager install-package`
Install an MCP server package by install ID.

**Options:**
- `--force, -f`: Force installation even if server exists
- `--scope`: Installation scope (user, project)
- `--dry-run`: Show what would be installed without installing

**Examples:**
```bash
mcp-manager install-package modelcontextprotocol-filesystem
mcp-manager install-package dd-SQLite --force
mcp-manager install-package playwright --scope project --dry-run
```

### `mcp-manager cleanup`
Fix broken MCP configurations and sync state.

**Example:**
```bash
mcp-manager cleanup
```

---

## Suite Management

### `mcp-manager install-suite-temp`
Install MCP servers tagged with a specific suite name.

**Options:**
- `--force, -f`: Skip confirmation prompts
- `--dry-run`: Show what would be installed without installing

**Examples:**
```bash
mcp-manager install-suite-temp working-servers
mcp-manager install-suite-temp test --dry-run
```

### `mcp-manager suite`
Manage MCP server suites for task-specific configurations.

#### `mcp-manager suite list`
List all MCP server suites.

**Options:**
- `--category`: Filter by category

**Examples:**
```bash
mcp-manager suite list
mcp-manager suite list --category development
```

#### `mcp-manager suite create`
Create a new MCP server suite.

**Options:**
- `--description`: Suite description
- `--category`: Suite category
- `--suite-id`: Custom suite ID (auto-generated if not provided)

**Examples:**
```bash
mcp-manager suite create "Development Tools" --description "Essential development servers" --category dev
mcp-manager suite create "AI Tools" --suite-id ai-suite
```

#### `mcp-manager suite add`
Add a server to a suite.

**Options:**
- `--role`: Server role in suite (member, primary, optional)
- `--priority`: Priority (0-100, higher = more important)

**Examples:**
```bash
mcp-manager suite add dev-suite filesystem --role primary --priority 90
mcp-manager suite add ai-suite claude-3 --role member --priority 50
```

#### `mcp-manager suite remove`
Remove a server from a suite.

**Example:**
```bash
mcp-manager suite remove dev-suite filesystem
```

#### `mcp-manager suite delete`
Delete a suite and all its memberships.

**Options:**
- `--force, -f`: Skip confirmation prompt

**Examples:**
```bash
mcp-manager suite delete old-suite
mcp-manager suite delete test-suite --force
```

#### `mcp-manager suite show`
Show detailed information about a specific suite.

**Example:**
```bash
mcp-manager suite show working-servers
```

#### `mcp-manager suite summary`
Show summary statistics about suites.

**Example:**
```bash
mcp-manager suite summary
```

#### `mcp-manager suite remove-suite`
Remove all servers from a suite while keeping the suite definition.

**Options:**
- `--force, -f`: Skip confirmation prompt

**Example:**
```bash
mcp-manager suite remove-suite working-servers --force
```

---

## AI/Analytics Commands

### `mcp-manager ai`
AI curation and recommendation system.

#### `mcp-manager ai setup`
Setup AI curation system with OpenAI API key.

**Options:**
- `--api-key`: OpenAI API key
- `--model`: OpenAI model (default: gpt-4)
- `--temperature`: Model temperature (0.0-1.0)

**Examples:**
```bash
mcp-manager ai setup --api-key sk-xxx --model gpt-4-turbo
mcp-manager ai setup --temperature 0.7
```

#### `mcp-manager ai status`
Show AI curation system status.

**Example:**
```bash
mcp-manager ai status
```

#### `mcp-manager ai test`
Test AI curation system.

**Example:**
```bash
mcp-manager ai test
```

#### `mcp-manager ai remove`
Remove AI curation configuration.

**Example:**
```bash
mcp-manager ai remove
```

#### `mcp-manager ai curate`
Run AI curation on discovered servers.

**Options:**
- `--query`: Search query for curation
- `--limit`: Limit number of servers to curate

**Examples:**
```bash
mcp-manager ai curate --query "development tools"
mcp-manager ai curate --limit 10
```

### `mcp-manager analytics`
Usage analytics and insights.

#### `mcp-manager analytics summary`
Show usage analytics summary.

**Example:**
```bash
mcp-manager analytics summary
```

#### `mcp-manager analytics query`
Query analytics with filters.

**Options:**
- `--category`: Analytics category
- `--days`: Number of days to analyze
- `--format`: Output format

**Examples:**
```bash
mcp-manager analytics query --category usage --days 30
mcp-manager analytics query --format json
```

---

## System Commands

### `mcp-manager system-info`
Show comprehensive system information.

**Example:**
```bash
mcp-manager system-info
```

### `mcp-manager config`
Show current configuration.

**Example:**
```bash
mcp-manager config
```

### `mcp-manager check-sync`
Check synchronization between MCP Manager and Claude Code.

**Example:**
```bash
mcp-manager check-sync
```

### `mcp-manager server-details`
Show detailed information about a specific server.

**Example:**
```bash
mcp-manager server-details filesystem
```

---

## TUI/Interface Commands

### `mcp-manager tui`
Launch terminal user interface.

**Example:**
```bash
mcp-manager tui
```

### `mcp-manager tui-simple`
Launch simple terminal interface.

**Example:**
```bash
mcp-manager tui-simple
```

### `mcp-manager tui-textual`
Launch advanced Textual-based TUI.

**Example:**
```bash
mcp-manager tui-textual
```

---

## Monitoring Commands

### `mcp-manager monitor-status`
Show monitoring system status.

**Example:**
```bash
mcp-manager monitor-status
```

### `mcp-manager mode`
Switch between different operational modes.

#### `mcp-manager mode status`
Show current operational mode.

**Example:**
```bash
mcp-manager mode status
```

#### `mcp-manager mode switch`
Switch operational mode.

**Options:**
- `--mode`: Target mode (development, production, testing)

**Example:**
```bash
mcp-manager mode switch --mode production
```

### `mcp-manager proxy`
MCP proxy management.

#### `mcp-manager proxy start`
Start MCP proxy server.

**Options:**
- `--port`: Proxy port
- `--host`: Proxy host

**Example:**
```bash
mcp-manager proxy start --port 8080 --host 0.0.0.0
```

#### `mcp-manager proxy status`
Show proxy status.

**Example:**
```bash
mcp-manager proxy status
```

#### `mcp-manager proxy stats`
Show proxy statistics.

**Example:**
```bash
mcp-manager proxy stats
```

#### `mcp-manager proxy add-server`
Add server to proxy.

**Example:**
```bash
mcp-manager proxy add-server filesystem
```

#### `mcp-manager proxy remove-server`
Remove server from proxy.

**Example:**
```bash
mcp-manager proxy remove-server filesystem
```

#### `mcp-manager proxy test`
Test proxy functionality.

**Example:**
```bash
mcp-manager proxy test
```

#### `mcp-manager proxy config`
Show proxy configuration.

**Example:**
```bash
mcp-manager proxy config
```

---

## API Commands

### `mcp-manager api`
API server management.

#### `mcp-manager api start`
Start API server.

**Options:**
- `--host`: Server host
- `--port`: Server port

**Example:**
```bash
mcp-manager api start --host 0.0.0.0 --port 8000
```

#### `mcp-manager api stop`
Stop API server.

**Example:**
```bash
mcp-manager api stop
```

#### `mcp-manager api status`
Show API server status.

**Example:**
```bash
mcp-manager api status
```

#### `mcp-manager api test`
Test API endpoints.

**Example:**
```bash
mcp-manager api test
```

#### `mcp-manager api create-key`
Create API authentication key.

**Options:**
- `--name`: Key name
- `--scopes`: Key scopes (multiple)
- `--expires-days`: Expiration in days

**Example:**
```bash
mcp-manager api create-key --name "dev-key" --scopes "servers:read" --scopes "analytics:read" --expires-days 30
```

---

## Advanced/Workflow Commands

### `mcp-manager workflow`
Workflow management for complex operations.

#### `mcp-manager workflow list`
List available workflows.

**Example:**
```bash
mcp-manager workflow list
```

#### `mcp-manager workflow create`
Create a new workflow.

**Options:**
- `--description`: Workflow description
- `--template`: Use template

**Example:**
```bash
mcp-manager workflow create development-setup --description "Setup development environment" --template dev
```

#### `mcp-manager workflow activate`
Activate a workflow.

**Example:**
```bash
mcp-manager workflow activate development-setup
```

#### `mcp-manager workflow deactivate`
Deactivate current workflow.

**Example:**
```bash
mcp-manager workflow deactivate
```

#### `mcp-manager workflow switch`
Switch to different workflow.

**Example:**
```bash
mcp-manager workflow switch production-setup
```

#### `mcp-manager workflow show`
Show workflow details.

**Example:**
```bash
mcp-manager workflow show development-setup
```

#### `mcp-manager workflow delete`
Delete a workflow.

**Options:**
- `--force, -f`: Skip confirmation

**Example:**
```bash
mcp-manager workflow delete old-workflow --force
```

#### `mcp-manager workflow status`
Show workflow system status.

**Example:**
```bash
mcp-manager workflow status
```

#### `mcp-manager workflow template`
Manage workflow templates.

**Example:**
```bash
mcp-manager workflow template
```

### `mcp-manager tools`
Tool registry and search functionality.

#### `mcp-manager tools search`
Search for tools in the registry.

**Options:**
- `--category`: Tool category
- `--tags`: Filter by tags
- `--limit`: Limit results

**Examples:**
```bash
mcp-manager tools search --category "file-system"
mcp-manager tools search --tags "development" --limit 10
```

#### `mcp-manager tools list`
List all tools in registry.

**Options:**
- `--category`: Filter by category

**Example:**
```bash
mcp-manager tools list --category "ai"
```

### `mcp-manager quality`
Quality assurance and server ranking.

#### `mcp-manager quality status`
Show quality system status.

**Example:**
```bash
mcp-manager quality status
```

#### `mcp-manager quality rankings`
Show server quality rankings.

**Example:**
```bash
mcp-manager quality rankings
```

#### `mcp-manager quality feedback`
Submit quality feedback.

**Example:**
```bash
mcp-manager quality feedback
```

#### `mcp-manager quality report`
Generate quality report.

**Example:**
```bash
mcp-manager quality report
```

#### `mcp-manager quality cleanup`
Clean up quality data.

**Example:**
```bash
mcp-manager quality cleanup
```

---

## Test Admin Commands

### `mcp-manager test-admin`
Administrative testing commands.

#### `mcp-manager test-admin create-test-data`
Create test data for development.

**Example:**
```bash
mcp-manager test-admin create-test-data
```

#### `mcp-manager test-admin run-stress-test`
Run system stress test.

**Example:**
```bash
mcp-manager test-admin run-stress-test
```

#### `mcp-manager test-admin validate-config`
Validate system configuration.

**Example:**
```bash
mcp-manager test-admin validate-config
```

#### `mcp-manager test-admin benchmark`
Run performance benchmarks.

**Example:**
```bash
mcp-manager test-admin benchmark
```

#### `mcp-manager test-admin generate-report`
Generate system report.

**Example:**
```bash
mcp-manager test-admin generate-report
```

#### `mcp-manager test-admin reset-test-env`
Reset test environment.

**Example:**
```bash
mcp-manager test-admin reset-test-env
```

#### `mcp-manager test-admin load-test-suite`
Load comprehensive test suite.

**Example:**
```bash
mcp-manager test-admin load-test-suite
```

---

## API Endpoints

The MCP Manager provides a comprehensive REST API with the following endpoints:

### Base URL
```
http://127.0.0.1:8000
```

### Authentication

All API endpoints (except `/health`) require authentication via:
1. API Key + JWT Token workflow
2. Bearer token in Authorization header

#### Create Authentication Token
```http
POST /auth/token
Content-Type: application/json

{
  "api_key": "your-api-key",
  "scope": ["servers:read", "analytics:read"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Token created",
  "token": "jwt-token-here",
  "expires_in": 86400,
  "scope": ["servers:read", "analytics:read"]
}
```

### Health & Status

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

### Server Management

#### List Servers
```http
GET /servers?status=enabled&server_type=npm
Authorization: Bearer <jwt-token>
```

**Query Parameters:**
- `status`: Filter by status (enabled, disabled)
- `server_type`: Filter by type (npm, docker_desktop, custom, docker_hub)

**Response:**
```json
{
  "success": true,
  "message": "Servers retrieved",
  "data": {
    "servers": [
      {
        "name": "filesystem",
        "type": "npm",
        "enabled": true,
        "description": "File system operations",
        "command": "npx",
        "args": ["@modelcontextprotocol/server-filesystem"]
      }
    ],
    "total": 1,
    "enabled": 1,
    "disabled": 0
  }
}
```

### Analytics

#### Query Analytics Data
```http
POST /analytics/query
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "category": "usage_summary",
  "time_range": "30d",
  "filters": {
    "server_type": "npm"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Analytics data retrieved",
  "data": {
    "category": "usage_summary",
    "results": [
      {
        "metric": "total_servers",
        "value": 15,
        "change": "+3"
      }
    ]
  }
}
```

#### Get Analytics Categories
```http
GET /analytics/categories
Authorization: Bearer <jwt-token>
```

**Response:**
```json
{
  "success": true,
  "message": "Analytics categories retrieved",
  "data": {
    "categories": [
      "usage_summary",
      "tool_usage", 
      "server_analytics",
      "recommendations",
      "api_usage",
      "trending_queries",
      "performance_metrics"
    ]
  }
}
```

### Tools

#### Search Tools
```http
POST /tools/search
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "query": "filesystem",
  "category": "file-operations",
  "limit": 10,
  "filters": {
    "type": "npm"
  }
}
```

#### Get Tool Categories
```http
GET /tools/categories
Authorization: Bearer <jwt-token>
```

### Data Export

#### Export Data
```http
POST /export
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "format": "json",
  "data_types": ["servers", "analytics", "suites"],
  "time_range": "30d"
}
```

### Admin Endpoints

#### List API Keys (Admin Only)
```http
GET /admin/api-keys
Authorization: Bearer <admin-jwt-token>
```

#### Create API Key (Admin Only)
```http
POST /admin/api-keys
Authorization: Bearer <admin-jwt-token>
Content-Type: application/json

{
  "name": "development-key",
  "scopes": ["servers:read", "analytics:read"],
  "expires_days": 30
}
```

#### Get API Statistics
```http
GET /admin/stats
Authorization: Bearer <jwt-token>
```

### Error Responses

All endpoints return consistent error responses:

```json
{
  "success": false,
  "message": "Error description",
  "error_code": "VALIDATION_ERROR",
  "details": {
    "field": "validation details"
  }
}
```

### Rate Limiting

- **Per Minute**: 60 requests
- **Per Hour**: 1000 requests

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1640995200
```

### Authentication Scopes

Available permission scopes:
- `servers:read` - Read server information
- `servers:write` - Modify servers
- `analytics:read` - Read analytics data
- `analytics:export` - Export analytics data
- `tools:read` - Search and read tools
- `admin:full` - Full administrative access

---

## Common Usage Patterns

### Quick Setup
```bash
# Discover and install essential servers
mcp-manager discover --query filesystem --limit 5
mcp-manager install-package modelcontextprotocol-filesystem

# Install a working suite
mcp-manager install-suite-temp working-servers

# Check status
mcp-manager list
```

### Development Workflow
```bash
# Create development workflow
mcp-manager workflow create dev-env --template development

# Setup AI assistance
mcp-manager ai setup --api-key sk-xxx

# Create custom suite
mcp-manager suite create "My Dev Tools" --category development
mcp-manager suite add my-dev-tools filesystem --role primary
```

### API Usage
```bash
# Start API server
mcp-manager api start --port 8000

# Create API key
mcp-manager api create-key --name "cli-key" --scopes "servers:read"

# Test API
curl -H "Authorization: Bearer <token>" http://localhost:8000/servers
```

---

## Configuration Files

### User Configuration
`~/.config/mcp-manager/config.toml`

### Project Configuration  
`./.mcp-manager.toml`

### Claude Code Integration
- `~/.claude.json` (Claude Code internal state)
- `~/.config/claude-code/mcp-servers.json` (User overrides)
- `./.mcp.json` (Project-specific config)

---

For the most up-to-date information, use `mcp-manager --help` or `mcp-manager <command> --help` for specific command details.