"""
Server configuration helper functions.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any

import yaml
from rich.console import Console
from rich.prompt import Prompt

from mcp_manager.core.models import ServerType

console = Console()


def _prompt_from_requirements(server_name: str, requirements: List[Dict[str, Any]], test_mode: bool = False) -> Optional[dict]:
    """Prompt user based on requirements specification."""
    from rich.prompt import Prompt
    
    if not requirements or test_mode:
        return None
    
    console.print(f"[blue]ℹ {server_name} requires additional configuration[/blue]")
    
    config = {}
    final_args = []
    
    for req in requirements:
        req_type = req.get("type")
        prompt = req.get("prompt", f"Enter {req_type}")
        default = req.get("default")
        required = req.get("required", False)
        
        if req_type == "directory_access":
            console.print(f"[dim]{prompt}[/dim]")
            directory = Prompt.ask("Directory path", default=default)
            if directory:
                # Add volume mount to final args
                final_args.extend(["-v", f"{directory}:{directory}"])
                config["directory_access"] = directory
        
        elif req_type == "api_key":
            api_key = Prompt.ask(prompt, password=True)
            if api_key:
                config["api_key"] = api_key
                # Add as environment variable
                final_args.extend(["-e", f"API_KEY={api_key}"])
        
        elif req_type == "grafana_url":
            url = Prompt.ask(prompt, default=default)
            if url:
                config["grafana_url"] = url
                final_args.extend(["-e", f"GRAFANA_URL={url}"])
        
        elif req_type == "slack_token":
            token = Prompt.ask(prompt, password=True)
            if token:
                config["slack_token"] = token
                final_args.extend(["-e", f"SLACK_TOKEN={token}"])
        
        # Add more requirement types as needed
    
    # Return configuration with generated args
    if final_args:
        config["args"] = final_args
    
    return config if config else None


def prompt_for_server_configuration(server_name: str, server_type: ServerType, package: Optional[str], test_mode: bool = False, requirements: List[Dict[str, Any]] = None) -> Optional[dict]:
    """Prompt user for server configuration if needed."""
    
    # Use new requirements system if available
    if requirements:
        return _prompt_from_requirements(server_name, requirements, test_mode)
    
    # Fallback to old system
    config_requirements = {
        # Filesystem servers
        'filesystem': {
            'description': 'Filesystem access requires specifying allowed directories',
            'prompts': [
                {
                    'key': 'directory',
                    'prompt': 'Enter directory path to allow access to',
                    'default': os.path.expanduser("~"),
                    'help': 'This directory will be accessible to the MCP server'
                }
            ]
        },
        # SQLite servers
        'sqlite': {
            'description': 'SQLite server requires a database file path',
            'prompts': [
                {
                    'key': 'db_path',
                    'prompt': 'Enter SQLite database file path',
                    'default': '/tmp/claude-mcp.db',
                    'help': 'Path to SQLite database file (will be created if it doesn\'t exist)'
                }
            ]
        },
        # PostgreSQL servers
        'postgres': {
            'description': 'PostgreSQL server requires database connection details',
            'prompts': [
                {
                    'key': 'connection_string',
                    'prompt': 'Enter PostgreSQL connection string',
                    'default': 'postgresql://localhost:5432/claude',
                    'help': 'Format: postgresql://user:password@host:port/database'
                }
            ]
        }
    }
    
    # Check if this server needs configuration
    server_key = None
    for key in config_requirements:
        if key in server_name.lower() or (package and key in package.lower()):
            server_key = key
            break
    
    if not server_key:
        return None
    
    config_req = config_requirements[server_key]
    
    if test_mode:
        # In test mode, use defaults without prompting
        console.print(f"\n[blue]ℹ[/blue] {config_req['description']} - Using defaults for test suite")
    else:
        console.print(f"\n[blue]ℹ[/blue] {config_req['description']}")
    
    config = {'args': []}
    for prompt_config in config_req['prompts']:
        if test_mode:
            # Use default value without prompting in test mode
            value = prompt_config['default']
            console.print(f"[dim]Using default for testing: {value}[/dim]")
        else:
            console.print(f"[dim]{prompt_config['help']}[/dim]")
            
            try:
                value = Prompt.ask(
                    prompt_config['prompt'],
                    default=prompt_config['default']
                )
            except (EOFError, KeyboardInterrupt):
                # Use default value if prompting fails (non-interactive context)
                value = prompt_config['default']
                console.print(f"[dim]Using default: {value}[/dim]")
        
        if server_key == 'filesystem':
            # Expand user path
            value = os.path.expanduser(value)
            if server_type == ServerType.DOCKER_DESKTOP:
                config['directory'] = value
            else:
                # For Docker containers, add volume mount and directory path as final arg
                config['args'].extend(['-v', f'{value}:{value}'])
                config['final_args'] = [value]  # Directory path goes after image name
                
        elif server_key == 'sqlite':
            # Create database file if it doesn't exist
            db_path = os.path.expanduser(value)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            if not os.path.exists(db_path):
                # Create empty SQLite database
                with sqlite3.connect(db_path):
                    pass
                console.print(f"[green]✓[/green] Created database file: {db_path}")
            
            if server_type == ServerType.DOCKER_DESKTOP:
                config['db_path'] = db_path
            else:
                config['args'].extend(['--db-path', db_path])
                
        elif server_key == 'postgres':
            if server_type == ServerType.DOCKER_DESKTOP:
                config['connection_string'] = value
            else:
                config['args'].extend(['--connection-string', value])
    
    return config if config.get('args') or any(k != 'args' for k in config.keys()) else None


def update_docker_mcp_config(server_name: str, config: dict):
    """Update Docker MCP configuration file with server-specific config."""
    
    config_file = Path.home() / ".docker" / "mcp" / "config.yaml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing config or create new
    existing_config = {}
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                existing_config = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            pass
    
    # Update with new server config
    server_config = {'env': {}}
    
    if 'directory' in config:
        server_config['args'] = [config['directory']]
    elif 'db_path' in config:
        server_config['args'] = [f"--db-path={config['db_path']}"]
    elif 'connection_string' in config:
        server_config['args'] = [f"--connection-string={config['connection_string']}"]
    
    existing_config[server_name] = server_config
    
    # Save updated config
    with open(config_file, 'w') as f:
        yaml.dump(existing_config, f, default_flow_style=False)