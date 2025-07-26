#!/usr/bin/env python3
"""
Automated Test Generator for MCP Manager CLI

This tool provides multiple ways to automatically generate comprehensive JSON test files:
1. Guided interactive prompts
2. AI-powered test generation from command descriptions
3. Command analysis and automatic test scenario creation

Usage:
    python tests/tools/auto_test_generator.py --guided
    python tests/tools/auto_test_generator.py --ai-generate --command "mcp-manager new-feature"
    python tests/tools/auto_test_generator.py --analyze-command "mcp-manager workflow advanced"
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse
import subprocess

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AutoTestGenerator:
    """Automated test generation with guided prompts and AI assistance."""
    
    def __init__(self):
        self.tests_dir = Path(__file__).parent.parent / "scenarios" / "cli_tests"
        self.master_config_path = self.tests_dir / "master_test_config.json"
        self.schema_path = Path(__file__).parent.parent / "schemas" / "test_scenario_schema.json"
        
    def load_master_config(self) -> Dict[str, Any]:
        """Load the master test configuration."""
        with open(self.master_config_path, 'r') as f:
            return json.load(f)
    
    def save_master_config(self, config: Dict[str, Any]):
        """Save updated master test configuration."""
        with open(self.master_config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_next_test_file_number(self) -> int:
        """Get the next available test file number."""
        existing_files = list(self.tests_dir.glob("*_*.json"))
        existing_numbers = []
        
        for file_path in existing_files:
            if file_path.name == "master_test_config.json":
                continue
            match = re.match(r"(\d+)_", file_path.name)
            if match:
                existing_numbers.append(int(match.group(1)))
        
        return max(existing_numbers, default=0) + 1
    
    def guided_test_creation(self) -> Dict[str, Any]:
        """Interactive guided test creation with user prompts."""
        print("🎯 Guided Test Generation")
        print("=" * 50)
        print("I'll help you create a comprehensive test file for your new CLI feature.\n")
        
        # Basic test suite info
        test_name = input("📝 Test Suite Name (e.g., 'New Feature Commands'): ").strip()
        if not test_name:
            test_name = "New Feature Commands"
        
        description = input("📄 Test Suite Description: ").strip()
        if not description:
            description = f"Tests for {test_name}"
        
        print("\\n📂 Available Categories:")
        categories = ["core", "discovery", "suite", "ai_analytics", "system", "interface", 
                     "api", "proxy", "workflow", "test_admin", "custom"]
        for i, cat in enumerate(categories, 1):
            print(f"   {i}. {cat}")
        
        while True:
            cat_choice = input("\\n🏷️  Select category (number or custom name): ").strip()
            if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(categories):
                category = categories[int(cat_choice) - 1]
                break
            elif cat_choice:
                category = cat_choice.lower().replace(" ", "_")
                break
            else:
                category = "custom"
                break
        
        print("\\n🎯 Available Priorities:")
        priorities = ["critical", "high", "medium", "low"]
        for i, pri in enumerate(priorities, 1):
            print(f"   {i}. {pri}")
        
        while True:
            pri_choice = input("\\n📊 Select priority (number): ").strip()
            if pri_choice.isdigit() and 1 <= int(pri_choice) <= len(priorities):
                priority = priorities[int(pri_choice) - 1]
                break
            else:
                priority = "medium"
                break
        
        # Command discovery
        print("\\n🔍 Let's discover the commands to test...")
        base_command = input("🖥️  Base command (e.g., 'mcp-manager new-feature'): ").strip()
        
        # Try to get help for the command
        subcommands = self.discover_subcommands(base_command)
        
        # Generate test scenarios
        scenarios = []
        print(f"\\n🧪 Generating test scenarios for '{base_command}'...")
        
        # Basic help test
        scenarios.append({
            "test_name": f"{base_command.replace('mcp-manager ', '').replace('-', '_')}_help",
            "description": f"Test {base_command} command help",
            "command": f"{base_command} --help",
            "expected_output_contains": [
                base_command.split()[-1],
                "--help"
            ],
            "expected_exit_code": 0,
            "timeout": 10
        })
        
        # Add subcommand tests if discovered
        for subcmd in subcommands:
            full_cmd = f"{base_command} {subcmd}"
            scenarios.append({
                "test_name": f"{subcmd.replace('-', '_')}_basic",
                "description": f"Test {full_cmd} basic functionality",
                "command": full_cmd,
                "expected_output_contains": [subcmd],
                "expected_exit_code": 0,
                "timeout": 15
            })
            
            # Help test for subcommand
            scenarios.append({
                "test_name": f"{subcmd.replace('-', '_')}_help",
                "description": f"Test {full_cmd} help",
                "command": f"{full_cmd} --help",
                "expected_output_contains": [subcmd, "--help"],
                "expected_exit_code": 0,
                "timeout": 10
            })
        
        # Let user add custom scenarios
        print(f"\\n✅ Generated {len(scenarios)} basic test scenarios")
        add_custom = input("\\n➕ Add custom test scenarios? (y/N): ").strip().lower()
        
        if add_custom in ['y', 'yes']:
            while True:
                print("\\n📝 Custom Test Scenario:")
                test_name = input("   Test name: ").strip()
                if not test_name:
                    break
                
                description = input("   Description: ").strip()
                command = input("   Command to test: ").strip()
                expected_output = input("   Expected output (comma-separated): ").strip()
                
                timeout = input("   Timeout in seconds (default 15): ").strip()
                timeout = int(timeout) if timeout.isdigit() else 15
                
                expected_list = [item.strip() for item in expected_output.split(',') if item.strip()]
                
                scenarios.append({
                    "test_name": test_name.replace(' ', '_').replace('-', '_'),
                    "description": description,
                    "command": command,
                    "expected_output_contains": expected_list,
                    "expected_exit_code": 0,
                    "timeout": timeout
                })
                
                another = input("\\n   Add another scenario? (y/N): ").strip().lower()
                if another not in ['y', 'yes']:
                    break
        
        return {
            "test_suite_name": test_name,
            "test_suite_description": description,
            "category": category,
            "priority": priority,
            "test_scenarios": scenarios
        }
    
    def discover_subcommands(self, base_command: str) -> List[str]:
        """Try to discover subcommands by running help."""
        try:
            result = subprocess.run(
                base_command.split() + ["--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Look for subcommands in help output
                subcommands = []
                lines = result.stdout.split('\\n')
                
                # Look for command patterns
                for line in lines:
                    # Pattern: "  command_name    Description"
                    if re.match(r'\\s{2,}([a-z][a-z0-9-]+)\\s+', line):
                        match = re.match(r'\\s{2,}([a-z][a-z0-9-]+)', line)
                        if match:
                            cmd = match.group(1)
                            if cmd not in ['help', 'version']:
                                subcommands.append(cmd)
                
                return subcommands[:10]  # Limit to avoid too many tests
                
        except Exception as e:
            logger.debug(f"Failed to discover subcommands for {base_command}: {e}")
        
        return []
    
    async def ai_generate_tests(self, command: str, description: str = "") -> Dict[str, Any]:
        """Use AI to generate comprehensive test scenarios."""
        print("🤖 AI-Powered Test Generation")
        print("=" * 50)
        
        # Check if AI is configured
        ai_available = self.check_ai_availability()
        if not ai_available:
            print("❌ AI not configured. Use guided mode instead.")
            return self.guided_test_creation()
        
        print(f"🎯 Generating AI tests for: {command}")
        
        # Create AI prompt for test generation
        prompt = self.create_ai_prompt(command, description)
        
        try:
            # Use the existing AI system if available
            from src.mcp_manager.core.ai_curation import AICurationSystem
            
            ai_system = AICurationSystem()
            response = await ai_system.generate_test_scenarios(prompt)
            
            if response and 'test_scenarios' in response:
                print(f"✅ AI generated {len(response['test_scenarios'])} test scenarios")
                return response
            else:
                print("⚠️  AI generation failed, falling back to guided mode")
                return self.guided_test_creation()
                
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            print("⚠️  AI generation failed, falling back to guided mode")
            return self.guided_test_creation()
    
    def check_ai_availability(self) -> bool:
        """Check if AI system is configured and available."""
        try:
            from src.mcp_manager.core.ai_config import AIConfig
            config = AIConfig()
            return config.is_configured()
        except:
            return False
    
    def create_ai_prompt(self, command: str, description: str) -> str:
        """Create AI prompt for test generation."""
        return f"""
Generate comprehensive JSON test scenarios for the MCP Manager CLI command: {command}

Description: {description}

Requirements:
1. Create 8-15 test scenarios covering:
   - Basic functionality test
   - Help command test  
   - Error handling (invalid arguments, missing parameters)
   - Edge cases and boundary conditions
   - Integration with existing MCP servers (Ref, filesystem, aws-diagram)

2. Follow this JSON schema:
{{
  "test_suite_name": "Command Name Tests",
  "test_suite_description": "Description of what this tests",
  "category": "appropriate_category",
  "priority": "high|medium|low",
  "test_scenarios": [
    {{
      "test_name": "descriptive_test_name",
      "description": "What this test validates",
      "command": "full command to execute",
      "expected_output_contains": ["output1", "output2"],
      "expected_exit_code": 0,
      "timeout": 15,
      "setup_commands": ["optional setup"],
      "cleanup_commands": ["optional cleanup"]
    }}
  ]
}}

3. Use realistic timeouts (10-30 seconds)
4. Include both positive and negative test cases
5. Reference existing database servers when possible
6. Ensure test names are unique and descriptive

Generate the complete JSON test suite:
"""
    
    def analyze_command_structure(self, command: str) -> Dict[str, Any]:
        """Analyze command structure and auto-generate basic tests."""
        print("🔬 Command Structure Analysis")
        print("=" * 50)
        
        # Parse command structure
        parts = command.split()
        if len(parts) < 2:
            print("❌ Invalid command format. Expected: mcp-manager <command>")
            return {}
        
        base_cmd = parts[0]
        feature = parts[1] if len(parts) > 1 else "unknown"
        subcommand = parts[2] if len(parts) > 2 else None
        
        print(f"🎯 Analyzing: {command}")
        print(f"   Base: {base_cmd}")
        print(f"   Feature: {feature}")
        print(f"   Subcommand: {subcommand}")
        
        # Auto-determine category based on feature name
        category_mapping = {
            'server': 'core',
            'suite': 'suite',
            'discover': 'discovery',
            'ai': 'ai_analytics',
            'analytics': 'ai_analytics',
            'api': 'api',
            'proxy': 'proxy',
            'workflow': 'workflow',
            'system': 'system',
            'config': 'system',
            'monitor': 'system',
            'tui': 'interface',
            'quality': 'ai_analytics',
            'tools': 'ai_analytics'
        }
        
        category = category_mapping.get(feature, 'custom')
        
        # Generate basic test scenarios
        scenarios = []
        
        # Help test
        scenarios.append({
            "test_name": f"{feature}_help",
            "description": f"Test {feature} command help",
            "command": f"{command} --help",
            "expected_output_contains": [feature, "--help"],
            "expected_exit_code": 0,
            "timeout": 10
        })
        
        # Basic functionality test
        scenarios.append({
            "test_name": f"{feature}_basic",
            "description": f"Test {feature} basic functionality",
            "command": command,
            "expected_output_contains": [feature],
            "expected_exit_code": 0,
            "timeout": 15
        })
        
        # Invalid argument test
        scenarios.append({
            "test_name": f"{feature}_invalid_args",
            "description": f"Test {feature} with invalid arguments",
            "command": f"{command} --invalid-flag",
            "expected_exit_code": 2,
            "timeout": 10
        })
        
        print(f"✅ Generated {len(scenarios)} basic scenarios")
        
        return {
            "test_suite_name": f"{feature.title()} Commands",
            "test_suite_description": f"Tests for {feature} command functionality",
            "category": category,
            "priority": "medium",
            "test_scenarios": scenarios
        }
    
    def create_test_file(self, test_data: Dict[str, Any]) -> Path:
        """Create the JSON test file."""
        file_number = self.get_next_test_file_number()
        category = test_data.get('category', 'custom')
        filename = f"{file_number:02d}_{category}_commands.json"
        file_path = self.tests_dir / filename
        
        with open(file_path, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        print(f"✅ Created test file: {filename}")
        return file_path
    
    def update_master_config(self, test_file_path: Path, test_data: Dict[str, Any]):
        """Update master configuration with new test file."""
        config = self.load_master_config()
        
        # Add new test suite entry
        new_entry = {
            "file": test_file_path.name,
            "category": test_data.get('category', 'custom'),
            "priority": test_data.get('priority', 'medium'),
            "test_count": len(test_data.get('test_scenarios', [])),
            "description": test_data.get('test_suite_description', '')
        }
        
        config['test_suites'].append(new_entry)
        config['execution_order'].append(test_file_path.name)
        
        # Update statistics
        config['test_statistics']['total_test_files'] += 1
        config['test_statistics']['total_test_scenarios'] += new_entry['test_count']
        
        self.save_master_config(config)
        print(f"✅ Updated master configuration")
    
    def validate_test_file(self, test_data: Dict[str, Any]) -> bool:
        """Validate test file against schema."""
        required_fields = ['test_suite_name', 'test_suite_description', 'category', 'priority', 'test_scenarios']
        
        for field in required_fields:
            if field not in test_data:
                print(f"❌ Missing required field: {field}")
                return False
        
        scenarios = test_data.get('test_scenarios', [])
        if not scenarios:
            print("❌ No test scenarios provided")
            return False
        
        # Validate each scenario
        for i, scenario in enumerate(scenarios):
            required_scenario_fields = ['test_name', 'description', 'command', 'expected_exit_code', 'timeout']
            for field in required_scenario_fields:
                if field not in scenario:
                    print(f"❌ Scenario {i+1} missing required field: {field}")
                    return False
        
        print(f"✅ Validation passed: {len(scenarios)} scenarios")
        return True


async def main():
    """Main CLI interface for auto test generation."""
    parser = argparse.ArgumentParser(
        description="Automated Test Generator for MCP Manager CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --guided                              # Interactive guided test creation
  %(prog)s --ai-generate --command "mcp-manager new-feature" --description "New feature description"
  %(prog)s --analyze --command "mcp-manager workflow advanced"
  %(prog)s --quick --command "mcp-manager export" --category system
        """
    )
    
    parser.add_argument(
        '--guided', 
        action='store_true',
        help='Interactive guided test creation with prompts'
    )
    
    parser.add_argument(
        '--ai-generate',
        action='store_true', 
        help='Use AI to generate comprehensive test scenarios'
    )
    
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze command structure and auto-generate basic tests'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test generation with minimal prompts'
    )
    
    parser.add_argument(
        '--command',
        required=True,
        help='Command to generate tests for (e.g., "mcp-manager new-feature")'
    )
    
    parser.add_argument(
        '--description',
        help='Description of the command functionality'
    )
    
    parser.add_argument(
        '--category',
        help='Test category (core, discovery, suite, etc.)'
    )
    
    parser.add_argument(
        '--priority',
        choices=['critical', 'high', 'medium', 'low'],
        help='Test priority level'
    )
    
    args = parser.parse_args()
    
    generator = AutoTestGenerator()
    
    print("🚀 MCP Manager Auto Test Generator")
    print("=" * 60)
    print(f"Command: {args.command}")
    print(f"Mode: {'Guided' if args.guided else 'AI-Powered' if args.ai_generate else 'Analysis' if args.analyze else 'Quick'}")
    print()
    
    try:
        # Generate test data based on mode
        if args.guided:
            test_data = generator.guided_test_creation()
        elif args.ai_generate:
            test_data = await generator.ai_generate_tests(args.command, args.description or "")
        elif args.analyze:
            test_data = generator.analyze_command_structure(args.command)
        else:  # quick mode
            test_data = generator.analyze_command_structure(args.command)
            # Override with provided values
            if args.category:
                test_data['category'] = args.category
            if args.priority:
                test_data['priority'] = args.priority
            if args.description:
                test_data['test_suite_description'] = args.description
        
        if not test_data:
            print("❌ Failed to generate test data")
            return 1
        
        # Validate test data
        if not generator.validate_test_file(test_data):
            print("❌ Test validation failed")
            return 1
        
        # Create test file
        test_file_path = generator.create_test_file(test_data)
        
        # Update master configuration  
        generator.update_master_config(test_file_path, test_data)
        
        print()
        print("🎉 Test Generation Complete!")
        print(f"📁 Test file: {test_file_path}")
        print(f"📊 Generated {len(test_data.get('test_scenarios', []))} test scenarios")
        print()
        print("💡 Next steps:")
        print(f"   • Review the generated tests in {test_file_path.name}")
        print(f"   • Run tests: python run_cli_tests.py --category {test_data.get('category', 'custom')}")
        print(f"   • Run all tests: python run_cli_tests.py")
        
        return 0
        
    except KeyboardInterrupt:
        print("\\n🛑 Test generation interrupted by user")
        return 130
    except Exception as e:
        print(f"\\n💥 Test generation failed: {e}")
        logger.error(f"Test generation error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)