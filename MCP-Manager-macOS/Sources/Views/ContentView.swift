//
//  ContentView.swift
//  MCP-Manager-macOS
//
//  Professional macOS app using NavigationSplitView and modern SwiftUI patterns
//

import SwiftUI

struct ContentView: View {
    @StateObject private var serverService = MCPServerService()
    @State private var selectedServer: MCPServer?
    @State private var showingAddServer = false
    @State private var showingPreferences = false
    @State private var showingBulkActions = false
    @State private var selectedServers = Set<String>()
    
    var body: some View {
        NavigationSplitView {
            // Sidebar
            SidebarView(
                serverService: serverService,
                selectedServer: $selectedServer,
                selectedServers: $selectedServers
            )
        } detail: {
            // Main content
            if let server = selectedServer {
                ServerDetailView(
                    server: server,
                    serverService: serverService
                )
            } else {
                ServerListView(
                    serverService: serverService,
                    selectedServer: $selectedServer,
                    selectedServers: $selectedServers
                )
            }
        }
        .navigationTitle("MCP Manager")
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                // Refresh button
                Button {
                    Task {
                        await serverService.refreshServerStatuses()
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Refresh server statuses")
                .disabled(serverService.isLoading)
                
                // Bulk actions
                Menu {
                    BulkActionsMenu(
                        serverService: serverService,
                        selectedServers: $selectedServers
                    )
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
                .help("Bulk actions")
                .disabled(serverService.servers.isEmpty)
                
                // Add server
                Button {
                    showingAddServer = true
                } label: {
                    Image(systemName: "plus")
                }
                .help("Add new server")
            }
            
            ToolbarItemGroup(placement: .secondaryAction) {
                Button {
                    showingPreferences = true
                } label: {
                    Image(systemName: "gear")
                }
                .help("Preferences")
            }
        }
        .sheet(isPresented: $showingAddServer) {
            AddServerSheet(serverService: serverService)
        }
        .sheet(isPresented: $showingPreferences) {
            PreferencesView()
        }
        .alert("Error", isPresented: .constant(serverService.errorMessage != nil)) {
            Button("OK") {
                serverService.errorMessage = nil
            }
        } message: {
            Text(serverService.errorMessage ?? "")
        }
    }
}

// MARK: - Sidebar View

struct SidebarView: View {
    @ObservedObject var serverService: MCPServerService
    @Binding var selectedServer: MCPServer?
    @Binding var selectedServers: Set<String>
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Status Summary
            StatusSummaryView(serverService: serverService)
            
            Divider()
            
            // Filters
            FiltersView(serverService: serverService)
            
            Divider()
            
            // Server Types
            VStack(alignment: .leading, spacing: 8) {
                Text("Server Types")
                    .font(.headline)
                    .foregroundColor(.secondary)
                
                ForEach(ServerType.allCases, id: \.self) { type in
                    let count = serverService.servers.filter { $0.serverType == type }.count
                    
                    HStack {
                        Button {
                            if serverService.selectedType == type {
                                serverService.selectedType = nil
                            } else {
                                serverService.setFilter(type: type)
                            }
                        } label: {
                            HStack {
                                Image(systemName: iconForServerType(type))
                                    .foregroundColor(colorForServerType(type))
                                Text(type.displayName)
                                Spacer()
                                Text("\(count)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                        .background(
                            serverService.selectedType == type ? 
                            Color.accentColor.opacity(0.2) : Color.clear
                        )
                        .cornerRadius(6)
                    }
                }
            }
            
            Spacer()
        }
        .padding()
        .frame(minWidth: 220)
        .background(Color(NSColor.controlBackgroundColor))
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

// MARK: - Status Summary View

struct StatusSummaryView: View {
    @ObservedObject var serverService: MCPServerService
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Status Overview")
                .font(.headline)
                .foregroundColor(.secondary)
            
            let counts = serverService.serverCounts
            
            HStack {
                VStack(alignment: .leading) {
                    Text("\(counts.total)")
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text("Total")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .leading) {
                    Text("\(counts.enabled)")
                        .font(.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(.blue)
                    Text("Enabled")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .leading) {
                    Text("\(counts.connected)")
                        .font(.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(.green)
                    Text("Connected")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                if counts.failed > 0 {
                    Spacer()
                    
                    VStack(alignment: .leading) {
                        Text("\(counts.failed)")
                            .font(.title2)
                            .fontWeight(.semibold)
                            .foregroundColor(.red)
                        Text("Failed")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .padding(12)
        .background(Color(NSColor.controlColor))
        .cornerRadius(8)
    }
}

// MARK: - Filters View

struct FiltersView: View {
    @ObservedObject var serverService: MCPServerService
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Filters")
                .font(.headline)
                .foregroundColor(.secondary)
            
            // Search
            TextField("Search servers...", text: $serverService.searchText)
                .textFieldStyle(.roundedBorder)
            
            // Scope filter
            HStack {
                Text("Scope:")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Picker("", selection: $serverService.selectedScope) {
                    Text("All").tag(ServerScope?.none)
                    ForEach(ServerScope.allCases, id: \.self) { scope in
                        Text(scope.displayName).tag(ServerScope?.some(scope))
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity)
            }
            
            // Show enabled only
            Toggle("Enabled only", isOn: $serverService.showEnabledOnly)
                .font(.caption)
            
            // Clear filters
            if !serverService.searchText.isEmpty || 
               serverService.selectedType != nil || 
               serverService.selectedScope != nil || 
               serverService.showEnabledOnly {
                Button("Clear Filters") {
                    serverService.clearFilters()
                }
                .font(.caption)
                .foregroundColor(.blue)
            }
        }
    }
}

// MARK: - Bulk Actions Menu

struct BulkActionsMenu: View {
    @ObservedObject var serverService: MCPServerService
    @Binding var selectedServers: Set<String>
    
    var body: some View {
        Group {
            Button("Enable All") {
                Task {
                    await serverService.enableAllServers()
                }
            }
            
            Button("Disable All") {
                Task {
                    await serverService.disableAllServers()
                }
            }
            
            if !selectedServers.isEmpty {
                Divider()
                
                Button("Remove Selected (\(selectedServers.count))") {
                    Task {
                        await serverService.removeSelectedServers(Array(selectedServers))
                        selectedServers.removeAll()
                    }
                }
                .foregroundColor(.red)
            }
            
            Divider()
            
            Button("Sync Docker Desktop Servers") {
                Task {
                    await serverService.syncDockerDesktopServers()
                }
            }
            
            Button("Refresh All Statuses") {
                Task {
                    await serverService.refreshServerStatuses()
                }
            }
        }
    }
}

#Preview {
    ContentView()
        .frame(width: 900, height: 600)
}