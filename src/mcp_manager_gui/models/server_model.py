"""
Qt Data Models for MCP Server Management.

Provides Qt model/view architecture compatible models for displaying and
managing MCP servers in the GUI. Supports real-time updates, filtering,
sorting, and drag-and-drop operations.
"""

import asyncio
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, QObject, QPersistentModelIndex,
    Qt, QTimer, Signal, QMimeData
)
from PySide6.QtGui import QColor, QIcon, QPixmap

from mcp_manager.core.models import Server, ServerStatus, ServerType, ServerScope
from mcp_manager_gui.services.cli_bridge import CLIBridge


class ServerColumn(IntEnum):
    """Column indices for server table model."""
    NAME = 0
    TYPE = 1
    STATUS = 2
    SCOPE = 3
    DESCRIPTION = 4
    ENABLED = 5
    SUITES = 6
    LAST_UPDATED = 7
    ACTIONS = 8


class ServerDataRole(IntEnum):
    """Custom data roles for server model."""
    ServerObjectRole = Qt.UserRole + 1
    ServerNameRole = Qt.UserRole + 2
    ServerTypeRole = Qt.UserRole + 3
    ServerStatusRole = Qt.UserRole + 4
    ServerScopeRole = Qt.UserRole + 5
    ServerEnabledRole = Qt.UserRole + 6
    ServerSuitesRole = Qt.UserRole + 7
    ServerCommandRole = Qt.UserRole + 8
    ServerArgsRole = Qt.UserRole + 9
    ServerEnvRole = Qt.UserRole + 10
    ServerPidRole = Qt.UserRole + 11
    FilterRole = Qt.UserRole + 12
    SortRole = Qt.UserRole + 13


class ServerTableModel(QAbstractTableModel):
    """Table model for displaying MCP servers in a table view."""
    
    # Signals
    serverAdded = Signal(str)  # server_name
    serverRemoved = Signal(str)  # server_name
    serverModified = Signal(str)  # server_name
    serverStatusChanged = Signal(str, str)  # server_name, new_status
    dataRefreshed = Signal()
    
    def __init__(self, cli_bridge: CLIBridge, parent: Optional[QObject] = None):
        """Initialize the server table model."""
        super().__init__(parent)
        
        self._cli_bridge = cli_bridge
        self._servers: List[Dict[str, Any]] = []
        self._headers = [
            "Name", "Type", "Status", "Scope", "Description", 
            "Enabled", "Suites", "Last Updated", "Actions"
        ]
        
        # Filtering and sorting
        self._filter_text = ""
        self._filter_type: Optional[str] = None
        self._filter_status: Optional[str] = None
        self._filter_scope: Optional[str] = None
        self._filter_enabled: Optional[bool] = None
        
        # Auto-refresh settings
        self._auto_refresh_enabled = True
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_data)
        self._refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Icons cache
        self._status_icons: Dict[str, QIcon] = {}
        self._type_icons: Dict[str, QIcon] = {}
        
        # Initial data load
        self._load_initial_data()
    
    def _load_initial_data(self) -> None:
        """Load initial server data asynchronously."""
        asyncio.create_task(self._async_refresh_data())
    
    async def _async_refresh_data(self) -> None:
        """Refresh server data from the CLI bridge."""
        try:
            servers = await self._cli_bridge.get_servers()
            
            # Update model data
            self.beginResetModel()
            old_servers = {s.get('name', '') for s in self._servers}
            new_servers = {s.get('name', '') for s in servers}
            
            self._servers = servers
            self.endResetModel()
            
            # Emit signals for server changes
            added = new_servers - old_servers
            removed = old_servers - new_servers
            
            for server_name in added:
                self.serverAdded.emit(server_name)
            
            for server_name in removed:
                self.serverRemoved.emit(server_name)
            
            # Check for status changes
            for server in servers:
                server_name = server.get('name', '')
                if server_name in old_servers:
                    # Find old server for comparison
                    old_server = next(
                        (s for s in self._servers if s.get('name') == server_name), 
                        None
                    )
                    if old_server and old_server.get('status') != server.get('status'):
                        self.serverStatusChanged.emit(
                            server_name, 
                            server.get('status', 'unknown')
                        )
            
            self.dataRefreshed.emit()
            
        except Exception as e:
            print(f"Error refreshing server data: {e}")
    
    def _refresh_data(self) -> None:
        """Timer callback to refresh data."""
        if self._auto_refresh_enabled:
            asyncio.create_task(self._async_refresh_data())
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of servers (rows)."""
        if parent.isValid():
            return 0
        return len(self._get_filtered_servers())
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of columns."""
        if parent.isValid():
            return 0
        return len(self._headers)
    
    def headerData(
        self, 
        section: int, 
        orientation: Qt.Orientation, 
        role: int = Qt.DisplayRole
    ) -> Any:
        """Return header data."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return data for the given index and role."""
        if not index.isValid():
            return None
        
        row = index.row()
        column = index.column()
        filtered_servers = self._get_filtered_servers()
        
        if row >= len(filtered_servers):
            return None
        
        server = filtered_servers[row]
        
        # Display role
        if role == Qt.DisplayRole:
            return self._get_display_data(server, column)
        
        # Decoration role (icons)
        elif role == Qt.DecorationRole:
            return self._get_decoration_data(server, column)
        
        # Background color role
        elif role == Qt.BackgroundRole:
            return self._get_background_color(server, column)
        
        # Text color role
        elif role == Qt.ForegroundRole:
            return self._get_text_color(server, column)
        
        # Tooltip role
        elif role == Qt.ToolTipRole:
            return self._get_tooltip(server, column)
        
        # Custom data roles
        elif role == ServerDataRole.ServerObjectRole:
            return server
        elif role == ServerDataRole.ServerNameRole:
            return server.get('name', '')
        elif role == ServerDataRole.ServerTypeRole:
            return server.get('server_type', 'unknown')
        elif role == ServerDataRole.ServerStatusRole:
            return server.get('status', 'unknown')
        elif role == ServerDataRole.ServerScopeRole:
            return server.get('scope', 'user')
        elif role == ServerDataRole.ServerEnabledRole:
            return server.get('enabled', False)
        elif role == ServerDataRole.ServerSuitesRole:
            return server.get('suites', [])
        elif role == ServerDataRole.ServerCommandRole:
            return server.get('command', '')
        elif role == ServerDataRole.ServerArgsRole:
            return server.get('args', [])
        elif role == ServerDataRole.ServerEnvRole:
            return server.get('env', {})
        elif role == ServerDataRole.ServerPidRole:
            return server.get('pid')
        elif role == ServerDataRole.FilterRole:
            return self._get_filter_text(server)
        elif role == ServerDataRole.SortRole:
            return self._get_sort_value(server, column)
        
        return None
    
    def _get_display_data(self, server: Dict[str, Any], column: int) -> str:
        """Get display text for server data."""
        if column == ServerColumn.NAME:
            return server.get('name', '')
        elif column == ServerColumn.TYPE:
            return server.get('server_type', 'unknown').replace('_', ' ').title()
        elif column == ServerColumn.STATUS:
            status = server.get('status', 'unknown')
            claude_status = server.get('claude_status', '')
            if claude_status and claude_status != status:
                return f"{status} ({claude_status})"
            return status.title()
        elif column == ServerColumn.SCOPE:
            return server.get('scope', 'user').title()
        elif column == ServerColumn.DESCRIPTION:
            desc = server.get('description', '')
            return desc[:50] + '...' if len(desc) > 50 else desc
        elif column == ServerColumn.ENABLED:
            return "Yes" if server.get('enabled', False) else "No"
        elif column == ServerColumn.SUITES:
            suites = server.get('suites', [])
            if not suites:
                return "None"
            return ", ".join(suites[:3]) + ("..." if len(suites) > 3 else "")
        elif column == ServerColumn.LAST_UPDATED:
            updated_at = server.get('updated_at')
            if isinstance(updated_at, str):
                try:
                    dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d %H:%M')
                except (ValueError, TypeError):
                    return updated_at
            elif isinstance(updated_at, datetime):
                return updated_at.strftime('%Y-%m-%d %H:%M')
            return "Unknown"
        elif column == ServerColumn.ACTIONS:
            return "..."  # Actions will be handled by delegate
        
        return ""
    
    def _get_decoration_data(self, server: Dict[str, Any], column: int) -> Optional[QIcon]:
        """Get icon for server data."""
        if column == ServerColumn.STATUS:
            status = server.get('status', 'unknown')
            return self._get_status_icon(status)
        elif column == ServerColumn.TYPE:
            server_type = server.get('server_type', 'unknown')
            return self._get_type_icon(server_type)
        elif column == ServerColumn.ENABLED:
            enabled = server.get('enabled', False)
            return self._get_enabled_icon(enabled)
        
        return None
    
    def _get_background_color(self, server: Dict[str, Any], column: int) -> Optional[QColor]:
        """Get background color for server data."""
        status = server.get('status', 'unknown')
        
        if status == 'error':
            return QColor(255, 240, 240)  # Light red
        elif status == 'inactive':
            return QColor(248, 248, 248)  # Light gray
        elif status == 'active':
            return QColor(240, 255, 240)  # Light green
        
        return None
    
    def _get_text_color(self, server: Dict[str, Any], column: int) -> Optional[QColor]:
        """Get text color for server data."""
        if not server.get('enabled', False):
            return QColor(128, 128, 128)  # Gray for disabled servers
        
        return None
    
    def _get_tooltip(self, server: Dict[str, Any], column: int) -> str:
        """Get tooltip text for server data."""
        name = server.get('name', 'Unknown')
        
        if column == ServerColumn.NAME:
            return f"Server: {name}\nCommand: {server.get('command', 'N/A')}"
        elif column == ServerColumn.STATUS:
            status = server.get('status', 'unknown')
            claude_status = server.get('claude_status', '')
            pid = server.get('pid')
            tooltip = f"Status: {status.title()}"
            if claude_status:
                tooltip += f"\nClaude Status: {claude_status}"
            if pid:
                tooltip += f"\nProcess ID: {pid}"
            last_error = server.get('last_error')
            if last_error:
                tooltip += f"\nLast Error: {last_error}"
            return tooltip
        elif column == ServerColumn.DESCRIPTION:
            return server.get('description', 'No description available')
        elif column == ServerColumn.SUITES:
            suites = server.get('suites', [])
            if not suites:
                return "Not part of any suite"
            return f"Member of suites:\n" + "\n".join(f"• {suite}" for suite in suites)
        elif column == ServerColumn.LAST_UPDATED:
            updated = server.get('updated_at', 'Unknown')
            created = server.get('created_at', 'Unknown')
            return f"Created: {created}\nLast Updated: {updated}"
        
        return f"Server: {name}"
    
    def _get_filter_text(self, server: Dict[str, Any]) -> str:
        """Get searchable text for server."""
        parts = [
            server.get('name', ''),
            server.get('description', ''),
            server.get('server_type', ''),
            server.get('status', ''),
            server.get('scope', ''),
            ' '.join(server.get('suites', [])),
            server.get('command', '')
        ]
        return ' '.join(str(part).lower() for part in parts if part)
    
    def _get_sort_value(self, server: Dict[str, Any], column: int) -> Any:
        """Get sort value for server data."""
        if column == ServerColumn.NAME:
            return server.get('name', '').lower()
        elif column == ServerColumn.TYPE:
            return server.get('server_type', 'zzz')  # Unknown sorts last
        elif column == ServerColumn.STATUS:
            # Sort by status priority: active, inactive, error, unknown
            status_order = {'active': 0, 'inactive': 1, 'error': 2, 'unknown': 3}
            return status_order.get(server.get('status', 'unknown'), 3)
        elif column == ServerColumn.SCOPE:
            scope_order = {'project': 0, 'user': 1, 'local': 2}
            return scope_order.get(server.get('scope', 'user'), 1)
        elif column == ServerColumn.ENABLED:
            return 0 if server.get('enabled', False) else 1
        elif column == ServerColumn.SUITES:
            suites = server.get('suites', [])
            return len(suites)
        elif column == ServerColumn.LAST_UPDATED:
            updated_at = server.get('updated_at')
            if isinstance(updated_at, str):
                try:
                    return datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return datetime.min
            elif isinstance(updated_at, datetime):
                return updated_at
            return datetime.min
        
        return ""
    
    def _get_filtered_servers(self) -> List[Dict[str, Any]]:
        """Get list of servers matching current filters."""
        if not any([
            self._filter_text, self._filter_type, self._filter_status,
            self._filter_scope, self._filter_enabled is not None
        ]):
            return self._servers
        
        filtered = []
        for server in self._servers:
            if self._matches_filters(server):
                filtered.append(server)
        
        return filtered
    
    def _matches_filters(self, server: Dict[str, Any]) -> bool:
        """Check if server matches current filters."""
        # Text filter
        if self._filter_text:
            filter_text = self._get_filter_text(server)
            if self._filter_text.lower() not in filter_text:
                return False
        
        # Type filter
        if self._filter_type:
            if server.get('server_type') != self._filter_type:
                return False
        
        # Status filter
        if self._filter_status:
            if server.get('status') != self._filter_status:
                return False
        
        # Scope filter
        if self._filter_scope:
            if server.get('scope') != self._filter_scope:
                return False
        
        # Enabled filter
        if self._filter_enabled is not None:
            if server.get('enabled', False) != self._filter_enabled:
                return False
        
        return True
    
    def _get_status_icon(self, status: str) -> QIcon:
        """Get status icon from cache or create new one."""
        if status not in self._status_icons:
            # Create colored circle icon based on status
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            
            if status == 'active':
                pixmap.fill(QColor(0, 200, 0))  # Green
            elif status == 'inactive':
                pixmap.fill(QColor(128, 128, 128))  # Gray
            elif status == 'error':
                pixmap.fill(QColor(255, 0, 0))  # Red
            else:
                pixmap.fill(QColor(255, 165, 0))  # Orange for unknown
            
            self._status_icons[status] = QIcon(pixmap)
        
        return self._status_icons[status]
    
    def _get_type_icon(self, server_type: str) -> QIcon:
        """Get type icon from cache or create new one."""
        if server_type not in self._type_icons:
            # For now, return empty icon - icons would be loaded from resources
            self._type_icons[server_type] = QIcon()
        
        return self._type_icons[server_type]
    
    def _get_enabled_icon(self, enabled: bool) -> QIcon:
        """Get enabled/disabled icon."""
        # Create simple checkmark or X icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        if enabled:
            pixmap.fill(QColor(0, 200, 0))  # Green checkmark
        else:
            pixmap.fill(QColor(200, 0, 0))  # Red X
        
        return QIcon(pixmap)
    
    # Filtering and sorting methods
    def set_filter_text(self, text: str) -> None:
        """Set text filter."""
        if self._filter_text != text:
            self._filter_text = text
            self.beginResetModel()
            self.endResetModel()
    
    def set_filter_type(self, server_type: Optional[str]) -> None:
        """Set type filter."""
        if self._filter_type != server_type:
            self._filter_type = server_type
            self.beginResetModel()
            self.endResetModel()
    
    def set_filter_status(self, status: Optional[str]) -> None:
        """Set status filter."""
        if self._filter_status != status:
            self._filter_status = status
            self.beginResetModel()
            self.endResetModel()
    
    def set_filter_scope(self, scope: Optional[str]) -> None:
        """Set scope filter."""
        if self._filter_scope != scope:
            self._filter_scope = scope
            self.beginResetModel()
            self.endResetModel()
    
    def set_filter_enabled(self, enabled: Optional[bool]) -> None:
        """Set enabled filter."""
        if self._filter_enabled != enabled:
            self._filter_enabled = enabled
            self.beginResetModel()
            self.endResetModel()
    
    def clear_filters(self) -> None:
        """Clear all filters."""
        changed = any([
            self._filter_text, self._filter_type, self._filter_status,
            self._filter_scope, self._filter_enabled is not None
        ])
        
        if changed:
            self._filter_text = ""
            self._filter_type = None
            self._filter_status = None
            self._filter_scope = None
            self._filter_enabled = None
            self.beginResetModel()
            self.endResetModel()
    
    # Auto-refresh control
    def set_auto_refresh(self, enabled: bool) -> None:
        """Enable or disable auto-refresh."""
        self._auto_refresh_enabled = enabled
        if enabled and not self._refresh_timer.isActive():
            self._refresh_timer.start(5000)
        elif not enabled and self._refresh_timer.isActive():
            self._refresh_timer.stop()
    
    def set_refresh_interval(self, milliseconds: int) -> None:
        """Set refresh interval in milliseconds."""
        if milliseconds > 0:
            self._refresh_timer.setInterval(milliseconds)
    
    def refresh_now(self) -> None:
        """Manually refresh data."""
        asyncio.create_task(self._async_refresh_data())
    
    # Server operations
    async def enable_server(self, server_name: str) -> bool:
        """Enable a server."""
        result = await self._cli_bridge.enable_server(server_name)
        if result:
            self.refresh_now()
        return result
    
    async def disable_server(self, server_name: str) -> bool:
        """Disable a server."""
        result = await self._cli_bridge.disable_server(server_name)
        if result:
            self.refresh_now()
        return result
    
    async def remove_server(self, server_name: str) -> bool:
        """Remove a server."""
        result = await self._cli_bridge.remove_server(server_name)
        if result:
            self.refresh_now()
        return result
    
    def get_server_by_row(self, row: int) -> Optional[Dict[str, Any]]:
        """Get server data by row index."""
        filtered_servers = self._get_filtered_servers()
        if 0 <= row < len(filtered_servers):
            return filtered_servers[row]
        return None
    
    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get server data by name."""
        for server in self._servers:
            if server.get('name') == name:
                return server
        return None
    
    # Drag and drop support
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Return item flags for drag and drop support."""
        if not index.isValid():
            return Qt.NoItemFlags
        
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        # Allow dragging servers to suites
        flags |= Qt.ItemIsDragEnabled
        
        return flags
    
    def supportedDragActions(self) -> Qt.DropActions:
        """Return supported drag actions."""
        return Qt.CopyAction | Qt.MoveAction
    
    def mimeTypes(self) -> List[str]:
        """Return supported MIME types for drag and drop."""
        return ["application/x-mcp-server"]
    
    def mimeData(self, indexes: List[QModelIndex]) -> QMimeData:
        """Return MIME data for drag and drop."""
        mime_data = QMimeData()
        
        # Get server names from selected indexes
        server_names = []
        for index in indexes:
            if index.column() == ServerColumn.NAME:  # Only process name column
                server_name = self.data(index, ServerDataRole.ServerNameRole)
                if server_name and server_name not in server_names:
                    server_names.append(server_name)
        
        # Store server names in MIME data
        if server_names:
            data = "\n".join(server_names)
            mime_data.setData("application/x-mcp-server", data.encode())
            mime_data.setText(data)  # Fallback text representation
        
        return mime_data