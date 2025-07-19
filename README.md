# MCP Manager

Enterprise-grade MCP (Model Context Protocol) server management tool with modern TUI and CLI interfaces.

## Overview

MCP Manager is a professional tool for managing MCP servers used by Claude Code. It provides both a beautiful terminal user interface (TUI) and comprehensive command-line interface (CLI) for discovering, installing, configuring, and managing MCP servers across different scopes.

## Features

### 🎯 Core Functionality
- **Server Management**: Add, remove, enable, disable MCP servers
- **Scope Support**: Local (private), Project (shared), User (global) configurations
- **Discovery**: Find and install new MCP servers from NPM and Docker registries
- **Bulk Operations**: Manage multiple servers simultaneously
- **Real-time Status**: Monitor server health and performance

### 🖥️ User Interfaces
- **Modern TUI**: Beautiful terminal interface built with Textual
- **Comprehensive CLI**: Full command-line interface with rich help
- **Interactive Menus**: Intuitive navigation and selection
- **Keyboard Shortcuts**: Efficient operation for power users

### 🏢 Enterprise Features
- **Structured Logging**: JSON and text logging with rotation
- **Configuration Management**: TOML-based configuration with validation
- **Dependency Checking**: Automatic validation of system requirements
- **Performance Monitoring**: Built-in profiling and metrics
- **Comprehensive Testing**: Unit and integration test coverage
- **Type Safety**: Full type hints and mypy validation

## Key Insights

- How CLAUDE works.

  1. Global Level

  File: ~/.config/claude-code/mcp-servers.json
  - User-wide servers available across all projects
  - Format: Standard MCP JSON schema
  - Managed by: External tools, manual editing

  2. Project Level

  File: ./.mcp.json (in project directory)
  - Project-specific servers
  - Format: Standard MCP JSON schema
  - Managed by: External tools, manual editing

  3. Internal (Claude Code's State)

  File: ~/.claude.json
  - Location: .projectConfigs["/path/to/project"].mcpServers
  - Contains the actual active configuration Claude Code uses
  - Managed by: claude mcp CLI commands only

  The Key Insight
  Claude Code primarily uses its internal state (.claude.json)
  Claude Code's internal state is the source of truth for what actually runs!

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/anthropics/claude-mcp-manager
cd claude-mcp-manager/mcp-manager-python

# Install with pip (development mode)
pip install -e .

# Or install with optional dependencies
pip install -e ".[dev,test]"
```

### Usage

#### Terminal User Interface (TUI)
```bash
# Launch the modern TUI
mcp-tui

# Or use the main command
mcp-manager tui
```

#### Command Line Interface (CLI)
```bash
# List all servers
mcp-manager list

# Add a new server
mcp-manager add filesystem "npx @modelcontextprotocol/server-filesystem" --scope user

# Discover available servers
mcp-manager discover

# Enable/disable servers
mcp-manager enable filesystem
mcp-manager disable filesystem

# Bulk operations
mcp-manager bulk-enable filesystem sequential-thinking fetch

# Get help
mcp-manager --help
```

## Architecture

### Project Structure
```
mcp-manager-python/
├── src/mcp_manager/          # Main package
│   ├── core/                 # Core business logic
│   ├── cli/                  # Command-line interface
│   ├── tui/                  # Terminal user interface
│   └── utils/                # Utilities and helpers
├── tests/                    # Test suite
├── docs/                     # Documentation
└── pyproject.toml           # Project configuration
```

### Key Components
- **Core Module**: MCP server management, configuration, discovery
- **CLI Module**: Command-line interface using Click
- **TUI Module**: Terminal interface using Textual
- **Utils Module**: Logging, configuration, validation utilities

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Format code
black src tests
isort src tests

# Type checking
mypy src

# Linting
flake8 src tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcp_manager

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

## Configuration

MCP Manager uses a hierarchical configuration system:

1. **System Configuration**: `/etc/mcp-manager/config.toml`
2. **User Configuration**: `~/.config/mcp-manager/config.toml`
3. **Project Configuration**: `./.mcp-manager.toml`
4. **Environment Variables**: `MCP_MANAGER_*`

### Example Configuration

```toml
[logging]
level = "INFO"
format = "json"
file = "~/.config/mcp-manager/logs/app.log"

[claude]
cli_path = "claude"
config_path = "~/.config/claude-code/mcp-servers.json"

[discovery]
npm_registry = "https://registry.npmjs.org"
docker_registry = "docker.io"
cache_ttl = 3600

[ui]
theme = "dark"
animations = true
confirm_destructive = true
```

## Scope Management

MCP Manager supports three configuration scopes:

### 🔒 Local Scope
- **Purpose**: Private to your user account
- **Storage**: User-specific configuration
- **Use Case**: Personal tools, experimental servers

### 🔄 Project Scope  
- **Purpose**: Shared with team via git
- **Storage**: `.mcp-manager.toml` in project root
- **Use Case**: Project-specific tools, team environments

### 🌐 User Scope
- **Purpose**: Global user configuration
- **Storage**: `~/.config/mcp-manager/`
- **Use Case**: Common tools, personal preferences

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the coding standards
4. Add tests for new functionality
5. Run the test suite (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Coding Standards

- Follow PEP 8 style guidelines
- Use type hints for all functions and methods
- Write docstrings for all public APIs
- Maintain test coverage above 90%
- Keep functions under 50 lines when possible
- Keep files under 1000 lines

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [Full documentation](https://claude-mcp-manager.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/anthropics/claude-mcp-manager/issues)
- **Discussions**: [GitHub Discussions](https://github.com/anthropics/claude-mcp-manager/discussions)

## Acknowledgments

- Built with [Textual](https://github.com/Textualize/textual) for the TUI
- Uses [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- Powered by [Click](https://click.palletsprojects.com/) for the CLI
- Configuration management with [Pydantic](https://pydantic.dev/)
