#!/usr/bin/env swift

import Foundation
import SQLite3

// Test script to verify Swift can read Python MCP Manager database
print("🧪 Testing Swift + Python MCP Database Integration")
print("="*60)

// Database path (same as Python CLI)
let homeDir = FileManager.default.homeDirectoryForCurrentUser
let dbPath = homeDir.appendingPathComponent(".local/share/mcp-manager/server_state.db").path

print("📁 Database path: \(dbPath)")

// Check if database exists
guard FileManager.default.fileExists(atPath: dbPath) else {
    print("❌ Database file not found!")
    exit(1)
}

var db: OpaquePointer?

// Open database
guard sqlite3_open(dbPath, &db) == SQLITE_OK else {
    print("❌ Failed to open database")
    exit(1)
}

print("✅ Database opened successfully")

// Query all servers (same as mcp-manager list)
let query = "SELECT name, server_type, command, enabled FROM mcp_server_registry ORDER BY name"
var statement: OpaquePointer?

guard sqlite3_prepare_v2(db, query, -1, &statement, nil) == SQLITE_OK else {
    print("❌ Failed to prepare query")
    sqlite3_close(db)
    exit(1)
}

print("\n📊 MCP Servers from Shared Database:")
print("="*60)

var serverCount = 0
while sqlite3_step(statement) == SQLITE_ROW {
    let name = String(cString: sqlite3_column_text(statement, 0))
    let type = String(cString: sqlite3_column_text(statement, 1))
    let command = String(cString: sqlite3_column_text(statement, 2))
    let enabled = sqlite3_column_int(statement, 3) == 1
    
    let status = enabled ? "✅ Enabled" : "❌ Disabled"
    let typeIcon = type == "docker" ? "🐳" : 
                   type == "docker-desktop" ? "🖥️" : 
                   type == "npm" ? "📦" : "⚙️"
    
    print("\(typeIcon) \(name)")
    print("   Type: \(type)")
    print("   Command: \(command)")
    print("   Status: \(status)")
    print()
    
    serverCount += 1
}

print("📈 Total servers found: \(serverCount)")

// Cleanup
sqlite3_finalize(statement)
sqlite3_close(db)

print("\n🎉 SUCCESS: Swift successfully read Python MCP Manager database!")
print("✅ Database integration works perfectly")
print("✅ Schema compatibility confirmed")
print("✅ Ready for SwiftUI app implementation")