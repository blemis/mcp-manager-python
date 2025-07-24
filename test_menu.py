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
        self.test_categories = {
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
        print("4. 📊 View Last Test Results")
        print("5. ❓ Help & Documentation")
        print("6. 🚪 Exit")
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
    
    def run_tests(self, categories: List[str], description: str = "") -> bool:
        """Run the specified test categories."""
        if not categories:
            print(f"{self.colors['red']}❌ No test categories specified{self.colors['reset']}")
            return False
        
        print(f"{self.colors['bold']}{self.colors['blue']}")
        print("🚀 STARTING TEST EXECUTION")
        print("=" * 60)
        print(f"Categories: {', '.join(categories)}")
        if description:
            print(f"Description: {description}")
        print("=" * 60)
        print(f"{self.colors['reset']}")
        
        # Run the test runner
        cmd = [sys.executable, "tests/test_runner.py"] + categories
        
        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                cwd=Path.cwd(),
                capture_output=False,  # Show output in real-time
                text=True
            )
            duration = time.time() - start_time
            
            print(f"\n{self.colors['bold']}")
            print("=" * 60)
            if result.returncode == 0:
                print(f"{self.colors['green']}🎉 ALL TESTS PASSED!{self.colors['reset']}")
                print(f"✨ Test execution completed successfully in {duration:.1f}s")
            else:
                print(f"{self.colors['red']}❌ SOME TESTS FAILED{self.colors['reset']}")
                print(f"⚠️  Test execution completed with issues in {duration:.1f}s")
                print("📋 Check the detailed output above for specific failures")
            print("=" * 60)
            print(f"{self.colors['reset']}")
            
            return result.returncode == 0
            
        except KeyboardInterrupt:
            print(f"\n{self.colors['yellow']}⚠️  Test execution interrupted by user{self.colors['reset']}")
            return False
        except Exception as e:
            print(f"{self.colors['red']}💥 Test execution failed: {e}{self.colors['reset']}")
            return False
    
    def view_last_results(self):
        """View the last test results."""
        results_file = Path("test-results-summary.json")
        
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
        
        print(f"{self.colors['cyan']}💡 Tips:{self.colors['reset']}")
        print("• Always start with Smoke Tests for critical issues")
        print("• Use Custom Selection for specific feature testing")
        print("• Check Last Results to track test history")
        print("• Tests run in isolated environments (safe to execute)")
        print()
        
        print(f"{self.colors['cyan']}🔧 Manual Commands (if needed):{self.colors['reset']}")
        print("• python tests/test_runner.py smoke")
        print("• python tests/test_runner.py all")
        print("• python -m pytest tests/ -v")
        print()
    
    def get_user_input(self, prompt: str) -> str:
        """Get user input with styled prompt."""
        return input(f"{self.colors['bold']}{prompt}{self.colors['reset']} ").strip()
    
    def wait_for_continue(self):
        """Wait for user to continue."""
        self.get_user_input("\n🔄 Press Enter to continue...")
    
    def handle_collections_menu(self):
        """Handle the collections menu selection."""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_collections_menu()
            
            choice = self.get_user_input("Select collection (0-4):")
            
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
                        success = self.run_tests(collection['categories'], collection['description'])
                        self.wait_for_continue()
                    return
                else:
                    print(f"{self.colors['red']}❌ Invalid selection{self.colors['reset']}")
                    self.wait_for_continue()
                    
            except ValueError:
                print(f"{self.colors['red']}❌ Please enter a valid number{self.colors['reset']}")
                self.wait_for_continue()
    
    def handle_categories_menu(self):
        """Handle individual categories menu selection."""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_categories_menu()
            
            choice = self.get_user_input("Select category (0-9):")
            
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
                        success = self.run_tests([key], category['description'])
                        self.wait_for_continue()
                    return
                else:
                    print(f"{self.colors['red']}❌ Invalid selection{self.colors['reset']}")
                    self.wait_for_continue()
                    
            except ValueError:
                print(f"{self.colors['red']}❌ Please enter a valid number{self.colors['reset']}")
                self.wait_for_continue()
    
    def handle_custom_menu(self):
        """Handle custom test selection."""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_custom_menu()
            
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
                    success = self.run_tests(selected_categories, description)
                    self.wait_for_continue()
            
            return
    
    def run(self):
        """Run the interactive test menu."""
        try:
            while True:
                self.clear_screen()
                self.print_header()
                self.print_main_menu()
                
                choice = self.get_user_input("Select option (1-6):")
                
                if choice == '1':
                    self.handle_collections_menu()
                elif choice == '2':
                    self.handle_categories_menu()
                elif choice == '3':
                    self.handle_custom_menu()
                elif choice == '4':
                    self.clear_screen()
                    self.print_header()
                    self.view_last_results()
                    self.wait_for_continue()
                elif choice == '5':
                    self.clear_screen()
                    self.print_header()
                    self.show_help()
                    self.wait_for_continue()
                elif choice == '6':
                    print(f"\n{self.colors['cyan']}👋 Thanks for using MCP Manager Test Suite!{self.colors['reset']}")
                    print("🚀 Keep testing, keep improving! ✨")
                    break
                else:
                    print(f"{self.colors['red']}❌ Invalid selection. Please choose 1-6.{self.colors['reset']}")
                    self.wait_for_continue()
                    
        except KeyboardInterrupt:
            print(f"\n\n{self.colors['yellow']}👋 Test menu interrupted. Goodbye!{self.colors['reset']}")
        except Exception as e:
            print(f"\n{self.colors['red']}💥 Unexpected error: {e}{self.colors['reset']}")


def main():
    """Main entry point."""
    # Check if we're in the right directory
    if not Path("tests/test_runner.py").exists():
        print("❌ Error: Please run this from the mcp-manager project root directory")
        print("   Expected to find: tests/test_runner.py")
        sys.exit(1)
    
    # Create and run the menu
    menu = TestMenu()
    menu.run()


if __name__ == "__main__":
    main()