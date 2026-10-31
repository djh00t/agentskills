import FluxAgeKeychainCore
import XCTest

/// Throwaway values only; nothing here is a real key.
private let oldKey = "AGE-SECRET-KEY-1TESTONLYOLD"
private let newKey = "AGE-SECRET-KEY-1TESTONLYNEW"

private final class Capture {
    var out = Data()
    var err = ""
}

private func invoke(_ args: [String], backend: KeychainBackend, stdin: String = "",
                 terminal: Bool = false) -> (code: Int32, out: String, err: String) {
    let capture = Capture()
    let runner = Runner(
        backend: backend,
        input: FixedInput(Data(stdin.utf8), isTerminal: terminal),
        stdout: { capture.out.append($0) },
        stderr: { capture.err += $0 })
    let code = runner.run(args)
    return (code, String(decoding: capture.out, as: UTF8.self), capture.err)
}

private func itemText(_ backend: MemoryBackend, _ name: String) -> String? {
    backend.items[name].map { String(decoding: $0, as: UTF8.self) }
}

final class RunnerTests: XCTestCase {
    func testSetStoresSecretWithoutTrailingNewlineAndPrintsNothing() {
        let backend = MemoryBackend()
        let r = invoke(["set", "flux-age/app-a"], backend: backend, stdin: oldKey + "\n")
        XCTAssertEqual(r.code, 0)
        XCTAssertEqual(itemText(backend, "flux-age/app-a"), oldKey)
        XCTAssertEqual(r.out, "")
        XCTAssertFalse(r.err.contains(oldKey))
    }

    func testSetRefusesToOverwrite() {
        let backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        let r = invoke(["set", "flux-age/app-a"], backend: backend, stdin: newKey)
        XCTAssertEqual(r.code, 3)
        XCTAssertEqual(itemText(backend, "flux-age/app-a"), oldKey)
        XCTAssertFalse(r.err.contains(newKey) || r.err.contains(oldKey))
    }

    func testSetRefusesBadInput() {
        for input in ["", "\n", "a\nb", "a\u{0}b", String(repeating: "a", count: maxSecretBytes + 1)] {
            let backend = MemoryBackend()
            let r = invoke(["set", "flux-age/app-a"], backend: backend, stdin: input)
            XCTAssertEqual(r.code, 2, "input \(input.prefix(8).debugDescription)")
            XCTAssertTrue(backend.items.isEmpty)
        }
    }

    func testSetRefusesTerminalStdin() {
        let backend = MemoryBackend()
        let r = invoke(["set", "flux-age/app-a"], backend: backend, stdin: oldKey, terminal: true)
        XCTAssertEqual(r.code, 2)
        XCTAssertTrue(backend.items.isEmpty)
    }

    func testGetPrintsSecretToStdoutOnly() {
        let backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        let r = invoke(["get", "flux-age/app-a"], backend: backend)
        XCTAssertEqual(r.code, 0)
        XCTAssertEqual(r.out, oldKey + "\n")
        XCTAssertEqual(r.err, "")
    }

    func testGetAndExistsMissing() {
        let backend = MemoryBackend()
        XCTAssertEqual(invoke(["get", "flux-age/app-a"], backend: backend).code, 4)
        XCTAssertEqual(invoke(["exists", "flux-age/app-a"], backend: backend).code, 4)
        XCTAssertTrue(backend.items.isEmpty)
    }

    func testExistsPresentPrintsNothing() {
        let backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        let r = invoke(["exists", "flux-age/app-a"], backend: backend)
        XCTAssertEqual(r.code, 0)
        XCTAssertEqual(r.out + r.err, "")
    }

    func testListShowsOnlyValidNamesNeverValues() {
        let backend = MemoryBackend(items: [
            "flux-age/app-a": Data(oldKey.utf8),
            "flux-age/app-a/previous": Data(newKey.utf8),
            "unrelated": Data("x".utf8),
        ])
        let r = invoke(["list"], backend: backend)
        XCTAssertEqual(r.code, 0)
        XCTAssertEqual(r.out, "flux-age/app-a\nflux-age/app-a/previous\n")
        XCTAssertFalse(r.out.contains("AGE-SECRET-KEY"))
    }

    private let replace = ["replace", "flux-age/app-a", "--previous", "flux-age/app-a/previous"]

    func testReplaceNeedsCurrentAndANewValue() {
        var backend = MemoryBackend()
        XCTAssertEqual(invoke(replace, backend: backend, stdin: newKey).code, 4)
        XCTAssertTrue(backend.items.isEmpty)

        backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        XCTAssertEqual(invoke(replace, backend: backend, stdin: oldKey).code, 5)
        XCTAssertEqual(backend.items, ["flux-age/app-a": Data(oldKey.utf8)])
    }

    func testReplaceKeepsOutgoingKeyInPreviousThenRotates() {
        let backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        let r = invoke(replace, backend: backend, stdin: newKey + "\n")
        XCTAssertEqual(r.code, 0)
        XCTAssertEqual(itemText(backend, "flux-age/app-a"), newKey)
        XCTAssertEqual(itemText(backend, "flux-age/app-a/previous"), oldKey)
        XCTAssertEqual(r.out, "")
        XCTAssertFalse(r.err.contains("AGE-SECRET-KEY"))
    }

    func testReplaceRotatesTwice() {
        let thirdKey = "AGE-SECRET-KEY-1TESTONLYTHIRD"
        let backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        XCTAssertEqual(invoke(replace, backend: backend, stdin: newKey).code, 0)
        XCTAssertEqual(invoke(replace, backend: backend, stdin: thirdKey).code, 0)
        XCTAssertEqual(itemText(backend, "flux-age/app-a"), thirdKey)
        XCTAssertEqual(itemText(backend, "flux-age/app-a/previous"), newKey)
        XCTAssertEqual(backend.updateCounts["flux-age/app-a"], 2)
        XCTAssertEqual(backend.updateCounts["flux-age/app-a/previous"], 1)
    }

    func testFailedPreviousWriteLeavesCurrentUnchanged() {
        for existingPrevious in [false, true] {
            var items = ["flux-age/app-a": Data(oldKey.utf8)]
            if existingPrevious { items["flux-age/app-a/previous"] = Data("AGE-SECRET-KEY-1OLDER".utf8) }
            let backend = MemoryBackend(items: items)
            backend.failWrites = ["flux-age/app-a/previous"]
            let r = invoke(replace, backend: backend, stdin: newKey)
            XCTAssertEqual(r.code, 6)
            XCTAssertEqual(itemText(backend, "flux-age/app-a"), oldKey)
            XCTAssertNil(backend.updateCounts["flux-age/app-a"])
            XCTAssertTrue(r.err.contains("flux-age/app-a unchanged"))
            XCTAssertFalse(r.err.contains("AGE-SECRET-KEY"))
        }
    }

    func testBadPreviousReadBackLeavesCurrentUnchanged() {
        let backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        backend.corruptWrites = ["flux-age/app-a/previous"]
        let r = invoke(replace, backend: backend, stdin: newKey)
        XCTAssertEqual(r.code, 6)
        XCTAssertEqual(itemText(backend, "flux-age/app-a"), oldKey)
        XCTAssertNil(backend.updateCounts["flux-age/app-a"])
        XCTAssertTrue(r.err.contains("did not read back"))
    }

    func testReplaceReportsFailedCurrentReadBack() {
        let backend = MemoryBackend(items: ["flux-age/app-a": Data(oldKey.utf8)])
        backend.corruptWrites = ["flux-age/app-a"]
        let r = invoke(replace, backend: backend, stdin: newKey)
        XCTAssertEqual(r.code, 6)
        XCTAssertEqual(itemText(backend, "flux-age/app-a/previous"), oldKey)
        XCTAssertFalse(r.err.contains("AGE-SECRET-KEY") || r.err.contains("corrupt"))
    }

    func testStdinIsReadOnlyUpToTheCap() {
        final class Counting: SecretInput {
            var limits: [Int] = []
            var isTerminal: Bool { false }
            func read(limit: Int) -> Data {
                limits.append(limit)
                return Data(String(repeating: "a", count: limit).utf8)
            }
        }
        let input = Counting()
        let backend = MemoryBackend()
        let runner = Runner(backend: backend, input: input, stdout: { _ in }, stderr: { _ in })
        XCTAssertEqual(runner.run(["set", "flux-age/app-a"]), 2)
        XCTAssertEqual(input.limits, [maxInputBytes + 1])
        XCTAssertTrue(backend.items.isEmpty)
    }

    func testLargestSecretWithCRLFIsAccepted() {
        let big = String(repeating: "a", count: maxSecretBytes)
        let backend = MemoryBackend()
        XCTAssertEqual(invoke(["set", "flux-age/app-a"], backend: backend, stdin: big + "\r\n").code, 0)
        XCTAssertEqual(itemText(backend, "flux-age/app-a"), big)
    }

    func testZeroizeOverwritesEveryByte() {
        var data = Data("AGE-SECRET-KEY-1TESTONLY".utf8)
        let count = data.count
        XCTAssertTrue(data.contains { $0 != 0 })
        zeroize(&data)
        XCTAssertEqual(data.count, count)
        XCTAssertTrue(data.allSatisfy { $0 == 0 })
    }

    // wipe() is zeroize() followed by removeAll(). Its zeroing can't be observed after the
    // buffer is released, so testZeroizeOverwritesEveryByte covers that part.

    func testLoneTrailingCRIsRefused() {
        let backend = MemoryBackend()
        XCTAssertEqual(invoke(["set", "flux-age/app-a"], backend: backend, stdin: "abc\r").code, 2)
        XCTAssertTrue(backend.items.isEmpty)
    }

    func testReadErrorIsRefused() {
        struct Failing: SecretInput {
            struct Broken: Error {}
            var isTerminal: Bool { false }
            func read(limit: Int) throws -> Data { throw Broken() }
        }
        let backend = MemoryBackend()
        let runner = Runner(backend: backend, input: Failing(), stdout: { _ in }, stderr: { _ in })
        XCTAssertEqual(runner.run(["set", "flux-age/app-a"]), 2)
        XCTAssertTrue(backend.items.isEmpty)
    }

    func testInputPastCRLFIsRefusedNotTruncated() {
        let big = String(repeating: "a", count: maxSecretBytes)
        let backend = MemoryBackend()
        XCTAssertEqual(invoke(["set", "flux-age/app-a"], backend: backend, stdin: big + "\r\nx").code, 2)
        XCTAssertTrue(backend.items.isEmpty)
    }

    func testOneByteOverLimitIsRefused() {
        let backend = MemoryBackend()
        let over = String(repeating: "a", count: maxSecretBytes + 1)
        XCTAssertEqual(invoke(["set", "flux-age/app-a"], backend: backend, stdin: over).code, 2)
        XCTAssertTrue(backend.items.isEmpty)
    }

    func testLargestSecretWithLFIsAccepted() {
        let big = String(repeating: "a", count: maxSecretBytes)
        let backend = MemoryBackend()
        XCTAssertEqual(invoke(["set", "flux-age/app-a"], backend: backend, stdin: big + "\n").code, 0)
        XCTAssertEqual(itemText(backend, "flux-age/app-a"), big)
    }

    func testDoctor() {
        let good = invoke(["doctor"], backend: MemoryBackend())
        XCTAssertEqual(good.code, 0)
        XCTAssertTrue(good.out.contains("status: ok"))

        let unsigned = MemoryBackend(diagnosis: Diagnosis(
            teamID: nil, accessGroup: nil, problems: ["no keychain-access-groups entitlement"]))
        let bad = invoke(["doctor"], backend: unsigned)
        XCTAssertEqual(bad.code, 6)
        XCTAssertTrue(bad.out.contains("status: not usable"))
    }

    func testMissingEntitlementIsExplained() {
        final class Unsigned: KeychainBackend {
            func add(_ service: Service, secret: Data) throws { throw KeychainError.status(-34018) }
            func read(_ service: Service) throws -> Data { throw KeychainError.status(-34018) }
            func contains(_ service: Service) throws -> Bool { throw KeychainError.status(-34018) }
            func update(_ service: Service, secret: Data) throws { throw KeychainError.status(-34018) }
            func serviceNames() throws -> [String] { throw KeychainError.status(-34018) }
            func diagnose() -> Diagnosis { Diagnosis(teamID: nil, accessGroup: nil, problems: ["unsigned"]) }
        }
        let r = invoke(["exists", "flux-age/app-a"], backend: Unsigned())
        XCTAssertEqual(r.code, 6)
        XCTAssertTrue(r.err.contains("-34018"))
    }

    func testUsageErrorsExit2() {
        XCTAssertEqual(invoke(["delete", "flux-age/app-a"], backend: MemoryBackend()).code, 2)
        XCTAssertEqual(invoke([], backend: MemoryBackend()).code, 2)
    }
}
