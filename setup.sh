#!/usr/bin/env bash
# ─── YT TUI Player — Setup ────────────────────────────────────
# One-command setup for new machines.
# Tested on: fedora 44
# ───────────────────────────────────────────────────────────────
set -euo pipefail

CDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$CDIR"

R="\033[1;31m"; G="\033[1;32m"; Y="\033[1;33m"; B="\033[1;34m"; N="\033[0m"

info()  { echo -e "${B}[INFO]${N} $1"; }
ok()    { echo -e "${G}[OK]${N}   $1"; }
warn()  { echo -e "${Y}[WARN]${N} $1"; }
fail()  { echo -e "${R}[FAIL]${N} $1"; exit 1; }

# ── 1. Detect distro ──
if command -v dnf &>/dev/null; then
    PKG_MGR="dnf"; PKG_INSTALL="sudo dnf install -y"
elif command -v apt &>/dev/null; then
    PKG_MGR="apt"; PKG_INSTALL="sudo apt install -y"
elif command -v pacman &>/dev/null; then
    PKG_MGR="pacman"; PKG_INSTALL="sudo pacman -S --noconfirm"
elif command -v zypper &>/dev/null; then
    PKG_MGR="zypper"; PKG_INSTALL="sudo zypper install -y"
else
    fail "Package manager not detected."
fi

info "Detected: $PKG_MGR"

# ── 2. System deps ──
info "Installing system dependencies..."
if [ "$PKG_MGR" = "dnf" ]; then
    $PKG_INSTALL mpv yt-dlp python3-pip python3-devel gcc
elif [ "$PKG_MGR" = "apt" ]; then
    $PKG_INSTALL mpv yt-dlp python3-pip python3-dev python3-venv build-essential
elif [ "$PKG_MGR" = "pacman" ]; then
    $PKG_INSTALL mpv yt-dlp python-pip python-virtualenv base-devel
elif [ "$PKG_MGR" = "zypper" ]; then
    $PKG_INSTALL mpv yt-dlp python3-pip python3-devel python3-virtualenv gcc
fi

for cmd in mpv yt-dlp python3; do
    command -v "$cmd" &>/dev/null || warn "$cmd not found"
done
ok "System dependencies installed"

# ── 3. Python venv ──
info "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    ok "Created .venv"
else
    ok ".venv already exists"
fi

# ── 4. Python packages ──
info "Installing Python packages..."
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Python packages installed"

echo ""
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo -e "${G}  ✅ YT TUI Player — Setup Complete${N}"
echo -e "${G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${N}"
echo ""
echo "  Run:  ${B}./run.sh${N}"
echo ""
