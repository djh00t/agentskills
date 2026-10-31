import FluxAgeKeychainCore
import XCTest

final class ParseTests: XCTestCase {
    let appA = Service("flux-age/app-a")!

    func testCommands() throws {
        XCTAssertEqual(try parse(["set", "flux-age/app-a"]), .set(appA))
        XCTAssertEqual(try parse(["set", "flux-age/app-a/previous"]), .set(appA.previous))
        XCTAssertEqual(try parse(["get", "flux-age/app-a"]), .get(appA))
        XCTAssertEqual(try parse(["exists", "flux-age/app-a"]), .exists(appA))
        XCTAssertEqual(try parse(["list"]), .list)
        XCTAssertEqual(try parse(["doctor"]), .doctor)
        XCTAssertEqual(try parse(["--version"]), .version)
        XCTAssertEqual(try parse(["--help"]), .help)
        XCTAssertEqual(
            try parse(["replace", "flux-age/app-a", "--previous", "flux-age/app-a/previous"]),
            .replace(appA))
    }

    func testRefusals() {
        let bad: [[String]] = [
            [], ["delete", "flux-age/app-a"], ["remove", "flux-age/app-a"],
            ["set"], ["set", "flux-age/app-a", "extra"], ["set", "nope"],
            ["get", "flux-age/app-a", "--secret", "x"], ["list", "x"], ["doctor", "x"],
            ["replace", "flux-age/app-a"],
            ["replace", "flux-age/app-a", "--previous", "flux-age/other/previous"],
            ["replace", "flux-age/app-a", "--previous", "flux-age/app-a"],
            ["replace", "flux-age/app-a/previous", "--previous", "flux-age/app-a/previous"],
            ["replace", "flux-age/app-a", "--prev", "flux-age/app-a/previous"],
        ]
        for args in bad {
            XCTAssertThrowsError(try parse(args), "accepted \(args)")
        }
    }
}
