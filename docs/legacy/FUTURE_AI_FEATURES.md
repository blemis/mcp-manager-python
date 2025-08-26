# MCP Manager: AI-Powered Testing System Implementation Plan

## Current Status: Transitioning to Fully Dynamic JSON-Based Testing

### Architecture Decision: Option 2 - Fully Dynamic Approach
- **Single dynamic test engine** that executes JSON test scenarios
- **No hardcoded pytest classes** - everything is data-driven via JSON
- **AI generates JSON test scenarios** instead of code
- **Perfect foundation** for AI test recommendations

## Phase 1: Core JSON Testing Infrastructure (Current Priority)

### 1. JSON Schema Design for Test Scenarios
**Status**: 🔄 Pending
**Priority**: High

Design comprehensive JSON schema that AI will use to generate test recommendations:

```json
{
  "schema_version": "1.0",
  "scenario": {
    "id": "unique_scenario_id",
    "name": "Human readable name",
    "description": "What this scenario tests",
    "created_by": "ai|admin|system",
    "category": "core|workflow|integration|performance",
    "confidence_score": 0.95,
    "ai_reasoning": "Why AI recommended this scenario"
  },
  "mcp_requirements": {
    "required_servers": [
      {"name": "filesystem-server", "type": "npm", "priority": "high"},
      {"name": "custom-test-server", "type": "custom", "priority": "medium"}
    ],
    "optional_servers": [],
    "scope": "user|project|mixed",
    "deduplication_key": "filesystem_operations_basic"
  },
  "test_steps": [
    {
      "step_id": 1,
      "action": "cli_command",
      "command": "mcp-manager list",
      "expect": "success|failure|contains:text",
      "timeout": 30,
      "setup_required": true
    }
  ],
  "validation": {
    "success_criteria": [],
    "failure_conditions": [],
    "cleanup_required": true
  }
}
```

### 2. Dynamic Test Engine
**Status**: 🔄 Pending  
**Priority**: High

Single test engine that can execute any JSON scenario:
- Parse JSON test scenarios
- Load appropriate MCP suites
- Execute test steps dynamically
- Report results in standardized format

### 3. Scenario Conversion
**Status**: 🔄 Pending
**Priority**: High

Convert ALL existing test scenarios to JSON format:
- ✅ Basic Commands → `scenarios/core/basic_commands.json`
- ✅ Server Management → `scenarios/core/server_management.json`  
- ✅ Suite Management → `scenarios/core/suite_management.json`
- ✅ Error Handling → `scenarios/core/error_handling.json`
- ✅ Workflows → `scenarios/core/workflows.json`
- ✅ Quality Tracking → `scenarios/core/quality_tracking.json`

## Phase 2: AI Integration Infrastructure

### 4. AI Recommendation Parser
**Status**: 🔄 Pending
**Priority**: High

System to consume AI-generated test scenarios:
- Validate JSON schema compliance
- Parse MCP server requirements
- Extract test steps and validation criteria
- Handle AI confidence scores and reasoning

### 5. MCP Deduplication & Filtering
**Status**: 🔄 Pending - Need to check existing systems
**Priority**: Medium

Quality control for AI recommendations:
- Deduplicate similar MCP server requirements
- Filter out invalid/risky test scenarios
- Validate MCP server availability
- Quality scoring for test scenarios

### 6. AI Prompt Engineering
**Status**: 🔄 Pending
**Priority**: Medium

Templates for AI to generate test scenarios:
- Standard prompt format for consistency
- Context about available MCP servers
- Example JSON outputs for training
- Validation rules and constraints

## Phase 3: Advanced AI Features

### 7. Natural Language Test Generation
**Flow**:
```
User: "I want to test file operations with different permissions"
AI: Generates comprehensive JSON scenario with:
- filesystem MCP server
- permission testing servers
- Error simulation scenarios
- Validation steps
```

### 8. Smart Learning System
- Analyze test execution results
- Learn from successful/failed scenarios
- Improve future recommendations
- Optimize MCP suite compositions

### 9. Advanced Quality Control
- Detect test coverage gaps
- Recommend additional test scenarios
- Suggest MCP server optimizations
- Performance impact analysis

## Technical Architecture

### Directory Structure
```
tests/
├── engine/
│   ├── test_engine.py              # Single dynamic test executor
│   ├── scenario_parser.py          # JSON scenario parser
│   └── result_reporter.py          # Standardized reporting
├── scenarios/
│   ├── core/                       # Static core scenarios (converted from pytest)
│   │   ├── basic_commands.json
│   │   ├── server_management.json
│   │   └── suite_management.json
│   ├── ai_generated/               # AI-created scenarios
│   │   └── file_permissions_20250725.json
│   └── admin_created/              # Admin-created scenarios
│       └── custom_workflow.json
├── ai_integration/
│   ├── scenario_generator.py       # AI scenario generation
│   ├── recommendation_parser.py    # Parse AI outputs
│   ├── quality_filter.py          # Filter bad recommendations
│   └── templates/                  # AI prompt templates
└── suites/                        # MCP server suite definitions
```

### Integration Points
- **Existing AI Infrastructure**: Leverage `AIToolRecommendationManager`
- **MCP Suite System**: Use existing suite management
- **Quality System**: Integrate with existing quality tracking
- **Admin Interface**: Extend CLI for scenario management

## Current Blockers & Dependencies

1. **JSON Schema Design** - Need to finalize schema before AI integration
2. **Test Engine Implementation** - Core foundation for everything else
3. **Scenario Conversion** - Must convert existing tests to establish baseline
4. **AI Prompt Templates** - Need clear format for AI to follow

## Success Metrics

- **100% scenario coverage** - All current tests converted to JSON
- **AI recommendation accuracy** - >90% valid scenarios generated
- **Zero code changes** for new test types - Pure JSON configuration
- **Performance** - Test execution time comparable to current system
- **Maintainability** - Easy for admins to create/modify scenarios

---

## Session Continuity Notes

### Completed in Previous Sessions
- ✅ Dynamic test category database system
- ✅ Admin CLI interface for category management  
- ✅ Basic dynamic suite loading with verbose output
- ✅ Architecture decision: Option 2 (Fully Dynamic)

### Current Session Focus
- 🔄 JSON schema design for AI compatibility
- 🔄 Dynamic test engine implementation
- 🔄 Conversion of existing test scenarios

### Next Session Priorities
1. Complete JSON schema and test engine
2. Convert all existing test scenarios to JSON
3. Implement AI recommendation parser
4. Build quality filtering system

*Last Updated: 2025-07-25 - Session transition to fully dynamic JSON-based testing*