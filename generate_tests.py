#!/usr/bin/env python3
"""
MCP Manager Test Generator - Convenient CLI Wrapper

This is the main entry point for automated test generation. It provides a simple,
user-friendly interface for creating comprehensive JSON test files.

Usage Examples:
    python generate_tests.py                                    # Interactive guided mode
    python generate_tests.py new-feature                       # Quick generation for new-feature
    python generate_tests.py --ai mcp-manager export --desc "Export data functionality"
    python generate_tests.py --analyze mcp-manager workflow advanced
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tests.tools.auto_test_generator import AutoTestGenerator


def print_banner():
    """Print a friendly banner."""
    print("🤖 MCP Manager Test Generator")
    print("=" * 50)
    print("Automatically generate comprehensive JSON test files for CLI commands")
    print()


def print_usage():
    """Print usage examples."""
    print("📖 Usage Examples:")
    print("  python generate_tests.py                           # Interactive guided mode")
    print("  python generate_tests.py new-feature              # Quick mode for 'mcp-manager new-feature'")
    print("  python generate_tests.py --ai export              # AI-powered generation")
    print("  python generate_tests.py --analyze workflow       # Analyze command structure")
    print("  python generate_tests.py --help                   # Full help")
    print()


async def main():
    """Main entry point with simplified interface."""
    args = sys.argv[1:]
    
    # Show banner
    print_banner()
    
    # Handle no arguments - default to guided mode
    if not args:
        print("🎯 No command specified - launching interactive guided mode...")
        print()
        
        # Run guided mode
        generator = AutoTestGenerator()
        test_data = generator.guided_test_creation()
        
        if test_data and generator.validate_test_file(test_data):
            test_file_path = generator.create_test_file(test_data)
            generator.update_master_config(test_file_path, test_data)
            
            print()
            print("🎉 Test Generation Complete!")
            print(f"📁 Created: {test_file_path.name}")
            print(f"📊 Generated {len(test_data.get('test_scenarios', []))} test scenarios")
            
            # Show next steps
            print()
            print("💡 Next Steps:")
            print(f"   • Review tests: cat {test_file_path}")
            print(f"   • Run tests: python run_cli_tests.py --category {test_data.get('category', 'custom')}")
            print(f"   • Run all: python run_cli_tests.py")
            
            return 0
        else:
            print("❌ Test generation failed")
            return 1
    
    # Handle help
    if args[0] in ['-h', '--help', 'help']:
        print_usage()
        print("🔧 Advanced Options:")
        print("  --ai COMMAND         Use AI to generate comprehensive tests")
        print("  --analyze COMMAND    Analyze command structure")
        print("  --desc TEXT          Add description for AI generation")
        print("  --category CAT       Specify category (core, suite, api, etc.)")
        print("  --priority PRI       Set priority (critical, high, medium, low)")
        print()
        print("📂 Available Categories:")
        print("  core, discovery, suite, ai_analytics, system, interface, api, proxy, workflow, test_admin")
        print()
        return 0
    
    # Parse arguments
    ai_mode = False
    analyze_mode = False
    command = ""
    description = ""
    category = ""
    priority = ""
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == '--ai':
            ai_mode = True
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                command = f"mcp-manager {args[i + 1]}"
                i += 1
        elif arg == '--analyze':
            analyze_mode = True
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                command = f"mcp-manager {args[i + 1]}"
                i += 1
        elif arg == '--desc':
            if i + 1 < len(args):
                description = args[i + 1]
                i += 1
        elif arg == '--category':
            if i + 1 < len(args):
                category = args[i + 1]
                i += 1
        elif arg == '--priority':
            if i + 1 < len(args):
                priority = args[i + 1]
                i += 1
        elif not arg.startswith('--') and not command:
            # First non-option argument is the command
            command = f"mcp-manager {arg}"
        
        i += 1
    
    # Validate command
    if not command:
        print("❌ No command specified")
        print_usage()
        return 1
    
    if not command.startswith('mcp-manager'):
        command = f"mcp-manager {command}"
    
    print(f"🎯 Generating tests for: {command}")
    if description:
        print(f"📝 Description: {description}")
    if ai_mode:
        print("🤖 Mode: AI-Powered Generation")
    elif analyze_mode:
        print("🔬 Mode: Command Analysis")
    else:
        print("⚡ Mode: Quick Generation")
    print()
    
    try:
        generator = AutoTestGenerator()
        
        # Generate test data
        if ai_mode:
            print("🤖 Using AI to generate comprehensive test scenarios...")
            try:
                from tests.tools.ai_test_scenarios import ai_generate_tests_advanced
                test_data = await ai_generate_tests_advanced(command, description)
            except Exception as e:
                print(f"⚠️  AI generation failed ({e}), falling back to analysis mode...")
                test_data = generator.analyze_command_structure(command)
        elif analyze_mode:
            print("🔬 Analyzing command structure...")
            test_data = generator.analyze_command_structure(command)
        else:
            # Quick mode - analyze and apply overrides
            print("⚡ Quick generation mode...")
            test_data = generator.analyze_command_structure(command)
        
        # Apply overrides
        if category:
            test_data['category'] = category
        if priority:
            test_data['priority'] = priority
        if description and not ai_mode:
            test_data['test_suite_description'] = description
        
        # Validate and create
        if generator.validate_test_file(test_data):
            test_file_path = generator.create_test_file(test_data)
            generator.update_master_config(test_file_path, test_data)
            
            print()
            print("🎉 Test Generation Complete!")
            print(f"📁 File: {test_file_path.name}")
            print(f"📊 Scenarios: {len(test_data.get('test_scenarios', []))}")
            print(f"📂 Category: {test_data.get('category', 'custom')}")
            print(f"⭐ Priority: {test_data.get('priority', 'medium')}")
            
            print()
            print("💡 Next Steps:")
            print(f"   python run_cli_tests.py --category {test_data.get('category', 'custom')}")
            
            return 0
        else:
            print("❌ Test validation failed")
            return 1
            
    except KeyboardInterrupt:
        print("\\n🛑 Generation interrupted")
        return 130
    except Exception as e:
        print(f"\\n💥 Generation failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)