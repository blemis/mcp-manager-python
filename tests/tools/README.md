# Test Tools Directory

This directory contains interactive utilities and tools for managing and running the MCP Manager test suite.

## Files

### test_menu.py
Interactive menu-driven test program that provides a user-friendly interface for running tests:
- Select individual test categories or collections
- View last test results
- Show output files for sharing
- Professional styling with progress indicators

Usage:
```bash
python tests/tools/test_menu.py
# or via launcher:
./test
```

### show_test_files.py
Utility to display all test output files with full paths for easy sharing:
- Shows summary JSON with statistics
- Lists individual XML reports
- Displays log files
- Provides ready-to-use copy commands

Usage:
```bash
python tests/tools/show_test_files.py
# or via launcher:
./test files
```

## Directory Structure

The test tools work with the following directory structure:
- `tests/results/` - Generated test output files (JSON, XML reports)
- `tests/fixtures/` - Test data and log files
- `tests/tools/` - Interactive utilities (this directory)
- Root `./test` - Quick launcher script

## Integration

These tools integrate with:
- `tests/test_runner.py` - Professional test execution engine
- `tests/conftest.py` - Test configuration and fixtures
- All test modules in the `tests/` directory