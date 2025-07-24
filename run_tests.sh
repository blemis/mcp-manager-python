#!/bin/bash
# Simple test runner script for MCP Manager
# This script provides easy access to the comprehensive test suite

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🧪 MCP Manager Test Runner${NC}"
echo -e "${BLUE}===========================${NC}"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    exit 1
fi

# Check if we're in a virtual environment (recommended)
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}⚠️  No virtual environment detected${NC}"
    echo -e "${YELLOW}   It's recommended to run tests in a virtual environment${NC}"
    echo ""
fi

# Default arguments
ARGS=()

# Parse command line arguments
case "${1:-all}" in
    "all"|"")
        echo -e "${GREEN}Running all tests...${NC}"
        ARGS=("--coverage" "--report")
        ;;
    "fast")
        echo -e "${GREEN}Running fast tests only...${NC}"
        ARGS=("--fast")
        ;;
    "integration")
        echo -e "${GREEN}Running integration tests only...${NC}"
        ARGS=("--integration")
        ;;
    "coverage")
        echo -e "${GREEN}Running all tests with coverage...${NC}"
        ARGS=("--coverage" "--verbose")
        ;;
    "verbose")
        echo -e "${GREEN}Running all tests with verbose output...${NC}"
        ARGS=("--verbose" "--coverage")
        ;;
    "performance")
        echo -e "${GREEN}Running performance tests...${NC}"
        ARGS=("--performance" "--coverage")
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [option]"
        echo ""
        echo "Options:"
        echo "  all          Run all tests (default)"
        echo "  fast         Run only fast tests (unit + core)"
        echo "  integration  Run only integration tests"
        echo "  coverage     Run all tests with coverage report"
        echo "  verbose      Run all tests with verbose output"
        echo "  performance  Run performance benchmarks"
        echo "  help         Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                 # Run all tests"
        echo "  $0 fast           # Quick test run"
        echo "  $0 coverage       # Full run with coverage"
        echo "  $0 integration    # Only integration tests"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Unknown option: $1${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac

# Change to script directory
cd "$SCRIPT_DIR"

# Ensure required directories exist
mkdir -p htmlcov
mkdir -p .pytest_cache

# Run the comprehensive test suite
echo ""
echo -e "${BLUE}Starting test execution...${NC}"
echo ""

if python3 run_comprehensive_tests.py "${ARGS[@]}"; then
    echo ""
    echo -e "${GREEN}✅ Tests completed successfully!${NC}"
    
    # Show coverage report location if generated
    if [[ " ${ARGS[*]} " =~ " --coverage " ]]; then
        echo -e "${GREEN}📈 Coverage report: htmlcov/index.html${NC}"
    fi
    
    # Show HTML report location if generated
    if [[ " ${ARGS[*]} " =~ " --report " ]]; then
        echo -e "${GREEN}📄 Detailed report: test_report.html${NC}"
    fi
    
    exit 0
else
    echo ""
    echo -e "${RED}❌ Tests failed!${NC}"
    echo -e "${YELLOW}💡 Try running with 'verbose' option for more details${NC}"
    exit 1
fi