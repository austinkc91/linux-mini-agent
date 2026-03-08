import ArgumentParser
import AppKit
import Foundation

struct See: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Capture screenshot + accessibility tree. Returns element map as JSON."
    )

    @Option(name: .long, help: "Target app name (default: frontmost)")
    var app: String?

    @Option(name: .long, help: "Screen index to capture (from 'steer screens')")
    var screen: Int?

    @Flag(name: .long, help: "Run OCR when accessibility tree is empty")
    var ocr = false

    @Option(name: .long, help: "Filter elements by role: button, text, image, etc.")
    var role: String?

    @Flag(name: .long, help: "Output compact JSON (default: human-readable table)")
    var json = false

    func run() throws {
        let image: CGImage
        let appName: String
        var elements: [UIElement] = []

        var windows: [ScreenCapture.WindowBounds] = []

        if let screenIndex = screen, app == nil {
            image = try ScreenCapture.captureScreen(index: screenIndex)
            appName = "screen-\(screenIndex)"
        } else {
            let target: NSRunningApplication
            if let name = app {
                guard let found = AppControl.find(name) else { throw SteerError.appNotFound(name) }
                target = found
            } else {
                guard let front = AppControl.frontmost() else { throw SteerError.appNotFound("(no frontmost)") }
                target = front
            }
            image = try ScreenCapture.captureApp(target)
            appName = target.localizedName ?? "?"
            elements = AccessibilityTree.walk(app: target)
            windows = ScreenCapture.windowBounds(for: target)

            if elements.isEmpty && ocr {
                let ocrResults = try OCR.recognize(image: image)
                elements = OCR.toElements(ocrResults)
            }
        }

        let snapId = String(UUID().uuidString.prefix(8).lowercased())
        try? FileManager.default.createDirectory(at: ElementStore.dir, withIntermediateDirectories: true)
        let screenshotURL = ElementStore.dir.appendingPathComponent("\(snapId).png")
        try ScreenCapture.savePNG(image, to: screenshotURL)

        if !elements.isEmpty {
            ElementStore.save(id: snapId, elements: elements)
        }

        let displayed = role != nil
            ? elements.filter { $0.role.lowercased().contains(role!.lowercased()) }
            : elements

        if json {
            let enc = JSONEncoder()
            enc.outputFormatting = [.prettyPrinted, .sortedKeys]
            let elJson = (try? String(data: enc.encode(displayed), encoding: .utf8)) ?? "[]"
            let winJson = (try? String(data: enc.encode(windows), encoding: .utf8)) ?? "[]"
            print("""
            {"snapshot":"\(snapId)","app":"\(appName)","screenshot":"\(screenshotURL.path)","count":\(displayed.count),"windows":\(winJson),"elements":\(elJson)}
            """)
        } else {
            print("snapshot: \(snapId)")
            print("app: \(appName)")
            print("screenshot: \(screenshotURL.path)")
            print("elements: \(displayed.count)\(role != nil ? " (filtered by \(role!))" : "")")
            for w in windows {
                let title = w.windowTitle ?? ""
                print("  window: (\(w.windowX),\(w.windowY)) \(w.windowWidth)x\(w.windowHeight)  \"\(title)\"")
            }
            print("")
            if displayed.isEmpty && screen != nil {
                print("  (full screen capture — no element tree)")
            } else if elements.isEmpty && !AccessibilityTree.isAccessibilityGranted() {
                print("  Accessibility permission required. Grant access in:")
                print("  System Settings > Privacy & Security > Accessibility")
                print("  (a permission prompt should have appeared)")
            } else if displayed.isEmpty {
                print("  (no interactive elements found for this app)")
            } else {
                for el in displayed {
                    let lbl = el.label.isEmpty ? (el.value ?? "") : el.label
                    let t = String(lbl.prefix(40))
                    print("  \(el.id.padding(toLength: 6, withPad: " ", startingAt: 0)) \(el.role.padding(toLength: 14, withPad: " ", startingAt: 0)) \"\(t)\"  (\(el.x),\(el.y) \(el.width)x\(el.height))")
                }
            }
        }
    }
}
