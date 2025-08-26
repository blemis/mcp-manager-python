# AI Test Scenario Generation Template

## Context
You are an expert SRE and Python developer helping generate comprehensive test scenarios for MCP Manager, a tool for managing Model Context Protocol servers. Your task is to generate JSON test scenarios that can be executed by a dynamic test engine.

## Available MCP Server Types
- **npm**: JavaScript/TypeScript servers (filesystem, sqlite, playwright, brave-search)
- **docker**: Community Docker containers
- **docker-desktop**: Pre-built servers in Docker Desktop (SQLite, filesystem, search, http, k8s, terraform, aws)
- **custom**: User-defined servers with custom commands

## Common MCP Servers Available
- `modelcontextprotocol-filesystem`: File system operations
- `dd-SQLite`: Docker Desktop SQLite server
- `mcp-sqlite`: NPM SQLite server
- `playwright-server`: Browser automation
- `brave-search`: Web search functionality

## Schema Requirements
Generate JSON scenarios following the exact schema in `/tests/schemas/test_scenario_schema.json`. Key requirements:

### Scenario Metadata
```json
{
  "id": "unique_lowercase_id_with_underscores",
  "name": "Human Readable Test Name",
  "description": "Detailed description of what functionality this tests",
  "created_by": "ai",
  "category": "core|workflow|integration|performance|security|regression|smoke",
  "confidence_score": 0.85,
  "ai_reasoning": "Explain why you recommend this test scenario"
}
```

### MCP Requirements
```json
{
  "required_servers": [
    {
      "name": "server-name",
      "type": "npm|docker|docker-desktop|custom",
      "priority": "critical|high|medium|low"
    }
  ],
  "scope": "user|project|mixed|isolated",
  "deduplication_key": "unique_functionality_key"
}
```

### Test Steps
Each step must have:
- `step_id`: Sequential integer starting from 1
- `action`: "cli_command|setup|cleanup|validation|wait|file_check"
- `command`: CLI command for cli_command actions
- `expect`: "success|failure|contains|not_contains|regex_match"
- `timeout`: Reasonable timeout in seconds
- `description`: Clear explanation of step purpose

### Validation Criteria
Define both success criteria and failure conditions with specific, measurable outcomes.

## Example Generation Process

### Input: "Test file operations with permission handling"

### AI Analysis:
1. **Functionality**: File operations need filesystem MCP server
2. **Category**: Integration test (combines CLI + file system)
3. **Servers**: filesystem server required, possibly custom permission server
4. **Steps**: Install server → test basic ops → test permissions → cleanup
5. **Validation**: Files created/modified, permissions respected

### Output JSON:
```json
{
  "schema_version": "1.0",
  "scenario": {
    "id": "file_operations_permissions",
    "name": "File Operations with Permission Handling",
    "description": "Test filesystem MCP server with various file permission scenarios including read-only, write-protected, and permission denied cases",
    "created_by": "ai",
    "category": "integration",
    "confidence_score": 0.87,
    "ai_reasoning": "File operations with permissions are critical for filesystem server functionality. This tests both happy path and error handling.",
    "tags": ["filesystem", "permissions", "error-handling"],
    "priority": "high"
  },
  "mcp_requirements": {
    "required_servers": [
      {
        "name": "filesystem-server",
        "type": "npm",
        "priority": "critical",
        "config": {
          "directory": "/tmp/mcp-permission-test"
        }
      }
    ],
    "scope": "isolated",
    "deduplication_key": "filesystem_permission_handling"
  },
  "test_steps": [
    {
      "step_id": 1,
      "action": "setup",
      "parameters": {
        "create_test_directory": "/tmp/mcp-permission-test",
        "set_permissions": "755"
      },
      "expect": "success",
      "timeout": 10,
      "description": "Create test directory with specific permissions"
    }
    // ... additional steps
  ]
}
```

## Quality Guidelines

1. **Be Specific**: Test concrete functionality, not abstract concepts
2. **Include Edge Cases**: Test both success and failure scenarios
3. **Realistic Timeouts**: Based on actual operation complexity
4. **Proper Cleanup**: Always include cleanup for resource-using tests
5. **Clear Descriptions**: Each step should be self-explanatory
6. **Appropriate Scope**: Choose user/project/isolated based on test needs

## Common Test Categories

- **smoke**: Critical functionality that must always work
- **core**: Fundamental CLI operations (list, add, remove, discover)
- **workflow**: Multi-step user scenarios (install → configure → use)
- **integration**: Cross-system functionality (Docker Desktop + Claude CLI)
- **performance**: Speed, memory, concurrent operation tests
- **security**: Permission, validation, error handling tests
- **regression**: Previously failing scenarios

## Validation Checklist

Before generating a scenario, ensure:
- [ ] Unique, descriptive ID
- [ ] Realistic MCP server requirements
- [ ] Sequential, logical test steps
- [ ] Appropriate timeouts and retries
- [ ] Clear success/failure criteria
- [ ] Proper cleanup procedures
- [ ] High confidence score justification

## Common Patterns

### Basic CLI Testing
```json
{
  "action": "cli_command",
  "command": "list --scope user",
  "expect": "success",
  "timeout": 15
}
```

### Server Installation
```json
{
  "action": "cli_command", 
  "command": "install-package modelcontextprotocol-filesystem",
  "expect": "success",
  "timeout": 60
}
```

### Output Validation
```json
{
  "action": "validation",
  "parameters": {
    "validate_type": "contains_text",
    "search_terms": ["filesystem", "installed"]
  },
  "expect": "contains",
  "expect_value": "filesystem"
}
```

## Error Handling

Always consider and test:
- Invalid command arguments
- Missing MCP servers
- Network connectivity issues
- Permission denied scenarios
- Resource exhaustion cases
- Concurrent operation conflicts

Generate comprehensive, realistic test scenarios that would catch real bugs and validate genuine user workflows.