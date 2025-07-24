"""
CLI helper functions and utilities.
"""

from .configuration import prompt_for_server_configuration, update_docker_mcp_config
from .discovery import generate_install_id, tag_server_with_suite
from .display import show_server_details_after_install, show_discovery_for_next_install
from .errors import handle_errors

__all__ = [
    'prompt_for_server_configuration',
    'update_docker_mcp_config', 
    'generate_install_id',
    'tag_server_with_suite',
    'show_server_details_after_install',
    'show_discovery_for_next_install',
    'handle_errors'
]