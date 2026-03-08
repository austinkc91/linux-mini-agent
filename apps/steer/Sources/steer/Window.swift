import ArgumentParser
import Foundation

struct Window: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Manage app windows: move, resize, minimize, fullscreen, close."
    )

    @Argument(help: "Action: list | move | resize | minimize | restore | fullscreen | close")
    var action: String

    @Argument(help: "App name")
    var app: String

    @Option(name: .shortAndLong, help: "X position (for move)")
    var x: Double?

    @Option(name: .shortAndLong, help: "Y position (for move)")
    var y: Double?

    @Option(name: .shortAndLong, help: "Width (for resize)")
    var width: Double?

    @Option(name: .shortAndLong, help: "Height (for resize)")
    var height: Double?

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        switch action.lowercased() {
        case "list":
            let windows = try WindowControl.listWindows(appName: app)
            if json {
                let enc = JSONEncoder()
                enc.outputFormatting = .prettyPrinted
                if let d = try? enc.encode(windows) { print(String(data: d, encoding: .utf8) ?? "[]") }
            } else {
                for (i, w) in windows.enumerated() {
                    let title = w.title.isEmpty ? "(untitled)" : w.title
                    let flags = [w.isMinimized ? "minimized" : nil, w.isFullscreen ? "fullscreen" : nil]
                        .compactMap { $0 }.joined(separator: ", ")
                    let extra = flags.isEmpty ? "" : "  [\(flags)]"
                    print("  \(i)  \"\(title)\"  (\(w.x),\(w.y) \(w.width)x\(w.height))\(extra)")
                }
            }
        case "move":
            guard let x = x, let y = y else { throw ValidationError("move requires --x and --y") }
            try WindowControl.move(appName: app, x: x, y: y)
            print(json ? "{\"action\":\"move\",\"app\":\"\(app)\",\"x\":\(Int(x)),\"y\":\(Int(y)),\"ok\":true}" : "Moved \(app) to (\(Int(x)), \(Int(y)))")
        case "resize":
            guard let width = width, let height = height else { throw ValidationError("resize requires --width and --height") }
            try WindowControl.resize(appName: app, width: width, height: height)
            print(json ? "{\"action\":\"resize\",\"app\":\"\(app)\",\"width\":\(Int(width)),\"height\":\(Int(height)),\"ok\":true}" : "Resized \(app) to \(Int(width))x\(Int(height))")
        case "minimize":
            try WindowControl.minimize(appName: app)
            print(json ? "{\"action\":\"minimize\",\"app\":\"\(app)\",\"ok\":true}" : "Minimized \(app)")
        case "restore":
            try WindowControl.minimize(appName: app, flag: false)
            print(json ? "{\"action\":\"restore\",\"app\":\"\(app)\",\"ok\":true}" : "Restored \(app)")
        case "fullscreen":
            try WindowControl.fullscreen(appName: app)
            print(json ? "{\"action\":\"fullscreen\",\"app\":\"\(app)\",\"ok\":true}" : "Toggled fullscreen for \(app)")
        case "close":
            try WindowControl.close(appName: app)
            print(json ? "{\"action\":\"close\",\"app\":\"\(app)\",\"ok\":true}" : "Closed \(app) window")
        default:
            throw ValidationError("Action must be: list, move, resize, minimize, restore, fullscreen, close")
        }
    }
}
