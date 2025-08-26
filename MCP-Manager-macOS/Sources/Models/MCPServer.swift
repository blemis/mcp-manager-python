//
//  MCPServer.swift
//  MCP-Manager-macOS
//
//  Native Swift models matching Python CLI's ServerInfo and ServerStatus
//

import Foundation

// MARK: - Enums

enum ServerStatus: String, CaseIterable {
    case connected = "connected"
    case failed = "failed"
    case timeout = "timeout"
    case unknown = "unknown"
    
    var displayName: String {
        switch self {
        case .connected: return "Connected"
        case .failed: return "Failed"
        case .timeout: return "Timeout"
        case .unknown: return "Unknown"
        }
    }
    
    var isHealthy: Bool {
        return self == .connected
    }
}

enum ServerType: String, CaseIterable {
    case npm = "npm"
    case docker = "docker"
    case dockerDesktop = "docker-desktop"
    case custom = "custom"
    
    var displayName: String {
        switch self {
        case .npm: return "NPM"
        case .docker: return "Docker"
        case .dockerDesktop: return "Docker Desktop"
        case .custom: return "Custom"
        }
    }
}

enum ServerScope: String, CaseIterable {
    case global = "global"
    case user = "user"
    case project = "project"
    
    var displayName: String {
        switch self {
        case .global: return "Global"
        case .user: return "User"
        case .project: return "Project"
        }
    }
}

// MARK: - Core Models

struct MCPServer: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let serverType: ServerType
    let command: String
    let args: [String]
    let env: [String: String]
    let enabled: Bool
    let scope: ServerScope
    let configHash: String
    
    // Optional fields
    let description: String?
    let installId: String?
    let package: String?
    let createdAt: Date?
    let updatedAt: Date?
    
    // Status information (populated from separate queries)
    var statusInfo: ServerStatusInfo?
    
    init(name: String,
         serverType: ServerType,
         command: String,
         args: [String] = [],
         env: [String: String] = [:],
         enabled: Bool = true,
         scope: ServerScope = .user,
         configHash: String = "",
         description: String? = nil,
         installId: String? = nil,
         package: String? = nil,
         createdAt: Date? = nil,
         updatedAt: Date? = nil,
         statusInfo: ServerStatusInfo? = nil) {
        
        self.name = name
        self.serverType = serverType
        self.command = command
        self.args = args
        self.env = env
        self.enabled = enabled
        self.scope = scope
        self.configHash = configHash.isEmpty ? Self.calculateConfigHash(command: command, args: args, env: env, enabled: enabled) : configHash
        self.description = description
        self.installId = installId
        self.package = package
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.statusInfo = statusInfo
    }
    
    // MARK: - Helper Methods
    
    /// Calculate configuration hash for drift detection (matches Python implementation)
    static func calculateConfigHash(command: String, args: [String], env: [String: String], enabled: Bool) -> String {
        let configData: [String: Any] = [
            "command": command,
            "args": args,
            "env": env,
            "enabled": enabled
        ]
        
        guard let jsonData = try? JSONSerialization.data(withJSONObject: configData, options: [.sortedKeys]),
              let jsonString = String(data: jsonData, encoding: .utf8) else {
            return ""
        }
        
        return jsonString.sha256.prefix(16).description
    }
    
    var displayStatus: String {
        if !enabled {
            return "Disabled"
        }
        return statusInfo?.status.displayName ?? "Unknown"
    }
    
    var statusColor: String {
        if !enabled {
            return "gray"
        }
        
        guard let status = statusInfo?.status else {
            return "gray"
        }
        
        switch status {
        case .connected:
            return "green"
        case .failed:
            return "red"
        case .timeout:
            return "orange"
        case .unknown:
            return "gray"
        }
    }
    
    var isHealthy: Bool {
        enabled && (statusInfo?.status.isHealthy ?? false)
    }
    
    // MARK: - Hashable & Identifiable
    
    func hash(into hasher: inout Hasher) {
        hasher.combine(name)
    }
    
    static func == (lhs: MCPServer, rhs: MCPServer) -> Bool {
        lhs.name == rhs.name
    }
}

// MARK: - Status Information

struct ServerStatusInfo {
    let name: String
    let status: ServerStatus
    let responseTimeMs: Double?
    let errorMessage: String?
    let toolCount: Int?
    let checkedAt: Date?
    
    init(name: String,
         status: ServerStatus,
         responseTimeMs: Double? = nil,
         errorMessage: String? = nil,
         toolCount: Int? = nil,
         checkedAt: Date? = nil) {
        
        self.name = name
        self.status = status
        self.responseTimeMs = responseTimeMs
        self.errorMessage = errorMessage
        self.toolCount = toolCount
        self.checkedAt = checkedAt
    }
    
    var responseTimeDisplay: String {
        guard let responseTime = responseTimeMs else { return "N/A" }
        return String(format: "%.0f ms", responseTime)
    }
    
    var toolCountDisplay: String {
        guard let count = toolCount else { return "N/A" }
        return "\(count) tool\(count == 1 ? "" : "s")"
    }
}

// MARK: - Server Requirements

struct ServerRequirement {
    let id = UUID()
    let serverIdentifier: String
    let serverType: ServerType
    let requirementType: String
    let prompt: String
    let envVarName: String?
    let required: Bool
    let defaultValue: String?
    let description: String?
    
    init(serverIdentifier: String,
         serverType: ServerType,
         requirementType: String,
         prompt: String,
         envVarName: String? = nil,
         required: Bool = true,
         defaultValue: String? = nil,
         description: String? = nil) {
        
        self.serverIdentifier = serverIdentifier
        self.serverType = serverType
        self.requirementType = requirementType
        self.prompt = prompt
        self.envVarName = envVarName
        self.required = required
        self.defaultValue = defaultValue
        self.description = description
    }
}

// MARK: - Extensions

extension String {
    /// Simple SHA256 implementation for config hashing
    var sha256: String {
        guard let data = self.data(using: .utf8) else { return "" }
        return data.sha256
    }
}

extension Data {
    var sha256: String {
        let digest = self.withUnsafeBytes { bytes in
            // Simple hash implementation for config drift detection
            // In production, you'd use CommonCrypto or CryptoKit
            var result: UInt64 = 5381
            for byte in bytes {
                result = ((result << 5) &+ result) &+ UInt64(byte)
            }
            
            // Convert to hex string
            return String(format: "%016llx", result)
        }
        return digest
    }
}