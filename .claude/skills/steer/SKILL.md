---
name: steer
description: Linux GUI automation CLI. Use steer to see the screen, click elements, type text, send hotkeys, scroll, drag, manage windows and apps, run OCR on Electron apps, and wait for UI conditions.
---

# Steer — Linux GUI Automation

Run from: `cd apps/steer && uv run python main.py <command>`

Run `steer --help` and `steer <command> --help` to learn each command's flags before using it.

## Commands

| Command     | Purpose                                                                                                                                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `see`       | Takes a screenshot (PNG) and walks the accessibility tree. Screenshot always succeeds. Elements are best-effort — may be empty for Electron apps. Pass `--ocr` to fall back to OCR when the tree is empty. |
| `click`     | Click by element ID, label, or coordinates                                                                                                                                                                 |
| `type`      | Type text into focused element or a target                                                                                                                                                                 |
| `hotkey`    | Keyboard shortcuts (ctrl+s, return, escape, etc.)                                                                                                                                                          |
| `scroll`    | Scroll up/down/left/right                                                                                                                                                                                  |
| `drag`      | Drag between elements or coordinates                                                                                                                                                                       |
| `apps`      | List, launch, or activate apps                                                                                                                                                                             |
| `screens`   | List displays with resolution and position                                                                                                                                                                 |
| `window`    | Move, resize, minimize, fullscreen, close windows                                                                                                                                                          |
| `ocr`       | Takes a screenshot and runs Tesseract OCR on it. Returns text with x/y positions. Use `--store` to make results clickable (O1, O2, etc.). Use when `see` returns no elements.                              |
| `focus`     | Show currently focused element                                                                                                                                                                             |
| `find`      | Search elements by text in latest snapshot                                                                                                                                                                 |
| `clipboard` | Read/write system clipboard                                                                                                                                                                                |
| `wait`      | Wait for app launch or element to appear                                                                                                                                                                   |

Always pass `--json` for structured output.

## How to Work

You are controlling a real Linux desktop. You cannot see anything unless you explicitly look. You cannot assume anything worked unless you verify.

### 1. Know your environment first

Before doing anything, understand the display setup, what's running, and capture the current state:

```
steer screens --json       → which monitors exist, their resolution
steer apps --json          → what apps are running
steer see --screen 0 --json  → screenshot of screen 0 (primary)
```

### 2. Focus the app, then verify

Before interacting with any app, make sure it's the active window:

```
steer apps activate firefox --json
steer see --app firefox --json        → verify it's in front, read the state
```

### 3. One action, then observe

**NEVER chain multiple steer commands in one bash call.** The screen changes after every action. You must look after every action.

The loop is:

1. `steer see` — look at the screen
2. Read the JSON — understand what you see
3. Do ONE action (click, type, hotkey, scroll)
4. `steer see` — look again to confirm it worked
5. Repeat

### 4. Clicking safely

Before clicking anything:

- Run `steer see --app <app> --json` to get a fresh snapshot
- Use element IDs from the snapshot (B1, T1, L3) — not coordinates when possible
- After clicking, run `steer see` again to confirm the click landed

### 5. Typing into fields

- Before typing anything: ALWAYS check focus with `steer focus --json`
- Use `steer type "text" --into T1 --json` to click-then-type in one step
- After typing, verify with `steer see` that the text appeared correctly
- For URLs in browsers: type the URL, then `steer hotkey return --json`

### 6. Reading content from apps

Both `see` and `ocr` save a screenshot PNG. The path is in the JSON output under `"screenshot"`. Read this image file to see what's on screen.

**Native apps**: `steer see --app <name> --json` gives the accessibility tree.

**Electron apps** (VS Code, Slack, Notion): Accessibility trees are empty. Use OCR:
```
steer ocr --app "code" --store --json
```

### 7. Hotkey mapping

Linux uses different modifier keys than macOS:
- `cmd` maps to `super` (the "Windows" key)
- `ctrl` stays `ctrl`
- `alt`/`option` maps to `alt`

Common shortcuts: `ctrl+s` (save), `ctrl+c` (copy), `ctrl+v` (paste), `alt+tab` (switch apps)

### 8. Multi-monitor awareness

If there are multiple screens, use `--screen <index>` when needed.

## Element IDs

Elements from `steer see` get role-based IDs: **B** (button), **T** (text field), **S** (static text), **I** (image), **C** (checkbox), **L** (link), **M** (menu item), **O** (OCR element), etc.

IDs regenerate with each snapshot. Always use IDs from the most recent `steer see` or `steer ocr --store`.

## Rules

- **One command per bash call** — never chain steer commands
- **Always verify** — `steer see` after every action
- **Focus first** — activate the app before interacting
- **Know your screens** — check `steer screens` before clicking
- **Use `--json` always** — structured output is reliable
- **Write all files to /tmp** — never write output files into the project directory
- **Run `steer <cmd> --help`** if you're unsure about a command's flags
