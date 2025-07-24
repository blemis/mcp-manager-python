"""
Error handling utilities for CLI commands.
"""

import functools
import sys
from rich.console import Console

console = Console()


def handle_errors(func):
    """Decorator to handle common CLI errors."""
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[dim]Use --debug for more details[/dim]")
            sys.exit(1)
    
    return wrapper