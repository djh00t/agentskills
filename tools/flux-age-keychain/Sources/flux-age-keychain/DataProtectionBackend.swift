#if canImport(Security)
import FluxAgeKeychainCore
import Foundation
import Security

/// The real backend: synchronizable generic-password items in the data protection
/// keychain, so they sync through iCloud Keychain. See TN3137.
///
/// The access group is read from this process's own `keychain-access-groups`
/// entitlement, which package.sh writes from FLUX_AGE_TEAM_ID at signing time, so no
/// team-specific value is compiled in. An unsigned build has no such entitlement and
/// every call fails before touching the keychain.
///
/// There is no delete here; `make check` and SourceCheckTests fail if the sources ever
/// call the Security framework delete API.
struct DataProtectionBackend: KeychainBackend {
    static let entitlementGroups = "keychain-access-groups"
    static let entitlementTeam = "com.apple.developer.team-identifier"

    let accessGroup: String?
    let teamID: String?

    init() {
        let task = SecTaskCreateFromSelf(nil)
        func entitlement(_ key: String) -> CFTypeRef? {
            guard let task else { return nil }
            return SecTaskCopyValueForEntitlement(task, key as CFString, nil)
        }
        accessGroup = (entitlement(Self.entitlementGroups) as? [String])?.first
        teamID = entitlement(Self.entitlementTeam) as? String
    }

    private func base() throws -> [String: Any] {
        guard let accessGroup else { throw KeychainError.status(errSecMissingEntitlement) }
        return [
            kSecClass as String: kSecClassGenericPassword,
            kSecUseDataProtectionKeychain as String: true,
            kSecAttrSynchronizable as String: true,
            kSecAttrAccessGroup as String: accessGroup,
        ]
    }

    private func query(_ service: Service) throws -> [String: Any] {
        var q = try base()
        q[kSecAttrService as String] = service.name
        return q
    }

    func add(_ service: Service, secret: Data) throws {
        var attrs = try query(service)
        attrs[kSecAttrAccount as String] = service.app
        attrs[kSecAttrLabel as String] = service.name
        // Not a ...ThisDeviceOnly class: those never sync.
        attrs[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlocked
        attrs[kSecValueData as String] = secret
        let status = SecItemAdd(attrs as CFDictionary, nil)
        switch status {
        case errSecSuccess: return
        case errSecDuplicateItem: throw KeychainError.duplicate
        default: throw KeychainError.status(status)
        }
    }

    func read(_ service: Service) throws -> Data {
        var q = try query(service)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        switch status {
        case errSecSuccess:
            guard let data = result as? Data else { throw KeychainError.status(errSecInternalError) }
            return data
        case errSecItemNotFound: throw KeychainError.notFound
        default: throw KeychainError.status(status)
        }
    }

    func contains(_ service: Service) throws -> Bool {
        var q = try query(service)
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        let status = SecItemCopyMatching(q as CFDictionary, nil)
        switch status {
        case errSecSuccess: return true
        case errSecItemNotFound: return false
        default: throw KeychainError.status(status)
        }
    }

    func update(_ service: Service, secret: Data) throws {
        let status = SecItemUpdate(try query(service) as CFDictionary,
                                   [kSecValueData as String: secret] as CFDictionary)
        switch status {
        case errSecSuccess: return
        case errSecItemNotFound: throw KeychainError.notFound
        default: throw KeychainError.status(status)
        }
    }

    func serviceNames() throws -> [String] {
        var q = try base()
        q[kSecReturnAttributes as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitAll
        var result: CFTypeRef?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        switch status {
        case errSecSuccess:
            let items = result as? [[String: Any]] ?? []
            return items.compactMap { $0[kSecAttrService as String] as? String }
        case errSecItemNotFound: return []
        default: throw KeychainError.status(status)
        }
    }

    func diagnose() -> Diagnosis {
        var problems: [String] = []
        if accessGroup == nil {
            problems.append("no keychain-access-groups entitlement; run the signed FluxAgeKeychain.app build")
        }
        if teamID == nil {
            problems.append("no team identifier entitlement")
        }
        if let accessGroup, let teamID, !accessGroup.hasPrefix(teamID + ".") {
            problems.append("access group does not start with the team id")
        }
        if accessGroup != nil {
            // Read-only probe: list attributes, never data, never a write.
            do {
                _ = try serviceNames()
            } catch {
                if case KeychainError.status(let code) = error {
                    problems.append("data protection keychain query failed with status \(code)")
                } else {
                    problems.append("data protection keychain query failed")
                }
            }
        }
        return Diagnosis(teamID: teamID, accessGroup: accessGroup, problems: problems)
    }
}
#endif
