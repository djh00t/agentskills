import FluxAgeKeychainCore
import XCTest

final class ServiceTests: XCTestCase {
    func testAcceptsCurrentAndPrevious() {
        XCTAssertEqual(Service("flux-age/foreman")?.app, "foreman")
        XCTAssertEqual(Service("flux-age/foreman")?.isPrevious, false)
        XCTAssertEqual(Service("flux-age/bruce-billing/previous")?.app, "bruce-billing")
        XCTAssertEqual(Service("flux-age/bruce-billing/previous")?.isPrevious, true)
        XCTAssertEqual(Service("flux-age/a")?.name, "flux-age/a")
        XCTAssertEqual(Service("flux-age/" + String(repeating: "a", count: 63))?.app.count, 63)
    }

    func testRejectsOtherNames() {
        let bad = [
            "", "flux-age/", "flux-age", "flux-age//previous", "flux-age/previous/previous/x",
            "flux-age/Foreman", "flux-age/-foreman", "flux-age/foreman-", "flux-age/fore_man",
            "flux-age/foreman/older", "flux-age/foreman/", "other/foreman", "flux-age/../x",
            "flux-age/" + String(repeating: "a", count: 64), "flux-age/foreman/previous/previous",
            " flux-age/foreman", "flux-age/foreman\n",
        ]
        for name in bad {
            XCTAssertNil(Service(name), "accepted \(name.debugDescription)")
        }
    }

    func testPreviousOfCurrent() {
        XCTAssertEqual(Service("flux-age/foreman")?.previous.name, "flux-age/foreman/previous")
    }
}
