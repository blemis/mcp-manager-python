//
//  EditServerSheet.swift
//  MCP-Manager-macOS
//
//  Modal sheet for editing existing MCP servers
//

import SwiftUI

struct EditServerSheet: View {
    let server: MCPServer
    @ObservedObject var serverService: MCPServerService
    @Environment(\.dismiss) private var dismiss
    
    @State private var serverName: String
    @State private var selectedType: ServerType
    @State private var selectedScope: ServerScope
    @State private var description: String
    @State private var command: String
    @State private var arguments: String
    @State private var package: String
    @State private var environmentVars: [EnvironmentVariable] = []
    @State private var enabled: Bool
    
    @State private var validationError: String?
    @State private var isSaving = false
    
    struct EnvironmentVariable: Identifiable {
        let id = UUID()
        var key: String
        var value: String
    }
    
    init(server: MCPServer, serverService: MCPServerService) {
        self.server = server
        self.serverService = serverService
        
        // Initialize state from server
        _serverName = State(initialValue: server.name)
        _selectedType = State(initialValue: server.serverType)
        _selectedScope = State(initialValue: server.scope)
        _description = State(initialValue: server.description ?? "")
        _command = State(initialValue: server.command)
        _package = State(initialValue: server.package ?? "")
        _enabled = State(initialValue: server.enabled)
        
        // Parse arguments back to string
        let argsString: String
        switch server.serverType {
        case .npm:
            // Remove npx args (-y, package) and -- separator if present
            let filteredArgs = server.args.dropFirst(2) // Remove -y and package
            if filteredArgs.first == "--" {
                argsString = Array(filteredArgs.dropFirst()).joined(separator: " ")
            } else {
                argsString = Array(filteredArgs).joined(separator: " ")
            }
        case .docker, .dockerDesktop:
            // Remove docker run args and image name
            let dockerArgs = ["run", "--rm", "-it"]
            let filteredArgs = server.args.drop(while: { dockerArgs.contains($0) })
            if filteredArgs.first != nil {
                argsString = Array(filteredArgs.dropFirst()).joined(separator: " ")
            } else {
                argsString = server.args.joined(separator: " ")
            }
        case .custom:
            argsString = server.args.joined(separator: " ")
        }
        _arguments = State(initialValue: argsString)
        
        // Initialize environment variables
        _environmentVars = State(initialValue: server.env.map { 
            EnvironmentVariable(key: $0.key, value: $0.value) 
        })
    }
    
    var body: some View {
        NavigationView {
            Form {
                Section("Basic Information") {
                    TextField("Server Name", text: $serverName)
                        .textFieldStyle(.roundedBorder)
                        .disabled(true) // Server name cannot be changed
                        .foregroundColor(.secondary)
                    
                    Picker("Server Type", selection: $selectedType) {
                        ForEach(ServerType.allCases, id: \.self) { type in
                            Label(type.displayName, systemImage: iconForServerType(type))
                                .tag(type)
                        }
                    }
                    .disabled(true) // Server type cannot be changed
                    
                    Picker("Scope", selection: $selectedScope) {
                        ForEach(ServerScope.allCases, id: \.self) { scope in
                            Text(scope.displayName).tag(scope)
                        }
                    }
                    
                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(2...4)
                    
                    Toggle("Enabled", isOn: $enabled)
                }
                
                Section("Configuration") {
                    // Type-specific configuration
                    switch selectedType {
                    case .npm:
                        NPMEditView(package: $package, arguments: $arguments)
                    case .docker, .dockerDesktop:
                        DockerEditView(package: $package, arguments: $arguments)
                    case .custom:
                        CustomEditView(command: $command, arguments: $arguments)
                    }
                }
                
                Section("Environment Variables") {
                    EnvironmentVariablesEditView(environmentVars: $environmentVars)
                }
                
                if let error = validationError {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                            .font(.caption)
                    }
                }
            }
            .formStyle(.grouped)
            .navigationTitle("Edit Server")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save Changes") {
                        Task {
                            await saveServer()
                        }
                    }
                    .disabled(isSaving || !isFormValid)
                }
            }
        }
        .frame(width: 500, height: 600)
    }
    
    private var isFormValid: Bool {
        !serverName.isEmpty && 
        (selectedType != .custom || !command.isEmpty) &&
        (selectedType == .custom || !package.isEmpty)
    }
    
    private func iconForServerType(_ type: ServerType) -> String {
        switch type {
        case .npm: return "cube.box"
        case .docker: return "shippingbox"
        case .dockerDesktop: return "dock.rectangle"
        case .custom: return "hammer"
        }
    }
    
    private func saveServer() async {
        isSaving = true
        validationError = nil
        
        // Create updated server
        let updatedServer: MCPServer
        
        switch selectedType {
        case .npm:
            updatedServer = createUpdatedNPMServer()
        case .docker, .dockerDesktop:
            updatedServer = createUpdatedDockerServer()
        case .custom:
            updatedServer = createUpdatedCustomServer()
        }
        
        await serverService.addServer(updatedServer) // This will replace the existing server
        
        isSaving = false
        dismiss()
    }
    
    private func createUpdatedNPMServer() -> MCPServer {
        let args = ["-y", package]
        let additionalArgs = parseArguments(arguments)
        let finalArgs = additionalArgs.isEmpty ? args : args + ["--"] + additionalArgs
        
        return MCPServer(
            name: serverName,
            serverType: .npm,
            command: "npx",
            args: finalArgs,
            env: environmentVarsDict,
            enabled: enabled,
            scope: selectedScope,
            description: description.isEmpty ? nil : description,
            installId: package,
            package: package,
            createdAt: server.createdAt,
            updatedAt: Date()
        )
    }
    
    private func createUpdatedDockerServer() -> MCPServer {
        let baseArgs = ["run", "--rm", "-it", package]
        let additionalArgs = parseArguments(arguments)
        let finalArgs = additionalArgs.isEmpty ? baseArgs : baseArgs + additionalArgs
        
        return MCPServer(
            name: serverName,
            serverType: selectedType,
            command: "docker",
            args: finalArgs,
            env: environmentVarsDict,
            enabled: enabled,
            scope: selectedScope,
            description: description.isEmpty ? nil : description,
            installId: server.installId,
            package: package,
            createdAt: server.createdAt,
            updatedAt: Date()
        )
    }
    
    private func createUpdatedCustomServer() -> MCPServer {
        return MCPServer(
            name: serverName,
            serverType: .custom,
            command: command,
            args: parseArguments(arguments),
            env: environmentVarsDict,
            enabled: enabled,
            scope: selectedScope,
            description: description.isEmpty ? nil : description,
            createdAt: server.createdAt,
            updatedAt: Date()
        )
    }
    
    private func parseArguments(_ argumentString: String) -> [String] {
        argumentString
            .components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
    }
    
    private var environmentVarsDict: [String: String] {
        var dict: [String: String] = [:]
        for envVar in environmentVars {
            if !envVar.key.isEmpty && !envVar.value.isEmpty {
                dict[envVar.key] = envVar.value
            }
        }
        return dict
    }
}

// MARK: - NPM Edit View

struct NPMEditView: View {
    @Binding var package: String
    @Binding var arguments: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Package Name", text: $package)
                .textFieldStyle(.roundedBorder)
                .help("e.g., @modelcontextprotocol/server-filesystem")
            
            TextField("Additional Arguments (optional)", text: $arguments)
                .textFieldStyle(.roundedBorder)
                .help("e.g., --directory /path/to/files")
            
            Text("The server will be run with: npx -y \(package)\(arguments.isEmpty ? "" : " -- \(arguments)")")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Docker Edit View

struct DockerEditView: View {
    @Binding var package: String
    @Binding var arguments: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Docker Image", text: $package)
                .textFieldStyle(.roundedBorder)
                .help("e.g., mcp-server-sqlite")
            
            TextField("Additional Arguments (optional)", text: $arguments)
                .textFieldStyle(.roundedBorder)
                .help("e.g., --port 3000")
            
            Text("The server will be run with: docker run --rm -it \(package)\(arguments.isEmpty ? "" : " \(arguments)")")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Custom Edit View

struct CustomEditView: View {
    @Binding var command: String
    @Binding var arguments: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Command", text: $command)
                .textFieldStyle(.roundedBorder)
                .help("e.g., python3 or /path/to/executable")
            
            TextField("Arguments (optional)", text: $arguments)
                .textFieldStyle(.roundedBorder)
                .help("e.g., server.py --port 8080")
            
            Text("The server will be run with: \(command)\(arguments.isEmpty ? "" : " \(arguments)")")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Environment Variables Edit View

struct EnvironmentVariablesEditView: View {
    @Binding var environmentVars: [EditServerSheet.EnvironmentVariable]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(environmentVars.indices, id: \.self) { index in
                HStack {
                    TextField("KEY", text: $environmentVars[index].key)
                        .textFieldStyle(.roundedBorder)
                        .textCase(.uppercase)
                    
                    Text("=")
                        .foregroundColor(.secondary)
                    
                    TextField("value", text: $environmentVars[index].value)
                        .textFieldStyle(.roundedBorder)
                    
                    Button {
                        environmentVars.remove(at: index)
                    } label: {
                        Image(systemName: "minus.circle.fill")
                            .foregroundColor(.red)
                    }
                    .buttonStyle(.plain)
                }
            }
            
            Button("Add Environment Variable") {
                environmentVars.append(EditServerSheet.EnvironmentVariable(key: "", value: ""))
            }
            .buttonStyle(.borderless)
            .foregroundColor(.accentColor)
            
            if !environmentVars.isEmpty {
                Text("Environment variables will be passed to the server process")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

#Preview {
    let sampleServer = MCPServer(
        name: "filesystem",
        serverType: .npm,
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "--", "/Users/example"],
        env: ["PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"],
        enabled: true,
        scope: .user,
        description: "File system operations server"
    )
    
    EditServerSheet(server: sampleServer, serverService: MCPServerService())
}