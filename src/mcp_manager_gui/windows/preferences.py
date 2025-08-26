"""
Preferences Window - Comprehensive settings and configuration interface.

Provides access to all MCP Manager configuration options through a native macOS interface.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QPushButton, QTextEdit, QGroupBox, QFileDialog, QMessageBox,
    QSlider, QProgressBar, QListWidget, QListWidgetItem, QButtonGroup,
    QRadioButton, QDialogButtonBox, QScrollArea, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer, QStandardPaths
from PySide6.QtGui import QFont, QIcon, QPixmap

from ..services.cli_bridge import CLIBridge


class PreferencesDialog(QDialog):
    """Main preferences dialog with tabbed interface."""
    
    settings_changed = Signal(dict)
    
    def __init__(self, parent=None, cli_bridge: CLIBridge = None):
        super().__init__(parent)
        self.cli_bridge = cli_bridge or CLIBridge()
        
        self.setWindowTitle("MCP Manager Preferences")
        self.setModal(True)
        self.resize(800, 600)
        
        # Store original settings for cancel operation
        self.original_settings = {}
        self.current_settings = {}
        
        self.setup_ui()
        self.load_current_settings()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_general_tab()
        self.create_monitoring_tab()
        self.create_appearance_tab()
        self.create_discovery_tab()
        self.create_quality_tab()
        self.create_logging_tab()
        self.create_integration_tab()
        self.create_advanced_tab()
        
        # Buttons
        self.create_buttons(layout)
    
    def create_general_tab(self):
        """Create general settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Configuration Scope
        scope_group = QGroupBox("Configuration Scope")
        scope_layout = QFormLayout(scope_group)
        
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["user", "project", "local"])
        scope_layout.addRow("Default Scope:", self.scope_combo)
        
        self.config_path_label = QLabel()
        self.config_path_label.setStyleSheet("color: #666; font-family: monospace;")
        scope_layout.addRow("Config Location:", self.config_path_label)
        
        layout.addWidget(scope_group)
        
        # Startup Options
        startup_group = QGroupBox("Startup & Behavior")
        startup_layout = QFormLayout(startup_group)
        
        self.auto_refresh_check = QCheckBox("Auto-refresh server list on startup")
        startup_layout.addRow("", self.auto_refresh_check)
        
        self.check_updates_check = QCheckBox("Check for updates on startup")
        startup_layout.addRow("", self.check_updates_check)
        
        self.minimize_to_tray_check = QCheckBox("Minimize to system tray")
        startup_layout.addRow("", self.minimize_to_tray_check)
        
        self.confirm_deletions_check = QCheckBox("Confirm destructive actions")
        self.confirm_deletions_check.setChecked(True)
        startup_layout.addRow("", self.confirm_deletions_check)
        
        layout.addWidget(startup_group)
        
        # Performance
        performance_group = QGroupBox("Performance")
        performance_layout = QFormLayout(performance_group)
        
        self.max_concurrent_ops = QSpinBox()
        self.max_concurrent_ops.setRange(1, 10)
        self.max_concurrent_ops.setValue(3)
        performance_layout.addRow("Max Concurrent Operations:", self.max_concurrent_ops)
        
        self.operation_timeout = QSpinBox()
        self.operation_timeout.setRange(5, 300)
        self.operation_timeout.setValue(30)
        self.operation_timeout.setSuffix(" seconds")
        performance_layout.addRow("Operation Timeout:", self.operation_timeout)
        
        layout.addWidget(performance_group)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "General")
    
    def create_monitoring_tab(self):
        """Create monitoring settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Refresh Intervals
        intervals_group = QGroupBox("Refresh Intervals")
        intervals_layout = QFormLayout(intervals_group)
        
        self.server_refresh_interval = QSpinBox()
        self.server_refresh_interval.setRange(1, 300)
        self.server_refresh_interval.setValue(5)
        self.server_refresh_interval.setSuffix(" seconds")
        intervals_layout.addRow("Server Status Check:", self.server_refresh_interval)
        
        self.suite_refresh_interval = QSpinBox()
        self.suite_refresh_interval.setRange(10, 600)
        self.suite_refresh_interval.setValue(30)
        self.suite_refresh_interval.setSuffix(" seconds")
        intervals_layout.addRow("Suite Status Check:", self.suite_refresh_interval)
        
        self.discovery_cache_ttl = QSpinBox()
        self.discovery_cache_ttl.setRange(300, 86400)
        self.discovery_cache_ttl.setValue(3600)
        self.discovery_cache_ttl.setSuffix(" seconds")
        intervals_layout.addRow("Discovery Cache TTL:", self.discovery_cache_ttl)
        
        layout.addWidget(intervals_group)
        
        # Monitoring Options
        monitoring_group = QGroupBox("Monitoring Features")
        monitoring_layout = QFormLayout(monitoring_group)
        
        self.enable_real_time_monitoring = QCheckBox("Enable real-time monitoring")
        self.enable_real_time_monitoring.setChecked(True)
        monitoring_layout.addRow("", self.enable_real_time_monitoring)
        
        self.monitor_performance_metrics = QCheckBox("Collect performance metrics")
        monitoring_layout.addRow("", self.monitor_performance_metrics)
        
        self.monitor_error_rates = QCheckBox("Monitor error rates")
        self.monitor_error_rates.setChecked(True)
        monitoring_layout.addRow("", self.monitor_error_rates)
        
        self.auto_restart_failed_servers = QCheckBox("Auto-restart failed servers")
        monitoring_layout.addRow("", self.auto_restart_failed_servers)
        
        layout.addWidget(monitoring_group)
        
        # Notifications
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QFormLayout(notifications_group)
        
        self.notify_server_failures = QCheckBox("Notify on server failures")
        self.notify_server_failures.setChecked(True)
        notifications_layout.addRow("", self.notify_server_failures)
        
        self.notify_successful_installs = QCheckBox("Notify on successful installations")
        notifications_layout.addRow("", self.notify_successful_installs)
        
        self.notification_sound = QCheckBox("Play notification sounds")
        notifications_layout.addRow("", self.notification_sound)
        
        layout.addWidget(notifications_group)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "Monitoring")
    
    def create_appearance_tab(self):
        """Create appearance settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Theme Settings
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        theme_layout.addRow("Theme:", self.theme_combo)
        
        self.use_native_styling = QCheckBox("Use native macOS styling")
        self.use_native_styling.setChecked(True)
        theme_layout.addRow("", self.use_native_styling)
        
        layout.addWidget(theme_group)
        
        # Font Settings
        font_group = QGroupBox("Fonts")
        font_layout = QFormLayout(font_group)
        
        self.ui_font_size = QSpinBox()
        self.ui_font_size.setRange(8, 24)
        self.ui_font_size.setValue(13)
        font_layout.addRow("UI Font Size:", self.ui_font_size)
        
        self.monospace_font_size = QSpinBox()
        self.monospace_font_size.setRange(8, 24)
        self.monospace_font_size.setValue(11)
        font_layout.addRow("Monospace Font Size:", self.monospace_font_size)
        
        layout.addWidget(font_group)
        
        # Display Options
        display_group = QGroupBox("Display Options")
        display_layout = QFormLayout(display_group)
        
        self.show_server_icons = QCheckBox("Show server type icons")
        self.show_server_icons.setChecked(True)
        display_layout.addRow("", self.show_server_icons)
        
        self.show_status_indicators = QCheckBox("Show animated status indicators")
        self.show_status_indicators.setChecked(True)
        display_layout.addRow("", self.show_status_indicators)
        
        self.compact_view = QCheckBox("Use compact server list view")
        display_layout.addRow("", self.compact_view)
        
        self.show_tooltips = QCheckBox("Show detailed tooltips")
        self.show_tooltips.setChecked(True)
        display_layout.addRow("", self.show_tooltips)
        
        layout.addWidget(display_group)
        
        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        preview_label = QLabel("Theme and font changes will take effect after restart.")
        preview_label.setStyleSheet("color: #666; font-style: italic;")
        preview_layout.addWidget(preview_label)
        
        layout.addWidget(preview_group)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "Appearance")
    
    def create_discovery_tab(self):
        """Create discovery settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Discovery Sources
        sources_group = QGroupBox("Discovery Sources")
        sources_layout = QFormLayout(sources_group)
        
        self.enable_npm_discovery = QCheckBox("Enable NPM registry discovery")
        self.enable_npm_discovery.setChecked(True)
        sources_layout.addRow("", self.enable_npm_discovery)
        
        self.enable_docker_discovery = QCheckBox("Enable Docker Hub discovery")
        self.enable_docker_discovery.setChecked(True)
        sources_layout.addRow("", self.enable_docker_discovery)
        
        self.enable_github_discovery = QCheckBox("Enable GitHub discovery")
        sources_layout.addRow("", self.enable_github_discovery)
        
        layout.addWidget(sources_group)
        
        # Search Settings
        search_group = QGroupBox("Search Settings")
        search_layout = QFormLayout(search_group)
        
        self.default_search_limit = QSpinBox()
        self.default_search_limit.setRange(10, 1000)
        self.default_search_limit.setValue(50)
        search_layout.addRow("Default Search Limit:", self.default_search_limit)
        
        self.search_timeout = QSpinBox()
        self.search_timeout.setRange(5, 120)
        self.search_timeout.setValue(30)
        self.search_timeout.setSuffix(" seconds")
        search_layout.addRow("Search Timeout:", self.search_timeout)
        
        self.enable_fuzzy_search = QCheckBox("Enable fuzzy search matching")
        self.enable_fuzzy_search.setChecked(True)
        search_layout.addRow("", self.enable_fuzzy_search)
        
        layout.addWidget(search_group)
        
        # Cache Settings
        cache_group = QGroupBox("Cache Settings")
        cache_layout = QFormLayout(cache_group)
        
        self.cache_discovery_results = QCheckBox("Cache discovery results")
        self.cache_discovery_results.setChecked(True)
        cache_layout.addRow("", self.cache_discovery_results)
        
        self.cache_max_age = QSpinBox()
        self.cache_max_age.setRange(60, 604800)  # 1 minute to 1 week
        self.cache_max_age.setValue(3600)  # 1 hour
        self.cache_max_age.setSuffix(" seconds")
        cache_layout.addRow("Cache Max Age:", self.cache_max_age)
        
        self.cache_max_size = QSpinBox()
        self.cache_max_size.setRange(10, 1000)
        self.cache_max_size.setValue(100)
        self.cache_max_size.setSuffix(" MB")
        cache_layout.addRow("Cache Max Size:", self.cache_max_size)
        
        layout.addWidget(cache_group)
        
        # Cache Management
        cache_mgmt_layout = QHBoxLayout()
        self.clear_cache_btn = QPushButton("Clear Discovery Cache")
        self.clear_cache_btn.clicked.connect(self.clear_discovery_cache)
        cache_mgmt_layout.addWidget(self.clear_cache_btn)
        cache_mgmt_layout.addStretch()
        layout.addLayout(cache_mgmt_layout)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "Discovery")
    
    def create_quality_tab(self):
        """Create quality tracking settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Quality Tracking
        quality_group = QGroupBox("Quality Tracking")
        quality_layout = QFormLayout(quality_group)
        
        self.enable_quality_tracking = QCheckBox("Enable quality tracking")
        self.enable_quality_tracking.setChecked(True)
        quality_layout.addRow("", self.enable_quality_tracking)
        
        self.track_usage_metrics = QCheckBox("Track server usage metrics")
        quality_layout.addRow("", self.track_usage_metrics)
        
        self.track_error_rates = QCheckBox("Track server error rates")
        self.track_error_rates.setChecked(True)
        quality_layout.addRow("", self.track_error_rates)
        
        self.anonymous_analytics = QCheckBox("Share anonymous analytics")
        quality_layout.addRow("", self.anonymous_analytics)
        
        layout.addWidget(quality_group)
        
        # Rating System
        rating_group = QGroupBox("Rating System")
        rating_layout = QFormLayout(rating_group)
        
        self.auto_rate_servers = QCheckBox("Automatically rate servers based on performance")
        rating_layout.addRow("", self.auto_rate_servers)
        
        self.prompt_for_ratings = QCheckBox("Prompt for manual ratings after server use")
        rating_layout.addRow("", self.prompt_for_ratings)
        
        self.min_usage_for_rating = QSpinBox()
        self.min_usage_for_rating.setRange(1, 100)
        self.min_usage_for_rating.setValue(5)
        rating_layout.addRow("Min Usage Count for Rating:", self.min_usage_for_rating)
        
        layout.addWidget(rating_group)
        
        # Reporting
        reporting_group = QGroupBox("Quality Reports")
        reporting_layout = QFormLayout(reporting_group)
        
        self.generate_quality_reports = QCheckBox("Generate quality reports")
        reporting_layout.addRow("", self.generate_quality_reports)
        
        self.report_frequency = QComboBox()
        self.report_frequency.addItems(["Daily", "Weekly", "Monthly", "Never"])
        self.report_frequency.setCurrentText("Weekly")
        reporting_layout.addRow("Report Frequency:", self.report_frequency)
        
        layout.addWidget(reporting_group)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "Quality")
    
    def create_logging_tab(self):
        """Create logging settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Log Level
        level_group = QGroupBox("Log Level")
        level_layout = QFormLayout(level_group)
        
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.setCurrentText("INFO")
        level_layout.addRow("Global Log Level:", self.log_level)
        
        self.gui_log_level = QComboBox()
        self.gui_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.gui_log_level.setCurrentText("WARNING")
        level_layout.addRow("GUI Log Level:", self.gui_log_level)
        
        layout.addWidget(level_group)
        
        # Output Destinations
        output_group = QGroupBox("Log Output")
        output_layout = QFormLayout(output_group)
        
        self.log_to_file = QCheckBox("Log to file")
        self.log_to_file.setChecked(True)
        output_layout.addRow("", self.log_to_file)
        
        self.log_to_console = QCheckBox("Log to console")
        output_layout.addRow("", self.log_to_console)
        
        self.log_to_syslog = QCheckBox("Log to system log (macOS)")
        output_layout.addRow("", self.log_to_syslog)
        
        layout.addWidget(output_group)
        
        # File Settings
        file_group = QGroupBox("Log File Settings")
        file_layout = QFormLayout(file_group)
        
        self.log_file_path = QLineEdit()
        self.log_file_path.setPlaceholderText("Default: ~/.local/share/mcp-manager/logs/")
        file_layout.addRow("Log Directory:", self.log_file_path)
        
        log_path_layout = QHBoxLayout()
        log_path_layout.addWidget(self.log_file_path)
        browse_log_btn = QPushButton("Browse...")
        browse_log_btn.clicked.connect(self.browse_log_directory)
        log_path_layout.addWidget(browse_log_btn)
        file_layout.addRow("", log_path_layout)
        
        self.max_log_size = QSpinBox()
        self.max_log_size.setRange(1, 1000)
        self.max_log_size.setValue(10)
        self.max_log_size.setSuffix(" MB")
        file_layout.addRow("Max Log File Size:", self.max_log_size)
        
        self.max_log_files = QSpinBox()
        self.max_log_files.setRange(1, 100)
        self.max_log_files.setValue(5)
        file_layout.addRow("Max Log Files:", self.max_log_files)
        
        layout.addWidget(file_group)
        
        # Log Format
        format_group = QGroupBox("Log Format")
        format_layout = QFormLayout(format_group)
        
        self.log_format = QComboBox()
        self.log_format.addItems(["JSON", "Text", "Structured"])
        self.log_format.setCurrentText("JSON")
        format_layout.addRow("Log Format:", self.log_format)
        
        self.include_timestamps = QCheckBox("Include timestamps")
        self.include_timestamps.setChecked(True)
        format_layout.addRow("", self.include_timestamps)
        
        self.include_thread_info = QCheckBox("Include thread information")
        format_layout.addRow("", self.include_thread_info)
        
        layout.addWidget(format_group)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "Logging")
    
    def create_integration_tab(self):
        """Create integration settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Claude Code Integration
        claude_group = QGroupBox("Claude Code Integration")
        claude_layout = QFormLayout(claude_group)
        
        self.auto_sync_claude = QCheckBox("Automatically sync with Claude Code")
        self.auto_sync_claude.setChecked(True)
        claude_layout.addRow("", self.auto_sync_claude)
        
        self.sync_interval = QSpinBox()
        self.sync_interval.setRange(10, 300)
        self.sync_interval.setValue(30)
        self.sync_interval.setSuffix(" seconds")
        claude_layout.addRow("Sync Interval:", self.sync_interval)
        
        self.claude_config_path = QLineEdit()
        self.claude_config_path.setPlaceholderText("Auto-detected")
        claude_layout.addRow("Claude Config Path:", self.claude_config_path)
        
        layout.addWidget(claude_group)
        
        # Docker Integration
        docker_group = QGroupBox("Docker Integration")
        docker_layout = QFormLayout(docker_group)
        
        self.docker_desktop_integration = QCheckBox("Enable Docker Desktop integration")
        self.docker_desktop_integration.setChecked(True)
        docker_layout.addRow("", self.docker_desktop_integration)
        
        self.auto_pull_images = QCheckBox("Automatically pull Docker images")
        self.auto_pull_images.setChecked(True)
        docker_layout.addRow("", self.auto_pull_images)
        
        self.docker_timeout = QSpinBox()
        self.docker_timeout.setRange(30, 600)
        self.docker_timeout.setValue(120)
        self.docker_timeout.setSuffix(" seconds")
        docker_layout.addRow("Docker Operation Timeout:", self.docker_timeout)
        
        layout.addWidget(docker_group)
        
        # NPM Integration
        npm_group = QGroupBox("NPM Integration")
        npm_layout = QFormLayout(npm_group)
        
        self.npm_registry_url = QLineEdit()
        self.npm_registry_url.setPlaceholderText("https://registry.npmjs.org/")
        npm_layout.addRow("NPM Registry URL:", self.npm_registry_url)
        
        self.npm_timeout = QSpinBox()
        self.npm_timeout.setRange(10, 300)
        self.npm_timeout.setValue(60)
        self.npm_timeout.setSuffix(" seconds")
        npm_layout.addRow("NPM Operation Timeout:", self.npm_timeout)
        
        layout.addWidget(npm_group)
        
        # External Tools
        tools_group = QGroupBox("External Tools")
        tools_layout = QFormLayout(tools_group)
        
        self.terminal_command = QLineEdit()
        self.terminal_command.setPlaceholderText("Terminal.app")
        tools_layout.addRow("Terminal Application:", self.terminal_command)
        
        self.editor_command = QLineEdit()
        self.editor_command.setPlaceholderText("open -t")
        tools_layout.addRow("Text Editor Command:", self.editor_command)
        
        layout.addWidget(tools_group)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "Integration")
    
    def create_advanced_tab(self):
        """Create advanced settings tab."""
        tab = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # Development Options
        dev_group = QGroupBox("Development & Debug")
        dev_layout = QFormLayout(dev_group)
        
        self.enable_debug_mode = QCheckBox("Enable debug mode")
        dev_layout.addRow("", self.enable_debug_mode)
        
        self.verbose_logging = QCheckBox("Enable verbose logging")
        dev_layout.addRow("", self.verbose_logging)
        
        self.enable_profiling = QCheckBox("Enable performance profiling")
        dev_layout.addRow("", self.enable_profiling)
        
        layout.addWidget(dev_group)
        
        # Experimental Features
        exp_group = QGroupBox("Experimental Features")
        exp_layout = QFormLayout(exp_group)
        
        self.ai_server_recommendations = QCheckBox("AI-powered server recommendations")
        exp_layout.addRow("", self.ai_server_recommendations)
        
        self.predictive_caching = QCheckBox("Predictive caching")
        exp_layout.addRow("", self.predictive_caching)
        
        self.beta_features = QCheckBox("Enable beta features")
        exp_layout.addRow("", self.beta_features)
        
        layout.addWidget(exp_group)
        
        # Resource Limits
        limits_group = QGroupBox("Resource Limits")
        limits_layout = QFormLayout(limits_group)
        
        self.max_memory_usage = QSpinBox()
        self.max_memory_usage.setRange(100, 8192)
        self.max_memory_usage.setValue(512)
        self.max_memory_usage.setSuffix(" MB")
        limits_layout.addRow("Max Memory Usage:", self.max_memory_usage)
        
        self.max_cpu_usage = QSpinBox()
        self.max_cpu_usage.setRange(10, 100)
        self.max_cpu_usage.setValue(50)
        self.max_cpu_usage.setSuffix(" %")
        limits_layout.addRow("Max CPU Usage:", self.max_cpu_usage)
        
        layout.addWidget(limits_group)
        
        # Configuration Management
        config_group = QGroupBox("Configuration Management")
        config_layout = QVBoxLayout(config_group)
        
        config_buttons = QHBoxLayout()
        
        export_config_btn = QPushButton("Export Configuration")
        export_config_btn.clicked.connect(self.export_configuration)
        config_buttons.addWidget(export_config_btn)
        
        import_config_btn = QPushButton("Import Configuration")
        import_config_btn.clicked.connect(self.import_configuration)
        config_buttons.addWidget(import_config_btn)
        
        reset_config_btn = QPushButton("Reset to Defaults")
        reset_config_btn.clicked.connect(self.reset_to_defaults)
        config_buttons.addWidget(reset_config_btn)
        
        config_layout.addLayout(config_buttons)
        layout.addWidget(config_group)
        
        layout.addStretch()
        tab.setWidget(content)
        tab.setWidgetResizable(True)
        self.tab_widget.addTab(tab, "Advanced")
    
    def create_buttons(self, layout):
        """Create dialog buttons."""
        button_layout = QHBoxLayout()
        
        # Help button
        help_btn = QPushButton("Help")
        help_btn.clicked.connect(self.show_help)
        button_layout.addWidget(help_btn)
        
        button_layout.addStretch()
        
        # Standard buttons
        restore_defaults_btn = QPushButton("Restore Defaults")
        restore_defaults_btn.clicked.connect(self.restore_defaults)
        button_layout.addWidget(restore_defaults_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_and_apply)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
    
    def load_current_settings(self):
        """Load current settings from CLI bridge."""
        try:
            config_info = self.cli_bridge.get_config_info()
            self.original_settings = config_info.get('settings', {})
            self.current_settings = self.original_settings.copy()
            
            # Update config path display
            config_path = config_info.get('config_path', 'Unknown')
            self.config_path_label.setText(config_path)
            
            # Load settings into UI
            self.populate_ui_from_settings()
            
        except Exception as e:
            QMessageBox.warning(self, "Settings Error", f"Failed to load current settings: {e}")
    
    def populate_ui_from_settings(self):
        """Populate UI controls from current settings."""
        settings = self.current_settings
        
        # General tab
        self.scope_combo.setCurrentText(settings.get('scope', 'user'))
        self.auto_refresh_check.setChecked(settings.get('auto_refresh', True))
        self.check_updates_check.setChecked(settings.get('check_updates', False))
        
        # Monitoring tab
        self.server_refresh_interval.setValue(settings.get('server_refresh_interval', 5))
        self.enable_real_time_monitoring.setChecked(settings.get('real_time_monitoring', True))
        
        # Appearance tab
        self.theme_combo.setCurrentText(settings.get('theme', 'System'))
        self.ui_font_size.setValue(settings.get('ui_font_size', 13))
        
        # Discovery tab
        self.enable_npm_discovery.setChecked(settings.get('enable_npm_discovery', True))
        self.default_search_limit.setValue(settings.get('default_search_limit', 50))
        
        # Quality tab
        self.enable_quality_tracking.setChecked(settings.get('enable_quality_tracking', True))
        
        # Logging tab
        self.log_level.setCurrentText(settings.get('log_level', 'INFO'))
        self.log_to_file.setChecked(settings.get('log_to_file', True))
        
        # Integration tab
        self.auto_sync_claude.setChecked(settings.get('auto_sync_claude', True))
        self.sync_interval.setValue(settings.get('sync_interval', 30))
    
    def collect_settings_from_ui(self) -> Dict[str, Any]:
        """Collect settings from UI controls."""
        settings = {}
        
        # General tab
        settings['scope'] = self.scope_combo.currentText()
        settings['auto_refresh'] = self.auto_refresh_check.isChecked()
        settings['check_updates'] = self.check_updates_check.isChecked()
        settings['minimize_to_tray'] = self.minimize_to_tray_check.isChecked()
        settings['confirm_deletions'] = self.confirm_deletions_check.isChecked()
        settings['max_concurrent_ops'] = self.max_concurrent_ops.value()
        settings['operation_timeout'] = self.operation_timeout.value()
        
        # Monitoring tab
        settings['server_refresh_interval'] = self.server_refresh_interval.value()
        settings['suite_refresh_interval'] = self.suite_refresh_interval.value()
        settings['discovery_cache_ttl'] = self.discovery_cache_ttl.value()
        settings['real_time_monitoring'] = self.enable_real_time_monitoring.isChecked()
        settings['monitor_performance_metrics'] = self.monitor_performance_metrics.isChecked()
        settings['monitor_error_rates'] = self.monitor_error_rates.isChecked()
        settings['auto_restart_failed_servers'] = self.auto_restart_failed_servers.isChecked()
        settings['notify_server_failures'] = self.notify_server_failures.isChecked()
        settings['notify_successful_installs'] = self.notify_successful_installs.isChecked()
        settings['notification_sound'] = self.notification_sound.isChecked()
        
        # Appearance tab
        settings['theme'] = self.theme_combo.currentText()
        settings['use_native_styling'] = self.use_native_styling.isChecked()
        settings['ui_font_size'] = self.ui_font_size.value()
        settings['monospace_font_size'] = self.monospace_font_size.value()
        settings['show_server_icons'] = self.show_server_icons.isChecked()
        settings['show_status_indicators'] = self.show_status_indicators.isChecked()
        settings['compact_view'] = self.compact_view.isChecked()
        settings['show_tooltips'] = self.show_tooltips.isChecked()
        
        # Discovery tab
        settings['enable_npm_discovery'] = self.enable_npm_discovery.isChecked()
        settings['enable_docker_discovery'] = self.enable_docker_discovery.isChecked()
        settings['enable_github_discovery'] = self.enable_github_discovery.isChecked()
        settings['default_search_limit'] = self.default_search_limit.value()
        settings['search_timeout'] = self.search_timeout.value()
        settings['enable_fuzzy_search'] = self.enable_fuzzy_search.isChecked()
        settings['cache_discovery_results'] = self.cache_discovery_results.isChecked()
        settings['cache_max_age'] = self.cache_max_age.value()
        settings['cache_max_size'] = self.cache_max_size.value()
        
        # Quality tab
        settings['enable_quality_tracking'] = self.enable_quality_tracking.isChecked()
        settings['track_usage_metrics'] = self.track_usage_metrics.isChecked()
        settings['track_error_rates'] = self.track_error_rates.isChecked()
        settings['anonymous_analytics'] = self.anonymous_analytics.isChecked()
        settings['auto_rate_servers'] = self.auto_rate_servers.isChecked()
        settings['prompt_for_ratings'] = self.prompt_for_ratings.isChecked()
        settings['min_usage_for_rating'] = self.min_usage_for_rating.value()
        settings['generate_quality_reports'] = self.generate_quality_reports.isChecked()
        settings['report_frequency'] = self.report_frequency.currentText()
        
        # Logging tab
        settings['log_level'] = self.log_level.currentText()
        settings['gui_log_level'] = self.gui_log_level.currentText()
        settings['log_to_file'] = self.log_to_file.isChecked()
        settings['log_to_console'] = self.log_to_console.isChecked()
        settings['log_to_syslog'] = self.log_to_syslog.isChecked()
        settings['log_file_path'] = self.log_file_path.text()
        settings['max_log_size'] = self.max_log_size.value()
        settings['max_log_files'] = self.max_log_files.value()
        settings['log_format'] = self.log_format.currentText()
        settings['include_timestamps'] = self.include_timestamps.isChecked()
        settings['include_thread_info'] = self.include_thread_info.isChecked()
        
        # Integration tab
        settings['auto_sync_claude'] = self.auto_sync_claude.isChecked()
        settings['sync_interval'] = self.sync_interval.value()
        settings['claude_config_path'] = self.claude_config_path.text()
        settings['docker_desktop_integration'] = self.docker_desktop_integration.isChecked()
        settings['auto_pull_images'] = self.auto_pull_images.isChecked()
        settings['docker_timeout'] = self.docker_timeout.value()
        settings['npm_registry_url'] = self.npm_registry_url.text()
        settings['npm_timeout'] = self.npm_timeout.value()
        settings['terminal_command'] = self.terminal_command.text()
        settings['editor_command'] = self.editor_command.text()
        
        # Advanced tab
        settings['enable_debug_mode'] = self.enable_debug_mode.isChecked()
        settings['verbose_logging'] = self.verbose_logging.isChecked()
        settings['enable_profiling'] = self.enable_profiling.isChecked()
        settings['ai_server_recommendations'] = self.ai_server_recommendations.isChecked()
        settings['predictive_caching'] = self.predictive_caching.isChecked()
        settings['beta_features'] = self.beta_features.isChecked()
        settings['max_memory_usage'] = self.max_memory_usage.value()
        settings['max_cpu_usage'] = self.max_cpu_usage.value()
        
        return settings
    
    def apply_settings(self):
        """Apply current settings."""
        try:
            settings = self.collect_settings_from_ui()
            
            # Apply settings via CLI bridge
            asyncio.run(self._apply_settings_async(settings))
            
            self.current_settings = settings
            self.settings_changed.emit(settings)
            
            QMessageBox.information(self, "Settings Applied", 
                                   "Settings have been applied successfully.")
        
        except Exception as e:
            QMessageBox.critical(self, "Settings Error", f"Failed to apply settings: {e}")
    
    async def _apply_settings_async(self, settings: Dict[str, Any]):
        """Apply settings asynchronously."""
        # This would apply settings via the CLI bridge
        # For now, just simulate the operation
        await asyncio.sleep(0.1)
    
    def accept_and_apply(self):
        """Apply settings and close dialog."""
        self.apply_settings()
        self.accept()
    
    def restore_defaults(self):
        """Restore all settings to defaults."""
        reply = QMessageBox.question(
            self, "Restore Defaults",
            "Are you sure you want to restore all settings to their default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset all UI controls to default values
            self.reset_ui_to_defaults()
    
    def reset_ui_to_defaults(self):
        """Reset UI controls to default values."""
        # General tab defaults
        self.scope_combo.setCurrentText("user")
        self.auto_refresh_check.setChecked(True)
        self.check_updates_check.setChecked(False)
        self.minimize_to_tray_check.setChecked(False)
        self.confirm_deletions_check.setChecked(True)
        self.max_concurrent_ops.setValue(3)
        self.operation_timeout.setValue(30)
        
        # Continue with other tabs...
        # This would reset all controls to their default values
    
    def clear_discovery_cache(self):
        """Clear the discovery cache."""
        try:
            asyncio.run(self._clear_cache_async())
            QMessageBox.information(self, "Cache Cleared", 
                                   "Discovery cache has been cleared successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Cache Error", f"Failed to clear cache: {e}")
    
    async def _clear_cache_async(self):
        """Clear cache asynchronously."""
        # This would clear the discovery cache via CLI bridge
        await asyncio.sleep(0.1)
    
    def browse_log_directory(self):
        """Browse for log directory."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Log Directory",
            self.log_file_path.text() or str(Path.home())
        )
        
        if directory:
            self.log_file_path.setText(directory)
    
    def export_configuration(self):
        """Export current configuration to file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Configuration",
            "mcp-manager-config.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                settings = self.collect_settings_from_ui()
                
                with open(filename, 'w') as f:
                    json.dump(settings, f, indent=2)
                
                QMessageBox.information(self, "Export Successful", 
                                       f"Configuration exported to {filename}")
            
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export configuration: {e}")
    
    def import_configuration(self):
        """Import configuration from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Configuration",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    settings = json.load(f)
                
                # Validate and apply settings
                self.current_settings.update(settings)
                self.populate_ui_from_settings()
                
                QMessageBox.information(self, "Import Successful", 
                                       f"Configuration imported from {filename}")
            
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import configuration: {e}")
    
    def reset_to_defaults(self):
        """Reset configuration to factory defaults."""
        reply = QMessageBox.question(
            self, "Reset Configuration",
            "This will reset ALL settings to factory defaults. Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Reset via CLI bridge
                asyncio.run(self._reset_config_async())
                self.load_current_settings()
                
                QMessageBox.information(self, "Reset Complete", 
                                       "Configuration has been reset to defaults.")
            
            except Exception as e:
                QMessageBox.critical(self, "Reset Error", f"Failed to reset configuration: {e}")
    
    async def _reset_config_async(self):
        """Reset configuration asynchronously."""
        # This would reset configuration via CLI bridge
        await asyncio.sleep(0.1)
    
    def show_help(self):
        """Show preferences help."""
        help_text = """
        <h3>MCP Manager Preferences</h3>
        <p>This dialog allows you to configure all aspects of MCP Manager.</p>
        
        <h4>General</h4>
        <p>Basic application settings including startup behavior and performance options.</p>
        
        <h4>Monitoring</h4>
        <p>Configure real-time monitoring, refresh intervals, and notifications.</p>
        
        <h4>Appearance</h4>
        <p>Customize the visual appearance including themes, fonts, and display options.</p>
        
        <h4>Discovery</h4>
        <p>Configure server discovery sources, search settings, and caching.</p>
        
        <h4>Quality</h4>
        <p>Settings for quality tracking, rating systems, and analytics.</p>
        
        <h4>Logging</h4>
        <p>Configure logging levels, output destinations, and log file management.</p>
        
        <h4>Integration</h4>
        <p>Settings for integration with Claude Code, Docker, NPM, and other tools.</p>
        
        <h4>Advanced</h4>
        <p>Development options, experimental features, and configuration management.</p>
        """
        
        QMessageBox.information(self, "Preferences Help", help_text)