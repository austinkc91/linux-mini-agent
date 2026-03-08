import ArgumentParser
import CoreGraphics
import Foundation

struct Drag: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Drag from one element/point to another."
    )

    @Option(name: .long, help: "Source element ID or label")
    var from: String?

    @Option(name: .customLong("from-x"), help: "Source X coordinate")
    var fromX: Double?

    @Option(name: .customLong("from-y"), help: "Source Y coordinate")
    var fromY: Double?

    @Option(name: .long, help: "Destination element ID or label")
    var to: String?

    @Option(name: .customLong("to-x"), help: "Destination X coordinate")
    var toX: Double?

    @Option(name: .customLong("to-y"), help: "Destination Y coordinate")
    var toY: Double?

    @Option(name: .long, help: "Snapshot ID")
    var snapshot: String?

    @Option(name: .long, help: "Screen index for coordinate translation")
    var screen: Int?

    @Option(name: .long, help: "Modifier keys: cmd, shift, alt, ctrl")
    var modifier: String?

    @Option(name: .long, help: "Intermediate drag points (default: 20)")
    var steps: Int = 20

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func validate() throws {
        let hasFrom = from != nil || (fromX != nil && fromY != nil)
        let hasTo = to != nil || (toX != nil && toY != nil)
        if !hasFrom { throw ValidationError("Provide --from <element> or --from-x/--from-y") }
        if !hasTo { throw ValidationError("Provide --to <element> or --to-x/--to-y") }
    }

    func run() throws {
        let sx: Double, sy: Double
        var fromLabel = ""
        let dx: Double, dy: Double
        var toLabel = ""

        if let from = from {
            let el = try ElementStore.resolve(from, snap: snapshot)
            sx = Double(el.centerX); sy = Double(el.centerY)
            fromLabel = "\(el.id) \"\(el.label)\""
        } else if let fx = fromX, let fy = fromY {
            if let idx = screen, let info = ScreenCapture.screenInfo(index: idx) {
                sx = (fx / info.scaleFactor) + Double(info.originX)
                sy = (fy / info.scaleFactor) + Double(info.originY)
            } else { sx = fx; sy = fy }
        } else { sx = 0; sy = 0 }

        if let to = to {
            let el = try ElementStore.resolve(to, snap: snapshot)
            dx = Double(el.centerX); dy = Double(el.centerY)
            toLabel = "\(el.id) \"\(el.label)\""
        } else if let tx = toX, let ty = toY {
            if let idx = screen, let info = ScreenCapture.screenInfo(index: idx) {
                dx = (tx / info.scaleFactor) + Double(info.originX)
                dy = (ty / info.scaleFactor) + Double(info.originY)
            } else { dx = tx; dy = ty }
        } else { dx = 0; dy = 0 }

        let flags = modifier.map { Keyboard.parseModifiers($0) } ?? []
        MouseControl.drag(fromX: sx, fromY: sy, toX: dx, toY: dy, steps: steps, flags: flags)

        if json {
            print("{\"action\":\"drag\",\"fromX\":\(Int(sx)),\"fromY\":\(Int(sy)),\"toX\":\(Int(dx)),\"toY\":\(Int(dy)),\"ok\":true}")
        } else {
            let mod = modifier != nil ? "[\(modifier!)] " : ""
            let src = fromLabel.isEmpty ? "(\(Int(sx)), \(Int(sy)))" : "\(fromLabel)"
            let dst = toLabel.isEmpty ? "(\(Int(dx)), \(Int(dy)))" : "\(toLabel)"
            print("\(mod)Dragged \(src) → \(dst)")
        }
    }
}
