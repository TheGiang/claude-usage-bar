#!/bin/bash
# Chạy Claude Usage Bar (tạo venv + cài deps lần đầu nếu cần)
cd "$(dirname "$0")" || exit 1
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi
exec ./.venv/bin/python3 claude_usage_bar.py
