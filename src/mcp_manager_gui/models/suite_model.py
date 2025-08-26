"""
Qt Data Models for MCP Suite Management.

Provides Qt model/view architecture compatible models for displaying and
managing MCP server suites in the GUI. Supports real-time updates, filtering,
sorting, and drag-and-drop operations for suite management.
"""

import asyncio
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import (
    QAbstractTableModel, QAbstractListModel, QModelIndex, QObject, 
    QPersistentModelIndex, Qt, QTimer, Signal, QMimeData
)
from PySide6.QtGui import QColor, QIcon, QPixmap

from mcp_manager.core.suites.models import Suite, SuiteMembership
from mcp_manager_gui.services.cli_bridge import CLIBridge


class SuiteColumn(IntEnum):
    """Column indices for suite table model."""
    NAME = 0
    DESCRIPTION = 1
    CATEGORY = 2
    SERVERS = 3
    STATUS = 4
    CREATED = 5
    UPDATED = 6
    ACTIONS = 7


class SuiteDataRole(IntEnum):
    """Custom data roles for suite model."""
    SuiteObjectRole = Qt.UserRole + 1
    SuiteIdRole = Qt.UserRole + 2
    SuiteNameRole = Qt.UserRole + 3
    SuiteCategoryRole = Qt.UserRole + 4
    SuiteDescriptionRole = Qt.UserRole + 5
    SuiteServersRole = Qt.UserRole + 6
    SuiteMembershipsRole = Qt.UserRole + 7
    SuiteConfigRole = Qt.UserRole + 8
    SuiteStatusRole = Qt.UserRole + 9
    FilterRole = Qt.UserRole + 10
    SortRole = Qt.UserRole + 11


class SuiteTableModel(QAbstractTableModel):
    """Table model for displaying MCP suites in a table view."""
    
    # Signals
    suiteAdded = Signal(str)  # suite_id
    suiteRemoved = Signal(str)  # suite_id
    suiteModified = Signal(str)  # suite_id
    serverAddedToSuite = Signal(str, str)  # suite_id, server_name
    serverRemovedFromSuite = Signal(str, str)  # suite_id, server_name
    dataRefreshed = Signal()
    
    def __init__(self, cli_bridge: CLIBridge, parent: Optional[QObject] = None):
        """Initialize the suite table model."""
        super().__init__(parent)
        
        self._cli_bridge = cli_bridge
        self._suites: List[Dict[str, Any]] = []
        self._headers = [
            "Name", "Description", "Category", "Servers", 
            "Status", "Created", "Updated", "Actions"
        ]
        
        # Filtering and sorting
        self._filter_text = ""
        self._filter_category: Optional[str] = None
        self._filter_status: Optional[str] = None
        
        # Auto-refresh settings
        self._auto_refresh_enabled = True
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_data)
        self._refresh_timer.start(10000)  # Refresh every 10 seconds (less frequent than servers)
        
        # Icons cache
        self._category_icons: Dict[str, QIcon] = {}
        self._status_icons: Dict[str, QIcon] = {}
        
        # Initial data load
        self._load_initial_data()
    
    def _load_initial_data(self) -> None:
        """Load initial suite data asynchronously."""
        asyncio.create_task(self._async_refresh_data())
    
    async def _async_refresh_data(self) -> None:
        """Refresh suite data from the CLI bridge."""
        try:
            # Get suites through CLI bridge
            suites = await self._get_suites_from_cli()
            
            # Update model data
            self.beginResetModel()
            old_suites = {s.get('id', '') for s in self._suites}
            new_suites = {s.get('id', '') for s in suites}
            
            self._suites = suites
            self.endResetModel()
            
            # Emit signals for suite changes
            added = new_suites - old_suites
            removed = old_suites - new_suites
            
            for suite_id in added:
                self.suiteAdded.emit(suite_id)
            
            for suite_id in removed:
                self.suiteRemoved.emit(suite_id)
            
            self.dataRefreshed.emit()
            
        except Exception as e:
            print(f"Error refreshing suite data: {e}")
    
    async def _get_suites_from_cli(self) -> List[Dict[str, Any]]:
        """Get suites from CLI bridge (placeholder implementation)."""
        # This would integrate with the actual suite management system
        # For now, return mock data structure
        try:
            # Would call something like: await self._cli_bridge.get_suites()
            return []
        except Exception:
            return []
    
    def _refresh_data(self) -> None:
        """Timer callback to refresh data."""
        if self._auto_refresh_enabled:
            asyncio.create_task(self._async_refresh_data())
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of suites (rows)."""
        if parent.isValid():
            return 0
        return len(self._get_filtered_suites())
    
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
        filtered_suites = self._get_filtered_suites()
        
        if row >= len(filtered_suites):
            return None
        
        suite = filtered_suites[row]
        
        # Display role
        if role == Qt.DisplayRole:
            return self._get_display_data(suite, column)
        
        # Decoration role (icons)
        elif role == Qt.DecorationRole:
            return self._get_decoration_data(suite, column)
        
        # Background color role
        elif role == Qt.BackgroundRole:
            return self._get_background_color(suite, column)
        
        # Text color role
        elif role == Qt.ForegroundRole:
            return self._get_text_color(suite, column)
        
        # Tooltip role
        elif role == Qt.ToolTipRole:
            return self._get_tooltip(suite, column)
        
        # Custom data roles
        elif role == SuiteDataRole.SuiteObjectRole:
            return suite
        elif role == SuiteDataRole.SuiteIdRole:
            return suite.get('id', '')
        elif role == SuiteDataRole.SuiteNameRole:
            return suite.get('name', '')
        elif role == SuiteDataRole.SuiteCategoryRole:
            return suite.get('category', 'general')
        elif role == SuiteDataRole.SuiteDescriptionRole:
            return suite.get('description', '')
        elif role == SuiteDataRole.SuiteServersRole:
            memberships = suite.get('memberships', [])
            return [m.get('server_name', '') for m in memberships]
        elif role == SuiteDataRole.SuiteMembershipsRole:
            return suite.get('memberships', [])
        elif role == SuiteDataRole.SuiteConfigRole:
            return suite.get('config', {})
        elif role == SuiteDataRole.SuiteStatusRole:
            return self._calculate_suite_status(suite)
        elif role == SuiteDataRole.FilterRole:
            return self._get_filter_text(suite)
        elif role == SuiteDataRole.SortRole:
            return self._get_sort_value(suite, column)
        
        return None
    
    def _get_display_data(self, suite: Dict[str, Any], column: int) -> str:
        """Get display text for suite data."""
        if column == SuiteColumn.NAME:
            return suite.get('name', '')
        elif column == SuiteColumn.DESCRIPTION:
            desc = suite.get('description', '')
            return desc[:60] + '...' if len(desc) > 60 else desc
        elif column == SuiteColumn.CATEGORY:
            return suite.get('category', 'general').replace('_', ' ').title()
        elif column == SuiteColumn.SERVERS:
            memberships = suite.get('memberships', [])
            count = len(memberships)
            if count == 0:
                return "Empty"
            elif count == 1:
                return "1 server"
            else:
                return f"{count} servers"
        elif column == SuiteColumn.STATUS:
            return self._calculate_suite_status(suite)
        elif column == SuiteColumn.CREATED:
            created_at = suite.get('created_at')
            if isinstance(created_at, str):
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    return created_at
            elif isinstance(created_at, datetime):
                return created_at.strftime('%Y-%m-%d')
            return "Unknown"
        elif column == SuiteColumn.UPDATED:
            updated_at = suite.get('updated_at')
            if isinstance(updated_at, str):
                try:
                    dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d %H:%M')
                except (ValueError, TypeError):
                    return updated_at
            elif isinstance(updated_at, datetime):
                return updated_at.strftime('%Y-%m-%d %H:%M')
            return "Unknown"
        elif column == SuiteColumn.ACTIONS:
            return "..."  # Actions will be handled by delegate
        
        return ""
    
    def _get_decoration_data(self, suite: Dict[str, Any], column: int) -> Optional[QIcon]:
        """Get icon for suite data."""
        if column == SuiteColumn.CATEGORY:
            category = suite.get('category', 'general')
            return self._get_category_icon(category)
        elif column == SuiteColumn.STATUS:
            status = self._calculate_suite_status(suite)
            return self._get_status_icon(status)
        
        return None
    
    def _get_background_color(self, suite: Dict[str, Any], column: int) -> Optional[QColor]:
        """Get background color for suite data."""
        status = self._calculate_suite_status(suite)
        
        if status == 'error':
            return QColor(255, 240, 240)  # Light red
        elif status == 'partial':
            return QColor(255, 248, 220)  # Light orange
        elif status == 'ready':
            return QColor(240, 255, 240)  # Light green
        elif status == 'empty':
            return QColor(248, 248, 248)  # Light gray
        
        return None
    
    def _get_text_color(self, suite: Dict[str, Any], column: int) -> Optional[QColor]:
        """Get text color for suite data."""
        status = self._calculate_suite_status(suite)
        
        if status == 'empty':
            return QColor(128, 128, 128)  # Gray for empty suites
        
        return None
    
    def _get_tooltip(self, suite: Dict[str, Any], column: int) -> str:
        """Get tooltip text for suite data."""
        name = suite.get('name', 'Unknown')
        
        if column == SuiteColumn.NAME:
            return f"Suite: {name}\nID: {suite.get('id', 'N/A')}"
        elif column == SuiteColumn.DESCRIPTION:
            return suite.get('description', 'No description available')
        elif column == SuiteColumn.CATEGORY:
            category = suite.get('category', 'general')
            return f"Category: {category.replace('_', ' ').title()}"
        elif column == SuiteColumn.SERVERS:
            memberships = suite.get('memberships', [])
            if not memberships:
                return "No servers in this suite"
            
            tooltip_parts = ["Servers in this suite:"]
            for membership in memberships[:10]:  # Limit to first 10
                server_name = membership.get('server_name', 'Unknown')
                role = membership.get('role', 'member')
                priority = membership.get('priority', 50)
                tooltip_parts.append(f"• {server_name} ({role}, priority: {priority})")
            
            if len(memberships) > 10:
                tooltip_parts.append(f"... and {len(memberships) - 10} more")
            
            return "\n".join(tooltip_parts)
        elif column == SuiteColumn.STATUS:
            status = self._calculate_suite_status(suite)
            return f"Suite Status: {status.title()}\n{self._get_status_description(status)}"
        elif column == SuiteColumn.CREATED:
            created = suite.get('created_at', 'Unknown')
            return f"Created: {created}"
        elif column == SuiteColumn.UPDATED:
            updated = suite.get('updated_at', 'Unknown')
            return f"Last Updated: {updated}"
        
        return f"Suite: {name}"
    
    def _get_filter_text(self, suite: Dict[str, Any]) -> str:
        """Get searchable text for suite."""
        parts = [
            suite.get('name', ''),
            suite.get('description', ''),
            suite.get('category', ''),
            suite.get('id', ''),
        ]
        
        # Add server names
        memberships = suite.get('memberships', [])
        for membership in memberships:
            parts.append(membership.get('server_name', ''))
        
        return ' '.join(str(part).lower() for part in parts if part)
    
    def _get_sort_value(self, suite: Dict[str, Any], column: int) -> Any:
        """Get sort value for suite data."""
        if column == SuiteColumn.NAME:
            return suite.get('name', '').lower()
        elif column == SuiteColumn.CATEGORY:
            return suite.get('category', 'zzz')  # Unknown sorts last
        elif column == SuiteColumn.SERVERS:
            return len(suite.get('memberships', []))
        elif column == SuiteColumn.STATUS:
            # Sort by status priority: ready, partial, empty, error
            status_order = {'ready': 0, 'partial': 1, 'empty': 2, 'error': 3}
            status = self._calculate_suite_status(suite)
            return status_order.get(status, 3)
        elif column == SuiteColumn.CREATED:
            created_at = suite.get('created_at')
            if isinstance(created_at, str):
                try:
                    return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return datetime.min
            elif isinstance(created_at, datetime):
                return created_at
            return datetime.min
        elif column == SuiteColumn.UPDATED:
            updated_at = suite.get('updated_at')
            if isinstance(updated_at, str):
                try:
                    return datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return datetime.min
            elif isinstance(updated_at, datetime):
                return updated_at
            return datetime.min
        
        return ""
    
    def _calculate_suite_status(self, suite: Dict[str, Any]) -> str:
        """Calculate overall suite status based on member servers."""
        memberships = suite.get('memberships', [])
        
        if not memberships:
            return 'empty'
        
        # This would need to be enhanced to check actual server statuses
        # For now, return basic status
        return 'ready'
    
    def _get_status_description(self, status: str) -> str:
        """Get human-readable status description."""
        descriptions = {
            'ready': 'All servers are available and configured',
            'partial': 'Some servers may be unavailable',
            'empty': 'No servers added to this suite',
            'error': 'One or more servers have errors'
        }
        return descriptions.get(status, 'Unknown status')
    
    def _get_filtered_suites(self) -> List[Dict[str, Any]]:
        """Get list of suites matching current filters."""
        if not any([
            self._filter_text, self._filter_category, self._filter_status
        ]):
            return self._suites
        
        filtered = []
        for suite in self._suites:
            if self._matches_filters(suite):
                filtered.append(suite)
        
        return filtered
    
    def _matches_filters(self, suite: Dict[str, Any]) -> bool:
        """Check if suite matches current filters."""
        # Text filter
        if self._filter_text:
            filter_text = self._get_filter_text(suite)
            if self._filter_text.lower() not in filter_text:
                return False
        
        # Category filter
        if self._filter_category:
            if suite.get('category') != self._filter_category:
                return False
        
        # Status filter
        if self._filter_status:
            if self._calculate_suite_status(suite) != self._filter_status:
                return False
        
        return True
    
    def _get_category_icon(self, category: str) -> QIcon:
        """Get category icon from cache or create new one."""
        if category not in self._category_icons:
            # Create colored icon based on category
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            
            # Color mapping for categories
            colors = {
                'web-development': QColor(0, 150, 255),     # Blue
                'data-analysis': QColor(255, 140, 0),       # Orange
                'system-administration': QColor(128, 0, 128), # Purple
                'research': QColor(0, 200, 100),            # Green
                'automation': QColor(255, 200, 0),          # Yellow
                'testing': QColor(255, 0, 100),             # Pink
                'general': QColor(128, 128, 128)            # Gray
            }
            
            color = colors.get(category, QColor(128, 128, 128))
            pixmap.fill(color)
            
            self._category_icons[category] = QIcon(pixmap)
        
        return self._category_icons[category]
    
    def _get_status_icon(self, status: str) -> QIcon:
        """Get status icon from cache or create new one."""
        if status not in self._status_icons:
            # Create colored circle icon based on status
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            
            if status == 'ready':
                pixmap.fill(QColor(0, 200, 0))      # Green
            elif status == 'partial':
                pixmap.fill(QColor(255, 165, 0))    # Orange
            elif status == 'empty':
                pixmap.fill(QColor(200, 200, 200))  # Light gray
            elif status == 'error':
                pixmap.fill(QColor(255, 0, 0))      # Red
            else:
                pixmap.fill(QColor(128, 128, 128))  # Dark gray
            
            self._status_icons[status] = QIcon(pixmap)
        
        return self._status_icons[status]
    
    # Filtering methods
    def set_filter_text(self, text: str) -> None:
        """Set text filter."""
        if self._filter_text != text:
            self._filter_text = text
            self.beginResetModel()
            self.endResetModel()
    
    def set_filter_category(self, category: Optional[str]) -> None:
        """Set category filter."""
        if self._filter_category != category:
            self._filter_category = category
            self.beginResetModel()
            self.endResetModel()
    
    def set_filter_status(self, status: Optional[str]) -> None:
        """Set status filter."""
        if self._filter_status != status:
            self._filter_status = status
            self.beginResetModel()
            self.endResetModel()
    
    def clear_filters(self) -> None:
        """Clear all filters."""
        changed = any([
            self._filter_text, self._filter_category, self._filter_status
        ])
        
        if changed:
            self._filter_text = ""
            self._filter_category = None
            self._filter_status = None
            self.beginResetModel()
            self.endResetModel()
    
    # Auto-refresh control
    def set_auto_refresh(self, enabled: bool) -> None:
        """Enable or disable auto-refresh."""
        self._auto_refresh_enabled = enabled
        if enabled and not self._refresh_timer.isActive():
            self._refresh_timer.start(10000)
        elif not enabled and self._refresh_timer.isActive():
            self._refresh_timer.stop()
    
    def set_refresh_interval(self, milliseconds: int) -> None:
        """Set refresh interval in milliseconds."""
        if milliseconds > 0:
            self._refresh_timer.setInterval(milliseconds)
    
    def refresh_now(self) -> None:
        """Manually refresh data."""
        asyncio.create_task(self._async_refresh_data())
    
    # Suite operations (placeholder methods)
    async def create_suite(
        self, 
        name: str, 
        description: str = "",
        category: str = "general"
    ) -> bool:
        """Create a new suite."""
        try:
            # This would integrate with the actual suite creation system
            # result = await self._cli_bridge.create_suite(name, description, category)
            result = False  # Placeholder
            if result:
                self.refresh_now()
            return result
        except Exception as e:
            print(f"Error creating suite '{name}': {e}")
            return False
    
    async def delete_suite(self, suite_id: str) -> bool:
        """Delete a suite."""
        try:
            # This would integrate with the actual suite deletion system
            # result = await self._cli_bridge.delete_suite(suite_id)
            result = False  # Placeholder
            if result:
                self.refresh_now()
            return result
        except Exception as e:
            print(f"Error deleting suite '{suite_id}': {e}")
            return False
    
    async def add_server_to_suite(
        self, 
        suite_id: str, 
        server_name: str,
        role: str = "member",
        priority: int = 50
    ) -> bool:
        """Add a server to a suite."""
        try:
            # This would integrate with the actual suite membership system
            # result = await self._cli_bridge.add_server_to_suite(suite_id, server_name, role, priority)
            result = False  # Placeholder
            if result:
                self.serverAddedToSuite.emit(suite_id, server_name)
                self.refresh_now()
            return result
        except Exception as e:
            print(f"Error adding server '{server_name}' to suite '{suite_id}': {e}")
            return False
    
    async def remove_server_from_suite(self, suite_id: str, server_name: str) -> bool:
        """Remove a server from a suite."""
        try:
            # This would integrate with the actual suite membership system
            # result = await self._cli_bridge.remove_server_from_suite(suite_id, server_name)
            result = False  # Placeholder
            if result:
                self.serverRemovedFromSuite.emit(suite_id, server_name)
                self.refresh_now()
            return result
        except Exception as e:
            print(f"Error removing server '{server_name}' from suite '{suite_id}': {e}")
            return False
    
    def get_suite_by_row(self, row: int) -> Optional[Dict[str, Any]]:
        """Get suite data by row index."""
        filtered_suites = self._get_filtered_suites()
        if 0 <= row < len(filtered_suites):
            return filtered_suites[row]
        return None
    
    def get_suite_by_id(self, suite_id: str) -> Optional[Dict[str, Any]]:
        """Get suite data by ID."""
        for suite in self._suites:
            if suite.get('id') == suite_id:
                return suite
        return None
    
    def get_suite_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get suite data by name."""
        for suite in self._suites:
            if suite.get('name') == name:
                return suite
        return None
    
    # Drag and drop support
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Return item flags for drag and drop support."""
        if not index.isValid():
            return Qt.ItemIsDropEnabled  # Allow dropping on empty space
        
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        # Allow dropping servers onto suites
        flags |= Qt.ItemIsDropEnabled
        
        # Allow dragging suites for reordering
        flags |= Qt.ItemIsDragEnabled
        
        return flags
    
    def supportedDropActions(self) -> Qt.DropActions:
        """Return supported drop actions."""
        return Qt.CopyAction | Qt.MoveAction
    
    def supportedDragActions(self) -> Qt.DropActions:
        """Return supported drag actions."""
        return Qt.CopyAction | Qt.MoveAction
    
    def mimeTypes(self) -> List[str]:
        """Return supported MIME types for drag and drop."""
        return ["application/x-mcp-server", "application/x-mcp-suite"]
    
    def mimeData(self, indexes: List[QModelIndex]) -> QMimeData:
        """Return MIME data for drag and drop."""
        mime_data = QMimeData()
        
        # Get suite IDs from selected indexes
        suite_ids = []
        for index in indexes:
            if index.column() == SuiteColumn.NAME:  # Only process name column
                suite_id = self.data(index, SuiteDataRole.SuiteIdRole)
                if suite_id and suite_id not in suite_ids:
                    suite_ids.append(suite_id)
        
        # Store suite IDs in MIME data
        if suite_ids:
            data = "\n".join(suite_ids)
            mime_data.setData("application/x-mcp-suite", data.encode())
            mime_data.setText(data)  # Fallback text representation
        
        return mime_data
    
    def dropMimeData(
        self, 
        data: QMimeData, 
        action: Qt.DropAction, 
        row: int, 
        column: int, 
        parent: QModelIndex
    ) -> bool:
        """Handle dropping MIME data (servers onto suites)."""
        if not data.hasFormat("application/x-mcp-server"):
            return False
        
        # Get target suite
        target_suite = None
        if parent.isValid():
            target_suite = self.get_suite_by_row(parent.row())
        
        if not target_suite:
            return False
        
        # Get dropped server names
        server_data = data.data("application/x-mcp-server").data().decode()
        server_names = [name.strip() for name in server_data.split('\n') if name.strip()]
        
        # Add servers to suite
        suite_id = target_suite.get('id', '')
        if suite_id:
            for server_name in server_names:
                asyncio.create_task(
                    self.add_server_to_suite(suite_id, server_name)
                )
            return True
        
        return False


class SuiteMembershipListModel(QAbstractListModel):
    """List model for displaying suite membership (servers in a suite)."""
    
    # Signals
    membershipChanged = Signal()
    
    def __init__(self, parent: Optional[QObject] = None):
        """Initialize the membership list model."""
        super().__init__(parent)
        
        self._memberships: List[Dict[str, Any]] = []
        self._suite_id: Optional[str] = None
    
    def set_suite(self, suite_data: Optional[Dict[str, Any]]) -> None:
        """Set the suite to display memberships for."""
        self.beginResetModel()
        
        if suite_data:
            self._suite_id = suite_data.get('id')
            self._memberships = suite_data.get('memberships', [])
        else:
            self._suite_id = None
            self._memberships = []
        
        self.endResetModel()
        self.membershipChanged.emit()
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return number of memberships."""
        if parent.isValid():
            return 0
        return len(self._memberships)
    
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return data for the given index and role."""
        if not index.isValid() or index.row() >= len(self._memberships):
            return None
        
        membership = self._memberships[index.row()]
        
        if role == Qt.DisplayRole:
            server_name = membership.get('server_name', 'Unknown')
            role_name = membership.get('role', 'member')
            priority = membership.get('priority', 50)
            return f"{server_name} ({role_name}, priority: {priority})"
        
        elif role == Qt.ToolTipRole:
            server_name = membership.get('server_name', 'Unknown')
            role_name = membership.get('role', 'member')
            priority = membership.get('priority', 50)
            server_type = membership.get('server_type', 'unknown')
            added_at = membership.get('added_at', 'Unknown')
            
            tooltip = f"Server: {server_name}\n"
            tooltip += f"Role: {role_name.title()}\n"
            tooltip += f"Priority: {priority}\n"
            tooltip += f"Type: {server_type.replace('_', ' ').title()}\n"
            tooltip += f"Added: {added_at}"
            
            return tooltip
        
        elif role == Qt.UserRole:
            return membership
        
        elif role == Qt.UserRole + 1:  # Server name role
            return membership.get('server_name', '')
        
        elif role == Qt.UserRole + 2:  # Role role
            return membership.get('role', 'member')
        
        elif role == Qt.UserRole + 3:  # Priority role
            return membership.get('priority', 50)
        
        return None
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Return item flags."""
        if not index.isValid():
            return Qt.NoItemFlags
        
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable
    
    def get_membership_by_row(self, row: int) -> Optional[Dict[str, Any]]:
        """Get membership data by row."""
        if 0 <= row < len(self._memberships):
            return self._memberships[row]
        return None
    
    def get_server_names(self) -> List[str]:
        """Get list of server names in the suite."""
        return [m.get('server_name', '') for m in self._memberships]