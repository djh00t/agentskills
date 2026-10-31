/// A validated Keychain service name: `flux-age/<app>` or `flux-age/<app>/previous`.
///
/// The app part must match
/// `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`. Any other name is refused, so the helper
/// can never be pointed at an unrelated Keychain item.
public struct Service: Equatable, Hashable, CustomStringConvertible, Sendable {
    public static let prefix = "flux-age/"
    public static let previousSuffix = "/previous"

    public let app: String
    public let isPrevious: Bool

    public init?(_ name: String) {
        guard name.hasPrefix(Service.prefix) else { return nil }
        var rest = Substring(name.dropFirst(Service.prefix.count))
        var previous = false
        if rest.hasSuffix(Service.previousSuffix) {
            rest = rest.dropLast(Service.previousSuffix.count)
            previous = true
        }
        guard Service.isValidApp(rest) else { return nil }
        self.app = String(rest)
        self.isPrevious = previous
    }

    public static func isValidApp<S: StringProtocol>(_ app: S) -> Bool {
        let bytes = Array(app.utf8)
        guard (1...63).contains(bytes.count) else { return false }
        func alnum(_ b: UInt8) -> Bool { (b >= 0x61 && b <= 0x7a) || (b >= 0x30 && b <= 0x39) }
        guard alnum(bytes.first!), alnum(bytes.last!) else { return false }
        return bytes.allSatisfy { alnum($0) || $0 == 0x2d }
    }

    /// The `/previous` item that keeps the key a rotation replaced.
    public var previous: Service {
        Service(app: app, isPrevious: true)
    }

    public var name: String {
        Service.prefix + app + (isPrevious ? Service.previousSuffix : "")
    }

    public var description: String { name }

    private init(app: String, isPrevious: Bool) {
        self.app = app
        self.isPrevious = isPrevious
    }
}
