# MCP Manager Comprehensive Test Plan

## 📋 Overview

This document provides **complete step-by-step instructions** for testing MCP Manager in both Direct Mode (traditional) and Proxy Mode (unified endpoint). This guide assumes **zero technical knowledge** and provides every command, option, and verification step needed.

**What we're testing:**
- ✅ Direct Mode (current behavior) - unchanged functionality
- ✅ Analytics CLI commands - comprehensive usage analytics
- ✅ Tools CLI commands - tool registry search and management
- ✅ Docker Desktop tool discovery - 35+ tools from unified gateway
- ✅ Workflow management - task-specific MCP configurations
- ✅ Proxy Mode (new feature) - unified MCP endpoint
- ✅ Mode switching between Direct/Proxy/Hybrid modes
- ✅ Backward compatibility (existing workflows still work)
- ✅ DEBUG mode setup and logging

---

## 🛠️ Prerequisites & Setup

### Step 1: System Requirements Check

**Before starting, verify you have:**

1. **Python 3.8 or newer**
   ```bash
   python3 --version
   ```
   - Expected output: `Python 3.8.x` or higher
   - If not installed: Visit https://python.org/downloads

2. **Git installed**
   ```bash
   git --version
   ```
   - Expected output: `git version 2.x.x`
   - If not installed: Visit https://git-scm.com/downloads

3. **Claude Code CLI installed**
   ```bash
   claude --version
   ```
   - Expected output: Version number
   - If not installed: Visit https://docs.anthropic.com/claude/docs/claude-code

4. **Docker Desktop (optional, for Docker MCP servers)**
   ```bash
   docker --version
   docker mcp --help
   ```
   - Expected output: Docker version and MCP help text
   - If not installed: Visit https://www.docker.com/products/docker-desktop/

### Step 2: Install MCP Manager

**Complete installation from scratch:**

1. **Open Terminal/Command Prompt**
   - **macOS**: Press `Cmd + Space`, type "Terminal", press Enter
   - **Windows**: Press `Win + R`, type "cmd", press Enter
   - **Linux**: Press `Ctrl + Alt + T`

2. **Navigate to your projects folder**
   ```bash
   cd ~/Projects
   ```
   - If folder doesn't exist: `mkdir -p ~/Projects && cd ~/Projects`

3. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/mcp-manager.git
   cd mcp-manager
   ```

4. **Install MCP Manager**
   ```bash
   pip install -e .
   ```
   - **Expected output**: Installation messages ending with "Successfully installed..."
   - **If error**: Try `pip3 install -e .` instead

5. **Verify installation**
   ```bash
   mcp-manager --version
   ```
   - **Expected output**: Version number
   - **If command not found**: Add to PATH or use `python -m mcp_manager` instead

6. **Enable DEBUG mode (optional but recommended for testing)**
   ```bash
   export MCP_MANAGER_LOG_LEVEL=DEBUG
   export MCP_MANAGER_DEBUG=true
   ```
   - **Enable detailed logging**: All operations will be logged in detail
   - **Check debug status**: `mcp-manager config` should show debug settings
   - **View debug logs**: `tail -f ~/.config/mcp-manager/logs/mcp-manager.log`

### Step 3: Backup Existing Configuration

**IMPORTANT: Backup your current Claude Code configuration**

1. **Check if Claude Code config exists**
   ```bash
   ls ~/.config/claude-code/
   ```

2. **Create backup (if config exists)**
   ```bash
   cp ~/.config/claude-code/mcp-servers.json ~/.config/claude-code/mcp-servers.json.backup.$(date +%Y%m%d_%H%M%S)
   ```

3. **Create backup of Claude's internal state**
   ```bash
   cp ~/.claude.json ~/.claude.json.backup.$(date +%Y%m%d_%H%M%S)
   ```

4. **Setup DEBUG environment (recommended)**
   ```bash
   # Create debug configuration directory
   mkdir -p ~/.config/mcp-manager/logs
   
   # Enable comprehensive debug logging
   export MCP_MANAGER_LOG_LEVEL=DEBUG
   export MCP_MANAGER_DEBUG=true
   export MCP_MANAGER_LOG_FILE=~/.config/mcp-manager/logs/test-session.log
   
   # Optional: Enable database query logging
   export MCP_MANAGER_DB_DEBUG=true
   
   # Verify debug setup
   mcp-manager config | grep -i debug
   ```
   - **Expected output**: Should show debug settings are enabled
   - **Log file**: Debug logs will be written to the specified file

---

## 🧪 Test Categories

## Category A: Direct Mode Testing (Traditional Behavior)

### Test A1: Basic Direct Mode Operation

**Purpose**: Verify existing functionality works unchanged

**Steps:**

1. **Ensure Direct Mode is active (default)**
   ```bash
   mcp-manager mode status
   ```
   - **Expected output**: `current_mode: direct`
   - **If different**: Run `mcp-manager mode switch direct`

2. **List existing servers**
   ```bash
   mcp-manager list
   ```
   - **Record output**: Write down all servers shown
   - **Expected**: List of your current MCP servers (may be empty)

3. **Check system status**
   ```bash
   mcp-manager status
   ```
   - **Expected**: Comprehensive system status with 6 panels (Server Status, Tools Registry, Workflow Status, Analytics, System Health, Configuration)
   - **Record**: Server counts, tool counts, workflow status, and any health issues
   - **Note**: This is the new status command we just added

4. **Test server discovery**
   ```bash
   mcp-manager discover --type npm --limit 5
   ```
   - **Expected**: List of 5 available NPM MCP servers
   - **Time it**: Record how long this takes (use stopwatch)

### Test A2: Server Management in Direct Mode

**Steps:**

1. **Add a test server**
   ```bash
   mcp-manager install-package modelcontextprotocol-filesystem
   ```
   - **Expected**: Success message about installation
   - **Wait for completion**: This may take 30-60 seconds

2. **Verify server was added**
   ```bash
   mcp-manager list
   ```
   - **Check**: Filesystem server appears in list
   - **Status**: Should show as "active" or "enabled"

3. **Test Claude Code integration**
   ```bash
   claude mcp list
   ```
   - **Expected**: Filesystem server appears in Claude's list
   - **If error**: Note the exact error message

4. **Test tool discovery**
   ```bash
   mcp-manager tools list --server filesystem
   ```
   - **Expected**: List of tools from filesystem server
   - **Record count**: How many tools were found

### Test A3: Direct Mode Analytics

**Steps:**

1. **Check analytics are working**
   ```bash
   mcp-manager analytics summary --days 1
   ```
   - **Expected**: Analytics summary (may be empty for new installation)

2. **Test tool search**
   ```bash
   mcp-manager tools search "read file"
   ```
   - **Expected**: List of file-related tools
   - **Record results**: Write down what tools were found

---

## Category B: Proxy Mode Testing (New Feature)

### Test B1: Proxy Mode Configuration

**Purpose**: Test optional proxy mode setup

**Steps:**

1. **Check proxy is disabled by default**
   ```bash
   mcp-manager mode status
   ```
   - **Expected**: `proxy_available: false` or `proxy_enabled: false`

2. **Enable proxy mode**
   ```bash
   export MCP_PROXY_MODE=true
   export MCP_PROXY_PORT=3000
   export MCP_PROXY_HOST=localhost
   ```

3. **Verify proxy configuration**
   ```bash
   mcp-manager mode status
   ```
   - **Expected**: `proxy_available: true`
   - **Record**: Full output for reference

4. **Test proxy validation**
   ```bash
   mcp-manager proxy validate
   ```
   - **Expected**: Validation results showing proxy is ready
   - **If errors**: Record exact error messages

### Test B2: Switch to Proxy Mode

**Steps:**

1. **Switch to proxy mode**
   ```bash
   mcp-manager mode switch proxy
   ```
   - **Expected**: Success message about mode switch
   - **If error**: Record exact error and try `mcp-manager mode switch proxy --force`

2. **Start proxy server**
   ```bash
   mcp-manager proxy start --daemon
   ```
   - **Expected**: Message about proxy server starting
   - **Wait**: Give it 10 seconds to fully start

3. **Check proxy status**
   ```bash
   mcp-manager proxy status
   ```
   - **Expected**: Shows proxy running on port 3000
   - **Record**: Endpoint URL provided

4. **Verify proxy is responding**
   ```bash
   curl -X GET http://localhost:3000/health
   ```
   - **Expected**: JSON response with status "healthy"
   - **If curl not found**: Use your browser and go to `http://localhost:3000/health`

### Test B3: Proxy Mode Functionality

**Steps:**

1. **Test tool listing through proxy**
   ```bash
   curl -X POST http://localhost:3000/mcp/v1/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
   ```
   - **Expected**: JSON response with list of available tools
   - **Record**: Number of tools returned

2. **Test specific tool call through proxy**
   ```bash
   curl -X POST http://localhost:3000/mcp/v1/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "filesystem/read_file", "arguments": {"path": "/tmp/test.txt"}}}'
   ```
   - **Expected**: JSON response (may be error if file doesn't exist, that's OK)
   - **Record**: Response type and any error codes

3. **Test proxy analytics**
   ```bash
   mcp-manager proxy analytics --hours 1
   ```
   - **Expected**: Analytics showing proxy requests
   - **Should show**: The curl requests you just made

---

## Category C: Hybrid Mode Testing

### Test C1: Hybrid Mode Setup

**Purpose**: Test running both Direct and Proxy modes simultaneously

**Steps:**

1. **Enable hybrid mode**
   ```bash
   export MCP_PROXY_MODE=true
   export MCP_ENABLE_DIRECT_MODE=true
   ```

2. **Switch to hybrid mode**
   ```bash
   mcp-manager mode switch hybrid
   ```
   - **Expected**: Success message
   - **Record**: Any warnings or messages

3. **Verify both modes active**
   ```bash
   mcp-manager mode status
   ```
   - **Expected**: `current_mode: hybrid`
   - **Check**: Both `direct_available: true` and `proxy_available: true`

### Test C2: Test Both Modes Working

**Steps:**

1. **Test direct mode still works**
   ```bash
   mcp-manager list
   ```
   - **Expected**: Same server list as before
   - **Compare**: Should match results from Test A1

2. **Test proxy mode still works**
   ```bash
   curl -X GET http://localhost:3000/health
   ```
   - **Expected**: Healthy response
   - **Should match**: Results from Test B2

3. **Test Claude Code integration in hybrid mode**
   ```bash
   claude mcp list
   ```
   - **Expected**: Shows both individual servers AND proxy endpoint
   - **Record**: Total count of available servers

---

## Category D: Mode Switching & Compatibility

### Test D1: Safe Mode Switching

**Purpose**: Test switching between modes without breaking anything

**Steps:**

1. **Switch from Hybrid to Direct**
   ```bash
   mcp-manager mode switch direct
   ```
   - **Expected**: Success message
   - **Check**: Proxy should stop automatically

2. **Verify Direct Mode**
   ```bash
   mcp-manager mode status
   ```
   - **Expected**: `current_mode: direct`
   - **Expected**: `proxy_available: false` (or proxy stopped)

3. **Verify existing functionality still works**
   ```bash
   mcp-manager list
   ```
   - **Expected**: Same servers as before
   - **Compare**: Should match previous test results

4. **Switch back to Proxy Mode**
   ```bash
   mcp-manager mode switch proxy
   ```
   - **Expected**: Success message
   - **Expected**: Proxy starts automatically

5. **Verify Proxy Mode works again**
   ```bash
   curl -X GET http://localhost:3000/health
   ```
   - **Expected**: Healthy response
   - **Should work**: Just like before

### Test D2: Error Handling & Recovery

**Steps:**

1. **Test invalid mode switch**
   ```bash
   mcp-manager mode switch invalid_mode
   ```
   - **Expected**: Clear error message about invalid mode
   - **Should not crash**: Command should fail gracefully

2. **Test switching with port conflict**
   ```bash
   # Start something on port 3000 (simulate conflict)
   python3 -m http.server 3000 &
   SERVER_PID=$!
   
   # Try to switch to proxy mode
   mcp-manager mode switch proxy
   ```
   - **Expected**: Error about port being unavailable
   - **Cleanup**: `kill $SERVER_PID`

3. **Test force mode switch**
   ```bash
   mcp-manager mode switch proxy --force
   ```
   - **Expected**: Should work even with validation warnings
   - **Use carefully**: Only use --force when instructed

---

## Category E: Performance & Load Testing

### Test E1: Performance Comparison

**Purpose**: Compare Direct Mode vs Proxy Mode performance

**Steps:**

1. **Time Direct Mode tool discovery**
   ```bash
   mcp-manager mode switch direct
   time mcp-manager tools list --limit 50
   ```
   - **Record time**: Write down the "real" time shown
   - **Record count**: Number of tools found

2. **Time Proxy Mode tool discovery**
   ```bash
   mcp-manager mode switch proxy
   time curl -X POST http://localhost:3000/mcp/v1/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"limit": 50}}'
   ```
   - **Record time**: Compare with direct mode
   - **Record count**: Should be same number of tools

3. **Test concurrent requests to proxy**
   ```bash
   # Run 5 requests simultaneously
   for i in {1..5}; do
     curl -X GET http://localhost:3000/health &
   done
   wait
   ```
   - **Expected**: All requests should complete successfully
   - **Record**: Any errors or timeouts

### Test E2: Resource Usage

**Steps:**

1. **Check memory usage in Direct Mode**
   ```bash
   mcp-manager mode switch direct
   ps aux | grep mcp-manager
   ```
   - **Record**: Memory usage (RSS column)

2. **Check memory usage in Proxy Mode**
   ```bash
   mcp-manager mode switch proxy
   ps aux | grep mcp-manager
   ```
   - **Record**: Memory usage and compare
   - **Expected**: Proxy mode may use slightly more memory

---

## Category F: Integration Testing

### Test F1: Claude Code Integration

**Purpose**: Test MCP Manager works with Claude Code in both modes

**Steps:**

1. **Test Direct Mode with Claude Code**
   ```bash
   mcp-manager mode switch direct
   claude mcp list
   ```
   - **Expected**: Lists all your MCP servers
   - **Record**: Server count and names

2. **Try using a tool through Claude Code**
   ```bash
   echo "Test file content" > /tmp/test.txt
   claude --mcp filesystem "Read the file /tmp/test.txt"
   ```
   - **Expected**: Claude should read and display file content
   - **If error**: Record exact error message

3. **Test Proxy Mode with Claude Code**
   ```bash
   mcp-manager mode switch proxy
   claude mcp list
   ```
   - **Expected**: Should show proxy endpoint as one of the servers
   - **Record**: Does it show individual servers or just proxy?

4. **Configure Claude Code to use proxy**
   ```bash
   # This will be automated in final version
   # For now, record what manual steps are needed
   cat ~/.config/claude-code/mcp-servers.json
   ```
   - **Record**: Current configuration for comparison

### Test F2: Third-Party Client Testing

**Steps:**

1. **Test with curl (simulating other MCP clients)**
   ```bash
   # Test MCP protocol initialization
   curl -X POST http://localhost:3000/mcp/v1/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'
   ```
   - **Expected**: JSON response with server capabilities
   - **Record**: Response details

2. **Test resource listing**
   ```bash
   curl -X POST http://localhost:3000/mcp/v1/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}}'
   ```
   - **Expected**: List of available resources
   - **Record**: Number of resources and types

---

## Category H: Analytics CLI Testing

### Test H1: Analytics Summary Command

**Purpose**: Test comprehensive usage analytics functionality

**Steps:**

1. **Test basic analytics summary**
   ```bash
   mcp-manager analytics summary
   ```
   - **Expected**: Rich formatted summary with usage statistics
   - **Record**: Number of servers, tools, and usage patterns shown

2. **Test analytics with custom time range**
   ```bash
   mcp-manager analytics summary --days 30
   ```
   - **Expected**: 30-day analytics summary
   - **Compare**: Should show more historical data than default 7-day view

3. **Test analytics with no data**
   ```bash
   # On fresh installation
   mcp-manager analytics summary
   ```
   - **Expected**: Graceful handling of empty analytics
   - **Should show**: "No usage data available" or similar message

### Test H2: Analytics Query Command

**Steps:**

1. **Test query analytics**
   ```bash
   mcp-manager analytics query --query "filesystem operations" --limit 10
   ```
   - **Expected**: Analytics for filesystem-related queries
   - **Record**: Number of results and relevance

2. **Test analytics export**
   ```bash
   mcp-manager analytics query --export analytics-export.json
   ```
   - **Expected**: JSON export file created
   - **Verify**: `ls -la analytics-export.json`

---

## Category I: Tools CLI Testing

### Test I1: Tools Search Command

**Purpose**: Test tool discovery and search functionality

**Steps:**

1. **Test basic tool search**
   ```bash
   mcp-manager tools search "file read"
   ```
   - **Expected**: List of file reading tools from all servers
   - **Record**: Number of tools found and server sources

2. **Test search with server filter**
   ```bash
   mcp-manager tools search "database" --server sqlite
   ```
   - **Expected**: Database tools only from SQLite server
   - **Verify**: All results should be from SQLite server

3. **Test search with category filter**
   ```bash
   mcp-manager tools search "*" --category filesystem
   ```
   - **Expected**: All filesystem-related tools
   - **Record**: Tool count and categories shown

### Test I2: Tools List Command

**Steps:**

1. **Test list all tools**
   ```bash
   mcp-manager tools list
   ```
   - **Expected**: Rich table of all available tools
   - **Record**: Total tool count and number of servers

2. **Test list with server filter**
   ```bash
   mcp-manager tools list --server filesystem
   ```
   - **Expected**: Tools only from filesystem server
   - **Verify**: Server column should show only "filesystem"

3. **Test list with limit**
   ```bash
   mcp-manager tools list --limit 5
   ```
   - **Expected**: Only 5 tools shown
   - **Verify**: Table should have exactly 5 rows

---

## Category J: Docker Desktop Tool Discovery Testing

### Test J1: Docker Desktop Integration

**Purpose**: Test the fixed Docker Desktop tool discovery (35+ tools)

**Prerequisites:**
- Docker Desktop installed and running
- At least one MCP server enabled in Docker Desktop

**Steps:**

1. **Enable Docker Desktop MCP servers**
   ```bash
   docker mcp server enable sqlite
   docker mcp server enable filesystem
   docker mcp server list
   ```
   - **Expected**: Shows enabled servers
   - **Record**: Which servers are enabled

2. **Test Docker Desktop tool discovery**
   ```bash
   mcp-manager tools list --server docker-gateway
   ```
   - **Expected**: 35+ tools from Docker Desktop servers
   - **Critical**: Should NOT show 0 tools (this was the bug we fixed)
   - **Record**: Exact tool count and server breakdown

3. **Test specific Docker Desktop server tools**
   ```bash
   mcp-manager discover --type docker-desktop --update-catalog
   ```
   - **Expected**: Discovery of Docker Desktop servers and their tools
   - **Record**: Discovery time and success rate

### Test J2: Docker Desktop vs Regular Docker

**Steps:**

1. **Compare Docker discovery types**
   ```bash
   # Regular Docker containers
   mcp-manager discover --type docker --limit 5
   
   # Docker Desktop unified gateway
   mcp-manager discover --type docker-desktop --limit 5
   ```
   - **Expected**: Different results showing the two discovery types
   - **Record**: Architecture differences as documented in PLAN.md

2. **Test docker-gateway integration**
   ```bash
   claude mcp add-from-claude-desktop docker-gateway
   claude mcp list | grep docker-gateway
   ```
   - **Expected**: docker-gateway appears as unified proxy
   - **Verify**: Shows as single entry representing all enabled DD servers

---

## Category K: Workflow Management Testing

### Test K1: Workflow Templates

**Purpose**: Test the comprehensive workflow management system

**Steps:**

1. **List available workflow templates**
   ```bash
   mcp-manager workflow templates
   ```
   - **Expected**: Rich table showing 12+ predefined templates
   - **Record**: Template categories and required servers

2. **Install a workflow template**
   ```bash
   mcp-manager workflow install-template "Web Development Suite"
   ```
   - **Expected**: Template installation with suite creation
   - **Verify**: `mcp-manager workflow list` should show new workflow

3. **Install all viable templates**
   ```bash
   mcp-manager workflow install-all-templates
   ```
   - **Expected**: Installation of all templates with available servers
   - **Record**: How many were installed vs skipped

### Test K2: Workflow Activation and Switching

**Steps:**

1. **Activate a workflow**
   ```bash
   mcp-manager workflow activate "Web Development Suite"
   ```
   - **Expected**: Workflow activation with server configuration changes
   - **Verify**: `mcp-manager workflow status` shows active workflow

2. **Switch workflows by category**
   ```bash
   mcp-manager workflow switch data-analysis
   ```
   - **Expected**: Switches to best data analysis workflow
   - **Record**: Which workflow was selected and why

3. **Test workflow creation**
   ```bash
   mcp-manager workflow create "Custom Test" --description "Test workflow" --suites "suite-1,suite-2" --category automation
   ```
   - **Expected**: Custom workflow creation
   - **Verify**: `mcp-manager workflow list` shows new workflow

### Test K3: Workflow Status and Management

**Steps:**

1. **Check workflow status**
   ```bash
   mcp-manager workflow status
   ```
   - **Expected**: Detailed status with active workflow and suite information
   - **Record**: Active workflow details and server counts

2. **Deactivate workflow**
   ```bash
   mcp-manager workflow deactivate
   ```
   - **Expected**: Workflow deactivation with server cleanup
   - **Verify**: Status should show no active workflow

3. **Delete workflow**
   ```bash
   mcp-manager workflow delete "Custom Test" --force
   ```
   - **Expected**: Workflow deletion without confirmation
   - **Verify**: Should not appear in workflow list

---

## Category L: DEBUG Mode and Logging Testing

### Test L1: DEBUG Mode Setup

**Purpose**: Test comprehensive debug logging and troubleshooting

**Steps:**

1. **Enable DEBUG mode**
   ```bash
   export MCP_MANAGER_LOG_LEVEL=DEBUG
   export MCP_MANAGER_DEBUG=true
   export MCP_MANAGER_LOG_FILE=~/.config/mcp-manager/logs/debug-test.log
   ```
   - **Expected**: Environment variables set
   - **Verify**: `echo $MCP_MANAGER_LOG_LEVEL` should return "DEBUG"

2. **Test debug logging**
   ```bash
   mcp-manager list
   tail -20 ~/.config/mcp-manager/logs/debug-test.log
   ```
   - **Expected**: Detailed debug logs for the list command
   - **Record**: Log detail level and database queries shown

3. **Test database debug mode**
   ```bash
   export MCP_MANAGER_DB_DEBUG=true
   mcp-manager tools search "test"
   tail -30 ~/.config/mcp-manager/logs/debug-test.log | grep -i sql
   ```
   - **Expected**: SQL queries logged in debug output
   - **Record**: Database query logging working

### Test L2: Performance Debugging

**Steps:**

1. **Test timing information**
   ```bash
   time mcp-manager discover --limit 10
   ```
   - **Expected**: Command completion with timing
   - **Record**: Execution time and any performance bottlenecks

2. **Test error debugging**
   ```bash
   # Trigger an error intentionally
   mcp-manager workflow activate "NonExistentWorkflow"
   tail -10 ~/.config/mcp-manager/logs/debug-test.log
   ```
   - **Expected**: Detailed error logging with stack traces
   - **Record**: Error detail level and troubleshooting information

3. **Test concurrent operation debugging**
   ```bash
   # Run multiple commands simultaneously
   mcp-manager tools list &
   mcp-manager analytics summary &
   wait
   grep -i "concurrent\|thread\|async" ~/.config/mcp-manager/logs/debug-test.log
   ```
   - **Expected**: Debug logs showing concurrent operation handling
   - **Record**: Thread safety and async operation logging

---

## Category G: Edge Cases & Error Conditions

### Test G1: Configuration Edge Cases

**Steps:**

1. **Test with invalid proxy port**
   ```bash
   export MCP_PROXY_PORT=99999
   mcp-manager mode switch proxy
   ```
   - **Expected**: Error about invalid port
   - **Should not crash**: Graceful error handling

2. **Test with invalid host**
   ```bash
   export MCP_PROXY_HOST=999.999.999.999
   mcp-manager mode switch proxy
   ```
   - **Expected**: Error about invalid host
   - **Cleanup**: `export MCP_PROXY_HOST=localhost`

3. **Test with missing environment variables**
   ```bash
   unset MCP_PROXY_MODE
   mcp-manager mode status
   ```
   - **Expected**: Should default to Direct Mode
   - **Should work**: No errors

### Test G2: Network & Connection Issues

**Steps:**

1. **Test proxy with no servers available**
   ```bash
   mcp-manager remove --all --force
   mcp-manager mode switch proxy
   curl -X POST http://localhost:3000/mcp/v1/rpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
   ```
   - **Expected**: Empty list of tools (not an error)
   - **Should not crash**: Proxy should handle gracefully

2. **Test stopping proxy while in use**
   ```bash
   mcp-manager proxy stop
   curl -X GET http://localhost:3000/health
   ```
   - **Expected**: Connection refused or timeout
   - **Record**: Exact error message

---

## 📊 Test Results Template

### Use this template to record your test results:

```
# Test Execution Report
Date: _______________
Tester: _______________
MCP Manager Version: _______________
DEBUG Mode Enabled: Yes/No
Log File Location: _______________

## Category A: Direct Mode Testing
[ ] Test A1: Basic Direct Mode Operation
    - Server list count: ___
    - Discovery time: ___ seconds
    - Errors encountered: ___

[ ] Test A2: Server Management
    - Installation successful: Yes/No
    - Tools discovered: ___ count
    - Claude integration: Yes/No

[ ] Test A3: Analytics
    - Analytics working: Yes/No
    - Search results: ___

## Category B: Proxy Mode Testing  
[ ] Test B1: Configuration
    - Proxy enabled: Yes/No
    - Validation passed: Yes/No
    - Errors: ___

[ ] Test B2: Switch to Proxy
    - Mode switch successful: Yes/No
    - Proxy started: Yes/No
    - Health check: Yes/No

[ ] Test B3: Functionality
    - Tool listing works: Yes/No
    - Tool calls work: Yes/No
    - Analytics work: Yes/No

## Category C: Hybrid Mode Testing
[ ] Test C1: Setup
    - Hybrid mode active: Yes/No
    - Both modes available: Yes/No

[ ] Test C2: Both Modes Working
    - Direct mode works: Yes/No
    - Proxy mode works: Yes/No
    - Claude integration: Yes/No

## Category D: Mode Switching
[ ] Test D1: Safe Switching
    - All mode switches successful: Yes/No
    - No data loss: Yes/No

[ ] Test D2: Error Handling
    - Invalid mode handled: Yes/No
    - Port conflicts handled: Yes/No
    - Force switch works: Yes/No

## Category E: Performance Testing
[ ] Test E1: Performance Comparison
    - Direct mode time: ___ seconds
    - Proxy mode time: ___ seconds
    - Concurrent requests: ___/5 successful

[ ] Test E2: Resource Usage
    - Direct mode memory: ___ MB
    - Proxy mode memory: ___ MB

## Category F: Integration Testing
[ ] Test F1: Claude Code Integration
    - Direct mode integration: Yes/No
    - Proxy mode integration: Yes/No
    - Tool usage works: Yes/No

[ ] Test F2: Third-Party Clients
    - MCP protocol compliance: Yes/No
    - Resource listing: Yes/No

## Category G: Edge Cases
[ ] Test G1: Configuration Edge Cases
    - Invalid port handled: Yes/No
    - Invalid host handled: Yes/No
    - Missing env vars handled: Yes/No

[ ] Test G2: Network Issues
    - No servers handled: Yes/No
    - Proxy stop handled: Yes/No

## Category H: Analytics CLI Testing
[ ] Test H1: Analytics Summary Command
    - Basic summary works: Yes/No
    - Custom time range works: Yes/No
    - Empty data handled: Yes/No

[ ] Test H2: Analytics Query Command
    - Query analytics works: Yes/No
    - Export functionality: Yes/No
    - Results count: ___

## Category I: Tools CLI Testing
[ ] Test I1: Tools Search Command
    - Basic search works: Yes/No
    - Server filter works: Yes/No
    - Category filter works: Yes/No
    - Tools found: ___ count

[ ] Test I2: Tools List Command
    - List all tools works: Yes/No
    - Server filter works: Yes/No
    - Limit parameter works: Yes/No
    - Total tools: ___ count

## Category J: Docker Desktop Tool Discovery
[ ] Test J1: Docker Desktop Integration
    - Docker servers enabled: Yes/No
    - Tool discovery works: Yes/No
    - Tools found: ___ (should be 35+)
    - Bug fixed (was showing 0): Yes/No

[ ] Test J2: Docker vs Docker Desktop
    - Architecture distinction clear: Yes/No
    - docker-gateway integration: Yes/No

## Category K: Workflow Management
[ ] Test K1: Workflow Templates
    - Templates list works: Yes/No
    - Template installation works: Yes/No
    - Install all templates works: Yes/No
    - Templates installed: ___ count

[ ] Test K2: Workflow Activation
    - Workflow activation works: Yes/No
    - Category switching works: Yes/No
    - Custom workflow creation: Yes/No

[ ] Test K3: Workflow Management
    - Status display works: Yes/No
    - Deactivation works: Yes/No
    - Deletion works: Yes/No

## Category L: DEBUG Mode and Logging
[ ] Test L1: DEBUG Mode Setup
    - DEBUG mode enabled: Yes/No
    - Debug logging works: Yes/No
    - Database debug works: Yes/No

[ ] Test L2: Performance Debugging
    - Timing information: Yes/No
    - Error debugging: Yes/No
    - Concurrent operations: Yes/No

## Overall Results
Total Test Categories: 12
Total Tests Passed: ___/48
Failed: ___
Critical Issues: ___

## NEW FUNCTIONALITY VALIDATION
✅ Analytics CLI Commands: Pass/Fail
✅ Tools CLI Commands: Pass/Fail  
✅ Docker Desktop Tool Discovery (35+ tools): Pass/Fail
✅ Workflow Management System: Pass/Fail
✅ DEBUG Mode and Logging: Pass/Fail

## Critical Issues Found
1. _______________
2. _______________
3. _______________

## Performance Benchmarks
- Analytics summary time: ___ seconds
- Tools search time: ___ seconds
- Docker tool discovery time: ___ seconds
- Workflow activation time: ___ seconds

## DEBUG Log Analysis
- Log file size: ___ MB
- Database queries logged: Yes/No
- Error stack traces complete: Yes/No
- Performance bottlenecks identified: ___

## Recommendations
1. _______________
2. _______________
3. _______________
```

---

## 🚨 Troubleshooting Guide

### Common Issues & Solutions

**Issue**: `mcp-manager: command not found`
**Solution**: 
```bash
pip install -e .
# OR add to PATH:
export PATH="$HOME/.local/bin:$PATH"
```

**Issue**: `Permission denied` errors
**Solution**: 
```bash
# Try with --user flag
pip install --user -e .
```

**Issue**: Proxy won't start (port in use)
**Solution**: 
```bash
# Find what's using the port
lsof -i :3000
# Kill the process or use different port
export MCP_PROXY_PORT=3001
```

**Issue**: Claude Code not recognizing changes
**Solution**: 
```bash
# Restart Claude Code completely
pkill claude
# Wait 5 seconds, then restart
claude --version
```

**Issue**: Tests failing with timeout
**Solution**: 
```bash
# Increase timeout
export MCP_PROXY_TIMEOUT=60
# Or test with smaller data sets
```

**Issue**: DEBUG logs not appearing
**Solution**: 
```bash
# Ensure debug environment is set
export MCP_MANAGER_LOG_LEVEL=DEBUG
export MCP_MANAGER_DEBUG=true
# Check log file permissions
ls -la ~/.config/mcp-manager/logs/
# Manually create log directory if needed
mkdir -p ~/.config/mcp-manager/logs
```

**Issue**: Workflow templates not installing
**Solution**: 
```bash
# Check available servers first
mcp-manager list
# Install required servers for templates
mcp-manager install-package modelcontextprotocol-filesystem
# Then retry template installation
mcp-manager workflow install-all-templates
```

**Issue**: Docker Desktop tools showing 0 count
**Solution**: 
```bash
# Ensure Docker Desktop is running
docker --version
# Enable at least one MCP server in Docker Desktop
docker mcp server enable sqlite
# Update tool discovery cache
mcp-manager discover --type docker-desktop --update-catalog
```

---

## 📞 Getting Help

**If you encounter issues:**

1. **Record everything**: Copy exact error messages
2. **Include context**: What command you ran, what you expected
3. **Check logs**: `mcp-manager logs --tail 50`  
4. **Report systematically**: Use the test results template above

**For urgent issues:**
- Check the `troubleshooting` section above
- Look for similar issues in existing documentation
- Include your test results template when asking for help

---

**End of Test Plan**

*This test plan covers all aspects of MCP Manager's dual-mode functionality. Follow every step carefully and record all results. The goal is to ensure both Direct Mode (existing functionality) and Proxy Mode (new feature) work perfectly together without breaking anything.*