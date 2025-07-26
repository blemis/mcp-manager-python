#!/usr/bin/env python3
"""
Interactive Menu-Driven Test Program for MCP Manager

Professional test execution interface with easy navigation and selection.
No more manual command typing - just select what you want to test!
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
import time


class TestMenu:
    """Professional interactive test menu system."""
    
    def __init__(self):
        # Legacy test categories for backward compatibility
        self.legacy_test_categories = {
            'smoke': {
                'name': 'Smoke Tests',
                'description': 'Critical functionality that must work (4 tests, ~30s)',
                'priority': 'CRITICAL',
                'color': '\033[91m'  # Red
            },
            'unit': {
                'name': 'Unit Tests', 
                'description': 'Fast isolated tests (25 tests, ~25s)',
                'priority': 'HIGH',
                'color': '\033[92m'  # Green
            },
            'server': {
                'name': 'Server Management',
                'description': 'Server CRUD operations (35+ tests, ~5min)',
                'priority': 'HIGH',
                'color': '\033[94m'  # Blue
            },
            'suite': {
                'name': 'Suite Management',
                'description': 'Suite operations + critical bug tests (40+ tests, ~8min)',
                'priority': 'HIGH',
                'color': '\033[95m'  # Magenta
            },
            'quality': {
                'name': 'Quality Tracking',
                'description': 'Feedback, rankings, reports (25+ tests, ~5min)',
                'priority': 'MEDIUM',
                'color': '\033[96m'  # Cyan
            },
            'error': {
                'name': 'Error Handling',
                'description': 'Edge cases and robustness (30+ tests, ~6min)',
                'priority': 'HIGH',
                'color': '\033[93m'  # Yellow
            },
            'workflow': {
                'name': 'User Workflows',
                'description': 'End-to-end user journeys (20+ tests, ~15min)',
                'priority': 'MEDIUM',
                'color': '\033[97m'  # White
            },
            'integration': {
                'name': 'Integration Tests',
                'description': 'Component interactions (15+ tests, ~10min)',
                'priority': 'MEDIUM',
                'color': '\033[90m'  # Gray
            },
            'regression': {
                'name': 'Regression Tests',
                'description': 'Known bug prevention (10+ tests, ~3min)',
                'priority': 'HIGH',
                'color': '\033[91m'  # Red
            }
        }
        
        # Initialize collections first (will be updated after loading dynamic categories)
        self.collections = {
            'quick': {
                'name': 'Quick Health Check',
                'description': 'Smoke + Unit tests (~1 minute)',
                'categories': ['smoke', 'unit'],
                'color': '\033[92m'
            },
            'core': {
                'name': 'Core Functionality', 
                'description': 'Critical tests (smoke, unit, server, suite)',
                'categories': ['smoke', 'unit', 'server', 'suite'],
                'color': '\033[94m'
            },
            'comprehensive': {
                'name': 'Comprehensive Testing',
                'description': 'All tests except slow workflows (~30min)',
                'categories': ['smoke', 'unit', 'server', 'suite', 'quality', 'error', 'regression', 'integration'],
                'color': '\033[95m'
            },
            'full': {
                'name': 'Complete Test Suite',
                'description': 'ALL tests including workflows (~45min)',
                'categories': ['smoke', 'unit', 'server', 'suite', 'quality', 'error', 'workflow', 'integration', 'regression'],
                'color': '\033[96m'
            }
        }
        
        # Dynamic test categories loaded from JSON files - load after collections are initialized
        self.test_categories = self._load_dynamic_test_categories()
        
        self.colors = {
            'reset': '\033[0m',
            'bold': '\033[1m',
            'green': '\033[92m',
            'red': '\033[91m',
            'blue': '\033[94m',
            'yellow': '\033[93m',
            'cyan': '\033[96m',
            'magenta': '\033[95m'
        }
    
    def _load_dynamic_test_categories(self) -> Dict[str, Dict]:
        """Load test categories dynamically from JSON test files and master config."""
        categories = {}
        
        # Start with legacy categories for backward compatibility
        categories.update(self.legacy_test_categories)
        
        try:
            # Load master test configuration
            master_config_path = Path("tests/scenarios/cli_tests/master_test_config.json")
            
            if master_config_path.exists():
                with open(master_config_path, 'r') as f:
                    master_config = json.load(f)
                
                # Create categories from JSON test suites
                for suite in master_config.get('test_suites', []):
                    category = suite.get('category', 'custom')
                    priority = suite.get('priority', 'medium').upper()
                    test_count = suite.get('test_count', 0)
                    description = suite.get('description', '')
                    
                    # Estimate duration based on test count
                    estimated_duration = max(10, test_count * 3)  # 3 seconds per test minimum
                    duration_str = f"~{estimated_duration}s" if estimated_duration < 60 else f"~{estimated_duration//60}min"
                    
                    # Get color based on priority
                    color_map = {
                        'CRITICAL': '\033[91m',  # Red
                        'HIGH': '\033[94m',      # Blue  
                        'MEDIUM': '\033[96m',    # Cyan
                        'LOW': '\033[90m'        # Gray
                    }
                    
                    # Create full description
                    full_description = f"{description} ({test_count} tests, {duration_str})"
                    
                    # Create friendly name from test suite name
                    suite_name = suite.get('test_suite_name', category)
                    if not suite_name or suite_name == category:
                        # Fallback to file name processing
                        file_name = suite.get('file', category)
                        suite_name = file_name.replace('.json', '').replace('_', ' ').replace('-', ' ')
                        suite_name = ' '.join(word.capitalize() for word in suite_name.split()[1:])  # Skip number prefix
                    
                    categories[category] = {
                        'name': suite_name,
                        'description': full_description,
                        'priority': priority,
                        'color': color_map.get(priority, '\033[96m'),
                        'file': suite.get('file'),
                        'test_count': test_count,
                        'is_json': True
                    }
                
                # Update collections to include new categories
                self._update_collections_with_json_categories(categories)
                
        except Exception as e:
            print(f"Warning: Failed to load dynamic test categories: {e}")
            print("Falling back to legacy categories")
        
        return categories
    
    def _update_collections_with_json_categories(self, categories: Dict[str, Dict]):
        """Update test collections to include JSON-based categories."""
        # Find categories by priority
        critical_categories = [k for k, v in categories.items() if v.get('priority') == 'CRITICAL']
        high_categories = [k for k, v in categories.items() if v.get('priority') == 'HIGH']
        all_categories = list(categories.keys())
        
        # Update collections with dynamic categories
        if critical_categories or high_categories:
            self.collections['quick']['categories'] = critical_categories + high_categories[:2]
            self.collections['core']['categories'] = critical_categories + high_categories
            self.collections['comprehensive']['categories'] = [k for k in all_categories if categories[k].get('priority') in ['CRITICAL', 'HIGH', 'MEDIUM']]
            self.collections['full']['categories'] = all_categories
        
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Print the application header."""
        print(f"{self.colors['bold']}{self.colors['cyan']}")
        print("=" * 80)
        print("🧪 MCP MANAGER INTERACTIVE TEST SUITE")
        print("Professional Menu-Driven Testing Interface")
        print("=" * 80)
        print(f"{self.colors['reset']}")
    
    def print_main_menu(self):
        """Print the main menu options."""
        print(f"{self.colors['bold']}📋 MAIN MENU{self.colors['reset']}")
        print("-" * 40)
        print("1. 🚀 Quick Collections (Recommended)")
        print("2. 🎯 Individual Test Categories") 
        print("3. 🔧 Custom Test Selection")
        print("4. 🤖 Generate New Tests (Auto-Create)")
        print("5. 📊 View Last Test Results")
        print("6. 📁 Show Output Files for Sharing")
        print("7. ⚖️  Compare Testing Systems (JSON vs Pytest)")
        print("8. 🔄 Legacy Pytest Mode")
        print("9. 💥 Nuke Config (Reset All)")
        print("10. ❓ Help & Documentation")
        print("11. 🚪 Exit")
        print()
    
    def print_collections_menu(self):
        """Print the test collections menu."""
        print(f"{self.colors['bold']}🚀 TEST COLLECTIONS{self.colors['reset']}")
        print("-" * 50)
        
        for i, (key, collection) in enumerate(self.collections.items(), 1):
            color = collection['color']
            name = collection['name']
            desc = collection['description']
            categories_str = ', '.join(collection['categories'])
            
            print(f"{color}{i}. {name}{self.colors['reset']}")
            print(f"   {desc}")
            print(f"   Categories: {categories_str}")
            print()
        
        print("0. ← Back to Main Menu")
        print()
    
    def print_categories_menu(self):
        """Print individual test categories menu."""
        print(f"{self.colors['bold']}🎯 INDIVIDUAL TEST CATEGORIES{self.colors['reset']}")
        print("-" * 50)
        
        for i, (key, category) in enumerate(self.test_categories.items(), 1):
            color = category['color']
            name = category['name']
            desc = category['description']
            priority = category['priority']
            
            priority_color = self.colors['red'] if priority == 'CRITICAL' else \
                           self.colors['yellow'] if priority == 'HIGH' else \
                           self.colors['green']
            
            print(f"{color}{i:2d}. {name}{self.colors['reset']} "
                  f"{priority_color}[{priority}]{self.colors['reset']}")
            print(f"     {desc}")
            print()
        
        print(" 0. ← Back to Main Menu")
        print()
    
    def print_custom_menu(self):
        """Print custom selection menu."""
        print(f"{self.colors['bold']}🔧 CUSTOM TEST SELECTION{self.colors['reset']}")
        print("-" * 50)
        print("Select multiple categories by entering numbers separated by spaces")
        print("Example: 1 3 5 (runs smoke + server + quality tests)")
        print()
        
        for i, (key, category) in enumerate(self.test_categories.items(), 1):
            color = category['color']
            name = category['name']
            print(f"{color}{i:2d}. {name}{self.colors['reset']}")
        
        print()
        print("Enter 'all' for all categories")
        print("Enter '0' to go back")
        print()
    
    def run_tests(self, categories: List[str], description: str = "", use_legacy: bool = False) -> bool:
        """Run the specified test categories."""
        if not categories:
            print(f"{self.colors['red']}❌ No test categories specified{self.colors['reset']}")
            return False
        
        # Determine which categories are JSON-based vs legacy
        json_categories = []
        legacy_categories = []
        
        for category in categories:
            if category in self.test_categories and self.test_categories[category].get('is_json'):
                json_categories.append(category)
            else:
                legacy_categories.append(category)
        
        success = True
        
        # Run JSON tests if any
        if json_categories and not use_legacy:
            print(f"{self.colors['bold']}{self.colors['blue']}")
            print(f"🚀 RUNNING JSON TESTS")
            print("=" * 50)
            print(f"Categories: {', '.join(json_categories)}")
            if description:
                print(f"Description: {description}")
            print("=" * 50)
            print(f"{self.colors['reset']}")
            
            # Use the modern test runner for JSON categories
            cmd = [sys.executable, "run_cli_tests.py"] + [f"--category={cat}" for cat in json_categories]
            
            try:
                start_time = time.time()
                print(f"{self.colors['cyan']}🚀 Executing: {' '.join(cmd)}{self.colors['reset']}")
                print(f"{self.colors['yellow']}💡 Live output will be shown below...{self.colors['reset']}")
                print("=" * 80)
                
                result = subprocess.run(cmd, cwd=Path.cwd(), text=True)
                duration = time.time() - start_time
                
                print(f"\n{self.colors['bold']}")
                print("=" * 60)
                if result.returncode == 0:
                    print(f"{self.colors['green']}🎉 JSON TESTS PASSED!{self.colors['reset']}")
                    print(f"✨ JSON test execution completed successfully in {duration:.1f}s")
                else:
                    print(f"{self.colors['red']}❌ SOME JSON TESTS FAILED{self.colors['reset']}")
                    print(f"⚠️  JSON test execution completed with issues in {duration:.1f}s")
                    success = False
                print("=" * 60)
                print(f"{self.colors['reset']}")
                
            except Exception as e:
                print(f"{self.colors['red']}💥 JSON test execution failed: {e}{self.colors['reset']}")
                success = False
        
        # Run legacy tests if any
        if legacy_categories:
            system_name = "Legacy Pytest" if use_legacy else "Legacy Pytest (Fallback)"
            print(f"{self.colors['bold']}{self.colors['blue']}")
            print(f"🚀 RUNNING LEGACY TESTS - {system_name}")
            print("=" * 60)
            print(f"Categories: {', '.join(legacy_categories)}")
            print("=" * 60)
            print(f"{self.colors['reset']}")
            
            cmd = [sys.executable, "tests/test_runner.py"] + legacy_categories
            
            try:
                start_time = time.time()
                print(f"{self.colors['cyan']}🚀 Executing: {' '.join(cmd)}{self.colors['reset']}")
                print("=" * 80)
                
                result = subprocess.run(cmd, cwd=Path.cwd(), text=True)
                duration = time.time() - start_time
                
                print(f"\n{self.colors['bold']}")
                print("=" * 60)
                if result.returncode == 0:
                    print(f"{self.colors['green']}🎉 LEGACY TESTS PASSED!{self.colors['reset']}")
                    print(f"✨ Legacy test execution completed successfully in {duration:.1f}s")
                else:
                    print(f"{self.colors['red']}❌ SOME LEGACY TESTS FAILED{self.colors['reset']}")
                    print(f"⚠️  Legacy test execution completed with issues in {duration:.1f}s")
                    success = False
                print("=" * 60)
                print(f"{self.colors['reset']}")
                
            except Exception as e:
                print(f"{self.colors['red']}💥 Legacy test execution failed: {e}{self.colors['reset']}")
                success = False
        
        # Final summary
        if json_categories and legacy_categories:
            print(f"\n{self.colors['bold']}")
            print("=" * 80)
            if success:
                print(f"{self.colors['green']}🎉 ALL TESTS PASSED (JSON + Legacy)!{self.colors['reset']}")
            else:
                print(f"{self.colors['red']}❌ SOME TESTS FAILED (JSON + Legacy){self.colors['reset']}")
            print("=" * 80)
            print(f"{self.colors['reset']}")
        
        return success
    
    def view_last_results(self):
        """View the last test results."""
        results_file = Path("tests/results/test-results-summary.json")
        
        if not results_file.exists():
            print(f"{self.colors['yellow']}⚠️  No test results found. Run some tests first!{self.colors['reset']}")
            return
        
        try:
            with open(results_file, 'r') as f:
                results = json.load(f)
            
            print(f"{self.colors['bold']}📊 LAST TEST RESULTS{self.colors['reset']}")
            print("-" * 50)
            
            # Summary stats
            total_categories = results.get('total_categories', 0)
            passed_categories = results.get('passed_categories', 0)
            failed_categories = results.get('failed_categories', 0)
            success_rate = results.get('success_rate', 0)
            total_time = results.get('total_time', 0)
            
            print(f"📈 Overall Statistics:")
            print(f"   Total Categories: {total_categories}")
            print(f"   Passed: {self.colors['green']}{passed_categories}{self.colors['reset']}")
            print(f"   Failed: {self.colors['red']}{failed_categories}{self.colors['reset']}")
            print(f"   Success Rate: {success_rate:.1f}%")
            print(f"   Total Time: {total_time:.1f}s")
            print()
            
            # Detailed results
            print("📋 Category Results:")
            for result in results.get('results', []):
                category = result.get('category', 'Unknown')
                success = result.get('success', False)
                duration = result.get('duration', 0)
                
                status = f"{self.colors['green']}✅ PASS{self.colors['reset']}" if success else f"{self.colors['red']}❌ FAIL{self.colors['reset']}"
                print(f"   {status} {category:20} ({duration:5.1f}s)")
                
                if not success:
                    returncode = result.get('returncode', 'unknown')
                    print(f"      └─ Exit code: {returncode}")
            
        except Exception as e:
            print(f"{self.colors['red']}❌ Error reading test results: {e}{self.colors['reset']}")
    
    def show_output_files(self):
        """Show test output files for sharing - uses the intelligent show_test_files utility."""
        # Just call the dedicated utility which is much smarter
        print(f"{self.colors['cyan']}🔄 Loading intelligent file analysis...{self.colors['reset']}")
        print()
        
        # Run the show_test_files.py utility
        import subprocess
        try:
            result = subprocess.run(
                [sys.executable, "tests/tools/show_test_files.py"],
                cwd=Path.cwd(),
                text=True
            )
            
            if result.returncode != 0:
                print(f"{self.colors['red']}❌ Error running file analysis utility{self.colors['reset']}")
                print("   Try running: ./test files")
        except Exception as e:
            print(f"{self.colors['red']}❌ Error: {e}{self.colors['reset']}")
            print("   Try running: ./test files")
    
    def nuke_config(self):
        """Nuclear option - use the existing nuke command to reset all MCP configurations."""
        print(f"{self.colors['bold']}{self.colors['red']}💥 NUCLEAR CONFIG RESET{self.colors['reset']}")
        print("-" * 50)
        print(f"{self.colors['yellow']}⚠️  This will use the built-in nuke command to remove ALL MCP servers.{self.colors['reset']}")
        print()
        
        try:
            # Use the existing nuke command with force flag to avoid double confirmation
            result = subprocess.run(
                [sys.executable, "-m", "mcp_manager.cli.main", "nuke", "--force"],
                cwd=Path.cwd(),
                text=True,
                capture_output=False  # Show output directly
            )
            
            if result.returncode == 0:
                print(f"\n{self.colors['green']}✅ Nuclear reset completed successfully!{self.colors['reset']}")
            else:
                print(f"\n{self.colors['red']}❌ Nuclear reset failed with exit code {result.returncode}{self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}❌ Error running nuke command: {e}{self.colors['reset']}")
            print("Try running manually: mcp-manager nuke")
    
    def handle_test_generation_menu(self):
        """Handle the test generation menu."""
        while True:
            self.clear_screen()
            self.print_header()
            print(f"{self.colors['bold']}🤖 AUTOMATED TEST GENERATION{self.colors['reset']}")
            print("-" * 50)
            print("Automatically create comprehensive JSON test files for new CLI commands")
            print()
            
            print("1. 🎯 Interactive Guided Mode (Recommended)")
            print("   Step-by-step prompts to create comprehensive tests")
            print()
            
            print("2. ⚡ Quick Generation")
            print("   Fast test creation for simple commands")
            print()
            
            print("3. 🤖 AI-Powered Generation (Advanced)")
            print("   Use AI to create comprehensive test scenarios")
            print()
            
            print("4. 📋 List Existing Test Files")
            print("   Show all current test files and scenarios")
            print()
            
            print("5. 🔍 View Test Generation Guide")
            print("   Complete documentation and examples")
            print()
            
            print("0. ← Back to Main Menu")
            print()
            
            choice = self.get_user_input("Select test generation option (0-5):")
            
            if choice == '0':
                return
            elif choice == '1':
                self.run_guided_test_generation()
                return
            elif choice == '2':
                self.run_quick_test_generation()
                return  
            elif choice == '3':
                self.run_ai_test_generation()
                return
            elif choice == '4':
                self.list_existing_test_files()
                self.wait_for_continue()
            elif choice == '5':
                self.show_test_generation_guide()
                self.wait_for_continue()
            else:
                print(f"{self.colors['red']}❌ Invalid selection{self.colors['reset']}")
                self.wait_for_continue()
    
    def run_guided_test_generation(self):
        """Run interactive guided test generation."""
        self.clear_screen()
        self.print_header()
        print(f"{self.colors['bold']}🎯 INTERACTIVE GUIDED TEST GENERATION{self.colors['reset']}")
        print("-" * 60)
        print("This will walk you through creating comprehensive test scenarios")
        print("for your new CLI command with step-by-step prompts.")
        print()
        
        confirm = self.get_user_input("Ready to start guided test generation? (y/N):").lower()
        
        if confirm in ['y', 'yes']:
            print(f"\n{self.colors['cyan']}🚀 Launching guided test generation...{self.colors['reset']}")
            
            try:
                result = subprocess.run(
                    [sys.executable, "generate_tests.py"],
                    cwd=Path.cwd(),
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"\n{self.colors['green']}✅ Test generation completed successfully!{self.colors['reset']}")
                else:
                    print(f"\n{self.colors['red']}❌ Test generation failed{self.colors['reset']}")
                    
            except Exception as e:
                print(f"{self.colors['red']}❌ Error running test generation: {e}{self.colors['reset']}")
            
            self.wait_for_continue()
    
    def run_quick_test_generation(self):
        """Run quick test generation."""
        self.clear_screen()
        self.print_header()
        print(f"{self.colors['bold']}⚡ QUICK TEST GENERATION{self.colors['reset']}")
        print("-" * 50)
        print("Fast test creation for simple commands")
        print()
        
        command = self.get_user_input("Enter command to generate tests for (e.g., 'export' or 'workflow advanced'):")
        
        if not command:
            print(f"{self.colors['red']}❌ No command specified{self.colors['reset']}")
            self.wait_for_continue()
            return
        
        # Optional parameters
        print()
        category = self.get_user_input("Category (optional - press Enter for auto-detection):").strip()
        priority = self.get_user_input("Priority (critical/high/medium/low - press Enter for auto):").strip()
        description = self.get_user_input("Description (optional):").strip()
        
        # Build command
        cmd = [sys.executable, "generate_tests.py", command]
        if category:
            cmd.extend(["--category", category])
        if priority:
            cmd.extend(["--priority", priority])
        if description:
            cmd.extend(["--desc", description])
        
        print(f"\n{self.colors['cyan']}🚀 Generating tests for: mcp-manager {command}{self.colors['reset']}")
        
        try:
            result = subprocess.run(cmd, cwd=Path.cwd(), text=True)
            
            if result.returncode == 0:
                print(f"\n{self.colors['green']}✅ Quick test generation completed!{self.colors['reset']}")
            else:
                print(f"\n{self.colors['red']}❌ Test generation failed{self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}❌ Error: {e}{self.colors['reset']}")
        
        self.wait_for_continue()
    
    def run_ai_test_generation(self):
        """Run AI-powered test generation."""
        self.clear_screen()
        self.print_header()
        print(f"{self.colors['bold']}🤖 AI-POWERED TEST GENERATION{self.colors['reset']}")
        print("-" * 50)
        print("Use AI to create comprehensive test scenarios with edge cases")
        print()
        
        command = self.get_user_input("Enter command to generate tests for:")
        
        if not command:
            print(f"{self.colors['red']}❌ No command specified{self.colors['reset']}")
            self.wait_for_continue()
            return
        
        description = self.get_user_input("Describe what this command does (helps AI generate better tests):")
        
        cmd = [sys.executable, "generate_tests.py", "--ai", command]
        if description:
            cmd.extend(["--desc", description])
        
        print(f"\n{self.colors['cyan']}🤖 Using AI to generate comprehensive tests...{self.colors['reset']}")
        print("This may take a moment...")
        
        try:
            result = subprocess.run(cmd, cwd=Path.cwd(), text=True)
            
            if result.returncode == 0:
                print(f"\n{self.colors['green']}✅ AI test generation completed!{self.colors['reset']}")
            else:
                print(f"\n{self.colors['red']}❌ AI generation failed (falling back to analysis){self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}❌ Error: {e}{self.colors['reset']}")
        
        self.wait_for_continue()
    
    def list_existing_test_files(self):
        """List all existing test files and their scenarios."""
        print(f"{self.colors['bold']}📋 EXISTING TEST FILES{self.colors['reset']}")
        print("-" * 50)
        
        try:
            result = subprocess.run(
                [sys.executable, "run_cli_tests.py", "--list"],
                cwd=Path.cwd(),
                text=True,
                capture_output=True
            )
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"{self.colors['red']}❌ Error listing test files{self.colors['reset']}")
                print(result.stderr)
                
        except Exception as e:
            print(f"{self.colors['red']}❌ Error: {e}{self.colors['reset']}")
    
    def show_test_generation_guide(self):
        """Show the test generation guide."""
        print(f"{self.colors['bold']}📖 TEST GENERATION GUIDE{self.colors['reset']}")
        print("-" * 50)
        
        guide_path = Path("TEST_GENERATION_GUIDE.md")
        if guide_path.exists():
            print("Opening comprehensive test generation guide...")
            print()
            print(f"{self.colors['cyan']}📄 Guide Location: {guide_path}{self.colors['reset']}")
            print()
            print("Key points:")
            print("• Three generation modes: Interactive, Quick, AI-powered")
            print("• Automatically creates JSON files and updates configuration")
            print("• Uses existing database servers for realistic testing")
            print("• Generates comprehensive scenarios including edge cases")
            print()
            print("Quick Examples:")
            print(f"  {self.colors['green']}python generate_tests.py{self.colors['reset']}                    # Interactive mode")
            print(f"  {self.colors['green']}python generate_tests.py export{self.colors['reset']}             # Quick generation")  
            print(f"  {self.colors['green']}python generate_tests.py --ai workflow batch{self.colors['reset']} # AI-powered")
            print()
            print(f"For complete guide: {self.colors['yellow']}cat TEST_GENERATION_GUIDE.md{self.colors['reset']}")
        else:
            print(f"{self.colors['red']}❌ Test generation guide not found{self.colors['reset']}")
            print("Expected location: TEST_GENERATION_GUIDE.md")

    def show_help(self):
        """Show help and documentation."""
        print(f"{self.colors['bold']}❓ HELP & DOCUMENTATION{self.colors['reset']}")
        print("-" * 50)
        print()
        print(f"{self.colors['cyan']}🎯 Test Categories Explained:{self.colors['reset']}")
        
        for key, category in self.test_categories.items():
            color = category['color']
            name = category['name']
            desc = category['description']
            priority = category['priority']
            
            print(f"{color}• {name}{self.colors['reset']} [{priority}]")
            print(f"  {desc}")
            print()
        
        print(f"{self.colors['cyan']}🚀 Recommended Testing Strategies:{self.colors['reset']}")
        print("• Quick Health Check: Run daily for basic validation")
        print("• Core Functionality: Before releases or major changes") 
        print("• Comprehensive: Weekly full validation")
        print("• Full Suite: Before major releases or deployments")
        print()
        
        print(f"{self.colors['cyan']}🤖 Test Generation (NEW!):{self.colors['reset']}")
        print("• Interactive Guided: Step-by-step test creation")
        print("• Quick Generation: Fast tests for simple commands")
        print("• AI-Powered: Comprehensive scenarios with edge cases")
        print("• Auto-updates configuration and creates JSON files")
        print()
        
        print(f"{self.colors['cyan']}💡 Tips:{self.colors['reset']}")
        print("• Always start with Smoke Tests for critical issues")
        print("• Use Test Generation for new CLI features")
        print("• Use Custom Selection for specific feature testing")
        print("• Check Last Results to track test history")
        print("• Tests run in isolated environments (safe to execute)")
        print("• Use 'Nuke Config' if you want to start completely fresh")
        print()
        
        print(f"{self.colors['cyan']}🔧 Manual Commands (if needed):{self.colors['reset']}")
        print("• python generate_tests.py                     # Generate new tests")
        print("• python run_cli_tests.py --category core      # Run specific tests")
        print("• python tests/json_test_runner_cli.py smoke   # JSON engine (default)")
        print("• python tests/test_runner.py smoke            # Legacy pytest")
        print("• ./test smoke --compare                       # Compare both systems")
        print("• ./test smoke --json                          # Force JSON mode")
        print("• mcp-manager remove --all                     # Manual config nuke")
        print()
    
    def get_user_input(self, prompt: str) -> str:
        """Get user input with styled prompt."""
        return input(f"{self.colors['bold']}{prompt}{self.colors['reset']} ").strip()
    
    def wait_for_continue(self):
        """Wait for user to continue."""
        self.get_user_input("\n🔄 Press Enter to continue...")
    
    def handle_collections_menu(self, use_legacy: bool = False):
        """Handle the collections menu selection."""
        while True:
            self.clear_screen()
            self.print_header()
            mode_str = "(Legacy Pytest Mode)" if use_legacy else "(JSON Test Engine - Default)"
            print(f"{self.colors['bold']}🚀 TEST COLLECTIONS {mode_str}{self.colors['reset']}")
            print("-" * 50)
            
            for i, (key, collection) in enumerate(self.collections.items(), 1):
                color = collection['color']
                name = collection['name']
                desc = collection['description']
                categories_str = ', '.join(collection['categories'])
                
                print(f"{color}{i}. {name}{self.colors['reset']}")
                print(f"   {desc}")
                print(f"   Categories: {categories_str}")
                print()
            
            print("0. ← Back to Main Menu")
            print()
            
            max_collection = len(self.collections)
            choice = self.get_user_input(f"Select collection (0-{max_collection}):")
            
            if choice == '0':
                return
            
            collections_list = list(self.collections.items())
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(collections_list):
                    key, collection = collections_list[idx]
                    
                    # Confirm selection
                    print(f"\n{self.colors['yellow']}🔄 You selected: {collection['name']}{self.colors['reset']}")
                    print(f"   {collection['description']}")
                    print(f"   Categories: {', '.join(collection['categories'])}")
                    
                    confirm = self.get_user_input("\nProceed with this test collection? (y/N):").lower()
                    
                    if confirm in ['y', 'yes']:
                        success = self.run_tests(collection['categories'], collection['description'], use_legacy)
                        self.wait_for_continue()
                    return
                else:
                    print(f"{self.colors['red']}❌ Invalid selection{self.colors['reset']}")
                    self.wait_for_continue()
                    
            except ValueError:
                print(f"{self.colors['red']}❌ Please enter a valid number{self.colors['reset']}")
                self.wait_for_continue()
    
    def handle_categories_menu(self, use_legacy: bool = False):
        """Handle individual categories menu selection."""
        while True:
            self.clear_screen()
            self.print_header()
            mode_str = "(Legacy Pytest Mode)" if use_legacy else "(JSON Test Engine - Default)"
            print(f"{self.colors['bold']}🎯 INDIVIDUAL TEST CATEGORIES {mode_str}{self.colors['reset']}")
            print("-" * 50)
            
            for i, (key, category) in enumerate(self.test_categories.items(), 1):
                color = category['color']
                name = category['name']
                desc = category['description']
                priority = category['priority']
                
                priority_color = self.colors['red'] if priority == 'CRITICAL' else \
                               self.colors['yellow'] if priority == 'HIGH' else \
                               self.colors['green']
                
                print(f"{color}{i:2d}. {name}{self.colors['reset']} "
                      f"{priority_color}[{priority}]{self.colors['reset']}")
                print(f"     {desc}")
                print()
            
            print(" 0. ← Back to Main Menu")
            print()
            
            max_category = len(self.test_categories)
            choice = self.get_user_input(f"Select category (0-{max_category}):")
            
            if choice == '0':
                return
            
            categories_list = list(self.test_categories.items())
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(categories_list):
                    key, category = categories_list[idx]
                    
                    # Confirm selection
                    print(f"\n{self.colors['yellow']}🔄 You selected: {category['name']}{self.colors['reset']}")
                    print(f"   {category['description']}")
                    
                    confirm = self.get_user_input("\nProceed with this test category? (y/N):").lower()
                    
                    if confirm in ['y', 'yes']:
                        success = self.run_tests([key], category['description'], use_legacy)
                        self.wait_for_continue()
                    return
                else:
                    print(f"{self.colors['red']}❌ Invalid selection{self.colors['reset']}")
                    self.wait_for_continue()
                    
            except ValueError:
                print(f"{self.colors['red']}❌ Please enter a valid number{self.colors['reset']}")
                self.wait_for_continue()
    
    def handle_custom_menu(self, use_legacy: bool = False):
        """Handle custom test selection."""
        while True:
            self.clear_screen()
            self.print_header()
            mode_str = "(Legacy Pytest Mode)" if use_legacy else "(JSON Test Engine - Default)"
            print(f"{self.colors['bold']}🔧 CUSTOM TEST SELECTION {mode_str}{self.colors['reset']}")
            print("-" * 50)
            print("Select multiple categories by entering numbers separated by spaces")
            print("Example: 1 3 5 (runs smoke + server + quality tests)")
            print()
            
            for i, (key, category) in enumerate(self.test_categories.items(), 1):
                color = category['color']
                name = category['name']
                print(f"{color}{i:2d}. {name}{self.colors['reset']}")
            
            print()
            print("Enter 'all' for all categories")
            print("Enter '0' to go back")
            print()
            
            choice = self.get_user_input("Enter category numbers (space-separated) or 'all':")
            
            if choice == '0':
                return
            
            categories_list = list(self.test_categories.keys())
            selected_categories = []
            
            if choice.lower() == 'all':
                selected_categories = categories_list
            else:
                try:
                    numbers = [int(x.strip()) for x in choice.split()]
                    for num in numbers:
                        if 1 <= num <= len(categories_list):
                            selected_categories.append(categories_list[num - 1])
                        else:
                            print(f"{self.colors['red']}❌ Invalid selection: {num}{self.colors['reset']}")
                            self.wait_for_continue()
                            return
                except ValueError:
                    print(f"{self.colors['red']}❌ Invalid input. Use numbers separated by spaces{self.colors['reset']}")
                    self.wait_for_continue()
                    continue
            
            if selected_categories:
                # Show selection
                selected_names = [self.test_categories[cat]['name'] for cat in selected_categories]
                print(f"\n{self.colors['yellow']}🔄 You selected:{self.colors['reset']}")
                for name in selected_names:
                    print(f"   • {name}")
                
                confirm = self.get_user_input("\nProceed with these test categories? (y/N):").lower()
                
                if confirm in ['y', 'yes']:
                    description = f"Custom selection: {', '.join(selected_names)}"
                    success = self.run_tests(selected_categories, description, use_legacy)
                    self.wait_for_continue()
            
            return
    
    def handle_comparison_menu(self):
        """Handle comparison menu for pytest vs JSON testing."""
        self.clear_screen()
        self.print_header()
        print(f"{self.colors['bold']}⚖️  TESTING SYSTEM COMPARISON{self.colors['reset']}")
        print("-" * 50)
        print("Compare JSON Test Engine vs Legacy Pytest systems")
        print()
        
        print("Available categories for comparison:")
        for i, (key, category) in enumerate(self.test_categories.items(), 1):
            print(f"{i:2d}. {category['name']}")
        
        print()
        choice = self.get_user_input("Select category to compare (1-9) or 'all':")
        
        if choice.lower() == 'all':
            category_keys = list(self.test_categories.keys())
        else:
            try:
                idx = int(choice) - 1
                categories_list = list(self.test_categories.keys())
                if 0 <= idx < len(categories_list):
                    category_keys = [categories_list[idx]]
                else:
                    print(f"{self.colors['red']}❌ Invalid selection{self.colors['reset']}")
                    self.wait_for_continue()
                    return
            except ValueError:
                print(f"{self.colors['red']}❌ Invalid input{self.colors['reset']}")
                self.wait_for_continue()
                return
        
        # Run comparison using the shell script functionality
        for category in category_keys:
            print(f"\n{self.colors['cyan']}🔄 Comparing {category} tests...{self.colors['reset']}")
            try:
                result = subprocess.run(
                    ["./test", category, "--compare"],
                    cwd=Path.cwd(),
                    text=True
                )
            except Exception as e:
                print(f"{self.colors['red']}❌ Comparison failed: {e}{self.colors['reset']}")
        
        self.wait_for_continue()
    
    def handle_legacy_mode(self):
        """Handle legacy pytest mode menu."""
        while True:
            self.clear_screen()
            self.print_header()
            print(f"{self.colors['bold']}{self.colors['red']}🔄 LEGACY PYTEST MODE{self.colors['reset']}")
            print("-" * 50)
            print("1. 🚀 Quick Collections (Pytest)")
            print("2. 🎯 Individual Categories (Pytest)")
            print("3. 🔧 Custom Selection (Pytest)")
            print("0. ← Back to Main Menu")
            print()
            
            choice = self.get_user_input("Select legacy option (0-3):")
            
            if choice == '0':
                return
            elif choice == '1':
                self.handle_collections_menu(use_legacy=True)
                return
            elif choice == '2':
                self.handle_categories_menu(use_legacy=True)
                return
            elif choice == '3':
                self.handle_custom_menu(use_legacy=True)
                return
            else:
                print(f"{self.colors['red']}❌ Invalid selection{self.colors['reset']}")
                self.wait_for_continue()
    
    def run(self):
        """Run the interactive test menu."""
        try:
            while True:
                self.clear_screen()
                self.print_header()
                self.print_main_menu()
                
                choice = self.get_user_input("Select option (1-11):")
                
                if choice == '1':
                    self.handle_collections_menu()
                elif choice == '2':
                    self.handle_categories_menu()
                elif choice == '3':
                    self.handle_custom_menu()
                elif choice == '4':
                    self.handle_test_generation_menu()
                elif choice == '5':
                    self.clear_screen()
                    self.print_header()
                    self.view_last_results()
                    self.wait_for_continue()
                elif choice == '6':
                    self.clear_screen()
                    self.print_header()
                    self.show_output_files()
                    self.wait_for_continue()
                elif choice == '7':
                    self.handle_comparison_menu()
                elif choice == '8':
                    self.clear_screen()
                    self.print_header()
                    print(f"{self.colors['bold']}{self.colors['red']}🔄 LEGACY PYTEST MODE{self.colors['reset']}")
                    print("-" * 50)
                    print(f"{self.colors['yellow']}⚠️  You are now using the legacy pytest system.{self.colors['reset']}")
                    print("This mode is provided for backward compatibility.")
                    print("The JSON test engine is recommended for new testing.")
                    print()
                    self.wait_for_continue()
                    self.handle_legacy_mode()
                elif choice == '9':
                    self.clear_screen()
                    self.print_header()
                    self.nuke_config()
                    self.wait_for_continue()
                elif choice == '10':
                    self.clear_screen()
                    self.print_header()
                    self.show_help()
                    self.wait_for_continue()
                elif choice == '11':
                    print(f"\n{self.colors['cyan']}👋 Thanks for using MCP Manager Test Suite!{self.colors['reset']}")
                    print("🚀 Keep testing, keep improving! ✨")
                    break
                else:
                    print(f"{self.colors['red']}❌ Invalid selection. Please choose 1-11.{self.colors['reset']}")
                    self.wait_for_continue()
                    
        except KeyboardInterrupt:
            print(f"\n\n{self.colors['yellow']}👋 Test menu interrupted. Goodbye!{self.colors['reset']}")
        except Exception as e:
            print(f"\n{self.colors['red']}💥 Unexpected error: {e}{self.colors['reset']}")


def main():
    """Main entry point."""
    # Check if we're in the right directory
    root_dir = Path(__file__).parent.parent.parent
    if not (root_dir / "tests/test_runner.py").exists():
        print("❌ Error: Please run this from the mcp-manager project root directory")
        print("   Expected to find: tests/test_runner.py")
        sys.exit(1)
    
    # Change to project root directory
    os.chdir(root_dir)
    
    # Create and run the menu
    menu = TestMenu()
    menu.run()


if __name__ == "__main__":
    main()