# MCP Manager Comprehensive Test Plan

## 📋 Overview

This document provides **complete step-by-step instructions** for testing MCP Manager in both Direct Mode (traditional) and Proxy Mode (unified endpoint). This guide assumes **zero technical knowledge** and provides every command, option, and verification step needed.

**What we're testing:**
- ✅ Direct Mode (current behavior) - unchanged functionality
- ✅ Proxy Mode (new feature) - unified MCP endpoint
- ✅ Mode switching between Direct/Proxy/Hybrid modes
- ✅ Backward compatibility (existing workflows still work)

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
   - **Expected**: System information and health status
   - **Record any errors**: Write them down for later comparison

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

## Overall Results
Total Tests: ___
Passed: ___
Failed: ___
Critical Issues: ___

## Critical Issues Found
1. _______________
2. _______________
3. _______________

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