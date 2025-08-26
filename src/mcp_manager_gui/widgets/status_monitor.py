"""
Status Monitor Widget - Real-time dashboard for system status monitoring.

Provides comprehensive monitoring of MCP servers, system health, and
performance metrics with real-time updates and alerts.
"""

from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QFrame, QProgressBar, QScrollArea, QPushButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QTextEdit, QTabWidget, QSplitter
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSize
from PySide6.QtGui import QFont, QPalette, QColor, QPainter, QPixmap, QIcon

from ..services.cli_bridge import CLIBridge


class MetricsWorker(QThread):
    """Background worker for collecting system metrics."""
    
    metrics_updated = Signal(dict)
    server_events = Signal(list)
    
    def __init__(self, cli_bridge: CLIBridge):
        super().__init__()
        self.cli_bridge = cli_bridge
        self.should_monitor = True
        self.event_history = []
        
    def run(self):
        """Main monitoring loop."""
        while self.should_monitor:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Collect metrics
                metrics = loop.run_until_complete(self.collect_metrics())
                self.metrics_updated.emit(metrics)
                
                # Collect recent events
                events = loop.run_until_complete(self.collect_events())
                if events:
                    self.event_history.extend(events)
                    # Keep only last 100 events
                    self.event_history = self.event_history[-100:]
                    self.server_events.emit(self.event_history[-10:])  # Send last 10
                
                loop.close()
                
            except Exception as e:
                print(f"Metrics worker error: {e}")
            
            # Update every 2 seconds
            self.msleep(2000)
    
    def stop(self):
        """Stop the monitoring worker."""
        self.should_monitor = False
        self.quit()
        self.wait()
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect system metrics."""
        try:
            servers = await self.cli_bridge.get_servers()
            
            # Calculate server statistics
            total_servers = len(servers)
            connected_servers = len([s for s in servers if s.get('claude_status') == 'Connected'])
            failed_servers = len([s for s in servers if s.get('claude_status') == 'Failed'])
            disabled_servers = len([s for s in servers if s.get('claude_status') == 'Disabled'])
            
            # Server types distribution
            types_count = {}
            for server in servers:
                server_type = server.get('type', 'Custom')
                types_count[server_type] = types_count.get(server_type, 0) + 1
            
            return {
                'timestamp': datetime.now(),
                'total_servers': total_servers,
                'connected_servers': connected_servers,
                'failed_servers': failed_servers,
                'disabled_servers': disabled_servers,
                'unknown_servers': total_servers - connected_servers - failed_servers - disabled_servers,
                'types_distribution': types_count,
                'health_score': self.calculate_health_score(servers),
                'uptime_percentage': self.calculate_uptime(servers)
            }
            
        except Exception as e:
            return {
                'timestamp': datetime.now(),
                'error': str(e),
                'total_servers': 0,
                'connected_servers': 0,
                'failed_servers': 0,
                'disabled_servers': 0,
                'unknown_servers': 0,
                'types_distribution': {},
                'health_score': 0,
                'uptime_percentage': 0
            }
    
    async def collect_events(self) -> List[Dict[str, Any]]:
        """Collect recent server events."""
        # This would collect actual events from logs or monitoring
        # For now, return simulated events
        return []
    
    def calculate_health_score(self, servers: List[Dict[str, Any]]) -> float:
        """Calculate overall system health score (0-100)."""
        if not servers:
            return 0.0
        
        connected = len([s for s in servers if s.get('claude_status') == 'Connected'])
        total = len(servers)
        
        # Health score based on percentage of connected servers
        base_score = (connected / total) * 100 if total > 0 else 0
        
        # Penalize for failed servers
        failed = len([s for s in servers if s.get('claude_status') == 'Failed'])
        penalty = (failed / total) * 20 if total > 0 else 0
        
        return max(0, base_score - penalty)
    
    def calculate_uptime(self, servers: List[Dict[str, Any]]) -> float:
        """Calculate average uptime percentage."""
        if not servers:
            return 0.0
        
        # This would calculate from actual uptime data
        # For now, estimate based on status
        connected = len([s for s in servers if s.get('claude_status') == 'Connected'])
        total = len(servers)
        
        return (connected / total) * 100 if total > 0 else 0


class MetricCard(QFrame):
    """Individual metric display card."""
    
    def __init__(self, title: str, value: str, color: str = "#007AFF", icon: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.value_text = value
        self.color = color
        self.icon = icon
        
        self.setup_ui()
        self.apply_styling()
    
    def setup_ui(self):
        """Set up the metric card UI."""
        self.setFrameStyle(QFrame.Box)
        self.setFixedSize(160, 100)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Icon and title row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)
        
        if self.icon:
            icon_label = QLabel(self.icon)
            icon_font = QFont()
            icon_font.setPointSize(16)
            icon_label.setFont(icon_font)
            icon_label.setStyleSheet(f"QLabel {{ color: {self.color}; }}")
            header_layout.addWidget(icon_label)
        
        self.title_label = QLabel(self.title)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setWeight(QFont.Weight.Medium)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("QLabel { color: #8E8E93; }")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Value
        self.value_label = QLabel(self.value_text)
        value_font = QFont()
        value_font.setPointSize(24)
        value_font.setWeight(QFont.Weight.Bold)
        self.value_label.setFont(value_font)
        self.value_label.setStyleSheet(f"QLabel {{ color: {self.color}; }}")
        layout.addWidget(self.value_label)
        
        layout.addStretch()
    
    def update_value(self, value: str):
        """Update the displayed value."""
        self.value_text = value
        self.value_label.setText(value)
    
    def apply_styling(self):
        """Apply styling to the metric card."""
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E5EA;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #C7C7CC;
                background-color: #FBFBFD;
            }
        """)


class SystemHealthWidget(QWidget):
    """System health overview widget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the system health UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header
        header = QLabel("System Health")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setWeight(QFont.Weight.Bold)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Health score gauge
        self.setup_health_gauge(layout)
        
        # Status indicators
        self.setup_status_indicators(layout)
    
    def setup_health_gauge(self, parent_layout):
        """Set up the health score gauge."""
        gauge_frame = QFrame()
        gauge_frame.setFrameStyle(QFrame.Box)
        gauge_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        gauge_frame.setFixedHeight(100)
        
        gauge_layout = QVBoxLayout(gauge_frame)
        gauge_layout.setSpacing(4)
        
        # Health score label
        self.health_score_label = QLabel("Health Score: 0%")
        score_font = QFont()
        score_font.setPointSize(14)
        score_font.setWeight(QFont.Weight.Medium)
        self.health_score_label.setFont(score_font)
        gauge_layout.addWidget(self.health_score_label)
        
        # Progress bar
        self.health_progress = QProgressBar()
        self.health_progress.setRange(0, 100)
        self.health_progress.setValue(0)
        self.health_progress.setTextVisible(False)
        self.health_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #F2F2F7;
                height: 12px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF3B30, stop:0.5 #FF9500, stop:1 #34C759);
            }
        """)
        gauge_layout.addWidget(self.health_progress)
        
        # Status text
        self.health_status_label = QLabel("System starting up...")
        self.health_status_label.setStyleSheet("QLabel { color: #8E8E93; font-size: 11px; }")
        gauge_layout.addWidget(self.health_status_label)
        
        parent_layout.addWidget(gauge_frame)
    
    def setup_status_indicators(self, parent_layout):
        """Set up status indicators."""
        indicators_frame = QFrame()
        indicators_layout = QVBoxLayout(indicators_frame)
        indicators_layout.setSpacing(4)
        
        # Status items
        self.status_items = {}
        statuses = [
            ("Connected Servers", "●", "#34C759"),
            ("Failed Servers", "●", "#FF3B30"),
            ("Disabled Servers", "●", "#8E8E93"),
            ("Unknown Servers", "●", "#C7C7CC")
        ]
        
        for name, icon, color in statuses:
            item_layout = QHBoxLayout()
            
            icon_label = QLabel(icon)
            icon_label.setStyleSheet(f"QLabel {{ color: {color}; font-size: 16px; }}")
            item_layout.addWidget(icon_label)
            
            name_label = QLabel(name)
            name_label.setStyleSheet("QLabel { color: #3C3C43; font-size: 12px; }")
            item_layout.addWidget(name_label)
            
            item_layout.addStretch()
            
            count_label = QLabel("0")
            count_label.setStyleSheet("QLabel { color: #8E8E93; font-size: 12px; font-weight: bold; }")
            item_layout.addWidget(count_label)
            
            self.status_items[name] = count_label
            indicators_layout.addLayout(item_layout)
        
        parent_layout.addWidget(indicators_frame)
    
    def update_health(self, metrics: Dict[str, Any]):
        """Update health display with new metrics."""
        health_score = metrics.get('health_score', 0)
        self.health_score_label.setText(f"Health Score: {health_score:.1f}%")
        self.health_progress.setValue(int(health_score))
        
        # Update status text
        if health_score >= 90:
            status_text = "Excellent - All systems operational"
            color = "#34C759"
        elif health_score >= 70:
            status_text = "Good - Minor issues detected"
            color = "#FF9500"
        elif health_score >= 50:
            status_text = "Fair - Several issues need attention"
            color = "#FF9500"
        else:
            status_text = "Poor - Critical issues detected"
            color = "#FF3B30"
        
        self.health_status_label.setText(status_text)
        self.health_status_label.setStyleSheet(f"QLabel {{ color: {color}; font-size: 11px; font-weight: 500; }}")
        
        # Update status counts
        self.status_items["Connected Servers"].setText(str(metrics.get('connected_servers', 0)))
        self.status_items["Failed Servers"].setText(str(metrics.get('failed_servers', 0)))
        self.status_items["Disabled Servers"].setText(str(metrics.get('disabled_servers', 0)))
        self.status_items["Unknown Servers"].setText(str(metrics.get('unknown_servers', 0)))


class EventLogWidget(QWidget):
    """Event log display widget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the event log UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header with clear button
        header_layout = QHBoxLayout()
        
        header = QLabel("Recent Events")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setWeight(QFont.Weight.Bold)
        header.setFont(header_font)
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_events)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #F2F2F7;
                color: #8E8E93;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #E5E5EA;
            }
        """)
        header_layout.addWidget(clear_btn)
        
        layout.addLayout(header_layout)
        
        # Event log text area
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(1000)  # Limit to 1000 lines
        self.event_log.setStyleSheet("""
            QTextEdit {
                background-color: #1C1C1E;
                color: #FFFFFF;
                border: 1px solid #38383A;
                border-radius: 8px;
                font-family: Monaco, Menlo, Consolas, monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.event_log)
    
    def add_event(self, timestamp: datetime, level: str, message: str):
        """Add an event to the log."""
        time_str = timestamp.strftime("%H:%M:%S")
        
        # Color based on level
        if level == "ERROR":
            color = "#FF3B30"
        elif level == "WARNING":
            color = "#FF9500"
        elif level == "INFO":
            color = "#007AFF"
        else:
            color = "#FFFFFF"
        
        html_line = f'<span style="color: #8E8E93;">[{time_str}]</span> <span style="color: {color};">{level}</span>: {message}'
        self.event_log.append(html_line)
        
        # Auto-scroll to bottom
        scrollbar = self.event_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def add_events(self, events: List[Dict[str, Any]]):
        """Add multiple events to the log."""
        for event in events:
            self.add_event(
                event.get('timestamp', datetime.now()),
                event.get('level', 'INFO'),
                event.get('message', 'Unknown event')
            )
    
    def clear_events(self):
        """Clear all events from the log."""
        self.event_log.clear()


class StatusMonitor(QWidget):
    """Main status monitoring dashboard widget."""
    
    refresh_requested = Signal()  # Emitted when refresh is needed
    
    def __init__(self, cli_bridge: CLIBridge, parent=None):
        super().__init__(parent)
        self.cli_bridge = cli_bridge
        self.metrics_history = []
        
        self.setup_ui()
        self.setup_worker()
        self.apply_styling()
        
        # Add some initial events
        self.add_system_event("INFO", "Status monitor initialized")
    
    def setup_ui(self):
        """Set up the monitoring dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("System Status Monitor")
        header_font = QFont()
        header_font.setPointSize(20)
        header_font.setWeight(QFont.Weight.Bold)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Create tabs for different views
        self.tab_widget = QTabWidget()
        
        # Overview tab
        self.setup_overview_tab()
        self.tab_widget.addTab(self.overview_widget, "Overview")
        
        # Metrics tab
        self.setup_metrics_tab()
        self.tab_widget.addTab(self.metrics_widget, "Metrics")
        
        # Events tab
        self.setup_events_tab()
        self.tab_widget.addTab(self.events_widget, "Events")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.setup_status_bar(layout)
    
    def setup_overview_tab(self):
        """Set up the overview tab."""
        self.overview_widget = QWidget()
        layout = QHBoxLayout(self.overview_widget)
        layout.setSpacing(16)
        
        # Left side - Metric cards
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        
        # Metric cards grid
        cards_frame = QFrame()
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setSpacing(12)
        
        self.metric_cards = {}
        metrics = [
            ("Total Servers", "0", "#007AFF", "🖥"),
            ("Connected", "0", "#34C759", "✅"),
            ("Failed", "0", "#FF3B30", "❌"),
            ("Uptime", "0%", "#FF9500", "⏱")
        ]
        
        for i, (title, value, color, icon) in enumerate(metrics):
            card = MetricCard(title, value, color, icon)
            self.metric_cards[title] = card
            cards_layout.addWidget(card, i // 2, i % 2)
        
        left_layout.addWidget(cards_frame)
        left_layout.addStretch()
        
        layout.addWidget(left_frame)
        
        # Right side - System health
        self.system_health = SystemHealthWidget()
        layout.addWidget(self.system_health)
        
        # Set equal stretching
        layout.setStretch(0, 1)
        layout.setStretch(1, 1)
    
    def setup_metrics_tab(self):
        """Set up the metrics tab."""
        self.metrics_widget = QWidget()
        layout = QVBoxLayout(self.metrics_widget)
        
        # Metrics table
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(2)
        self.metrics_table.setHorizontalHeaderLabels(["Metric", "Value"])
        
        header = self.metrics_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        self.metrics_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #F2F2F7;
            }
            QHeaderView::section {
                background-color: #F2F2F7;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.metrics_table)
    
    def setup_events_tab(self):
        """Set up the events tab."""
        self.events_widget = EventLogWidget()
    
    def setup_status_bar(self, parent_layout):
        """Set up the status bar."""
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 8, 0, 0)
        
        self.last_update_label = QLabel("Last updated: Never")
        self.last_update_label.setStyleSheet("QLabel { color: #8E8E93; font-size: 12px; }")
        status_layout.addWidget(self.last_update_label)
        
        status_layout.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.manual_refresh)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #0056CC;
            }
        """)
        status_layout.addWidget(refresh_btn)
        
        parent_layout.addWidget(status_frame)
    
    def setup_worker(self):
        """Set up the metrics worker."""
        self.worker = MetricsWorker(self.cli_bridge)
        self.worker.metrics_updated.connect(self.update_metrics)
        self.worker.server_events.connect(self.handle_server_events)
        
        # Start monitoring
        self.worker.start()
    
    def update_metrics(self, metrics: Dict[str, Any]):
        """Update all metrics displays."""
        self.metrics_history.append(metrics)
        
        # Keep only last 100 metrics
        if len(self.metrics_history) > 100:
            self.metrics_history.pop(0)
        
        # Update metric cards
        self.metric_cards["Total Servers"].update_value(str(metrics.get('total_servers', 0)))
        self.metric_cards["Connected"].update_value(str(metrics.get('connected_servers', 0)))
        self.metric_cards["Failed"].update_value(str(metrics.get('failed_servers', 0)))
        self.metric_cards["Uptime"].update_value(f"{metrics.get('uptime_percentage', 0):.1f}%")
        
        # Update system health
        self.system_health.update_health(metrics)
        
        # Update metrics table
        self.update_metrics_table(metrics)
        
        # Update last update time
        self.last_update_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        
        # Log metrics update
        if 'error' not in metrics:
            self.add_system_event("INFO", f"Metrics updated - {metrics.get('connected_servers', 0)} servers connected")
        else:
            self.add_system_event("ERROR", f"Metrics update failed: {metrics.get('error', 'Unknown error')}")
    
    def update_metrics_table(self, metrics: Dict[str, Any]):
        """Update the metrics table."""
        # Clear existing rows
        self.metrics_table.setRowCount(0)
        
        # Add metrics rows
        metrics_to_show = [
            ("Total Servers", metrics.get('total_servers', 0)),
            ("Connected Servers", metrics.get('connected_servers', 0)),
            ("Failed Servers", metrics.get('failed_servers', 0)),
            ("Disabled Servers", metrics.get('disabled_servers', 0)),
            ("Unknown Status", metrics.get('unknown_servers', 0)),
            ("Health Score", f"{metrics.get('health_score', 0):.1f}%"),
            ("Uptime Percentage", f"{metrics.get('uptime_percentage', 0):.1f}%"),
        ]
        
        # Add server type distribution
        types_dist = metrics.get('types_distribution', {})
        for server_type, count in types_dist.items():
            metrics_to_show.append((f"{server_type} Servers", count))
        
        self.metrics_table.setRowCount(len(metrics_to_show))
        
        for i, (metric, value) in enumerate(metrics_to_show):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(metric))
            self.metrics_table.setItem(i, 1, QTableWidgetItem(str(value)))
    
    def handle_server_events(self, events: List[Dict[str, Any]]):
        """Handle server events from worker."""
        self.events_widget.add_events(events)
    
    def add_system_event(self, level: str, message: str):
        """Add a system event to the log."""
        self.events_widget.add_event(datetime.now(), level, message)
    
    def manual_refresh(self):
        """Handle manual refresh request."""
        self.add_system_event("INFO", "Manual refresh requested")
        self.refresh_requested.emit()
    
    def apply_styling(self):
        """Apply macOS styling."""
        self.setStyleSheet("""
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #F2F2F7;
            }
            
            QTabWidget::pane {
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                background-color: white;
            }
            
            QTabWidget::tab-bar {
                alignment: center;
            }
            
            QTabBar::tab {
                background-color: #F2F2F7;
                color: #3C3C43;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                color: #007AFF;
            }
            
            QTabBar::tab:hover {
                background-color: #E5E5EA;
            }
        """)
    
    def closeEvent(self, event):
        """Clean up when widget is closed."""
        if hasattr(self, 'worker'):
            self.worker.stop()
        event.accept()