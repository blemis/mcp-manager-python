"""
AI-Powered Test Scenario Generation Extension

This module extends the auto test generator with advanced AI capabilities
for creating comprehensive, intelligent test scenarios.
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path

from src.mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AITestScenarioGenerator:
    """Advanced AI-powered test scenario generation."""
    
    def __init__(self):
        self.ai_system = None
        self._initialize_ai()
    
    def _initialize_ai(self):
        """Initialize AI system if available."""
        try:
            from src.mcp_manager.core.ai_curation import AICurationSystem
            self.ai_system = AICurationSystem()
        except ImportError:
            logger.warning("AI curation system not available")
    
    async def generate_comprehensive_tests(self, command: str, description: str = "") -> Dict[str, Any]:
        """Generate comprehensive test scenarios using AI analysis."""
        if not self.ai_system:
            raise RuntimeError("AI system not available")
        
        # Analyze command structure
        command_analysis = self._analyze_command_structure(command)
        
        # Generate AI prompt
        prompt = self._create_comprehensive_prompt(command, description, command_analysis)
        
        # Get AI response
        try:
            response = await self.ai_system.analyze_and_generate(prompt)
            return self._parse_ai_response(response, command)
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise
    
    def _analyze_command_structure(self, command: str) -> Dict[str, Any]:
        """Analyze command structure for AI context."""
        parts = command.split()
        
        analysis = {
            "base_command": parts[0] if parts else "",
            "primary_feature": parts[1] if len(parts) > 1 else "",
            "subcommand": parts[2] if len(parts) > 2 else None,
            "complexity_level": self._assess_complexity(command),
            "category_hints": self._get_category_hints(command),
            "integration_requirements": self._get_integration_hints(command)
        }
        
        return analysis
    
    def _assess_complexity(self, command: str) -> str:
        """Assess command complexity for test generation."""
        complex_keywords = ['workflow', 'ai', 'analytics', 'proxy', 'api', 'advanced']
        medium_keywords = ['suite', 'discovery', 'config', 'system']
        
        cmd_lower = command.lower()
        
        if any(keyword in cmd_lower for keyword in complex_keywords):
            return "high"
        elif any(keyword in cmd_lower for keyword in medium_keywords):
            return "medium"
        else:
            return "low"
    
    def _get_category_hints(self, command: str) -> List[str]:
        """Get category hints based on command analysis."""
        cmd_lower = command.lower()
        hints = []
        
        category_mapping = {
            'server': ['core', 'server-management'],
            'suite': ['suite', 'configuration'],
            'discover': ['discovery', 'installation'],
            'ai': ['ai_analytics', 'intelligence'],
            'analytics': ['ai_analytics', 'data'],
            'api': ['api', 'server'],
            'proxy': ['proxy', 'network'],
            'workflow': ['workflow', 'automation'],
            'system': ['system', 'configuration'],
            'monitor': ['system', 'monitoring'],
            'tui': ['interface', 'user-experience'],
            'quality': ['ai_analytics', 'quality-assurance'],
            'tools': ['ai_analytics', 'utilities']
        }
        
        for keyword, categories in category_mapping.items():
            if keyword in cmd_lower:
                hints.extend(categories)
        
        return list(set(hints))
    
    def _get_integration_hints(self, command: str) -> List[str]:
        """Get integration requirements hints."""
        cmd_lower = command.lower()
        integrations = []
        
        if any(word in cmd_lower for word in ['server', 'suite', 'install']):
            integrations.append("database_servers")
        
        if any(word in cmd_lower for word in ['docker', 'container']):
            integrations.append("docker_desktop")
        
        if any(word in cmd_lower for word in ['api', 'proxy', 'network']):
            integrations.append("network_services")
        
        if any(word in cmd_lower for word in ['ai', 'analytics', 'quality']):
            integrations.append("ai_services")
        
        return integrations
    
    def _create_comprehensive_prompt(self, command: str, description: str, analysis: Dict[str, Any]) -> str:
        """Create comprehensive AI prompt for test generation."""
        
        available_servers = ["Ref", "filesystem", "aws-diagram"]
        
        prompt = f"""
You are a senior QA engineer creating comprehensive test scenarios for the MCP Manager CLI.

COMMAND TO TEST: {command}
DESCRIPTION: {description}
COMPLEXITY LEVEL: {analysis.get('complexity_level', 'medium')}
CATEGORY HINTS: {', '.join(analysis.get('category_hints', []))}
INTEGRATION NEEDS: {', '.join(analysis.get('integration_requirements', []))}

AVAILABLE DATABASE SERVERS: {', '.join(available_servers)}

Create a comprehensive JSON test suite following this exact schema:

{{
  "test_suite_name": "Descriptive Test Suite Name",
  "test_suite_description": "Detailed description of what this test suite covers",
  "category": "appropriate_category_from_hints",
  "priority": "critical|high|medium|low",
  "test_scenarios": [
    {{
      "test_name": "unique_descriptive_name",
      "description": "What this specific test validates",
      "command": "exact command to execute",
      "expected_output_contains": ["expected_text_1", "expected_text_2"],
      "expected_exit_code": 0,
      "timeout": 15,
      "setup_commands": ["optional setup command"],
      "cleanup_commands": ["optional cleanup command"]
    }}
  ]
}}

REQUIREMENTS:
1. Generate 10-20 test scenarios including:
   - Basic functionality test
   - Help command test (--help)
   - Error handling tests (invalid args, missing params)
   - Edge cases and boundary conditions
   - Integration tests with existing servers when relevant
   - Negative test cases
   - Performance/timeout scenarios

2. Use realistic expectations:
   - Timeouts: 10-30 seconds based on operation complexity
   - Exit codes: 0 for success, 1 for expected errors, 2 for argument errors
   - Output validation should be specific but not overly restrictive

3. Leverage existing database servers when appropriate:
   - Use "Ref", "filesystem", "aws-diagram" for integration tests
   - Include setup/cleanup only when necessary
   - Prefer database servers over creating temporary ones

4. Test naming convention:
   - Use descriptive, unique names
   - Follow pattern: feature_action_condition (e.g., "suite_create_with_invalid_name")
   - Use underscores, not hyphens

5. Consider the command's purpose and generate relevant scenarios:
   - If it's a management command, test CRUD operations
   - If it's a query command, test filtering and output formats
   - If it's an admin command, test permission scenarios
   - If it integrates with external services, test connection scenarios

6. Include realistic error scenarios:
   - Missing required arguments
   - Invalid argument values
   - Resource not found errors
   - Permission issues
   - Network/service unavailable

Generate the complete, valid JSON test suite now:
"""
        return prompt
    
    def _parse_ai_response(self, response: str, command: str) -> Dict[str, Any]:
        """Parse and validate AI response."""
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in AI response")
            
            json_str = response[json_start:json_end]
            test_data = json.loads(json_str)
            
            # Validate structure
            required_fields = ['test_suite_name', 'test_suite_description', 'category', 'priority', 'test_scenarios']
            for field in required_fields:
                if field not in test_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate scenarios
            scenarios = test_data.get('test_scenarios', [])
            if not scenarios:
                raise ValueError("No test scenarios generated")
            
            for scenario in scenarios:
                required_scenario_fields = ['test_name', 'description', 'command', 'expected_exit_code', 'timeout']
                for field in required_scenario_fields:
                    if field not in scenario:
                        raise ValueError(f"Scenario missing field: {field}")
            
            logger.info(f"Successfully parsed AI response: {len(scenarios)} scenarios")
            return test_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI response: {e}")
            raise ValueError(f"Invalid JSON in AI response: {e}")
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise
    
    async def enhance_existing_tests(self, test_file_path: Path) -> Dict[str, Any]:
        """Enhance existing test file with AI-generated additional scenarios."""
        if not self.ai_system:
            raise RuntimeError("AI system not available")
        
        # Load existing test file
        with open(test_file_path, 'r') as f:
            existing_tests = json.load(f)
        
        # Analyze gaps in coverage
        coverage_analysis = self._analyze_test_coverage(existing_tests)
        
        # Generate enhancement prompt
        enhancement_prompt = self._create_enhancement_prompt(existing_tests, coverage_analysis)
        
        # Get AI suggestions
        try:
            response = await self.ai_system.analyze_and_generate(enhancement_prompt)
            enhancements = self._parse_enhancement_response(response)
            
            # Merge with existing tests
            enhanced_tests = self._merge_test_enhancements(existing_tests, enhancements)
            
            return enhanced_tests
            
        except Exception as e:
            logger.error(f"Test enhancement failed: {e}")
            raise
    
    def _analyze_test_coverage(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test coverage to identify gaps."""
        scenarios = test_data.get('test_scenarios', [])
        
        coverage = {
            "has_help_test": any('help' in s.get('test_name', '') for s in scenarios),
            "has_error_handling": any(s.get('expected_exit_code', 0) != 0 for s in scenarios),
            "has_edge_cases": any('edge' in s.get('description', '').lower() for s in scenarios),
            "has_integration_tests": any('setup_commands' in s for s in scenarios),
            "scenario_count": len(scenarios),
            "timeout_range": {
                "min": min((s.get('timeout', 15) for s in scenarios), default=15),
                "max": max((s.get('timeout', 15) for s in scenarios), default=15)
            }
        }
        
        # Identify gaps
        gaps = []
        if not coverage["has_help_test"]:
            gaps.append("help_command_test")
        if not coverage["has_error_handling"]:
            gaps.append("error_handling_tests")
        if coverage["scenario_count"] < 8:
            gaps.append("insufficient_coverage")
        if not coverage["has_edge_cases"]:
            gaps.append("edge_case_tests")
        
        coverage["gaps"] = gaps
        return coverage
    
    def _create_enhancement_prompt(self, existing_tests: Dict[str, Any], coverage: Dict[str, Any]) -> str:
        """Create prompt for enhancing existing tests."""
        gaps = coverage.get('gaps', [])
        scenarios = existing_tests.get('test_scenarios', [])
        
        prompt = f"""
Enhance the following existing test suite by adding missing test scenarios.

EXISTING TEST SUITE:
{json.dumps(existing_tests, indent=2)}

COVERAGE ANALYSIS:
- Current scenarios: {len(scenarios)}
- Identified gaps: {', '.join(gaps)}
- Has help test: {coverage.get('has_help_test', False)}
- Has error handling: {coverage.get('has_error_handling', False)}
- Has edge cases: {coverage.get('has_edge_cases', False)}

ENHANCEMENT REQUIREMENTS:
1. Add 3-8 additional test scenarios to fill gaps
2. Focus on missing coverage areas: {', '.join(gaps)}
3. Ensure new scenarios are unique and don't duplicate existing ones
4. Follow the same schema as existing scenarios
5. Use realistic expectations and timeouts

Return ONLY the additional scenarios in this format:
{{
  "additional_scenarios": [
    {{
      "test_name": "new_scenario_name",
      "description": "What this new test validates",
      "command": "command to execute",
      "expected_output_contains": ["expected_output"],
      "expected_exit_code": 0,
      "timeout": 15
    }}
  ]
}}
"""
        return prompt
    
    def _parse_enhancement_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI enhancement response."""
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in enhancement response")
            
            json_str = response[json_start:json_end]
            enhancement_data = json.loads(json_str)
            
            return enhancement_data.get('additional_scenarios', [])
            
        except Exception as e:
            logger.error(f"Failed to parse enhancement response: {e}")
            return []
    
    def _merge_test_enhancements(self, existing_tests: Dict[str, Any], enhancements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge enhancements with existing tests."""
        enhanced_tests = existing_tests.copy()
        
        # Add new scenarios
        existing_scenarios = enhanced_tests.get('test_scenarios', [])
        existing_names = {s.get('test_name') for s in existing_scenarios}
        
        # Filter out duplicates
        new_scenarios = []
        for enhancement in enhancements:
            if enhancement.get('test_name') not in existing_names:
                new_scenarios.append(enhancement)
        
        enhanced_tests['test_scenarios'] = existing_scenarios + new_scenarios
        
        # Update description to reflect enhancement
        original_desc = enhanced_tests.get('test_suite_description', '')
        enhanced_tests['test_suite_description'] = f"{original_desc} (Enhanced with AI-generated scenarios)"
        
        return enhanced_tests


# Integration with auto test generator
async def ai_generate_tests_advanced(command: str, description: str = "") -> Dict[str, Any]:
    """Advanced AI test generation function for integration."""
    generator = AITestScenarioGenerator()
    return await generator.generate_comprehensive_tests(command, description)


async def ai_enhance_tests(test_file_path: Path) -> Dict[str, Any]:
    """AI test enhancement function for integration."""
    generator = AITestScenarioGenerator()
    return await generator.enhance_existing_tests(test_file_path)