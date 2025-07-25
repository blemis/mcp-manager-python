#!/usr/bin/env python3
"""
Update test suites to use REAL MCP servers instead of fake ones.
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

def update_suite_with_real_servers():
    """Replace fake test servers with real MCP servers in the database."""
    
    db_path = Path(__file__).parent / "tests" / "fixtures" / "test_suites.db"
    
    with sqlite3.connect(db_path) as conn:
        # Remove fake test servers from basic-commands-test suite
        print("🗑️  Removing fake test servers...")
        conn.execute("DELETE FROM suite_memberships WHERE suite_id = 'basic-commands-test' AND server_name LIKE 'test-%'")
        
        # Add real MCP servers to basic-commands-test suite
        real_servers = [
            {
                "server_name": "@modelcontextprotocol/server-filesystem",
                "role": "primary",
                "priority": 95,
                "description": "NPM filesystem server for basic file operations"
            },
            {
                "server_name": "dd-SQLite", 
                "role": "secondary",
                "priority": 80,
                "description": "Docker Desktop SQLite server for database operations"
            },
            {
                "server_name": "@modelcontextprotocol/server-sqlite",
                "role": "optional", 
                "priority": 60,
                "description": "NPM SQLite server as alternative"
            }
        ]
        
        print("✅ Adding real MCP servers to basic-commands-test suite:")
        for server in real_servers:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO suite_memberships 
                    (suite_id, server_name, role, priority, config_overrides, added_at)
                    VALUES (?, ?, ?, ?, '{}', ?)
                """, (
                    'basic-commands-test',
                    server["server_name"],
                    server["role"], 
                    server["priority"],
                    datetime.now().isoformat()
                ))
                print(f"   ➕ {server['server_name']} ({server['role']}, priority {server['priority']})")
            except Exception as e:
                print(f"   ❌ Failed to add {server['server_name']}: {e}")
        
        # Create additional real test suites
        additional_suites = [
            {
                "id": "server-management-test",
                "name": "Server Management Test Suite", 
                "description": "Real MCP servers for testing server management functionality",
                "servers": [
                    {"name": "@modelcontextprotocol/server-brave-search", "role": "primary", "priority": 90},
                    {"name": "dd-Ref", "role": "secondary", "priority": 80},
                    {"name": "@modelcontextprotocol/server-playwright", "role": "optional", "priority": 70}
                ]
            },
            {
                "id": "workflows-test",
                "name": "Workflows Test Suite",
                "description": "Real MCP servers for testing workflow functionality", 
                "servers": [
                    {"name": "@modelcontextprotocol/server-filesystem", "role": "primary", "priority": 95},
                    {"name": "@modelcontextprotocol/server-sqlite", "role": "primary", "priority": 90},
                    {"name": "dd-SQLite", "role": "secondary", "priority": 75}
                ]
            }
        ]
        
        for suite in additional_suites:
            # Create suite if it doesn't exist
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO mcp_suites (id, name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    suite["id"],
                    suite["name"], 
                    suite["description"],
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                print(f"\n✅ Created/Updated suite: {suite['name']}")
                
                # Add servers to suite
                for server in suite["servers"]:
                    conn.execute("""
                        INSERT OR REPLACE INTO suite_memberships
                        (suite_id, server_name, role, priority, config_overrides, added_at)
                        VALUES (?, ?, ?, ?, '{}', ?)
                    """, (
                        suite["id"],
                        server["name"],
                        server["role"],
                        server["priority"], 
                        datetime.now().isoformat()
                    ))
                    print(f"   ➕ {server['name']} ({server['role']}, priority {server['priority']})")
                    
            except Exception as e:
                print(f"❌ Failed to create suite {suite['id']}: {e}")
        
        conn.commit()
        
        # Verify the changes
        print("\n📋 Verification - Current suites and their real servers:")
        cursor = conn.execute("""
            SELECT s.id, s.name, COUNT(sm.server_name) as server_count
            FROM mcp_suites s
            LEFT JOIN suite_memberships sm ON s.id = sm.suite_id  
            GROUP BY s.id, s.name
            ORDER BY s.id
        """)
        
        for row in cursor.fetchall():
            suite_id, suite_name, server_count = row
            print(f"\n🎯 {suite_name} ({suite_id}): {server_count} servers")
            
            # List servers in this suite
            server_cursor = conn.execute("""
                SELECT server_name, role, priority 
                FROM suite_memberships 
                WHERE suite_id = ? 
                ORDER BY priority DESC
            """, (suite_id,))
            
            for server_row in server_cursor.fetchall():
                server_name, role, priority = server_row
                role_emoji = {"primary": "🎯", "secondary": "⚡", "optional": "🔧"}.get(role, "📦")
                print(f"   {role_emoji} {server_name} ({role}, {priority})")

if __name__ == "__main__":
    update_suite_with_real_servers()