# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Claude MCP Manager - a CLI tool for managing MCP (Model Context Protocol) servers used by Claude Code. The tool manages configurations for both Docker Desktop MCP servers and NPM-based MCP servers.

## Key Concepts

### MCP Servers
- **Docker Desktop MCP Servers**: Pre-built servers available through Docker Desktop (puppeteer, search, http, k8s, terraform, aws)
- **NPM MCP Servers**: JavaScript/TypeScript servers installed via npm (playwright, filesystem, sqlite)
- **Custom MCP Servers**: User-defined servers with custom commands

### Configuration Files
The tool manages three configuration levels:
1. `~/.config/mcp-manager/servers.json` - User-level server registry
2. `./.mcp-config.json` - Project-level overrides (in working directory)
3. `~/.config/claude-code/mcp-servers.json` - Claude Code integration config

## Implementation Structure

The project should include:
- `install.sh` - Installation script that sets up the tool, PATH, and shell aliases
- `mcp-manager` - Main executable script (likely Bash) that handles all commands
- Supporting scripts for specific functionality (if needed)

## Core Commands to Implement

```bash
# Server management
mcp-manager list                          # List all servers and status
mcp-manager enable <server-name>          # Enable a server
mcp-manager disable <server-name>         # Disable a server
mcp-manager add <name> <type> <command>   # Add custom server

# Docker MCP specific
mcp-manager list dmcp                     # List available Docker MCP servers
mcp-manager add dmcp <server-name>        # Add Docker MCP server

# Configuration
mcp-manager project <server> <enabled>    # Set project-level override
mcp-manager aliases                       # Generate shell aliases
```

## Key Features to Implement

1. **Dynamic Docker Discovery**: Query Docker Desktop to find available MCP servers
2. **JSON Configuration Management**: Read/write JSON configs maintaining proper structure
3. **Shell Alias Generation**: Create shortcuts like `mcp-docker-puppeteer-on`
4. **Claude Code Integration**: Update `~/.config/claude-code/mcp-servers.json` when servers change

## Implementation Notes

- Docker MCP servers use the command format: `docker run -i --rm --pull always mcp-docker-desktop/server-name:latest`
- NPM servers typically use: `npx -y @package/name`
- The tool should validate server availability before enabling
- Project overrides should merge with (not replace) user configuration
- Shell aliases should be idempotent and handle both individual and group controls

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