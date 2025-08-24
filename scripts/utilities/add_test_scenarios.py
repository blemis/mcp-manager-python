#!/usr/bin/env python3
"""
Quick script to add more test scenarios to the database for demonstration.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.mcp_manager.core.test_management.database import TestManagementDB
from src.mcp_manager.core.test_management.models import TestScenario

def add_scenarios():
    """Add a few more test scenarios to the database."""
    
    # Initialize database
    test_db_path = Path(__file__).parent / "tests" / "fixtures" / "test_suites.db"
    db = TestManagementDB(test_db_path)
    
    # Check if basic-commands category has scenarios
    existing = db.list_test_scenarios(category="basic-commands")
    print(f"Found {len(existing)} existing scenarios for basic-commands")
    
    # Get suite ID for basic-commands
    suite_id = db.get_suite_for_category("basic-commands")
    if not suite_id:
        print("No suite found for basic-commands category")
        return
    
    scenarios_to_add = [
        {
            "id": "basic_commands_status_test",
            "name": "Basic Commands Status Test", 
            "description": "Test the status command for basic CLI functionality",
            "command": "status",
            "test_description": "Test status command execution"
        },
        {
            "id": "basic_commands_help_test",
            "name": "Basic Commands Help Test",
            "description": "Test the help command for basic CLI functionality", 
            "command": "help",
            "test_description": "Test help command execution"
        },
        {
            "id": "basic_commands_version_test",
            "name": "Basic Commands Version Test",
            "description": "Test the version display for basic CLI functionality",
            "command": "list --help",
            "test_description": "Test command help functionality"
        }
    ]
    
    for scenario_info in scenarios_to_add:
        # Check if scenario already exists
        existing_scenario = db.get_test_scenario(scenario_info["id"])
        if existing_scenario:
            print(f"Scenario {scenario_info['id']} already exists, skipping")
            continue
            
        # Create scenario JSON
        scenario_json = {
            "schema_version": "1.0",
            "scenario": {
                "id": scenario_info["id"],
                "name": scenario_info["name"],
                "description": scenario_info["description"],
                "created_by": "system",
                "category": "basic-commands",
                "priority": "medium",
                "confidence_score": 0.8,
                "tags": ["system-generated", "basic-commands"]
            },
            "mcp_requirements": {
                "required_servers": [],
                "optional_servers": [],
                "scope": "user"
            },
            "test_steps": [
                {
                    "step_id": 1,
                    "action": "cli_command",
                    "command": scenario_info["command"],
                    "expect": "success",
                    "timeout": 15,
                    "description": scenario_info["test_description"]
                }
            ],
            "validation": {
                "success_criteria": [
                    {
                        "type": "all_steps_pass",
                        "description": "All test steps must complete successfully"
                    }
                ],
                "cleanup_strategy": "minimal",
                "cleanup_required": False,
                "cleanup_steps": []
            },
            "metadata": {
                "created_date": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "execution_count": 0,
                "success_rate": 0.0,
                "average_duration": 0.0
            }
        }
        
        # Create TestScenario object
        test_scenario = TestScenario(
            id=scenario_info["id"],
            name=scenario_info["name"],
            description=scenario_info["description"],
            category="basic-commands",
            priority="medium",
            created_by="system",
            scenario_json=json.dumps(scenario_json, indent=2),
            tags=["system-generated", "basic-commands"],
            suite_id=suite_id,
            confidence_score=0.8
        )
        
        # Save to database
        if db.create_test_scenario(test_scenario):
            print(f"✅ Created scenario: {scenario_info['name']}")
        else:
            print(f"❌ Failed to create scenario: {scenario_info['name']}")
    
    # List all scenarios
    all_scenarios = db.list_test_scenarios(category="basic-commands")
    print(f"\n📋 Total scenarios in basic-commands category: {len(all_scenarios)}")
    for scenario in all_scenarios:
        print(f"   - {scenario.name}")

if __name__ == "__main__":
    add_scenarios()