#!/usr/bin/env python3
"""
Create Quality-Integrated Test Scenario

Creates a real test scenario that uses quality scores and IDE connectivity validation.
This replaces the hardcoded fallback scenarios with real quality-aware testing.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent))

async def create_quality_test_scenario():
    """Create test scenario that uses quality integration and real connectivity validation."""
    print("🎯 Creating quality-integrated test scenario...")
    print("=" * 60)
    
    try:
        # Import after path setup
        from src.mcp_manager.core.validation.quality_integration import TestScenarioQualityFilter
        from src.mcp_manager.core.database.connection import get_database_connection
        from src.mcp_manager.core.validation.ide_connectivity import IDEType
        
        # Set database path
        db_path = Path("data/mcp_manager.db")
        if not db_path.exists():
            print(f"❌ Database not found at {db_path} - run quick_init.py first")
            return False
        
        # Reset connection to use correct path
        import src.mcp_manager.core.database.connection as db_conn_module
        db_conn_module._db_connection = None
        db_conn = get_database_connection(db_path)
        
        # Get quality-filtered servers for testing
        print("🔍 Finding high-quality servers for testing...")
        quality_filter = TestScenarioQualityFilter(IDEType.CLAUDE_CODE)
        
        # Get servers that meet quality requirements
        quality_servers = await quality_filter.get_servers_for_testing(
            category="connectivity-validation",
            max_servers=3,
            min_quality=40  # Minimum 40/100 quality score
        )
        
        if not quality_servers:
            print("⚠️ No high-quality servers found - cannot create test scenario")
            print("💡 Try running: mcp-manager quality rankings")
            return False
        
        print(f"✅ Found {len(quality_servers)} quality servers:")
        for server in quality_servers:
            print(f"   • {server.server_name}: {server.quality_score}/100 quality, {server.success_rate:.1%} success")
        
        # Create test scenario JSON that validates real connectivity
        scenario_json = {
            "schema_version": "1.0",
            "scenario": {
                "id": "quality_connectivity_validation",
                "name": "Quality-Integrated Connectivity Validation",
                "description": "Validates MCP server connectivity using quality scores and real IDE connectivity testing",
                "created_by": "quality_integration",
                "category": "connectivity-validation", 
                "priority": "high",
                "confidence_score": 0.9,
                "tags": ["quality-integrated", "connectivity", "real-validation"]
            },
            "mcp_requirements": {
                "required_servers": [
                    {
                        "name": server.server_name,
                        "min_quality_score": server.quality_score,
                        "expected_connectivity": True
                    } for server in quality_servers if server.recommended_for_testing
                ],
                "scope": "user",
                "quality_requirements": {
                    "min_quality_score": 40,
                    "min_success_rate": 0.6,
                    "require_recent_health_check": True
                }
            },
            "test_steps": [
                {
                    "step_id": 1,
                    "name": "Quality Score Validation",
                    "action": "validate_quality",
                    "description": "Verify servers meet minimum quality requirements",
                    "validation": {
                        "min_quality_score": 40,
                        "min_success_rate": 0.6
                    },
                    "timeout": 10
                },
                {
                    "step_id": 2, 
                    "name": "IDE Connectivity Test",
                    "action": "ide_connectivity",
                    "description": "Run claude mcp list to validate real connectivity",
                    "command": ["claude", "mcp", "list"],
                    "validation": {
                        "expect_connected": True,
                        "fail_on_connection_error": True,
                        "check_server_status": True
                    },
                    "timeout": 30
                },
                {
                    "step_id": 3,
                    "name": "Update Quality Metrics", 
                    "action": "update_quality",
                    "description": "Update quality scores based on connectivity test results",
                    "update_quality_database": True,
                    "timeout": 5
                }
            ],
            "validation": {
                "success_criteria": [
                    {
                        "type": "all_steps_pass",
                        "description": "All validation steps must pass"
                    },
                    {
                        "type": "connectivity_confirmed",
                        "description": "All required servers must show as connected in claude mcp list"
                    },
                    {
                        "type": "quality_maintained",
                        "description": "Server quality scores must remain above minimum threshold"
                    }
                ],
                "failure_conditions": [
                    {
                        "type": "connectivity_failed",
                        "description": "Any server shows ✗ Failed to connect in claude mcp list",
                        "action": "fail_immediately"
                    },
                    {
                        "type": "quality_degraded", 
                        "description": "Server quality drops below threshold during test",
                        "action": "update_and_continue"
                    }
                ],
                "cleanup_strategy": "preserve_on_success",
                "cleanup_required": False
            },
            "metadata": {
                "created_date": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "execution_count": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "quality_integrated": True,
                "ide_type": "claude-code",
                "min_quality_threshold": 40
            }
        }
        
        # Store scenario in database
        print("💾 Storing scenario in database...")
        async with db_conn.get_connection() as conn:
            await conn.execute("""
                INSERT INTO test_scenarios (
                    id, scenario_json, category, priority, created_by, created_at, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                scenario_json["scenario"]["id"],
                json.dumps(scenario_json, indent=2),
                scenario_json["scenario"]["category"], 
                scenario_json["scenario"]["priority"],
                scenario_json["scenario"]["created_by"],
                datetime.now().isoformat(),
                True
            ))
            
        print("✅ Quality-integrated test scenario created successfully!")
        print()
        print("📋 Scenario Details:")
        print(f"   ID: {scenario_json['scenario']['id']}")
        print(f"   Name: {scenario_json['scenario']['name']}")
        print(f"   Required Servers: {len(scenario_json['mcp_requirements']['required_servers'])}")
        print(f"   Quality Threshold: {scenario_json['mcp_requirements']['quality_requirements']['min_quality_score']}")
        print()
        print("🧪 Test with:")
        print("   ./test unit")
        print("   # Should now run real quality-integrated connectivity validation")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create quality test scenario: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(create_quality_test_scenario())
    sys.exit(0 if success else 1)