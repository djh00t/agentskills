#if canImport(Security)
import FluxAgeKeychainCore
import Foundation

/// stdin as the secret source. Reads at most `limit` bytes, so an accidental pipe of a
/// large file is refused without being held in memory; the read buffer is wiped.
struct StandardInput: SecretInput {
    var isTerminal: Bool { isatty(STDIN_FILENO) == 1 }

    func read(limit: Int) -> Data {
        var buffer = [UInt8](repeating: 0, count: limit)
        defer { buffer.withUnsafeMutableBytes { _ = memset($0.baseAddress!, 0, $0.count) } }
        var count = 0
        while count < limit {
            let n = buffer.withUnsafeMutableBytes {
                Foundation.read(STDIN_FILENO, $0.baseAddress! + count, limit - count)
            }
            if n > 0 {
                count += n
            } else if n == 0 || errno != EINTR {
                break
            }
        }
        return Data(buffer[0..<count])
    }
}

let runner = Runner(
    backend: DataProtectionBackend(),
    input: StandardInput(),
    stdout: { FileHandle.standardOutput.write($0) },
    stderr: { FileHandle.standardError.write(Data($0.utf8)) }
)
exit(runner.run(Array(CommandLine.arguments.dropFirst())))
#else
// The data protection keychain exists only on Apple platforms. Off macOS this target
// still builds, so `swift test` can run the FluxAgeKeychainCore tests in Linux CI.
import Foundation

FileHandle.standardError.write(Data("flux-age-keychain: macOS only (needs the Security framework)\n".utf8))
exit(2)
#endif
