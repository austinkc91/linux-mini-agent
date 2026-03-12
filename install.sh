#!/usr/bin/env bash
# Linux Mini Agent — Automated Installer
# Run: ./install.sh
#
# Installs system dependencies, Python environments, and verifies everything works.
# Requires sudo for apt packages. Safe to re-run (skips already-installed tools).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0
WARN=0

# --- Helpers ---

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[PASS]\033[0m  $*"; PASS=$((PASS + 1)); }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; FAIL=$((FAIL + 1)); }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; WARN=$((WARN + 1)); }
step()  { echo ""; echo -e "\033[1;37m--- $* ---\033[0m"; }

has() { command -v "$1" &>/dev/null; }

# --- Phase 1: System Info ---

step "System Info"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "OS: $PRETTY_NAME"
else
    info "OS: $(uname -s) $(uname -r)"
fi
info "Kernel: $(uname -r)"
info "Arch: $(uname -m)"

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    warn "No DISPLAY set — GUI tools (steer) require an X11 session"
fi

# --- Phase 2: Install System Packages ---

step "System Packages"

APT_PACKAGES=(
    tmux
    xdotool
    scrot
    tesseract-ocr
    wmctrl
    xclip
    x11-utils
    imagemagick
)

OPTIONAL_PACKAGES=(
    python3-gi
    gir1.2-atspi-2.0
)

missing=()
for pkg in "${APT_PACKAGES[@]}"; do
    if dpkg -s "$pkg" &>/dev/null; then
        info "$pkg: already installed"
    else
        missing+=("$pkg")
    fi
done

optional_missing=()
for pkg in "${OPTIONAL_PACKAGES[@]}"; do
    if dpkg -s "$pkg" &>/dev/null; then
        info "$pkg: already installed"
    else
        optional_missing+=("$pkg")
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    info "Installing: ${missing[*]}"
    sudo apt update -qq
    sudo apt install -y -qq "${missing[@]}"
fi

if [ ${#optional_missing[@]} -gt 0 ]; then
    info "Installing optional (AT-SPI accessibility): ${optional_missing[*]}"
    sudo apt install -y -qq "${optional_missing[@]}" 2>/dev/null || warn "Optional AT-SPI packages failed — accessibility trees won't work"
fi

# --- Phase 3: Install uv ---

step "Python Package Manager (uv)"

if has uv; then
    info "uv: $(uv --version)"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if has uv; then
        info "uv installed: $(uv --version)"
    else
        fail "uv installation failed"
    fi
fi

# --- Phase 4: Install just ---

step "Task Runner (just)"

if has just; then
    info "just: $(just --version)"
else
    info "Installing just..."
    if has cargo; then
        cargo install just
    elif has apt; then
        sudo apt install -y -qq just 2>/dev/null || {
            # just may not be in apt on older distros — try prebuilt
            curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to "$HOME/.local/bin"
        }
    fi
    if has just; then
        info "just installed: $(just --version)"
    else
        fail "just installation failed — install manually: https://github.com/casey/just"
    fi
fi

# --- Phase 5: Sync Python Apps ---

step "Python App Dependencies"

cd "$REPO_ROOT"

for app in steer drive listen direct telegram; do
    app_dir="$REPO_ROOT/apps/$app"
    if [ -f "$app_dir/pyproject.toml" ]; then
        info "Syncing $app..."
        (cd "$app_dir" && uv sync --quiet 2>&1) && info "$app: dependencies synced" || warn "$app: sync had warnings"
    else
        warn "$app: no pyproject.toml found"
    fi
done

# --- Phase 6: Create .env if missing ---

step "Environment Configuration"

if [ ! -f "$REPO_ROOT/.env" ]; then
    cp "$REPO_ROOT/.env.sample" "$REPO_ROOT/.env"
    chmod 600 "$REPO_ROOT/.env"
    info "Created .env from .env.sample (permissions: 600) — edit it to add your API keys and tokens"
else
    # Ensure existing .env has restrictive permissions (contains API keys)
    chmod 600 "$REPO_ROOT/.env"
    info ".env already exists (permissions secured)"
fi

# --- Phase 7: Verification ---

step "Verification"

# Check system tools
for tool in tmux xdotool scrot tesseract wmctrl xclip xrandr; do
    if has "$tool"; then
        ok "$tool"
    else
        fail "$tool not found"
    fi
done

# Check uv
if has uv; then
    ok "uv ($(uv --version 2>/dev/null || echo '?'))"
else
    fail "uv not found"
fi

# Check just
if has just; then
    ok "just ($(just --version 2>/dev/null || echo '?'))"
else
    fail "just not found"
fi

# Check steer
if (cd "$REPO_ROOT/apps/steer" && uv run python main.py --version) &>/dev/null; then
    ok "steer CLI"
else
    fail "steer CLI failed to run"
fi

# Check drive
if (cd "$REPO_ROOT/apps/drive" && uv run python main.py --version) &>/dev/null; then
    ok "drive CLI"
else
    fail "drive CLI failed to run"
fi

# Check listen (no --help flag; just verify imports work)
if (cd "$REPO_ROOT/apps/listen" && uv run python -c "import main; print('ok')") &>/dev/null; then
    ok "listen server"
else
    fail "listen server failed"
fi

# Check direct
if (cd "$REPO_ROOT/apps/direct" && uv run python main.py --help) &>/dev/null; then
    ok "direct CLI"
else
    fail "direct CLI failed"
fi

# Check telegram
if (cd "$REPO_ROOT/apps/telegram" && uv run python -c "import telegram; print('ok')") &>/dev/null; then
    ok "telegram bot dependencies"
else
    fail "telegram bot dependencies failed"
fi

# Check justfile
if (cd "$REPO_ROOT" && just --list) &>/dev/null; then
    ok "justfile recipes"
else
    fail "justfile failed"
fi

# Screenshot test (only if DISPLAY is set)
if [ -n "${DISPLAY:-}" ]; then
    screenshot_out=$(cd "$REPO_ROOT/apps/steer" && uv run python main.py see --json 2>/dev/null || echo "")
    if echo "$screenshot_out" | grep -q '"screenshot"'; then
        ok "steer screenshot (X11)"
    else
        fail "steer screenshot — check DISPLAY and scrot"
    fi
else
    warn "Skipping screenshot test — no DISPLAY set"
fi

# tmux test
if tmux new-session -d -s _install_test 2>/dev/null; then
    tmux kill-session -t _install_test 2>/dev/null
    ok "tmux sessions"
else
    fail "tmux session creation"
fi

# --- Report ---

step "Results"

TOTAL=$((PASS + FAIL))
echo ""
echo "  Passed: $PASS/$TOTAL"
if [ $FAIL -gt 0 ]; then
    echo "  Failed: $FAIL"
fi
if [ $WARN -gt 0 ]; then
    echo "  Warnings: $WARN"
fi
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "\033[1;32m✓ Installation complete! All checks passed.\033[0m"
    echo ""
    echo "  Next steps:"
    echo "    1. Edit .env with your API keys"
    echo "    2. just listen          — start the job server"
    echo "    3. just telegram        — start the Telegram bot (needs TELEGRAM_BOT_TOKEN)"
    echo "    4. just send \"prompt\"   — send a job"
    echo ""
else
    echo -e "\033[1;31m✗ $FAIL check(s) failed. Fix the issues above and re-run ./install.sh\033[0m"
    exit 1
fi
