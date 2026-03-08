import ArgumentParser

@main
struct Steer: ParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "steer",
        abstract: "macOS automation CLI for AI agents. Eyes and hands on your Mac.",
        version: "0.2.0",
        subcommands: [
            See.self, Click.self, Type.self, Hotkey.self, Scroll.self, Drag.self,
            Apps.self, Screens.self, Window.self,
            OcrCommand.self, Focus.self, Find.self,
            Clipboard.self, Wait.self
        ]
    )
}
