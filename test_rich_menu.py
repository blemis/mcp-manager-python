#!/usr/bin/env python3
"""
Quick test script for the new Rich-based TUI menu.
Run this to see the new interface in action.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_manager.tui.rich_menu import main

if __name__ == "__main__":
    print("🚀 Starting Rich-based MCP Manager TUI...")
    print("✨ Features: Clean tables, proper colors, reliable navigation")
    print("📝 Much better than the problematic Textual interface!")
    print()
    main()