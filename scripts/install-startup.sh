#!/bin/bash
# Cài LaunchAgent để Claude Usage Bar tự chạy khi đăng nhập macOS.
# Tự dò đường dẫn repo & venv nên máy nào chạy cũng đúng.
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="io.github.claude-usage-bar"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="$REPO_DIR/.venv/bin/python3"

# Tạo venv + cài deps nếu chưa có
if [ ! -x "$PYTHON" ]; then
  echo "==> Tạo venv và cài dependencies..."
  python3 -m venv "$REPO_DIR/.venv"
  "$REPO_DIR/.venv/bin/pip" install -q --upgrade pip
  "$REPO_DIR/.venv/bin/pip" install -q -r "$REPO_DIR/requirements.txt"
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$REPO_DIR/claude_usage_bar.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/claude-usage-bar.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/claude-usage-bar.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "==> Đã cài & khởi động: $PLIST"
echo "    Log: /tmp/claude-usage-bar.log"
echo "    Gỡ:  ./scripts/uninstall-startup.sh"
