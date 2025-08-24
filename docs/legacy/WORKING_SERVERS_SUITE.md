# Working Servers Suite

This suite demonstrates that all three MCP server types are working correctly with version 2.0.0.

## Suite: working-servers

**Description**: Suite with verified working servers from all three types: Docker Desktop, NPM, and Docker Hub
**Category**: integration-test
**Suite ID**: working-servers

## Verified Working Servers

### 1. Docker Desktop Servers (via docker-gateway)
- **SQLite** (priority: 90, role: primary)
- **Ref** (priority: 75, role: secondary)
- **aws-diagram** (active in docker-gateway)
- **filesystem** (active in docker-gateway)

**Connection**: All Docker Desktop servers connect through a single `docker-gateway` using:
```
docker mcp gateway run --servers Ref,SQLite,aws-diagram,filesystem
```

### 2. NPM Servers
- **notion-mcp** (priority: 85, role: primary)
  - Package: `@notionhq/notion-mcp-server`
  - Command: `npx -y @notionhq/notion-mcp-server --`
  - Tools: 19 Notion API tools

### 3. Docker Hub Servers
- **fetch** (priority: 80, role: primary)
  - Package: `mcp/fetch`
  - Command: `docker run -i --rm --pull always mcp/fetch:latest`
  - Tools: URL fetching and content extraction

## Connection Status

All servers show "✓ Connected" status in `claude mcp list`:

```bash
$ claude mcp list
Checking MCP server health...

docker-gateway: /opt/homebrew/bin/docker mcp gateway run --servers Ref,SQLite,aws-diagram,filesystem - ✓ Connected
notion-mcp: npx -y @notionhq/notion-mcp-server -- - ✓ Connected
fetch: docker run -i --rm --pull always mcp/fetch:latest - ✓ Connected
```

## Usage

To install this complete suite:
```bash
mcp-manager install-suite --suite-name working-servers
```

To list all servers:
```bash
mcp-manager list
```

To show suite details:
```bash
mcp-manager suite show working-servers
```

## Architecture Verification

This suite proves that:
1. ✅ **Docker Desktop architecture** works correctly (individual servers enabled, aggregated via docker-gateway)
2. ✅ **NPM servers** install and connect directly via npx
3. ✅ **Docker Hub servers** install and connect directly via docker run
4. ✅ **All server types** can coexist and work simultaneously
5. ✅ **Discovery and installation** works for all three types
6. ✅ **Suite management** can organize servers by type and priority

This demonstrates that the basic MCP Manager functionality is working correctly with proper server connectivity.