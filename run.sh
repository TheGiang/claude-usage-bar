#!/usr/bin/env bash
# Wrapper cho macOS/Linux — gọi bootstrap Python đa nền tảng.
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" run.py "$@"
