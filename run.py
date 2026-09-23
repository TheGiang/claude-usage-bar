#!/usr/bin/env python3
"""
Bootstrap đa nền tảng cho Claude Usage Bar (macOS / Linux / Windows).

Chạy:
    python run.py            # hoặc python3 run.py
Nó sẽ: (Linux) cài gói hệ thống cho tray -> tạo virtualenv -> cài deps -> chạy app.

Cờ:
    --reinstall   cài lại dependencies
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(ROOT, ".venv")
IS_WIN = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"

VENV_PY = os.path.join(VENV, "Scripts", "python.exe") if IS_WIN else os.path.join(VENV, "bin", "python3")


def sh(cmd, **kw):
    print("   $", " ".join(cmd))
    return subprocess.call(cmd, **kw)


def _sudo():
    if not IS_WIN and os.geteuid() != 0 and shutil.which("sudo"):
        return ["sudo"]
    return []


def ensure_linux_system_deps():
    """Cài PyGObject + GTK3 + AppIndicator (chỉ khi 'gi' chưa có)."""
    try:
        subprocess.check_call([sys.executable, "-c", "import gi"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return  # đã có
    except Exception:
        pass

    print("==> Cài gói hệ thống cho system tray...")
    s = _sudo()
    if shutil.which("apt-get"):
        sh(s + ["apt-get", "update", "-y"])
        base = ["apt-get", "install", "-y", "python3-venv", "python3-gi", "gir1.2-gtk-3.0"]
        if sh(s + base + ["gir1.2-ayatanaappindicator3-0.1"]) != 0:
            sh(s + base + ["gir1.2-appindicator3-0.1"])
    elif shutil.which("dnf"):
        sh(s + ["dnf", "install", "-y", "python3-gobject", "gtk3", "libappindicator-gtk3"])
    elif shutil.which("pacman"):
        sh(s + ["pacman", "-S", "--needed", "--noconfirm",
                "python-gobject", "gtk3", "libappindicator-gtk3"])
    else:
        print("⚠️  Không nhận ra trình quản lý gói — hãy tự cài PyGObject + GTK3 + AppIndicator.")


def ensure_venv():
    fresh = not os.path.exists(VENV_PY)
    if fresh:
        print("==> Tạo virtualenv...")
        args = [sys.executable, "-m", "venv"]
        if IS_LINUX:  # để venv thấy 'gi' của hệ thống
            args.append("--system-site-packages")
        args.append(VENV)
        if sh(args) != 0:
            sys.exit("❌ Tạo venv thất bại. Trên Debian/Ubuntu cần: sudo apt-get install python3-venv")
    return fresh


def install_deps():
    print("==> Cài dependencies Python...")
    sh([VENV_PY, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    sh([VENV_PY, "-m", "pip", "install", "-q", "-r", os.path.join(ROOT, "requirements.txt")])


def main():
    if shutil.which(sys.executable) is None and sys.executable is None:
        sys.exit("❌ Không tìm thấy Python 3.")

    if IS_LINUX:
        ensure_linux_system_deps()

    fresh = ensure_venv()
    if fresh or "--reinstall" in sys.argv:
        install_deps()

    if IS_LINUX and (os.environ.get("XDG_CURRENT_DESKTOP", "")).lower().find("gnome") >= 0:
        print("ℹ️  GNOME: nếu không thấy icon tray, cài extension 'AppIndicator Support':")
        print("   https://extensions.gnome.org/extension/615/appindicator-support/")

    print("==> Khởi động Claude Usage Bar")
    sys.stdout.flush()
    app = os.path.join(ROOT, "claude_usage_app.py")
    if IS_WIN:
        sys.exit(subprocess.call([VENV_PY, app]))
    else:
        os.execv(VENV_PY, [VENV_PY, app])


if __name__ == "__main__":
    main()
