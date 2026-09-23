#!/bin/bash
# Gỡ LaunchAgent tự khởi động của Claude Usage Bar.
set -e
LABEL="io.github.claude-usage-bar"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
pkill -f claude_usage_bar.py 2>/dev/null || true
echo "==> Đã gỡ $LABEL và tắt app."
