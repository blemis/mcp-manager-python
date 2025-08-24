#!/usr/bin/env python3
"""
Quick Database Initialization - No hanging, no complex migration
Just creates the database with sample data and exits fast.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def create_database():
    """Create database with schema and sample data quickly."""
    db_path = Path("data/mcp_manager.db")
    db_path.parent.mkdir(exist_ok=True)
    
    # Remove existing database
    if db_path.exists():
        db_path.unlink()
    
    print("🚀 Quick Database Setup")
    print("=" * 30)
    
    # Create database with schema
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Create tables
    print("📋 Creating tables...")
    
    # Server registry
    conn.execute("""
        CREATE TABLE mcp_server_registry (
            server_name TEXT PRIMARY KEY,
            description TEXT,
            server_type TEXT,
            install_command TEXT,
            package_name TEXT,
            version TEXT,
            author TEXT,
            repository_url TEXT,
            documentation_url TEXT,
            tags TEXT,
            discovery_metadata TEXT,
            last_discovered TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    # Suites
    conn.execute("""
        CREATE TABLE mcp_suites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            purpose TEXT,
            config TEXT,
            created_at TEXT,
            updated_at TEXT,
            created_by TEXT
        )
    """)
    
    # Suite memberships
    conn.execute("""
        CREATE TABLE suite_memberships (
            suite_id TEXT,
            server_name TEXT,
            role TEXT DEFAULT 'member',
            priority INTEGER DEFAULT 50,
            suite_specific_config TEXT,
            notes TEXT,
            added_at TEXT,
            added_by TEXT,
            PRIMARY KEY (suite_id, server_name),
            FOREIGN KEY (suite_id) REFERENCES mcp_suites(id) ON DELETE CASCADE,
            FOREIGN KEY (server_name) REFERENCES mcp_server_registry(server_name)
        )
    """)
    
    # Other tables
    conn.execute("""
        CREATE TABLE test_scenarios (
            id TEXT PRIMARY KEY,
            suite_id TEXT,
            scenario_data TEXT,
            created_at TEXT,
            FOREIGN KEY (suite_id) REFERENCES mcp_suites(id)
        )
    """)
    
    conn.execute("""CREATE TABLE discovery_cache (
        cache_key TEXT PRIMARY KEY,
        server_type TEXT,
        raw_data TEXT,
        cached_at TEXT,
        expires_at TEXT
    )""")
    
    conn.execute("""CREATE TABLE suite_usage (
        id TEXT PRIMARY KEY,
        suite_id TEXT,
        used_at TEXT,
        usage_type TEXT,
        metadata TEXT,
        FOREIGN KEY (suite_id) REFERENCES mcp_suites(id)
    )""")
    
    print("✅ Tables created")
    
    # Database is ready - NO hardcoded servers!
    print("✅ Empty database created - ready for discovery system to populate")
    
    conn.commit()
    conn.close()
    
    print(f"📊 Database ready: {db_path}")
    print()
    print("🧪 Next: Discovery system will populate servers automatically")
    print("   Use: mcp-manager discover")
    print("   Or: ./test unit (auto-populates during testing)")
    return True

if __name__ == "__main__":
    success = create_database()
    exit(0 if success else 1)