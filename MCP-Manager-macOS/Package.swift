// swift-tools-version: 5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "MCP-Manager-macOS",
    platforms: [
        .macOS(.v14) // Sonoma and later for latest SwiftUI features
    ],
    products: [
        .executable(
            name: "MCP-Manager-macOS",
            targets: ["MCP-Manager-macOS"]
        ),
    ],
    dependencies: [
        .package(url: "https://github.com/stephencelis/SQLite.swift.git", from: "0.15.3")
    ],
    targets: [
        .executableTarget(
            name: "MCP-Manager-macOS",
            dependencies: [
                .product(name: "SQLite", package: "SQLite.swift")
            ],
            path: "Sources"
        ),
        .testTarget(
            name: "MCP-Manager-macOSTests",
            dependencies: ["MCP-Manager-macOS"],
            path: "Tests"
        ),
    ]
)