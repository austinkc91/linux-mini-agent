import ArgumentParser
import AppKit
import Foundation

struct Wait: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Wait for an app to launch or a UI element to appear."
    )

    @Option(name: .long, help: "Element label or ID to wait for")
    var `for`: String?

    @Option(name: .long, help: "App name (required for element wait, or alone to wait for app)")
    var app: String?

    @Option(name: .long, help: "Max seconds to wait (default: 10)")
    var timeout: Double = 10

    @Option(name: .long, help: "Poll interval in seconds (default: 0.5)")
    var interval: Double = 0.5

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func validate() throws {
        guard app != nil || `for` != nil else {
            throw ValidationError("Provide --app, --for, or both")
        }
    }

    func run() throws {
        let deadline = Date().addingTimeInterval(timeout)

        if let appName = app, `for` == nil {
            try waitForApp(appName, deadline: deadline)
        } else if let query = `for` {
            try waitForElement(query, appName: app, deadline: deadline)
        }
    }

    private func waitForApp(_ name: String, deadline: Date) throws {
        while Date() < deadline {
            if AppControl.find(name) != nil {
                print(json ? "{\"action\":\"wait\",\"condition\":\"app\",\"app\":\"\(name)\",\"ok\":true}" : "Found \(name)")
                return
            }
            Thread.sleep(forTimeInterval: interval)
        }
        if json { print("{\"action\":\"wait\",\"condition\":\"app\",\"app\":\"\(name)\",\"ok\":false,\"error\":\"timeout\"}") }
        throw SteerError.waitTimeout("app \(name)", timeout)
    }

    private func waitForElement(_ query: String, appName: String?, deadline: Date) throws {
        let lq = query.lowercased()
        while Date() < deadline {
            let target: NSRunningApplication?
            if let name = appName { target = AppControl.find(name) }
            else { target = AppControl.frontmost() }

            if let target = target {
                let elements = AccessibilityTree.walk(app: target)
                if let el = elements.first(where: { $0.id.lowercased() == lq })
                    ?? elements.first(where: { $0.label.lowercased() == lq })
                    ?? elements.first(where: { $0.label.lowercased().contains(lq) }) {
                    if json {
                        print("{\"action\":\"wait\",\"condition\":\"element\",\"id\":\"\(el.id)\",\"label\":\"\(el.label)\",\"app\":\"\(target.localizedName ?? "?")\",\"ok\":true}")
                    } else {
                        print("Found \(el.id) \"\(el.label)\" in \(target.localizedName ?? "?")")
                    }
                    return
                }
            }
            Thread.sleep(forTimeInterval: interval)
        }
        let ctx = appName ?? "frontmost"
        if json { print("{\"action\":\"wait\",\"condition\":\"element\",\"for\":\"\(query)\",\"app\":\"\(ctx)\",\"ok\":false,\"error\":\"timeout\"}") }
        throw SteerError.waitTimeout("element \"\(query)\" in \(ctx)", timeout)
    }
}
