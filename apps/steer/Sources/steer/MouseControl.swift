import CoreGraphics
import Foundation

enum MouseControl {
    static func click(x: Double, y: Double, button: CGMouseButton = .left, count: Int = 1, flags: CGEventFlags = []) {
        let pt = CGPoint(x: x, y: y)
        let dType: CGEventType = button == .right ? .rightMouseDown
            : button == .center ? .otherMouseDown : .leftMouseDown
        let uType: CGEventType = button == .right ? .rightMouseUp
            : button == .center ? .otherMouseUp : .leftMouseUp
        CGWarpMouseCursorPosition(pt)
        usleep(20_000)
        for i in 1...count {
            let dn = CGEvent(mouseEventSource: nil, mouseType: dType, mouseCursorPosition: pt, mouseButton: button)
            let up = CGEvent(mouseEventSource: nil, mouseType: uType, mouseCursorPosition: pt, mouseButton: button)
            dn?.setIntegerValueField(.mouseEventClickState, value: Int64(i))
            up?.setIntegerValueField(.mouseEventClickState, value: Int64(i))
            if !flags.isEmpty { dn?.flags = flags; up?.flags = flags }
            dn?.post(tap: .cghidEventTap)
            usleep(50_000)
            up?.post(tap: .cghidEventTap)
            if i < count { usleep(50_000) }
        }
    }

    static func drag(fromX: Double, fromY: Double, toX: Double, toY: Double, steps: Int = 20, flags: CGEventFlags = []) {
        let start = CGPoint(x: fromX, y: fromY)
        let end = CGPoint(x: toX, y: toY)
        CGWarpMouseCursorPosition(start)
        usleep(50_000)
        let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: start, mouseButton: .left)
        if !flags.isEmpty { down?.flags = flags }
        down?.post(tap: .cghidEventTap)
        usleep(100_000)
        for i in 1...steps {
            let t = Double(i) / Double(steps)
            let pt = CGPoint(x: fromX + (toX - fromX) * t, y: fromY + (toY - fromY) * t)
            let drag = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDragged, mouseCursorPosition: pt, mouseButton: .left)
            if !flags.isEmpty { drag?.flags = flags }
            drag?.post(tap: .cghidEventTap)
            usleep(10_000)
        }
        usleep(50_000)
        let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: end, mouseButton: .left)
        if !flags.isEmpty { up?.flags = flags }
        up?.post(tap: .cghidEventTap)
    }

    static func moveTo(x: Double, y: Double) {
        CGWarpMouseCursorPosition(CGPoint(x: x, y: y))
    }

    static func scroll(dx: Int32 = 0, dy: Int32 = 0) {
        let ev = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: dy, wheel2: dx, wheel3: 0)
        ev?.post(tap: .cghidEventTap)
    }
}
