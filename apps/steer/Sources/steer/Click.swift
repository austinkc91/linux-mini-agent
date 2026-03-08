import ArgumentParser
import CoreGraphics
import Foundation

struct Click: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Click an element by ID (B1), label, or x,y coordinates."
    )

    @Option(name: .long, help: "Element ID (B1) or label text")
    var on: String?

    @Option(name: .shortAndLong, help: "X coordinate")
    var x: Double?

    @Option(name: .shortAndLong, help: "Y coordinate")
    var y: Double?

    @Option(name: .long, help: "Snapshot ID to resolve element from")
    var snapshot: String?

    @Option(name: .long, help: "Screen index — translates local screenshot coords to global")
    var screen: Int?

    @Flag(name: .long, help: "Double-click")
    var double = false

    @Flag(name: .long, help: "Right-click")
    var right = false

    @Flag(name: .long, help: "Middle-click")
    var middle = false

    @Option(name: .long, help: "Modifier keys: cmd, shift, alt, ctrl (combine with +)")
    var modifier: String?

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func validate() throws {
        if right && middle { throw ValidationError("Cannot combine --right and --middle") }
    }

    func run() throws {
        let px: Double
        let py: Double
        var label = ""

        if let on = on {
            let el = try ElementStore.resolve(on, snap: snapshot)
            px = Double(el.centerX)
            py = Double(el.centerY)
            label = "\(el.id) \"\(el.label)\""
        } else if let x = x, let y = y {
            if let screenIdx = screen, let info = ScreenCapture.screenInfo(index: screenIdx) {
                px = (x / info.scaleFactor) + Double(info.originX)
                py = (y / info.scaleFactor) + Double(info.originY)
            } else {
                px = x; py = y
            }
        } else {
            throw ValidationError("Provide --on <element> or --x/--y coordinates")
        }

        let button: CGMouseButton = right ? .right : (middle ? .center : .left)
        let count = double ? 2 : 1
        let flags = modifier.map { Keyboard.parseModifiers($0) } ?? []
        MouseControl.click(x: px, y: py, button: button, count: count, flags: flags)

        if json {
            print("{\"action\":\"click\",\"x\":\(Int(px)),\"y\":\(Int(py)),\"label\":\"\(label)\",\"ok\":true}")
        } else {
            let mod = modifier != nil ? "[\(modifier!)] " : ""
            let verb = double ? "Double-clicked" : (right ? "Right-clicked" : (middle ? "Middle-clicked" : "Clicked"))
            let target = label.isEmpty ? "(\(Int(px)), \(Int(py)))" : "\(label) at (\(Int(px)), \(Int(py)))"
            print("\(mod)\(verb) \(target)")
        }
    }
}
