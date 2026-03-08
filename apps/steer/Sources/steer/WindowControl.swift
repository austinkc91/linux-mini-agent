import ApplicationServices
import AppKit
import Foundation

enum WindowControl {
    struct WinInfo: Codable {
        let app: String
        let title: String
        let x: Int
        let y: Int
        let width: Int
        let height: Int
        let isMinimized: Bool
        let isFullscreen: Bool
    }

    static func focusedWindow(appName: String) throws -> AXUIElement {
        guard let app = AppControl.find(appName) else { throw SteerError.appNotFound(appName) }
        let appEl = AXUIElementCreateApplication(app.processIdentifier)
        var win: CFTypeRef?
        if AXUIElementCopyAttributeValue(appEl, kAXFocusedWindowAttribute as CFString, &win) == .success,
           let w = win { return (w as! AXUIElement) }
        var windows: CFTypeRef?
        guard AXUIElementCopyAttributeValue(appEl, kAXWindowsAttribute as CFString, &windows) == .success,
              let winList = windows as? [AXUIElement], let first = winList.first else {
            throw SteerError.windowNotFound(appName)
        }
        return first
    }

    static func listWindows(appName: String) throws -> [WinInfo] {
        guard let app = AppControl.find(appName) else { throw SteerError.appNotFound(appName) }
        let appEl = AXUIElementCreateApplication(app.processIdentifier)
        var windows: CFTypeRef?
        guard AXUIElementCopyAttributeValue(appEl, kAXWindowsAttribute as CFString, &windows) == .success,
              let winList = windows as? [AXUIElement] else { return [] }
        return winList.map { w in
            let title = AccessibilityTree.axStr(w, kAXTitleAttribute) ?? ""
            var pos = CGPoint.zero; var size = CGSize.zero
            if let pv = AccessibilityTree.axVal(w, kAXPositionAttribute) { AXValueGetValue(pv, .cgPoint, &pos) }
            if let sv = AccessibilityTree.axVal(w, kAXSizeAttribute) { AXValueGetValue(sv, .cgSize, &size) }
            let minimized = AccessibilityTree.axBool(w, kAXMinimizedAttribute) ?? false
            let fullscreen = AccessibilityTree.axBool(w, "AXFullScreen") ?? false
            return WinInfo(app: appName, title: title,
                           x: Int(pos.x), y: Int(pos.y), width: Int(size.width), height: Int(size.height),
                           isMinimized: minimized, isFullscreen: fullscreen)
        }
    }

    static func move(appName: String, x: Double, y: Double) throws {
        let win = try focusedWindow(appName: appName)
        var point = CGPoint(x: x, y: y)
        guard let value = AXValueCreate(.cgPoint, &point) else { throw SteerError.windowActionFailed("move", appName) }
        guard AXUIElementSetAttributeValue(win, kAXPositionAttribute as CFString, value) == .success else {
            throw SteerError.windowActionFailed("move", appName)
        }
    }

    static func resize(appName: String, width: Double, height: Double) throws {
        let win = try focusedWindow(appName: appName)
        var size = CGSize(width: width, height: height)
        guard let value = AXValueCreate(.cgSize, &size) else { throw SteerError.windowActionFailed("resize", appName) }
        guard AXUIElementSetAttributeValue(win, kAXSizeAttribute as CFString, value) == .success else {
            throw SteerError.windowActionFailed("resize", appName)
        }
    }

    static func minimize(appName: String, flag: Bool = true) throws {
        let win = try focusedWindow(appName: appName)
        guard AXUIElementSetAttributeValue(win, kAXMinimizedAttribute as CFString, flag as CFBoolean) == .success else {
            throw SteerError.windowActionFailed("minimize", appName)
        }
    }

    static func fullscreen(appName: String) throws {
        let win = try focusedWindow(appName: appName)
        let current = AccessibilityTree.axBool(win, "AXFullScreen") ?? false
        let result = AXUIElementSetAttributeValue(win, "AXFullScreen" as CFString, (!current) as CFBoolean)
        if result != .success {
            var zoomBtn: CFTypeRef?
            guard AXUIElementCopyAttributeValue(win, "AXZoomButton" as CFString, &zoomBtn) == .success else {
                throw SteerError.windowActionFailed("fullscreen", appName)
            }
            AXUIElementPerformAction(zoomBtn as! AXUIElement, kAXPressAction as CFString)
        }
    }

    static func close(appName: String) throws {
        let win = try focusedWindow(appName: appName)
        var closeBtn: CFTypeRef?
        guard AXUIElementCopyAttributeValue(win, kAXCloseButtonAttribute as CFString, &closeBtn) == .success else {
            throw SteerError.windowActionFailed("close", appName)
        }
        AXUIElementPerformAction(closeBtn as! AXUIElement, kAXPressAction as CFString)
    }
}
