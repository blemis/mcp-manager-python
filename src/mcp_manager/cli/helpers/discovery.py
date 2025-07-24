"""
Discovery and installation helper functions.
"""

from typing import Optional
from rich.console import Console

from mcp_manager.core.models import ServerType

console = Console()


def generate_install_id(result) -> str:
    """Generate consistent install ID for a discovery result."""
    if result.server_type == ServerType.NPM:
        return result.package.replace("@", "").replace("/", "-").replace("server-", "")
    elif result.server_type == ServerType.DOCKER:
        return result.package.replace("/", "-")
    elif result.server_type == ServerType.DOCKER_DESKTOP:
        return f"dd-{result.name.replace('docker-desktop-', '')}"
    else:
        return result.name


async def tag_server_with_suite(server_name: str, category: str, priority: str, install_id: str):
    """Tag a server with suite information in the database."""
    import sqlite3
    from pathlib import Path
    
    try:
        # Connect to the tool registry database
        db_path = Path.home() / ".config" / "mcp-manager" / "tool_registry.db"
        if not db_path.exists():
            return
        
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Check if servers table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='servers'")
            if not cursor.fetchone():
                return
            
            # Update or insert server with suite tags
            cursor.execute("""
                INSERT OR REPLACE INTO servers (
                    name, install_id, category, priority, suite_tags, last_updated
                ) VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (server_name, install_id, category, priority, category))
            
            conn.commit()
            
    except Exception as e:
        # Silent failure - tagging is nice-to-have
        pass