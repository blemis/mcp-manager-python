# Test Generation Guide

Comprehensive guide for automatically generating JSON test files for MCP Manager CLI commands.

## Quick Start

### 🚀 Generate Tests in 3 Ways

#### 1. Interactive Guided Mode (Recommended for beginners)
```bash
python generate_tests.py
```
- Walks you through step-by-step prompts
- Discovers subcommands automatically 
- Generates comprehensive test scenarios
- Perfect for new CLI features

#### 2. Quick Generation
```bash
python generate_tests.py new-feature
python generate_tests.py export --category system
python generate_tests.py workflow advanced --priority high
```
- Fast command analysis and test generation
- Automatically determines category and scenarios
- Good for simple commands

#### 3. AI-Powered Generation (Advanced)
```bash
python generate_tests.py --ai export --desc "Export data in multiple formats"
python generate_tests.py --ai workflow create --desc "Create complex workflows"
```
- Uses AI to generate 10-20 comprehensive scenarios
- Analyzes command complexity and integration needs
- Creates realistic edge cases and error handling tests

## What Gets Generated

### ✅ Comprehensive Test Coverage
Each generated test file includes:

- **Basic Functionality Tests** - Core command operations
- **Help Command Tests** - Validate --help output
- **Error Handling Tests** - Invalid arguments, missing parameters
- **Edge Case Tests** - Boundary conditions, special inputs
- **Integration Tests** - Works with existing database servers
- **Negative Tests** - Expected failure scenarios

### 📁 File Structure
```
tests/scenarios/cli_tests/
├── 01_core_commands.json           # ✅ Existing
├── 02_discovery_commands.json      # ✅ Existing  
├── 03_suite_management.json        # ✅ Existing
├── ...
├── 11_your_new_feature.json        # 🆕 Auto-generated
└── master_test_config.json         # 🔄 Auto-updated
```

### 🤖 Smart Automation
The system automatically:
- ✅ **Creates JSON file** with proper schema
- ✅ **Updates master config** with new test suite entry
- ✅ **Validates test scenarios** against schema requirements
- ✅ **Numbers files sequentially** (11_, 12_, etc.)
- ✅ **Uses existing database servers** (Ref, filesystem, aws-diagram)
- ✅ **Generates unique test names** with proper conventions

## Usage Examples

### Example 1: New Export Feature
```bash
# User runs this simple command
python generate_tests.py export

# System automatically generates:
# - 11_system_commands.json (file)
# - 8 test scenarios covering export functionality
# - Updates master_test_config.json
# - Ready to run: python run_cli_tests.py --category system
```

### Example 2: Complex Workflow Feature  
```bash
# AI-powered generation
python generate_tests.py --ai workflow batch --desc "Batch workflow processing"

# System generates:
# - 12_workflow_commands.json
# - 15+ comprehensive scenarios including:
#   - Basic batch processing
#   - Error handling for invalid workflows
#   - Integration with existing suites
#   - Performance/timeout scenarios
#   - Edge cases with large batches
```

### Example 3: Interactive Mode
```bash
python generate_tests.py

# Guided prompts:
# 📝 Test Suite Name: Advanced Analytics Commands
# 📄 Description: Tests for advanced analytics and reporting
# 🏷️ Category: ai_analytics  
# 📊 Priority: high
# 🖥️ Base command: mcp-manager analytics advanced
# ➕ Add custom scenarios? y
# ... (user adds 3 custom scenarios)
# ✅ Generated 11 test scenarios
```

## Categories and Conventions

### 📂 Available Categories
- `core` - Core server management (add, remove, list, enable/disable)
- `discovery` - Server discovery and installation  
- `suite` - Suite management and server assignment
- `ai_analytics` - AI, analytics, tools, quality features
- `system` - System info, configuration, monitoring
- `interface` - TUI and interactive commands
- `api` - API server management  
- `proxy` - MCP proxy functionality
- `workflow` - Workflow and automation features
- `test_admin` - Administrative and development tools

### ⭐ Priority Levels
- `critical` - Core functionality that must always work
- `high` - Important features users rely on
- `medium` - Standard features and edge cases
- `low` - Nice-to-have and administrative tools

### 🏷️ Test Naming Convention
Tests follow the pattern: `feature_action_condition`

Examples:
- `export_basic_functionality`
- `export_help_command`
- `export_invalid_format`
- `export_missing_arguments`
- `suite_create_with_invalid_name`

## Advanced Features

### 🔬 Command Analysis
The system automatically analyzes commands to:
- Detect subcommands via --help output
- Determine appropriate category based on keywords
- Assess complexity level (low/medium/high)
- Identify integration requirements
- Generate realistic timeout values

### 🤖 AI Integration
When AI is available:
- Analyzes command purpose and generates relevant scenarios
- Creates realistic error conditions and edge cases
- Suggests integration tests with existing servers
- Generates comprehensive descriptions and expectations

### ✅ Validation & Quality
All generated tests include:
- Schema validation against JSON schema
- Unique test names to prevent conflicts
- Realistic timeouts based on operation complexity
- Proper exit codes (0=success, 1=error, 2=arg-error)
- Integration with existing database servers when appropriate

## Running Generated Tests

### 🏃 Execute Your New Tests
```bash
# Run just your new category
python run_cli_tests.py --category your_category

# Run by priority
python run_cli_tests.py --critical

# Run everything
python run_cli_tests.py

# List what's available
python run_cli_tests.py --list
```

### 📊 Test Reports
```bash
# Save detailed report
python run_cli_tests.py --save-report my_test_results.json

# View results
python run_cli_tests.py --category core --verbose
```

## Troubleshooting

### ❌ Common Issues

**"AI generation failed"**
- Falls back to command analysis automatically
- AI requires proper configuration in ai_config.py

**"No subcommands discovered"** 
- Normal for simple commands
- Basic tests still generated (help, basic, error cases)

**"Schema validation failed"**
- Generated tests are automatically validated
- Should not occur with automated generation

**"Command not found"**
- Ensure command exists: `mcp-manager your-command --help`
- Use full command: `mcp-manager feature subcommand`

### 🔧 Getting Help
```bash
python generate_tests.py --help     # Full options
python generate_tests.py           # Interactive mode
python run_cli_tests.py --list     # See all available tests
```

## Best Practices

### ✅ Do This
- Use descriptive test suite names
- Provide meaningful descriptions for AI generation
- Review generated tests before committing
- Run tests after generation to verify they work
- Use existing database servers in integration tests

### ❌ Avoid This
- Don't manually edit master_test_config.json
- Don't create duplicate test names
- Don't hardcode temporary server names
- Don't skip validation of generated tests

## Integration with Development Workflow

### 🔄 Typical Development Flow
1. **Develop new CLI feature**
2. **Generate tests**: `python generate_tests.py new-feature`
3. **Review generated tests** and customize if needed
4. **Run tests**: `python run_cli_tests.py --category new_category`
5. **Fix any failures**
6. **Commit both feature and tests**

### 🚀 CI/CD Integration
The generated tests integrate seamlessly with:
- GitHub Actions workflows
- pytest frameworks  
- Coverage reporting
- Automated quality gates

---

## Summary

The automated test generation system provides:

✅ **Zero Manual Schema Work** - No JSON editing required  
✅ **Intelligent Test Discovery** - Finds subcommands automatically  
✅ **AI-Powered Scenarios** - Comprehensive edge case coverage  
✅ **Database Integration** - Uses real servers, not mocks  
✅ **One-Command Generation** - `python generate_tests.py new-feature`  
✅ **Auto-Configuration Updates** - Master config updated automatically  

**Result**: Adding comprehensive test coverage for any new CLI feature takes less than 2 minutes!