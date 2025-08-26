# MCP Manager for macOS

A native Swift macOS application for managing MCP (Model Context Protocol) servers used by Claude Code. This application provides a professional, native macOS experience for discovering, installing, configuring, and managing MCP servers.

## Features

### Core Functionality
- **Native Server Management**: Add, remove, enable/disable MCP servers directly through native Swift code
- **Real-time Status Monitoring**: Check server connection status and health using Claude CLI integration
- **Bulk Operations**: Enable/disable all servers, remove multiple servers at once
- **Professional macOS UI**: NavigationSplitView with sidebar and detail views following Apple HIG

### Database Integration
- **Shared Database**: Uses the EXACT same SQLite database as the Python CLI (`~/.local/share/mcp-manager/server_state.db`)
- **Schema Compatibility**: Native Swift models that match Python CLI's ServerInfo and ServerStatus exactly
- **No CLI Dependencies**: All server operations implemented natively in Swift (except status checking)

### Server Types Supported
- **NPM Servers**: JavaScript/TypeScript servers installed via npm
- **Docker Servers**: Containerized servers via Docker
- **Docker Desktop Servers**: Pre-built servers available through Docker Desktop
- **Custom Servers**: User-defined servers with custom commands

### Professional UI Features
- **NavigationSplitView**: Modern macOS three-pane interface
- **Search & Filtering**: Filter by server type, scope, status, and text search
- **Status Overview**: Real-time dashboard showing server counts and health
- **Bulk Selection**: Multi-select servers for batch operations
- **Context Menus**: Right-click actions for server management
- **Preferences**: Configurable settings and database management

## Architecture

### No Python CLI Calls
Unlike previous implementations, this native Swift app does NOT call Python CLI commands for server management. The only exception is using `claude mcp list` for status checking.

### Database Layer
- **Direct SQLite Access**: Uses SQLite.swift for direct database operations
- **Schema Matching**: Implements the exact same database schema as Python CLI
- **Foreign Key Support**: Proper relationships and constraints
- **Transaction Safety**: WAL mode for concurrent access

### Service Layer
- **MCPServerService**: Main business logic service with @MainActor
- **DatabaseManager**: Direct SQLite operations with exact Python CLI schema
- **ClaudeService**: Limited to status checking only via `claude mcp list`

## Building and Running

### Requirements
- macOS 14+ (Sonoma or later)
- Swift 5.9+
- Xcode 15+

### Build
```bash
cd MCP-Manager-macOS
swift build
```

### Run
```bash
swift run
```

### Tests
```bash
swift test
```

All tests use isolated temporary databases to avoid interfering with the shared database.

## Project Structure

```
MCP-Manager-macOS/
├── Package.swift              # Swift Package Manager configuration
├── Sources/
│   ├── App.swift             # Main application entry point
│   ├── Models/
│   │   └── MCPServer.swift   # Core data models matching Python CLI
│   ├── Database/
│   │   └── DatabaseManager.swift # Direct SQLite operations
│   ├── Services/
│   │   └── MCPServerService.swift # Business logic service
│   └── Views/
│       ├── ContentView.swift      # Main app layout
│       ├── ServerListView.swift   # Server listing with search/filter
│       ├── ServerDetailView.swift # Individual server details
│       ├── AddServerSheet.swift   # Add new server modal
│       ├── EditServerSheet.swift  # Edit server modal
│       ├── PreferencesView.swift  # App preferences
│       └── ServerLogsView.swift   # Server logs and history
└── Tests/
    └── DatabaseManagerTests.swift # Unit tests
```

## Database Schema

The app uses the exact same database schema as the Python CLI:

### Main Tables
- **mcp_server_registry**: Core server information
- **mcp_connection_history**: Server status and health history  
- **mcp_usage_events**: Server usage analytics
- **mcp_server_requirements**: Server-specific requirements

### Compatibility
This ensures perfect compatibility between the Swift app and Python CLI - both can read and modify the same servers seamlessly.

## Integration with Claude Code

The app integrates with Claude Code by:

1. **Reading Server Status**: Uses `claude mcp list` to get current server statuses
2. **Syncing Configuration**: Updates Claude's internal configuration when servers are modified
3. **Shared Database**: Both tools work with the same server registry

## Key Differences from Python GUI

### What's Better
- **Native Performance**: True native macOS app with better performance
- **Modern UI**: SwiftUI with NavigationSplitView and modern macOS patterns
- **No Python Dependencies**: Self-contained Swift application
- **Type Safety**: Full Swift type safety and compile-time checks
- **Professional Look**: Follows Apple Human Interface Guidelines

### What's the Same
- **Exact Database Schema**: 100% compatible with Python CLI database
- **All Functionality**: Every feature from Python CLI is implemented
- **Server Types**: Supports all the same server types and configurations

## Development Notes

### Testing
- All tests use isolated databases to avoid conflicts
- Comprehensive test coverage for database operations
- Tests verify schema compatibility with Python CLI

### Error Handling
- Proper Swift error handling throughout
- User-friendly error messages
- Graceful degradation when services are unavailable

### Logging
- Structured logging for debugging
- Database operation logging
- Server management event logging

## Future Enhancements

- Menu bar status integration
- Real-time server monitoring
- Server discovery from additional sources
- Export/import server configurations
- Advanced server analytics and reporting

## License

This project follows the same license as the main MCP Manager project.