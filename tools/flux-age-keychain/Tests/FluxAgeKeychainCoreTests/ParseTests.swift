import FluxAgeKeychainCore
import XCTest

final class ParseTests: XCTestCase {
    let foreman = Service("flux-age/foreman")!

    func testCommands() throws {
        XCTAssertEqual(try parse(["set", "flux-age/foreman"]), .set(foreman))
        XCTAssertEqual(try parse(["set", "flux-age/foreman/previous"]), .set(foreman.previous))
        XCTAssertEqual(try parse(["get", "flux-age/foreman"]), .get(foreman))
        XCTAssertEqual(try parse(["exists", "flux-age/foreman"]), .exists(foreman))
        XCTAssertEqual(try parse(["list"]), .list)
        XCTAssertEqual(try parse(["doctor"]), .doctor)
        XCTAssertEqual(try parse(["--version"]), .version)
        XCTAssertEqual(try parse(["--help"]), .help)
        XCTAssertEqual(
            try parse(["replace", "flux-age/foreman", "--previous", "flux-age/foreman/previous"]),
            .replace(foreman))
    }

    func testRefusals() {
        let bad: [[String]] = [
            [], ["delete", "flux-age/foreman"], ["remove", "flux-age/foreman"],
            ["set"], ["set", "flux-age/foreman", "extra"], ["set", "nope"],
            ["get", "flux-age/foreman", "--secret", "x"], ["list", "x"], ["doctor", "x"],
            ["replace", "flux-age/foreman"],
            ["replace", "flux-age/foreman", "--previous", "flux-age/other/previous"],
            ["replace", "flux-age/foreman", "--previous", "flux-age/foreman"],
            ["replace", "flux-age/foreman/previous", "--previous", "flux-age/foreman/previous"],
            ["replace", "flux-age/foreman", "--prev", "flux-age/foreman/previous"],
        ]
        for args in bad {
            XCTAssertThrowsError(try parse(args), "accepted \(args)")
        }
    }
}
