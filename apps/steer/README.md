# steer

**macOS automation CLI for AI agents.** Give your agent the wheel.

7 commands, 1 binary, ~750 lines of Swift. Wraps CGEvent, AXUIElement, CGWindowListCreateImage, NSWorkspace, and NSScreen.

## Install

```bash
cd steer
swift build -c release
cp .build/release/steer /usr/local/bin/
```

## Requirements

- macOS 13+
- **Accessibility** permission — required for element tree + input events
- **Screen Recording** permission — required for screenshots

Steer auto-prompts for Accessibility on first run. Grant both in System Settings > Privacy & Security.

## Commands

### see — Screenshot + accessibility tree

```bash
steer see                        # frontmost app
steer see --app Safari           # target app by name
steer see --screen 1             # capture specific display
steer see --json                 # structured output for agents
```

### click — Click elements or coordinates

```bash
steer click --on B3              # by element ID
steer click --on "Submit"        # by label text
steer click --x 500 --y 300     # by coordinates
steer click --on B3 --double    # double-click
steer click --on B3 --right     # right-click
steer click --x 100 --y 200 --screen 1  # with screen coordinate translation
```

### type — Type text

```bash
steer type "hello world"                    # into focused element
steer type "search query" --into T1         # click target first
steer type "replace" --into T1 --clear      # clear field, then type
```

### hotkey — Key combinations

```bash
steer hotkey cmd+s
steer hotkey cmd+shift+n
steer hotkey return
steer hotkey escape
```

### scroll — Scroll by lines

```bash
steer scroll down 5
steer scroll up 3
steer scroll left 2
steer scroll right 2
```

### apps — App management

```bash
steer apps list                  # running apps with PIDs
steer apps launch Safari         # open an app
steer apps activate "VS Code"   # bring to front
```

### screens — Display info

```bash
steer screens                    # list connected displays
steer screens --json             # with resolution, origin, scale factor
```

## The Agent Loop

```bash
steer see --json          # 1. observe — screenshot + element map
steer click --on B3       # 2. act — click, type, hotkey
steer see --json          # 3. verify — see the result
```

Element IDs (`B3`, `T1`, `S5`) are stable within a snapshot. `click` and `type` resolve IDs from the latest snapshot automatically.

## Multi-Monitor

```bash
steer screens
#  0  Built-in Retina Display  1728x1117  at (0,0)       scale:2.0 (main)
#  1  LG ULTRAWIDE             5120x1440  at (-1567,1117) scale:1.0

steer see --screen 1                          # capture specific display
steer click --x 500 --y 300 --screen 1       # auto-translates to global coords
```

The `--screen` flag on `click` handles coordinate translation (screen offset + Retina scaling) so agents don't need to do math.

## Element ID Prefixes

| Prefix | Role |
|--------|------|
| B | Button |
| T | Text field / text area / search / combo box |
| S | Static text |
| I | Image |
| C | Checkbox |
| R | Radio button |
| P | Pop-up button |
| SL | Slider |
| L | Link |
| M | Menu item / menu bar item |
| TB | Tab |
| E | Other |

## JSON Mode

All commands support `--json`:

```json
{"snapshot":"a1b2c3d4","app":"Finder","screenshot":"/tmp/steer/a1b2c3d4.png","count":141,"elements":[...]}
{"action":"click","x":450,"y":320,"label":"B3 \"Submit\"","ok":true}
{"action":"type","text":"hello","ok":true}
```

## Known Limitations

- **Electron apps** (VS Code, Slack, Discord) expose minimal accessibility trees — only native window chrome and menu bar
- **Native apps** (Finder, Safari, TextEdit, Xcode) expose full element trees
- Element IDs are positional per-snapshot, not persistent across snapshots
- Screen indices from `steer screens` can shift if displays are connected/disconnected

## Architecture

```
steer (ArgumentParser)
  ├── see        → ScreenCapture + AccessibilityTree + ElementStore
  ├── click      → ElementStore.resolve + MouseControl
  ├── type       → ElementStore.resolve + Keyboard + MouseControl
  ├── hotkey     → Keyboard
  ├── scroll     → MouseControl
  ├── apps       → AppControl (NSWorkspace)
  └── screens    → ScreenCapture.listScreens (NSScreen)
```

## License

MIT
