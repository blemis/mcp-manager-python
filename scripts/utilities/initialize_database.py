#!/usr/bin/env python3
"""
MCP Manager Database Bootstrap Script

Initializes the complete SQLite + WAL database system with Option 3 schema.
Migrates existing data and populates server registry from discovery.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.mcp_manager.core.database.initialization import bootstrap_mcp_database

async def main():
    """Bootstrap the MCP Manager database system."""
    print("🚀 MCP Manager Database Bootstrap")
    print("=" * 50)
    print()
    
    # Paths
    new_db_path = Path("data/mcp_manager.db")
    old_db_path = Path("tests/fixtures/test_suites.db")
    
    print(f"📊 New database: {new_db_path}")
    print(f"🔄 Old database: {old_db_path}")
    print()
    
    # Create data directory
    new_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Bootstrap the system
    success = await bootstrap_mcp_database(
        db_path=new_db_path,
        old_db_path=old_db_path,
        force_migration=True
    )
    
    if success:
        print("\n" + "=" * 50)
        print("✅ Database bootstrap completed successfully!")
        print()
        print("📝 Next steps:")
        print("   1. Test with: python -c 'from src.mcp_manager.core.database import *; print(\"Database ready!\")'")
        print("   2. List suites: mcp-manager test-admin list-suites")
        print("   3. Run tests: ./test unit")
        print()
        return True
    else:
        print("\n" + "=" * 50)
        print("❌ Database bootstrap failed!")
        print()
        print("🔍 Check the logs above for error details")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)