# steer

**Linux GUI automation CLI for AI agents.** Give your agent the wheel.

14 commands, Python CLI using xdotool, scrot, tesseract, wmctrl, and xclip.

## Install

```bash
cd apps/steer
# Install system dependencies
sudo apt install xdotool scrot tesseract-ocr wmctrl xclip x11-utils imagemagick
# Install Python CLI
uv run python main.py --version
```

## Requirements

- Linux with X11 (Wayland not yet supported)
- **xdotool** — mouse, keyboard, and window control
- **scrot** — screenshots
- **tesseract-ocr** — OCR text recognition
- **wmctrl** — window management
- **xclip** — clipboard access
- **imagemagick** — window capture (import command)

Optional (for accessibility tree):
- **python3-gi** + **gir1.2-atspi-2.0** — AT-SPI accessibility

## Commands

### see — Screenshot + accessibility tree

```bash
steer see                        # frontmost app
steer see --app firefox          # target app by name
steer see --screen 1             # capture specific display
steer see --json                 # structured output for agents
```

### click — Click elements or coordinates

```bash
steer click --on B3              # by element ID
steer click --on "Submit"        # by label text
steer click -x 500 -y 300       # by coordinates
steer click --on B3 --double     # double-click
steer click --on B3 --right      # right-click
steer click -x 100 -y 200 --screen 1  # with screen coordinate translation
```

### type — Type text

```bash
steer type "hello world"                    # into focused element
steer type "search query" --into T1         # click target first
steer type "replace" --into T1 --clear      # clear field, then type
```

### hotkey — Key combinations

```bash
steer hotkey ctrl+s
steer hotkey ctrl+shift+n
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
steer apps launch firefox        # open an app
steer apps activate "code"       # bring to front
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
#  0  DP-1                        1920x1080  at (0,0)       scale:1.0 (main)
#  1  HDMI-1                      2560x1440  at (1920,0)    scale:1.0

steer see --screen 1                          # capture specific display
steer click -x 500 -y 300 --screen 1          # auto-translates to global coords
```

## Element ID Prefixes

| Prefix | Role |
|--------|------|
| B | Button |
| T | Text field / text area / search / combo box |
| S | Static text / label |
| I | Image |
| C | Checkbox |
| R | Radio button |
| P | Pop-up / combo box |
| SL | Slider |
| L | Link |
| M | Menu item / menu bar item |
| TB | Tab |
| O | OCR text element |
| E | Other |

## JSON Mode

All commands support `--json`:

```json
{"snapshot":"a1b2c3d4","app":"firefox","screenshot":"/tmp/steer/a1b2c3d4.png","count":141,"elements":[...]}
{"action":"click","x":450,"y":320,"label":"B3 \"Submit\"","ok":true}
{"action":"type","text":"hello","ok":true}
```

## Known Limitations

- **Wayland** is not supported — X11 is required
- **Accessibility trees** depend on AT-SPI support — many apps have limited trees
- **Electron apps** (VS Code, Slack, Discord) have minimal accessibility — use OCR
- Element IDs are positional per-snapshot, not persistent across snapshots

## Architecture

```
steer (Click CLI)
  ├── see        → screen_capture + accessibility + element_store
  ├── click      → element_store.resolve + mouse_control
  ├── type       → element_store.resolve + keyboard + mouse_control
  ├── hotkey     → keyboard (xdotool)
  ├── scroll     → mouse_control (xdotool)
  ├── drag       → mouse_control (xdotool)
  ├── apps       → app_control (wmctrl)
  ├── screens    → screen_capture (xrandr)
  ├── window     → window_control (wmctrl + xdotool)
  ├── ocr        → ocr (tesseract)
  ├── focus      → accessibility (AT-SPI)
  ├── find       → element_store
  ├── clipboard  → clipboard_control (xclip)
  └── wait       → app_control + accessibility
```

## License

MIT
