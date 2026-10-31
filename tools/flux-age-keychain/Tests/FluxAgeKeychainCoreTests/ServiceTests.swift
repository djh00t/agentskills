import FluxAgeKeychainCore
import XCTest

final class ServiceTests: XCTestCase {
    func testAcceptsCurrentAndPrevious() {
        XCTAssertEqual(Service("flux-age/app-a")?.app, "app-a")
        XCTAssertEqual(Service("flux-age/app-a")?.isPrevious, false)
        XCTAssertEqual(Service("flux-age/app-b/previous")?.app, "app-b")
        XCTAssertEqual(Service("flux-age/app-b/previous")?.isPrevious, true)
        XCTAssertEqual(Service("flux-age/a")?.name, "flux-age/a")
        XCTAssertEqual(Service("flux-age/" + String(repeating: "a", count: 63))?.app.count, 63)
    }

    func testRejectsOtherNames() {
        let bad = [
            "", "flux-age/", "flux-age", "flux-age//previous", "flux-age/previous/previous/x",
            "flux-age/App-a", "flux-age/-app-a", "flux-age/app-a-", "flux-age/app_a",
            "flux-age/app-a/older", "flux-age/app-a/", "other/app-a", "flux-age/../x",
            "flux-age/" + String(repeating: "a", count: 64), "flux-age/app-a/previous/previous",
            " flux-age/app-a", "flux-age/app-a\n",
        ]
        for name in bad {
            XCTAssertNil(Service(name), "accepted \(name.debugDescription)")
        }
    }

    func testPreviousOfCurrent() {
        XCTAssertEqual(Service("flux-age/app-a")?.previous.name, "flux-age/app-a/previous")
    }
}
