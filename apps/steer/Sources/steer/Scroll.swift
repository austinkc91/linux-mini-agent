import ArgumentParser
import Foundation

struct Scroll: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Scroll in a direction by N lines."
    )

    @Argument(help: "Direction: up, down, left, right")
    var direction: String

    @Argument(help: "Lines to scroll (default: 3)")
    var lines: Int32 = 3

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        var dx: Int32 = 0, dy: Int32 = 0
        switch direction.lowercased() {
        case "up": dy = lines
        case "down": dy = -lines
        case "left": dx = lines
        case "right": dx = -lines
        default: throw ValidationError("Direction must be: up, down, left, right")
        }
        MouseControl.scroll(dx: dx, dy: dy)

        if json {
            print("{\"action\":\"scroll\",\"direction\":\"\(direction)\",\"lines\":\(lines),\"ok\":true}")
        } else {
            print("Scrolled \(direction) \(lines) lines")
        }
    }
}
