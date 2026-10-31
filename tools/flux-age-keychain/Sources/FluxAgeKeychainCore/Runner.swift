import Foundation

/// Exit codes, also listed in README.md.
public enum Exit: Int32, Sendable {
    case ok = 0
    case usage = 2
    case exists = 3
    case notFound = 4
    case guardFailed = 5
    case keychain = 6
}

/// Where a secret comes from. The real one is the process's stdin.
public protocol SecretInput {
    /// True when stdin is a terminal; secrets are refused then, so they are never echoed.
    var isTerminal: Bool { get }
    /// Read until EOF or `limit` bytes, whichever comes first. Throws on an I/O error,
    /// so a partial secret is never stored.
    func read(limit: Int) throws -> Data
}

public struct FixedInput: SecretInput {
    public let data: Data
    public let isTerminal: Bool
    public init(_ data: Data, isTerminal: Bool = false) {
        self.data = data
        self.isTerminal = isTerminal
    }
    public func read(limit: Int) -> Data { data.prefix(limit) }
}

public let version = "0.1.0"
/// Largest accepted secret. An age identity line is 74 bytes; this leaves room but stops
/// a mistaken pipe of a whole file into the keychain.
public let maxSecretBytes = 4096
/// Largest accepted stdin input: the largest secret plus a trailing CRLF. One more byte
/// than this is read, so longer input is refused instead of silently truncated.
public let maxInputBytes = maxSecretBytes + 2

/// Overwrite a buffer holding secret bytes before it is released (best effort: copies
/// made by the Security framework or Foundation are out of reach).
public func wipe(_ data: inout Data) {
    zeroize(&data)
    data.removeAll()
}

/// Overwrite every byte of a buffer with zero, keeping its length.
public func zeroize(_ data: inout Data) {
    data.resetBytes(in: 0..<data.count)
}

/// Runs one command. Secrets only ever reach `stdout`, and only for `get`.
public struct Runner {
    let backend: KeychainBackend
    let input: SecretInput
    let stdout: (Data) -> Void
    let stderr: (String) -> Void

    public init(backend: KeychainBackend, input: SecretInput,
                stdout: @escaping (Data) -> Void, stderr: @escaping (String) -> Void) {
        self.backend = backend
        self.input = input
        self.stdout = stdout
        self.stderr = stderr
    }

    public func run(_ args: [String]) -> Int32 {
        let command: Command
        do {
            command = try parse(args)
        } catch let error as UsageError {
            stderr("flux-age-keychain: \(error.message)\n\(usageText)\n")
            return Exit.usage.rawValue
        } catch {
            return Exit.usage.rawValue
        }
        do {
            return try execute(command).rawValue
        } catch let failure as Failure {
            stderr("flux-age-keychain: \(failure.message)\n")
            return failure.exit.rawValue
        } catch {
            stderr("flux-age-keychain: \(Runner.describe(error))\n")
            return Exit.keychain.rawValue
        }
    }

    struct Failure: Error {
        let exit: Exit
        let message: String
    }

    static func describe(_ error: Error) -> String {
        switch error as? KeychainError {
        case .duplicate?: return "item already exists"
        case .notFound?: return "item not found"
        case .status(let code)?:
            if code == -34018 {
                return "keychain error -34018 (missing entitlement: is this the signed FluxAgeKeychain.app build?)"
            }
            return "keychain error \(code)"
        case nil: return "unexpected error"
        }
    }

    func execute(_ command: Command) throws -> Exit {
        switch command {
        case .help:
            stderr(usageText + "\n")
            return .ok
        case .version:
            stdout(Data("flux-age-keychain \(version)\n".utf8))
            return .ok
        case .exists(let service):
            return try keychain { try backend.contains(service) } ? .ok : .notFound
        case .get(let service):
            var line = try fetch(service)
            defer { wipe(&line) }
            line.append(0x0a)
            stdout(line)
            return .ok
        case .list:
            let names = try keychain { try backend.serviceNames() }
                .filter { Service($0) != nil }
            let unique = Array(Set(names)).sorted()
            stdout(Data(unique.map { $0 + "\n" }.joined().utf8))
            return .ok
        case .set(let service):
            if try keychain({ try backend.contains(service) }) {
                throw Failure(exit: .exists, message: "\(service) already exists; set never overwrites")
            }
            var secret = try readSecret()
            defer { wipe(&secret) }
            do {
                try backend.add(service, secret: secret)
            } catch KeychainError.duplicate {
                throw Failure(exit: .exists, message: "\(service) already exists; set never overwrites")
            } catch {
                throw Failure(exit: .keychain, message: "could not add \(service): \(Runner.describe(error))")
            }
            try verify(service, equals: secret)
            return .ok
        case .replace(let service):
            // Rotation: keep the outgoing key in /previous (the only item ever
            // overwritten, and only here), verify it byte for byte, then change the
            // current key. Any failure before the last step leaves the current key as it was.
            var secret = try readSecret()
            defer { wipe(&secret) }
            var current = try fetch(service)
            defer { wipe(&current) }
            guard secret != current else {
                throw Failure(exit: .guardFailed, message: "new secret equals the current key of \(service); nothing changed")
            }
            do {
                do {
                    try backend.add(service.previous, secret: current)
                } catch KeychainError.duplicate {
                    try backend.update(service.previous, secret: current)
                }
            } catch {
                throw Failure(exit: .keychain,
                              message: "could not write \(service.previous): \(Runner.describe(error)); \(service) unchanged")
            }
            do {
                try verify(service.previous, equals: current)
            } catch let failure as Failure {
                throw Failure(exit: failure.exit, message: failure.message + "; \(service) unchanged")
            }
            do {
                try backend.update(service, secret: secret)
            } catch {
                throw Failure(exit: .keychain, message: "could not update \(service): \(Runner.describe(error))")
            }
            try verify(service, equals: secret)
            return .ok
        case .doctor:
            let d = backend.diagnose()
            var report = "flux-age-keychain \(version)\n"
            report += "team id: \(d.teamID ?? "(none)")\n"
            report += "access group: \(d.accessGroup ?? "(none)")\n"
            for problem in d.problems { report += "problem: \(problem)\n" }
            report += d.problems.isEmpty ? "status: ok\n" : "status: not usable\n"
            stdout(Data(report.utf8))
            return d.problems.isEmpty ? .ok : .keychain
        }
    }

    /// Run a backend call, mapping any error to exit 6 with a message that has no secret.
    func keychain<T>(_ body: () throws -> T) throws -> T {
        do {
            return try body()
        } catch {
            throw Failure(exit: .keychain, message: Runner.describe(error))
        }
    }

    func fetch(_ service: Service) throws -> Data {
        do {
            return try backend.read(service)
        } catch KeychainError.notFound {
            throw Failure(exit: .notFound, message: "\(service) not found")
        } catch {
            throw Failure(exit: .keychain, message: "could not read \(service): \(Runner.describe(error))")
        }
    }

    func verify(_ service: Service, equals secret: Data) throws {
        var stored = try fetch(service)
        defer { wipe(&stored) }
        guard stored == secret else {
            throw Failure(exit: .keychain, message: "\(service) did not read back as written")
        }
    }

    /// Read one secret from stdin. A single trailing LF or CRLF (as `printf '%s\n'` adds)
    /// is dropped; a lone CR is not, so it is refused as multi-line; empty, oversized, multi-line or NUL-containing input is refused. At most
    /// `maxInputBytes + 1` bytes are read: getting more than `maxInputBytes` means the
    /// input is too long and it is refused before any newline is stripped, so a secret is
    /// never silently truncated. A refused buffer is wiped.
    func readSecret() throws -> Data {
        guard !input.isTerminal else {
            throw Failure(exit: .usage, message: "refusing to read a secret from a terminal; pipe it on stdin")
        }
        var data: Data
        do {
            data = try input.read(limit: maxInputBytes + 1)
        } catch {
            throw Failure(exit: .usage, message: "could not read the secret from stdin")
        }
        if data.count > maxInputBytes {
            wipe(&data)
            throw Failure(exit: .usage, message: "secret on stdin is larger than \(maxSecretBytes) bytes")
        }
        if data.last == 0x0a {
            data.removeLast()
            // Drop a CR only as part of a trailing CRLF; a lone CR is refused below.
            if data.last == 0x0d { data.removeLast() }
        }
        let problem: String?
        if data.isEmpty {
            problem = "no secret on stdin"
        } else if data.count > maxSecretBytes {
            problem = "secret on stdin is larger than \(maxSecretBytes) bytes"
        } else if data.contains(0x0a) || data.contains(0x0d) || data.contains(0x00) {
            problem = "secret on stdin must be a single line"
        } else {
            problem = nil
        }
        if let problem {
            wipe(&data)
            throw Failure(exit: .usage, message: problem)
        }
        return data
    }
}
