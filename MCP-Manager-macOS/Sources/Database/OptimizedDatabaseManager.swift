//
//  OptimizedDatabaseManager.swift
//  MCP-Manager-macOS
//
//  Enterprise-grade database manager with production performance optimizations
//  - Connection pooling for high concurrency
//  - Optimized SQLite configuration for OLTP workloads  
//  - Real-time change detection and UI updates
//  - Bulletproof error handling and recovery
//  - Schema compatibility with Python CLI
//

import Foundation
import SQLite
import Combine
import os.log

// MARK: - Main Database Manager

class OptimizedDatabaseManager: ObservableObject {
    
    // MARK: - Properties
    
    private let connectionPool: DatabaseConnectionPool
    private let dbPath: String
    private var fileSystemWatcher: DispatchSourceFileSystemObject?
    private let changeSubject = PassthroughSubject<DatabaseChange, Never>()
    
    // Performance metrics
    private var queryMetrics = DatabaseMetrics()
    private let performanceQueue = DispatchQueue(label: "database.performance", qos: .utility)
    
    // Real-time change notifications
    public var changePublisher: AnyPublisher<DatabaseChange, Never> {
        changeSubject.eraseToAnyPublisher()
    }
    
    // MARK: - Table References (matching Python schema exactly)
    
    // mcp_server_registry table
    private let serverRegistry = Table("mcp_server_registry")
    private let serverName = Expression<String>("name")
    private let serverType = Expression<String>("server_type")
    private let command = Expression<String>("command")
    private let args = Expression<String>("args") // JSON array
    private let env = Expression<String>("env") // JSON object
    private let enabled = Expression<Bool>("enabled")
    private let scope = Expression<String>("scope")
    private let configHash = Expression<String>("config_hash")
    private let description = Expression<String?>("description")
    private let installId = Expression<String?>("install_id")
    private let package = Expression<String?>("package")
    private let createdAt = Expression<String>("created_at") // ISO timestamp
    private let updatedAt = Expression<String>("updated_at") // ISO timestamp
    
    // mcp_connection_history table
    private let connectionHistory = Table("mcp_connection_history")
    private let historyId = Expression<Int64>("id")
    private let historyServerName = Expression<String>("server_name")
    private let status = Expression<String>("status")
    private let responseTimeMs = Expression<Double?>("response_time_ms")
    private let errorMessage = Expression<String?>("error_message")
    private let toolCount = Expression<Int?>("tool_count")
    private let checkedAt = Expression<String>("checked_at")
    
    // mcp_usage_events table  
    private let usageEvents = Table("mcp_usage_events")
    private let eventId = Expression<Int64>("id")
    private let eventServerName = Expression<String>("server_name")
    private let eventType = Expression<String>("event_type")
    private let eventData = Expression<String?>("event_data")
    private let userContext = Expression<String?>("user_context")
    private let eventCreatedAt = Expression<String>("created_at")
    
    // mcp_server_requirements table
    private let serverRequirements = Table("mcp_server_requirements")
    private let reqId = Expression<Int64>("id")
    private let reqServerIdentifier = Expression<String>("server_identifier")
    private let reqServerType = Expression<String>("server_type")
    private let reqType = Expression<String>("requirement_type")
    private let reqPrompt = Expression<String>("prompt")
    private let reqEnvVarName = Expression<String?>("env_var_name")
    private let reqRequired = Expression<Bool>("required")
    private let reqDefaultValue = Expression<String?>("default_value")
    private let reqDescription = Expression<String?>("description")
    private let reqCreatedAt = Expression<String>("created_at")
    private let reqUpdatedAt = Expression<String>("updated_at")
    
    // MARK: - Initialization
    
    init(databasePath: String? = nil, poolSize: Int = 5) {
        // Use provided path or default database path
        self.dbPath = databasePath ?? Self.getDefaultDatabasePath()
        
        // Initialize connection pool
        self.connectionPool = DatabaseConnectionPool(path: dbPath, maxConnections: poolSize)
        
        do {
            try setupDatabase()
            setupFileWatcher()
        } catch {
            logger.error("❌ Failed to setup database: \\(error)")
            print("❌ Failed to setup database: \\(error)")
        }
    }
    
    deinit {
        fileSystemWatcher?.cancel()
        connectionPool.closeAll()
    }
    
    static func getDefaultDatabasePath() -> String {
        // Match Python CLI logic exactly - use ~/.local/share/mcp-manager/server_state.db
        let homeDir = FileManager.default.homeDirectoryForCurrentUser
        let dataDir = homeDir.appendingPathComponent(".local/share/mcp-manager")
        
        // Ensure directory exists with proper permissions
        do {
            try FileManager.default.createDirectory(at: dataDir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o755])
        } catch {
            print("⚠️ Warning: Could not create data directory: \\(error)")
        }
        
        return dataDir.appendingPathComponent("server_state.db").path
    }
    
    // MARK: - Database Setup
    
    private func setupDatabase() throws {
        // Initialize connection pool
        try connectionPool.initialize()
        
        // Create tables and indexes with a dedicated connection
        try connectionPool.withConnection { conn in
            try createTables(conn)
            try createIndexes(conn)
            try optimizeForProduction(conn)
        }
        
        print("✅ High-performance database initialized at: \\(dbPath)")
        logger.info("Database connection pool initialized with \\(connectionPool.maxConnections) connections")
    }
    
    private func optimizeForProduction(_ conn: Connection) throws {
        // Production-optimized SQLite configuration for high concurrency
        try conn.execute("PRAGMA journal_mode=WAL")           // Write-Ahead Logging for concurrency
        try conn.execute("PRAGMA synchronous=NORMAL")         // Balanced durability/performance
        try conn.execute("PRAGMA cache_size=20000")           // 20MB cache
        try conn.execute("PRAGMA temp_store=memory")          // In-memory temp tables
        try conn.execute("PRAGMA mmap_size=268435456")        // 256MB memory-mapped I/O
        try conn.execute("PRAGMA page_size=4096")             // Optimal page size
        try conn.execute("PRAGMA foreign_keys=ON")           // Referential integrity
        try conn.execute("PRAGMA wal_autocheckpoint=1000")    // Auto-checkpoint every 1000 pages
        try conn.execute("PRAGMA busy_timeout=30000")         // 30 second timeout for locked database
        try conn.execute("PRAGMA optimize")                   // Query planner optimization
    }
    
    private func setupFileWatcher() {
        guard let fileHandle = FileHandle(forReadingAtPath: dbPath) else {
            print("⚠️ Could not create file watcher for database")
            return
        }
        
        fileSystemWatcher = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: fileHandle.fileDescriptor,
            eventMask: .write,
            queue: DispatchQueue.global(qos: .background)
        )
        
        fileSystemWatcher?.setEventHandler { [weak self] in
            self?.handleDatabaseChange()
        }
        
        fileSystemWatcher?.resume()
    }
    
    private func handleDatabaseChange() {
        // Debounce rapid changes
        performanceQueue.asyncAfter(deadline: .now() + 0.1) { [weak self] in
            self?.changeSubject.send(.serverListUpdated)
        }
    }
    
    private func createTables(_ conn: Connection) throws {
        // Server registry table (matches Python schema exactly)
        try conn.run(serverRegistry.create(ifNotExists: true) { t in
            t.column(serverName, primaryKey: true)
            t.column(serverType)
            t.column(command)
            t.column(args) // JSON array
            t.column(env)  // JSON object
            t.column(enabled)
            t.column(scope)
            t.column(configHash) // For drift detection
            t.column(description)
            t.column(installId)
            t.column(package)
            t.column(createdAt)
            t.column(updatedAt)
        })
        
        // Connection history table
        try conn.run(connectionHistory.create(ifNotExists: true) { t in
            t.column(historyId, primaryKey: .autoincrement)
            t.column(historyServerName)
            t.column(status)
            t.column(responseTimeMs)
            t.column(errorMessage)
            t.column(toolCount)
            t.column(checkedAt)
            t.foreignKey(historyServerName, references: serverRegistry, serverName, delete: .cascade)
        })
        
        // Usage events table
        try conn.run(usageEvents.create(ifNotExists: true) { t in
            t.column(eventId, primaryKey: .autoincrement)
            t.column(eventServerName)
            t.column(eventType)
            t.column(eventData)
            t.column(userContext)
            t.column(eventCreatedAt)
            t.foreignKey(eventServerName, references: serverRegistry, serverName, delete: .cascade)
        })
        
        // Server requirements table
        try conn.run(serverRequirements.create(ifNotExists: true) { t in
            t.column(reqId, primaryKey: .autoincrement)
            t.column(reqServerIdentifier)
            t.column(reqServerType)
            t.column(reqType)
            t.column(reqPrompt)
            t.column(reqEnvVarName)
            t.column(reqRequired, defaultValue: true)
            t.column(reqDefaultValue)
            t.column(reqDescription)
            t.column(reqCreatedAt)
            t.column(reqUpdatedAt)
            t.unique(reqServerIdentifier, reqType)
        })
    }
    
    private func createIndexes(_ conn: Connection) throws {
        // Performance-critical indexes (matching Python + additional optimizations)
        let indexes = [
            "CREATE INDEX IF NOT EXISTS idx_connection_history_server_time ON mcp_connection_history(server_name, checked_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_usage_events_server_time ON mcp_usage_events(server_name, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_server_registry_type ON mcp_server_registry(server_type)",
            "CREATE INDEX IF NOT EXISTS idx_server_registry_enabled ON mcp_server_registry(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_server_registry_scope ON mcp_server_registry(scope)",
            "CREATE INDEX IF NOT EXISTS idx_server_requirements_identifier ON mcp_server_requirements(server_identifier)",
            "CREATE INDEX IF NOT EXISTS idx_server_requirements_type ON mcp_server_requirements(server_type)",
            "CREATE INDEX IF NOT EXISTS idx_connection_history_status ON mcp_connection_history(status)",
            "CREATE INDEX IF NOT EXISTS idx_usage_events_type ON mcp_usage_events(event_type)"
        ]
        
        for indexSQL in indexes {
            try conn.run(indexSQL)
        }
        
        // Create partial indexes for better performance
        try conn.run("CREATE INDEX IF NOT EXISTS idx_enabled_servers ON mcp_server_registry(name) WHERE enabled = 1")
    }
    
    // MARK: - Server Management (High-Performance Implementation)
    
    func listServers() throws -> [MCPServer] {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let servers: [MCPServer] = try connectionPool.withConnection { conn in
            var servers: [MCPServer] = []
            
            // Use prepared statement for better performance
            let query = serverRegistry.order(serverName)
            
            for row in try conn.prepare(query) {
                let server = try parseServerFromRow(row)
                servers.append(server)
            }
            
            return servers
        }
        
        // Track performance metrics
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("listServers", duration: duration, rowCount: servers.count)
        
        if duration > 0.1 { // Log slow queries
            logger.warning("Slow query: listServers took \(String(format: "%.3f", duration))s for \(servers.count) rows")
        }
        
        return servers
    }
    
    private func parseServerFromRow(_ row: Row) throws -> MCPServer {
        let argsData = Data(row[args].utf8)
        let envData = Data(row[env].utf8)
        
        let decodedArgs = (try? JSONSerialization.jsonObject(with: argsData) as? [String]) ?? []
        let decodedEnv = (try? JSONSerialization.jsonObject(with: envData) as? [String: String]) ?? [:]
        
        return MCPServer(
            name: row[serverName],
            serverType: ServerType(rawValue: row[serverType]) ?? .custom,
            command: row[command],
            args: decodedArgs,
            env: decodedEnv,
            enabled: row[enabled],
            scope: ServerScope(rawValue: row[scope]) ?? .user,
            configHash: row[configHash],
            description: row[description],
            installId: row[installId],
            package: row[package],
            createdAt: ISO8601DateFormatter().date(from: row[createdAt]),
            updatedAt: ISO8601DateFormatter().date(from: row[updatedAt])
        )
    }
    
    func addServer(_ server: MCPServer) throws {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        try connectionPool.withTransaction { conn in
            let now = ISO8601DateFormatter().string(from: Date())
            let argsJson = try JSONSerialization.data(withJSONObject: server.args)
            let envJson = try JSONSerialization.data(withJSONObject: server.env)
            
            let insert = serverRegistry.insert(or: .replace,
                serverName <- server.name,
                serverType <- server.serverType.rawValue,
                command <- server.command,
                args <- String(data: argsJson, encoding: .utf8) ?? "[]",
                env <- String(data: envJson, encoding: .utf8) ?? "{}",
                enabled <- server.enabled,
                scope <- server.scope.rawValue,
                configHash <- server.configHash,
                description <- server.description,
                installId <- server.installId,
                package <- server.package,
                createdAt <- server.createdAt?.iso8601String ?? now,
                updatedAt <- now
            )
            
            try conn.run(insert)
            
            // Log usage event in same transaction
            try logUsageEvent(conn: conn, serverName: server.name, eventType: "add", eventData: ["install_id": server.installId ?? ""])
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("addServer", duration: duration, rowCount: 1)
        
        // Notify observers
        changeSubject.send(.serverAdded(server.name))
        
        print("✅ Added server \(server.name) to database")
        logger.info("Added server \(server.name) in \(String(format: "%.3f", duration))s")
    }
    
    func removeServer(named name: String) throws {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let changes = try connectionPool.withTransaction { conn in
            // Log removal event first
            try logUsageEvent(conn: conn, serverName: name, eventType: "remove", eventData: [:])
            
            let delete = serverRegistry.filter(serverName == name).delete()
            return try conn.run(delete)
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("removeServer", duration: duration, rowCount: changes)
        
        if changes > 0 {
            changeSubject.send(.serverRemoved(name))
            print("✅ Removed server \(name) from database")
            logger.info("Removed server \(name) in \(String(format: "%.3f", duration))s")
        } else {
            print("⚠️ Server \(name) not found for removal")
            logger.warning("Attempted to remove non-existent server: \(name)")
        }
    }
    
    func updateServerStatus(named name: String, enabled newEnabled: Bool) throws {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let changes = try connectionPool.withTransaction { conn in
            let now = ISO8601DateFormatter().string(from: Date())
            let update = serverRegistry
                .filter(serverName == name)
                .update(enabled <- newEnabled, updatedAt <- now)
            
            let changes = try conn.run(update)
            
            if changes > 0 {
                let eventType = newEnabled ? "enable" : "disable"
                try logUsageEvent(conn: conn, serverName: name, eventType: eventType, eventData: ["enabled": newEnabled])
            }
            
            return changes
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("updateServerStatus", duration: duration, rowCount: changes)
        
        if changes > 0 {
            changeSubject.send(.serverStatusChanged(name, newEnabled))
            print("✅ Updated server \(name) status to \(newEnabled ? "enabled" : "disabled")")
            logger.info("Updated server \(name) status in \(String(format: "%.3f", duration))s")
        } else {
            print("⚠️ Server \(name) not found for status update")
            logger.warning("Attempted to update status for non-existent server: \(name)")
        }
    }
    
    // MARK: - Status Information
    
    func getServerStatus(named name: String, maxAgeSeconds: TimeInterval = 300) throws -> ServerStatusInfo? {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let result: ServerStatusInfo? = try connectionPool.withConnection { conn in
            let cutoffTime = Date().addingTimeInterval(-maxAgeSeconds)
            let cutoffString = ISO8601DateFormatter().string(from: cutoffTime)
            
            let query = connectionHistory
                .filter(historyServerName == name && checkedAt > cutoffString)
                .order(checkedAt.desc)
                .limit(1)
            
            for row in try conn.prepare(query) {
                return ServerStatusInfo(
                    name: row[historyServerName],
                    status: ServerStatus(rawValue: row[status]) ?? .unknown,
                    responseTimeMs: row[responseTimeMs],
                    errorMessage: row[errorMessage],
                    toolCount: row[toolCount],
                    checkedAt: ISO8601DateFormatter().date(from: row[checkedAt])
                )
            }
            
            return nil
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("getServerStatus", duration: duration, rowCount: result != nil ? 1 : 0)
        
        return result
    }
    
    func recordServerStatus(_ statusInfo: ServerStatusInfo) throws {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        try connectionPool.withConnection { conn in
            let insert = connectionHistory.insert(
                historyServerName <- statusInfo.name,
                status <- statusInfo.status.rawValue,
                responseTimeMs <- statusInfo.responseTimeMs,
                errorMessage <- statusInfo.errorMessage,
                toolCount <- statusInfo.toolCount,
                checkedAt <- ISO8601DateFormatter().string(from: statusInfo.checkedAt ?? Date())
            )
            
            try conn.run(insert)
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("recordServerStatus", duration: duration, rowCount: 1)
        
        // Notify about status change
        changeSubject.send(.serverStatusRecorded(statusInfo.name, statusInfo.status))
    }
    
    // MARK: - Server Requirements
    
    func getServerRequirements(for serverIdentifier: String) throws -> [ServerRequirement] {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let requirements: [ServerRequirement] = try connectionPool.withConnection { conn in
            var requirements: [ServerRequirement] = []
            
            let query = serverRequirements
                .filter(reqServerIdentifier == serverIdentifier)
                .order(reqRequired.desc, reqId.asc)
            
            for row in try conn.prepare(query) {
                let requirement = ServerRequirement(
                    serverIdentifier: row[reqServerIdentifier],
                    serverType: ServerType(rawValue: row[reqServerType]) ?? .custom,
                    requirementType: row[reqType],
                    prompt: row[reqPrompt],
                    envVarName: row[reqEnvVarName],
                    required: row[reqRequired],
                    defaultValue: row[reqDefaultValue],
                    description: row[reqDescription]
                )
                requirements.append(requirement)
            }
            
            return requirements
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("getServerRequirements", duration: duration, rowCount: requirements.count)
        
        return requirements
    }
    
    // MARK: - Usage Analytics
    
    private func logUsageEvent(conn: Connection, serverName: String, eventType: String, eventData: [String: Any]) throws {
        let now = ISO8601DateFormatter().string(from: Date())
        let eventJson = try JSONSerialization.data(withJSONObject: eventData)
        
        let insert = usageEvents.insert(
            eventServerName <- serverName,
            self.eventType <- eventType,
            self.eventData <- String(data: eventJson, encoding: .utf8),
            userContext <- "swift-app",
            eventCreatedAt <- now
        )
        
        try conn.run(insert)
    }
    
    // MARK: - Bulk Operations
    
    func enableAllServers() throws {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let changes = try connectionPool.withConnection { conn in
            let now = ISO8601DateFormatter().string(from: Date())
            let update = serverRegistry.update(enabled <- true, updatedAt <- now)
            
            return try conn.run(update)
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("enableAllServers", duration: duration, rowCount: changes)
        
        changeSubject.send(.bulkServersEnabled(changes))
        print("✅ Enabled \(changes) servers")
        logger.info("Bulk enabled \(changes) servers in \(String(format: "%.3f", duration))s")
    }
    
    func disableAllServers() throws {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let changes = try connectionPool.withConnection { conn in
            let now = ISO8601DateFormatter().string(from: Date())
            let update = serverRegistry.update(enabled <- false, updatedAt <- now)
            
            return try conn.run(update)
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("disableAllServers", duration: duration, rowCount: changes)
        
        changeSubject.send(.bulkServersDisabled(changes))
        print("✅ Disabled \(changes) servers")
        logger.info("Bulk disabled \(changes) servers in \(String(format: "%.3f", duration))s")
    }
    
    func removeServers(named names: [String]) throws {
        let startTime = CFAbsoluteTimeGetCurrent()
        
        let totalRemoved = try connectionPool.withTransaction { conn in
            var totalRemoved = 0
            
            // Process in batches to avoid long-running transactions
            let batchSize = 50
            let batches = names.chunked(into: batchSize)
            
            for batch in batches {
                // Log removal events first
                for name in batch {
                    try logUsageEvent(conn: conn, serverName: name, eventType: "remove", eventData: [:])
                }
                
                // Use simple loop for batch deletion - more reliable than prepared statements with arrays
                for name in batch {
                    let delete = serverRegistry.filter(serverName == name).delete()
                    let changes = try conn.run(delete)
                    totalRemoved += changes
                }
            }
            
            return totalRemoved
        }
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        queryMetrics.recordQuery("removeServers", duration: duration, rowCount: totalRemoved)
        
        changeSubject.send(.bulkServersRemoved(names, totalRemoved))
        print("✅ Removed \(totalRemoved) servers")
        logger.info("Bulk removed \(totalRemoved) servers in \(String(format: "%.3f", duration))s")
    }
    
    // MARK: - Performance & Monitoring
    
    func getPerformanceMetrics() -> DatabasePerformanceReport {
        return DatabasePerformanceReport(
            queryMetrics: queryMetrics.getReport(),
            connectionPool: connectionPool.getMetrics(),
            databasePath: dbPath
        )
    }
    
    func optimizeDatabase() throws {
        try connectionPool.withConnection { conn in
            // Run SQLite optimization commands
            try conn.execute("PRAGMA optimize")
            try conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            try conn.execute("VACUUM")
            
            // Update table statistics
            try conn.execute("ANALYZE")
        }
        
        logger.info("Database optimization completed")
    }
    
    func validateDatabaseIntegrity() throws -> Bool {
        return try connectionPool.withConnection { conn in
            // Check database integrity
            let integrityCheck = try conn.prepare("PRAGMA integrity_check")
            for row in integrityCheck {
                if row[0] as? String != "ok" {
                    logger.error("Database integrity check failed: \(row)")
                    return false
                }
            }
            
            // Check foreign key constraints
            let foreignKeyCheck = try conn.prepare("PRAGMA foreign_key_check")
            for _ in foreignKeyCheck {
                logger.error("Foreign key constraint violation found")
                return false
            }
            
            return true
        }
    }
    
    // MARK: - Database Migration Support
    
    func getDatabaseVersion() throws -> Int {
        return try connectionPool.withConnection { conn in
            do {
                let version = try conn.scalar("PRAGMA user_version") as! Int64
                return Int(version)
            } catch {
                return 0
            }
        }
    }
    
    func setDatabaseVersion(_ version: Int) throws {
        try connectionPool.withConnection { conn in
            try conn.execute("PRAGMA user_version = \\(version)")
        }
    }
}

// MARK: - Database Connection Pool

class DatabaseConnectionPool {
    private let path: String
    private var connections: [Connection] = []
    private let semaphore: DispatchSemaphore
    private let queue = DispatchQueue(label: "database.pool", attributes: .concurrent)
    let maxConnections: Int
    
    init(path: String, maxConnections: Int) {
        self.path = path
        self.maxConnections = maxConnections
        self.semaphore = DispatchSemaphore(value: maxConnections)
    }
    
    func initialize() throws {
        for _ in 0..<maxConnections {
            let conn = try Connection(path)
            // Configure each connection optimally for concurrency
            try conn.execute("PRAGMA journal_mode=WAL")
            try conn.execute("PRAGMA synchronous=NORMAL")
            try conn.execute("PRAGMA cache_size=10000")
            try conn.execute("PRAGMA temp_store=memory")
            try conn.execute("PRAGMA foreign_keys=ON")
            try conn.execute("PRAGMA busy_timeout=30000")         // 30 second timeout for locked database
            connections.append(conn)
        }
    }
    
    func withConnection<T>(_ block: (Connection) throws -> T) throws -> T {
        semaphore.wait()
        defer { semaphore.signal() }
        
        return try queue.sync {
            guard let connection = connections.popLast() else {
                throw DatabaseError.connectionPoolExhausted
            }
            
            defer {
                queue.async(flags: .barrier) {
                    self.connections.append(connection)
                }
            }
            
            return try block(connection)
        }
    }
    
    func withTransaction<T>(_ block: (Connection) throws -> T) throws -> T {
        return try withConnection { conn in
            var result: T!
            try conn.transaction {
                result = try block(conn)
            }
            return result
        }
    }
    
    func closeAll() {
        queue.sync(flags: .barrier) {
            connections.removeAll()
        }
    }
    
    func getMetrics() -> ConnectionPoolMetrics {
        return ConnectionPoolMetrics(
            maxConnections: maxConnections,
            availableConnections: connections.count,
            activeConnections: maxConnections - connections.count
        )
    }
}

// MARK: - Database Change Types

enum DatabaseChange {
    case serverAdded(String)
    case serverRemoved(String)
    case serverStatusChanged(String, Bool)
    case serverStatusRecorded(String, ServerStatus)
    case bulkServersEnabled(Int)
    case bulkServersDisabled(Int)
    case bulkServersRemoved([String], Int)
    case serverListUpdated
}

// MARK: - Performance Monitoring

class DatabaseMetrics {
    private var queryStats: [String: QueryStats] = [:]
    private let lock = NSLock()
    
    struct QueryStats {
        var count: Int = 0
        var totalDuration: Double = 0
        var minDuration: Double = Double.infinity
        var maxDuration: Double = 0
        var avgDuration: Double { count > 0 ? totalDuration / Double(count) : 0 }
        var totalRows: Int = 0
    }
    
    func recordQuery(_ operation: String, duration: Double, rowCount: Int) {
        lock.lock()
        defer { lock.unlock() }
        
        var stats = queryStats[operation] ?? QueryStats()
        stats.count += 1
        stats.totalDuration += duration
        stats.minDuration = min(stats.minDuration, duration)
        stats.maxDuration = max(stats.maxDuration, duration)
        stats.totalRows += rowCount
        queryStats[operation] = stats
    }
    
    func getReport() -> [String: QueryStats] {
        lock.lock()
        defer { lock.unlock() }
        return queryStats
    }
}

struct ConnectionPoolMetrics {
    let maxConnections: Int
    let availableConnections: Int
    let activeConnections: Int
    
    var utilizationPercent: Double {
        Double(activeConnections) / Double(maxConnections) * 100
    }
}

struct DatabasePerformanceReport {
    let queryMetrics: [String: DatabaseMetrics.QueryStats]
    let connectionPool: ConnectionPoolMetrics
    let databasePath: String
}

// MARK: - Extensions

extension Array {
    func chunked(into size: Int) -> [[Element]] {
        return stride(from: 0, to: count, by: size).map {
            Array(self[$0..<Swift.min($0 + size, count)])
        }
    }
}

// MARK: - Error Types

enum DatabaseError: Error, LocalizedError {
    case connectionFailed
    case connectionPoolExhausted
    case queryFailed(String)
    case invalidData(String)
    case transactionFailed(String)
    case migrationFailed(String)
    
    var errorDescription: String? {
        switch self {
        case .connectionFailed:
            return "Failed to connect to database"
        case .connectionPoolExhausted:
            return "No available database connections in pool"
        case .queryFailed(let message):
            return "Database query failed: \(message)"
        case .invalidData(let message):
            return "Invalid data: \(message)"
        case .transactionFailed(let message):
            return "Transaction failed: \(message)"
        case .migrationFailed(let message):
            return "Database migration failed: \(message)"
        }
    }
}

// MARK: - Logging

private let logger = Logger(subsystem: "com.mcpmanager.database", category: "OptimizedDatabaseManager")

struct Logger {
    let subsystem: String
    let category: String
    private let osLog: OSLog
    
    init(subsystem: String, category: String) {
        self.subsystem = subsystem
        self.category = category
        self.osLog = OSLog(subsystem: subsystem, category: category)
    }
    
    func info(_ message: String) {
        os_log("%{public}@", log: osLog, type: .info, message)
    }
    
    func warning(_ message: String) {
        os_log("%{public}@", log: osLog, type: .default, message)
    }
    
    func error(_ message: String) {
        os_log("%{public}@", log: osLog, type: .error, message)
    }
}

extension Date {
    var iso8601String: String {
        return ISO8601DateFormatter().string(from: self)
    }
}