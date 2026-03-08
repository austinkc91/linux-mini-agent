import AppKit
import CoreGraphics
import Foundation
import UniformTypeIdentifiers

enum ScreenCapture {
    static func captureDisplay() throws -> CGImage {
        guard let image = CGWindowListCreateImage(
            CGRect.null, .optionOnScreenOnly, kCGNullWindowID, [.bestResolution]
        ) else { throw SteerError.captureFailure("Failed to capture display") }
        return image
    }

    static func captureApp(_ app: NSRunningApplication) throws -> CGImage {
        let list = CGWindowListCopyWindowInfo(
            [.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID
        ) as? [[String: Any]] ?? []
        let wins = list.filter {
            ($0[kCGWindowOwnerPID as String] as? pid_t) == app.processIdentifier
        }
        guard let first = wins.first,
              let wid = first[kCGWindowNumber as String] as? CGWindowID else {
            return try captureDisplay()
        }
        if let image = CGWindowListCreateImage(
            CGRect.null, .optionIncludingWindow, wid, [.bestResolution, .boundsIgnoreFraming]
        ) {
            return image
        }
        // Fall back to full display capture if per-window capture fails (e.g. missing Screen Recording permission)
        return try captureDisplay()
    }

    static func listScreens() -> [ScreenInfo] {
        NSScreen.screens.enumerated().map { (i, screen) in
            let frame = screen.frame
            return ScreenInfo(
                index: i,
                name: screen.localizedName,
                width: Int(frame.size.width),
                height: Int(frame.size.height),
                originX: Int(frame.origin.x),
                originY: Int(frame.origin.y),
                isMain: screen == NSScreen.main,
                scaleFactor: screen.backingScaleFactor
            )
        }
    }

    static func captureScreen(index: Int) throws -> CGImage {
        let screens = NSScreen.screens
        guard index >= 0, index < screens.count else {
            throw SteerError.screenNotFound(index, available: screens.count)
        }
        let screen = screens[index]
        let displayID = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as! CGDirectDisplayID
        let bounds = CGDisplayBounds(displayID)
        guard let image = CGWindowListCreateImage(
            bounds, .optionOnScreenOnly, kCGNullWindowID, [.bestResolution]
        ) else {
            throw SteerError.captureFailure("Failed to capture screen \(index)")
        }
        return image
    }

    struct WindowBounds: Codable {
        let windowX: Int
        let windowY: Int
        let windowWidth: Int
        let windowHeight: Int
        let windowTitle: String?
        let windowID: UInt32
    }

    static func windowBounds(for app: NSRunningApplication) -> [WindowBounds] {
        let list = CGWindowListCopyWindowInfo(
            [.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID
        ) as? [[String: Any]] ?? []
        return list.compactMap { win -> WindowBounds? in
            guard (win[kCGWindowOwnerPID as String] as? pid_t) == app.processIdentifier,
                  let bounds = win[kCGWindowBounds as String] as? [String: CGFloat],
                  let wid = win[kCGWindowNumber as String] as? CGWindowID else { return nil }
            let w = bounds["Width"] ?? 0
            let h = bounds["Height"] ?? 0
            guard w > 1 && h > 1 else { return nil }
            return WindowBounds(
                windowX: Int(bounds["X"] ?? 0), windowY: Int(bounds["Y"] ?? 0),
                windowWidth: Int(w), windowHeight: Int(h),
                windowTitle: win[kCGWindowName as String] as? String,
                windowID: wid
            )
        }
    }

    static func screenInfo(index: Int) -> ScreenInfo? {
        let screens = NSScreen.screens
        guard index >= 0, index < screens.count else { return nil }
        let screen = screens[index]
        let frame = screen.frame
        return ScreenInfo(
            index: index,
            name: screen.localizedName,
            width: Int(frame.size.width),
            height: Int(frame.size.height),
            originX: Int(frame.origin.x),
            originY: Int(frame.origin.y),
            isMain: screen == NSScreen.main,
            scaleFactor: screen.backingScaleFactor
        )
    }

    static func savePNG(_ image: CGImage, to url: URL) throws {
        guard let dest = CGImageDestinationCreateWithURL(
            url as CFURL, UTType.png.identifier as CFString, 1, nil
        ) else { throw SteerError.captureFailure("Cannot create image dest") }
        CGImageDestinationAddImage(dest, image, nil)
        guard CGImageDestinationFinalize(dest) else {
            throw SteerError.captureFailure("Failed to write PNG")
        }
    }
}
