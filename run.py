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

# Khi stdout bị chuyển hướng, console Windows có thể không in được tiếng Việt/emoji -> đừng crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
IS_WIN = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"

# Windows dùng venv riêng: thư mục dự án có thể dùng chung giữa nhiều OS (ổ ngoài, đồng bộ),
# mà pyvenv.cfg / bin / Scripts của venv không dùng chung được giữa các OS.
VENV = os.path.join(ROOT, ".venv-win" if IS_WIN else ".venv")
VENV_PY = os.path.join(VENV, "Scripts", "python.exe") if IS_WIN else os.path.join(VENV, "bin", "python3")

# Module bắt buộc phải import được thì app mới chạy (kiểm tra bằng find_spec, không import thật)
REQUIRED = (["rumps", "browser_cookie3"] if IS_MAC
            else ["pystray", "PIL", "websocket", "browser_cookie3"])

# Phụ thuộc của browser-cookie3 TRỪ lz4. lz4 chưa có wheel cho Python mới (vd 3.15) nên pip
# phải biên dịch C (cần MSVC) và thất bại; lz4 chỉ phục vụ cookie session Firefox,
# claude_usage_core có shim thay thế khi thiếu.
BC3_DEPS_NO_LZ4 = [
    "pycryptodomex",
    'shadowcopy; platform_system == "Windows"',
    'jeepney; sys_platform == "linux"',
]


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
    if not fresh and subprocess.call([VENV_PY, "-c", "pass"], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL) != 0:
        # venv tạo bởi Python khác (máy / tài khoản Windows khác) nên không chạy được -> tạo lại
        print("==> venv cũ không dùng được, tạo lại...")
        shutil.rmtree(VENV, ignore_errors=True)
        fresh = True
    if fresh:
        print("==> Tạo virtualenv...")
        args = [sys.executable, "-m", "venv"]
        if IS_LINUX:  # để venv thấy 'gi' của hệ thống
            args.append("--system-site-packages")
        args.append(VENV)
        if sh(args) != 0:
            sys.exit("❌ Tạo venv thất bại. Trên Debian/Ubuntu cần: sudo apt-get install python3-venv")
    return fresh


def pip_install(*args):
    return sh([VENV_PY, "-m", "pip", "install", *args])


def deps_ok():
    """Mọi module cần thiết đã có trong venv chưa?"""
    code = ("import importlib.util as u, sys; "
            f"sys.exit(any(u.find_spec(m) is None for m in {REQUIRED!r}))")
    return subprocess.call([VENV_PY, "-c", code]) == 0


def install_deps():
    """Cài dependencies; trả về True nếu app đủ thư viện để chạy."""
    print("==> Cài dependencies Python...")
    pip_install("-q", "--upgrade", "pip")
    req = os.path.join(ROOT, "requirements.txt")

    # --only-binary=lz4: nếu không có wheel thì thất bại ngay, khỏi mất công biên dịch C (cần MSVC)
    if pip_install("--only-binary=lz4", "-r", req) == 0 and deps_ok():
        return True

    print("⚠️  Không có bản lz4 dựng sẵn cho Python này — cài lại không cần lz4 "
          "(chỉ ảnh hưởng cookie session của Firefox)...")
    with open(req, encoding="utf-8") as f:
        lines = [l.strip() for l in f]
    others = [l for l in lines
              if l and not l.startswith("#") and not l.lower().startswith("browser-cookie3")]
    ok = (pip_install(*others) == 0
          and pip_install("--no-deps", "browser-cookie3") == 0
          and pip_install(*BC3_DEPS_NO_LZ4) == 0)
    return ok and deps_ok()


def main():
    if shutil.which(sys.executable) is None and sys.executable is None:
        sys.exit("❌ Không tìm thấy Python 3.")

    if IS_LINUX:
        ensure_linux_system_deps()

    fresh = ensure_venv()
    # Cài khi venv mới, khi bị yêu cầu, hoặc khi venv thiếu thư viện (lần cài trước dở dang)
    if fresh or "--reinstall" in sys.argv or not deps_ok():
        if not install_deps():
            sys.exit("❌ Không cài được dependencies — xem lỗi pip ở phía trên.\n"
                     f"   Thử lại: xoá thư mục {os.path.basename(VENV)} rồi chạy lại.")

    if IS_LINUX and (os.environ.get("XDG_CURRENT_DESKTOP", "")).lower().find("gnome") >= 0:
        print("ℹ️  GNOME: nếu không thấy icon tray, cài extension 'AppIndicator Support':")
        print("   https://extensions.gnome.org/extension/615/appindicator-support/")

    print("==> Khởi động Claude Usage Bar")
    sys.stdout.flush()
    app = os.path.join(ROOT, "claude_usage_app.py")
    if IS_WIN:
        launch_detached_windows(app)
    else:
        os.execv(VENV_PY, [VENV_PY, app])


def launch_detached_windows(app):
    """Chạy app bằng pythonw (không cửa sổ cmd), tách khỏi console để đóng cmd không tắt app."""
    import tempfile
    import time

    pythonw = os.path.join(VENV, "Scripts", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = VENV_PY
    log_path = os.path.join(tempfile.gettempdir(), "claude-usage-bar.log")
    log = open(log_path, "a", encoding="utf-8")  # pythonw không có console -> ghi lỗi ra file
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
             | subprocess.CREATE_NO_WINDOW)
    subprocess.Popen([pythonw, app], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                     creationflags=flags, close_fds=True)
    print("✅ Đã chạy nền. Tìm icon Claude Usage ở khay hệ thống (góc phải taskbar,")
    print("   nếu không thấy hãy bấm mũi tên ^ để mở các icon ẩn).")
    print(f"   Log: {log_path}")
    sys.stdout.flush()
    time.sleep(5)  # để kịp đọc thông báo trước khi cửa sổ tự đóng


if __name__ == "__main__":
    main()
