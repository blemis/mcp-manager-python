# MCP Manager GUI Resources

This directory contains all resources needed for the MCP Manager GUI application, including stylesheets, icons, and app metadata. The resources are designed to provide a professional macOS-native experience.

## Directory Structure

```
resources/
├── __init__.py              # Resource management utilities
├── Info.plist               # macOS app metadata
├── resources.qrc            # Qt resource bundle definition
├── example_usage.py         # Example of how to use resources
├── styles/
│   └── main.qss            # Main application stylesheet
└── icons/
    ├── README.md           # Icon documentation
    ├── app_icon.svg        # Main application icon
    ├── server_*.svg        # Server status icons
    ├── *.svg               # UI control and action icons
    └── [provider icons]    # Docker, NPM, Claude icons
```

## Quick Start

### 1. Basic Usage

```python
from mcp_manager_gui.resources import (
    load_stylesheet, load_icon, apply_theme,
    setup_app_resources, Icons, Themes, Styles
)

# Initialize resources (call once at app startup)
setup_app_resources()

# Apply main stylesheet
app.setStyleSheet(load_stylesheet("main.qss"))

# Load icons
refresh_icon = load_icon(Icons.REFRESH)
button.setIcon(refresh_icon)
```

### 2. Applying Styles

```python
# Set widget properties for styling
button.setProperty("buttonStyle", Styles.BUTTON_PRIMARY)
frame.setProperty("frameStyle", Styles.FRAME_CARD) 
label.setProperty("statusType", Styles.STATUS_SUCCESS)

# Apply themes
apply_theme(widget, Themes.DARK)
apply_theme(widget, Themes.LIGHT)
```

### 3. Using Icons

```python
# Load icons by name
online_icon = load_icon(Icons.SERVER_ONLINE)
settings_icon = load_icon(Icons.SETTINGS)

# Load as pixmaps with custom size
pixmap = load_pixmap(Icons.APP_ICON, (64, 64))
```

## Styling System

### Theme Support

The styling system supports both light and dark themes that automatically adapt to macOS system preferences:

- **Light Theme**: Default macOS light appearance
- **Dark Theme**: macOS dark appearance with proper contrast

### Widget Styles

#### Buttons

```python
# Primary action button (blue)
button.setProperty("buttonStyle", Styles.BUTTON_PRIMARY)

# Secondary button (gray)
button.setProperty("buttonStyle", Styles.BUTTON_SECONDARY)

# Destructive action (red)
button.setProperty("buttonStyle", Styles.BUTTON_DESTRUCTIVE)

# Icon-only button
button.setProperty("buttonStyle", Styles.BUTTON_ICON)
```

#### Cards and Panels

```python
# Content card with rounded corners and shadow
frame.setProperty("frameStyle", Styles.FRAME_CARD)

# Sidebar panel
frame.setProperty("frameStyle", Styles.FRAME_SIDEBAR)

# Server status card
frame.setProperty("widgetType", Styles.WIDGET_SERVER_CARD)
```

#### Status Indicators

```python
# Status labels
label.setProperty("statusType", Styles.STATUS_SUCCESS)  # Green
label.setProperty("statusType", Styles.STATUS_WARNING)  # Orange
label.setProperty("statusType", Styles.STATUS_ERROR)    # Red
label.setProperty("statusType", Styles.STATUS_INFO)     # Blue

# Status badges
label.setProperty("badgeStyle", Styles.BADGE_SUCCESS)
```

### Search Fields

```python
# Search field with magnifying glass icon
search_field.setProperty("searchField", True)
```

## Icon System

### Available Icons

#### Status Icons
- `Icons.SERVER_ONLINE` - Green server status
- `Icons.SERVER_OFFLINE` - Gray server status  
- `Icons.SERVER_ERROR` - Red server with warning

#### UI Controls
- `Icons.SEARCH` - Magnifying glass
- `Icons.CHEVRON_DOWN` - Dropdown arrow
- `Icons.ARROW_RIGHT` / `Icons.ARROW_DOWN` - Tree expansion
- `Icons.CHECKMARK` - Checkbox checked state
- `Icons.RADIO_DOT` - Radio button selected

#### Actions
- `Icons.ADD` - Plus icon for adding items
- `Icons.REMOVE` - Minus icon for removing items
- `Icons.SETTINGS` - Gear icon for preferences
- `Icons.REFRESH` - Circular arrow for reloading
- `Icons.INFO` / `Icons.WARNING` / `Icons.ERROR` / `Icons.SUCCESS`

#### Services
- `Icons.DOCKER` - Docker whale logo
- `Icons.NPM` - NPM package manager
- `Icons.CLAUDE` - Claude AI integration

### Icon Usage Patterns

```python
# Button with icon and text
button = QPushButton("Add Server")
button.setIcon(load_icon(Icons.ADD))

# Icon-only button with tooltip
icon_button = QPushButton()
icon_button.setIcon(load_icon(Icons.SETTINGS))
icon_button.setToolTip("Settings")
icon_button.setProperty("buttonStyle", Styles.BUTTON_ICON)

# Status indicator
status_icon = QLabel()
status_icon.setPixmap(load_icon(Icons.SERVER_ONLINE).pixmap(16, 16))
```

## macOS Integration

### App Metadata (Info.plist)

The `Info.plist` file provides proper macOS integration:

- **Bundle Identifier**: `com.mcp-manager.gui`
- **App Category**: Developer Tools
- **File Associations**: JSON and TOML configuration files
- **URL Scheme**: `mcp-manager://` protocol support
- **Permissions**: Network access, file system access
- **Hardened Runtime**: Security entitlements

### Native macOS Features

- **Dark Mode Support**: Automatic theme switching
- **Retina Display**: High-resolution icon support
- **Accessibility**: VoiceOver and keyboard navigation
- **Services Integration**: System-wide services menu
- **Spotlight**: Custom file type indexing

### App Store Compliance

The configuration includes App Store-ready settings:
- Sandboxing support (commented out, can be enabled)
- Privacy usage descriptions
- App Transport Security
- Reduced attack surface

## Performance Optimization

### Resource Caching

The resource manager includes intelligent caching:

```python
# Icons and stylesheets are cached after first load
icon = load_icon(Icons.SETTINGS)  # Loads from file
icon2 = load_icon(Icons.SETTINGS) # Returns cached version

# Clear cache if needed
resource_manager.clear_cache()
```

### Preloading

Common resources are preloaded for better startup performance:

```python
# Preload frequently used icons
resource_manager.preload_common_icons()
```

## Development Workflow

### Adding New Icons

1. Create SVG icon following design guidelines (see `icons/README.md`)
2. Add to `Icons` class in `__init__.py`
3. Update `resources.qrc` file
4. Optionally add to preload list

### Updating Styles

1. Edit `styles/main.qss`
2. Add new style constants to `Styles` class if needed
3. Test with both light and dark themes
4. Verify accessibility compliance

### Theme Development

```python
# Test theme switching
apply_theme(widget, Themes.DARK)
widget.style().unpolish(widget)
widget.style().polish(widget)
widget.update()
```

## Accessibility

### High Contrast Support

```python
# Enable high contrast mode
widget.setProperty("highContrast", True)
```

### Reduced Motion

```python
# Disable animations for accessibility
widget.setProperty("reducedMotion", True)
```

### Focus Indicators

All interactive elements include proper focus indicators for keyboard navigation.

## Troubleshooting

### Common Issues

1. **Icons not loading**: Check file paths and ensure SVG files are valid
2. **Styles not applying**: Verify property names and call `style().polish()`
3. **Theme not switching**: Ensure theme property is set and widget is updated

### Debug Mode

```python
# Enable resource debug logging
import logging
logging.getLogger('mcp_manager_gui.resources').setLevel(logging.DEBUG)
```

### Resource Validation

```python
# Validate all resources are loadable
from mcp_manager_gui.resources import resource_manager
resource_manager.validate_resources()  # Custom validation method
```

## Examples

See `example_usage.py` for a complete working example showing:
- Theme switching
- All button styles
- Status indicators
- Server status cards
- Input controls
- Icon usage patterns

## Integration with PyQt6

The resource system is designed for PyQt6 but can be adapted for other Qt bindings:

```python
# PyQt6 (default)
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

# PySide6 (alternative)
# from PySide6.QtWidgets import QApplication  
# from PySide6.QtGui import QIcon
```