#!/usr/bin/env python3
"""
Phần lõi (đa nền tảng) của Claude Usage Bar: đọc cookie đăng nhập claude.ai
từ trình duyệt, tự tìm org, gọi endpoint usage và trả kết quả đã format.

Không phụ thuộc GUI -> dùng chung cho bản macOS (rumps) và bản tray (pystray).
"""

import datetime as dt
import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://claude.ai"
CONFIG_PATH = (os.environ.get("CLAUDE_USAGE_CONFIG")
               or os.path.expanduser("~/.config/claude-usage/config.json"))

DEFAULT_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# Các trình duyệt sẽ thử đọc cookie (theo thứ tự). Ép 1 cái qua config
# {"browser": "brave"} hoặc biến môi trường CLAUDE_USAGE_BROWSER=brave.
BROWSERS = ["chrome", "brave", "edge", "chromium", "vivaldi", "opera", "firefox", "safari"]

# Glyph tròn phản ánh mức đầy
FILL_GLYPHS = ["○", "◔", "◑", "◕", "●"]


def level(pct):
    """0..4 theo mức % (dùng chọn glyph / màu icon)."""
    if pct is None:
        return 0
    return min(len(FILL_GLYPHS) - 1, int(pct) // 25)


def glyph(pct):
    if pct is None:
        return "…"
    return FILL_GLYPHS[level(pct)]


# --------------------------------------------------------------- auth/cookies ----

def _load_config():
    try:
        # utf-8-sig: chấp nhận file có BOM (Notepad / PowerShell hay thêm) và luôn đọc UTF-8
        with open(CONFIG_PATH, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def save_session_key(raw):
    """
    Lưu sessionKey người dùng dán vào config.json (giữ nguyên các mục khác) và trả về đường dẫn file.
    Chấp nhận dán cả dạng 'sessionKey=...; ...' hoặc có dấu nháy.
    """
    global _ORG_CACHE
    key = (raw or "").strip().strip("\"'")
    if key.lower().startswith("sessionkey="):
        key = key.split("=", 1)[1]
    key = key.split(";")[0].strip()
    if not key:
        raise ValueError("sessionKey rỗng")

    cfg = _load_config()
    cfg["sessionKey"] = key
    cfg.pop("cookie", None)      # 'cookie' được ưu tiên hơn sessionKey -> bỏ để khoá mới có hiệu lực
    cfg.pop("user_agent", None)  # UA cũ thuộc về phiên đăng nhập trước
    _write_config(cfg)
    _ORG_CACHE = None
    return CONFIG_PATH


def save_login(cookie_header, user_agent=None):
    """Lưu phiên đăng nhập lấy từ cửa sổ đăng nhập của app: toàn bộ cookie claude.ai + UA."""
    global _ORG_CACHE
    cfg = _load_config()
    cfg["cookie"] = cookie_header
    if user_agent:
        cfg["user_agent"] = user_agent
    cfg.pop("sessionKey", None)  # tránh nhầm với khoá dán tay cũ
    _write_config(cfg)
    _ORG_CACHE = None
    return CONFIG_PATH


def get_setting(key, default=None):
    return _load_config().get(key, default)


def update_config(**values):
    """Gộp các cài đặt (vd widget=True, widget_pos=[x, y]) vào config.json, giữ nguyên mục khác."""
    cfg = _load_config()
    cfg.update(values)
    _write_config(cfg)


def _write_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG_PATH, 0o600)  # trên Windows gần như không có tác dụng, vô hại
    except OSError:
        pass


def _import_browser_cookie3():
    """
    Import browser_cookie3 ngay cả khi không có `lz4`.

    browser_cookie3 `import lz4.block` ở đầu file, nhưng chỉ dùng nó để đọc cookie
    session của Firefox. lz4 chưa có wheel cho Python mới (vd 3.15 trên Windows) và
    phải biên dịch C, nên khi thiếu ta nạp một module giả: Chrome/Edge/Brave/Safari
    chạy bình thường, riêng cookie session Firefox bị bỏ qua.
    """
    try:
        import lz4.block  # noqa: F401
    except Exception:
        import sys
        import types

        def _unavailable(*_a, **_k):
            raise RuntimeError("lz4 không khả dụng")

        block = types.ModuleType("lz4.block")
        block.decompress = _unavailable
        pkg = types.ModuleType("lz4")
        pkg.block = block
        sys.modules["lz4"], sys.modules["lz4.block"] = pkg, block

    import browser_cookie3
    return browser_cookie3


def _cookie_header():
    """(cookie_header_string, source). Ưu tiên config; sau đó tự đọc từ trình duyệt."""
    cfg = _load_config()
    if cfg.get("cookie"):
        return cfg["cookie"], "config.cookie"
    if cfg.get("sessionKey"):
        return f"sessionKey={cfg['sessionKey']}", "config.sessionKey"

    browser_cookie3 = _import_browser_cookie3()

    pref = cfg.get("browser") or os.environ.get("CLAUDE_USAGE_BROWSER")
    names = [pref] + [b for b in BROWSERS if b != pref] if pref else BROWSERS

    errors = []
    for name in names:
        loader = getattr(browser_cookie3, name, None)
        if loader is None:
            continue
        try:
            jar = loader(domain_name="claude.ai")
            parts = [f"{c.name}={c.value}" for c in jar]
            if parts:
                return "; ".join(parts), name
        except Exception as e:
            errors.append(f"{name}: {str(e)[:60]}")

    # Chrome/Edge mới trên Windows mã hoá cookie kiểu App-Bound: chỉ đọc được khi chạy Admin.
    # Thông báo ngắn (tooltip tray Windows giới hạn ~128 ký tự) và nêu đúng lối ra.
    if any("admin" in e.lower() for e in errors):
        raise RuntimeError("Không đọc được cookie Chrome. "
                           "Chuột phải icon → 'Đăng nhập claude.ai…'")

    raise RuntimeError(
        "Không đọc được cookie claude.ai từ trình duyệt nào. "
        "Hãy đăng nhập claude.ai trên Chrome/Brave/Edge/Firefox, "
        "hoặc dán sessionKey vào ~/.config/claude-usage/config.json. "
        + (" [" + " | ".join(errors[:3]) + "]" if errors else "")
    )


def _http_get_json(path, cookie):
    req = urllib.request.Request(
        BASE + path,
        headers={
            "Cookie": cookie,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": BASE + "/settings/usage",
            "Origin": BASE,
            # Sau khi đăng nhập trong app, dùng đúng UA của trình duyệt đó (cookie Cloudflare gắn với UA)
            "User-Agent": _load_config().get("user_agent") or DEFAULT_UA,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


_ORG_CACHE = None  # nhớ org id để khỏi gọi /api/organizations mỗi lần (bớt cơ hội dính 403)


def _pick_org(cookie):
    global _ORG_CACHE
    cfg = _load_config()
    if cfg.get("org_id"):
        return cfg["org_id"]
    if _ORG_CACHE:
        return _ORG_CACHE
    orgs = _http_get_json("/api/organizations", cookie)
    for o in orgs:
        caps = o.get("capabilities") or []
        if "chat" in caps or "claude_pro" in caps or "claude_max" in caps:
            _ORG_CACHE = o["uuid"]
            return _ORG_CACHE
    _ORG_CACHE = orgs[0]["uuid"]
    return _ORG_CACHE


# --------------------------------------------------------------------- format ----

def fmt_reset(resets_at):
    """resets_at ISO -> 'còn 2h37m' / 'còn 3d10h' / '' nếu không có."""
    if not resets_at:
        return ""
    try:
        t = dt.datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        secs = int((t - dt.datetime.now(dt.timezone.utc)).total_seconds())
        if secs <= 0:
            return "sắp reset"
        h, m = secs // 3600, (secs % 3600) // 60
        if h >= 24:
            return f"còn {h // 24}d{h % 24}h"
        if h:
            return f"còn {h}h{m:02d}m"
        return f"còn {m}m"
    except Exception:
        return ""


def fmt_reset_long(resets_at):
    """resets_at ISO -> 'Còn 2 giờ 23 phút' / 'Còn khoảng 4 ngày 7 giờ' / '' nếu không có."""
    if not resets_at:
        return ""
    try:
        t = dt.datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        secs = int((t - dt.datetime.now(dt.timezone.utc)).total_seconds())
        if secs <= 0:
            return "Sắp đặt lại"
        h, m = secs // 3600, (secs % 3600) // 60
        if h >= 24:
            d, h = divmod(h, 24)
            return f"Còn khoảng {d} ngày" + (f" {h} giờ" if h else "")
        if h:
            return f"Còn {h} giờ" + (f" {m} phút" if m else "")
        return f"Còn {max(m, 1)} phút"
    except Exception:
        return ""


def fmt_reset_abs(resets_at):
    """resets_at ISO -> giờ reset cụ thể theo giờ máy: 'lúc 21:19' / 'lúc 21:19 11/10'."""
    if not resets_at:
        return ""
    try:
        t = dt.datetime.fromisoformat(resets_at.replace("Z", "+00:00")).astimezone()
        now = dt.datetime.now().astimezone()
        if t.date() == now.date():
            return "lúc " + t.strftime("%H:%M")
        return "lúc " + t.strftime("%H:%M %d/%m")
    except Exception:
        return ""


# Mã lỗi tạm thời (Cloudflare/claude.ai thỉnh thoảng trả về) -> cứ thử lại
_RETRYABLE = {403, 408, 429, 500, 502, 503, 504}


def _fetch_once():
    global _ORG_CACHE
    cookie, _src = _cookie_header()
    try:
        org = _pick_org(cookie)
        return _http_get_json(f"/api/organizations/{org}/usage", cookie)
    except urllib.error.HTTPError as e:
        # Org cache có thể sai -> xoá để lần sau dò lại
        if e.code in (403, 404):
            _ORG_CACHE = None
        raise


def fetch_usage(retries=4, backoff=1.2):
    """
    Trả về dict: ok, five, five_reset, seven, seven_reset, error.
    Tự retry khi gặp lỗi tạm thời (403/429/5xx...) giống như bấm "Làm mới".
    """
    last = "lỗi không rõ"
    for attempt in range(retries):
        try:
            data = _fetch_once()
            five = data.get("five_hour") or {}
            seven = data.get("seven_day") or {}
            return {
                "ok": True,
                "error": None,
                "five": five.get("utilization"),
                "five_reset": fmt_reset(five.get("resets_at")),
                "five_reset_abs": fmt_reset_abs(five.get("resets_at")),
                "five_reset_long": fmt_reset_long(five.get("resets_at")),
                "seven": seven.get("utilization"),
                "seven_reset": fmt_reset(seven.get("resets_at")),
                "seven_reset_abs": fmt_reset_abs(seven.get("resets_at")),
                "seven_reset_long": fmt_reset_long(seven.get("resets_at")),
            }
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} (đăng nhập lại claude.ai?)"
            retryable = e.code in _RETRYABLE
        except Exception as e:
            last = str(e)[:120]
            retryable = True  # lỗi mạng tạm thời

        if attempt < retries - 1 and retryable:
            time.sleep(backoff * (attempt + 1))  # 1.2s, 2.4s, 3.6s...
            continue
        break

    return {"ok": False, "error": last}


# ----------------------------------------------------------- startup/autostart ----

def get_startup_status():
    """Kiểm tra xem ứng dụng đã bật tự khởi động cùng máy tính chưa."""
    import sys
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return False
        lnk = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Claude Usage Bar.lnk")
        return os.path.isfile(lnk)
    elif sys.platform == "darwin":
        plist = os.path.expanduser("~/Library/LaunchAgents/io.github.claude-usage-bar.plist")
        return os.path.isfile(plist)
    elif sys.platform.startswith("linux"):
        desktop = os.path.expanduser("~/.config/autostart/io.github.claude-usage-bar.desktop")
        return os.path.isfile(desktop)
    return False


def set_startup(enable=True):
    """Bật hoặc tắt tự khởi động cùng hệ thống. Trả về bool trạng thái sau khi cập nhật."""
    import subprocess
    import sys
    root_dir = os.path.dirname(os.path.abspath(__file__))

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return False
        lnk = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Claude Usage Bar.lnk")
        if enable:
            run_bat = os.path.join(root_dir, "run.bat")
            if not os.path.isfile(run_bat):
                return False
            ps_cmd = (
                f"$ws = New-Object -ComObject WScript.Shell; "
                f"$s = $ws.CreateShortcut('{lnk}'); "
                f"$s.TargetPath = '{run_bat}'; "
                f"$s.WorkingDirectory = '{root_dir}'; "
                f"$s.WindowStyle = 7; "
                f"$s.Description = 'Claude Usage Bar Startup'; "
                f"$s.Save()"
            )
            subprocess.call(["powershell", "-NoProfile", "-Command", ps_cmd],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            if os.path.isfile(lnk):
                try:
                    os.remove(lnk)
                except OSError:
                    pass
        return get_startup_status()
    else:
        script = "install-startup.sh" if enable else "uninstall-startup.sh"
        script_path = os.path.join(root_dir, "scripts", script)
        if os.path.isfile(script_path):
            subprocess.call(["bash", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return get_startup_status()


def toggle_startup():
    """Đảo trạng thái tự khởi động. Trả về trạng thái mới."""
    cur = get_startup_status()
    return set_startup(not cur)


if __name__ == "__main__":  # test nhanh: python3 claude_usage_core.py
    u = fetch_usage()
    if u["ok"]:
        print(f"Session 5h: {u['five']}%  {u['five_reset']}")
        print(f"Week    7d: {u['seven']}%  {u['seven_reset']}")
    else:
        print("Lỗi:", u["error"])
