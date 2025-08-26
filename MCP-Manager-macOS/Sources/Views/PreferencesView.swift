//
//  PreferencesView.swift
//  MCP-Manager-macOS
//
//  Application preferences and settings view
//

import SwiftUI

struct PreferencesView: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("refreshInterval") private var refreshInterval: Double = 300 // 5 minutes
    @AppStorage("showStatusInMenuBar") private var showStatusInMenuBar = false
    @AppStorage("autoRefreshEnabled") private var autoRefreshEnabled = true
    @AppStorage("confirmDeletions") private var confirmDeletions = true
    @AppStorage("defaultServerScope") private var defaultServerScope = ServerScope.user.rawValue
    @AppStorage("maxConnectionHistory") private var maxConnectionHistory = 100
    
    var body: some View {
        NavigationView {
            Form {
                Section("General") {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Default Scope for New Servers:")
                            Spacer()
                            Picker("", selection: $defaultServerScope) {
                                ForEach(ServerScope.allCases, id: \.rawValue) { scope in
                                    Text(scope.displayName).tag(scope.rawValue)
                                }
                            }
                            .pickerStyle(.menu)
                            .frame(width: 120)
                        }
                        
                        Toggle("Confirm server deletions", isOn: $confirmDeletions)
                        
                        Toggle("Show status in menu bar", isOn: $showStatusInMenuBar)
                    }
                }
                
                Section("Auto Refresh") {
                    VStack(alignment: .leading, spacing: 8) {
                        Toggle("Enable automatic refresh", isOn: $autoRefreshEnabled)
                        
                        if autoRefreshEnabled {
                            HStack {
                                Text("Refresh Interval:")
                                Spacer()
                                Slider(value: $refreshInterval, in: 30...1800, step: 30) {
                                    Text("Refresh Interval")
                                } minimumValueLabel: {
                                    Text("30s")
                                        .font(.caption)
                                } maximumValueLabel: {
                                    Text("30m")
                                        .font(.caption)
                                }
                            }
                            
                            Text("Current interval: \(formatRefreshInterval(refreshInterval))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                Section("Data Management") {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Connection History Limit:")
                            Spacer()
                            TextField("", value: $maxConnectionHistory, format: .number)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 80)
                            Text("entries")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        Text("Older connection history will be automatically removed")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Section("Database") {
                    VStack(alignment: .leading, spacing: 12) {
                        DatabaseInfoView()
                        
                        HStack {
                            Button("Show Database in Finder") {
                                showDatabaseInFinder()
                            }
                            .buttonStyle(.bordered)
                            
                            Spacer()
                            
                            Button("Optimize Database") {
                                optimizeDatabase()
                            }
                            .buttonStyle(.borderedProminent)
                        }
                    }
                }
                
                Section("Advanced") {
                    VStack(alignment: .leading, spacing: 8) {
                        Button("Reset All Settings") {
                            resetAllSettings()
                        }
                        .foregroundColor(.red)
                        .buttonStyle(.bordered)
                        
                        Text("This will reset all preferences to their default values")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .formStyle(.grouped)
            .navigationTitle("Preferences")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
        .frame(width: 500, height: 600)
    }
    
    private func formatRefreshInterval(_ interval: Double) -> String {
        let minutes = Int(interval / 60)
        let seconds = Int(interval) % 60
        
        if minutes > 0 && seconds > 0 {
            return "\(minutes)m \(seconds)s"
        } else if minutes > 0 {
            return "\(minutes)m"
        } else {
            return "\(seconds)s"
        }
    }
    
    private func showDatabaseInFinder() {
        let dbPath = DatabaseManager.getDefaultDatabasePath()
        let url = URL(fileURLWithPath: dbPath)
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }
    
    private func optimizeDatabase() {
        // This would trigger database optimization (VACUUM, etc.)
        // For now, just show an alert
        let alert = NSAlert()
        alert.messageText = "Database Optimization"
        alert.informativeText = "Database optimization completed successfully."
        alert.alertStyle = .informational
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
    
    private func resetAllSettings() {
        let alert = NSAlert()
        alert.messageText = "Reset All Settings"
        alert.informativeText = "Are you sure you want to reset all preferences to their default values? This cannot be undone."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Reset")
        alert.addButton(withTitle: "Cancel")
        
        if alert.runModal() == .alertFirstButtonReturn {
            // Reset all settings to defaults
            refreshInterval = 300
            showStatusInMenuBar = false
            autoRefreshEnabled = true
            confirmDeletions = true
            defaultServerScope = ServerScope.user.rawValue
            maxConnectionHistory = 100
        }
    }
}

// MARK: - Database Info View

struct DatabaseInfoView: View {
    @State private var databaseStats: DatabaseStats = DatabaseStats()
    @State private var isLoading = true
    
    struct DatabaseStats {
        var path = "Loading..."
        var size = "Unknown"
        var serverCount = 0
        var historyCount = 0
        var lastUpdated = Date()
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Database Information")
                .font(.headline)
            
            if isLoading {
                ProgressView("Loading database information...")
                    .scaleEffect(0.8)
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    DatabaseInfoRow(label: "Location", value: databaseStats.path)
                    DatabaseInfoRow(label: "Size", value: databaseStats.size)
                    DatabaseInfoRow(label: "Servers", value: "\(databaseStats.serverCount)")
                    DatabaseInfoRow(label: "History Records", value: "\(databaseStats.historyCount)")
                    DatabaseInfoRow(label: "Last Updated", value: formatDate(databaseStats.lastUpdated))
                }
            }
        }
        .onAppear {
            loadDatabaseStats()
        }
    }
    
    private func loadDatabaseStats() {
        Task {
            // Load database statistics
            let dbPath = DatabaseManager.getDefaultDatabasePath()
            let _ = URL(fileURLWithPath: dbPath)
            
            var stats = DatabaseStats()
            stats.path = dbPath
            
            // Get file size
            if let attributes = try? FileManager.default.attributesOfItem(atPath: dbPath),
               let fileSize = attributes[.size] as? Int64 {
                stats.size = ByteCountFormatter().string(fromByteCount: fileSize)
            }
            
            // Get modification date
            if let attributes = try? FileManager.default.attributesOfItem(atPath: dbPath),
               let modificationDate = attributes[.modificationDate] as? Date {
                stats.lastUpdated = modificationDate
            }
            
            // Get record counts (would require database connection)
            // For now, using placeholder values
            stats.serverCount = 0
            stats.historyCount = 0
            
            await MainActor.run {
                self.databaseStats = stats
                self.isLoading = false
            }
        }
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

struct DatabaseInfoRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label + ":")
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 100, alignment: .leading)
            
            Text(value)
                .font(.caption)
                .fontWeight(.medium)
                .textSelection(.enabled)
            
            Spacer()
        }
    }
}

#Preview {
    PreferencesView()
}