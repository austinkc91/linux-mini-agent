import ArgumentParser
import Foundation

struct Apps: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "List running apps, launch, or activate by name."
    )

    @Argument(help: "Action: list | launch | activate")
    var action: String = "list"

    @Argument(help: "App name (for launch/activate)")
    var name: String?

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        switch action.lowercased() {
        case "list":
            let apps = AppControl.list()
            if json {
                let enc = JSONEncoder()
                enc.outputFormatting = .prettyPrinted
                if let d = try? enc.encode(apps) { print(String(data: d, encoding: .utf8) ?? "[]") }
            } else {
                for a in apps {
                    let star = a.isActive ? " *" : ""
                    print("  \(a.name.padding(toLength: 25, withPad: " ", startingAt: 0)) pid:\(a.pid)\(star)")
                }
            }
        case "launch":
            guard let name = name else { throw ValidationError("Provide app name") }
            try AppControl.launch(name)
            print(json ? "{\"action\":\"launch\",\"app\":\"\(name)\",\"ok\":true}" : "Launched \(name)")
        case "activate", "focus":
            guard let name = name else { throw ValidationError("Provide app name") }
            try AppControl.activate(name)
            print(json ? "{\"action\":\"activate\",\"app\":\"\(name)\",\"ok\":true}" : "Activated \(name)")
        default:
            throw ValidationError("Action must be: list, launch, activate")
        }
    }
}
