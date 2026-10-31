// swift-tools-version:5.9
// flux-age-keychain: syncing Keychain store for per-app SOPS age keys.
import PackageDescription

let package = Package(
    name: "flux-age-keychain",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "flux-age-keychain", targets: ["flux-age-keychain"]),
    ],
    targets: [
        // Pure logic: names, argument parsing, command rules. No Security calls, so it
        // is fully testable against an in-memory backend.
        .target(name: "FluxAgeKeychainCore"),
        // The real data protection keychain backend and main entry point.
        .executableTarget(name: "flux-age-keychain", dependencies: ["FluxAgeKeychainCore"]),
        .testTarget(name: "FluxAgeKeychainCoreTests", dependencies: ["FluxAgeKeychainCore"]),
    ]
)
