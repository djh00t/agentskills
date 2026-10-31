/// A parsed command line.
public enum Command: Equatable, Sendable {
    case set(Service)
    case get(Service)
    case exists(Service)
    case list
    case replace(Service)
    case doctor
    case version
    case help
}

/// Why a command line was refused. Shown on stderr with exit code 2.
public struct UsageError: Error, Equatable, Sendable {
    public let message: String
    public init(_ message: String) { self.message = message }
}

public let usageText = """
    usage: flux-age-keychain set <service>        secret on stdin; refuses to overwrite
           flux-age-keychain get <service>        secret to stdout, for piping only
           flux-age-keychain exists <service>     exit 0 if present, 4 if not
           flux-age-keychain list                 service names only, never values
           flux-age-keychain replace <service> --previous <service>/previous
                                                  new secret on stdin; first copies the current
                                                  key to <service>/previous and verifies it
           flux-age-keychain doctor               entitlement and keychain checks
           flux-age-keychain --version

    <service> is flux-age/<app> or flux-age/<app>/previous. There is no delete command.
    """

public func parse(_ args: [String]) throws -> Command {
    guard let verb = args.first else { throw UsageError("missing command") }
    let rest = Array(args.dropFirst())

    func service(_ name: String) throws -> Service {
        guard let s = Service(name) else {
            throw UsageError("invalid service name: \(name) (want flux-age/<app> or flux-age/<app>/previous)")
        }
        return s
    }
    func one() throws -> Service {
        guard rest.count == 1 else { throw UsageError("\(verb) takes exactly one service name") }
        return try service(rest[0])
    }

    switch verb {
    case "set": return .set(try one())
    case "get": return .get(try one())
    case "exists": return .exists(try one())
    case "list":
        guard rest.isEmpty else { throw UsageError("list takes no arguments") }
        return .list
    case "replace":
        guard rest.count == 3, rest[1] == "--previous" else {
            throw UsageError("usage: replace <service> --previous <service>/previous")
        }
        let target = try service(rest[0])
        guard !target.isPrevious else {
            throw UsageError("replace only changes the current key, not a /previous item")
        }
        guard try service(rest[2]) == target.previous else {
            throw UsageError("--previous must be \(target.previous.name)")
        }
        return .replace(target)
    case "doctor":
        guard rest.isEmpty else { throw UsageError("doctor takes no arguments") }
        return .doctor
    case "--version", "version":
        guard rest.isEmpty else { throw UsageError("\(verb) takes no arguments") }
        return .version
    case "-h", "--help", "help":
        return .help
    default:
        throw UsageError("unknown command: \(verb)")
    }
}
