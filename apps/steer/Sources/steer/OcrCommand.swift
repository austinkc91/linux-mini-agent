import ArgumentParser
import AppKit
import Foundation

struct OcrCommand: ParsableCommand {
    static let configuration = CommandConfiguration(
        commandName: "ocr",
        abstract: "Extract text from a screenshot via OCR. Works on Electron apps where AX tree is empty."
    )

    @Option(name: .long, help: "Path to a screenshot PNG (default: captures fresh)")
    var image: String?

    @Option(name: .long, help: "Target app name (default: frontmost)")
    var app: String?

    @Option(name: .long, help: "Screen index to capture")
    var screen: Int?

    @Option(name: .long, help: "Minimum confidence 0.0-1.0 (default: 0.5)")
    var confidence: Float = 0.5

    @Flag(name: .long, help: "Save OCR results as snapshot for click --on")
    var store = false

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        let cgImage: CGImage
        let appName: String

        if let imagePath = image {
            guard let dp = CGDataProvider(filename: imagePath),
                  let img = CGImage(pngDataProviderSource: dp, decode: nil, shouldInterpolate: true, intent: .defaultIntent) else {
                throw SteerError.captureFailure("Cannot load: \(imagePath)")
            }
            cgImage = img
            appName = URL(fileURLWithPath: imagePath).deletingPathExtension().lastPathComponent
        } else if let screenIndex = screen, app == nil {
            cgImage = try ScreenCapture.captureScreen(index: screenIndex)
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
            cgImage = try ScreenCapture.captureApp(target)
            appName = target.localizedName ?? "?"
        }

        let results = try OCR.recognize(image: cgImage, minimumConfidence: confidence)
        var snapId: String? = nil

        if store {
            let id = String(UUID().uuidString.prefix(8).lowercased())
            snapId = id
            try? FileManager.default.createDirectory(at: ElementStore.dir, withIntermediateDirectories: true)
            try ScreenCapture.savePNG(cgImage, to: ElementStore.dir.appendingPathComponent("\(id).png"))
            ElementStore.save(id: id, elements: OCR.toElements(results))
        }

        if json {
            let enc = JSONEncoder()
            enc.outputFormatting = [.prettyPrinted, .sortedKeys]
            let rJson = (try? String(data: enc.encode(results), encoding: .utf8)) ?? "[]"
            var obj = "{\"app\":\"\(appName)\",\"count\":\(results.count)"
            if let s = snapId { obj += ",\"snapshot\":\"\(s)\"" }
            obj += ",\"results\":\(rJson)}"
            print(obj)
        } else {
            print("app: \(appName)")
            print("text regions: \(results.count)")
            if let s = snapId { print("snapshot: \(s)") }
            print("")
            for r in results {
                let t = String(r.text.prefix(60))
                print("  \"\(t)\"  (\(r.x),\(r.y) \(r.width)x\(r.height))  conf:\(String(format: "%.2f", r.confidence))")
            }
        }
    }
}
