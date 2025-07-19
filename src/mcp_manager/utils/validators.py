"""
Validation utilities for MCP Manager.

Provides validation functions for server configurations,
dependencies, and system requirements.
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from mcp_manager.core.exceptions import DependencyError, ValidationError
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


def validate_server_name(name: str) -> bool:
    """
    Validate server name.
    
    Args:
        name: Server name to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Server name cannot be empty")
        
    if len(name) > 100:
        raise ValidationError("Server name too long (max 100 characters)")
        
    # Check for invalid characters
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValidationError("Server name can only contain letters, numbers, hyphens, and underscores")
        
    return True


def validate_command(command: str) -> bool:
    """
    Validate server command.
    
    Args:
        command: Command to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If command is invalid
    """
    if not command or not command.strip():
        raise ValidationError("Server command cannot be empty")
        
    # Check if command is too long
    if len(command) > 1000:
        raise ValidationError("Server command too long (max 1000 characters)")
        
    return True


def validate_environment_variables(env_vars: str) -> bool:
    """
    Validate environment variables format.
    
    Args:
        env_vars: Environment variables in KEY=VALUE format
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If format is invalid
    """
    if not env_vars.strip():
        return True
        
    for line in env_vars.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if '=' not in line:
            raise ValidationError(f"Invalid environment variable format: {line}")
            
        key, _ = line.split('=', 1)
        if not key.strip():
            raise ValidationError(f"Empty environment variable key: {line}")
            
        # Check for valid environment variable name
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key.strip()):
            raise ValidationError(f"Invalid environment variable name: {key}")
            
    return True


def check_system_dependencies() -> List[str]:
    """
    Check for required system dependencies.
    
    Returns:
        List of missing dependencies
    """
    logger.debug("Checking system dependencies")
    
    required_deps = [
        ("python", "Python interpreter"),
        ("claude", "Claude CLI"),
    ]
    
    optional_deps = [
        ("npm", "NPM package manager"),
        ("docker", "Docker container runtime"),
        ("git", "Git version control"),
    ]
    
    missing = []
    
    # Check required dependencies
    for dep, description in required_deps:
        if not shutil.which(dep):
            missing.append(f"{dep} ({description})")
            logger.warning(f"Missing required dependency: {dep}")
            
    # Check optional dependencies (log but don't fail)
    for dep, description in optional_deps:
        if not shutil.which(dep):
            logger.info(f"Optional dependency not available: {dep}")
            
    return missing


def validate_claude_cli() -> Tuple[bool, Optional[str]]:
    """
    Validate Claude CLI availability and version.
    
    Returns:
        Tuple of (available, version)
    """
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            logger.debug(f"Claude CLI available: {version}")
            return True, version
        else:
            logger.warning("Claude CLI found but version check failed")
            return False, None
            
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Claude CLI not available: {e}")
        return False, None


def validate_npm_package(package: str) -> bool:
    """
    Validate NPM package name format.
    
    Args:
        package: NPM package name
        
    Returns:
        True if valid format
        
    Raises:
        ValidationError: If package name is invalid
    """
    if not package or not package.strip():
        raise ValidationError("NPM package name cannot be empty")
        
    # Basic NPM package name validation
    if not re.match(r"^(@[a-z0-9-*~][a-z0-9-*._~]*/)?[a-z0-9-~][a-z0-9-._~]*$", package.lower()):
        raise ValidationError(f"Invalid NPM package name: {package}")
        
    return True


def validate_docker_image(image: str) -> bool:
    """
    Validate Docker image name format.
    
    Args:
        image: Docker image name
        
    Returns:
        True if valid format
        
    Raises:
        ValidationError: If image name is invalid
    """
    if not image or not image.strip():
        raise ValidationError("Docker image name cannot be empty")
        
    # Basic Docker image name validation
    if not re.match(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*(?::[a-zA-Z0-9._-]+)?$", image.lower()):
        raise ValidationError(f"Invalid Docker image name: {image}")
        
    return True


def validate_config_directory(config_dir: Path) -> bool:
    """
    Validate configuration directory.
    
    Args:
        config_dir: Configuration directory path
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If directory is invalid
    """
    try:
        # Check if directory exists or can be created
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            
        # Check if directory is writable
        test_file = config_dir / ".test_write"
        test_file.touch()
        test_file.unlink()
        
        logger.debug(f"Configuration directory validated: {config_dir}")
        return True
        
    except (OSError, PermissionError) as e:
        raise ValidationError(f"Cannot access configuration directory {config_dir}: {e}")


def validate_log_file(log_file: Path) -> bool:
    """
    Validate log file path.
    
    Args:
        log_file: Log file path
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If log file path is invalid
    """
    try:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file can be created/written
        log_file.touch(exist_ok=True)
        
        logger.debug(f"Log file path validated: {log_file}")
        return True
        
    except (OSError, PermissionError) as e:
        raise ValidationError(f"Cannot access log file {log_file}: {e}")


def validate_server_config(config: dict) -> bool:
    """
    Validate complete server configuration.
    
    Args:
        config: Server configuration dictionary
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If configuration is invalid
    """
    required_fields = ["name", "command", "scope", "server_type"]
    
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"Missing required field: {field}")
            
    # Validate individual fields
    validate_server_name(config["name"])
    validate_command(config["command"])
    
    return True