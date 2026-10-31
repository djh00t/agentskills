import Foundation

/// Errors a keychain backend reports. Messages never include secret bytes.
public enum KeychainError: Error, Equatable, Sendable {
    /// An item with this service already exists.
    case duplicate
    /// No item with this service exists.
    case notFound
    /// Any other Security framework status (for example -34018, a missing entitlement).
    case status(Int32)
}

/// What `doctor` reports about the running process and keychain.
public struct Diagnosis: Equatable, Sendable {
    public var teamID: String?
    public var accessGroup: String?
    public var problems: [String]

    public init(teamID: String?, accessGroup: String?, problems: [String]) {
        self.teamID = teamID
        self.accessGroup = accessGroup
        self.problems = problems
    }
}

/// Storage for flux-age items. There is deliberately no delete: in a synchronizable
/// keychain a delete removes the item from every device signed in to the iCloud account.
public protocol KeychainBackend {
    /// Add a new item. Throws `.duplicate` when one exists; never overwrites.
    func add(_ service: Service, secret: Data) throws
    /// Return the item's secret. Throws `.notFound` when it does not exist.
    func read(_ service: Service) throws -> Data
    /// Report whether the item exists without reading its secret.
    func contains(_ service: Service) throws -> Bool
    /// Change the secret of an existing item. Only `replace` calls this: on `/previous`
    /// to keep the outgoing key, then on the current item once that is verified.
    func update(_ service: Service, secret: Data) throws
    /// Service names of every item the backend can see, unfiltered.
    func serviceNames() throws -> [String]
    /// Entitlement and keychain checks for `doctor`. Read-only.
    func diagnose() -> Diagnosis
}

/// In-memory backend for tests and dry runs.
public final class MemoryBackend: KeychainBackend {
    public private(set) var items: [String: Data]
    public var diagnosis: Diagnosis
    /// Service names whose `add`/`update` store the wrong bytes (to test read-back).
    public var corruptWrites: Set<String> = []
    /// Service names whose `add`/`update` fail with a keychain error.
    public var failWrites: Set<String> = []
    /// Number of `update` calls per service name.
    public private(set) var updateCounts: [String: Int] = [:]

    public init(items: [String: Data] = [:],
                diagnosis: Diagnosis = Diagnosis(teamID: "TEST-TEAM",
                                                 accessGroup: "TEST-TEAM.test", problems: [])) {
        self.items = items
        self.diagnosis = diagnosis
    }

    public func add(_ service: Service, secret: Data) throws {
        guard items[service.name] == nil else { throw KeychainError.duplicate }
        try write(service, secret)
    }

    public func read(_ service: Service) throws -> Data {
        guard let value = items[service.name] else { throw KeychainError.notFound }
        return value
    }

    public func contains(_ service: Service) throws -> Bool {
        items[service.name] != nil
    }

    public func update(_ service: Service, secret: Data) throws {
        guard items[service.name] != nil else { throw KeychainError.notFound }
        updateCounts[service.name, default: 0] += 1
        try write(service, secret)
    }

    private func write(_ service: Service, _ secret: Data) throws {
        if failWrites.contains(service.name) { throw KeychainError.status(-25293) }
        items[service.name] = corruptWrites.contains(service.name) ? Data("corrupt".utf8) : secret
    }

    public func serviceNames() throws -> [String] {
        Array(items.keys)
    }

    public func diagnose() -> Diagnosis {
        diagnosis
    }
}
