//
//  ServerDetailView.swift
//  MCP-Manager-macOS
//
//  Detailed view for individual server management and information
//

import SwiftUI

struct ServerDetailView: View {
    let server: MCPServer
    @ObservedObject var serverService: MCPServerService
    
    @State private var showingEditSheet = false
    @State private var showingLogs = false
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                ServerHeaderView(server: server, serverService: serverService, showingEditSheet: $showingEditSheet)
                
                // Status Information
                StatusDetailView(server: server)
                
                // Configuration Details
                ConfigurationDetailView(server: server)
                
                // Command Information
                CommandDetailView(server: server)
                
                // Environment Variables (if any)
                if !server.env.isEmpty {
                    EnvironmentDetailView(server: server)
                }
                
                // Recent Activity (if we have status history)
                ActivityDetailView(server: server)
            }
            .padding(20)
        }
        .navigationTitle(server.name)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button("Edit Server") {
                        showingEditSheet = true
                    }
                    
                    Button("View Logs") {
                        showingLogs = true
                    }
                    
                    Button("Copy Command") {
                        copyCommandToClipboard()
                    }
                    
                    Divider()
                    
                    Button(server.enabled ? "Disable Server" : "Enable Server") {
                        Task {
                            await serverService.toggleServerStatus(server)
                        }
                    }
                    .foregroundColor(server.enabled ? .orange : .green)
                    
                    Divider()
                    
                    Button("Remove Server") {
                        Task {
                            await serverService.removeServer(named: server.name)
                        }
                    }
                    .foregroundColor(.red)
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .sheet(isPresented: $showingEditSheet) {
            EditServerSheet(server: server, serverService: serverService)
        }
        .sheet(isPresented: $showingLogs) {
            ServerLogsView(server: server)
        }
    }
    
    private func copyCommandToClipboard() {
        let command = "\(server.command) \(server.args.joined(separator: " "))"
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(command, forType: .string)
    }
}

// MARK: - Server Header

struct ServerHeaderView: View {
    let server: MCPServer
    @ObservedObject var serverService: MCPServerService
    @Binding var showingEditSheet: Bool
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                // Server icon and name
                HStack(spacing: 12) {
                    Image(systemName: iconForServerType(server.serverType))
                        .font(.title)
                        .foregroundColor(colorForServerType(server.serverType))
                    
                    VStack(alignment: .leading) {
                        Text(server.name)
                            .font(.title)
                            .fontWeight(.bold)
                        
                        if let description = server.description {
                            Text(description)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                Spacer()
                
                // Status and actions
                VStack(alignment: .trailing, spacing: 8) {
                    HStack(spacing: 8) {
                        StatusBadge(server: server)
                        
                        Button {
                            Task {
                                await serverService.toggleServerStatus(server)
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: server.enabled ? "pause.circle.fill" : "play.circle.fill")
                                Text(server.enabled ? "Disable" : "Enable")
                            }
                            .foregroundColor(server.enabled ? .orange : .green)
                        }
                        .buttonStyle(.bordered)
                    }
                    
                    Button("Edit Server") {
                        showingEditSheet = true
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            
            // Metadata
            HStack {
                MetadataChip(label: "Type", value: server.serverType.displayName)
                MetadataChip(label: "Scope", value: server.scope.displayName)
                
                if let package = server.package {
                    MetadataChip(label: "Package", value: package)
                }
                
                if let installId = server.installId {
                    MetadataChip(label: "Install ID", value: installId)
                }
                
                Spacer()
            }
        }
        .padding(20)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(12)
    }
    
    private func iconForServerType(_ type: ServerType) -> String {
        switch type {
        case .npm: return "cube.box"
        case .docker: return "shippingbox"
        case .dockerDesktop: return "dock.rectangle"
        case .custom: return "hammer"
        }
    }
    
    private func colorForServerType(_ type: ServerType) -> Color {
        switch type {
        case .npm: return .red
        case .docker: return .blue
        case .dockerDesktop: return .cyan
        case .custom: return .purple
        }
    }
}

struct MetadataChip: View {
    let label: String
    let value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
                .textCase(.uppercase)
            
            Text(value)
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(6)
    }
}

// MARK: - Status Detail

struct StatusDetailView: View {
    let server: MCPServer
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Status Information", systemImage: "info.circle")
            
            VStack(spacing: 12) {
                StatusDetailRow(label: "Current Status", value: server.displayStatus, statusColor: server.statusColor)
                
                if let statusInfo = server.statusInfo {
                    if let responseTime = statusInfo.responseTimeMs {
                        StatusDetailRow(label: "Response Time", value: String(format: "%.0f ms", responseTime))
                    }
                    
                    if let toolCount = statusInfo.toolCount {
                        StatusDetailRow(label: "Available Tools", value: "\(toolCount) tool\(toolCount == 1 ? "" : "s")")
                    }
                    
                    if let error = statusInfo.errorMessage {
                        StatusDetailRow(label: "Error Message", value: error, statusColor: "red")
                    }
                    
                    if let checkedAt = statusInfo.checkedAt {
                        StatusDetailRow(label: "Last Checked", value: formatDate(checkedAt))
                    }
                }
            }
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.dateTimeStyle = .named
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

struct StatusDetailRow: View {
    let label: String
    let value: String
    var statusColor: String? = nil
    
    var body: some View {
        HStack {
            Text(label)
                .font(.body)
                .foregroundColor(.secondary)
                .frame(width: 120, alignment: .leading)
            
            Text(value)
                .font(.body)
                .fontWeight(.medium)
                .foregroundColor(colorFromString(statusColor))
            
            Spacer()
        }
    }
    
    private func colorFromString(_ colorString: String?) -> Color {
        switch colorString {
        case "green": return .green
        case "red": return .red
        case "orange": return .orange
        case "blue": return .blue
        default: return .primary
        }
    }
}

// MARK: - Configuration Detail

struct ConfigurationDetailView: View {
    let server: MCPServer
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Configuration", systemImage: "gearshape")
            
            VStack(spacing: 12) {
                ConfigRow(label: "Enabled", value: server.enabled ? "Yes" : "No")
                ConfigRow(label: "Server Type", value: server.serverType.displayName)
                ConfigRow(label: "Scope", value: server.scope.displayName)
                
                if let createdAt = server.createdAt {
                    ConfigRow(label: "Created", value: formatDate(createdAt))
                }
                
                if let updatedAt = server.updatedAt {
                    ConfigRow(label: "Last Updated", value: formatDate(updatedAt))
                }
                
                ConfigRow(label: "Config Hash", value: String(server.configHash.prefix(16)))
            }
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

struct ConfigRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .font(.body)
                .foregroundColor(.secondary)
                .frame(width: 120, alignment: .leading)
            
            Text(value)
                .font(.body)
                .fontWeight(.medium)
            
            Spacer()
        }
    }
}

// MARK: - Command Detail

struct CommandDetailView: View {
    let server: MCPServer
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Command Configuration", systemImage: "terminal")
            
            VStack(alignment: .leading, spacing: 8) {
                // Command
                VStack(alignment: .leading, spacing: 4) {
                    Text("Command")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .textCase(.uppercase)
                    
                    Text(server.command)
                        .font(.system(.body, design: .monospaced))
                        .padding(8)
                        .background(Color(NSColor.textBackgroundColor))
                        .cornerRadius(6)
                }
                
                // Arguments
                if !server.args.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Arguments")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .textCase(.uppercase)
                        
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(Array(server.args.enumerated()), id: \.offset) { index, arg in
                                Text("[\(index)] \(arg)")
                                    .font(.system(.caption, design: .monospaced))
                            }
                        }
                        .padding(8)
                        .background(Color(NSColor.textBackgroundColor))
                        .cornerRadius(6)
                    }
                }
                
                // Full command
                VStack(alignment: .leading, spacing: 4) {
                    Text("Full Command")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .textCase(.uppercase)
                    
                    let fullCommand = "\(server.command) \(server.args.joined(separator: " "))"
                    Text(fullCommand)
                        .font(.system(.body, design: .monospaced))
                        .padding(8)
                        .background(Color(NSColor.textBackgroundColor))
                        .cornerRadius(6)
                        .textSelection(.enabled)
                }
            }
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
}

// MARK: - Environment Detail

struct EnvironmentDetailView: View {
    let server: MCPServer
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Environment Variables", systemImage: "externaldrive")
            
            VStack(alignment: .leading, spacing: 8) {
                ForEach(Array(server.env.keys.sorted()), id: \.self) { key in
                    HStack {
                        Text(key)
                            .font(.system(.body, design: .monospaced))
                            .foregroundColor(.secondary)
                            .frame(width: 120, alignment: .leading)
                        
                        Text("=")
                            .foregroundColor(.secondary)
                        
                        Text(server.env[key] ?? "")
                            .font(.system(.body, design: .monospaced))
                            .textSelection(.enabled)
                        
                        Spacer()
                    }
                }
            }
            .padding(8)
            .background(Color(NSColor.textBackgroundColor))
            .cornerRadius(6)
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
}

// MARK: - Activity Detail

struct ActivityDetailView: View {
    let server: MCPServer
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Recent Activity", systemImage: "clock.arrow.circlepath")
            
            VStack(alignment: .leading, spacing: 8) {
                if let statusInfo = server.statusInfo, let checkedAt = statusInfo.checkedAt {
                    HStack {
                        Circle()
                            .fill(statusInfo.status == .connected ? .green : .red)
                            .frame(width: 8, height: 8)
                        
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Status Check")
                                .font(.body)
                                .fontWeight(.medium)
                            
                            Text("\(statusInfo.status.displayName) - \(formatRelativeDate(checkedAt))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        Spacer()
                    }
                } else {
                    HStack {
                        Circle()
                            .fill(Color.gray)
                            .frame(width: 8, height: 8)
                        
                        Text("No recent activity")
                            .font(.body)
                            .foregroundColor(.secondary)
                        
                        Spacer()
                    }
                }
            }
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
    }
    
    private func formatRelativeDate(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.dateTimeStyle = .named
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

// MARK: - Section Header

struct SectionHeader: View {
    let title: String
    let systemImage: String
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: systemImage)
                .foregroundColor(.accentColor)
            
            Text(title)
                .font(.headline)
                .fontWeight(.semibold)
            
            Spacer()
        }
    }
}

#Preview {
    let sampleServer = MCPServer(
        name: "filesystem",
        serverType: .npm,
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "--", "/Users/example"],
        env: [:],
        enabled: true,
        scope: .user,
        description: "File system operations server",
        installId: "@modelcontextprotocol/server-filesystem",
        package: "@modelcontextprotocol/server-filesystem",
        createdAt: Date().addingTimeInterval(-86400),
        updatedAt: Date().addingTimeInterval(-3600),
        statusInfo: ServerStatusInfo(
            name: "filesystem",
            status: .connected,
            responseTimeMs: 45.2,
            errorMessage: nil,
            toolCount: 12,
            checkedAt: Date().addingTimeInterval(-300)
        )
    )
    
    ServerDetailView(server: sampleServer, serverService: MCPServerService())
        .frame(width: 600, height: 800)
}