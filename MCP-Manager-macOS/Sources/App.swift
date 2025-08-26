//
//  App.swift
//  MCP-Manager-macOS
//
//  Main application entry point for the native Swift MCP Manager macOS application
//

import SwiftUI

@main
struct MCPManagerApp: App {
    
    // App delegate for macOS-specific functionality
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 800, minHeight: 600)
                .onAppear {
                    setupDatabase()
                }
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .commands {
            // Custom menu commands
            CommandGroup(replacing: .newItem) {}
            
            CommandGroup(after: .newItem) {
                Button("Add Server...") {
                    // This would trigger the add server sheet
                    // Implementation would need to be coordinated with ContentView
                }
                .keyboardShortcut("n", modifiers: .command)
                
                Button("Refresh All Servers") {
                    // This would trigger a refresh of all server statuses
                }
                .keyboardShortcut("r", modifiers: .command)
                
                Divider()
                
                Button("Sync Docker Desktop Servers") {
                    // This would sync Docker Desktop servers
                }
                
                Button("Enable All Servers") {
                    // This would enable all servers
                }
                
                Button("Disable All Servers") {
                    // This would disable all servers
                }
            }
        }
        
        // Settings window
        Settings {
            PreferencesView()
        }
    }
    
    private func setupDatabase() {
        Task {
            let _ = DatabaseManager()
            print("✅ MCP Manager database initialized successfully")
            
            // Log app startup
            print("🚀 MCP Manager for macOS started")
            print("📁 Database: \(DatabaseManager.getDefaultDatabasePath())")
        }
    }
}

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        print("🎯 MCP Manager application launched")
        
        // Set app name in menu bar
        if let app = NSApplication.shared.windows.first {
            app.title = "MCP Manager"
        }
    }
    
    func applicationWillTerminate(_ notification: Notification) {
        print("👋 MCP Manager application terminating")
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

// MARK: - Menu Bar Status (Future Enhancement)

extension AppDelegate {
    
    // This would be used for menu bar status functionality
    private func setupMenuBarStatus() {
        // Implementation for menu bar status item
        // Would show server count, health status, etc.
    }
}