#!/usr/bin/env python3
"""
Đăng nhập claude.ai ngay từ app (dùng cho Windows/Linux, nơi không đọc được cookie
Chrome thường vì trình duyệt mã hoá chúng).

Cách hoạt động:
  1. Mở Chrome/Edge/Brave với một profile TẠM do app tạo (tách hẳn profile thật của bạn)
     và bật cổng debug cục bộ (127.0.0.1) cho chính cửa sổ đó.
  2. Bạn tự đăng nhập claude.ai trong cửa sổ đó (Google, email...). App không thấy mật khẩu.
  3. Khi cookie `sessionKey` xuất hiện, app lấy cookie claude.ai của phiên tạm này, lưu vào
     config.json, đóng cửa sổ và xoá profile tạm.

Mã thoát: 0 = đã đăng nhập & lưu | 2 = không tìm thấy trình duyệt | 3 = đóng cửa sổ/hết giờ.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import claude_usage_core as core

LOGIN_URL = "https://claude.ai/login"
TIMEOUT_SECONDS = 600
PORT_ENV = "CLAUDE_USAGE_LOGIN_PORT"  # cố định cổng (dùng khi test); mặc định chọn cổng trống


def find_browser():
    """Đường dẫn trình duyệt Chromium đầu tiên tìm thấy (ưu tiên Chrome), hoặc None."""
    cands = []
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [os.path.join(base, r"Google\Chrome\Application\chrome.exe"),
                          os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"),
                          os.path.join(base, r"BraveSoftware\Brave-Browser\Application\brave.exe")]
    elif sys.platform == "darwin":
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                     "microsoft-edge", "brave-browser"):
            p = shutil.which(name)
            if p:
                cands.append(p)
    return next((p for p in cands if os.path.exists(p)), None)


def _free_port():
    env = os.environ.get(PORT_ENV)
    if env:
        return int(env)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _browser_ws_url(port, proc, timeout=30):
    """Đợi trình duyệt mở cổng debug, trả về URL websocket cấp trình duyệt."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return None
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.loads(r.read().decode())["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    return None


class _Cdp:
    """Client Chrome DevTools Protocol tối giản qua websocket-client."""

    def __init__(self, url):
        import websocket
        self.ws = websocket.create_connection(url, timeout=10)
        self._id = 0

    def call(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                return msg.get("result", {})

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def _claude_cookies(cdp):
    cookies = cdp.call("Storage.getCookies").get("cookies", [])
    return [c for c in cookies if c.get("domain", "").lstrip(".").endswith("claude.ai")]


def main():
    exe = find_browser()
    if not exe:
        print("Không tìm thấy Chrome/Edge/Brave.", file=sys.stderr)
        return 2

    profile = tempfile.mkdtemp(prefix="claude-usage-login-")
    port = _free_port()
    proc = subprocess.Popen(
        [exe, f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", f"--app={LOGIN_URL}"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = None
    code = 3
    try:
        url = _browser_ws_url(port, proc)
        if not url:
            return 3
        cdp = _Cdp(url)
        user_agent = cdp.call("Browser.getVersion").get("userAgent")

        deadline = time.time() + TIMEOUT_SECONDS
        while time.time() < deadline and proc.poll() is None:
            cookies = _claude_cookies(cdp)
            key = next((c for c in cookies if c["name"] == "sessionKey" and len(c["value"]) > 20), None)
            if key:
                header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                core.save_login(header, user_agent)
                code = 0
                break
            time.sleep(1.5)
    except Exception as e:  # trình duyệt bị đóng giữa chừng, mất kết nối...
        print(f"Lỗi: {e}", file=sys.stderr)
    finally:
        if cdp:
            try:
                cdp.call("Browser.close")
            except Exception:
                pass
            cdp.close()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()
        _remove_profile(profile)  # profile tạm chứa phiên đăng nhập -> xoá
    return code


def _remove_profile(path, attempts=10):
    """Tiến trình con của trình duyệt có thể còn giữ file một lúc (Windows) -> thử lại."""
    for _ in range(attempts):
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            return
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
