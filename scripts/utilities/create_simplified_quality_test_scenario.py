#!/usr/bin/env python3
"""
Create quality-integrated test scenarios using existing discovery system.

This script creates test scenarios that:
1. Use the discovery system to find real MCP servers
2. Validate connectivity using `claude mcp list` 
3. Create database scenarios without complex quality tracking
4. Focus on real server testing with docker-gateway pattern
"""

import asyncio
import json
import sqlite3
from pathlib import Path

async def create_simplified_quality_scenarios():
    """Create simplified test scenarios using discovery system."""
    
    print("🚀 Creating simplified quality-integrated test scenarios...")
    
    # Use the discovery system to get real MCP servers
    from mcp_manager.core.discovery import ServerDiscovery
    from mcp_manager.core.models import ServerType
    
    discovery = ServerDiscovery()
    
    # Get real Docker Desktop servers
    print("📦 Discovering Docker Desktop servers...")
    dd_servers = await discovery.discover_servers(
        server_type=ServerType.DOCKER_DESKTOP,
        limit=10
    )
    
    # Get real NPM servers  
    print("📦 Discovering NPM servers...")
    npm_servers = await discovery.discover_servers(
        server_type=ServerType.NPM,
        limit=5
    )
    
    print(f"Found {len(dd_servers)} Docker Desktop servers and {len(npm_servers)} NPM servers")
    
    # Initialize database
    db_path = Path("data/mcp_manager.db")
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Initialize schema if needed
    from mcp_manager.core.database.schema import MCPDatabaseSchema
    schema = MCPDatabaseSchema()
    await schema.initialize_database()
    
    # Create test scenarios for discovered servers
    scenarios = []
    
    # Docker Desktop scenarios using docker-gateway pattern
    for server in dd_servers[:3]:  # Limit to 3 servers
        # Create connectivity test scenario
        scenario = {
            "name": f"test_docker_desktop_{server.name}_connectivity",
            "description": f"Test connectivity to Docker Desktop server: {server.name}",
            "server_name": f"docker-gateway",  # Use docker-gateway pattern
            "server_command": "docker",
            "server_args": ["mcp", "gateway", "run"],
            "test_type": "connectivity",
            "expected_outcome": "success",
            "timeout": 30,
            "validation": {
                "method": "claude_mcp_list",
                "expected_status": "connected"
            },
            "cleanup": {
                "strategy": "none",  # Docker Desktop servers are persistent
                "commands": []
            }
        }
        scenarios.append(scenario)
    
    # NPM server scenarios
    for server in npm_servers[:2]:  # Limit to 2 servers
        scenario = {
            "name": f"test_npm_{server.name}_connectivity", 
            "description": f"Test connectivity to NPM server: {server.name}",
            "server_name": server.name,
            "server_command": "npx",
            "server_args": ["-y", server.package] if server.package else ["-y", server.name],
            "test_type": "connectivity",
            "expected_outcome": "success", 
            "timeout": 45,
            "validation": {
                "method": "claude_mcp_list",
                "expected_status": "connected"
            },
            "cleanup": {
                "strategy": "remove_after_test",
                "commands": ["claude", "mcp", "remove", server.name]
            }
        }
        scenarios.append(scenario)
    
    # Store scenarios in database
    print("💾 Storing scenarios in database...")
    
    # Create suite if it doesn't exist
    suite_name = "quality-integrated-basic"
    
    # Insert scenarios into database
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        
        # Check if suite exists
        cursor = await db.execute(
            "SELECT id FROM mcp_suites WHERE name = ?",
            (suite_name,)
        )
        suite_row = await cursor.fetchone()
        
        if not suite_row:
            # Create suite
            await db.execute(
                """INSERT INTO mcp_suites (name, description, category, is_active)
                   VALUES (?, ?, ?, ?)""",
                (suite_name, "Quality-integrated basic connectivity tests", "core", True)
            )
            await db.commit()
            
            cursor = await db.execute(
                "SELECT id FROM mcp_suites WHERE name = ?",
                (suite_name,)
            )
            suite_row = await cursor.fetchone()
        
        suite_id = suite_row[0]
        
        # Insert scenarios
        for scenario in scenarios:
            await db.execute(
                """INSERT OR REPLACE INTO test_scenarios 
                   (name, description, scenario_data, suite_id, category, is_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    scenario["name"],
                    scenario["description"],
                    json.dumps(scenario),
                    suite_id,
                    "core",
                    True
                )
            )
        
        await db.commit()
    
    print(f"✅ Created {len(scenarios)} quality-integrated test scenarios")
    
    # Test the scenario execution
    print("🧪 Testing scenario execution...")
    
    try:
        from tests.engine.json_test_runner import JSONTestRunner
        
        runner = JSONTestRunner()
        results = await runner.run_scenarios(category="core", suite_filter=suite_name)
        
        print(f"📊 Test Results:")
        print(f"  Total scenarios: {len(results)}")
        print(f"  Scenarios found: {[r.get('name', 'unnamed') for r in results]}")
        
    except Exception as e:
        print(f"⚠️  Test execution error: {e}")
        print("This is expected if dependencies are missing")
    
    print("🎉 Quality-integrated test scenario creation completed!")

if __name__ == "__main__":
    import aiosqlite
    asyncio.run(create_simplified_quality_scenarios())