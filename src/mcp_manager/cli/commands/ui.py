"""
UI commands for MCP Manager CLI.
"""

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def ui_commands(cli_context):
    """Add UI commands to the CLI."""
    
    @click.command()
    @handle_errors 
    def tui():
        """Launch the Rich-based terminal user interface."""
        try:
            from mcp_manager.tui.rich_menu import launch_rich_menu
            launch_rich_menu()
        except ImportError:
            console.print("[red]Rich TUI not available - missing dependencies[/red]")
        except Exception as e:
            console.print(f"[red]Failed to launch TUI: {e}[/red]")
    
    
    @click.command("tui-simple")
    @handle_errors
    def tui_simple():
        """Launch the simple Rich-based terminal user interface."""
        try:
            from mcp_manager.tui.simple_tui import SimpleTUI
            tui = SimpleTUI()
            tui.run()
        except ImportError:
            console.print("[red]Simple TUI not available - missing dependencies[/red]")
        except Exception as e:
            console.print(f"[red]Failed to launch simple TUI: {e}[/red]")
    
    
    @click.command("tui-textual")
    @handle_errors
    def tui_textual():
        """Launch the Textual-based terminal user interface (same as 'tui')."""
        try:
            from mcp_manager.tui.menu_app import MCPManagerApp
            app = MCPManagerApp()
            app.run()
        except ImportError:
            console.print("[red]Textual TUI not available - install with: pip install textual[/red]")
        except Exception as e:
            console.print(f"[red]Failed to launch Textual TUI: {e}[/red]")
    
    return [tui, tui_simple, tui_textual]