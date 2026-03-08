import ArgumentParser
import AppKit
import Foundation

struct Focus: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Show the currently focused UI element."
    )

    @Option(name: .long, help: "Target app name (default: frontmost)")
    var app: String?

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        let target: NSRunningApplication
        if let name = app {
            guard let found = AppControl.find(name) else { throw SteerError.appNotFound(name) }
            target = found
        } else {
            guard let front = AppControl.frontmost() else { throw SteerError.appNotFound("(no frontmost)") }
            target = front
        }

        let appName = target.localizedName ?? "?"

        guard let el = AccessibilityTree.focusedElement(app: target) else {
            if json {
                print("{\"app\":\"\(appName)\",\"focused\":null}")
            } else {
                print("app: \(appName)")
                print("focused: (none)")
            }
            return
        }

        if json {
            let enc = JSONEncoder()
            enc.outputFormatting = [.prettyPrinted, .sortedKeys]
            let elJson = (try? String(data: enc.encode(el), encoding: .utf8)) ?? "{}"
            print("{\"app\":\"\(appName)\",\"focused\":\(elJson)}")
        } else {
            let lbl = el.label.isEmpty ? (el.value ?? "(no label)") : el.label
            print("app: \(appName)")
            print("focused: \(el.role) \"\(lbl)\"  (\(el.x),\(el.y) \(el.width)x\(el.height))")
            if let v = el.value, !v.isEmpty && !el.label.isEmpty {
                print("  value: \"\(String(v.prefix(80)))\"")
            }
        }
    }
}
