//
//  AddServerSheet.swift
//  MCP-Manager-macOS
//
//  Modal sheet for adding new MCP servers with validation
//

import SwiftUI

struct AddServerSheet: View {
    @ObservedObject var serverService: MCPServerService
    @Environment(\.dismiss) private var dismiss
    
    @State private var serverName = ""
    @State private var selectedType: ServerType = .npm
    @State private var selectedScope: ServerScope = .user
    @State private var description = ""
    @State private var command = ""
    @State private var arguments = ""
    @State private var package = ""
    @State private var environmentVars: [EnvironmentVariable] = []
    
    @State private var validationError: String?
    @State private var isCreating = false
    
    struct EnvironmentVariable: Identifiable {
        let id = UUID()
        var key: String = ""
        var value: String = ""
    }
    
    var body: some View {
        NavigationView {
            Form {
                Section("Basic Information") {
                    TextField("Server Name", text: $serverName)
                        .textFieldStyle(.roundedBorder)
                        .onChange(of: serverName) { _, _ in
                            validationError = nil
                        }
                    
                    Picker("Server Type", selection: $selectedType) {
                        ForEach(ServerType.allCases, id: \.self) { type in
                            Label(type.displayName, systemImage: iconForServerType(type))
                                .tag(type)
                        }
                    }
                    .onChange(of: selectedType) { _, newType in
                        updateCommandForType(newType)
                    }
                    
                    Picker("Scope", selection: $selectedScope) {
                        ForEach(ServerScope.allCases, id: \.self) { scope in
                            Text(scope.displayName).tag(scope)
                        }
                    }
                    
                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(2...4)
                }
                
                Section("Configuration") {
                    // Type-specific configuration
                    switch selectedType {
                    case .npm:
                        NPMConfigurationView(package: $package, arguments: $arguments)
                    case .docker, .dockerDesktop:
                        DockerConfigurationView(package: $package, arguments: $arguments)
                    case .custom:
                        CustomConfigurationView(command: $command, arguments: $arguments)
                    }
                }
                
                Section("Environment Variables") {
                    EnvironmentVariablesView(environmentVars: $environmentVars)
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
            .navigationTitle("Add MCP Server")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add Server") {
                        Task {
                            await createServer()
                        }
                    }
                    .disabled(isCreating || !isFormValid)
                }
            }
        }
        .frame(width: 500, height: 600)
        .onAppear {
            updateCommandForType(selectedType)
        }
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
    
    private func updateCommandForType(_ type: ServerType) {
        switch type {
        case .npm:
            command = "npx"
            if package.isEmpty {
                package = "@modelcontextprotocol/server-"
            }
        case .docker, .dockerDesktop:
            command = "docker"
            if package.isEmpty {
                package = "mcp-server-"
            }
        case .custom:
            command = ""
            package = ""
        }
    }
    
    private func createServer() async {
        isCreating = true
        validationError = nil
        
        // Validate server name
        if let nameError = serverService.validateServerName(serverName) {
            validationError = nameError
            isCreating = false
            return
        }
        
        // Create server based on type
        let server: MCPServer
        
        switch selectedType {
        case .npm:
            server = createNPMServer()
        case .docker, .dockerDesktop:
            server = createDockerServer()
        case .custom:
            server = createCustomServer()
        }
        
        await serverService.addServer(server)
        
        isCreating = false
        dismiss()
    }
    
    private func createNPMServer() -> MCPServer {
        let args = ["-y", package]
        let additionalArgs = parseArguments(arguments)
        let finalArgs = additionalArgs.isEmpty ? args : args + ["--"] + additionalArgs
        
        return MCPServer(
            name: serverName,
            serverType: .npm,
            command: "npx",
            args: finalArgs,
            env: environmentVarsDict,
            enabled: false,
            scope: selectedScope,
            description: description.isEmpty ? nil : description,
            installId: package,
            package: package,
            createdAt: Date(),
            updatedAt: Date()
        )
    }
    
    private func createDockerServer() -> MCPServer {
        let baseArgs = ["run", "--rm", "-it", package]
        let additionalArgs = parseArguments(arguments)
        let finalArgs = additionalArgs.isEmpty ? baseArgs : baseArgs + additionalArgs
        
        return MCPServer(
            name: serverName,
            serverType: selectedType,
            command: "docker",
            args: finalArgs,
            env: environmentVarsDict,
            enabled: false,
            scope: selectedScope,
            description: description.isEmpty ? nil : description,
            installId: "docker-\(package)",
            package: package,
            createdAt: Date(),
            updatedAt: Date()
        )
    }
    
    private func createCustomServer() -> MCPServer {
        return MCPServer(
            name: serverName,
            serverType: .custom,
            command: command,
            args: parseArguments(arguments),
            env: environmentVarsDict,
            enabled: false,
            scope: selectedScope,
            description: description.isEmpty ? nil : description,
            createdAt: Date(),
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

// MARK: - NPM Configuration View

struct NPMConfigurationView: View {
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

// MARK: - Docker Configuration View

struct DockerConfigurationView: View {
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

// MARK: - Custom Configuration View

struct CustomConfigurationView: View {
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

// MARK: - Environment Variables View

struct EnvironmentVariablesView: View {
    @Binding var environmentVars: [AddServerSheet.EnvironmentVariable]
    
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
                environmentVars.append(AddServerSheet.EnvironmentVariable())
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
    AddServerSheet(serverService: MCPServerService())
}