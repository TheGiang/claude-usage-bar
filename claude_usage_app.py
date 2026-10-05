#!/usr/bin/env python3
"""
Claude Usage Bar — hiển thị % usage session (5h) của Claude ngay trên
menu bar (macOS) / system tray (Linux, Windows).

Một codebase, tự chọn giao diện theo hệ điều hành:
  - macOS  -> rumps  (chữ trên menu bar)
  - khác   -> pystray (icon tray + tooltip + menu chuột phải)

Số liệu lấy từ claude_usage_core.fetch_usage().
"""

import datetime as dt
import sys
import threading

import claude_usage_core as core

POLL_SECONDS = 30  # nhịp tự làm mới


def _now():
    return dt.datetime.now().strftime("%H:%M:%S")


# ============================================================= macOS (rumps) ====

def run_macos():
    import rumps

    class App(rumps.App):
        def __init__(self):
            super().__init__("Claude", title="⋯", quit_button=None)
            self._have_data = False
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
            self.timer = rumps.Timer(lambda _: self.refresh_async(), POLL_SECONDS)
            self.timer.start()
            self.refresh_async()

        def on_refresh(self, _):
            self.title = "⟳"
            self.refresh_async()

        def refresh_async(self):
            threading.Thread(target=self._refresh, daemon=True).start()

        def _refresh(self):
            u = core.fetch_usage()
            if not u["ok"]:
                # Giữ nguyên số tốt gần nhất, chỉ báo lỗi nhẹ ở dòng trạng thái
                if self._have_data:
                    self.m_updated.title = f"⚠ lỗi lúc {_now()} — đang giữ số cũ"
                else:
                    self.title = "⚠︎"
                    self.m_session.title = "Lỗi: " + u["error"]
                    self.m_updated.title = "Cập nhật: " + _now()
                return
            f, s = u["five"], u["seven"]
            self._have_data = True
            self.title = f"{core.glyph(f)} {f}%" if f is not None else "?"
            self.m_session.title = f"Session (5h): {f}%  ·  {u['five_reset']}"
            self.m_week.title = f"Tuần (7d): {s}%  ·  {u['seven_reset']}"
            self.m_updated.title = "Cập nhật: " + _now()

    App().run()


# ================================================= Linux / Windows (pystray) ====

# Màu icon theo mức đầy (0..4)
_LEVEL_COLORS = [
    (52, 168, 83),    # xanh lá
    (52, 168, 83),
    (251, 188, 4),    # vàng
    (244, 132, 20),   # cam
    (217, 48, 37),    # đỏ
]


def _make_image(pct):
    """Vẽ icon tray: nền bo tròn màu theo mức + số % ở giữa."""
    from PIL import Image, ImageDraw, ImageFont

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = _LEVEL_COLORS[core.level(pct)] if pct is not None else (120, 120, 120)
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=14, fill=color + (255,))

    text = "?" if pct is None else f"{int(round(pct))}"
    fsize = 34 if len(text) < 3 else 26
    font = None
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf",
                 "arial.ttf", "Helvetica.ttc", "segoeuib.ttf"):
        try:
            font = ImageFont.truetype(name, fsize)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    d.text(((size - (r - l)) / 2 - l, (size - (b - t)) / 2 - t), text,
           font=font, fill=(255, 255, 255, 255))
    return img


def run_tray():
    import pystray

    state = {"good": None, "note": ""}  # good = lần lấy thành công gần nhất

    def title_text():
        g = state["good"]
        if g is None:
            return "Claude Usage — " + (state["note"] or "đang tải…")
        return (f"Session 5h: {g['five']}%  {g['five_reset']}\n"
                f"Tuần 7d:   {g['seven']}%  {g['seven_reset']}\n"
                + (state["note"] or f"Cập nhật: {_now()}"))

    def menu_line(_):
        g = state["good"]
        if g is None:
            return "Lỗi: " + state["note"] if state["note"] else "Đang tải…"
        return f"Session 5h: {g['five']}%  ·  {g['five_reset']}"

    def menu_week(_):
        g = state["good"]
        return "" if g is None else f"Tuần 7d: {g['seven']}%  ·  {g['seven_reset']}"

    icon = pystray.Icon("claude-usage", _make_image(None), "Claude Usage")

    def refresh(_=None, __=None):
        u = core.fetch_usage()
        if u["ok"]:
            state["good"] = u
            state["note"] = f"Cập nhật: {_now()}"
        else:
            # giữ số cũ, chỉ ghi chú lỗi
            state["note"] = (f"⚠ lỗi lúc {_now()} — giữ số cũ"
                             if state["good"] else u["error"])
        pct = state["good"]["five"] if state["good"] else None
        icon.icon = _make_image(pct)
        icon.title = title_text()
        icon.menu = pystray.Menu(
            pystray.MenuItem(menu_line, None, enabled=False),
            pystray.MenuItem(menu_week, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Làm mới ngay", lambda i, it: refresh()),
            pystray.MenuItem("Thoát", lambda i, it: i.stop()),
        )

    def loop():
        import time
        while True:
            try:
                refresh()
            except Exception:
                pass
            time.sleep(POLL_SECONDS)

    threading.Thread(target=loop, daemon=True).start()
    icon.run()


# ============================================================================ ==

def main():
    if sys.platform == "darwin":
        run_macos()
    else:
        run_tray()


if __name__ == "__main__":
    main()
