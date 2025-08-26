//
//  DatabaseManager.swift
//  MCP-Manager-macOS
//
//  Compatibility layer for OptimizedDatabaseManager
//

import Foundation
import SQLite
import Combine

class DatabaseManager: ObservableObject {
    
    private let optimizedManager: OptimizedDatabaseManager
    
    // Expose the change publisher for real-time updates
    public var changePublisher: AnyPublisher<DatabaseChange, Never> {
        optimizedManager.changePublisher
    }
    
    // MARK: - Initialization
    
    init(databasePath: String? = nil, poolSize: Int = 5) {
        self.optimizedManager = OptimizedDatabaseManager(databasePath: databasePath, poolSize: poolSize)
    }
    
    static func getDefaultDatabasePath() -> String {
        return OptimizedDatabaseManager.getDefaultDatabasePath()
    }
    
    // MARK: - Server Management Methods (Delegate to Optimized Manager)
    
    func listServers() throws -> [MCPServer] {
        return try optimizedManager.listServers()
    }
    
    func addServer(_ server: MCPServer) throws {
        try optimizedManager.addServer(server)
    }
    
    func removeServer(named name: String) throws {
        try optimizedManager.removeServer(named: name)
    }
    
    func updateServerStatus(named name: String, enabled newEnabled: Bool) throws {
        try optimizedManager.updateServerStatus(named: name, enabled: newEnabled)
    }
    
    // MARK: - Status Information
    
    func getServerStatus(named name: String, maxAgeSeconds: TimeInterval = 300) throws -> ServerStatusInfo? {
        return try optimizedManager.getServerStatus(named: name, maxAgeSeconds: maxAgeSeconds)
    }
    
    func recordServerStatus(_ statusInfo: ServerStatusInfo) throws {
        try optimizedManager.recordServerStatus(statusInfo)
    }
    
    // MARK: - Server Requirements
    
    func getServerRequirements(for serverIdentifier: String) throws -> [ServerRequirement] {
        return try optimizedManager.getServerRequirements(for: serverIdentifier)
    }
    
    // MARK: - Bulk Operations
    
    func enableAllServers() throws {
        try optimizedManager.enableAllServers()
    }
    
    func disableAllServers() throws {
        try optimizedManager.disableAllServers()
    }
    
    func removeServers(named names: [String]) throws {
        try optimizedManager.removeServers(named: names)
    }
    
    // MARK: - Performance & Monitoring
    
    func getPerformanceMetrics() -> DatabasePerformanceReport {
        return optimizedManager.getPerformanceMetrics()
    }
    
    func optimizeDatabase() throws {
        try optimizedManager.optimizeDatabase()
    }
    
    func validateDatabaseIntegrity() throws -> Bool {
        return try optimizedManager.validateDatabaseIntegrity()
    }
    
    // MARK: - Database Migration Support
    
    func getDatabaseVersion() throws -> Int {
        return try optimizedManager.getDatabaseVersion()
    }
    
    func setDatabaseVersion(_ version: Int) throws {
        try optimizedManager.setDatabaseVersion(version)
    }
}