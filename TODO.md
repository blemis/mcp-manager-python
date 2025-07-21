# TODO.md - MCP Manager Python Project

## Current Status

✅ **Completed Tasks**
- Fixed TUI syntax error preventing startup
- Resolved Pydantic v2 deprecation warnings (.dict() → .model_dump())
- Enhanced test coverage with comprehensive test suites
- Verified CLI and TUI functionality
- Created project CLAUDE.md with development guidelines
- Implemented comprehensive integration tests (task-001)
- Implemented server discovery functionality (task-002) 
- Enhanced CLI command validation (task-003)
- Fixed critical Docker Desktop MCP integration architecture

✅ **Recently Completed**
- **CRITICAL: Enhanced Discovery System & Install-Package Command** - COMPLETED!
  - Implemented unique Install IDs to distinguish servers with same names
  - Added install-package command for easy one-command installation
  - Fixed NPX command argument parsing with proper -- separator handling
  - Added comprehensive duplicate detection across server types
  - Created cleanup command to remove problematic MCP configurations
  - Enhanced Docker Desktop discovery to use real docker mcp catalog commands
  - Moved verbose INFO logs to DEBUG level for cleaner user experience
  - All major user experience issues resolved - system now production-ready!

## Key Architectural Discovery

Found that Claude Code has three configuration levels:
1. Global: ~/.config/claude-code/mcp-servers.json 
2. Project: ./.mcp.json
3. **Internal (source of truth): ~/.claude.json** managed by `claude mcp` commands

✅ **Working Solution Identified**: 
- `claude mcp add-from-claude-desktop docker-gateway` automatically imports ALL active Docker Desktop MCPs
- Docker Desktop servers are managed via `docker mcp server enable/disable`
- The docker-gateway acts as a proxy/aggregator for all enabled DD servers

## Current Implementation Status

**Files Modified:**
- `simple_manager.py` - Added seamless DD integration
- `claude_interface.py` - Fixed command formatting issues
- `discovery.py` - Added dynamic Docker catalog discovery

**Key Functions Implemented:**
- `_enable_docker_desktop_server()` - Enables server in DD, then syncs to Claude
- `_disable_docker_desktop_server()` - Disables server in DD, then syncs to Claude  
- `_import_docker_gateway_to_claude_code()` - Uses official import command
- `_is_docker_desktop_server()` - Detects DD servers for proper handling

**Final Implementation:**
- ✅ Enhanced discovery with unique Install IDs (dd-SQLite, modelcontextprotocol-filesystem, etc.)
- ✅ Simple installation: `mcp-manager install-package dd-SQLite` 
- ✅ Docker Desktop integration: `mcp-manager install-package dd-filesystem` 
- ✅ NPX integration: `mcp-manager install-package modelcontextprotocol-filesystem`
- ✅ Automatic duplicate detection with user warnings
- ✅ Cleanup command: `mcp-manager cleanup` for fixing broken configurations
- ✅ Complete workflow tested and verified working with actual MCP server connections

## Next Steps

### Highest Priority (CURRENT)

**task-014**: ✅ **COMPLETED** - Implement disabled server status tracking
- ✅ Created local server catalog system (`~/.config/mcp-manager/server_catalog.json`)
- ✅ Track servers that have been installed/configured vs never-installed
- ✅ Show disabled servers with red "disabled" status when previously installed
- ✅ Auto-populate catalog for existing servers from Claude/Docker state
- ✅ Proper state management for add/disable/enable/remove operations

**task-015**: 🚧 **IN PROGRESS** - External Change Detection & Synchronization
- Implement detection of servers added via `docker mcp` or `claude mcp` commands
- Handle multi-scope configuration synchronization (user/project/local)
- Real-time monitoring and automatic catalog updates
- Seamless user experience across all MCP management tools
- **See detailed plan in [External Change Detection Plan](#external-change-detection-plan) below**

### High Priority

**task-001**: ✅ **COMPLETED** - Create comprehensive integration tests
- ✅ Tested full CLI workflows (discover → install-package → verify connections)
- ✅ Verified Claude CLI integration end-to-end with working MCP servers
- ✅ Docker Desktop integration fully tested and working
- ✅ NPX integration tested (with configuration limitations identified)

**task-002**: ✅ **COMPLETED** - Implement server discovery functionality  
- ✅ Complete NPM registry integration for discovering MCP servers
- ✅ Docker Hub API integration for Docker-based MCP servers
- ✅ Docker Desktop catalog integration using `docker mcp catalog show`
- ✅ Search and filtering capabilities implemented
- ✅ Caching for discovery results implemented

**task-003**: ✅ **COMPLETED** - Enhance CLI command validation
- ✅ Input validation for server names, commands, and types
- ✅ Proper error handling for invalid configurations  
- ✅ Confirmation prompts for destructive operations
- ✅ Comprehensive duplicate detection and user warnings
- ✅ Improved error messages with actionable suggestions

**task-013**: Enhance install-package for servers requiring configuration
- Add automatic detection of servers that need configuration (filesystem, database)
- Prompt users for required parameters (directories, connection strings)
- Provide sensible defaults (home directory for filesystem servers)
- Handle environment variable requirements for servers

### Medium Priority

**task-004**: Add configuration management features
- Implement configuration import/export functionality
- Add configuration validation and migration tools
- Support for configuration templates and presets
- Add backup and restore capabilities for configurations

**task-005**: Implement server health monitoring
- Add server status checking (running/stopped/error states)
- Implement periodic health checks for enabled servers
- Add logging and alerting for server failures
- Create dashboard view for server health overview

**task-006**: Enhance TUI user experience
- Add keyboard shortcuts documentation
- Implement context-sensitive help system
- Add server configuration editing in TUI
- Improve visual feedback for long-running operations

### Low Priority

**task-007**: Add advanced server management
- Implement server dependency management
- Add server grouping and tagging capabilities
- Support for server environment variables and configuration
- Add server performance metrics and logging

**task-008**: Create installation and distribution tools
- Create installation script for easy setup
- Add package distribution (PyPI, Homebrew, etc.)
- Create documentation website
- Add shell completion scripts

**task-009**: Implement security features
- Add configuration encryption for sensitive data
- Implement access control and permissions
- Add audit logging for configuration changes
- Security scanning for server commands

## Technical Debt

**task-010**: Code quality improvements
- Refactor large files to stay under 1000 lines
- Add type hints to remaining untyped functions
- Improve error handling consistency across modules
- Add performance optimization for large server lists

**task-011**: Documentation enhancements
- Create comprehensive API documentation
- Add usage examples and tutorials
- Create troubleshooting guide
- Add architecture and design documentation

**task-012**: Testing improvements
- Increase test coverage to 95%+
- Add performance and load testing
- Implement end-to-end testing automation
- Add mutation testing for test quality verification

## Notes

- All new features should follow the modular architecture guidelines in CLAUDE.md
- Each task should be implemented in a separate git branch
- Comprehensive testing is required for all new functionality
- Follow the git workflow: branch → develop → test → commit → merge

## External Change Detection Plan

### Overview
Implement comprehensive detection and synchronization of MCP servers that are added/modified/removed through external commands (`docker mcp` or `claude mcp`) rather than through mcp-manager itself.

### Phase 1: Configuration Monitoring Infrastructure (task-015-1)
- [ ] **File System Watchers** (`src/mcp_manager/core/watchers.py`)
  - Monitor `~/.docker/mcp/registry.yaml` for Docker Desktop changes
  - Monitor `~/.config/claude-code/mcp-servers.json` for user-level Claude changes
  - Monitor `./.mcp.json` in current and parent directories for project changes
  - Monitor `~/.claude.json` for internal Claude state changes
  - Use `watchdog` library for cross-platform file monitoring

- [ ] **Configuration Parsers** (`src/mcp_manager/core/parsers/`)
  - Docker Registry Parser for `registry.yaml` changes
  - Claude Config Parser for JSON configs across all scopes
  - Handle malformed files gracefully with proper error recovery

- [ ] **Change Detection Engine** (`src/mcp_manager/core/change_detector.py`)
  - Compare current external state vs. internal catalog
  - Identify added/removed/modified servers by source
  - Generate reconciliation actions with conflict detection

### Phase 2: Catalog Synchronization (task-015-2)
- [ ] **Auto-Reconciliation Service** (`src/mcp_manager/core/reconciler.py`)
  - Reconcile external changes with internal catalog automatically
  - Handle conflicts with user-defined resolution strategies
  - Maintain change history and audit trail for debugging

- [ ] **Multi-Scope Support** (enhance existing `simple_manager.py`)
  - Track servers by scope (local/project/user) with proper precedence
  - Merge configurations from multiple scopes correctly
  - Support scope-specific enable/disable operations

- [ ] **External Server Handler** (`src/mcp_manager/core/external_handler.py`)
  - Auto-catalog externally added servers with metadata preservation
  - Support "adopt" vs "ignore" policies for unknown servers
  - Handle servers with unknown origins gracefully

### Phase 3: Real-Time Synchronization (task-015-3)
- [ ] **Background Sync Service** (`src/mcp_manager/core/sync_service.py`)
  - Run file watchers in background thread with proper lifecycle
  - Debounce rapid changes during batch operations
  - Support manual sync triggers and health monitoring

- [ ] **Event System** (`src/mcp_manager/core/events.py`)
  - Define change event types with rich metadata
  - Publish events when external changes detected
  - Subscribe catalog and UI components to events with filtering

- [ ] **Conflict Resolver** (`src/mcp_manager/core/conflicts.py`)
  - Detect conflicting states between sources
  - Implement resolution strategies (last-write-wins, user-prompt, etc.)
  - Support manual conflict resolution with user guidance

### Phase 4: User Interface Integration (task-015-4)
- [ ] **Enhanced CLI Integration** (update `cli/main.py`)
  - Show server origin and sync status in list command
  - Add `--sync`, `--external-only` flags for control
  - New commands: `sync status`, `sync run`, `sync resolve`

- [ ] **Real-Time TUI Updates** (update `tui/main.py`)
  - Live update server list when external changes detected
  - Visual indicators for external changes and conflicts
  - Manual refresh triggers and sync status display

### Phase 5: Testing & Validation (task-015-5)
- [ ] **External Change Test Suite** (`tests/integration/test_external_sync.py`)
  - Test Docker MCP and Claude MCP command detection
  - Test manual config file changes and conflict scenarios
  - Test performance with large catalogs and many files

### Success Criteria
- ✅ All external Docker MCP changes automatically detected and synced
- ✅ All external Claude MCP changes automatically detected and synced  
- ✅ Multi-scope configuration handling works correctly
- ✅ No user-visible inconsistencies between tools
- ✅ Real-time updates in both CLI and TUI
- ✅ Performance impact minimal (< 1% CPU, < 10MB memory)
- ✅ Reliable across all supported platforms

### Configuration File Locations by Scope
- **User Scope**: `~/.config/claude-code/mcp-servers.json`, `~/.docker/mcp/registry.yaml`
- **Project Scope**: `./.mcp.json`, `./.mcp-manager.toml`  
- **Internal Scope**: `~/.claude.json`
- **MCP Manager Catalog**: `~/.config/mcp-manager/server_catalog.json`

## Dependencies

- Python 3.8+
- Click for CLI framework
- Textual for TUI framework
- Pydantic for data validation
- aiohttp for async HTTP requests
- pytest for testing framework
- **NEW**: watchdog for file system monitoring
- **NEW**: pyyaml for Docker registry parsing