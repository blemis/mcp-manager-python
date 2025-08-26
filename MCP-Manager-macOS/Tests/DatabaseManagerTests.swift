//
//  DatabaseManagerTests.swift
//  MCP-Manager-macOS Tests
//
//  Unit tests for the DatabaseManager
//

import XCTest
@testable import MCP_Manager_macOS

final class DatabaseManagerTests: XCTestCase {
    
    var databaseManager: DatabaseManager!
    
    override func setUpWithError() throws {
        // Create a temporary database for testing
        let tempDir = FileManager.default.temporaryDirectory
        let testDBPath = tempDir.appendingPathComponent("test_mcp_manager_\(UUID().uuidString).db").path
        
        // Use dedicated test database path
        databaseManager = DatabaseManager(databasePath: testDBPath)
    }
    
    override func tearDownWithError() throws {
        databaseManager = nil
    }
    
    func testDatabaseInitialization() throws {
        // Test that database initializes without errors
        XCTAssertNotNil(databaseManager)
        
        // Test that we can list servers (should be empty initially)
        let servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 0)
    }
    
    func testAddServer() throws {
        // Create a test server
        let server = MCPServer(
            name: "test-server",
            serverType: .npm,
            command: "npx",
            args: ["-y", "@test/server"],
            env: ["TEST": "value"],
            enabled: true,
            scope: .user,
            description: "Test server",
            installId: "@test/server",
            package: "@test/server"
        )
        
        // Add server to database
        try databaseManager.addServer(server)
        
        // Verify server was added
        let servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 1)
        XCTAssertEqual(servers.first?.name, "test-server")
        XCTAssertEqual(servers.first?.serverType, .npm)
        XCTAssertEqual(servers.first?.enabled, true)
    }
    
    func testRemoveServer() throws {
        // Add a server
        let server = MCPServer(
            name: "test-server",
            serverType: .custom,
            command: "test-command",
            args: ["arg1"],
            env: [:],
            enabled: false,
            scope: .project
        )
        
        try databaseManager.addServer(server)
        
        // Verify it was added
        var servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 1)
        
        // Remove the server
        try databaseManager.removeServer(named: "test-server")
        
        // Verify it was removed
        servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 0)
    }
    
    func testUpdateServerStatus() throws {
        // Add a server
        let server = MCPServer(
            name: "test-server",
            serverType: .docker,
            command: "docker",
            args: ["run", "test"],
            env: [:],
            enabled: false,
            scope: .user
        )
        
        try databaseManager.addServer(server)
        
        // Update server status
        try databaseManager.updateServerStatus(named: "test-server", enabled: true)
        
        // Verify status was updated
        let servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 1)
        XCTAssertEqual(servers.first?.enabled, true)
    }
    
    func testServerStatusRecording() throws {
        // Add a server first
        let server = MCPServer(
            name: "test-server",
            serverType: .npm,
            command: "npx",
            args: ["-y", "@test/server"],
            env: [:],
            enabled: true,
            scope: .user
        )
        
        try databaseManager.addServer(server)
        
        // Record status information
        let statusInfo = ServerStatusInfo(
            name: "test-server",
            status: .connected,
            responseTimeMs: 45.2,
            errorMessage: nil,
            toolCount: 5,
            checkedAt: Date()
        )
        
        try databaseManager.recordServerStatus(statusInfo)
        
        // Retrieve status
        let retrievedStatus = try databaseManager.getServerStatus(named: "test-server")
        XCTAssertNotNil(retrievedStatus)
        XCTAssertEqual(retrievedStatus?.status, .connected)
        XCTAssertEqual(retrievedStatus?.responseTimeMs, 45.2)
        XCTAssertEqual(retrievedStatus?.toolCount, 5)
    }
    
    func testBulkOperations() throws {
        // Add multiple servers
        let server1 = MCPServer(name: "server1", serverType: .npm, command: "npx", args: [], env: [:], enabled: false, scope: .user)
        let server2 = MCPServer(name: "server2", serverType: .docker, command: "docker", args: [], env: [:], enabled: false, scope: .user)
        let server3 = MCPServer(name: "server3", serverType: .custom, command: "custom", args: [], env: [:], enabled: false, scope: .user)
        
        try databaseManager.addServer(server1)
        try databaseManager.addServer(server2)
        try databaseManager.addServer(server3)
        
        // Verify all are disabled
        var servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 3)
        XCTAssertTrue(servers.allSatisfy { !$0.enabled })
        
        // Enable all servers
        try databaseManager.enableAllServers()
        
        // Verify all are enabled
        servers = try databaseManager.listServers()
        XCTAssertTrue(servers.allSatisfy { $0.enabled })
        
        // Disable all servers
        try databaseManager.disableAllServers()
        
        // Verify all are disabled
        servers = try databaseManager.listServers()
        XCTAssertTrue(servers.allSatisfy { !$0.enabled })
        
        // Remove multiple servers
        try databaseManager.removeServers(named: ["server1", "server3"])
        
        // Verify only server2 remains
        servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 1)
        XCTAssertEqual(servers.first?.name, "server2")
    }
    
    func testConfigHashCalculation() {
        // Test config hash calculation
        let server1 = MCPServer(
            name: "test",
            serverType: .npm,
            command: "npx",
            args: ["-y", "test"],
            env: ["KEY": "value"],
            enabled: true,
            scope: .user
        )
        
        let server2 = MCPServer(
            name: "test",
            serverType: .npm,
            command: "npx",
            args: ["-y", "test"],
            env: ["KEY": "value"],
            enabled: true,
            scope: .user
        )
        
        // Same configuration should produce same hash
        XCTAssertEqual(server1.configHash, server2.configHash)
        
        // Different configuration should produce different hash
        let server3 = MCPServer(
            name: "test",
            serverType: .npm,
            command: "npx",
            args: ["-y", "different"],
            env: ["KEY": "value"],
            enabled: true,
            scope: .user
        )
        
        XCTAssertNotEqual(server1.configHash, server3.configHash)
    }
}

// MARK: - MCPServer Tests

final class MCPServerTests: XCTestCase {
    
    func testServerInitialization() {
        let server = MCPServer(
            name: "test-server",
            serverType: .npm,
            command: "npx",
            args: ["-y", "@test/server"],
            env: ["NODE_ENV": "production"],
            enabled: true,
            scope: .user,
            description: "Test server description"
        )
        
        XCTAssertEqual(server.name, "test-server")
        XCTAssertEqual(server.serverType, .npm)
        XCTAssertEqual(server.command, "npx")
        XCTAssertEqual(server.args, ["-y", "@test/server"])
        XCTAssertEqual(server.env["NODE_ENV"], "production")
        XCTAssertEqual(server.enabled, true)
        XCTAssertEqual(server.scope, .user)
        XCTAssertEqual(server.description, "Test server description")
        XCTAssertFalse(server.configHash.isEmpty)
    }
    
    func testServerStatusDisplay() {
        // Test disabled server
        let disabledServer = MCPServer(
            name: "disabled",
            serverType: .npm,
            command: "npx",
            args: [],
            env: [:],
            enabled: false,
            scope: .user
        )
        
        XCTAssertEqual(disabledServer.displayStatus, "Disabled")
        XCTAssertFalse(disabledServer.isHealthy)
        
        // Test enabled server with status
        var enabledServer = MCPServer(
            name: "enabled",
            serverType: .npm,
            command: "npx",
            args: [],
            env: [:],
            enabled: true,
            scope: .user
        )
        
        enabledServer.statusInfo = ServerStatusInfo(
            name: "enabled",
            status: .connected,
            responseTimeMs: 50.0,
            toolCount: 10
        )
        
        XCTAssertEqual(enabledServer.displayStatus, "Connected")
        XCTAssertTrue(enabledServer.isHealthy)
    }
    
    func testServerTypeEnums() {
        // Test ServerType enum
        XCTAssertEqual(ServerType.npm.displayName, "NPM")
        XCTAssertEqual(ServerType.docker.displayName, "Docker")
        XCTAssertEqual(ServerType.dockerDesktop.displayName, "Docker Desktop")
        XCTAssertEqual(ServerType.custom.displayName, "Custom")
        
        // Test ServerStatus enum
        XCTAssertEqual(ServerStatus.connected.displayName, "Connected")
        XCTAssertEqual(ServerStatus.failed.displayName, "Failed")
        XCTAssertEqual(ServerStatus.timeout.displayName, "Timeout")
        XCTAssertEqual(ServerStatus.unknown.displayName, "Unknown")
        
        XCTAssertTrue(ServerStatus.connected.isHealthy)
        XCTAssertFalse(ServerStatus.failed.isHealthy)
        XCTAssertFalse(ServerStatus.timeout.isHealthy)
        XCTAssertFalse(ServerStatus.unknown.isHealthy)
        
        // Test ServerScope enum
        XCTAssertEqual(ServerScope.global.displayName, "Global")
        XCTAssertEqual(ServerScope.user.displayName, "User")
        XCTAssertEqual(ServerScope.project.displayName, "Project")
    }
}