"""
Modern py-cui based TUI for MCP Manager.

Provides a clean, keyboard-driven interface similar to whiptail
with arrow key navigation and simple interactions.
"""

import asyncio
import threading
from typing import List, Optional
import py_cui

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class MCPManagerTUI:
    """Modern py-cui TUI for MCP Manager."""
    
    def __init__(self):
        # Create 6x4 grid for the interface
        self.root = py_cui.PyCUI(6, 4)
        self.root.set_title("MCP Manager - Server Management")
        
        # Core components
        self.manager = SimpleMCPManager()
        self.discovery = ServerDiscovery()
        self.servers: List[Server] = []
        self.selected_server: Optional[Server] = None
        
        # UI state
        self.current_view = "main"  # main, servers, discovery, add
        self.selected_servers: List[int] = []  # Multi-select indices
        self.multi_select_mode = False
        
        self._setup_ui()
        self._setup_keybindings()
    
    def _setup_ui(self):
        """Setup the UI layout with widgets."""
        
        # Title and status bar
        self.title_label = self.root.add_label("MCP Manager v1.0", 0, 0, column_span=4)
        self.status_label = self.root.add_label("Ready", 5, 0, column_span=4)
        
        # Main menu (left side)
        self.main_menu = self.root.add_scroll_menu("Main Menu", 1, 0, row_span=3)
        self.main_menu.add_item("📋 Manage Servers")
        self.main_menu.add_item("➕ Add Server") 
        self.main_menu.add_item("🔍 Discover & Install")
        self.main_menu.add_item("📦 Install Package")
        self.main_menu.add_item("🧹 Cleanup Config")
        self.main_menu.add_item("ℹ️  System Info")
        self.main_menu.add_item("❓ Help")
        self.main_menu.add_item("🚪 Exit")
        
        # Server list (right side)
        self.server_list = self.root.add_scroll_menu("Servers", 1, 1, row_span=3, column_span=2)
        
        # Action buttons (bottom right)
        self.action_menu = self.root.add_scroll_menu("Actions", 1, 3, row_span=3)
        self.action_menu.add_item("🔄 Refresh")
        self.action_menu.add_item("✅ Enable")
        self.action_menu.add_item("❌ Disable") 
        self.action_menu.add_item("🗑️  Remove")
        self.action_menu.add_item("📝 Details")
        self.action_menu.add_item("🔲 Multi-Select")
        self.action_menu.add_item("📋 Select All")
        self.action_menu.add_item("🚫 Clear Selection")
        
        # Info panel (bottom)
        self.info_panel = self.root.add_text_block("Info", 4, 0, column_span=4)
        self.info_panel.set_text("Use arrow keys to navigate, Enter to select, Escape to go back")
        
        # Set up callbacks
        self.main_menu.add_key_command(py_cui.keys.KEY_ENTER, self._handle_main_menu)
        self.server_list.add_key_command(py_cui.keys.KEY_ENTER, self._select_server)
        self.action_menu.add_key_command(py_cui.keys.KEY_ENTER, self._handle_action)
        
        # Load servers on startup
        self._load_servers_async()
    
    def _setup_keybindings(self):
        """Setup global key bindings."""
        self.root.add_key_command(py_cui.keys.KEY_Q_LOWER, self._exit)
        self.root.add_key_command(py_cui.keys.KEY_F5, self._refresh)
        self.root.add_key_command(py_cui.keys.KEY_ESCAPE, self._go_back)
        
        # Multi-select keybindings
        self.server_list.add_key_command(py_cui.keys.KEY_SPACE, self._toggle_server_selection)
        self.root.add_key_command(py_cui.keys.KEY_CTRL_A, self._select_all_servers)
        self.root.add_key_command(py_cui.keys.KEY_CTRL_U, self._clear_selection)
    
    def _load_servers_async(self):
        """Load servers asynchronously."""
        def load_servers():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                servers = loop.run_until_complete(self.manager.list_servers())
                self.servers = servers
                
                # Update UI on main thread
                self.root.run_on_exit(lambda: self._update_server_list())
                
            except Exception as e:
                self._set_status(f"Error loading servers: {e}", "red")
        
        thread = threading.Thread(target=load_servers, daemon=True)
        thread.start()
    
    def _update_server_list(self):
        """Update the server list display."""
        self.server_list.clear()
        
        if not self.servers:
            self.server_list.add_item("No servers configured")
            return
        
        for i, server in enumerate(self.servers):
            status = "✓" if server.enabled else "✗"
            selected = "☑" if i in self.selected_servers else "☐"
            multi_prefix = f"{selected} " if self.multi_select_mode else ""
            server_item = f"{multi_prefix}{status} {server.name} ({server.server_type.value})"
            self.server_list.add_item(server_item)
        
        selected_count = len(self.selected_servers)
        if self.multi_select_mode and selected_count > 0:
            self._set_status(f"Multi-select: {selected_count} server(s) selected")
        else:
            self._set_status(f"Loaded {len(self.servers)} servers")
    
    def _handle_main_menu(self):
        """Handle main menu selection."""
        selection = self.main_menu.get()
        
        if "Manage Servers" in selection:
            self._refresh_servers()
        elif "Add Server" in selection:
            self._show_add_server()
        elif "Discover" in selection:
            self._show_discovery()
        elif "Install Package" in selection:
            self._show_install_package()
        elif "Cleanup" in selection:
            self._cleanup_config()
        elif "System Info" in selection:
            self._show_system_info()
        elif "Help" in selection:
            self._show_help()
        elif "Exit" in selection:
            self._exit()
    
    def _select_server(self):
        """Handle server selection."""
        if not self.servers:
            return
            
        selected_index = self.server_list.get_selected_item_index()
        if 0 <= selected_index < len(self.servers):
            if self.multi_select_mode:
                # In multi-select mode, toggle selection
                self._toggle_server_selection()
            else:
                # Single select mode
                self.selected_server = self.servers[selected_index]
                server = self.selected_server
                info_text = f"Selected: {server.name}\\n"
                info_text += f"Type: {server.server_type.value}\\n"
                info_text += f"Status: {'Enabled' if server.enabled else 'Disabled'}\\n"
                info_text += f"Command: {server.command[:80]}..."
                self.info_panel.set_text(info_text)
    
    def _handle_action(self):
        """Handle action menu selection."""
        selection = self.action_menu.get()
        
        if "Refresh" in selection:
            self._refresh_servers()
        elif "Multi-Select" in selection:
            self._toggle_multi_select_mode()
        elif "Select All" in selection:
            self._select_all_servers()
        elif "Clear Selection" in selection:
            self._clear_selection()
        elif "Enable" in selection:
            self._enable_servers()
        elif "Disable" in selection:
            self._disable_servers()
        elif "Remove" in selection:
            self._confirm_remove_servers()
        elif "Details" in selection:
            self._show_server_details()
    
    def _refresh_servers(self):
        """Refresh the server list."""
        self._set_status("Refreshing servers...", "cyan")
        self._load_servers_async()
    
    def _get_target_servers(self):
        """Get servers to operate on (selected servers in multi-select mode, or current server)."""
        if self.multi_select_mode and self.selected_servers:
            return [self.servers[i] for i in self.selected_servers]
        elif self.selected_server:
            return [self.selected_server]
        else:
            return []
    
    def _enable_servers(self):
        """Enable the selected server(s)."""
        target_servers = self._get_target_servers()
        if not target_servers:
            self._set_status("No servers selected", "yellow")
            return
        
        def enable_servers():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                success_count = 0
                for server in target_servers:
                    try:
                        loop.run_until_complete(self.manager.enable_server(server.name))
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to enable {server.name}: {e}")
                
                if success_count == len(target_servers):
                    self._set_status(f"Enabled {success_count} server(s)", "green")
                else:
                    self._set_status(f"Enabled {success_count}/{len(target_servers)} servers", "yellow")
                
                self._load_servers_async()
            except Exception as e:
                self._set_status(f"Failed to enable servers: {e}", "red")
        
        thread = threading.Thread(target=enable_servers, daemon=True)
        thread.start()
    
    def _disable_servers(self):
        """Disable the selected server(s)."""
        target_servers = self._get_target_servers()
        if not target_servers:
            self._set_status("No servers selected", "yellow")
            return
            
        def disable_servers():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                success_count = 0
                for server in target_servers:
                    try:
                        loop.run_until_complete(self.manager.disable_server(server.name))
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to disable {server.name}: {e}")
                
                if success_count == len(target_servers):
                    self._set_status(f"Disabled {success_count} server(s)", "green")
                else:
                    self._set_status(f"Disabled {success_count}/{len(target_servers)} servers", "yellow")
                
                self._load_servers_async()
            except Exception as e:
                self._set_status(f"Failed to disable servers: {e}", "red")
        
        thread = threading.Thread(target=disable_servers, daemon=True)
        thread.start()
    
    def _confirm_remove_servers(self):
        """Show confirmation dialog for server removal."""
        target_servers = self._get_target_servers()
        if not target_servers:
            self._set_status("No servers selected", "yellow")
            return
        
        if len(target_servers) == 1:
            server_text = f"'{target_servers[0].name}'"
        else:
            server_text = f"{len(target_servers)} servers"
            
        # Create confirmation popup
        popup = self.root.create_yes_no_popup(
            f"Remove Server(s)",
            f"Are you sure you want to remove {server_text}?\\n\\nThis action cannot be undone."
        )
        popup.add_command(self._remove_servers)
    
    def _remove_servers(self):
        """Remove the selected server(s)."""
        target_servers = self._get_target_servers()
        if not target_servers:
            return
            
        def remove_servers():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                success_count = 0
                for server in target_servers:
                    try:
                        loop.run_until_complete(self.manager.remove_server(server.name))
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to remove {server.name}: {e}")
                
                if success_count == len(target_servers):
                    self._set_status(f"Removed {success_count} server(s)", "green")
                else:
                    self._set_status(f"Removed {success_count}/{len(target_servers)} servers", "yellow")
                
                self.selected_server = None
                self.selected_servers.clear()
                self.info_panel.set_text("Use arrow keys to navigate, Enter to select, Escape to go back")
                self._load_servers_async()
            except Exception as e:
                self._set_status(f"Failed to remove servers: {e}", "red")
        
        thread = threading.Thread(target=remove_servers, daemon=True)
        thread.start()
    
    def _show_server_details(self):
        """Show detailed server information."""
        if not self.selected_server:
            return
            
        server = self.selected_server
        details = f"Server Details: {server.name}\\n\\n"
        details += f"Type: {server.server_type.value}\\n"
        details += f"Scope: {server.scope.value}\\n"
        details += f"Status: {'Enabled' if server.enabled else 'Disabled'}\\n"
        details += f"Command: {server.command}\\n"
        if server.args:
            details += f"Arguments: {' '.join(server.args)}\\n"
        if server.description:
            details += f"Description: {server.description}\\n"
        
        popup = self.root.create_info_popup("Server Details", details)
    
    def _show_add_server(self):
        """Show add server dialog."""
        # Create form popup for adding server
        popup_text = "Add New Server\\n\\n"
        popup_text += "This feature opens the CLI add command.\\n"
        popup_text += "Use: mcp-manager add <name> <command>"
        
        popup = self.root.create_info_popup("Add Server", popup_text)
    
    def _show_discovery(self):
        """Show discovery interface."""
        popup_text = "Server Discovery\\n\\n"
        popup_text += "This feature opens the CLI discovery.\\n"
        popup_text += "Use: mcp-manager discover --query <search>"
        
        popup = self.root.create_info_popup("Discovery", popup_text)
    
    def _show_install_package(self):
        """Show package installation."""
        popup_text = "Install Package\\n\\n"
        popup_text += "Install servers by package ID.\\n"
        popup_text += "Use: mcp-manager install-package <id>"
        
        popup = self.root.create_info_popup("Install Package", popup_text)
    
    def _cleanup_config(self):
        """Cleanup configuration."""
        popup_text = "Configuration Cleanup\\n\\n"
        popup_text += "This will fix broken MCP configurations.\\n"
        popup_text += "Use: mcp-manager cleanup"
        
        popup = self.root.create_info_popup("Cleanup Config", popup_text)
    
    def _show_system_info(self):
        """Show system information."""
        info = self.manager.get_system_info()
        
        details = f"System Information\\n\\n"
        details += f"Python: {info.python_version}\\n"
        details += f"Platform: {info.platform}\\n\\n"
        details += f"Dependencies:\\n"
        details += f"Claude CLI: {'✓' if info.claude_cli_available else '✗'} {info.claude_cli_version or 'N/A'}\\n"
        details += f"NPM: {'✓' if info.npm_available else '✗'} {info.npm_version or 'N/A'}\\n"
        details += f"Docker: {'✓' if info.docker_available else '✗'} {info.docker_version or 'N/A'}\\n"
        details += f"Git: {'✓' if info.git_available else '✗'} {info.git_version or 'N/A'}\\n"
        
        popup = self.root.create_info_popup("System Info", details)
    
    def _show_help(self):
        """Show help information."""
        help_text = "MCP Manager Help\\n\\n"
        help_text += "Navigation:\\n"
        help_text += "• Arrow keys - Navigate between widgets\\n"
        help_text += "• Tab/Shift+Tab - Cycle through widgets\\n"
        help_text += "• Enter - Select item or activate widget\\n"
        help_text += "• Escape - Go back or exit focus mode\\n\\n"
        help_text += "Multi-Select:\\n"
        help_text += "• Space - Toggle server selection\\n"
        help_text += "• Ctrl+A - Select all servers\\n"
        help_text += "• Ctrl+U - Clear selection\\n\\n"
        help_text += "Shortcuts:\\n"
        help_text += "• F5 - Refresh server list\\n"
        help_text += "• q - Quit application\\n\\n"
        help_text += "Workflow:\\n"
        help_text += "1. Use Multi-Select action to enable multi-selection\\n"
        help_text += "2. Select multiple servers with Space key\\n"
        help_text += "3. Choose bulk actions (Enable/Disable/Remove)\\n"
        help_text += "4. Use main menu for other operations"
        
        popup = self.root.create_info_popup("Help", help_text)
    
    def _refresh(self):
        """Refresh interface (F5 key)."""
        self._refresh_servers()
    
    def _toggle_multi_select_mode(self):
        """Toggle multi-select mode on/off."""
        self.multi_select_mode = not self.multi_select_mode
        if not self.multi_select_mode:
            self.selected_servers.clear()
        
        self._update_server_list()
        
        if self.multi_select_mode:
            self._set_status("Multi-select mode enabled - Use Space to select/deselect")
            self.info_panel.set_text("Multi-Select Mode:\\n• Space - Toggle selection\\n• Ctrl+A - Select all\\n• Ctrl+U - Clear selection")
        else:
            self._set_status("Multi-select mode disabled")
            self.info_panel.set_text("Use arrow keys to navigate, Enter to select, Escape to go back")
    
    def _toggle_server_selection(self):
        """Toggle selection of current server in multi-select mode."""
        if not self.multi_select_mode:
            return
            
        selected_index = self.server_list.get_selected_item_index()
        if 0 <= selected_index < len(self.servers):
            if selected_index in self.selected_servers:
                self.selected_servers.remove(selected_index)
            else:
                self.selected_servers.append(selected_index)
            
            self._update_server_list()
    
    def _select_all_servers(self):
        """Select all servers in multi-select mode."""
        if not self.multi_select_mode:
            self._toggle_multi_select_mode()
        
        self.selected_servers = list(range(len(self.servers)))
        self._update_server_list()
    
    def _clear_selection(self):
        """Clear all server selections."""
        self.selected_servers.clear()
        self.selected_server = None
        self._update_server_list()
        self.info_panel.set_text("Use arrow keys to navigate, Enter to select, Escape to go back")
        
        if self.multi_select_mode:
            self._set_status("Selection cleared - Multi-select mode still active")
        else:
            self._set_status("Selection cleared")
    
    def _go_back(self):
        """Go back or clear selection (Escape key)."""
        if self.multi_select_mode:
            self._toggle_multi_select_mode()
        elif self.selected_server or self.selected_servers:
            self._clear_selection()
        else:
            self._set_status("Press 'q' to quit")
    
    def _set_status(self, message: str, color: str = "white"):
        """Set status bar message."""
        self.status_label.set_text(f"Status: {message}")
        # py-cui doesn't have easy color changing, so we just update text
    
    def _exit(self):
        """Exit the application."""
        exit()
    
    def run(self):
        """Start the TUI application."""
        try:
            self.root.start()
        except KeyboardInterrupt:
            pass


def main():
    """Main entry point for py-cui TUI."""
    try:
        app = MCPManagerTUI()
        app.run()
    except Exception as e:
        print(f"TUI Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()