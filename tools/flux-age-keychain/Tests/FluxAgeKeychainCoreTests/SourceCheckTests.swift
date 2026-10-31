import Foundation
import XCTest

/// A keychain delete syncs to every device, so the helper must never call the delete API.
/// The needle is built by concatenation so this file does not match itself.
final class SourceCheckTests: XCTestCase {
    func testSourcesNeverCallKeychainDelete() throws {
        let root = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let sources = root.appendingPathComponent("Sources")
        let needle = "SecItem" + "Delete"
        let files = FileManager.default.enumerator(at: sources, includingPropertiesForKeys: nil)?
            .compactMap { $0 as? URL }
            .filter { $0.pathExtension == "swift" } ?? []
        XCTAssertFalse(files.isEmpty, "no Swift sources found under \(sources.path)")
        for file in files {
            let text = try String(contentsOf: file, encoding: .utf8)
            XCTAssertFalse(text.contains(needle), "\(file.lastPathComponent) calls \(needle)")
        }
    }
}
