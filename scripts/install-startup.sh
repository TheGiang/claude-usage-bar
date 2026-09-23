#!/usr/bin/env bash
# Cài tự-khởi-động khi đăng nhập: macOS (LaunchAgent) hoặc Linux (autostart .desktop).
# Tự dò đường dẫn repo & venv nên máy nào chạy cũng đúng.
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OS="$(uname -s 2>/dev/null || echo unknown)"
LABEL="io.github.claude-usage-bar"

# Đảm bảo venv + deps đã sẵn sàng
if [ ! -x "$REPO_DIR/.venv/bin/python3" ]; then
  echo "==> venv chưa có, chạy run.sh để cài trước..."
  ( cd "$REPO_DIR" && ./run.sh & sleep 1; pkill -f claude_usage_app.py 2>/dev/null || true )
fi
PYTHON="$REPO_DIR/.venv/bin/python3"

if [ "$OS" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$REPO_DIR/claude_usage_app.py</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/claude-usage-bar.log</string>
    <key>StandardErrorPath</key><string>/tmp/claude-usage-bar.log</string>
</dict>
</plist>
EOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "==> Đã cài LaunchAgent: $PLIST"

else  # Linux
  DESKTOP="$HOME/.config/autostart/$LABEL.desktop"
  mkdir -p "$HOME/.config/autostart"
  cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Bar
Exec=$PYTHON $REPO_DIR/claude_usage_app.py
X-GNOME-Autostart-enabled=true
EOF
  echo "==> Đã cài autostart: $DESKTOP"
  # chạy luôn ngay bây giờ
  ( "$PYTHON" "$REPO_DIR/claude_usage_app.py" >/tmp/claude-usage-bar.log 2>&1 & )
fi

echo "    Gỡ: ./scripts/uninstall-startup.sh"
