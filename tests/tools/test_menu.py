#!/usr/bin/env python3
"""
Clean Test Menu for MCP Manager

Simple, functional menu system built from scratch.
Uses the working test runner and actual categories.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)


class TestMenu:
    """Simple test menu that works with the actual test runner."""
    
    def __init__(self):
        self.colors = {
            'reset': '\033[0m',
            'bold': '\033[1m',
            'green': '\033[92m',
            'red': '\033[91m',
            'blue': '\033[94m',
            'yellow': '\033[93m',
            'cyan': '\033[96m'
        }
        
        # Load actual categories from the working test runner
        self.categories = self._get_actual_categories()
    
    def _get_actual_categories(self) -> Dict[str, Dict]:
        """Get real test categories from the working test runner."""
        try:
            result = subprocess.run(
                [sys.executable, "tests/runner.py", "--list"],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            categories = {}
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if ':' in line and 'tests)' in line:
                        # Parse line like "   core: Core Commands (15 tests)"
                        parts = line.strip().split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            desc_part = parts[1].strip()
                            # Extract test count
                            if '(' in desc_part and 'tests)' in desc_part:
                                desc = desc_part.split('(')[0].strip()
                                test_count = desc_part.split('(')[1].split(' tests)')[0]
                                categories[key] = {
                                    'name': desc,
                                    'test_count': int(test_count),
                                    'priority': 'HIGH' if key in ['core', 'discovery'] else 'MEDIUM'
                                }
            
            return categories
            
        except Exception as e:
            print(f"Warning: Could not load categories: {e}")
            return {}
    
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Print the application header."""
        print(f"{self.colors['bold']}{self.colors['cyan']}")
        print("=" * 60)
        print("🧪 MCP MANAGER TEST MENU")
        print("Simple, Working Test Interface")
        print("=" * 60)
        print(f"{self.colors['reset']}")
    
    def run_tests(self, category: str, show_summary: bool = False, save_report: str = None):
        """Run tests using the working test runner."""
        cmd = [sys.executable, "tests/runner.py", category]
        
        if show_summary:
            cmd.append("--summary")
        
        if save_report:
            cmd.extend(["--save-report", save_report])
        
        print(f"\n{self.colors['cyan']}🚀 Running {category} tests...{self.colors['reset']}")
        print("=" * 50)
        
        try:
            result = subprocess.run(cmd, cwd=project_root, text=True)
            
            if result.returncode == 0:
                print(f"\n{self.colors['green']}✅ Tests completed successfully!{self.colors['reset']}")
            else:
                print(f"\n{self.colors['red']}❌ Some tests failed{self.colors['reset']}")
                
        except Exception as e:
            print(f"{self.colors['red']}Error running tests: {e}{self.colors['reset']}")
    
    def show_categories(self):
        """Show available test categories."""
        if not self.categories:
            print(f"{self.colors['red']}No test categories found{self.colors['reset']}")
            return
        
        print(f"{self.colors['bold']}📋 Available Test Categories:{self.colors['reset']}")
        print("-" * 40)
        
        for i, (key, info) in enumerate(self.categories.items(), 1):
            name = info['name']
            count = info['test_count']
            priority = info['priority']
            
            color = self.colors['red'] if priority == 'HIGH' else self.colors['yellow']
            print(f"{color}{i:2d}. {key:<12} {self.colors['reset']}- {name} ({count} tests)")
        
        print()
    
    def run_bug_report_mode(self):
        """Run tests in bug report mode."""
        print(f"{self.colors['bold']}{self.colors['red']}🐛 BUG REPORT MODE{self.colors['reset']}")
        print("-" * 40)
        print("Generate failure summaries for systematic bug fixing")
        print()
        
        self.show_categories()
        
        choice = input(f"{self.colors['bold']}Select category number (or 'q' to quit): {self.colors['reset']}").strip()
        
        if choice.lower() == 'q':
            return
        
        try:
            idx = int(choice) - 1
            categories_list = list(self.categories.keys())
            if 0 <= idx < len(categories_list):
                category = categories_list[idx]
                print(f"\n{self.colors['yellow']}Running {category} tests with failure summary...{self.colors['reset']}")
                self.run_tests(category, show_summary=True)
            else:
                print(f"{self.colors['red']}Invalid selection{self.colors['reset']}")
        except ValueError:
            print(f"{self.colors['red']}Invalid input{self.colors['reset']}")
    
    def main_menu(self):
        """Show the main menu."""
        while True:
            self.clear_screen()
            self.print_header()
            
            print(f"{self.colors['bold']}Main Menu:{self.colors['reset']}")
            print("1. 📋 Show Available Categories")
            print("2. 🚀 Run Test Category")
            print("3. 🐛 Bug Report Mode")
            print("4. 🚪 Exit")
            print()
            
            choice = input(f"{self.colors['bold']}Select option (1-4): {self.colors['reset']}").strip()
            
            if choice == '1':
                self.show_categories()
                input(f"\n{self.colors['bold']}Press Enter to continue...{self.colors['reset']}")
                
            elif choice == '2':
                self.show_categories()
                cat_choice = input(f"{self.colors['bold']}Select category number: {self.colors['reset']}").strip()
                
                try:
                    idx = int(cat_choice) - 1
                    categories_list = list(self.categories.keys())
                    if 0 <= idx < len(categories_list):
                        category = categories_list[idx]
                        self.run_tests(category)
                        input(f"\n{self.colors['bold']}Press Enter to continue...{self.colors['reset']}")
                    else:
                        print(f"{self.colors['red']}Invalid selection{self.colors['reset']}")
                        input(f"{self.colors['bold']}Press Enter to continue...{self.colors['reset']}")
                except ValueError:
                    print(f"{self.colors['red']}Invalid input{self.colors['reset']}")
                    input(f"{self.colors['bold']}Press Enter to continue...{self.colors['reset']}")
                    
            elif choice == '3':
                self.run_bug_report_mode()
                input(f"\n{self.colors['bold']}Press Enter to continue...{self.colors['reset']}")
                
            elif choice == '4':
                print(f"\n{self.colors['cyan']}👋 Thanks for using MCP Manager Test Suite!{self.colors['reset']}")
                break
                
            else:
                print(f"{self.colors['red']}Invalid selection{self.colors['reset']}")
                input(f"{self.colors['bold']}Press Enter to continue...{self.colors['reset']}")


def main():
    """Main entry point."""
    menu = TestMenu()
    menu.main_menu()


if __name__ == "__main__":
    main()