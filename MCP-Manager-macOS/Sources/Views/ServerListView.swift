//
//  ServerListView.swift
//  MCP-Manager-macOS
//
//  Professional server list view with selection and status display
//

import SwiftUI

struct ServerListView: View {
    @ObservedObject var serverService: MCPServerService
    @Binding var selectedServer: MCPServer?
    @Binding var selectedServers: Set<String>
    
    @State private var sortOrder: SortOrder = .name
    @State private var sortAscending = true
    
    enum SortOrder: CaseIterable {
        case name, type, status, scope
        
        var displayName: String {
            switch self {
            case .name: return "Name"
            case .type: return "Type"
            case .status: return "Status"
            case .scope: return "Scope"
            }
        }
    }
    
    private var sortedServers: [MCPServer] {
        let filtered = serverService.filteredServers
        
        return filtered.sorted { server1, server2 in
            let result: Bool
            
            switch sortOrder {
            case .name:
                result = server1.name.localizedCaseInsensitiveCompare(server2.name) == .orderedAscending
            case .type:
                result = server1.serverType.rawValue < server2.serverType.rawValue
            case .status:
                let status1 = server1.displayStatus
                let status2 = server2.displayStatus
                result = status1.localizedCaseInsensitiveCompare(status2) == .orderedAscending
            case .scope:
                result = server1.scope.rawValue < server2.scope.rawValue
            }
            
            return sortAscending ? result : !result
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Header with sorting
            HeaderView(
                sortOrder: $sortOrder,
                sortAscending: $sortAscending,
                selectedServers: $selectedServers,
                servers: serverService.filteredServers
            )
            
            Divider()
            
            // Server list
            if serverService.isLoading {
                ProgressView("Loading servers...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if sortedServers.isEmpty {
                EmptyStateView(hasFilters: hasActiveFilters)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(sortedServers, id: \.name, selection: $selectedServer) { server in
                    ServerRowView(
                        server: server,
                        isSelected: selectedServers.contains(server.name),
                        serverService: serverService
                    ) {
                        // Toggle selection
                        if selectedServers.contains(server.name) {
                            selectedServers.remove(server.name)
                        } else {
                            selectedServers.insert(server.name)
                        }
                    }
                    .contextMenu {
                        ServerContextMenu(server: server, serverService: serverService)
                    }
                }
                .listStyle(.inset)
            }
        }
        .navigationTitle("Servers (\(serverService.filteredServers.count))")
        .refreshable {
            await serverService.refreshServerStatuses()
        }
    }
    
    private var hasActiveFilters: Bool {
        !serverService.searchText.isEmpty ||
        serverService.selectedType != nil ||
        serverService.selectedScope != nil ||
        serverService.showEnabledOnly
    }
}

// MARK: - Header View

struct HeaderView: View {
    @Binding var sortOrder: ServerListView.SortOrder
    @Binding var sortAscending: Bool
    @Binding var selectedServers: Set<String>
    let servers: [MCPServer]
    
    var body: some View {
        HStack {
            // Select all checkbox
            Button {
                if selectedServers.count == servers.count {
                    selectedServers.removeAll()
                } else {
                    selectedServers = Set(servers.map { $0.name })
                }
            } label: {
                Image(systemName: selectedServers.isEmpty ? "square" :
                      selectedServers.count == servers.count ? "checkmark.square.fill" : "minus.square.fill")
                    .foregroundColor(selectedServers.isEmpty ? .secondary : .accentColor)
            }
            .buttonStyle(.plain)
            .help(selectedServers.isEmpty ? "Select all" : "Deselect all")
            
            // Column headers
            Group {
                SortableHeader(title: "Name", sortOrder: .name, currentSort: $sortOrder, ascending: $sortAscending)
                    .frame(minWidth: 120, alignment: .leading)
                
                SortableHeader(title: "Type", sortOrder: .type, currentSort: $sortOrder, ascending: $sortAscending)
                    .frame(width: 100, alignment: .leading)
                
                SortableHeader(title: "Status", sortOrder: .status, currentSort: $sortOrder, ascending: $sortAscending)
                    .frame(width: 100, alignment: .leading)
                
                SortableHeader(title: "Scope", sortOrder: .scope, currentSort: $sortOrder, ascending: $sortAscending)
                    .frame(width: 80, alignment: .leading)
                
                Text("Actions")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.secondary)
                    .frame(width: 80, alignment: .center)
            }
            
            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 8)
        .background(Color(NSColor.controlBackgroundColor))
    }
}

struct SortableHeader: View {
    let title: String
    let sortOrder: ServerListView.SortOrder
    @Binding var currentSort: ServerListView.SortOrder
    @Binding var ascending: Bool
    
    var body: some View {
        Button {
            if currentSort == sortOrder {
                ascending.toggle()
            } else {
                currentSort = sortOrder
                ascending = true
            }
        } label: {
            HStack(spacing: 4) {
                Text(title)
                    .font(.caption)
                    .fontWeight(.medium)
                
                if currentSort == sortOrder {
                    Image(systemName: ascending ? "chevron.up" : "chevron.down")
                        .font(.caption2)
                }
            }
            .foregroundColor(currentSort == sortOrder ? .accentColor : .secondary)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Server Row View

struct ServerRowView: View {
    let server: MCPServer
    let isSelected: Bool
    @ObservedObject var serverService: MCPServerService
    let onSelectionToggle: () -> Void
    
    var body: some View {
        HStack(spacing: 12) {
            // Selection checkbox
            Button(action: onSelectionToggle) {
                Image(systemName: isSelected ? "checkmark.square.fill" : "square")
                    .foregroundColor(isSelected ? .accentColor : .secondary)
            }
            .buttonStyle(.plain)
            
            // Server info
            HStack {
                // Name and description
                VStack(alignment: .leading, spacing: 2) {
                    Text(server.name)
                        .font(.system(.body, design: .monospaced))
                        .fontWeight(.medium)
                    
                    if let description = server.description {
                        Text(description)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }
                .frame(minWidth: 120, alignment: .leading)
                
                // Type
                HStack(spacing: 4) {
                    Image(systemName: iconForServerType(server.serverType))
                        .foregroundColor(colorForServerType(server.serverType))
                    Text(server.serverType.displayName)
                        .font(.caption)
                }
                .frame(width: 100, alignment: .leading)
                
                // Status
                StatusBadge(server: server)
                    .frame(width: 100, alignment: .leading)
                
                // Scope
                Text(server.scope.displayName)
                    .font(.caption)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.gray.opacity(0.2))
                    .cornerRadius(4)
                    .frame(width: 80, alignment: .leading)
                
                // Actions
                HStack(spacing: 4) {
                    // Enable/Disable toggle
                    Button {
                        Task {
                            await serverService.toggleServerStatus(server)
                        }
                    } label: {
                        Image(systemName: server.enabled ? "pause.circle.fill" : "play.circle.fill")
                            .foregroundColor(server.enabled ? .orange : .green)
                    }
                    .buttonStyle(.plain)
                    .help(server.enabled ? "Disable server" : "Enable server")
                    
                    // Remove button
                    Button {
                        Task {
                            await serverService.removeServer(named: server.name)
                        }
                    } label: {
                        Image(systemName: "trash.circle.fill")
                            .foregroundColor(.red)
                    }
                    .buttonStyle(.plain)
                    .help("Remove server")
                }
                .frame(width: 80, alignment: .center)
            }
            
            Spacer()
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(isSelected ? Color.accentColor.opacity(0.1) : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .strokeBorder(isSelected ? Color.accentColor : Color.clear, lineWidth: 1)
        )
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

// MARK: - Status Badge

struct StatusBadge: View {
    let server: MCPServer
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)
            
            Text(server.displayStatus)
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(statusColor.opacity(0.1))
        .cornerRadius(12)
    }
    
    private var statusColor: Color {
        if !server.enabled {
            return .gray
        }
        
        switch server.statusInfo?.status {
        case .connected:
            return .green
        case .failed:
            return .red
        case .timeout:
            return .orange
        case .unknown, .none:
            return .gray
        }
    }
}

// MARK: - Context Menu

struct ServerContextMenu: View {
    let server: MCPServer
    @ObservedObject var serverService: MCPServerService
    
    var body: some View {
        Group {
            Button(server.enabled ? "Disable" : "Enable") {
                Task {
                    await serverService.toggleServerStatus(server)
                }
            }
            
            Divider()
            
            Button("View Details") {
                // This would show detailed server information
            }
            
            Button("Copy Command") {
                let command = "\(server.command) \(server.args.joined(separator: " "))"
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(command, forType: .string)
            }
            
            Divider()
            
            Button("Remove Server") {
                Task {
                    await serverService.removeServer(named: server.name)
                }
            }
            .foregroundColor(.red)
        }
    }
}

// MARK: - Empty State View

struct EmptyStateView: View {
    let hasFilters: Bool
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: hasFilters ? "magnifyingglass" : "server.rack")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            
            Text(hasFilters ? "No servers match your filters" : "No servers configured")
                .font(.title2)
                .fontWeight(.medium)
                .foregroundColor(.secondary)
            
            Text(hasFilters ? 
                 "Try adjusting your search criteria or filters." :
                 "Add your first MCP server to get started.")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(40)
    }
}

#Preview {
    ServerListView(
        serverService: MCPServerService(),
        selectedServer: .constant(nil),
        selectedServers: .constant(Set())
    )
    .frame(width: 800, height: 600)
}