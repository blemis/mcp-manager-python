"""
Dynamic executable path detection for MCP Manager.

Automatically detects where system executables are located to fix
Claude Code's inability to find executables not in standard paths.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional
from functools import lru_cache

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ExecutableDetector:
    """Detects and caches executable paths for MCP server commands."""
    
    # Cache discovered paths
    _path_cache: Dict[str, Optional[str]] = {}
    
    @classmethod
    @lru_cache(maxsize=100)
    def find_executable(cls, executable_name: str) -> Optional[str]:
        """
        Find the full path to an executable.
        
        Args:
            executable_name: Name of executable to find (e.g., 'docker', 'npx')
            
        Returns:
            Full path to executable if found, None otherwise
        """
        # Check cache first
        if executable_name in cls._path_cache:
            return cls._path_cache[executable_name]
        
        # Try multiple detection methods
        path = None
        
        # Method 1: Use shutil.which (most reliable)
        try:
            path = shutil.which(executable_name)
            if path:
                logger.debug(f"Found {executable_name} at {path} via shutil.which")
        except Exception as e:
            logger.debug(f"shutil.which failed for {executable_name}: {e}")
        
        # Method 2: Try common paths if shutil.which fails
        if not path:
            common_paths = [
                '/opt/homebrew/bin',
                '/usr/local/bin', 
                '/usr/bin',
                '/bin',
                '/opt/local/bin',
                '~/.local/bin',
                '~/bin'
            ]
            
            for base_path in common_paths:
                expanded_path = Path(base_path).expanduser()
                full_path = expanded_path / executable_name
                if full_path.exists() and full_path.is_file():
                    path = str(full_path)
                    logger.debug(f"Found {executable_name} at {path} in common paths")
                    break
        
        # Method 3: Try subprocess which as fallback
        if not path:
            try:
                result = subprocess.run(
                    ['which', executable_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    path = result.stdout.strip()
                    logger.debug(f"Found {executable_name} at {path} via subprocess which")
            except Exception as e:
                logger.debug(f"subprocess which failed for {executable_name}: {e}")
        
        # Cache the result (even if None)
        cls._path_cache[executable_name] = path
        
        if path:
            logger.info(f"Detected executable: {executable_name} -> {path}")
        else:
            logger.warning(f"Could not find executable: {executable_name}")
            
        return path
    
    @classmethod
    def get_docker_path(cls) -> Optional[str]:
        """Get full path to docker executable."""
        return cls.find_executable('docker')
    
    @classmethod
    def get_npx_path(cls) -> Optional[str]:
        """Get full path to npx executable."""
        return cls.find_executable('npx')
    
    @classmethod
    def get_uv_path(cls) -> Optional[str]:
        """Get full path to uv executable.""" 
        return cls.find_executable('uv')
    
    @classmethod
    def get_python_path(cls) -> Optional[str]:
        """Get full path to python executable."""
        return cls.find_executable('python3') or cls.find_executable('python')
    
    @classmethod
    def clear_cache(cls):
        """Clear the executable path cache."""
        cls._path_cache.clear()
        cls.find_executable.cache_clear()
        logger.debug("Cleared executable path cache")
    
    @classmethod
    def get_command_with_full_path(cls, command: str, args: list = None) -> tuple[str, list]:
        """
        Get command with detected full path.
        
        Args:
            command: Command name (e.g., 'docker', 'npx')
            args: Command arguments
            
        Returns:
            Tuple of (full_path_command, args)
        """
        args = args or []
        
        # Get full path to executable
        full_path = cls.find_executable(command)
        
        if full_path:
            return full_path, args
        else:
            # If we can't find it, return original and hope for the best
            logger.warning(f"Using original command '{command}' - executable not found")
            return command, args
    
    @classmethod
    def verify_executable_works(cls, executable_path: str) -> bool:
        """
        Verify that an executable actually works.
        
        Args:
            executable_path: Full path to executable
            
        Returns:
            True if executable works, False otherwise
        """
        try:
            result = subprocess.run(
                [executable_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            works = result.returncode == 0
            if works:
                logger.debug(f"Verified {executable_path} works: {result.stdout.strip()}")
            else:
                logger.warning(f"Executable {executable_path} failed version check")
            return works
        except Exception as e:
            logger.warning(f"Could not verify {executable_path}: {e}")
            return False
    
    @classmethod
    def get_system_info(cls) -> Dict[str, str]:
        """Get information about detected executables."""
        info = {}
        
        for executable in ['docker', 'npx', 'uv', 'python3', 'python']:
            path = cls.find_executable(executable)
            if path:
                info[executable] = path
                
                # Get version if possible
                try:
                    result = subprocess.run(
                        [path, '--version'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        info[f"{executable}_version"] = result.stdout.strip()
                except:
                    pass
        
        return info


# Convenience functions
def find_executable(name: str) -> Optional[str]:
    """Find full path to executable."""
    return ExecutableDetector.find_executable(name)

def get_docker_path() -> Optional[str]:
    """Get full path to docker."""
    return ExecutableDetector.get_docker_path()

def get_npx_path() -> Optional[str]:
    """Get full path to npx."""
    return ExecutableDetector.get_npx_path()