#!/usr/bin/env swift

import Foundation
import SQLite3

// Test script to validate Swift can read/write same database as Python CLI
func testDatabaseIntegration() {
    let homeDir = FileManager.default.homeDirectoryForCurrentUser
    let dbPath = homeDir.appendingPathComponent(".local/share/mcp-manager/server_state.db").path
    
    print("Testing database integration at: \(dbPath)")
    
    var db: OpaquePointer?
    
    // Open database
    guard sqlite3_open(dbPath, &db) == SQLITE_OK else {
        print("❌ Failed to open database")
        return
    }
    defer { sqlite3_close(db) }
    
    // Test 1: Read existing data
    print("\n=== TEST 1: Reading existing servers ===")
    let selectSQL = "SELECT name, server_type, command, args, env, enabled FROM mcp_server_registry"
    var statement: OpaquePointer?
    
    if sqlite3_prepare_v2(db, selectSQL, -1, &statement, nil) == SQLITE_OK {
        while sqlite3_step(statement) == SQLITE_ROW {
            let name = String(cString: sqlite3_column_text(statement, 0))
            let serverType = String(cString: sqlite3_column_text(statement, 1))
            let command = String(cString: sqlite3_column_text(statement, 2))
            let args = String(cString: sqlite3_column_text(statement, 3))
            let env = String(cString: sqlite3_column_text(statement, 4))
            let enabled = sqlite3_column_int(statement, 5) == 1
            
            print("Server: \(name)")
            print("  Type: \(serverType)")
            print("  Command: \(command)")
            print("  Args: \(args)")
            print("  Env: \(env)")
            print("  Enabled: \(enabled)")
            print()
        }
    }
    sqlite3_finalize(statement)
    
    // Test 2: Write a test server (then remove it)
    print("=== TEST 2: Writing test server ===")
    let testServerName = "swift-test-server-" + UUID().uuidString
    let insertSQL = """
        INSERT INTO mcp_server_registry (name, server_type, command, args, env, enabled, scope, config_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    if sqlite3_prepare_v2(db, insertSQL, -1, &statement, nil) == SQLITE_OK {
        sqlite3_bind_text(statement, 1, testServerName, -1, nil)
        sqlite3_bind_text(statement, 2, "custom", -1, nil)
        sqlite3_bind_text(statement, 3, "echo", -1, nil)
        sqlite3_bind_text(statement, 4, "[\"hello\", \"world\"]", -1, nil)
        sqlite3_bind_text(statement, 5, "{\"TEST_VAR\": \"test_value\"}", -1, nil)
        sqlite3_bind_int(statement, 6, 1)
        sqlite3_bind_text(statement, 7, "user", -1, nil)
        sqlite3_bind_text(statement, 8, "test-hash", -1, nil)
        
        let dateFormatter = ISO8601DateFormatter()
        let now = dateFormatter.string(from: Date())
        sqlite3_bind_text(statement, 9, now, -1, nil)
        sqlite3_bind_text(statement, 10, now, -1, nil)
        
        if sqlite3_step(statement) == SQLITE_DONE {
            print("✅ Successfully inserted test server: \(testServerName)")
        } else {
            let errorMessage = String(cString: sqlite3_errmsg(db))
            print("❌ Failed to insert test server: \(errorMessage)")
        }
    }
    sqlite3_finalize(statement)
    
    // Test 3: Read the test server back
    print("\n=== TEST 3: Reading back test server ===")
    let readTestSQL = "SELECT * FROM mcp_server_registry WHERE name = ?"
    if sqlite3_prepare_v2(db, readTestSQL, -1, &statement, nil) == SQLITE_OK {
        sqlite3_bind_text(statement, 1, testServerName, -1, nil)
        
        if sqlite3_step(statement) == SQLITE_ROW {
            let name = String(cString: sqlite3_column_text(statement, 0))
            let args = String(cString: sqlite3_column_text(statement, 3))
            let env = String(cString: sqlite3_column_text(statement, 4))
            
            print("✅ Successfully read back test server:")
            print("  Name: \(name)")
            print("  Args JSON: \(args)")
            print("  Env JSON: \(env)")
            
            // Test JSON parsing
            if let argsData = args.data(using: .utf8),
               let argsArray = try? JSONSerialization.jsonObject(with: argsData) as? [String] {
                print("  Parsed args: \(argsArray)")
            }
            
            if let envData = env.data(using: .utf8),
               let envDict = try? JSONSerialization.jsonObject(with: envData) as? [String: String] {
                print("  Parsed env: \(envDict)")
            }
        }
    }
    sqlite3_finalize(statement)
    
    // Test 4: Clean up test server
    print("\n=== TEST 4: Cleaning up test server ===")
    let deleteSQL = "DELETE FROM mcp_server_registry WHERE name = ?"
    if sqlite3_prepare_v2(db, deleteSQL, -1, &statement, nil) == SQLITE_OK {
        sqlite3_bind_text(statement, 1, testServerName, -1, nil)
        
        if sqlite3_step(statement) == SQLITE_DONE {
            print("✅ Successfully deleted test server")
        } else {
            let errorMessage = String(cString: sqlite3_errmsg(db))
            print("❌ Failed to delete test server: \(errorMessage)")
        }
    }
    sqlite3_finalize(statement)
    
    print("\n=== DATABASE INTEGRATION TEST COMPLETE ===")
}

testDatabaseIntegration()