#!/usr/bin/env bash
# Gỡ tự-khởi-động và tắt app (macOS + Linux).
set -e
OS="$(uname -s 2>/dev/null || echo unknown)"
LABEL="io.github.claude-usage-bar"

if [ "$OS" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
else
  rm -f "$HOME/.config/autostart/$LABEL.desktop"
fi

pkill -f claude_usage_app.py 2>/dev/null || true
echo "==> Đã gỡ tự-khởi-động và tắt app."
