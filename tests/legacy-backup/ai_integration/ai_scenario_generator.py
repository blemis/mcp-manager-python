"""
AI Scenario Generator for MCP Manager Testing.

Integrates with AI services to generate test scenarios based on natural language
descriptions and existing system knowledge.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

from tests.ai_integration.schema_validator import TestScenarioValidator
from tests.engine.scenario_parser import ScenarioParser

logger = logging.getLogger(__name__)

class AIScenarioGenerator:
    """Generates test scenarios using AI recommendations."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize AI scenario generator."""
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "scenarios" / "ai_generated"
        
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.validator = TestScenarioValidator()
        self.parser = ScenarioParser()
        
        # Load prompt template
        template_path = Path(__file__).parent / "templates" / "scenario_generation_prompt.md"
        with open(template_path, 'r') as f:
            self.prompt_template = f.read()
    
    def generate_scenario_from_description(self, 
                                         description: str,
                                         category: Optional[str] = None,
                                         priority: Optional[str] = None,
                                         required_servers: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate a test scenario from natural language description.
        
        This is a simulated AI response - in practice, this would call
        an actual AI service like OpenAI, Claude, etc.
        
        Args:
            description: Natural language description of what to test
            category: Optional category override
            priority: Optional priority override  
            required_servers: Optional list of required MCP servers
            
        Returns:
            Generated scenario dictionary
        """
        logger.info(f"🤖 Generating scenario from: '{description}'")
        
        # Simulate AI processing
        scenario_id = self._generate_scenario_id(description)
        
        # Extract key concepts from description
        concepts = self._extract_concepts(description)
        
        # Determine category and priority
        inferred_category = category or self._infer_category(description, concepts)
        inferred_priority = priority or self._infer_priority(description, concepts)
        
        # Generate MCP server requirements
        mcp_requirements = self._generate_mcp_requirements(
            description, concepts, required_servers
        )
        
        # Generate test steps
        test_steps = self._generate_test_steps(description, concepts, mcp_requirements)
        
        # Create scenario
        scenario = {
            "schema_version": "1.0",
            "scenario": {
                "id": scenario_id,
                "name": self._generate_scenario_name(description),
                "description": f"AI-generated test scenario: {description}",
                "created_by": "ai",
                "category": inferred_category,
                "confidence_score": self._calculate_confidence_score(description, concepts),
                "ai_reasoning": self._generate_ai_reasoning(description, concepts, inferred_category),
                "tags": self._generate_tags(description, concepts),
                "priority": inferred_priority
            },
            "mcp_requirements": mcp_requirements,
            "test_steps": test_steps,
            "validation": self._generate_validation_criteria(description, test_steps),
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
    
    def _generate_scenario_id(self, description: str) -> str:
        """Generate unique scenario ID from description."""
        # Simple ID generation - extract key words
        import re
        words = re.findall(r'\b\w+\b', description.lower())
        key_words = [w for w in words if len(w) > 3 and w not in ['test', 'testing', 'with', 'that', 'this', 'should']]
        
        # Take first 4 key words
        id_parts = key_words[:4]
        if not id_parts:
            id_parts = ['ai', 'generated']
        
        base_id = '_'.join(id_parts)
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return f"ai_{base_id}_{timestamp}"
    
    def _extract_concepts(self, description: str) -> List[str]:
        """Extract key concepts from description."""
        concepts = []
        
        # MCP server concepts
        server_patterns = {
            'filesystem': ['file', 'directory', 'folder', 'path', 'filesystem'],
            'sqlite': ['database', 'sqlite', 'sql', 'query'],
            'docker': ['docker', 'container', 'image'],
            'playwright': ['browser', 'web', 'page', 'playwright'],
            'search': ['search', 'find', 'query', 'discover']
        }
        
        description_lower = description.lower()
        for server, patterns in server_patterns.items():
            if any(pattern in description_lower for pattern in patterns):
                concepts.append(f"server:{server}")
        
        # Action concepts  
        action_patterns = {
            'install': ['install', 'add', 'setup'],
            'remove': ['remove', 'delete', 'uninstall'],
            'list': ['list', 'show', 'display'],
            'configure': ['configure', 'config', 'setup'],
            'error': ['error', 'failure', 'exception', 'invalid']
        }
        
        for action, patterns in action_patterns.items():
            if any(pattern in description_lower for pattern in patterns):
                concepts.append(f"action:{action}")
        
        return concepts
    
    def _infer_category(self, description: str, concepts: List[str]) -> str:
        """Infer scenario category from description and concepts."""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['smoke', 'basic', 'critical', 'startup']):
            return "smoke"
        elif any(word in description_lower for word in ['workflow', 'complete', 'end-to-end', 'journey']):
            return "workflow"
        elif any(word in description_lower for word in ['performance', 'speed', 'load', 'stress']):
            return "performance"
        elif any(word in description_lower for word in ['error', 'failure', 'invalid', 'regression']):
            return "regression"
        elif any(word in description_lower for word in ['integration', 'multiple', 'combined']):
            return "integration"
        else:
            return "core"
    
    def _infer_priority(self, description: str, concepts: List[str]) -> str:
        """Infer scenario priority from description and concepts."""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['critical', 'essential', 'must', 'required']):
            return "critical"
        elif any(word in description_lower for word in ['important', 'high', 'priority', 'key']):
            return "high"
        elif any(word in description_lower for word in ['nice', 'optional', 'low', 'minor']):
            return "low"
        else:
            return "medium"
    
    def _generate_mcp_requirements(self, 
                                 description: str, 
                                 concepts: List[str],
                                 required_servers: Optional[List[str]]) -> Dict[str, Any]:
        """Generate MCP server requirements."""
        servers = []
        
        # Add explicitly required servers
        if required_servers:
            for server_name in required_servers:
                servers.append({
                    "name": server_name,
                    "type": self._infer_server_type(server_name),
                    "priority": "high"
                })
        
        # Add servers inferred from concepts
        server_concepts = [c for c in concepts if c.startswith('server:')]
        for concept in server_concepts:
            server_name = concept.split(':')[1]
            
            # Map to actual server names
            server_mapping = {
                'filesystem': 'filesystem-server',
                'sqlite': 'sqlite-server', 
                'docker': 'docker-server',
                'playwright': 'playwright-server'
            }
            
            actual_name = server_mapping.get(server_name, f"{server_name}-server")
            
            if not any(s['name'] == actual_name for s in servers):
                servers.append({
                    "name": actual_name,
                    "type": self._infer_server_type(actual_name),
                    "priority": "medium"
                })
        
        return {
            "required_servers": servers,
            "optional_servers": [],
            "scope": "user",
            "deduplication_key": f"ai_generated_{len(servers)}_servers",
            "resource_requirements": {
                "min_memory_mb": 64 + (len(servers) * 32),
                "max_execution_time_seconds": min(300, 60 + (len(servers) * 30)),
                "parallel_safe": len(servers) <= 2
            }
        }
    
    def _infer_server_type(self, server_name: str) -> str:
        """Infer server type from server name."""
        if 'docker' in server_name.lower():
            return "docker-desktop"
        elif any(name in server_name.lower() for name in ['filesystem', 'sqlite', 'playwright']):
            return "npm"
        else:
            return "custom"
    
    def _generate_test_steps(self, 
                           description: str, 
                           concepts: List[str],
                           mcp_requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate test steps for MCP Manager deployment and Claude Code integration testing."""
        steps = []
        step_id = 1
        
        # Setup step if servers required
        if mcp_requirements['required_servers']:
            steps.append({
                "step_id": step_id,
                "action": "setup",
                "parameters": {
                    "action_type": "deploy_real_mcps",
                    "servers_needed": len(mcp_requirements['required_servers']),
                    "backup_claude_config": True
                },
                "expect": "success",
                "timeout": 90,
                "setup_required": False,
                "cleanup_on_failure": True,
                "retry_count": 1,
                "description": "Deploy real MCP servers for management testing"
            })
            step_id += 1
            
            # Add Claude integration validation step
            steps.append({
                "step_id": step_id,
                "action": "validation",
                "parameters": {
                    "validate_type": "claude_integration_check",
                    "check_claude_startup": True,
                    "check_mcp_registration": True
                },
                "expect": "success",
                "timeout": 30,
                "description": "Verify MCPs integrate with Claude Code without breaking it"
            })
            step_id += 1
        
        # Generate steps based on action concepts
        action_concepts = [c for c in concepts if c.startswith('action:')]
        
        for concept in action_concepts:
            action = concept.split(':')[1]
            
            if action == 'install':
                steps.append({
                    "step_id": step_id,
                    "action": "cli_command",
                    "command": "install-package test-server",
                    "expect": "success",
                    "timeout": 60,
                    "description": "Test server installation functionality"
                })
            elif action == 'remove':
                steps.append({
                    "step_id": step_id,
                    "action": "cli_command", 
                    "command": "remove test-server",
                    "expect": "success",
                    "timeout": 30,
                    "description": "Test server removal functionality"
                })
            elif action == 'list':
                steps.append({
                    "step_id": step_id,
                    "action": "cli_command",
                    "command": "list --scope user",
                    "expect": "success", 
                    "timeout": 15,
                    "description": "Test server listing functionality"
                })
            elif action == 'error':
                steps.append({
                    "step_id": step_id,
                    "action": "cli_command",
                    "command": "invalid-command-test",
                    "expect": "failure",
                    "timeout": 15,
                    "description": "Test error handling with invalid command"
                })
            
            step_id += 1
        
        # Default step if no specific actions found
        if len(steps) <= 1:  # Only setup step or no steps
            steps.append({
                "step_id": step_id,
                "action": "cli_command",
                "command": "status",
                "expect": "success",
                "timeout": 15,
                "description": "Basic functionality test based on description"
            })
        
        return steps
    
    def _calculate_confidence_score(self, description: str, concepts: List[str]) -> float:
        """Calculate AI confidence score for the generated scenario."""
        base_score = 0.7  # Base confidence
        
        # Increase confidence based on specific concepts
        if len(concepts) >= 3:
            base_score += 0.1
        
        # Increase confidence for specific patterns
        if any(word in description.lower() for word in ['test', 'verify', 'check', 'ensure']):
            base_score += 0.1
        
        # Decrease confidence for vague descriptions
        if len(description.split()) < 5:
            base_score -= 0.1
        
        return min(0.95, max(0.5, base_score))
    
    def _generate_ai_reasoning(self, description: str, concepts: List[str], category: str) -> str:
        """Generate AI reasoning for the scenario."""
        reasoning_parts = [
            f"Generated scenario for: '{description}'",
            f"Identified {len(concepts)} key concepts: {', '.join(concepts[:3])}",
            f"Categorized as '{category}' based on content analysis"
        ]
        
        if any(c.startswith('server:') for c in concepts):
            server_concepts = [c.split(':')[1] for c in concepts if c.startswith('server:')]
            reasoning_parts.append(f"Requires {', '.join(server_concepts)} MCP servers")
        
        return '. '.join(reasoning_parts) + '.'
    
    def _generate_tags(self, description: str, concepts: List[str]) -> List[str]:
        """Generate tags for the scenario."""
        tags = ['ai-generated']
        
        # Add concept-based tags
        for concept in concepts:
            if concept.startswith('server:'):
                tags.append(concept.split(':')[1])
            elif concept.startswith('action:'):
                tags.append(concept.split(':')[1])
        
        # Add description-based tags
        description_lower = description.lower()
        tag_patterns = {
            'cli': ['command', 'cli'],
            'integration': ['integration', 'multiple'],
            'workflow': ['workflow', 'process'],
            'error-handling': ['error', 'failure', 'invalid']
        }
        
        for tag, patterns in tag_patterns.items():
            if any(pattern in description_lower for pattern in patterns):
                tags.append(tag)
        
        return list(set(tags))  # Remove duplicates
    	
    def _generate_scenario_name(self, description: str) -> str:
        """Generate human-readable scenario name."""
        # Capitalize first letter and ensure proper sentence structure
        name = description.strip()
        if not name.endswith('.'):
            name = name.rstrip('.!?') + ' Test'
        
        return name.capitalize()
    
    def _generate_validation_criteria(self, description: str, test_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate validation criteria for the scenario with intelligent cleanup strategies."""
        
        # Determine appropriate cleanup strategy based on test description
        cleanup_strategy = self._determine_cleanup_strategy(description)
        cleanup_timing = self._determine_cleanup_timing(description)
        preserve_state = self._determine_preserve_state(description)
        cleanup_steps = self._generate_cleanup_steps(cleanup_strategy, description)
        
        return {
            "success_criteria": [
                {
                    "type": "all_steps_pass",
                    "description": "All test steps must complete successfully"
                },
                {
                    "type": "specific_output",
                    "description": "Commands produce expected output",
                    "value": "success"
                }
            ],
            "failure_conditions": [
                {
                    "type": "timeout",
                    "description": "Test execution exceeds maximum allowed time",
                    "value": str(sum(step.get('timeout', 30) for step in test_steps))
                },
                {
                    "type": "error_output",
                    "description": "Unexpected error messages in output",
                    "value": "error"
                }
            ],
            "cleanup_strategy": cleanup_strategy,
            "cleanup_timing": cleanup_timing,
            "preserve_state": preserve_state,
            "cleanup_required": cleanup_strategy != "none",
            "cleanup_steps": cleanup_steps
        }
    
    def _determine_cleanup_strategy(self, description: str) -> str:
        """Determine appropriate cleanup strategy based on test description."""
        desc_lower = description.lower()
        
        # No cleanup for read-only operations
        if any(word in desc_lower for word in ['list', 'show', 'display', 'view', 'query', 'status']):
            return 'none'
        
        # Preserve suite servers for management operations
        if any(word in desc_lower for word in ['manage', 'configure', 'update', 'enable', 'disable']):
            return 'suite_preserve'
        
        # Full cleanup for operations that reset/initialize system
        if any(word in desc_lower for word in ['reset', 'initialize', 'setup', 'bulk', 'install multiple']):
            return 'full'
        
        # Custom cleanup for complex operations
        if any(word in desc_lower for word in ['complex', 'workflow', 'end-to-end', 'integration']):
            return 'custom'
        
        # Default to minimal cleanup for simple operations
        return 'minimal'
    
    def _determine_cleanup_timing(self, description: str) -> str:
        """Determine when cleanup should occur."""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['step by step', 'incremental', 'progressive']):
            return 'after_each_step'
        
        if any(word in desc_lower for word in ['error handling', 'failure', 'exception']):
            return 'on_failure_only'
        
        return 'after_test'
    
    def _determine_preserve_state(self, description: str) -> List[str]:
        """Determine what state to preserve during cleanup."""
        preserve = []
        desc_lower = description.lower()
        
        # Always preserve suite servers unless explicitly testing server installation
        if not any(word in desc_lower for word in ['install server', 'add server', 'remove server', 'delete server']):
            preserve.append('suite_servers')
        
        # Preserve configs for non-configuration tests
        if not any(word in desc_lower for word in ['config', 'configure', 'settings', 'setup']):
            preserve.extend(['user_config', 'project_config'])
        
        # Preserve logs unless testing logging functionality
        if 'log' not in desc_lower:
            preserve.append('logs')
        
        # Preserve cache unless testing cache operations
        if 'cache' not in desc_lower:
            preserve.append('cache')
        
        return preserve
    
    def _generate_cleanup_steps(self, strategy: str, description: str) -> List[Dict[str, Any]]:
        """Generate specific cleanup steps based on strategy and description."""
        steps = []
        desc_lower = description.lower()
        
        if strategy == 'suite_preserve':
            steps.append({
                "action": "preserve_suite",
                "condition": "always",
                "ignore_errors": True
            })
            steps.append({
                "action": "remove_test_servers",
                "target": "test_only",
                "server_pattern": "test-*",
                "condition": "always",
                "ignore_errors": True
            })
        
        elif strategy == 'full':
            steps.append({
                "action": "remove_servers",
                "target": "all",
                "condition": "on_success",
                "ignore_errors": False
            })
            steps.append({
                "action": "reset_config",
                "condition": "always",
                "ignore_errors": True
            })
        
        elif strategy == 'custom':
            # Intelligent custom cleanup based on description
            if 'server' in desc_lower:
                steps.append({
                    "action": "remove_test_servers",
                    "target": "specific",
                    "server_pattern": "tmp-*",
                    "condition": "always",
                    "ignore_errors": True
                })
            
            if 'config' in desc_lower:
                steps.append({
                    "action": "reset_config",
                    "condition": "on_success",
                    "ignore_errors": True
                })
        
        elif strategy == 'minimal':
            steps.append({
                "action": "remove_test_servers",
                "target": "test_only",
                "server_pattern": "tmp-*",
                "condition": "always",
                "ignore_errors": True
            })
        
        return steps
    
    async def generate_and_save_scenario(self, 
                                       description: str,
                                       **kwargs) -> Tuple[bool, str, Optional[Path]]:
        """
        Generate and save a scenario from description.
        
        Returns:
            Tuple of (success, message, file_path)
        """
        try:
            # Generate scenario
            scenario = self.generate_scenario_from_description(description, **kwargs)
            
            # Validate scenario
            is_valid, errors = self.validator.validate_scenario(scenario)
            if not is_valid:
                error_msg = f"Generated scenario failed validation: {errors}"
                logger.error(error_msg)
                return False, error_msg, None
            
            # Save scenario
            scenario_id = scenario['scenario']['id']
            category = scenario['scenario']['category']
            
            # Create category directory
            category_dir = self.output_dir / category
            category_dir.mkdir(exist_ok=True)
            
            # Save file
            file_path = category_dir / f"{scenario_id}.json"
            with open(file_path, 'w') as f:
                json.dump(scenario, f, indent=2)
            
            success_msg = f"Generated and saved scenario: {scenario['scenario']['name']}"
            logger.info(f"✅ {success_msg}")
            
            return True, success_msg, file_path
            
        except Exception as e:
            error_msg = f"Failed to generate scenario: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def generate_batch_scenarios(self, descriptions: List[str]) -> List[Tuple[str, bool, str]]:
        """
        Generate multiple scenarios from a list of descriptions.
        
        Returns:
            List of (description, success, message) tuples
        """
        results = []
        
        logger.info(f"🤖 Generating {len(descriptions)} scenarios in batch")
        
        for i, description in enumerate(descriptions, 1):
            logger.info(f"Processing {i}/{len(descriptions)}: {description[:50]}...")
            
            try:
                success, message, file_path = asyncio.run(
                    self.generate_and_save_scenario(description)
                )
                results.append((description, success, message))
                
            except Exception as e:
                error_msg = f"Failed to process description: {e}"
                results.append((description, False, error_msg))
        
        successful = sum(1 for _, success, _ in results if success)
        logger.info(f"🎯 Batch complete: {successful}/{len(descriptions)} scenarios generated")
        
        return results

# CLI interface for AI scenario generation
def main():
    """CLI interface for generating scenarios."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Test Scenario Generator")
    parser.add_argument("description", help="Description of what to test")
    parser.add_argument("--category", help="Override category")
    parser.add_argument("--priority", help="Override priority")
    parser.add_argument("--servers", nargs="+", help="Required MCP servers")
    parser.add_argument("--output-dir", help="Output directory for scenarios")
    
    args = parser.parse_args()
    
    # Initialize generator
    output_dir = Path(args.output_dir) if args.output_dir else None
    generator = AIScenarioGenerator(output_dir)
    
    # Generate scenario
    success, message, file_path = asyncio.run(
        generator.generate_and_save_scenario(
            args.description,
            category=args.category,
            priority=args.priority,
            required_servers=args.servers
        )
    )
    
    if success:
        print(f"✅ {message}")
        print(f"📄 Saved to: {file_path}")
    else:
        print(f"❌ {message}")
        exit(1)

if __name__ == "__main__":
    main()