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


def _pct(p):
    """% dạng số nguyên gọn (93.0 -> '93')."""
    return "?" if p is None else f"{int(round(p))}"


# U+FE0E = text variation selector: ép glyph tròn render đơn sắc, canh baseline
# đúng trên menu bar macOS (nếu không macOS hay vẽ nó thành emoji màu, lệch xuống).
_TEXT_VS = "︎"


# ============================================================= macOS (rumps) ====

def run_macos():
    import rumps

    class App(rumps.App):
        def __init__(self):
            super().__init__("Claude", title="⋯", quit_button=None)
            self._last = None          # số tốt gần nhất (dict từ fetch_usage)
            self._reset_abs = False    # False = "còn ..."  ·  True = "lúc HH:MM"
            # Bấm vào dòng Session/Tuần để đổi kiểu hiển thị giờ reset
            self.m_session = rumps.MenuItem("Session (5h): …", callback=self.on_toggle_reset)
            self.m_week = rumps.MenuItem("Tuần (7d): …", callback=self.on_toggle_reset)
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

        def on_toggle_reset(self, _):
            self._reset_abs = not self._reset_abs
            self._render_lines()

        def refresh_async(self):
            threading.Thread(target=self._refresh, daemon=True).start()

        def _reset_str(self, u, which):
            key = f"{which}_reset_abs" if self._reset_abs else f"{which}_reset"
            return u.get(key) or u.get(f"{which}_reset") or ""

        def _render_lines(self):
            """Vẽ lại 2 dòng Session/Tuần theo số gần nhất + kiểu giờ hiện tại."""
            u = self._last
            if not u:
                return
            self.m_session.title = f"Session (5h): {_pct(u['five'])}%  ·  {self._reset_str(u, 'five')}"
            self.m_week.title = f"Tuần (7d): {_pct(u['seven'])}%  ·  {self._reset_str(u, 'seven')}"

        def _refresh(self):
            u = core.fetch_usage()
            if not u["ok"]:
                # Giữ nguyên số tốt gần nhất, chỉ báo lỗi nhẹ ở dòng trạng thái
                if self._last:
                    self.m_updated.title = f"⚠ lỗi lúc {_now()} — đang giữ số cũ"
                else:
                    self.title = "⚠︎"
                    self.m_session.title = "Lỗi: " + u["error"]
                    self.m_updated.title = "Cập nhật: " + _now()
                return
            self._last = u
            f = u["five"]
            self.title = f"{core.glyph(f)}{_TEXT_VS} {_pct(f)}%" if f is not None else "?"
            self._render_lines()
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

    state = {"good": None, "note": "", "abs": False}  # abs: kiểu giờ reset

    def _reset_str(g, which):
        key = f"{which}_reset_abs" if state["abs"] else f"{which}_reset"
        return g.get(key) or g.get(f"{which}_reset") or ""

    def title_text():
        g = state["good"]
        if g is None:
            return "Claude Usage — " + (state["note"] or "đang tải…")
        return (f"Session 5h: {_pct(g['five'])}%  {_reset_str(g, 'five')}\n"
                f"Tuần 7d:   {_pct(g['seven'])}%  {_reset_str(g, 'seven')}\n"
                + (state["note"] or f"Cập nhật: {_now()}"))

    def menu_line(_):
        g = state["good"]
        if g is None:
            return "Lỗi: " + state["note"] if state["note"] else "Đang tải…"
        return f"Session 5h: {_pct(g['five'])}%  ·  {_reset_str(g, 'five')}"

    def menu_week(_):
        g = state["good"]
        return "" if g is None else f"Tuần 7d: {_pct(g['seven'])}%  ·  {_reset_str(g, 'seven')}"

    icon = pystray.Icon("claude-usage", _make_image(None), "Claude Usage")

    def toggle_reset(_=None, __=None):
        state["abs"] = not state["abs"]
        refresh(skip_fetch=True)

    def refresh(_=None, __=None, skip_fetch=False):
        if not skip_fetch:
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
            # Bấm 2 dòng này để đổi kiểu giờ reset ("còn ..." ↔ "lúc HH:MM")
            pystray.MenuItem(menu_line, toggle_reset),
            pystray.MenuItem(menu_week, toggle_reset),
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
