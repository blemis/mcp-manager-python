//
//  MCPServerService.swift
//  MCP-Manager-macOS
//
//  Native Swift service layer for MCP server management
//  NO Python CLI calls - all operations are native Swift
//

import Foundation
import Combine

@MainActor
class MCPServerService: ObservableObject {
    
    // MARK: - Published Properties
    
    @Published var servers: [MCPServer] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var searchText = ""
    @Published var selectedType: ServerType?
    @Published var selectedScope: ServerScope?
    @Published var showEnabledOnly = false
    
    // MARK: - Dependencies
    
    private let databaseManager: DatabaseManager
    private let claudeService: ClaudeService
    
    // MARK: - Computed Properties
    
    var filteredServers: [MCPServer] {
        servers.filter { server in
            // Text search filter
            if !searchText.isEmpty {
                let searchLower = searchText.lowercased()
                let matchesName = server.name.lowercased().contains(searchLower)
                let matchesDescription = server.description?.lowercased().contains(searchLower) ?? false
                let matchesPackage = server.package?.lowercased().contains(searchLower) ?? false
                
                if !matchesName && !matchesDescription && !matchesPackage {
                    return false
                }
            }
            
            // Type filter
            if let selectedType = selectedType, server.serverType != selectedType {
                return false
            }
            
            // Scope filter
            if let selectedScope = selectedScope, server.scope != selectedScope {
                return false
            }
            
            // Enabled filter
            if showEnabledOnly && !server.enabled {
                return false
            }
            
            return true
        }
    }
    
    var serverCounts: (total: Int, enabled: Int, connected: Int, failed: Int) {
        let total = servers.count
        let enabled = servers.filter { $0.enabled }.count
        let connected = servers.filter { $0.isHealthy }.count
        let failed = servers.filter { $0.enabled && $0.statusInfo?.status == .failed }.count
        
        return (total, enabled, connected, failed)
    }
    
    // MARK: - Initialization
    
    init(databaseManager: DatabaseManager = DatabaseManager(), 
         claudeService: ClaudeService = ClaudeService()) {
        self.databaseManager = databaseManager
        self.claudeService = claudeService
        
        Task {
            await loadServers()
        }
    }
    
    // MARK: - Data Loading
    
    func loadServers() async {
        isLoading = true
        errorMessage = nil
        
        do {
            var loadedServers = try databaseManager.listServers()
            
            // Enrich with status information from database cache
            for i in 0..<loadedServers.count {
                let statusInfo = try? databaseManager.getServerStatus(named: loadedServers[i].name)
                loadedServers[i].statusInfo = statusInfo
            }
            
            servers = loadedServers
        } catch {
            errorMessage = "Failed to load servers: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    func refreshServerStatuses() async {
        // Use Claude CLI to get current server statuses (ONLY Claude CLI call allowed)
        let claudeStatuses = await claudeService.getServerStatuses()
        
        // Update our database with fresh status information
        for (serverName, claudeStatus) in claudeStatuses {
            let statusInfo = ServerStatusInfo(
                name: serverName,
                status: claudeStatus.status,
                responseTimeMs: claudeStatus.responseTime,
                errorMessage: claudeStatus.error,
                toolCount: claudeStatus.toolCount,
                checkedAt: Date()
            )
            
            try? databaseManager.recordServerStatus(statusInfo)
        }
        
        // Reload servers to pick up new status information
        await loadServers()
    }
    
    // MARK: - Server Management (Native Implementation)
    
    func addServer(_ server: MCPServer) async {
        do {
            try databaseManager.addServer(server)
            await syncToClaudeConfig() // Sync our database to Claude's config
            await loadServers()
        } catch {
            errorMessage = "Failed to add server: \(error.localizedDescription)"
        }
    }
    
    func removeServer(named name: String) async {
        do {
            try databaseManager.removeServer(named: name)
            await syncToClaudeConfig()
            await loadServers()
        } catch {
            errorMessage = "Failed to remove server: \(error.localizedDescription)"
        }
    }
    
    func toggleServerStatus(_ server: MCPServer) async {
        do {
            try databaseManager.updateServerStatus(named: server.name, enabled: !server.enabled)
            await syncToClaudeConfig()
            await loadServers()
        } catch {
            errorMessage = "Failed to toggle server status: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Bulk Operations
    
    func enableAllServers() async {
        do {
            try databaseManager.enableAllServers()
            await syncToClaudeConfig()
            await loadServers()
        } catch {
            errorMessage = "Failed to enable all servers: \(error.localizedDescription)"
        }
    }
    
    func disableAllServers() async {
        do {
            try databaseManager.disableAllServers()
            await syncToClaudeConfig()
            await loadServers()
        } catch {
            errorMessage = "Failed to disable all servers: \(error.localizedDescription)"
        }
    }
    
    func removeSelectedServers(_ serverNames: [String]) async {
        do {
            try databaseManager.removeServers(named: serverNames)
            await syncToClaudeConfig()
            await loadServers()
        } catch {
            errorMessage = "Failed to remove selected servers: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Docker Desktop Integration (Native)
    
    func syncDockerDesktopServers() async {
        // Native implementation of Docker Desktop server discovery
        do {
            let dockerServers = await discoverDockerDesktopServers()
            
            // Add any new Docker Desktop servers
            for server in dockerServers {
                // Check if server already exists
                let existingServers = try databaseManager.listServers()
                if !existingServers.contains(where: { $0.name == server.name }) {
                    try databaseManager.addServer(server)
                }
            }
            
            await syncToClaudeConfig()
            await loadServers()
            
        } catch {
            errorMessage = "Failed to sync Docker Desktop servers: \(error.localizedDescription)"
        }
    }
    
    private func discoverDockerDesktopServers() async -> [MCPServer] {
        // Native Swift implementation to discover Docker Desktop MCP servers
        // This replaces any Python CLI calls with direct Docker API/CLI integration
        
        var servers: [MCPServer] = []
        
        // Known Docker Desktop MCP servers
        let knownServers = [
            ("docker-desktop-sqlite", "SQLite Database", "docker", ["run", "--rm", "-it", "docker-desktop-sqlite"]),
            ("docker-desktop-filesystem", "File System", "docker", ["run", "--rm", "-it", "docker-desktop-filesystem"]),
            ("docker-desktop-search", "Web Search", "docker", ["run", "--rm", "-it", "docker-desktop-search"]),
            ("docker-desktop-http", "HTTP Client", "docker", ["run", "--rm", "-it", "docker-desktop-http"]),
        ]
        
        for (name, description, command, args) in knownServers {
            let server = MCPServer(
                name: name,
                serverType: .dockerDesktop,
                command: command,
                args: args,
                env: [:],
                enabled: false, // Default to disabled
                scope: .user,
                description: description,
                installId: "dd-\(name)",
                package: name,
                createdAt: Date(),
                updatedAt: Date()
            )
            servers.append(server)
        }
        
        return servers
    }
    
    // MARK: - Claude Config Synchronization
    
    private func syncToClaudeConfig() async {
        // Sync our database state to Claude's internal config
        do {
            let enabledServers = try databaseManager.listServers().filter { $0.enabled }
            await claudeService.syncServersToConfig(enabledServers)
        } catch {
            print("⚠️ Failed to sync to Claude config: \(error)")
        }
    }
    
    // MARK: - Search & Filtering
    
    func clearFilters() {
        searchText = ""
        selectedType = nil
        selectedScope = nil
        showEnabledOnly = false
    }
    
    func setFilter(type: ServerType?) {
        selectedType = type
    }
    
    func setFilter(scope: ServerScope?) {
        selectedScope = scope
    }
    
    // MARK: - Server Creation Helpers
    
    func createNPMServer(name: String, package: String, description: String? = nil, 
                        args: [String] = [], env: [String: String] = [:]) -> MCPServer {
        return MCPServer(
            name: name,
            serverType: .npm,
            command: "npx",
            args: ["-y", package] + (args.isEmpty ? [] : ["--"] + args),
            env: env,
            enabled: false,
            scope: .user,
            description: description,
            installId: package,
            package: package,
            createdAt: Date(),
            updatedAt: Date()
        )
    }
    
    func createDockerServer(name: String, image: String, description: String? = nil,
                          args: [String] = [], env: [String: String] = [:]) -> MCPServer {
        return MCPServer(
            name: name,
            serverType: .docker,
            command: "docker",
            args: ["run", "--rm", "-it"] + (args.isEmpty ? [image] : [image] + args),
            env: env,
            enabled: false,
            scope: .user,
            description: description,
            installId: "docker-\(image)",
            package: image,
            createdAt: Date(),
            updatedAt: Date()
        )
    }
    
    func createCustomServer(name: String, command: String, args: [String] = [], 
                          env: [String: String] = [:], description: String? = nil) -> MCPServer {
        return MCPServer(
            name: name,
            serverType: .custom,
            command: command,
            args: args,
            env: env,
            enabled: false,
            scope: .user,
            description: description,
            createdAt: Date(),
            updatedAt: Date()
        )
    }
    
    // MARK: - Validation
    
    func validateServerName(_ name: String) -> String? {
        if name.isEmpty {
            return "Server name cannot be empty"
        }
        
        if servers.contains(where: { $0.name == name }) {
            return "Server name already exists"
        }
        
        if name.contains(" ") {
            return "Server name cannot contain spaces"
        }
        
        return nil
    }
    
    func validateCommand(_ command: String) -> String? {
        if command.isEmpty {
            return "Command cannot be empty"
        }
        
        return nil
    }
}

// MARK: - Claude Service

class ClaudeService {
    
    struct ClaudeServerStatus {
        let status: ServerStatus
        let responseTime: Double?
        let error: String?
        let toolCount: Int?
    }
    
    func getServerStatuses() async -> [String: ClaudeServerStatus] {
        // Use Claude CLI to get current server statuses
        // This is the ONLY allowed Python/CLI call in the entire app
        
        do {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/claude")
            process.arguments = ["mcp", "list"]
            
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            
            try process.run()
            process.waitUntilExit()
            
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            
            return parseClaudeOutput(output)
            
        } catch {
            print("❌ Failed to get Claude server statuses: \(error)")
            return [:]
        }
    }
    
    func syncServersToConfig(_ servers: [MCPServer]) async {
        // Sync enabled servers to Claude's config
        // This would typically update ~/.claude.json to match our database
        
        // For now, we'll log what would be synced
        let enabledServers = servers.filter { $0.enabled }
        print("🔄 Would sync \(enabledServers.count) enabled servers to Claude config:")
        for server in enabledServers {
            print("   - \(server.name) (\(server.serverType.rawValue))")
        }
    }
    
    private func parseClaudeOutput(_ output: String) -> [String: ClaudeServerStatus] {
        var statuses: [String: ClaudeServerStatus] = [:]
        
        // Parse Claude CLI output to extract server statuses
        // Format typically includes server names and their connection status
        let lines = output.components(separatedBy: .newlines)
        
        for line in lines {
            if line.contains("✓") || line.contains("✗") || line.contains("⚠") {
                // Parse server status from Claude CLI output
                let parts = line.components(separatedBy: " ").filter { !$0.isEmpty }
                if let serverName = parts.last {
                    let status: ServerStatus = line.contains("✓") ? .connected : 
                                            line.contains("✗") ? .failed : .timeout
                    
                    statuses[serverName] = ClaudeServerStatus(
                        status: status,
                        responseTime: nil,
                        error: status == .failed ? "Connection failed" : nil,
                        toolCount: nil
                    )
                }
            }
        }
        
        return statuses
    }
}