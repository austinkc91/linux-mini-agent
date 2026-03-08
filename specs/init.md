# STEER BUILD PLAN

Claude Code agent: execute this top-to-bottom. Stop and report on any failure.

## PHASE 1: GENERATE PROJECT

```bash
cd ~/Projects
chmod +x setup.sh
./setup.sh
cd steer
```

Verify: find Sources/steer -name "*.swift" | wc -l should return 15

## PHASE 2: BUILD

```bash
swift build -c release 2>&1
```

Verify: Exit code 0. Binary at .build/release/steer

```bash
.build/release/steer --help
```

Verify: Version 0.1.0, 6 subcommands: see click type hotkey scroll apps

## PHASE 3: PERMISSIONS

Terminal needs Accessibility and Screen Recording in System Settings.
If not granted, see will return empty elements. Note it and continue.

## PHASE 4: TEST COMMANDS

### 4.1 apps list
```bash
.build/release/steer apps list
```
Expected: Table of running apps with PIDs

### 4.2 apps list json
```bash
.build/release/steer apps list --json
```
Expected: Valid JSON array with name, pid, bundleId, isActive

### 4.3 see
```bash
.build/release/steer see
```
Expected: snapshot ID, app name, screenshot path, element count
Verify: ls -la /tmp/steer/*.png

### 4.4 see json
```bash
.build/release/steer see --json
```
Expected: JSON with snapshot, app, screenshot, count, elements

### 4.5 see app target
```bash
.build/release/steer see --app Finder
```
Expected: Finder elements (always running)

### 4.6 click no args
```bash
.build/release/steer click 2>&1
```
Expected: Error, non-zero exit

### 4.7 click element
```bash
.build/release/steer click --on B1
```
Expected: Clicked with coordinates (skip if no elements from see)

### 4.8 click coordinates
```bash
.build/release/steer click --x 100 --y 100
```
Expected: Clicked (100, 100)

### 4.9 type text
```bash
.build/release/steer apps launch TextEdit
sleep 1
.build/release/steer type "hello from steer"
```
Expected: Text appears in TextEdit

### 4.10 hotkey
```bash
.build/release/steer hotkey cmd+a
.build/release/steer hotkey escape
```
Expected: Prints pressed for each

### 4.11 scroll
```bash
.build/release/steer scroll down 5
.build/release/steer scroll up 3
```
Expected: Confirmation messages

### 4.12 scroll bad input
```bash
.build/release/steer scroll diagonal 2>&1
```
Expected: Error, non-zero exit

## PHASE 5: INTEGRATION TEST

```bash
.build/release/steer apps launch "TextEdit"
sleep 2
.build/release/steer see --app TextEdit --json > /tmp/steer_test.json

SCREENSHOT=$(python3 -c "import json; print(json.load(open('/tmp/steer_test.json'))['screenshot'])")
ls -la "$SCREENSHOT"

FIRST_BUTTON=$(python3 -c "
import json
d = json.load(open('/tmp/steer_test.json'))
buttons = [e for e in d['elements'] if e['role'] == 'button']
print(buttons[0]['id'] if buttons else 'NONE')
")
echo "First button: $FIRST_BUTTON"
if [ "$FIRST_BUTTON" != "NONE" ]; then
    .build/release/steer click --on "$FIRST_BUTTON"
fi

.build/release/steer type "steer integration test"
.build/release/steer see --app TextEdit
```

## PHASE 6: REPORT

Summarize:
1. Build: Clean compile? Warnings? Binary size?
2. Permissions: Accessibility and Screen Recording granted?
3. Tests: Each of 12 tests pass/fail/skip
4. Integration: Did see-click-type-see complete?
5. Issues: Crashes, unexpected output
6. Fixes: Changes needed in setup.sh

## KNOWN ISSUES

- launchApplication deprecated warning expected
- Empty elements = permissions issue, not a bug
- AXValue force cast in axVal could crash on unexpected types
- JSON from see uses string interpolation, may break on app names with quotes
- Scroll direction follows macOS conventions not natural scrolling