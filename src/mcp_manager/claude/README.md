# Claude Interface Module

This module provides a focused, modular interface to Claude Code's MCP management capabilities.

## Architecture

The original 679-line `claude_interface.py` has been refactored into focused modules:

### Core Modules

- **`claude_interface.py`** (195 lines) - Main orchestrator that coordinates all operations
- **`claude_client.py`** (190 lines) - Claude CLI integration and path discovery
- **`server_operations.py`** (180 lines) - Server CRUD operations (add, remove, update)
- **`sync_manager.py`** (140 lines) - Background sync operations and cache management
- **`docker_gateway.py`** (170 lines) - Docker gateway expansion and management

### Key Benefits

1. **Focused Responsibilities**: Each module has a single, clear purpose
2. **Maintainable**: Easy to understand and modify individual components
3. **Testable**: Each module can be tested independently
4. **Professional**: Enterprise-grade modular architecture
5. **Backward Compatible**: Legacy imports still work with deprecation warnings

### Usage

```python
# New recommended import
from mcp_manager.claude import ClaudeInterface

# Legacy import (deprecated but still works)
from mcp_manager.core.claude_interface import ClaudeInterface
```

### Module Responsibilities

- **SyncManager**: File modification tracking, cache invalidation, background database sync
- **ClaudeClient**: CLI discovery, environment setup, basic server listing
- **ServerOperations**: Add/remove/update server operations with validation
- **DockerGatewayExpander**: Docker Desktop server expansion and configuration
- **ClaudeInterface**: Main orchestrator that delegates to focused modules

All modules are under 200 lines and follow the modular architecture principle.