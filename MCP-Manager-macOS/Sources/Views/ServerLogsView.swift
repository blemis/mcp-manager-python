//
//  ServerLogsView.swift
//  MCP-Manager-macOS
//
//  View for displaying server logs and connection history
//

import SwiftUI

struct ServerLogsView: View {
    let server: MCPServer
    @Environment(\.dismiss) private var dismiss
    
    @State private var selectedTab = 0
    @State private var isLoading = true
    @State private var connectionHistory: [ConnectionHistoryEntry] = []
    @State private var realtimeLogs: [LogEntry] = []
    @State private var isMonitoring = false
    
    struct ConnectionHistoryEntry: Identifiable {
        let id = UUID()
        let timestamp: Date
        let status: ServerStatus
        let responseTime: Double?
        let errorMessage: String?
        let toolCount: Int?
    }
    
    struct LogEntry: Identifiable {
        let id = UUID()
        let timestamp: Date
        let level: LogLevel
        let message: String
        
        enum LogLevel: String, CaseIterable {
            case debug = "DEBUG"
            case info = "INFO"
            case warning = "WARNING"
            case error = "ERROR"
            
            var color: Color {
                switch self {
                case .debug: return .secondary
                case .info: return .primary
                case .warning: return .orange
                case .error: return .red
                }
            }
        }
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Tab picker
                Picker("View", selection: $selectedTab) {
                    Text("Connection History").tag(0)
                    Text("Real-time Logs").tag(1)
                }
                .pickerStyle(.segmented)
                .padding()
                
                Divider()
                
                // Content based on selected tab
                Group {
                    switch selectedTab {
                    case 0:
                        ConnectionHistoryView(
                            server: server,
                            connectionHistory: $connectionHistory,
                            isLoading: $isLoading
                        )
                    case 1:
                        RealTimeLogsView(
                            server: server,
                            realtimeLogs: $realtimeLogs,
                            isMonitoring: $isMonitoring
                        )
                    default:
                        EmptyView()
                    }
                }
            }
            .navigationTitle("\(server.name) Logs")
            .toolbar {
                ToolbarItemGroup(placement: .primaryAction) {
                    if selectedTab == 0 {
                        Button("Refresh History") {
                            loadConnectionHistory()
                        }
                        .disabled(isLoading)
                    } else {
                        Button(isMonitoring ? "Stop Monitoring" : "Start Monitoring") {
                            toggleMonitoring()
                        }
                        .foregroundColor(isMonitoring ? .red : .green)
                    }
                }
                
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") {
                        dismiss()
                    }
                }
            }
        }
        .frame(width: 700, height: 500)
        .onAppear {
            loadConnectionHistory()
        }
    }
    
    private func loadConnectionHistory() {
        isLoading = true
        
        Task {
            // Simulate loading connection history from database
            // In a real implementation, this would query the mcp_connection_history table
            try? await Task.sleep(for: .seconds(1))
            
            let sampleHistory = [
                ConnectionHistoryEntry(
                    timestamp: Date().addingTimeInterval(-300),
                    status: .connected,
                    responseTime: 45.2,
                    errorMessage: nil,
                    toolCount: 12
                ),
                ConnectionHistoryEntry(
                    timestamp: Date().addingTimeInterval(-600),
                    status: .failed,
                    responseTime: nil,
                    errorMessage: "Connection timeout",
                    toolCount: nil
                ),
                ConnectionHistoryEntry(
                    timestamp: Date().addingTimeInterval(-900),
                    status: .connected,
                    responseTime: 52.1,
                    errorMessage: nil,
                    toolCount: 12
                )
            ]
            
            await MainActor.run {
                self.connectionHistory = sampleHistory
                self.isLoading = false
            }
        }
    }
    
    private func toggleMonitoring() {
        isMonitoring.toggle()
        
        if isMonitoring {
            startRealTimeMonitoring()
        } else {
            stopRealTimeMonitoring()
        }
    }
    
    private func startRealTimeMonitoring() {
        // Start real-time log monitoring
        // In a real implementation, this would connect to the server's log output
        
        Task {
            while isMonitoring {
                let randomMessages = [
                    "Server started successfully",
                    "New connection established",
                    "Processing request: list_tools",
                    "Tool execution completed",
                    "Connection closed by client",
                    "Received ping request",
                    "Heartbeat sent"
                ]
                
                let levels: [LogEntry.LogLevel] = [.info, .debug, .warning]
                
                let newEntry = LogEntry(
                    timestamp: Date(),
                    level: levels.randomElement() ?? .info,
                    message: randomMessages.randomElement() ?? "Unknown log message"
                )
                
                await MainActor.run {
                    realtimeLogs.append(newEntry)
                    
                    // Keep only last 100 log entries
                    if realtimeLogs.count > 100 {
                        realtimeLogs.removeFirst()
                    }
                }
                
                try? await Task.sleep(for: .seconds(Double.random(in: 1...5)))
            }
        }
    }
    
    private func stopRealTimeMonitoring() {
        // Stop real-time monitoring
        // The Task will exit when isMonitoring becomes false
    }
}

// MARK: - Connection History View

struct ConnectionHistoryView: View {
    let server: MCPServer
    @Binding var connectionHistory: [ServerLogsView.ConnectionHistoryEntry]
    @Binding var isLoading: Bool
    
    var body: some View {
        VStack {
            if isLoading {
                ProgressView("Loading connection history...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if connectionHistory.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.system(size: 48))
                        .foregroundColor(.secondary)
                    
                    Text("No Connection History")
                        .font(.title2)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)
                    
                    Text("Connection history will appear here once the server has been checked.")
                        .font(.body)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(connectionHistory) { entry in
                    ConnectionHistoryRow(entry: entry)
                }
                .listStyle(.inset)
            }
        }
    }
}

struct ConnectionHistoryRow: View {
    let entry: ServerLogsView.ConnectionHistoryEntry
    
    var body: some View {
        HStack(spacing: 12) {
            // Status indicator
            Circle()
                .fill(statusColor)
                .frame(width: 10, height: 10)
            
            // Main content
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(entry.status.displayName)
                        .font(.body)
                        .fontWeight(.medium)
                        .foregroundColor(statusColor)
                    
                    Spacer()
                    
                    Text(formatTimestamp(entry.timestamp))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                if let responseTime = entry.responseTime {
                    Text("Response time: \(String(format: "%.1f", responseTime)) ms")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                if let toolCount = entry.toolCount {
                    Text("\(toolCount) tool\(toolCount == 1 ? "" : "s") available")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                if let error = entry.errorMessage {
                    Text("Error: \(error)")
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
        }
        .padding(.vertical, 4)
    }
    
    private var statusColor: Color {
        switch entry.status {
        case .connected: return .green
        case .failed: return .red
        case .timeout: return .orange
        case .unknown: return .gray
        }
    }
    
    private func formatTimestamp(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .none
        formatter.timeStyle = .medium
        return formatter.string(from: date)
    }
}

// MARK: - Real Time Logs View

struct RealTimeLogsView: View {
    let server: MCPServer
    @Binding var realtimeLogs: [ServerLogsView.LogEntry]
    @Binding var isMonitoring: Bool
    
    @State private var selectedLogLevel: ServerLogsView.LogEntry.LogLevel? = nil
    @State private var searchText = ""
    @State private var autoScroll = true
    
    private var filteredLogs: [ServerLogsView.LogEntry] {
        realtimeLogs.filter { entry in
            // Level filter
            if let selectedLevel = selectedLogLevel, entry.level != selectedLevel {
                return false
            }
            
            // Text search
            if !searchText.isEmpty {
                return entry.message.localizedCaseInsensitiveContains(searchText)
            }
            
            return true
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Filters
            HStack {
                // Search
                TextField("Search logs...", text: $searchText)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 200)
                
                // Level filter
                Picker("Log Level", selection: $selectedLogLevel) {
                    Text("All Levels").tag(ServerLogsView.LogEntry.LogLevel?.none)
                    ForEach(ServerLogsView.LogEntry.LogLevel.allCases, id: \.self) { level in
                        Text(level.rawValue).tag(ServerLogsView.LogEntry.LogLevel?.some(level))
                    }
                }
                .pickerStyle(.menu)
                .frame(width: 120)
                
                Spacer()
                
                // Auto-scroll toggle
                Toggle("Auto-scroll", isOn: $autoScroll)
                
                // Clear logs
                Button("Clear") {
                    realtimeLogs.removeAll()
                }
                .buttonStyle(.bordered)
            }
            .padding()
            
            Divider()
            
            // Logs list
            if !isMonitoring && realtimeLogs.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "doc.text")
                        .font(.system(size: 48))
                        .foregroundColor(.secondary)
                    
                    Text("Real-time Monitoring Stopped")
                        .font(.title2)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)
                    
                    Text("Start monitoring to see real-time logs from the server.")
                        .font(.body)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollViewReader { proxy in
                    List(filteredLogs) { entry in
                        LogEntryRow(entry: entry)
                            .id(entry.id)
                    }
                    .listStyle(.inset)
                    .onChange(of: filteredLogs.count) { _, _ in
                        if autoScroll && !filteredLogs.isEmpty {
                            withAnimation {
                                proxy.scrollTo(filteredLogs.last?.id, anchor: .bottom)
                            }
                        }
                    }
                }
            }
        }
    }
}

struct LogEntryRow: View {
    let entry: ServerLogsView.LogEntry
    
    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            // Timestamp
            Text(formatTimestamp(entry.timestamp))
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.secondary)
                .frame(width: 80, alignment: .leading)
            
            // Level badge
            Text(entry.level.rawValue)
                .font(.system(.caption2, design: .monospaced))
                .fontWeight(.bold)
                .foregroundColor(.white)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(entry.level.color)
                .cornerRadius(4)
            
            // Message
            Text(entry.message)
                .font(.system(.body, design: .monospaced))
                .textSelection(.enabled)
            
            Spacer()
        }
        .padding(.vertical, 2)
    }
    
    private func formatTimestamp(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: date)
    }
}

#Preview {
    let sampleServer = MCPServer(
        name: "filesystem",
        serverType: .npm,
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem"],
        env: [:],
        enabled: true,
        scope: .user,
        description: "File system operations server"
    )
    
    ServerLogsView(server: sampleServer)
}