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
        
    if len(name) < 2:
        raise ValidationError("Server name too short (min 2 characters)")
        
    # Reserved names
    reserved_names = ["all", "none", "true", "false", "null", "undefined"]
    if name.lower() in reserved_names:
        raise ValidationError(f"'{name}' is a reserved name. Please choose a different name")
        
    # Check for invalid characters - allow @ for scoped packages
    if not re.match(r"^[@a-zA-Z0-9/_.-]+$", name):
        raise ValidationError(
            "Server name can only contain letters, numbers, hyphens, underscores, "
            "forward slashes, dots, and @ symbol (for scoped packages)"
        )
        
    # Check for valid scoped package format if @ is present
    if "@" in name:
        if not re.match(r"^@[a-zA-Z0-9-]+/[a-zA-Z0-9_.-]+$", name):
            raise ValidationError(
                "Invalid scoped package format. Expected: @scope/package-name"
            )
        
    return True


def validate_command(command: str, server_type: Optional[str] = None) -> bool:
    """
    Validate server command.
    
    Args:
        command: Command to validate
        server_type: Type of server (npm, docker, custom)
        
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
        
    # Security checks
    dangerous_patterns = [
        r";\s*rm\s+-rf",  # rm -rf command
        r"&&\s*rm\s+-rf",
        r"\|\s*rm\s+-rf",
        r">\s*/dev/.*",  # redirecting to device files
        r"curl.*\|\s*sh",  # curl piped to shell
        r"wget.*\|\s*sh",
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            raise ValidationError(
                f"Command contains potentially dangerous pattern. "
                "Please review the command for security concerns."
            )
    
    # Type-specific validation
    if server_type == "npm":
        if not command.startswith(("npx", "npm", "node")):
            logger.warning(
                f"NPM server command doesn't start with npx/npm/node: {command}"
            )
            
    elif server_type == "docker":
        if not command.startswith("docker"):
            raise ValidationError(
                "Docker server command must start with 'docker'. "
                f"Got: {command.split()[0] if command.split() else ''}"
            )
            
        # Check for required docker flags
        if "-i" not in command and "--interactive" not in command:
            logger.warning(
                "Docker command missing interactive flag (-i). "
                "MCP servers typically require interactive mode."
            )
        
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
    validate_command(config["command"], config.get("server_type"))
    
    return True


def suggest_server_name_correction(invalid_name: str) -> Optional[str]:
    """
    Suggest a corrected server name based on invalid input.
    
    Args:
        invalid_name: The invalid server name
        
    Returns:
        Suggested correction or None
    """
    if not invalid_name:
        return None
        
    # Remove invalid characters
    suggested = re.sub(r"[^@a-zA-Z0-9/_.-]", "-", invalid_name)
    
    # Replace multiple consecutive hyphens
    suggested = re.sub(r"-+", "-", suggested)
    
    # Remove leading/trailing hyphens
    suggested = suggested.strip("-")
    
    # Ensure minimum length
    if len(suggested) < 2:
        suggested = f"server-{suggested}" if suggested else "server-name"
        
    # Truncate if too long
    if len(suggested) > 100:
        suggested = suggested[:100]
        
    return suggested


def validate_server_availability(server_type: str, server_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a server is available for installation.
    
    Args:
        server_type: Type of server (npm, docker)
        server_name: Name/package of the server
        
    Returns:
        Tuple of (available, error_message)
    """
    if server_type == "npm":
        # Check if NPM is available
        if not shutil.which("npm"):
            return False, "NPM is not installed. Install Node.js and NPM to use NPM-based servers."
            
        # Could check NPM registry here, but that would be async
        # For now, assume it's available
        return True, None
        
    elif server_type == "docker":
        # Check if Docker is available
        if not shutil.which("docker"):
            return False, "Docker is not installed. Install Docker Desktop to use Docker-based servers."
            
        # Check if Docker daemon is running
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False, "Docker daemon is not running. Start Docker Desktop and try again."
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return False, "Cannot connect to Docker. Ensure Docker Desktop is running."
            
        return True, None
        
    # Custom servers are always "available"
    return True, None