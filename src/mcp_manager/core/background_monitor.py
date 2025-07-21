"""
Background monitoring service for external MCP configuration changes.

This module provides a daemon-like service that continuously monitors
external MCP configurations and can automatically sync changes or notify users.
"""

import asyncio
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
import json
import logging

from mcp_manager.core.change_detector import ChangeDetector, DetectedChange
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.utils.logging import get_logger
from mcp_manager.utils.config import get_config

logger = get_logger(__name__)


class BackgroundMonitor:
    """Background service for monitoring external MCP configuration changes."""
    
    def __init__(
        self, 
        manager: Optional[SimpleMCPManager] = None,
        check_interval: int = 60,  # seconds
        auto_sync: bool = False,
        notification_callback: Optional[Callable[[List[DetectedChange]], None]] = None
    ):
        self.manager = manager or SimpleMCPManager()
        self.detector = ChangeDetector(self.manager)
        self.check_interval = check_interval
        self.auto_sync = auto_sync
        self.notification_callback = notification_callback
        
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.change_history: List[DetectedChange] = []
        
        # Statistics
        self.start_time: Optional[datetime] = None
        self.checks_performed = 0
        self.changes_detected = 0
        self.changes_synced = 0
        self.last_check: Optional[datetime] = None
        
        # State file for persistence
        self.state_file = Path.home() / ".config" / "mcp-manager" / "monitor_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start the background monitoring service."""
        if self.running:
            logger.warning("Monitor is already running")
            return
        
        self.running = True
        self.start_time = datetime.now()
        
        logger.info(f"Starting background monitor with {self.check_interval}s interval")
        logger.info(f"Auto-sync: {'enabled' if self.auto_sync else 'disabled'}")
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        try:
            await self.monitor_task
        except asyncio.CancelledError:
            logger.info("Monitor task cancelled")
    
    async def stop(self):
        """Stop the background monitoring service."""
        if not self.running:
            logger.warning("Monitor is not running")
            return
        
        logger.info("Stopping background monitor...")
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # Save final state
        await self._save_state()
        logger.info("Background monitor stopped")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.stop())
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # Signal handling not available (e.g., running in a thread)
            logger.debug("Signal handling not available in this context")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Monitor loop started")
        
        while self.running:
            try:
                await self._perform_check()
                await self._save_state()
                
                # Wait for next check interval
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.debug("Monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                # Continue monitoring even if there's an error
                await asyncio.sleep(min(self.check_interval, 30))  # Wait at least 30 seconds on error
    
    async def _perform_check(self):
        """Perform a single check for changes."""
        self.checks_performed += 1
        self.last_check = datetime.now()
        
        logger.debug(f"Performing check #{self.checks_performed}")
        
        try:
            changes = await self.detector.detect_changes()
            
            if changes:
                new_changes = [c for c in changes if c not in self.change_history]
                
                if new_changes:
                    self.changes_detected += len(new_changes)
                    self.change_history.extend(new_changes)
                    
                    logger.info(f"Detected {len(new_changes)} new configuration changes")
                    
                    # Notify callback if provided
                    if self.notification_callback:
                        try:
                            self.notification_callback(new_changes)
                        except Exception as e:
                            logger.error(f"Error in notification callback: {e}")
                    
                    # Auto-sync if enabled and safe
                    if self.auto_sync:
                        from mcp_manager.core.simple_manager import SimpleMCPManager
                        if SimpleMCPManager.is_sync_safe():
                            await self._auto_sync_changes(new_changes)
                        else:
                            logger.debug("Skipping auto-sync due to recent mcp-manager operations")
                    else:
                        logger.info("Auto-sync disabled - changes detected but not applied")
                        for change in new_changes:
                            logger.info(f"  {change}")
            
        except Exception as e:
            logger.error(f"Error during change detection: {e}")
    
    async def _auto_sync_changes(self, changes: List[DetectedChange]):
        """Automatically apply detected changes."""
        logger.info(f"Auto-syncing {len(changes)} changes...")
        
        success_count = 0
        error_count = 0
        
        for change in changes:
            try:
                logger.debug(f"Applying {change.change_type.value} for {change.server_name}")
                
                if change.change_type.value == 'server_added':
                    server_info = change.details.get('server_info', {})
                    await self.manager.add_server(
                        name=change.server_name,
                        command=server_info.get('command', ''),
                        args=server_info.get('args', []),
                        env=server_info.get('env', {}),
                        scope=server_info.get('scope', 'user'),
                        enabled=server_info.get('enabled', True)
                    )
                    
                elif change.change_type.value == 'server_removed':
                    await self.manager.remove_server(change.server_name)
                    
                elif change.change_type.value in ['server_enabled', 'server_disabled']:
                    enabled = change.change_type.value == 'server_enabled'
                    await self.manager._update_server_status(change.server_name, enabled)
                
                success_count += 1
                self.changes_synced += 1
                logger.info(f"✅ Applied {change.change_type.value} for {change.server_name}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Failed to apply {change.change_type.value} for {change.server_name}: {e}")
        
        logger.info(f"Auto-sync complete: {success_count} successful, {error_count} failed")
    
    async def _save_state(self):
        """Save monitor state to disk."""
        try:
            state = {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'last_check': self.last_check.isoformat() if self.last_check else None,
                'checks_performed': self.checks_performed,
                'changes_detected': self.changes_detected,
                'changes_synced': self.changes_synced,
                'check_interval': self.check_interval,
                'auto_sync': self.auto_sync,
                'running': self.running,
                'change_history': [change.to_dict() for change in self.change_history[-100:]]  # Keep last 100 changes
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.debug(f"Failed to save monitor state: {e}")
    
    def _load_state(self) -> Dict[str, Any]:
        """Load monitor state from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Failed to load monitor state: {e}")
        
        return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status."""
        uptime = None
        if self.start_time:
            uptime = datetime.now() - self.start_time
        
        return {
            'running': self.running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'uptime': str(uptime) if uptime else None,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'check_interval': self.check_interval,
            'auto_sync': self.auto_sync,
            'statistics': {
                'checks_performed': self.checks_performed,
                'changes_detected': self.changes_detected,
                'changes_synced': self.changes_synced,
            },
            'recent_changes': len(self.change_history)
        }
    
    def get_recent_changes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent detected changes."""
        recent = self.change_history[-limit:] if self.change_history else []
        return [change.to_dict() for change in recent]
    
    async def force_check(self) -> List[DetectedChange]:
        """Force an immediate check for changes."""
        logger.info("Forcing immediate change detection...")
        
        old_history_len = len(self.change_history)
        await self._perform_check()
        
        # Return new changes found
        new_changes = self.change_history[old_history_len:]
        return new_changes


class MonitorDaemon:
    """Daemon wrapper for the background monitor."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.monitor: Optional[BackgroundMonitor] = None
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load daemon configuration."""
        default_config = {
            'check_interval': 60,
            'auto_sync': False,
            'log_level': 'INFO',
            'max_history': 1000
        }
        
        if self.config_file and Path(self.config_file).exists():
            try:
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.warning(f"Failed to load config file {self.config_file}: {e}")
        
        return default_config
    
    async def start_daemon(self):
        """Start the monitor as a daemon."""
        logger.info("Starting MCP Manager background monitor daemon")
        
        # Setup logging based on configuration
        logging.getLogger().setLevel(self.config.get('log_level', 'INFO'))
        
        # Create and start monitor
        self.monitor = BackgroundMonitor(
            check_interval=self.config.get('check_interval', 60),
            auto_sync=self.config.get('auto_sync', False),
            notification_callback=self._notification_handler
        )
        
        try:
            await self.monitor.start()
        except KeyboardInterrupt:
            logger.info("Daemon interrupted by user")
        finally:
            if self.monitor:
                await self.monitor.stop()
    
    def _notification_handler(self, changes: List[DetectedChange]):
        """Handle change notifications."""
        logger.info(f"🔔 Configuration changes detected: {len(changes)} changes")
        
        for change in changes:
            logger.info(f"  • {change}")
        
        # Could implement additional notification methods here:
        # - Desktop notifications
        # - Email alerts
        # - Webhook calls
        # - Log file entries
    
    def get_status(self) -> Dict[str, Any]:
        """Get daemon status."""
        if self.monitor:
            return self.monitor.get_status()
        
        return {
            'running': False,
            'error': 'Monitor not initialized'
        }


async def main():
    """Main entry point for the background monitor daemon."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Manager Background Monitor")
    parser.add_argument(
        "--config", 
        help="Configuration file path"
    )
    parser.add_argument(
        "--interval", 
        type=int, 
        default=60, 
        help="Check interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--auto-sync", 
        action="store_true", 
        help="Automatically apply detected changes"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    )
    
    # Create and start daemon
    daemon = MonitorDaemon(args.config)
    daemon.config.update({
        'check_interval': args.interval,
        'auto_sync': args.auto_sync,
        'log_level': 'DEBUG' if args.verbose else 'INFO'
    })
    
    await daemon.start_daemon()


if __name__ == "__main__":
    asyncio.run(main())