"""
Pytest to JSON Scenario Converter.

Automatically converts existing pytest test classes to JSON test scenarios
for use with the dynamic test engine.
"""

import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class PytestToJsonConverter:
    """Converts pytest test classes to JSON scenarios."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize converter."""
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "scenarios" / "migrated"
        
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Mapping of test file patterns to categories
        self.file_to_category = {
            "test_basic_commands": "core",
            "test_server_management": "core", 
            "test_suite_management": "core",
            "test_workflows": "workflow",
            "test_error_handling": "regression",
            "test_quality_tracking": "integration",
            "test_runner": "integration"
        }
        
        # Priority mapping based on test markers and naming
        self.priority_patterns = {
            "smoke": "critical",
            "critical": "critical",
            "basic": "high",
            "core": "high",
            "workflow": "medium",
            "integration": "medium",
            "regression": "low"
        }
    
    def convert_test_file(self, test_file_path: Path) -> List[Dict[str, Any]]:
        """
        Convert a pytest file to JSON scenarios.
        
        Args:
            test_file_path: Path to pytest file
            
        Returns:
            List of JSON scenario dictionaries
        """
        logger.info(f"🔄 Converting {test_file_path.name} to JSON scenarios")
        
        try:
            with open(test_file_path, 'r') as f:
                content = f.read()
            
            # Parse Python AST
            tree = ast.parse(content)
            
            scenarios = []
            
            # Find test classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                    class_scenarios = self._convert_test_class(node, test_file_path, content)
                    scenarios.extend(class_scenarios)
            
            logger.info(f"✅ Converted {len(scenarios)} scenarios from {test_file_path.name}")
            return scenarios
            
        except Exception as e:
            logger.error(f"❌ Failed to convert {test_file_path}: {e}")
            return []
    
    def _convert_test_class(self, class_node: ast.ClassDef, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Convert a test class to JSON scenarios."""
        scenarios = []
        
        # Extract class information
        class_name = class_node.name
        class_docstring = ast.get_docstring(class_node) or ""
        
        # Determine category from file name
        file_stem = file_path.stem
        category = self.file_to_category.get(file_stem, "integration")
        
        # Find test methods
        test_methods = [
            node for node in class_node.body 
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')
        ]
        
        for method_node in test_methods:
            scenario = self._convert_test_method(
                method_node, class_name, category, file_path, content
            )
            if scenario:
                scenarios.append(scenario)
        
        return scenarios
    
    def _convert_test_method(self, 
                           method_node: ast.FunctionDef, 
                           class_name: str,
                           category: str,
                           file_path: Path,
                           content: str) -> Optional[Dict[str, Any]]:
        """Convert a test method to a JSON scenario."""
        try:
            method_name = method_node.name
            method_docstring = ast.get_docstring(method_node) or ""
            
            # Generate scenario ID
            scenario_id = self._generate_scenario_id(class_name, method_name)
            
            # Generate human-readable name
            scenario_name = self._generate_scenario_name(method_name, method_docstring)
            
            # Extract test steps from method body
            test_steps = self._extract_test_steps(method_node, content)
            
            # Determine priority
            priority = self._determine_priority(method_name, method_docstring, category)
            
            # Extract MCP requirements (simplified)
            mcp_requirements = self._extract_mcp_requirements(method_node, content, category, scenario_id)
            
            # Create scenario
            scenario = {
                "schema_version": "1.0",
                "scenario": {
                    "id": scenario_id,
                    "name": scenario_name,
                    "description": method_docstring or f"Migrated from {class_name}.{method_name}",
                    "created_by": "migration",
                    "category": category,
                    "confidence_score": 0.85,
                    "ai_reasoning": f"Automatically migrated from pytest test {class_name}.{method_name}",
                    "tags": self._extract_tags(method_name, method_docstring),
                    "priority": priority
                },
                "mcp_requirements": mcp_requirements,
                "test_steps": test_steps,
                "validation": {
                    "success_criteria": [
                        {
                            "type": "all_steps_pass",
                            "description": "All test steps must complete successfully"
                        }
                    ],
                    "failure_conditions": [
                        {
                            "type": "timeout",
                            "description": "Test steps timeout",
                            "value": "300"
                        }
                    ],
                    "cleanup_required": True,
                    "cleanup_steps": [
                        {
                            "action": "reset_config",
                            "ignore_errors": True
                        }
                    ]
                },
                "metadata": {
                    "created_date": datetime.now().isoformat(),
                    "last_modified": datetime.now().isoformat(),
                    "execution_count": 0,
                    "success_rate": 0.0,
                    "average_duration": 0.0,
                    "related_scenarios": []
                }
            }
            
            return scenario
            
        except Exception as e:
            logger.warning(f"Failed to convert method {method_name}: {e}")
            return None
    
    def _generate_scenario_id(self, class_name: str, method_name: str) -> str:
        """Generate a unique scenario ID."""
        # Convert class name from CamelCase to snake_case
        class_snake = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name.replace('Test', '')).lower()
        
        # Remove test_ prefix from method name
        method_clean = method_name.replace('test_', '')
        
        return f"{class_snake}_{method_clean}"
    
    def _generate_scenario_name(self, method_name: str, docstring: str) -> str:
        """Generate human-readable scenario name."""
        if docstring and '.' in docstring:
            # Use first sentence of docstring
            return docstring.split('.')[0].strip()
        
        # Convert method name to title case
        name = method_name.replace('test_', '').replace('_', ' ').title()
        return name
    
    def _extract_test_steps(self, method_node: ast.FunctionDef, content: str) -> List[Dict[str, Any]]:
        """Extract test steps from method body."""
        steps = []
        step_id = 1
        
        # This is a simplified extraction - in practice, we'd need more sophisticated parsing
        for stmt in method_node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                
                # Look for CLI runner calls
                if (hasattr(call.func, 'attr') and 
                    call.func.attr == 'run_command' and
                    call.args):
                    
                    command_arg = call.args[0]
                    if isinstance(command_arg, ast.Constant):
                        command = command_arg.value
                        
                        # Determine if we expect success or failure
                        expect = "success"  # Default
                        
                        # Look for expect_success=False in kwargs
                        for keyword in call.keywords:
                            if keyword.arg == 'expect_success' and isinstance(keyword.value, ast.Constant):
                                if not keyword.value.value:
                                    expect = "failure"
                        
                        step = {
                            "step_id": step_id,
                            "action": "cli_command",
                            "command": command,
                            "expect": expect,
                            "timeout": 30,
                            "setup_required": False,
                            "cleanup_on_failure": True,
                            "retry_count": 0,
                            "description": f"Execute: {command}"
                        }
                        
                        steps.append(step)
                        step_id += 1
        
        # If no steps found, create a placeholder
        if not steps:
            steps = [{
                "step_id": 1,
                "action": "cli_command",
                "command": "--help",
                "expect": "success",
                "timeout": 15,
                "description": "Placeholder command - requires manual conversion"
            }]
        
        return steps
    
    def _determine_priority(self, method_name: str, docstring: str, category: str) -> str:
        """Determine scenario priority."""
        text = f"{method_name} {docstring}".lower()
        
        for pattern, priority in self.priority_patterns.items():
            if pattern in text:
                return priority
        
        # Default based on category
        if category == "smoke":
            return "critical"
        elif category == "core":
            return "high"
        else:
            return "medium"
    
    def _extract_mcp_requirements(self, method_node: ast.FunctionDef, content: str, category: str, scenario_id: str) -> Dict[str, Any]:
        """Extract MCP server requirements for REAL MCP deployment testing."""
        # MCP Manager tests SHOULD deploy real MCPs to test:
        # 1. Installation/removal works correctly
        # 2. Claude Code integration doesn't break
        # 3. Quality tracking (does it break Claude?)
        # We don't care if the MCP functions - only that it installs/integrates cleanly
        
        method_content = ast.get_source_segment(content, method_node) or ""
        method_lower = method_content.lower()
        method_name = method_node.name.lower()
        
        required_servers = []
        scope = "user"  # Most tests should use user scope for real deployment
        
        # Server patterns for REAL deployment testing
        server_patterns = {
            "filesystem": {"name": "modelcontextprotocol-filesystem", "type": "npm"},
            "sqlite": {"name": "dd-SQLite", "type": "docker-desktop"}, 
            "http": {"name": "dd-http", "type": "docker-desktop"},
            "search": {"name": "dd-search", "type": "docker-desktop"},
            "playwright": {"name": "playwright-server", "type": "npm"},
            "brave": {"name": "brave-search", "type": "npm"}
        }
        
        # Look for server mentions in test names and content
        for pattern, server_info in server_patterns.items():
            if (pattern in method_lower or 
                pattern in method_content.lower() or
                f"install-package {pattern}" in method_content.lower() or
                f"discover --query {pattern}" in method_content.lower()):
                
                required_servers.append({
                    "name": server_info["name"],
                    "type": server_info["type"],
                    "priority": "high",
                    "purpose": f"Test MCP Manager deployment and Claude Code integration"
                })
        
        # Workflow tests typically need multiple servers for comprehensive testing
        if "workflow" in category.lower() or "complete" in method_name:
            # Add common servers for workflow testing if not already included
            common_servers = [
                {"name": "modelcontextprotocol-filesystem", "type": "npm", "priority": "high"},
                {"name": "dd-SQLite", "type": "docker-desktop", "priority": "medium"}
            ]
            
            for server in common_servers:
                if not any(s["name"] == server["name"] for s in required_servers):
                    required_servers.append(server)
        
        # Some tests are pure CLI tests (help, version, etc.) - no servers needed
        cli_only_patterns = [
            "help", "version", "invalid", "missing_arg", "empty", "malformed"
        ]
        
        is_cli_only = any(pattern in method_name for pattern in cli_only_patterns)
        
        if is_cli_only:
            required_servers = []
            scope = "isolated"
        
        return {
            "required_servers": required_servers,
            "optional_servers": [],
            "scope": scope,
            "deduplication_key": f"{category}_{scenario_id}",
            "resource_requirements": {
                "min_memory_mb": 64 + (len(required_servers) * 32),
                "max_execution_time_seconds": 60 + (len(required_servers) * 30),
                "parallel_safe": len(required_servers) <= 1  # Multiple servers may conflict
            }
        }
    
    def _extract_tags(self, method_name: str, docstring: str) -> List[str]:
        """Extract tags from method name and docstring."""
        tags = []
        
        text = f"{method_name} {docstring}".lower()
        
        # Common tag patterns
        tag_patterns = {
            "basic": ["basic", "fundamental"],
            "advanced": ["advanced", "complex"],
            "error": ["error", "failure", "exception"],
            "integration": ["integration", "end-to-end"],
            "performance": ["performance", "speed", "timeout"],
            "security": ["security", "permission", "auth"],
            "cli": ["command", "cli"],
            "server": ["server", "mcp"],
            "config": ["config", "configuration"],
            "discovery": ["discover", "search", "find"]
        }
        
        for tag, patterns in tag_patterns.items():
            if any(pattern in text for pattern in patterns):
                tags.append(tag)
        
        return tags[:5]  # Limit to 5 tags
    
    def convert_all_test_files(self, test_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
        """Convert all test files in a directory."""
        results = {}
        
        test_files = list(test_dir.glob("test_*.py"))
        logger.info(f"🔄 Converting {len(test_files)} test files")
        
        for test_file in test_files:
            # Skip certain files
            if test_file.name in ["test_runner.py", "__init__.py"]:
                continue
            
            scenarios = self.convert_test_file(test_file)
            if scenarios:
                results[str(test_file)] = scenarios
        
        return results
    
    def save_scenarios(self, scenarios: List[Dict[str, Any]], category: str, prefix: str = "") -> List[Path]:
        """Save scenarios to JSON files organized by category."""
        saved_files = []
        
        # Group scenarios by category if not specified
        if not category:
            category_groups = {}
            for scenario in scenarios:
                cat = scenario["scenario"]["category"]
                if cat not in category_groups:
                    category_groups[cat] = []
                category_groups[cat].append(scenario)
        else:
            category_groups = {category: scenarios}
        
        for cat, cat_scenarios in category_groups.items():
            # Create category directory
            cat_dir = self.output_dir / cat
            cat_dir.mkdir(exist_ok=True)
            
            # Save each scenario as a separate file
            for scenario in cat_scenarios:
                scenario_id = scenario["scenario"]["id"]
                filename = f"{prefix}{scenario_id}.json"
                file_path = cat_dir / filename
                
                with open(file_path, 'w') as f:
                    json.dump(scenario, f, indent=2)
                
                saved_files.append(file_path)
                logger.debug(f"💾 Saved scenario: {file_path}")
        
        return saved_files
    
    def generate_conversion_report(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Generate a report of the conversion process."""
        total_files = len(results)
        total_scenarios = sum(len(scenarios) for scenarios in results.values())
        
        categories = {}
        priorities = {}
        
        for scenarios in results.values():
            for scenario in scenarios:
                cat = scenario["scenario"]["category"]
                pri = scenario["scenario"]["priority"]
                
                categories[cat] = categories.get(cat, 0) + 1
                priorities[pri] = priorities.get(pri, 0) + 1
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_files_converted": total_files,
            "total_scenarios_created": total_scenarios,
            "scenarios_per_file": total_scenarios / total_files if total_files > 0 else 0,
            "categories": dict(sorted(categories.items())),
            "priorities": dict(sorted(priorities.items())),
            "files_converted": list(results.keys())
        }

def convert_existing_tests():
    """Main function to convert all existing tests."""
    converter = PytestToJsonConverter()
    
    # Convert all test files
    test_dir = Path(__file__).parent.parent
    results = converter.convert_all_test_files(test_dir)
    
    # Save all scenarios
    all_saved_files = []
    for file_path, scenarios in results.items():
        file_name = Path(file_path).stem
        category = converter.file_to_category.get(file_name, "integration")
        saved_files = converter.save_scenarios(scenarios, category, "migrated_")
        all_saved_files.extend(saved_files)
    
    # Generate report
    report = converter.generate_conversion_report(results)
    
    # Save report
    report_path = converter.output_dir / "conversion_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\\n🎯 Conversion Complete!")
    print(f"{'='*50}")
    print(f"📁 Files Converted: {report['total_files_converted']}")
    print(f"📋 Scenarios Created: {report['total_scenarios_created']}")
    print(f"📊 Average per File: {report['scenarios_per_file']:.1f}")
    print(f"💾 Saved to: {converter.output_dir}")
    print(f"📄 Report: {report_path}")
    
    return all_saved_files, report

if __name__ == "__main__":
    convert_existing_tests()