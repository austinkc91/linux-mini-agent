import CoreGraphics
import Foundation

enum Keyboard {
    /// Type a string using virtual key codes for each character.
    /// Uses correct key codes so keystrokes work through Screen Sharing / VNC.
    static func typeText(_ text: String) {
        // Release all modifiers upfront to prevent sticky state from prior hotkey calls
        releaseAllModifiers()
        usleep(30_000) // 30ms settle

        for char in text {
            if let (code, shifted) = resolveChar(char) {
                // Use virtual key code path — works through Screen Sharing
                let flags: CGEventFlags = shifted ? .maskShift : []
                let dn = CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(code), keyDown: true)
                dn?.flags = flags
                dn?.post(tap: .cghidEventTap)
                usleep(8_000)
                let up = CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(code), keyDown: false)
                up?.flags = []
                up?.post(tap: .cghidEventTap)
                if shifted { releaseKey(56) } // Release Shift
                usleep(8_000)
            } else {
                // Fallback to unicode path for unmapped characters (emoji, etc.)
                var u = Array(char.utf16)
                let d = CGEvent(keyboardEventSource: nil, virtualKey: 0, keyDown: true)
                d?.keyboardSetUnicodeString(stringLength: u.count, unicodeString: &u)
                d?.flags = []
                d?.post(tap: .cghidEventTap)
                usleep(8_000)
                let up = CGEvent(keyboardEventSource: nil, virtualKey: 0, keyDown: false)
                up?.keyboardSetUnicodeString(stringLength: u.count, unicodeString: &u)
                up?.flags = []
                up?.post(tap: .cghidEventTap)
                usleep(8_000)
            }
        }
    }

    /// Resolve a Character to its virtual key code and whether Shift is needed
    private static func resolveChar(_ char: Character) -> (UInt16, Bool)? {
        let lower = Character(char.lowercased())
        // Direct match in letters map (lowercase letters, digits, unshifted symbols)
        if let code = letters[lower] {
            let shifted = char.isUppercase || shiftedChars[char] != nil
            return (code, shifted)
        }
        // Shifted symbol — look up the base key
        if let base = shiftedChars[char], let code = letters[base] {
            return (code, true)
        }
        // Space
        if char == " " { return (49, false) }
        return nil
    }

    /// Map of shifted characters to their unshifted base key
    private static let shiftedChars: [Character: Character] = [
        "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
        "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
        "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
        ":": ";", "\"": "'", "<": ",", ">": ".", "?": "/",
        "~": "`",
    ]

    /// Parse modifier string like "cmd+shift" into CGEventFlags
    static func parseModifiers(_ combo: String) -> CGEventFlags {
        var flags: CGEventFlags = []
        for m in combo.lowercased().split(separator: "+").map(String.init) {
            switch m {
            case "cmd", "command": flags.insert(.maskCommand)
            case "shift": flags.insert(.maskShift)
            case "alt", "option", "opt": flags.insert(.maskAlternate)
            case "ctrl", "control": flags.insert(.maskControl)
            case "fn": flags.insert(.maskSecondaryFn)
            default: break
            }
        }
        return flags
    }

    /// Execute a hotkey combo: "cmd+s", "cmd+shift+n", "return", "escape"
    static func hotkey(_ combo: String) {
        let parts = combo.lowercased().split(separator: "+").map(String.init)
        guard let keyPart = parts.last, let code = resolve(keyPart) else {
            fputs("steer: unknown key in combo '\(combo)'\n", stderr)
            return
        }
        let flags = parseModifiers(parts.dropLast().joined(separator: "+"))

        // Key down with modifiers
        let dn = CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(code), keyDown: true)
        dn?.flags = flags
        dn?.post(tap: .cghidEventTap)
        usleep(30_000) // 30ms hold

        // Key up — clear modifier flags so OS knows they're released
        let up = CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(code), keyDown: false)
        up?.flags = []
        up?.post(tap: .cghidEventTap)

        // Explicitly release all modifier keys to prevent sticky state
        if flags.contains(.maskCommand) {
            releaseKey(55) // Left Command
        }
        if flags.contains(.maskShift) {
            releaseKey(56) // Left Shift
        }
        if flags.contains(.maskAlternate) {
            releaseKey(58) // Left Option
        }
        if flags.contains(.maskControl) {
            releaseKey(59) // Left Control
        }
        usleep(30_000) // 30ms settle after modifier release
    }

    /// Send a key-up event for a specific virtual key code
    private static func releaseKey(_ code: UInt16) {
        let up = CGEvent(keyboardEventSource: nil, virtualKey: CGKeyCode(code), keyDown: false)
        up?.flags = []
        up?.post(tap: .cghidEventTap)
    }

    /// Release all modifier keys to clear any sticky state
    static func releaseAllModifiers() {
        releaseKey(55) // Left Command
        releaseKey(56) // Left Shift
        releaseKey(58) // Left Option
        releaseKey(59) // Left Control
    }

    /// Resolve a key name to its virtual key code
    static func resolve(_ k: String) -> UInt16? {
        if let c = codes[k] { return c }
        if k.count == 1, let ch = k.first, let c = letters[ch] { return c }
        return nil
    }

    static let codes: [String: UInt16] = [
        "return": 36, "enter": 36, "tab": 48, "space": 49,
        "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
        "left": 123, "right": 124, "down": 125, "up": 126,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
        "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
        "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
        "forwarddelete": 117,
    ]

    static let letters: [Character: UInt16] = [
        "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
        "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
        "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
        "0": 29, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28, "9": 25,
        "-": 27, "=": 24, "[": 33, "]": 30, ";": 41, "'": 39, ",": 43, ".": 47, "/": 44, "`": 50,
        "\\": 42,
    ]
}
