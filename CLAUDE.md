# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Claude MCP Manager - an enterprise-grade Python tool for managing MCP (Model Context Protocol) servers used by Claude Code. The tool provides both a modern terminal user interface (TUI) and comprehensive command-line interface (CLI) for discovering, installing, configuring, and managing MCP servers.

## Key Concepts

### MCP Servers
- **Docker Desktop MCP Servers**: Pre-built servers available through Docker Desktop (SQLite, filesystem, search, http, k8s, terraform, aws)
- **NPM MCP Servers**: JavaScript/TypeScript servers installed via npm (playwright, filesystem, sqlite, brave-search)
- **Docker Hub Servers**: Community-built servers available via Docker containers
- **Custom MCP Servers**: User-defined servers with custom commands

### Configuration Architecture (Claude Code)
Claude Code uses a hierarchical configuration system:
1. **Internal State**: `~/.claude.json` - Source of truth managed by `claude mcp` commands
2. **User Config**: `~/.config/claude-code/mcp-servers.json` - User-level overrides
3. **Project Config**: `./.mcp.json` - Project-specific configurations

### MCP Manager Configuration
The tool uses TOML-based configuration with hierarchical overrides:
1. **System Configuration**: `/etc/mcp-manager/config.toml`
2. **User Configuration**: `~/.config/mcp-manager/config.toml` 
3. **Project Configuration**: `./.mcp-manager.toml`
4. **Environment Variables**: `MCP_MANAGER_*`

## Implementation Structure

The project is a Python package with modular architecture:
```
src/mcp_manager/
├── core/                 # Core business logic
│   ├── simple_manager.py # Main MCP management
│   ├── discovery.py      # Server discovery
│   └── claude_interface.py # Claude Code integration
├── cli/                  # Command-line interface
│   └── main.py          # CLI commands with Click
├── tui/                  # Terminal user interface
│   └── menu_app.py      # TUI with Textual
└── utils/                # Utilities and helpers
    ├── config.py        # Configuration management
    ├── logging.py       # Structured logging
    └── validation.py    # Input validation
```

## Core Commands (Current Implementation)

```bash
# Modern user interfaces
mcp-tui                                   # Launch terminal user interface
mcp-manager tui                          # Alternative TUI command

# Easy installation with unique Install IDs
mcp-manager discover --query filesystem  # Find servers with unique IDs
mcp-manager install-package dd-SQLite    # One-command installation
mcp-manager install-package modelcontextprotocol-filesystem

# Server management
mcp-manager list                         # List all servers and status
mcp-manager add <name> <command>         # Add custom server
mcp-manager remove <server-name>         # Remove server
mcp-manager cleanup                      # Fix broken configurations

# Discovery and search
mcp-manager discover                     # Discover all available servers
mcp-manager discover --type npm          # Filter by server type
mcp-manager discover --update-catalog    # Refresh Docker Desktop catalog

# Configuration management
mcp-manager config                       # Show current configuration
mcp-manager --scope user/project         # Set configuration scope
```

## Key Features (Implemented)

1. **Unique Install IDs**: Distinguish servers with same names (dd-SQLite vs mcp-sqlite)
2. **One-Command Installation**: `mcp-manager install-package <install-id>`
3. **Multi-Source Discovery**: NPM registry, Docker Hub, Docker Desktop catalogs
4. **Duplicate Detection**: Automatic warnings for similar functionality servers
5. **Docker Desktop Integration**: Uses `docker mcp` commands and docker-gateway
6. **Configuration Cleanup**: Automatically fix broken MCP configurations
7. **Structured Logging**: JSON and text logging with rotation
8. **Type Safety**: Full type hints and mypy validation
9. **Comprehensive Testing**: Unit and integration test coverage

## Critical Implementation Details

### Docker Desktop Integration
- Use `docker mcp server enable/disable` for Docker Desktop servers
- Import all enabled DD servers with: `claude mcp add-from-claude-desktop docker-gateway`
- The docker-gateway acts as a unified proxy for all enabled DD servers
- Automatic synchronization between DD state and Claude Code's internal configuration

### NPX Command Handling
- Use proper `--` separator: `npx -y @package/name -- --arg value`
- Validate command arguments and handle complex parameter passing
- Support for servers requiring configuration (directories, API keys)

### Discovery System
- Real-time discovery from NPM registry, Docker Hub, Docker Desktop
- Quality scoring and relevance ranking for search results
- Caching with TTL for performance optimization
- Install ID generation for unique server identification

### Configuration Management
- TOML-based configuration with Pydantic validation
- Hierarchical configuration with proper precedence
- Automatic backup creation before destructive operations
- Environment variable support for all configuration options

## Development Guidance

### Git Workflow
- When working on a new feature you MUST create a new branch in github. Once I confirm the feature is working (you can ask me), you should merge changes into the main branch.
- CRITICAL: You MUST commit after each significant step or fix. Do not batch multiple changes into a single commit.
- Always run lint and typecheck commands before committing if they are available.

### Code Quality
- Use a proper production level project directory structure.
- All projects require proper logging and error handling
- All projects should be designed to debug switching and logging built in, as a basic attribute 
- All projects that use sensitive data must encrypt that data
- Use MCP servers, when available and applicable

### Modular Architecture
- Use a modular architecture with clean separation of concerns
- Individual modules can be imported and used independently
- Clean separation of concerns for easier testing and maintenance
- Plugin architecture foundation for future extensions
- Comprehensive documentation in `README.md`
- Enhanced error handling and logging throughout

### File Size Management
- To keep things modular we need to try to keep file sizes down to 1000 lines or less at all times

### Data Handling
- CRITICAL: Use ONLY real data from actual APIs/systems. NEVER use fake, hardcoded, placeholder, or simulated data. If real data is not available, say 'Data not available' - do not make up values.
- Do not hardcode any variables in prompts or otherwise, build production ready code in a modular fashion, instead of placeholders and to-dos