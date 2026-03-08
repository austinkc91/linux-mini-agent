import ArgumentParser
import Foundation

struct Hotkey: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Press a key combination: cmd+s, ctrl+c, return, escape, etc."
    )

    @Argument(help: "Key combo: cmd+s, cmd+shift+n, return, escape, tab, etc.")
    var combo: String

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        Keyboard.hotkey(combo)

        if json {
            print("{\"action\":\"hotkey\",\"combo\":\"\(combo)\",\"ok\":true}")
        } else {
            print("Pressed \(combo)")
        }
    }
}
