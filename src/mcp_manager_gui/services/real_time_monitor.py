"""
Real-time monitoring service for the MCP Manager GUI.

This service provides background monitoring capabilities that integrate with Qt's
event system to deliver real-time updates to GUI components without blocking
the user interface thread.
"""

import asyncio
import platform
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from PySide6.QtCore import QObject, QTimer, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication

from mcp_manager.core.models import Server, ServerStatus, ServerType
from mcp_manager.utils.logging import get_logger
from .cli_bridge import CLIBridge


logger = get_logger(__name__)


class MonitoringState(str, Enum):
    """Monitoring service states."""
    
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ServerMetrics:
    """Server performance metrics."""
    
    def __init__(self):
        self.response_time_ms: Optional[int] = None
        self.last_response_time: Optional[datetime] = None
        self.connection_status: str = "unknown"
        self.error_count: int = 0
        self.success_count: int = 0
        self.uptime_start: Optional[datetime] = None
        self.last_check: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.error_count + self.success_count
        if total == 0:
            return 0.0
        return self.success_count / total
    
    @property
    def uptime(self) -> Optional[timedelta]:
        """Calculate uptime."""
        if self.uptime_start:
            return datetime.now() - self.uptime_start
        return None


class MonitoringWorker(QThread):
    """Background worker thread for monitoring operations."""
    
    # Signals
    server_status_changed = Signal(str, str)  # server_name, status
    server_metrics_updated = Signal(str, dict)  # server_name, metrics
    monitoring_error = Signal(str, str)  # error_type, message
    
    def __init__(self, cli_bridge: CLIBridge, check_interval: int = 5000):
        super().__init__()
        self.cli_bridge = cli_bridge
        self.check_interval = check_interval  # milliseconds
        self.running = False
        self.servers_cache: Dict[str, Dict[str, Any]] = {}
        self.metrics_cache: Dict[str, ServerMetrics] = {}
    
    def run(self):
        """Main monitoring loop running in background thread."""
        self.running = True
        logger.info("Monitoring worker thread started")
        
        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while self.running:
                loop.run_until_complete(self._perform_monitoring_cycle())
                
                # Sleep with interruptible intervals
                sleep_time = self.check_interval / 1000  # Convert to seconds
                for _ in range(int(sleep_time * 10)):  # Check every 100ms
                    if not self.running:
                        break
                    self.msleep(100)
                    
        except Exception as e:
            logger.error(f"Error in monitoring worker: {e}")
            self.monitoring_error.emit("worker_error", str(e))
        finally:
            loop.close()
            logger.info("Monitoring worker thread stopped")
    
    async def _perform_monitoring_cycle(self):
        """Perform one complete monitoring cycle."""
        try:
            # Get current server list
            current_servers = await self.cli_bridge.get_servers()
            
            # Process each server
            for server_data in current_servers:
                server_name = server_data.get('name', 'unknown')
                await self._monitor_server(server_name, server_data)
            
            # Clean up metrics for removed servers
            current_names = {s.get('name') for s in current_servers}
            removed_servers = set(self.metrics_cache.keys()) - current_names
            for removed_name in removed_servers:
                del self.metrics_cache[removed_name]
                
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")
            self.monitoring_error.emit("monitoring_cycle", str(e))
    
    async def _monitor_server(self, server_name: str, server_data: Dict[str, Any]):
        """Monitor a specific server."""
        try:
            # Get or create metrics for this server
            if server_name not in self.metrics_cache:
                self.metrics_cache[server_name] = ServerMetrics()
            
            metrics = self.metrics_cache[server_name]
            metrics.last_check = datetime.now()
            
            # Check for status changes
            current_status = server_data.get('status', 'unknown')
            old_status = self.servers_cache.get(server_name, {}).get('status')
            
            if current_status != old_status:
                logger.debug(f"Server {server_name} status changed: {old_status} -> {current_status}")
                self.server_status_changed.emit(server_name, current_status)
            
            # Update server cache
            self.servers_cache[server_name] = server_data
            
            # Perform connection check if server is active
            if server_data.get('enabled', False):
                await self._check_server_connection(server_name, server_data, metrics)
            
            # Emit metrics update
            metrics_dict = {
                'response_time_ms': metrics.response_time_ms,
                'connection_status': metrics.connection_status,
                'error_count': metrics.error_count,
                'success_count': metrics.success_count,
                'success_rate': metrics.success_rate,
                'uptime': str(metrics.uptime) if metrics.uptime else None,
                'last_check': metrics.last_check.isoformat() if metrics.last_check else None
            }
            self.server_metrics_updated.emit(server_name, metrics_dict)
            
        except Exception as e:
            logger.error(f"Error monitoring server {server_name}: {e}")
            self.monitoring_error.emit("server_monitoring", f"{server_name}: {e}")
    
    async def _check_server_connection(self, server_name: str, server_data: Dict[str, Any], metrics: ServerMetrics):
        """Check server connection and update metrics."""
        start_time = datetime.now()
        
        try:
            # Get detailed server information (this tests connectivity)
            details = await self.cli_bridge.get_server_details(server_name)
            
            # Calculate response time
            end_time = datetime.now()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            if details:
                metrics.response_time_ms = response_time
                metrics.last_response_time = end_time
                metrics.connection_status = "connected"
                metrics.success_count += 1
                
                # Set uptime start if this is first successful connection
                if metrics.uptime_start is None:
                    metrics.uptime_start = start_time
            else:
                metrics.connection_status = "failed"
                metrics.error_count += 1
                metrics.uptime_start = None
                
        except Exception as e:
            metrics.connection_status = "error"
            metrics.error_count += 1
            metrics.uptime_start = None
            logger.debug(f"Connection check failed for {server_name}: {e}")
    
    def stop(self):
        """Stop the monitoring worker."""
        self.running = False


class RealTimeMonitor(QObject):
    """Real-time monitoring service for MCP Manager GUI."""
    
    # Signals for UI updates
    server_added = Signal(dict)  # server_data
    server_removed = Signal(str)  # server_name
    server_status_changed = Signal(str, str)  # server_name, new_status
    server_metrics_updated = Signal(str, dict)  # server_name, metrics
    monitoring_state_changed = Signal(str)  # new_state
    error_detected = Signal(str, str)  # error_type, message
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self.cli_bridge = CLIBridge()
        self.state = MonitoringState.STOPPED
        self.check_interval = 5000  # 5 seconds default
        self.worker: Optional[MonitoringWorker] = None
        
        # UI update timer (separate from worker thread)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui_state)
        
        # Statistics
        self.start_time: Optional[datetime] = None
        self.total_checks = 0
        self.errors_count = 0
        self.last_error: Optional[str] = None
        
        # Server tracking
        self.monitored_servers: Dict[str, Dict[str, Any]] = {}
        self.server_metrics: Dict[str, Dict[str, Any]] = {}
        
        # macOS specific handling
        self._setup_macos_lifecycle()
    
    def _setup_macos_lifecycle(self):
        """Setup macOS app lifecycle event handling."""
        if platform.system() == "Darwin":
            app = QApplication.instance()
            if app:
                # Handle app becoming active/inactive
                app.applicationStateChanged.connect(self._handle_app_state_change)
    
    def _handle_app_state_change(self, state):
        """Handle macOS app state changes."""
        try:
            from PySide6.QtCore import Qt
            
            if state == Qt.ApplicationActive:
                if self.state == MonitoringState.RUNNING:
                    # Resume more frequent monitoring when app becomes active
                    self._adjust_monitoring_frequency(high_frequency=True)
            elif state == Qt.ApplicationInactive:
                if self.state == MonitoringState.RUNNING:
                    # Reduce monitoring frequency when app is inactive to save resources
                    self._adjust_monitoring_frequency(high_frequency=False)
                    
        except Exception as e:
            logger.debug(f"Error handling app state change: {e}")
    
    def _adjust_monitoring_frequency(self, high_frequency: bool):
        """Adjust monitoring frequency based on app state."""
        if self.worker:
            # High frequency: 5 seconds, Low frequency: 30 seconds
            new_interval = 5000 if high_frequency else 30000
            if self.worker.check_interval != new_interval:
                self.worker.check_interval = new_interval
                logger.debug(f"Adjusted monitoring interval to {new_interval}ms")
    
    def start_monitoring(self, check_interval: int = 5000) -> bool:
        """Start real-time monitoring."""
        if self.state != MonitoringState.STOPPED:
            logger.warning(f"Cannot start monitoring - current state: {self.state}")
            return False
        
        try:
            self._set_state(MonitoringState.STARTING)
            self.check_interval = check_interval
            self.start_time = datetime.now()
            self.total_checks = 0
            self.errors_count = 0
            
            # Create and start worker thread
            self.worker = MonitoringWorker(self.cli_bridge, check_interval)
            self._connect_worker_signals()
            self.worker.start()
            
            # Start UI update timer (every 1 second for responsive UI)
            self.ui_timer.start(1000)
            
            self._set_state(MonitoringState.RUNNING)
            logger.info(f"Real-time monitoring started with {check_interval}ms interval")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            self._set_state(MonitoringState.ERROR)
            self.last_error = str(e)
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop real-time monitoring."""
        if self.state not in [MonitoringState.RUNNING, MonitoringState.ERROR]:
            logger.warning(f"Cannot stop monitoring - current state: {self.state}")
            return False
        
        try:
            self._set_state(MonitoringState.STOPPING)
            
            # Stop UI timer
            self.ui_timer.stop()
            
            # Stop worker thread
            if self.worker:
                self.worker.stop()
                if not self.worker.wait(5000):  # Wait up to 5 seconds
                    logger.warning("Worker thread did not stop cleanly, terminating")
                    self.worker.terminate()
                    self.worker.wait()
                
                self.worker.deleteLater()
                self.worker = None
            
            self._set_state(MonitoringState.STOPPED)
            logger.info("Real-time monitoring stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop monitoring: {e}")
            self._set_state(MonitoringState.ERROR)
            self.last_error = str(e)
            return False
    
    def _connect_worker_signals(self):
        """Connect worker thread signals to local handlers."""
        if self.worker:
            self.worker.server_status_changed.connect(self._on_server_status_changed)
            self.worker.server_metrics_updated.connect(self._on_server_metrics_updated)
            self.worker.monitoring_error.connect(self._on_monitoring_error)
    
    @Slot(str, str)
    def _on_server_status_changed(self, server_name: str, status: str):
        """Handle server status change from worker."""
        logger.debug(f"Server status changed: {server_name} -> {status}")
        
        # Update local cache
        if server_name in self.monitored_servers:
            self.monitored_servers[server_name]['status'] = status
        
        # Emit signal for UI updates
        self.server_status_changed.emit(server_name, status)
    
    @Slot(str, dict)
    def _on_server_metrics_updated(self, server_name: str, metrics: Dict[str, Any]):
        """Handle server metrics update from worker."""
        # Update local cache
        self.server_metrics[server_name] = metrics
        
        # Emit signal for UI updates
        self.server_metrics_updated.emit(server_name, metrics)
    
    @pyqtSlot(str, str)
    def _on_monitoring_error(self, error_type: str, message: str):
        """Handle monitoring error from worker."""
        self.errors_count += 1
        self.last_error = f"{error_type}: {message}"
        
        logger.warning(f"Monitoring error - {error_type}: {message}")
        self.error_detected.emit(error_type, message)
    
    def _update_ui_state(self):
        """Update UI state periodically (called by timer)."""
        self.total_checks += 1
        
        # This runs in the main thread and can be used for
        # any UI-specific updates that don't come from the worker
    
    def _set_state(self, new_state: MonitoringState):
        """Set monitoring state and emit change signal."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.debug(f"Monitoring state changed: {old_state} -> {new_state}")
            self.monitoring_state_changed.emit(new_state.value)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        uptime = None
        if self.start_time and self.state == MonitoringState.RUNNING:
            uptime = datetime.now() - self.start_time
        
        return {
            'state': self.state.value,
            'running': self.state == MonitoringState.RUNNING,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'uptime': str(uptime) if uptime else None,
            'check_interval': self.check_interval,
            'total_checks': self.total_checks,
            'errors_count': self.errors_count,
            'last_error': self.last_error,
            'monitored_servers_count': len(self.monitored_servers),
            'worker_active': self.worker is not None and self.worker.isRunning()
        }
    
    def get_server_metrics(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific server."""
        return self.server_metrics.get(server_name)
    
    def get_all_server_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all monitored servers."""
        return self.server_metrics.copy()
    
    def force_refresh(self):
        """Force an immediate refresh of all monitored data."""
        if self.state == MonitoringState.RUNNING and self.worker:
            # The worker will pick up the refresh on its next cycle
            # We could implement a signal to trigger immediate refresh if needed
            logger.info("Monitoring refresh requested")
    
    def set_check_interval(self, interval_ms: int):
        """Change the monitoring check interval."""
        if interval_ms < 1000:  # Minimum 1 second
            interval_ms = 1000
        elif interval_ms > 300000:  # Maximum 5 minutes
            interval_ms = 300000
        
        self.check_interval = interval_ms
        
        if self.worker:
            self.worker.check_interval = interval_ms
            logger.info(f"Monitoring interval changed to {interval_ms}ms")
    
    def cleanup(self):
        """Clean up resources before destruction."""
        if self.state == MonitoringState.RUNNING:
            self.stop_monitoring()
        
        # Clean up timers
        if self.ui_timer.isActive():
            self.ui_timer.stop()