import AppKit
import Foundation

enum ClipboardControl {
    static func readText() -> String? {
        NSPasteboard.general.string(forType: .string)
    }

    static func writeText(_ text: String) {
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(text, forType: .string)
    }

    static func availableType() -> String {
        let pb = NSPasteboard.general
        if pb.availableType(from: [.string]) != nil { return "text" }
        if pb.availableType(from: [.tiff, .png]) != nil { return "image" }
        return "empty"
    }

    static func readImage(saveTo path: String? = nil) throws -> String {
        let pb = NSPasteboard.general
        guard let imgData = pb.data(forType: .tiff) ?? pb.data(forType: .png) else {
            throw SteerError.clipboardEmpty("image")
        }
        guard let image = NSImage(data: imgData),
              let tiffData = image.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiffData),
              let pngData = bitmap.representation(using: .png, properties: [:]) else {
            throw SteerError.clipboardEmpty("image")
        }
        let outPath: String
        if let path = path {
            outPath = path
        } else {
            try? FileManager.default.createDirectory(at: ElementStore.dir, withIntermediateDirectories: true)
            outPath = ElementStore.dir.appendingPathComponent("clipboard-\(UUID().uuidString.prefix(8).lowercased()).png").path
        }
        try pngData.write(to: URL(fileURLWithPath: outPath))
        return outPath
    }

    static func writeImage(fromPath path: String) throws {
        guard let image = NSImage(contentsOfFile: path) else {
            throw SteerError.clipboardEmpty("image at \(path)")
        }
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.writeObjects([image])
    }
}
