# 🧪 MCP Manager Interactive Test Menu

**Professional Menu-Driven Testing Interface**

No more typing manual commands! Just run the menu and select what you want to test with an intuitive interface.

## 🚀 Quick Start

### Launch Interactive Menu
```bash
# Method 1: Direct launcher (recommended)
./test

# Method 2: Python script
python test_menu.py
```

### Quick Command Line Testing
```bash
# Quick smoke test
./test smoke

# Unit tests
./test unit

# Quick health check (smoke + unit)
./test quick

# All tests
./test all
```

## 📋 Menu Overview

### Main Menu Options

```
🧪 MCP MANAGER INTERACTIVE TEST SUITE
================================================================================

📋 MAIN MENU
1. 🚀 Quick Collections (Recommended)
2. 🎯 Individual Test Categories  
3. 🔧 Custom Test Selection
4. 📊 View Last Test Results
5. ❓ Help & Documentation
6. 🚪 Exit
```

## 🚀 Quick Collections (Option 1)

**Pre-configured test combinations for common scenarios:**

| Collection | Description | Categories | Time |
|------------|-------------|------------|------|
| **Quick Health Check** | Daily validation | smoke + unit | ~1 min |
| **Core Functionality** | Critical tests | smoke + unit + server + suite | ~15 min |
| **Comprehensive Testing** | Most tests | All except workflows | ~30 min |
| **Complete Test Suite** | Everything | All categories | ~45 min |

**Perfect for:**
- ✅ Daily development testing (Quick)
- ✅ Pre-commit validation (Core)  
- ✅ Weekly QA testing (Comprehensive)
- ✅ Release validation (Complete)

## 🎯 Individual Test Categories (Option 2)

**Test specific functionality areas:**

| Category | Tests | Time | Priority | Description |
|----------|-------|------|----------|-------------|
| **Smoke Tests** | 4 | ~30s | CRITICAL | Must-work functionality |
| **Unit Tests** | 25 | ~25s | HIGH | Fast isolated tests |
| **Server Management** | 35+ | ~5min | HIGH | Server CRUD operations |
| **Suite Management** | 40+ | ~8min | HIGH | Suite ops + bug tests |
| **Quality Tracking** | 25+ | ~5min | MEDIUM | Feedback & reports |
| **Error Handling** | 30+ | ~6min | HIGH | Edge cases & robustness |
| **User Workflows** | 20+ | ~15min | MEDIUM | End-to-end journeys |
| **Integration Tests** | 15+ | ~10min | MEDIUM | Component interactions |
| **Regression Tests** | 10+ | ~3min | HIGH | Known bug prevention |

**Perfect for:**
- 🎯 Testing specific features after changes
- 🐛 Debugging specific functionality
- ⚡ Quick targeted validation

## 🔧 Custom Test Selection (Option 3)

**Mix and match any categories:**

```
Select multiple categories by entering numbers separated by spaces
Example: 1 3 5 (runs smoke + server + quality tests)

1. Smoke Tests
2. Unit Tests  
3. Server Management
4. Suite Management
5. Quality Tracking
6. Error Handling
7. User Workflows
8. Integration Tests
9. Regression Tests

Enter 'all' for all categories
```

**Perfect for:**
- 🔧 Custom testing scenarios
- 🚀 Feature-specific testing
- 📊 Balanced test execution

## 📊 View Last Test Results (Option 4)

**Detailed results from your last test run:**

```
📊 LAST TEST RESULTS
────────────────────────────────────────────────────
📈 Overall Statistics:
   Total Categories: 2
   Passed: ✅ 2
   Failed: ❌ 0  
   Success Rate: 100.0%
   Total Time: 26.1s

📋 Category Results:
   ✅ PASS Smoke Tests          (  2.3s)
   ✅ PASS Unit Tests           ( 23.9s)
```

**Perfect for:**
- 📈 Tracking test history
- 🐛 Analyzing failure patterns
- ⏱️ Performance monitoring

## ❓ Help & Documentation (Option 5)

**Comprehensive testing guidance:**
- 📖 Test category explanations
- 🚀 Recommended testing strategies  
- 💡 Best practices and tips
- 🔧 Manual command references

## 🎨 User Interface Features

### Professional Styling
- 🌈 **Color-coded categories** - Easy visual identification
- 🚨 **Priority indicators** - CRITICAL/HIGH/MEDIUM
- ⏱️ **Time estimates** - Plan your testing sessions
- 📊 **Real-time progress** - Watch tests execute

### Smart Navigation
- 🔄 **Easy navigation** - Clear menu flow
- ✅ **Confirmation prompts** - Prevent accidental runs
- 🔙 **Back options** - Return to previous menus
- 🛡️ **Error handling** - Graceful failure recovery

### Professional Output
- 📈 **Real-time execution** - See tests run live
- 📊 **Detailed reporting** - Comprehensive results
- 💾 **Result persistence** - View later with option 4
- 🎯 **Actionable feedback** - Clear success/failure

## 🔧 Advanced Usage

### Testing Strategies

**Daily Development:**
```bash
./test              # Interactive menu
Select: 1 → 1       # Quick Health Check
```

**Feature Development:**
```bash
./test              # Interactive menu  
Select: 2 → 3       # Server Management (if working on servers)
```

**Pre-Release:**
```bash
./test              # Interactive menu
Select: 1 → 4       # Complete Test Suite
```

**Custom Scenarios:**
```bash
./test              # Interactive menu
Select: 3           # Custom selection
Enter: 1 2 6        # Smoke + Unit + Error Handling
```

### Command Line Shortcuts

For power users who want direct command access:

```bash
# Individual categories
./test smoke unit server

# Collections don't work via CLI, use menu for collections
./test              # Launch menu for collections

# All tests
./test all
```

## 📁 Files Created

| File | Purpose |
|------|---------|
| `test_menu.py` | Interactive menu system |
| `test` | Quick launcher script |
| `TEST_MENU_GUIDE.md` | This documentation |

## 🚀 Benefits

### For Developers
- ⚡ **No command memorization** - Point and click testing
- 🎯 **Targeted testing** - Test exactly what you changed
- 📊 **Visual feedback** - Clear progress and results
- 🔄 **Repeatable** - Easy to run same tests again

### For QA Teams  
- 📋 **Structured testing** - Organized test categories
- 📈 **Progress tracking** - Monitor test execution
- 📊 **Result history** - Compare test runs
- 🎨 **Professional interface** - Easy to use and explain

### For DevOps
- 🤖 **Scriptable** - Can be automated with input redirection
- 📊 **Detailed reporting** - Machine-readable results
- 🔧 **Flexible execution** - Collections or individual tests
- 📈 **Performance monitoring** - Execution time tracking

## 💡 Pro Tips

### Efficient Testing Workflow
1. **Start with Quick Health Check** - Catch obvious issues fast
2. **Use targeted categories** - Focus on areas you changed
3. **Run comprehensive before commits** - Ensure broad compatibility  
4. **Check results history** - Track improvements over time

### Troubleshooting
- 🔍 **Check file permissions** - `chmod +x test test_menu.py`
- 📁 **Run from project root** - Menu checks for proper directory
- 🐛 **View detailed output** - Tests show real-time execution
- 📊 **Use option 4** - Review last results for debugging

### Customization
- 🎨 **Modify collections** - Edit `test_menu.py` collections dict
- ⏱️ **Adjust timeouts** - Modify timeout values in test runner
- 🔧 **Add categories** - Extend test_categories dict
- 📊 **Enhance reporting** - Customize result formatting

---

**🎉 Happy Testing! This menu system makes comprehensive testing effortless and professional.** 

No more remembering complex commands - just run `./test` and select what you need! ✨