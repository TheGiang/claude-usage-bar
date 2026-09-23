#!/usr/bin/env python3
"""
Claude Usage Bar — hiển thị % usage session (5h) của Claude trên menu bar macOS.

Dữ liệu lấy từ đúng endpoint mà trang claude.ai/settings/usage gọi:
    GET https://claude.ai/api/organizations/{org_id}/usage
    -> { "five_hour": {"utilization": N, "resets_at": ...},
         "seven_day": {"utilization": N, "resets_at": ...}, ... }

Auth: tự đọc cookie đăng nhập claude.ai từ trình duyệt của bạn
(Chrome/Brave/Edge/Chromium/Vivaldi/Opera/Firefox/Safari) qua browser_cookie3.
"""

import datetime as dt
import json
import os
import threading
import urllib.request
import urllib.error

import rumps

# ------------------------------------------------------------------ config ----

BASE = "https://claude.ai"
POLL_SECONDS = 30          # nhịp tự làm mới
CONFIG_PATH = os.path.expanduser("~/.config/claude-usage/config.json")

# Glyph tròn phản ánh mức đầy (dùng cho session 5h)
FILL_GLYPHS = ["○", "◔", "◑", "◕", "●"]


def _glyph(pct):
    if pct is None:
        return "…"
    return FILL_GLYPHS[min(len(FILL_GLYPHS) - 1, int(pct) // 25)]


# --------------------------------------------------------------- auth/cookies ----

def _load_config():
    """Config tuỳ chọn: {"sessionKey": "...", "org_id": "...", "cookie": "..."}."""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


# Các trình duyệt sẽ thử đọc cookie (theo thứ tự). Có thể ép 1 cái qua config
# {"browser": "brave"} hoặc biến môi trường CLAUDE_USAGE_BROWSER=brave.
BROWSERS = ["chrome", "brave", "edge", "chromium", "vivaldi", "opera", "firefox", "safari"]


def _cookie_header():
    """
    Trả về (cookie_header_string, source).
    Ưu tiên config thủ công; nếu không có thì tự đọc cookie claude.ai từ trình duyệt.
    """
    cfg = _load_config()
    if cfg.get("cookie"):
        return cfg["cookie"], "config.cookie"
    if cfg.get("sessionKey"):
        return f"sessionKey={cfg['sessionKey']}", "config.sessionKey"

    import browser_cookie3

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
        except Exception as e:  # trình duyệt chưa cài / không đọc được -> thử cái kế
            errors.append(f"{name}: {str(e)[:60]}")

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
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _pick_org(cookie):
    cfg = _load_config()
    if cfg.get("org_id"):
        return cfg["org_id"]
    orgs = _http_get_json("/api/organizations", cookie)
    # Chọn org của gói Claude (có capability 'chat'), tránh org 'api'
    for o in orgs:
        caps = o.get("capabilities") or []
        if "chat" in caps or "claude_pro" in caps or "claude_max" in caps:
            return o["uuid"]
    return orgs[0]["uuid"]  # fallback


# --------------------------------------------------------------------- format ----

def _fmt_reset(resets_at):
    """resets_at ISO -> 'còn 2h37m' hoặc '' nếu không có."""
    if not resets_at:
        return ""
    try:
        t = dt.datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        delta = t - now
        secs = int(delta.total_seconds())
        if secs <= 0:
            return "sắp reset"
        h, m = secs // 3600, (secs % 3600) // 60
        if h >= 24:
            d = h // 24
            return f"còn {d}n{h % 24}h"
        if h:
            return f"còn {h}h{m:02d}m"
        return f"còn {m}m"
    except Exception:
        return ""


# ------------------------------------------------------------------------ app ----

class ClaudeUsageBar(rumps.App):
    def __init__(self):
        super().__init__("Claude", title="⋯", quit_button=None)
        self.m_session = rumps.MenuItem("Session (5h): …")
        self.m_week = rumps.MenuItem("Tuần (7d): …")
        self.m_updated = rumps.MenuItem("Chưa cập nhật")
        self.menu = [
            self.m_session,
            self.m_week,
            None,
            self.m_updated,
            rumps.MenuItem("Làm mới ngay", callback=self.on_refresh),
            None,
            rumps.MenuItem("Thoát", callback=rumps.quit_application),
        ]
        self.timer = rumps.Timer(self.on_tick, POLL_SECONDS)
        self.timer.start()
        self.refresh_async()  # lần đầu ngay khi mở

    # -- events --
    def on_tick(self, _):
        self.refresh_async()

    def on_refresh(self, _):
        self.title = "⟳"
        self.refresh_async()

    def refresh_async(self):
        threading.Thread(target=self._refresh, daemon=True).start()

    # -- core --
    def _refresh(self):
        try:
            cookie, _src = _cookie_header()
            org = _pick_org(cookie)
            data = _http_get_json(f"/api/organizations/{org}/usage", cookie)
        except urllib.error.HTTPError as e:
            self._set_error(f"HTTP {e.code} (đăng nhập lại claude.ai?)")
            return
        except Exception as e:
            self._set_error(str(e)[:80])
            return

        five = (data.get("five_hour") or {})
        seven = (data.get("seven_day") or {})

        f_pct = five.get("utilization")
        s_pct = seven.get("utilization")

        # Cập nhật UI trên main thread không bắt buộc với rumps title/menu — an toàn set trực tiếp
        self.title = f"{_glyph(f_pct)} {f_pct}%" if f_pct is not None else "?"
        self.m_session.title = (
            f"Session (5h): {f_pct}%  ·  {_fmt_reset(five.get('resets_at'))}"
        )
        self.m_week.title = (
            f"Tuần (7d): {s_pct}%  ·  {_fmt_reset(seven.get('resets_at'))}"
        )
        self.m_updated.title = "Cập nhật: " + dt.datetime.now().strftime("%H:%M:%S")

    def _set_error(self, msg):
        self.title = "⚠︎"
        self.m_session.title = "Lỗi: " + msg
        self.m_updated.title = "Cập nhật: " + dt.datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    ClaudeUsageBar().run()
