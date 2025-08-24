# MCP Manager User Guide

**Version 2.0** | **Enterprise-Grade MCP Server Management**

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Installation & Setup](#installation--setup)
3. [Core Features](#core-features)
4. [Server Management](#server-management)
5. [Suite-Based Organization](#suite-based-organization)
6. [Workflow Automation](#workflow-automation)
7. [Analytics & Monitoring](#analytics--monitoring)
8. [API Server](#api-server)
9. [Proxy Server](#proxy-server)
10. [Terminal User Interface](#terminal-user-interface)
11. [Command Reference](#command-reference)
12. [Troubleshooting](#troubleshooting)
13. [Best Practices](#best-practices)

---

## Getting Started

### What is MCP Manager?

MCP Manager is an enterprise-grade tool for managing **Model Context Protocol (MCP) servers** used by Claude Code. It provides a complete ecosystem for MCP server lifecycle management with advanced features:

- **🔍 Intelligent Discovery** - Multi-source server discovery with AI curation
- **🎯 Suite Management** - Organized collections of servers for specific workflows
- **⚡ Workflow Automation** - Task-specific configurations with AI recommendations
- **📊 Advanced Analytics** - Comprehensive usage tracking and performance insights
- **🔄 Proxy Server** - Unified endpoint with protocol translation and load balancing
- **🌐 REST API** - Full API server with authentication and rate limiting
- **🎨 Rich Interfaces** - Modern CLI, TUI, and web dashboard options

### New in Version 2.0

- **Task-Specific Workflows** - AI-driven workflow recommendations
- **MCP Proxy Server** - Protocol translation and unified endpoints
- **REST API Server** - Complete API with JWT authentication
- **Advanced Analytics** - Usage patterns and performance metrics
- **Tool Registry** - Centralized tool discovery and management
- **Suite-Based Architecture** - Modular server organization

---

## Installation & Setup

### Prerequisites

- **Python 3.8+** with pip
- **Claude Code** installed and configured
- **Docker** (optional, for Docker-based servers)
- **Node.js** (optional, for NPM servers)

### Installation

```bash
# Install MCP Manager
pip install mcp-manager

# Verify installation
mcp-manager --version

# Initialize system
mcp-manager system init
```

### Quick Setup

```bash
# Check system status
mcp-manager status

# Discover available servers
mcp-manager discover

# Install a basic suite
mcp-manager install-suite --suite-name development

# Start monitoring
mcp-manager monitoring start
```

---

## Core Features

### 🔍 Multi-Source Discovery

MCP Manager discovers servers from multiple sources with intelligent ranking:

```bash
# Discover all available servers
mcp-manager discover

# Search with AI-powered relevance
mcp-manager discover --query "database operations"
mcp-manager discover --query "web scraping tools"

# Filter by source type
mcp-manager discover --type npm
mcp-manager discover --type docker-desktop
mcp-manager discover --type docker-hub

# Update discovery cache
mcp-manager discover --update-catalog
```

**Discovery Sources:**
- **Docker Desktop** - Pre-built, tested servers
- **NPM Registry** - JavaScript/TypeScript servers
- **Docker Hub** - Community containers
- **GitHub** - Open source implementations
- **AI Curation** - Quality-scored recommendations

### 📦 Intelligent Installation

Install servers with dependency resolution and conflict detection:

```bash
# Install by unique ID
mcp-manager install-package dd-SQLite
mcp-manager install-package modelcontextprotocol-filesystem

# Install with automatic dependencies
mcp-manager install-package playwright-mcp --with-deps

# Batch installation
mcp-manager install-package dd-filesystem dd-http sqlite-mcp
```

### 🎯 Suite-Based Organization

Organize servers into logical collections:

```bash
# List available suites
mcp-manager suite list

# Install pre-configured suite
mcp-manager install-suite --suite-name web-development

# View suite details
mcp-manager suite show web-development

# Create custom suite
mcp-manager suite create "Data Science Stack" \
  --description "ML and data analysis tools" \
  --category data_analysis
```

---

## Server Management

### Basic Server Operations

```bash
# List all servers
mcp-manager list

# Show active servers only
mcp-manager list --active-only

# Server details
mcp-manager show <server-name>

# Remove server
mcp-manager remove <server-name>

# Restart server
mcp-manager restart <server-name>
```

### Advanced Server Configuration

```bash
# Add custom server
mcp-manager add my-custom-server \
  "npx my-mcp-package" \
  --type npm \
  --args "--port 3000" \
  --env "API_KEY=secret"

# Configure server parameters
mcp-manager configure <server-name> \
  --timeout 30 \
  --retries 3 \
  --health-check-interval 60

# Server health monitoring
mcp-manager health <server-name>
```

### Docker Desktop Integration

MCP Manager provides seamless Docker Desktop integration:

```bash
# Sync with Docker Desktop
mcp-manager claude sync --docker-desktop

# Enable Docker Desktop servers
mcp-manager docker enable-server sqlite
mcp-manager docker enable-server filesystem

# Import all enabled DD servers
mcp-manager claude add-from-docker-desktop
```

---

## Suite-Based Organization

### Understanding Suites

**Suites** are curated collections of MCP servers optimized for specific tasks or workflows. They provide:

- **Logical Grouping** - Related servers bundled together
- **Dependency Management** - Automatic resolution of server dependencies
- **Conflict Detection** - Prevents duplicate functionality
- **Team Collaboration** - Shareable configurations

### Working with Suites

```bash
# Browse available suites
mcp-manager suite list --category development
mcp-manager suite list --category data_analysis

# Suite information
mcp-manager suite show development-suite

# Install complete suite
mcp-manager install-suite --suite-name development-suite

# Create custom suite
mcp-manager suite create "My DevOps Stack" \
  --description "Docker, K8s, and CI/CD tools" \
  --category devops

# Add servers to suite
mcp-manager suite add my-devops-stack docker-mcp --role primary --priority 90
mcp-manager suite add my-devops-stack kubernetes-mcp --role secondary --priority 70
```

### Popular Pre-configured Suites

#### Development Suite
- **Servers**: filesystem, git, docker, sqlite, http-client
- **Use Cases**: Full-stack development, code management, testing
- **Install**: `mcp-manager install-suite --suite-name development`

#### Data Analysis Suite  
- **Servers**: pandas-mcp, jupyter-mcp, sqlite, visualization-tools
- **Use Cases**: Data science, analytics, reporting
- **Install**: `mcp-manager install-suite --suite-name data-analysis`

#### Web Development Suite
- **Servers**: playwright, http-client, filesystem, database, deployment-tools
- **Use Cases**: Web development, testing, deployment
- **Install**: `mcp-manager install-suite --suite-name web-development`

#### AI Research Suite
- **Servers**: pytorch-mcp, huggingface-mcp, jupyter, data-tools
- **Use Cases**: Machine learning, research, experimentation
- **Install**: `mcp-manager install-suite --suite-name ai-research`

---

## Workflow Automation

### Task-Specific Workflows

**Workflows** provide automated, task-specific MCP server configurations that adapt to your current work context.

### Creating Workflows

```bash
# Create development workflow
mcp-manager workflow create development-workflow \
  --description "Full-stack development environment" \
  --suites development-suite web-tools-suite \
  --category development \
  --priority 80 \
  --auto-activate

# Create data analysis workflow
mcp-manager workflow create data-workflow \
  --description "Data science and analytics" \
  --suites data-analysis-suite visualization-suite \
  --category data_analysis \
  --priority 75
```

### Workflow Management

```bash
# List all workflows
mcp-manager workflow list

# Show workflow details
mcp-manager workflow show development-workflow

# Activate workflow
mcp-manager workflow activate development-workflow

# AI-recommended workflow switching
mcp-manager workflow switch data_analysis

# Deactivate current workflow
mcp-manager workflow deactivate

# Workflow status
mcp-manager workflow status
```

### Workflow Templates

Create reusable workflow templates:

```bash
# Create template from servers
mcp-manager workflow template "Docker Development" \
  --servers docker-mcp kubernetes-mcp filesystem-mcp \
  --category development \
  --description "Containerized development stack"

# Create template from existing workflow
mcp-manager workflow template "Team Standard" \
  --from-workflow development-workflow \
  --priority 85
```

### AI-Driven Workflow Recommendations

MCP Manager uses AI to recommend optimal workflows:

```bash
# Get AI workflow recommendations
mcp-manager ai recommend-workflow --task "web development"
mcp-manager ai recommend-workflow --task "data analysis"

# Auto-switch based on task category
mcp-manager workflow switch content_creation
mcp-manager workflow switch system_administration
```

---

## Analytics & Monitoring

### Usage Analytics

Track and analyze MCP server usage patterns:

```bash
# Usage summary
mcp-manager analytics summary --days 7
mcp-manager analytics summary --days 30

# Query usage patterns
mcp-manager analytics query --pattern "database"
mcp-manager analytics query --pattern "file operations"

# Tool usage statistics
mcp-manager tools search filesystem --with-stats
```

**Sample Analytics Output:**
```
📊 Usage Analytics Summary (30 days)

Total Queries: 3,456
Unique Users: 5
Active Tools: 47
Success Rate: 96.8%
Average Response Time: 142.3ms

🏆 Most Used Tools:
  1. filesystem/read: 567 uses (16.4%)
  2. sqlite/query: 423 uses (12.2%)
  3. http/request: 334 uses (9.7%)
  4. git/status: 298 uses (8.6%)
  5. docker/ps: 234 uses (6.8%)

📈 Trending Queries:
  1. "code analysis": 89 queries
  2. "database operations": 76 queries
  3. "file management": 62 queries

⚡ Performance Metrics:
P50 Response Time: 98ms
P95 Response Time: 287ms
P99 Response Time: 543ms
Error Rate: 3.2%
```

### Real-Time Monitoring

```bash
# Start background monitoring
mcp-manager monitoring start

# Monitor specific servers
mcp-manager monitoring watch filesystem-mcp sqlite-mcp

# Live performance dashboard
mcp-manager monitoring dashboard

# Server health checks
mcp-manager monitoring health-check --all
```

### Performance Analysis

```bash
# Performance trends
mcp-manager analytics performance --timeframe week
mcp-manager analytics performance --server sqlite-mcp

# Error analysis
mcp-manager analytics errors --top 10
mcp-manager analytics errors --server problematic-server

# Resource usage
mcp-manager analytics resources --memory --cpu
```

---

## API Server

### REST API Server

MCP Manager includes a full-featured REST API server with authentication, rate limiting, and comprehensive endpoints.

### Starting the API Server

```bash
# Start API server
mcp-manager api start --host 127.0.0.1 --port 8000

# Start with custom configuration
mcp-manager api start --config api-config.json

# Check API server status
mcp-manager api status

# Test API connectivity
mcp-manager api test --host 127.0.0.1 --port 8000
```

### Authentication Management

```bash
# Create API key
mcp-manager api create-key "my-app" \
  --scopes analytics:read tools:read servers:read

# Create admin API key
mcp-manager api create-key "admin-access" \
  --scopes admin:full \
  --expires-days 90

# List API keys (admin only)
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/admin/api-keys
```

### API Endpoints

**Core Endpoints:**
- `GET /health` - Health check
- `POST /auth/token` - Authentication
- `POST /analytics/query` - Analytics data
- `POST /tools/search` - Tool search
- `GET /servers` - Server listing
- `POST /export` - Data export

**Authentication:**
- JWT tokens with configurable expiration
- API key-based access control
- Role-based permissions (read, write, admin)
- Rate limiting (per-minute and per-hour limits)

### Using the API

```bash
# Get authentication token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "YOUR_API_KEY"}'

# Query analytics
curl -X POST http://localhost:8000/analytics/query \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query_type": "usage_summary", "days": 7}'

# Search tools
curl -X POST http://localhost:8000/tools/search \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "filesystem", "limit": 10}'
```

---

## Proxy Server

### MCP Proxy Server

The proxy server provides a unified endpoint for multiple MCP servers with protocol translation, load balancing, and failover capabilities.

### Starting the Proxy Server

```bash
# Start proxy server
mcp-manager proxy start --host 127.0.0.1 --port 3001

# Start with specific mode
mcp-manager proxy start --mode load_balancing

# Start with configuration file
mcp-manager proxy start --config proxy-config.json

# Check proxy status
mcp-manager proxy status
```

### Proxy Modes

#### Transparent Mode (Default)
Routes requests to appropriate servers with minimal modification:
```bash
mcp-manager proxy start --mode transparent
```

#### Load Balancing Mode
Distributes requests across multiple servers:
```bash
mcp-manager proxy start --mode load_balancing
```

#### Aggregating Mode
Combines responses from multiple servers:
```bash
mcp-manager proxy start --mode aggregating
```

#### Failover Mode
Automatic failover on server failures:
```bash
mcp-manager proxy start --mode failover
```

### Managing Proxy Servers

```bash
# Add server to proxy
mcp-manager proxy add-server my-server \
  http://localhost:3000/mcp \
  --protocol mcp-v1 \
  --weight 100

# Remove server from proxy
mcp-manager proxy remove-server my-server

# View proxy statistics
mcp-manager proxy stats

# Test proxy functionality
mcp-manager proxy test --method tools/list
```

### Protocol Translation

The proxy automatically translates between different MCP protocol versions:

- **MCP v1** - Standard JSON-RPC 2.0 format
- **MCP v2** - Enhanced format with metadata
- **Legacy** - Simplified format for older servers

```bash
# Generate proxy configuration
mcp-manager proxy config --template --output proxy-config.json

# Start with protocol translation
mcp-manager proxy start --config proxy-config.json
```

### Proxy Web Interface

Access the proxy web interface at `http://localhost:3001` for:
- Real-time server status
- Request/response monitoring
- Configuration management
- Performance metrics

---

## Terminal User Interface

### Rich TUI Experience

Launch the modern terminal user interface:

```bash
# Start TUI
mcp-tui

# Or via main command
mcp-manager tui
```

### TUI Features

**Main Dashboard:**
- Server status overview
- Real-time analytics
- Quick actions menu
- System health indicators

**Server Management:**
- Interactive server browser
- One-click installation
- Configuration editing
- Health monitoring

**Suite Explorer:**
- Browse available suites
- Preview suite contents
- Install with progress tracking
- Custom suite creation

**Workflow Designer:**
- Visual workflow creation
- Drag-and-drop server assignment
- Workflow testing
- Performance metrics

**Analytics Viewer:**
- Interactive charts and graphs
- Usage pattern analysis
- Performance trends
- Export capabilities

---

## Command Reference

### Core Commands

| Command | Description | Example |
|---------|-------------|---------|
| `mcp-manager status` | System status overview | `mcp-manager status --verbose` |
| `mcp-manager list` | List configured servers | `mcp-manager list --format table` |
| `mcp-manager discover` | Find available servers | `mcp-manager discover --query git` |
| `mcp-manager install-package <id>` | Install server by ID | `mcp-manager install-package dd-SQLite` |
| `mcp-manager remove <name>` | Remove server | `mcp-manager remove old-server` |
| `mcp-manager restart <name>` | Restart server | `mcp-manager restart sqlite-mcp` |

### Suite Management

| Command | Description | Example |
|---------|-------------|---------|
| `mcp-manager suite list` | List available suites | `mcp-manager suite list --category web` |
| `mcp-manager suite create <name>` | Create new suite | `mcp-manager suite create "DevOps Tools"` |
| `mcp-manager suite add <suite> <server>` | Add server to suite | `mcp-manager suite add devops docker-mcp` |
| `mcp-manager suite show <suite>` | Show suite details | `mcp-manager suite show development` |
| `mcp-manager install-suite --suite-name <id>` | Install complete suite | `mcp-manager install-suite --suite-name web-dev` |
| `mcp-manager suite delete <suite>` | Delete suite | `mcp-manager suite delete old-suite` |

### Workflow Automation

| Command | Description | Example |
|---------|-------------|---------|
| `mcp-manager workflow list` | List workflows | `mcp-manager workflow list --category dev` |
| `mcp-manager workflow create <name>` | Create workflow | `mcp-manager workflow create dev-flow` |
| `mcp-manager workflow activate <name>` | Activate workflow | `mcp-manager workflow activate dev-flow` |
| `mcp-manager workflow switch <category>` | AI-recommended switch | `mcp-manager workflow switch data_analysis` |
| `mcp-manager workflow deactivate` | Deactivate current | `mcp-manager workflow deactivate` |
| `mcp-manager workflow status` | Show workflow status | `mcp-manager workflow status` |
| `mcp-manager workflow template <name>` | Create template | `mcp-manager workflow template "Team Standard"` |

### Analytics & Monitoring

| Command | Description | Example |
|---------|-------------|---------|
| `mcp-manager analytics summary` | Usage overview | `mcp-manager analytics summary --days 30` |
| `mcp-manager analytics query` | Query usage patterns | `mcp-manager analytics query --pattern db` |
| `mcp-manager tools search <query>` | Search tool registry | `mcp-manager tools search filesystem` |
| `mcp-manager tools list` | List all tools | `mcp-manager tools list --available-only` |
| `mcp-manager monitoring start` | Start monitoring | `mcp-manager monitoring start` |
| `mcp-manager monitoring status` | Monitoring status | `mcp-manager monitoring status` |

### API Server

| Command | Description | Example |
|---------|-------------|---------|
| `mcp-manager api start` | Start API server | `mcp-manager api start --port 8000` |
| `mcp-manager api stop` | Stop API server | `mcp-manager api stop` |
| `mcp-manager api status` | API server status | `mcp-manager api status` |
| `mcp-manager api test` | Test API connectivity | `mcp-manager api test` |
| `mcp-manager api create-key <name>` | Create API key | `mcp-manager api create-key myapp` |

### Proxy Server

| Command | Description | Example |
|---------|-------------|---------|
| `mcp-manager proxy start` | Start proxy server | `mcp-manager proxy start --mode failover` |
| `mcp-manager proxy status` | Proxy server status | `mcp-manager proxy status` |
| `mcp-manager proxy stats` | Proxy statistics | `mcp-manager proxy stats` |
| `mcp-manager proxy add-server <name> <url>` | Add server to proxy | `mcp-manager proxy add-server srv1 http://localhost:3000` |
| `mcp-manager proxy remove-server <name>` | Remove server from proxy | `mcp-manager proxy remove-server srv1` |
| `mcp-manager proxy test` | Test proxy functionality | `mcp-manager proxy test --method tools/list` |
| `mcp-manager proxy config --template` | Generate config template | `mcp-manager proxy config --template` |

### System Management

| Command | Description | Example |
|---------|-------------|---------|
| `mcp-manager system init` | Initialize system | `mcp-manager system init` |
| `mcp-manager system diagnose` | System diagnostics | `mcp-manager system diagnose` |
| `mcp-manager system cleanup` | Clean system state | `mcp-manager system cleanup --fix-config` |
| `mcp-manager system export-config` | Export configuration | `mcp-manager system export-config` |
| `mcp-manager system logs` | View system logs | `mcp-manager system logs --tail 50` |

---

## Troubleshooting

### Common Issues

#### Server Installation Problems

**Problem**: Server installation fails
```bash
# Check discovery cache
mcp-manager discover --update-catalog

# Verify server availability
mcp-manager discover --query <server-name>

# Check installation logs
mcp-manager system logs --filter installation
```

**Problem**: Dependency conflicts
```bash
# Check for conflicts
mcp-manager system diagnose --check-conflicts

# Resolve conflicts
mcp-manager cleanup --resolve-conflicts

# Force reinstall
mcp-manager install-package <server> --force
```

#### Performance Issues

**Problem**: Slow MCP operations
```bash
# Check server health
mcp-manager monitoring health-check --all

# Analyze performance
mcp-manager analytics performance --server <problematic-server>

# Restart problematic servers
mcp-manager restart <server-name>
```

**Problem**: High memory usage
```bash
# Check resource usage
mcp-manager analytics resources --memory

# Identify heavy servers
mcp-manager monitoring top --memory

# Optimize configuration
mcp-manager configure <server> --memory-limit 512MB
```

#### Configuration Problems

**Problem**: Claude Code doesn't see servers
```bash
# Sync with Claude Code
mcp-manager claude sync

# Check Claude Code status
mcp-manager claude status

# Force configuration update
mcp-manager cleanup --fix-config
```

**Problem**: Workflow activation fails
```bash
# Check workflow status
mcp-manager workflow status

# Validate workflow
mcp-manager workflow show <workflow-name>

# Recreate workflow
mcp-manager workflow delete <workflow-name>
mcp-manager workflow create <workflow-name> --suites <suites>
```

#### API/Proxy Server Issues

**Problem**: API server won't start
```bash
# Check port availability
mcp-manager api status

# Start with different port
mcp-manager api start --port 8001

# Check logs
mcp-manager system logs --component api-server
```

**Problem**: Proxy server connection issues
```bash
# Test proxy connectivity
mcp-manager proxy test

# Check server health
mcp-manager proxy status

# Restart proxy with debug logging
mcp-manager proxy start --log-level DEBUG
```

### Diagnostic Tools

#### System Health Check
```bash
# Comprehensive system check
mcp-manager system diagnose

# Check specific components
mcp-manager system diagnose --check servers
mcp-manager system diagnose --check workflows
mcp-manager system diagnose --check api
```

#### Configuration Validation
```bash
# Validate all configurations
mcp-manager system validate

# Export current state
mcp-manager system export-config --output backup.json

# Reset to clean state
mcp-manager system reset --keep-servers
```

#### Log Analysis
```bash
# View recent logs
mcp-manager system logs --tail 100

# Filter by component
mcp-manager system logs --component proxy --level ERROR

# Export logs for support
mcp-manager system logs --export --output support-logs.txt
```

---

## Best Practices

### 🎯 Server Management

**Optimal Server Selection:**
- Start with pre-configured suites for common tasks
- Avoid installing duplicate functionality servers
- Regularly review and remove unused servers
- Monitor server performance and health
- Keep servers updated to latest versions

**Server Organization:**
```bash
# Good: Use suites for organization
mcp-manager suite create "Web Development" --category web
mcp-manager suite add web-development playwright-mcp --role primary
mcp-manager suite add web-development http-client-mcp --role secondary

# Good: Regular cleanup
mcp-manager cleanup --remove-unused --days 30
```

### 🔄 Workflow Optimization

**Effective Workflow Design:**
- Create task-specific workflows with clear purposes
- Use AI recommendations for workflow switching
- Monitor workflow performance with analytics
- Document workflow purposes for team sharing
- Regular workflow optimization based on usage patterns

**Workflow Best Practices:**
```bash
# Good: Descriptive workflow creation
mcp-manager workflow create "Full-Stack Development" \
  --description "Complete development environment with testing tools" \
  --suites development-suite testing-suite \
  --category development \
  --priority 85

# Good: Use AI recommendations
mcp-manager workflow switch data_analysis  # AI picks best workflow
```

### 📊 Performance Monitoring

**Monitoring Strategy:**
- Enable continuous monitoring for production use
- Set up alerts for performance degradation
- Regular analytics review (weekly/monthly)
- Track resource usage trends
- Monitor error rates and response times

**Performance Optimization:**
```bash
# Set up monitoring
mcp-manager monitoring start --alerts

# Regular performance checks
mcp-manager analytics performance --trends

# Resource optimization
mcp-manager configure --optimize-memory --all-servers
```

### 🔒 Security Best Practices

**API Security:**
- Use strong API keys with appropriate scopes
- Set reasonable token expiration times
- Monitor API usage for anomalies
- Regularly rotate API keys
- Enable rate limiting in production

**Server Security:**
```bash
# Good: Scoped API key creation
mcp-manager api create-key "dashboard-app" \
  --scopes analytics:read tools:read \
  --expires-days 30

# Good: Monitor API usage
mcp-manager analytics api-usage --alerts
```

### 👥 Team Collaboration

**Team Setup:**
- Create shared suite configurations
- Document team workflows and standards
- Use version control for configuration files
- Establish server naming conventions
- Regular team configuration reviews

**Collaboration Tools:**
```bash
# Share team configuration
mcp-manager system export-config --team-template

# Create team-specific suites
mcp-manager suite create "Team Standard Development" \
  --description "Company standard development stack" \
  --category team-standard
```

### 🚀 Production Deployment

**Production Readiness:**
- Enable comprehensive logging and monitoring
- Set up backup and recovery procedures
- Configure proper resource limits
- Implement health checks and alerting
- Document operational procedures

**Production Configuration:**
```bash
# Production API server
mcp-manager api start \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level INFO \
  --daemon

# Production proxy server
mcp-manager proxy start \
  --mode failover \
  --config production-proxy.json \
  --daemon
```

---

## Quick Start Guide

### Day 1: Basic Setup
1. **Install MCP Manager**: `pip install mcp-manager`
2. **Initialize system**: `mcp-manager system init`
3. **Discover servers**: `mcp-manager discover`
4. **Install basic suite**: `mcp-manager install-suite --suite-name development`
5. **Verify installation**: `mcp-manager status`

### Week 1: Customization
1. **Create custom workflow**: Based on your primary tasks
2. **Set up monitoring**: `mcp-manager monitoring start`
3. **Explore analytics**: `mcp-manager analytics summary`
4. **Try TUI interface**: `mcp-tui`
5. **Configure API access**: For integrations

### Month 1: Optimization
1. **Review usage patterns**: `mcp-manager analytics summary --days 30`
2. **Optimize workflows**: Based on analytics insights
3. **Set up team sharing**: Export configurations for team use
4. **Configure proxy server**: For unified access patterns
5. **Performance tuning**: Based on monitoring data

### Ongoing: Maintenance
- **Weekly**: Check analytics and health status
- **Monthly**: Review and clean unused servers
- **Quarterly**: Update workflows and optimize configuration
- **As needed**: Discover new servers and capabilities

---

## Getting Support

### Documentation Resources
- **Admin Guide**: Advanced configuration and architecture
- **API Reference**: Complete API documentation
- **GitHub Repository**: Source code and examples
- **Community Forum**: Discussions and Q&A

### Support Channels
- **GitHub Issues**: Bug reports and feature requests
- **Community Discussions**: General questions and sharing
- **Documentation**: Comprehensive guides and tutorials
- **Examples Repository**: Sample configurations and workflows

### Staying Updated
- **Release Notes**: Follow GitHub releases for updates
- **Community**: Join discussions for tips and best practices
- **Blog**: Technical deep-dives and use cases
- **Roadmap**: Upcoming features and improvements

---

**Welcome to the future of MCP server management! 🚀**

*This guide covers all user-facing features of MCP Manager v2.0. For system administration, server development, and detailed architecture information, see the [Admin Guide](ADMIN_GUIDE.md).*