# MCP Manager GUI Icons

This directory contains SVG icons used throughout the MCP Manager GUI application. All icons are designed to follow macOS design guidelines and support both light and dark themes.

## Icon Categories

### Application Icons
- `app_icon.svg` - Main application icon with MCP Manager branding
- `app_icon.icns` - Native macOS icon format (to be generated from SVG)

### Status Indicators
- `server_online.svg` - Green indicator for running servers
- `server_offline.svg` - Gray indicator for stopped servers  
- `server_error.svg` - Red indicator for servers with errors

### UI Controls
- `search.svg` - Search icon for search fields
- `chevron-down.svg` - Dropdown indicator for combo boxes
- `arrow-right.svg` - Tree widget collapsed state
- `arrow-down.svg` - Tree widget expanded state
- `checkmark.svg` - Checkmark for selected checkboxes
- `radio-dot.svg` - Dot for selected radio buttons

### Window Controls
- `close.svg` - Window close button
- `restore.svg` - Window restore/maximize button

### Action Icons
- `add.svg` - Add/create new item
- `remove.svg` - Remove/delete item
- `settings.svg` - Settings/preferences
- `refresh.svg` - Refresh/reload data
- `info.svg` - Information indicator
- `warning.svg` - Warning indicator
- `error.svg` - Error indicator
- `success.svg` - Success indicator

### Service/Provider Icons
- `docker.svg` - Docker Desktop servers
- `npm.svg` - NPM package servers
- `claude.svg` - Claude Code integration

## Design Guidelines

### Color Scheme
- Primary: `#007AFF` (iOS/macOS blue)
- Success: `#30D158` (iOS/macOS green)
- Warning: `#FF9F0A` (iOS/macOS orange)
- Error: `#FF3B30` (iOS/macOS red)
- Secondary: `#8E8E93` (iOS/macOS gray)

### Sizing
- Standard UI icons: 16x16px
- Small UI icons: 12x12px  
- Status indicators: 24x24px
- Service icons: 20x20px
- App icon: 1024x1024px (scalable)

### Theme Support
Icons automatically adapt to dark mode through the QSS stylesheet. SVG icons use semantic colors that are handled by the theme system.

## Usage in QSS

Icons are referenced in the main stylesheet using the Qt resource system:

```css
QTreeWidget::branch:closed:has-children {
    image: url(:/icons/arrow-right.svg);
}

QLineEdit[searchField="true"] {
    background-image: url(:/icons/search.svg);
}
```

## Accessibility

All icons include proper semantic markup and support high contrast modes. Icon meanings are supplemented with text labels and tooltips where appropriate.

## File Formats

- **SVG**: Primary format for scalability and theming
- **PNG**: Rasterized versions at multiple resolutions (if needed)
- **ICNS**: Native macOS app icon format (generated from SVG)

## Generating Additional Sizes

To generate PNG versions at different sizes from the SVG files:

```bash
# Using librsvg (install with: brew install librsvg)
rsvg-convert -h 32 -w 32 app_icon.svg -o app_icon_32.png
rsvg-convert -h 64 -w 64 app_icon.svg -o app_icon_64.png

# Using ImageMagick (install with: brew install imagemagick)  
magick app_icon.svg -resize 32x32 app_icon_32.png
```

## App Icon Generation

To create the macOS app icon bundle:

```bash
# Create iconset directory
mkdir AppIcon.iconset

# Generate all required sizes
sips -z 16 16 app_icon.svg --out AppIcon.iconset/icon_16x16.png
sips -z 32 32 app_icon.svg --out AppIcon.iconset/icon_16x16@2x.png
sips -z 32 32 app_icon.svg --out AppIcon.iconset/icon_32x32.png
sips -z 64 64 app_icon.svg --out AppIcon.iconset/icon_32x32@2x.png
sips -z 128 128 app_icon.svg --out AppIcon.iconset/icon_128x128.png
sips -z 256 256 app_icon.svg --out AppIcon.iconset/icon_128x128@2x.png
sips -z 256 256 app_icon.svg --out AppIcon.iconset/icon_256x256.png
sips -z 512 512 app_icon.svg --out AppIcon.iconset/icon_256x256@2x.png
sips -z 512 512 app_icon.svg --out AppIcon.iconset/icon_512x512.png
sips -z 1024 1024 app_icon.svg --out AppIcon.iconset/icon_512x512@2x.png

# Convert to ICNS
iconutil -c icns AppIcon.iconset
```