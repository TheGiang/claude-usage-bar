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
CONFIG_PATH = os.path.expanduser("~/.config/claude-usage/config.json")

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
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _cookie_header():
    """(cookie_header_string, source). Ưu tiên config; sau đó tự đọc từ trình duyệt."""
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
        except Exception as e:
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
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": BASE + "/settings/usage",
            "Origin": BASE,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
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
                "seven": seven.get("utilization"),
                "seven_reset": fmt_reset(seven.get("resets_at")),
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


if __name__ == "__main__":  # test nhanh: python3 claude_usage_core.py
    u = fetch_usage()
    if u["ok"]:
        print(f"Session 5h: {u['five']}%  {u['five_reset']}")
        print(f"Week    7d: {u['seven']}%  {u['seven_reset']}")
    else:
        print("Lỗi:", u["error"])
