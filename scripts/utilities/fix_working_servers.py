#!/usr/bin/env python3
"""
Replace broken MCP servers with actually working ones.
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

def update_with_working_servers():
    """Replace broken servers with known working ones."""
    
    db_path = Path(__file__).parent / "tests" / "fixtures" / "test_suites.db"
    
    # Working server configurations
    working_servers = {
        "dd-SQLite": {
            "type": "docker-desktop",
            "command": "docker-desktop://SQLite",
            "config_overrides": '{"enabled": true}'
        },
        "dd-Ref": {
            "type": "docker-desktop", 
            "command": "docker-desktop://Ref",
            "config_overrides": '{"enabled": true}'
        },
        "@anthropic/mcp-server-sqlite": {
            "type": "npm",
            "command": "npx -y @anthropic/mcp-server-sqlite",
            "config_overrides": '{"args": ["--db-path", "/tmp/test.db"]}'
        }
    }
    
    with sqlite3.connect(db_path) as conn:
        # Clear all existing suite memberships
        print("🗑️  Clearing existing suite memberships...")
        conn.execute("DELETE FROM suite_memberships")
        
        # Update basic-commands-test suite with working servers
        basic_commands_servers = [
            {"name": "dd-SQLite", "role": "primary", "priority": 95},
            {"name": "dd-Ref", "role": "secondary", "priority": 80}
        ]
        
        print("✅ Adding working servers to basic-commands-test suite:")
        for server in basic_commands_servers:
            server_info = working_servers[server["name"]]
            conn.execute("""
                INSERT INTO suite_memberships 
                (suite_id, server_name, role, priority, server_type, server_command, config_overrides, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'basic-commands-test',
                server["name"],
                server["role"],
                server["priority"],
                server_info["type"],
                server_info["command"],
                server_info["config_overrides"],
                datetime.now().isoformat()
            ))
            print(f"   ➕ {server['name']} ({server_info['type']}, {server['role']})")
        
        # Update server-management-test suite
        server_mgmt_servers = [
            {"name": "dd-SQLite", "role": "primary", "priority": 90},
            {"name": "dd-Ref", "role": "secondary", "priority": 85}
        ]
        
        print("\n✅ Adding working servers to server-management-test suite:")
        for server in server_mgmt_servers:
            server_info = working_servers[server["name"]]
            conn.execute("""
                INSERT INTO suite_memberships 
                (suite_id, server_name, role, priority, server_type, server_command, config_overrides, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'server-management-test',
                server["name"],
                server["role"],
                server["priority"],
                server_info["type"],
                server_info["command"],
                server_info["config_overrides"],
                datetime.now().isoformat()
            ))
            print(f"   ➕ {server['name']} ({server_info['type']}, {server['role']})")
        
        # Update workflows-test suite
        workflow_servers = [
            {"name": "dd-SQLite", "role": "primary", "priority": 95},
            {"name": "dd-Ref", "role": "secondary", "priority": 80}
        ]
        
        print("\n✅ Adding working servers to workflows-test suite:")
        for server in workflow_servers:
            server_info = working_servers[server["name"]]
            conn.execute("""
                INSERT INTO suite_memberships 
                (suite_id, server_name, role, priority, server_type, server_command, config_overrides, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'workflows-test',
                server["name"],
                server["role"],
                server["priority"],
                server_info["type"],
                server_info["command"],
                server_info["config_overrides"],
                datetime.now().isoformat()
            ))
            print(f"   ➕ {server['name']} ({server_info['type']}, {server['role']})")
        
        conn.commit()
        
        # Verify the changes
        print("\n📋 Verification - Working servers in suites:")
        cursor = conn.execute("""
            SELECT s.name, sm.server_name, sm.server_type, sm.role, sm.priority
            FROM mcp_suites s
            JOIN suite_memberships sm ON s.id = sm.suite_id
            ORDER BY s.id, sm.priority DESC
        """)
        
        current_suite = None
        for row in cursor.fetchall():
            suite_name, server_name, server_type, role, priority = row
            if suite_name != current_suite:
                print(f"\n🎯 {suite_name}:")
                current_suite = suite_name
            
            type_emoji = {"docker-desktop": "🐳", "npm": "📦"}.get(server_type, "❓")
            role_emoji = {"primary": "🎯", "secondary": "⚡", "optional": "🔧"}.get(role, "📦")
            print(f"   {type_emoji}{role_emoji} {server_name} ({role}, {priority})")

if __name__ == "__main__":
    update_with_working_servers()