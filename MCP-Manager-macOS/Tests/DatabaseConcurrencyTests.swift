//
//  DatabaseConcurrencyTests.swift
//  MCP-Manager-macOS Tests
//
//  Performance and concurrency tests for enterprise-grade database operations
//

import XCTest
import Foundation
@testable import MCP_Manager_macOS

final class DatabaseConcurrencyTests: XCTestCase {
    
    var databaseManager: DatabaseManager!
    var testDBPath: String!
    
    override func setUpWithError() throws {
        // Create a temporary database for testing with connection pooling
        let tempDir = FileManager.default.temporaryDirectory
        testDBPath = tempDir.appendingPathComponent("test_concurrent_\(UUID().uuidString).db").path
        
        // Initialize with larger connection pool for concurrency testing
        databaseManager = DatabaseManager(databasePath: testDBPath, poolSize: 10)
    }
    
    override func tearDownWithError() throws {
        databaseManager = nil
        try? FileManager.default.removeItem(atPath: testDBPath)
    }
    
    // MARK: - Concurrent Read Tests
    
    func testConcurrentReads() throws {
        // Add test data first
        let testServers = generateTestServers(count: 100)
        for server in testServers {
            try databaseManager.addServer(server)
        }
        
        let expectation = self.expectation(description: "Concurrent reads")
        expectation.expectedFulfillmentCount = 10
        
        let startTime = CFAbsoluteTimeGetCurrent()
        
        // Perform 10 concurrent read operations
        for i in 0..<10 {
            DispatchQueue.global().async {
                do {
                    let servers = try self.databaseManager.listServers()
                    XCTAssertEqual(servers.count, 100, "Thread \(i) should read all servers")
                    expectation.fulfill()
                } catch {
                    XCTFail("Thread \(i) failed to read servers: \(error)")
                    expectation.fulfill()
                }
            }
        }
        
        waitForExpectations(timeout: 10.0)
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        print("✅ 10 concurrent reads completed in \(String(format: "%.3f", duration))s")
        
        // Should complete quickly with connection pooling
        XCTAssertLessThan(duration, 2.0, "Concurrent reads should be fast with connection pooling")
    }
    
    // MARK: - Concurrent Write Tests
    
    func testConcurrentWrites() throws {
        let expectation = self.expectation(description: "Concurrent writes")
        expectation.expectedFulfillmentCount = 20
        
        let startTime = CFAbsoluteTimeGetCurrent()
        
        // Perform 20 concurrent write operations
        for i in 0..<20 {
            DispatchQueue.global().async {
                do {
                    let server = MCPServer(
                        name: "concurrent-server-\(i)",
                        serverType: .npm,
                        command: "npx",
                        args: ["-y", "test-\(i)"],
                        env: ["TEST": "concurrent"],
                        enabled: true,
                        scope: .user
                    )
                    try self.databaseManager.addServer(server)
                    expectation.fulfill()
                } catch {
                    XCTFail("Thread \(i) failed to add server: \(error)")
                    expectation.fulfill()
                }
            }
        }
        
        waitForExpectations(timeout: 15.0)
        
        let duration = CFAbsoluteTimeGetCurrent() - startTime
        print("✅ 20 concurrent writes completed in \(String(format: "%.3f", duration))s")
        
        // Verify all servers were added
        let servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 20, "All concurrent writes should succeed")
        
        // Should handle concurrent writes efficiently
        XCTAssertLessThan(duration, 5.0, "Concurrent writes should complete within reasonable time")
    }
    
    // MARK: - Performance Metrics Tests
    
    func testPerformanceMetrics() throws {
        // Perform various operations
        let testServers = generateTestServers(count: 50)
        for server in testServers {
            try databaseManager.addServer(server)
        }
        
        // Perform multiple reads
        for _ in 0..<10 {
            let _ = try databaseManager.listServers()
        }
        
        // Get performance report
        let report = databaseManager.getPerformanceMetrics()
        
        XCTAssertGreaterThan(report.queryMetrics.count, 0, "Should have query metrics")
        XCTAssertGreaterThan(report.connectionPool.maxConnections, 0, "Should report connection pool size")
        
        // Verify specific metrics
        if let addServerStats = report.queryMetrics["addServer"] {
            XCTAssertEqual(addServerStats.count, 50, "Should track all add operations")
            XCTAssertGreaterThan(addServerStats.avgDuration, 0, "Should have average duration")
        }
        
        print("📊 Performance Report:")
        print("   Database Path: \(report.databasePath)")
        print("   Connection Pool: \(report.connectionPool.activeConnections)/\(report.connectionPool.maxConnections) (\(String(format: "%.1f", report.connectionPool.utilizationPercent))% utilization)")
        
        for (operation, stats) in report.queryMetrics {
            print("   \(operation): \(stats.count) ops, avg \(String(format: "%.3f", stats.avgDuration))s")
        }
    }
    
    // MARK: - Database Optimization Tests
    
    func testDatabaseOptimization() throws {
        // Add test data
        let testServers = generateTestServers(count: 100)
        for server in testServers {
            try databaseManager.addServer(server)
        }
        
        // Perform optimization
        try databaseManager.optimizeDatabase()
        
        // Verify database still works after optimization
        let servers = try databaseManager.listServers()
        XCTAssertEqual(servers.count, 100, "Data should be preserved after optimization")
        
        // Verify integrity
        XCTAssertTrue(try databaseManager.validateDatabaseIntegrity(), "Database should be valid after optimization")
    }
    
    // MARK: - Python CLI Compatibility Tests
    
    func testPythonCompatibilitySchema() throws {
        // Test that our schema matches Python CLI exactly
        let testServer = MCPServer(
            name: "python-compat-test",
            serverType: .dockerDesktop,
            command: "docker",
            args: ["run", "--rm", "test/server"],
            env: ["DOCKER_HOST": "unix:///var/run/docker.sock"],
            enabled: true,
            scope: .user,
            description: "Python compatibility test server",
            installId: "dd-test-server",
            package: "docker-desktop/test-server"
        )
        
        try databaseManager.addServer(testServer)
        
        // Verify we can retrieve with all fields
        let retrieved = try databaseManager.listServers().first
        XCTAssertEqual(retrieved?.name, "python-compat-test")
        XCTAssertEqual(retrieved?.serverType, .dockerDesktop)
        XCTAssertEqual(retrieved?.args, ["run", "--rm", "test/server"])
        XCTAssertEqual(retrieved?.env["DOCKER_HOST"], "unix:///var/run/docker.sock")
        XCTAssertEqual(retrieved?.description, "Python compatibility test server")
        XCTAssertEqual(retrieved?.installId, "dd-test-server")
        XCTAssertEqual(retrieved?.package, "docker-desktop/test-server")
        XCTAssertNotNil(retrieved?.createdAt)
        XCTAssertNotNil(retrieved?.updatedAt)
    }
    
    // MARK: - Helper Methods
    
    private func generateTestServers(count: Int) -> [MCPServer] {
        return (0..<count).map { i in
            MCPServer(
                name: "test-server-\(i)",
                serverType: [.npm, .docker, .custom].randomElement()!,
                command: "test-command-\(i)",
                args: ["arg1", "arg\(i)"],
                env: ["TEST_VAR_\(i)": "value\(i)"],
                enabled: Bool.random(),
                scope: [.user, .project, .global].randomElement()!,
                description: "Test server \(i) for performance testing"
            )
        }
    }
}