"""
File system watchers for monitoring external MCP configuration changes.

This module provides comprehensive monitoring of MCP-related configuration files
across all scopes (user, project, internal) to detect changes made by external
tools like `docker mcp` or `claude mcp` commands.
"""

import asyncio
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigChangeEvent:
    """Represents a configuration file change event."""
    
    def __init__(
        self,
        file_path: str,
        event_type: str,
        scope: str,
        source: str,
        timestamp: datetime = None
    ):
        self.file_path = file_path
        self.event_type = event_type  # 'created', 'modified', 'deleted', 'moved'
        self.scope = scope  # 'user', 'project', 'internal'
        self.source = source  # 'docker', 'claude', 'manual'
        self.timestamp = timestamp or datetime.now()
    
    def __str__(self) -> str:
        return f"ConfigChangeEvent({self.source}:{self.scope}:{self.event_type}:{Path(self.file_path).name})"


class ConfigFileHandler(FileSystemEventHandler):
    """Handles file system events for MCP configuration files."""
    
    def __init__(self, callback: Callable[[ConfigChangeEvent], None], scope: str, source: str):
        super().__init__()
        self.callback = callback
        self.scope = scope
        self.source = source
        self._debounce_events: Dict[str, datetime] = {}
        self._debounce_delay = timedelta(seconds=1)  # Debounce rapid changes
    
    def _should_process_event(self, file_path: str) -> bool:
        """Check if we should process this event (debouncing)."""
        now = datetime.now()
        last_event = self._debounce_events.get(file_path)
        
        if last_event and (now - last_event) < self._debounce_delay:
            return False
        
        self._debounce_events[file_path] = now
        return True
    
    def _is_relevant_file(self, file_path: str) -> bool:
        """Check if the file is relevant for MCP configuration monitoring."""
        file_name = os.path.basename(file_path)
        relevant_files = [
            'registry.yaml',
            'mcp-servers.json',
            '.mcp.json',
            '.claude.json',
            'server_catalog.json',
            '.mcp-manager.toml'
        ]
        return file_name in relevant_files
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
            
        if not self._is_relevant_file(event.src_path):
            return
            
        if not self._should_process_event(event.src_path):
            return
            
        logger.debug(f"Config file modified: {event.src_path}")
        change_event = ConfigChangeEvent(
            file_path=event.src_path,
            event_type='modified',
            scope=self.scope,
            source=self.source
        )
        self.callback(change_event)
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
            
        if not self._is_relevant_file(event.src_path):
            return
            
        logger.debug(f"Config file created: {event.src_path}")
        change_event = ConfigChangeEvent(
            file_path=event.src_path,
            event_type='created',
            scope=self.scope,
            source=self.source
        )
        self.callback(change_event)
    
    def on_deleted(self, event):
        """Handle file deletion events."""
        if event.is_directory:
            return
            
        if not self._is_relevant_file(event.src_path):
            return
            
        logger.debug(f"Config file deleted: {event.src_path}")
        change_event = ConfigChangeEvent(
            file_path=event.src_path,
            event_type='deleted',
            scope=self.scope,
            source=self.source
        )
        self.callback(change_event)
    
    def on_moved(self, event):
        """Handle file move/rename events."""
        if event.is_directory:
            return
            
        # Check both source and destination paths
        src_relevant = self._is_relevant_file(event.src_path)
        dest_relevant = self._is_relevant_file(event.dest_path)
        
        if src_relevant or dest_relevant:
            logger.debug(f"Config file moved: {event.src_path} -> {event.dest_path}")
            change_event = ConfigChangeEvent(
                file_path=event.dest_path,
                event_type='moved',
                scope=self.scope,
                source=self.source
            )
            self.callback(change_event)


class ConfigWatcher:
    """Watches MCP configuration files for changes across all scopes."""
    
    def __init__(self, change_callback: Optional[Callable[[ConfigChangeEvent], None]] = None):
        self.change_callback = change_callback or self._default_change_callback
        self.observer = Observer()
        self._watch_handles: List[Any] = []
        self._is_running = False
        self._lock = threading.Lock()
        
        # Configuration paths to monitor
        self._config_paths = self._get_config_paths()
    
    def _default_change_callback(self, event: ConfigChangeEvent):
        """Default callback that just logs the event."""
        logger.info(f"Config change detected: {event}")
    
    def _get_config_paths(self) -> Dict[str, Dict[str, str]]:
        """Get all configuration paths to monitor by scope and source."""
        home_dir = Path.home()
        
        return {
            # Docker Desktop configurations
            'docker': {
                'user': str(home_dir / '.docker' / 'mcp'),
                'registry_file': str(home_dir / '.docker' / 'mcp' / 'registry.yaml'),
            },
            
            # Claude configurations
            'claude': {
                'user': str(home_dir / '.config' / 'claude-code'),
                'user_file': str(home_dir / '.config' / 'claude-code' / 'mcp-servers.json'),
                'internal': str(home_dir),
                'internal_file': str(home_dir / '.claude.json'),
            },
            
            # MCP Manager configurations  
            'mcp_manager': {
                'user': str(home_dir / '.config' / 'mcp-manager'),
                'catalog_file': str(home_dir / '.config' / 'mcp-manager' / 'server_catalog.json'),
            }
        }
    
    def start(self):
        """Start monitoring configuration files."""
        with self._lock:
            if self._is_running:
                logger.warning("ConfigWatcher is already running")
                return
            
            try:
                self._setup_watchers()
                self.observer.start()
                self._is_running = True
                logger.info("ConfigWatcher started successfully")
                
            except Exception as e:
                logger.error(f"Failed to start ConfigWatcher: {e}")
                self.stop()
                raise
    
    def stop(self):
        """Stop monitoring configuration files."""
        with self._lock:
            if not self._is_running:
                return
            
            try:
                self.observer.stop()
                self.observer.join(timeout=5.0)
                self._watch_handles.clear()
                self._is_running = False
                logger.info("ConfigWatcher stopped successfully")
                
            except Exception as e:
                logger.error(f"Error stopping ConfigWatcher: {e}")
    
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._is_running
    
    def _setup_watchers(self):
        """Set up file system watchers for all configuration paths."""
        config_paths = self._config_paths
        
        # Watch Docker Desktop registry
        self._setup_docker_watcher(config_paths['docker'])
        
        # Watch Claude configurations
        self._setup_claude_watcher(config_paths['claude'])
        
        # Watch MCP Manager configurations
        self._setup_mcp_manager_watcher(config_paths['mcp_manager'])
        
        # Watch for project-level configurations (current directory)
        self._setup_project_watcher()
    
    def _setup_docker_watcher(self, docker_paths: Dict[str, str]):
        """Set up watcher for Docker Desktop MCP configurations."""
        docker_dir = docker_paths['user']
        
        if os.path.exists(docker_dir):
            handler = ConfigFileHandler(
                callback=self.change_callback,
                scope='user',
                source='docker'
            )
            watch_handle = self.observer.schedule(handler, docker_dir, recursive=False)
            self._watch_handles.append(watch_handle)
            logger.debug(f"Watching Docker MCP directory: {docker_dir}")
        else:
            logger.debug(f"Docker MCP directory not found: {docker_dir}")
    
    def _setup_claude_watcher(self, claude_paths: Dict[str, str]):
        """Set up watcher for Claude MCP configurations."""
        # Watch user-level Claude config
        claude_user_dir = claude_paths['user']
        if os.path.exists(claude_user_dir):
            handler = ConfigFileHandler(
                callback=self.change_callback,
                scope='user',
                source='claude'
            )
            watch_handle = self.observer.schedule(handler, claude_user_dir, recursive=False)
            self._watch_handles.append(watch_handle)
            logger.debug(f"Watching Claude user config directory: {claude_user_dir}")
        
        # Watch internal Claude config (home directory for .claude.json)
        claude_internal_dir = claude_paths['internal']
        if os.path.exists(claude_internal_dir):
            handler = ConfigFileHandler(
                callback=self.change_callback,
                scope='internal',
                source='claude'
            )
            watch_handle = self.observer.schedule(handler, claude_internal_dir, recursive=False)
            self._watch_handles.append(watch_handle)
            logger.debug(f"Watching Claude internal config directory: {claude_internal_dir}")
    
    def _setup_mcp_manager_watcher(self, mcp_manager_paths: Dict[str, str]):
        """Set up watcher for MCP Manager configurations."""
        mcp_manager_dir = mcp_manager_paths['user']
        
        if os.path.exists(mcp_manager_dir):
            handler = ConfigFileHandler(
                callback=self.change_callback,
                scope='user',
                source='mcp_manager'
            )
            watch_handle = self.observer.schedule(handler, mcp_manager_dir, recursive=False)
            self._watch_handles.append(watch_handle)
            logger.debug(f"Watching MCP Manager config directory: {mcp_manager_dir}")
    
    def _setup_project_watcher(self):
        """Set up watcher for project-level MCP configurations."""
        # Watch current working directory for .mcp.json and .mcp-manager.toml
        current_dir = os.getcwd()
        
        handler = ConfigFileHandler(
            callback=self.change_callback,
            scope='project',
            source='claude'
        )
        watch_handle = self.observer.schedule(handler, current_dir, recursive=False)
        self._watch_handles.append(watch_handle)
        logger.debug(f"Watching project config directory: {current_dir}")
        
        # Also watch parent directories up to home directory for project configs
        parent_dir = Path(current_dir).parent
        home_dir = Path.home()
        
        while parent_dir != home_dir and parent_dir != parent_dir.parent:
            if parent_dir.exists():
                handler = ConfigFileHandler(
                    callback=self.change_callback,
                    scope='project',
                    source='claude'
                )
                watch_handle = self.observer.schedule(handler, str(parent_dir), recursive=False)
                self._watch_handles.append(watch_handle)
                logger.debug(f"Watching parent project directory: {parent_dir}")
            
            parent_dir = parent_dir.parent


class AsyncConfigWatcher:
    """Async wrapper for ConfigWatcher that integrates with asyncio event loops."""
    
    def __init__(self, change_callback: Optional[Callable[[ConfigChangeEvent], Any]] = None):
        self.change_callback = change_callback
        self._watcher = None
        self._event_queue = asyncio.Queue()
        self._processing_task = None
    
    async def start(self):
        """Start the async config watcher."""
        if self._watcher and self._watcher.is_running():
            logger.warning("AsyncConfigWatcher is already running")
            return
        
        # Create watcher with queue-based callback
        self._watcher = ConfigWatcher(self._queue_event)
        
        # Start the background watcher
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._watcher.start)
        
        # Start event processing task
        self._processing_task = asyncio.create_task(self._process_events())
        
        logger.info("AsyncConfigWatcher started")
    
    async def stop(self):
        """Stop the async config watcher."""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        if self._watcher:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._watcher.stop)
        
        logger.info("AsyncConfigWatcher stopped")
    
    def _queue_event(self, event: ConfigChangeEvent):
        """Queue an event for async processing."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"Event queue full, dropping event: {event}")
    
    async def _process_events(self):
        """Process queued events asynchronously."""
        while True:
            try:
                event = await self._event_queue.get()
                
                if self.change_callback:
                    if asyncio.iscoroutinefunction(self.change_callback):
                        await self.change_callback(event)
                    else:
                        self.change_callback(event)
                
                self._event_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing config change event: {e}")


# Convenience functions for common use cases

def start_config_monitoring(callback: Callable[[ConfigChangeEvent], None]) -> ConfigWatcher:
    """Start monitoring configuration files with a callback."""
    watcher = ConfigWatcher(callback)
    watcher.start()
    return watcher


async def start_async_config_monitoring(
    callback: Callable[[ConfigChangeEvent], Any]
) -> AsyncConfigWatcher:
    """Start async monitoring of configuration files."""
    watcher = AsyncConfigWatcher(callback)
    await watcher.start()
    return watcher