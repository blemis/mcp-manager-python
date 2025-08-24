#!/usr/bin/env python3
"""
Fix real MCP server suites to include proper installation commands.
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

def fix_server_commands():
    """Update suite memberships with proper server installation commands."""
    
    db_path = Path(__file__).parent / "tests" / "fixtures" / "test_suites.db"
    
    # Server installation details
    server_commands = {
        "@modelcontextprotocol/server-filesystem": {
            "type": "npm",
            "command": "npx -y @modelcontextprotocol/server-filesystem",
            "config_overrides": '{"args": ["--directory", "/tmp/test_fs"]}'
        },
        "dd-SQLite": {
            "type": "docker-desktop", 
            "command": "docker-desktop://SQLite",
            "config_overrides": '{"enabled": true}'
        },
        "@modelcontextprotocol/server-sqlite": {
            "type": "npm",
            "command": "npx -y @modelcontextprotocol/server-sqlite",
            "config_overrides": '{"args": ["--db-path", "/tmp/test.db"]}'
        },
        "@modelcontextprotocol/server-brave-search": {
            "type": "npm", 
            "command": "npx -y @modelcontextprotocol/server-brave-search",
            "config_overrides": '{"env": {"BRAVE_API_KEY": "test-key"}}'
        },
        "dd-Ref": {
            "type": "docker-desktop",
            "command": "docker-desktop://Ref", 
            "config_overrides": '{"enabled": true}'
        },
        "@modelcontextprotocol/server-playwright": {
            "type": "npm",
            "command": "npx -y @modelcontextprotocol/server-playwright",
            "config_overrides": '{"args": ["--headless"]}'
        }
    }
    
    with sqlite3.connect(db_path) as conn:
        # First, check if we need to add server_type and server_command columns
        cursor = conn.execute("PRAGMA table_info(suite_memberships)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'server_type' not in columns:
            print("➕ Adding server_type column to suite_memberships...")
            conn.execute("ALTER TABLE suite_memberships ADD COLUMN server_type TEXT DEFAULT 'custom'")
        
        if 'server_command' not in columns:
            print("➕ Adding server_command column to suite_memberships...")
            conn.execute("ALTER TABLE suite_memberships ADD COLUMN server_command TEXT DEFAULT ''")
        
        print("🔧 Updating server installation commands...")
        
        for server_name, details in server_commands.items():
            try:
                conn.execute("""
                    UPDATE suite_memberships 
                    SET server_type = ?, 
                        server_command = ?,
                        config_overrides = ?
                    WHERE server_name = ?
                """, (
                    details["type"],
                    details["command"], 
                    details["config_overrides"],
                    server_name
                ))
                
                rows_updated = conn.total_changes
                if rows_updated > 0:
                    print(f"   ✅ Updated {server_name} ({details['type']})")
                else:
                    print(f"   ⚠️ No rows updated for {server_name}")
                    
            except Exception as e:
                print(f"   ❌ Failed to update {server_name}: {e}")
        
        conn.commit()
        
        # Verify the updates
        print("\n📋 Verification - Server installation commands:")
        cursor = conn.execute("""
            SELECT DISTINCT sm.server_name, sm.server_type, sm.server_command, sm.config_overrides
            FROM suite_memberships sm
            ORDER BY sm.server_name
        """)
        
        for row in cursor.fetchall():
            server_name, server_type, server_command, config_overrides = row
            type_emoji = {"npm": "📦", "docker-desktop": "🐳", "custom": "⚙️"}.get(server_type, "❓")
            print(f"{type_emoji} {server_name}")
            print(f"   Type: {server_type}")
            print(f"   Command: {server_command[:60]}{'...' if len(server_command) > 60 else ''}")
            if config_overrides != '{}':
                print(f"   Config: {config_overrides[:40]}{'...' if len(config_overrides) > 40 else ''}")
            print()

if __name__ == "__main__":
    fix_server_commands()