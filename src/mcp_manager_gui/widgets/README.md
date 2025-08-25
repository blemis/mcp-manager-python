# MCP Manager GUI Widgets

This directory contains the core UI widgets for the MCP Manager GUI application. The widgets are built using PySide6 and follow macOS design patterns.

## Core Widgets

### ServerList (`server_list.py`)
A comprehensive server list widget that provides:

- **Real-time server monitoring** with automatic updates
- **Search and filtering** capabilities (by name, type, status)
- **Bulk operations** (enable/disable all servers)
- **Interactive server cards** with status indicators
- **Context menus** for quick actions
- **Background worker thread** to keep UI responsive

**Key Features:**
- Automatic refresh every 5 seconds
- Search by server name, type, or description
- Filter by status (Connected, Failed, Disabled, Unknown)
- Filter by type (Docker Desktop, NPM, Docker Hub, Custom)
- Enable/disable all visible servers at once
- Real-time server count display

**Signals:**
- `server_selected(dict)` - Emitted when a server is selected
- `server_action_requested(str, str)` - Emitted for server actions
- `refresh_requested()` - Emitted when manual refresh is requested

### ServerCard (`server_card.py`)
Individual server information display card that shows:

- **Status indicator** with animated states (Connected, Failed, etc.)
- **Server details** (name, type, description, command)
- **Action buttons** (Enable/Disable, Info, More actions)
- **Context menu** with server operations
- **Hover and selection effects** with smooth animations
- **Tools information** if available

**Key Features:**
- Real-time status indicator with pulse animations
- Hover effects and selection highlighting
- Context menu with Enable/Disable/Remove/Restart actions
- Detailed server information dialog
- Responsive design that adapts to content
- macOS-style visual design

**Signals:**
- `server_selected(dict)` - Emitted when card is clicked
- `action_requested(str, str)` - Emitted for server actions

### StatusMonitor (`status_monitor.py`)
Real-time system status dashboard that provides:

- **System health overview** with health score gauge
- **Metric cards** showing key statistics
- **Real-time event log** with syntax highlighting
- **Detailed metrics table** with all system data
- **Tabbed interface** for different views
- **Background monitoring** with automatic updates

**Key Features:**
- Health score calculation (0-100%) based on server status
- Real-time metrics collection every 2 seconds
- Event logging with different severity levels (INFO, WARNING, ERROR)
- Metrics history tracking
- Server type distribution analysis
- Automatic scrolling event log with 1000-line limit

**Components:**
- `MetricCard` - Individual metric display cards
- `SystemHealthWidget` - Health overview with gauge
- `EventLogWidget` - Real-time event logging
- `MetricsWorker` - Background thread for data collection

## Usage Examples

### Basic Server List
```python
from mcp_manager_gui.services.cli_bridge import CLIBridge
from mcp_manager_gui.widgets import ServerList

cli_bridge = CLIBridge()
server_list = ServerList(cli_bridge, parent_widget)

# Connect signals
server_list.server_selected.connect(handle_server_selection)
server_list.server_action_requested.connect(handle_server_action)
```

### Individual Server Card
```python
from mcp_manager_gui.widgets import ServerCard

server_data = {
    'name': 'SQLite MCP',
    'type': 'Docker Desktop',
    'claude_status': 'Connected',
    'description': 'SQLite database management server',
    'command': 'docker run sqlite-mcp',
    'tools': [{'name': 'query'}, {'name': 'schema'}]
}

card = ServerCard(server_data, cli_bridge, parent_widget)
card.server_selected.connect(handle_selection)
card.action_requested.connect(handle_action)
```

### Status Monitor Dashboard
```python
from mcp_manager_gui.widgets import StatusMonitor

monitor = StatusMonitor(cli_bridge, parent_widget)
monitor.refresh_requested.connect(handle_refresh_request)
```

## Styling and Theme

All widgets follow macOS design patterns:
- **System fonts**: -apple-system, BlinkMacSystemFont
- **Color scheme**: iOS/macOS color palette
- **Animations**: Smooth transitions and hover effects
- **Shadows**: Subtle drop shadows for depth
- **Borders**: Rounded corners with subtle borders

### Color Palette
- **Primary Blue**: #007AFF
- **Success Green**: #34C759
- **Warning Orange**: #FF9500
- **Error Red**: #FF3B30
- **Gray Text**: #8E8E93
- **Light Background**: #F2F2F7
- **White**: #FFFFFF

## Architecture

The widgets are designed with separation of concerns:

1. **UI Layer**: PySide6 widgets with macOS styling
2. **Business Logic**: CLI Bridge service for data operations
3. **Background Processing**: Worker threads for non-blocking operations
4. **Event System**: Qt signals and slots for component communication

### Thread Safety
- UI updates are performed on the main thread
- Data operations use background worker threads
- Thread-safe communication via Qt signals

### Performance Considerations
- Background workers prevent UI blocking
- Efficient update mechanisms (only when data changes)
- Memory management with proper widget cleanup
- Optimized animations and rendering

## Dependencies

The widgets require:
- **PySide6 >= 6.6.0**: Qt6 Python bindings
- **Python >= 3.9**: Modern Python features
- **CLI Bridge Service**: For MCP server operations

## Development

When extending these widgets:

1. **Follow Qt patterns**: Use signals/slots for communication
2. **Maintain thread safety**: Keep UI updates on main thread
3. **Handle cleanup**: Implement proper closeEvent handlers
4. **Test thoroughly**: Consider edge cases and error conditions
5. **Document changes**: Update this README for new features

## Testing

Run the widget demo to test functionality:
```bash
python -m mcp_manager_gui.examples.widget_demo
```

This will open a demonstration window with all widgets in action.