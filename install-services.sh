#!/usr/bin/env bash
# Linux Mini Agent — Systemd Service Installer
# Run: sudo ./install-services.sh
#
# Installs systemd services so the listen server and telegram bot
# auto-start on boot and restart on failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

# --- Require root ---

if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run with sudo: sudo ./install-services.sh"
fi

# --- Detect uv path ---

UV_PATH=$(command -v uv 2>/dev/null || echo "")
# Also check common locations
if [ -z "$UV_PATH" ]; then
    for candidate in /root/.local/bin/uv /home/*/.local/bin/uv /usr/local/bin/uv; do
        if [ -x "$candidate" ]; then
            UV_PATH="$candidate"
            break
        fi
    done
fi

if [ -z "$UV_PATH" ]; then
    fail "uv not found. Run ./install.sh first."
fi

# --- Detect home directory and user ---
# When run with sudo, SUDO_USER tells us the real user
if [ -n "${SUDO_USER:-}" ]; then
    HOME_DIR=$(eval echo "~$SUDO_USER")
    RUN_USER="$SUDO_USER"
else
    HOME_DIR="$HOME"
    RUN_USER="$(whoami)"
fi

info "Repo root: $REPO_ROOT"
info "uv path:   $UV_PATH"
info "Home dir:  $HOME_DIR"
info "Run as:    $RUN_USER"

# --- Check .env exists ---

if [ ! -f "$REPO_ROOT/.env" ]; then
    fail ".env file not found. Run ./install.sh first, then edit .env with your API keys."
fi

# --- Install services ---

for service in linux-agent-listen linux-agent-telegram; do
    template="$REPO_ROOT/systemd/${service}.service"
    target="/etc/systemd/system/${service}.service"

    if [ ! -f "$template" ]; then
        fail "Template not found: $template"
    fi

    info "Installing $service..."
    sed \
        -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
        -e "s|__UV_PATH__|$UV_PATH|g" \
        -e "s|__HOME_DIR__|$HOME_DIR|g" \
        -e "s|__USER__|$RUN_USER|g" \
        "$template" > "$target"

    ok "$service → $target"
done

# --- Reload and enable ---

systemctl daemon-reload
ok "systemd daemon reloaded"

systemctl enable linux-agent-listen
ok "linux-agent-listen enabled (will start on boot)"

# Only enable telegram if token is configured
if grep -q 'TELEGRAM_BOT_TOKEN=.' "$REPO_ROOT/.env" 2>/dev/null; then
    systemctl enable linux-agent-telegram
    ok "linux-agent-telegram enabled (will start on boot)"
else
    info "Skipping telegram auto-start — TELEGRAM_BOT_TOKEN not set in .env"
    info "To enable later: sudo systemctl enable --now linux-agent-telegram"
fi

echo ""
info "Services installed. Useful commands:"
echo ""
echo "  Start now:     sudo systemctl start linux-agent-listen"
echo "                 sudo systemctl start linux-agent-telegram"
echo ""
echo "  Check status:  sudo systemctl status linux-agent-listen"
echo "                 sudo systemctl status linux-agent-telegram"
echo ""
echo "  View logs:     journalctl -u linux-agent-listen -f"
echo "                 journalctl -u linux-agent-telegram -f"
echo ""
echo "  Stop:          sudo systemctl stop linux-agent-listen"
echo "                 sudo systemctl stop linux-agent-telegram"
echo ""
echo "  Disable:       sudo systemctl disable linux-agent-listen"
echo "                 sudo systemctl disable linux-agent-telegram"
echo ""
ok "Done! Services will auto-start on next reboot."
