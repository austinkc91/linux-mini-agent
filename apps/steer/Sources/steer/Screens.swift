import ArgumentParser
import Foundation

struct ScreenInfo: Codable {
    let index: Int
    let name: String
    let width: Int
    let height: Int
    let originX: Int
    let originY: Int
    let isMain: Bool
    let scaleFactor: Double
}

struct Screens: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "List connected displays with index, resolution, and position."
    )

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        let screens = ScreenCapture.listScreens()

        if json {
            let enc = JSONEncoder()
            enc.outputFormatting = .prettyPrinted
            if let d = try? enc.encode(screens) {
                print(String(data: d, encoding: .utf8) ?? "[]")
            }
        } else {
            for s in screens {
                let main = s.isMain ? " (main)" : ""
                print("  \(s.index)  \(s.name.padding(toLength: 30, withPad: " ", startingAt: 0)) \(s.width)x\(s.height)  at (\(s.originX),\(s.originY))  scale:\(s.scaleFactor)\(main)")
            }
        }
    }
}
