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

# Session vượt ngưỡng này -> hiển thị đỏ cảnh báo
RED_AT = 80


# ============================================================= macOS (rumps) ====

def run_macos():
    import objc
    import rumps
    from AppKit import (NSView, NSTextField, NSClickGestureRecognizer, NSColor,
                        NSFont, NSAttributedString, NSForegroundColorAttributeName)
    from Foundation import NSObject, NSMakeRect

    # Đối tượng nhận click từ gesture recognizer (menu không đóng khi click trong view)
    class _Toggler(NSObject):
        def initWithCb_(self, cb):
            self = objc.super(_Toggler, self).init()
            if self is None:
                return None
            self._cb = cb
            return self

        def onClick_(self, _recognizer):
            self._cb()

    def _label(frame, size, dim=False):
        lb = NSTextField.alloc().initWithFrame_(frame)
        lb.setBezeled_(False)
        lb.setDrawsBackground_(False)
        lb.setEditable_(False)
        lb.setSelectable_(False)
        lb.setFont_(NSFont.menuFontOfSize_(size))
        lb.setTextColor_(NSColor.secondaryLabelColor() if dim else NSColor.labelColor())
        return lb

    class App(rumps.App):
        def __init__(self):
            super().__init__("Claude", title="⋯", quit_button=None)
            self._last = None          # số tốt gần nhất (dict từ fetch_usage)
            self._reset_abs = False    # False = "còn ..."  ·  True = "lúc HH:MM"

            # --- Panel 2 dòng dạng custom view: bấm để đổi giờ reset, menu KHÔNG đóng ---
            w, h = 260, 66
            view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
            self._lbl_session = _label(NSMakeRect(14, 42, w - 28, 18), 13)
            self._lbl_week = _label(NSMakeRect(14, 22, w - 28, 18), 13)
            self._lbl_hint = _label(NSMakeRect(14, 4, w - 28, 14), 10, dim=True)
            self._lbl_hint.setStringValue_("bấm để đổi giờ reset ↔")
            for lb in (self._lbl_session, self._lbl_week, self._lbl_hint):
                view.addSubview_(lb)
            self._toggler = _Toggler.alloc().initWithCb_(self._toggle_reset)
            gr = NSClickGestureRecognizer.alloc().initWithTarget_action_(self._toggler, b"onClick:")
            view.addGestureRecognizer_(gr)
            self.m_panel = rumps.MenuItem("")
            self.m_panel._menuitem.setView_(view)

            self.m_updated = rumps.MenuItem("Chưa cập nhật")
            self.menu = [
                self.m_panel,
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
            self.refresh_async()

        def _toggle_reset(self):
            self._reset_abs = not self._reset_abs
            self._render_lines()  # cập nhật tại chỗ, panel vẫn mở

        def refresh_async(self):
            threading.Thread(target=self._refresh, daemon=True).start()

        def _reset_str(self, u, which):
            key = f"{which}_reset_abs" if self._reset_abs else f"{which}_reset"
            return u.get(key) or u.get(f"{which}_reset") or ""

        def _set_title(self, text, red):
            """Đặt title menu bar; tô đỏ toàn bộ khi cảnh báo."""
            self.title = text  # giữ layout/độ rộng của rumps
            try:
                btn = self._nsapp.nsstatusitem.button()
                if btn is None:
                    return
                color = NSColor.systemRedColor() if red else NSColor.labelColor()
                attr = NSAttributedString.alloc().initWithString_attributes_(
                    text, {NSForegroundColorAttributeName: color})
                btn.setAttributedTitle_(attr)
            except Exception:
                pass

        def _render_lines(self):
            u = self._last
            if not u:
                return
            self._lbl_session.setStringValue_(
                f"Session (5h): {_pct(u['five'])}%   ·   {self._reset_str(u, 'five')}")
            self._lbl_week.setStringValue_(
                f"Tuần (7d): {_pct(u['seven'])}%   ·   {self._reset_str(u, 'seven')}")

        def _refresh(self):
            u = core.fetch_usage()
            if not u["ok"]:
                if self._last:
                    self.m_updated.title = f"⚠ lỗi lúc {_now()} — đang giữ số cũ"
                else:
                    self._set_title("⚠︎", True)
                    self._lbl_session.setStringValue_("Lỗi: " + u["error"])
                    self.m_updated.title = "Cập nhật: " + _now()
                return
            self._last = u
            f = u["five"]
            if f is not None:
                red = f >= RED_AT
                self._set_title(f"{core.glyph(f)}{_TEXT_VS} {_pct(f)}%", red)
            else:
                self._set_title("?", False)
            self._render_lines()
            self.m_updated.title = "Cập nhật: " + _now()

    App().run()


# ================================================= Linux / Windows (pystray) ====

# Màu số trên icon tray: xanh khi bình thường, đỏ khi session >= RED_AT, xám khi chưa có số
_COLOR_OK = (30, 200, 90)
_COLOR_WARN = (255, 59, 48)
_COLOR_UNKNOWN = (150, 150, 150)


def _load_bold_font(size):
    from PIL import ImageFont
    # Arial Black (Windows) cho nét dày nhất -> số còn rõ khi bị ép cao và thu nhỏ còn 16 px
    for name in ("ariblk.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf",
                 "segoeuib.ttf", "arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _make_image(pct):
    """
    Vẽ icon tray: chỉ có số %, không nền; xanh bình thường, đỏ khi >= RED_AT.

    Mỗi chữ số có kích thước CỐ ĐỊNH, không phụ thuộc giá trị ("5" và từng chữ số của
    "99" to bằng nhau): hệ số phóng được đo từ bộ chữ số 0-9, không phải từ chuỗi đang vẽ.
    Tối đa 2 chữ số vừa khít canvas; riêng "100" phải ép hẹp lại để đủ 3 chữ số.
    """
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if pct is None:
        color = _COLOR_UNKNOWN
    elif pct >= RED_AT:
        color = _COLOR_WARN
    else:
        color = _COLOR_OK

    text = "?" if pct is None else f"{int(round(pct))}"
    n = len(text)

    font = _load_bold_font(200)
    adv = font.getlength("0")                                  # bề ngang 1 ô chữ số (cố định)
    top = min(font.getbbox(c)[1] for c in "0123456789")
    bot = max(font.getbbox(c)[3] for c in "0123456789")
    vh = bot - top                                             # chiều cao chữ số (cố định)

    layer = Image.new("L", (max(1, round(adv * n)), vh), 0)
    ImageDraw.Draw(layer).text((0, -top), text, font=font, fill=255)

    sx = (size / max(2, n)) / adv                              # mỗi chữ số rộng size/2 (hoặc size/3)
    sy = (size - 2) / vh                                       # cao gần kín canvas
    nw, nh = max(1, round(adv * n * sx)), max(1, round(vh * sy))
    layer = layer.resize((nw, nh), Image.LANCZOS)
    img.paste(Image.new("RGBA", (nw, nh), color + (255,)),
              ((size - nw) // 2, (size - nh) // 2), layer)
    return img


def run_tray():
    import pystray
    from claude_usage_widget import ANCHOR_KEYS, ANCHORS

    # abs: kiểu giờ reset · logging_in: cửa sổ đăng nhập đang mở (tạm dừng tự làm mới)
    # widget_on: widget nổi ở góc trái taskbar (xem claude_usage_widget.py), nhớ qua config.json
    state = {"good": None, "note": "", "abs": False, "logging_in": False,
             "widget_on": bool(core.get_setting("widget", False)), "widget": None,
             # điểm neo của widget: bottom-left | bottom-right | top-left | top-right | free
             # chưa chọn bao giờ: ai đã tự kéo widget từ trước (có widget_pos) giữ chế độ tự do
             "anchor": (lambda a: a if a in ANCHOR_KEYS else "bottom-left")(
                 core.get_setting("widget_anchor")
                 or ("free" if core.get_setting("widget_pos") else "bottom-left"))}

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
            return state["note"] or "Đang tải…"
        return f"Session 5h: {_pct(g['five'])}%  ·  {_reset_str(g, 'five')}"

    def menu_week(_):
        g = state["good"]
        return "" if g is None else f"Tuần 7d: {_pct(g['seven'])}%  ·  {_reset_str(g, 'seven')}"

    icon = pystray.Icon("claude-usage", _make_image(None), "Claude Usage")

    def _widget_info():
        """Số liệu gần nhất cho widget + panel mở rộng (None nếu chưa có)."""
        g = state["good"]
        if not g:
            return {"five": None, "seven": None}
        return {"five": g["five"], "seven": g["seven"],
                "five_long": g.get("five_reset_long"), "five_abs": g.get("five_reset_abs"),
                "seven_long": g.get("seven_reset_long"), "seven_abs": g.get("seven_reset_abs")}

    def _in_thread(fn):
        """Callback của widget chạy trong thread Tk của nó -> việc nặng/chặn đưa sang thread riêng."""
        return lambda: threading.Thread(target=fn, daemon=True).start()

    def get_widget():
        if state["widget"] is None:
            from claude_usage_widget import Widget
            state["widget"] = Widget(
                on_refresh=_in_thread(refresh),
                on_login=_in_thread(login_via_browser),
                on_session_key=_in_thread(prompt_session_key),
                on_quit=lambda: icon.stop(),
                on_hide=lambda: set_widget(False),  # "Ẩn widget" ở panel / menu chuột phải
                on_move=lambda xy: core.update_config(widget_pos=list(xy)),
                on_anchor=lambda a: set_anchor(a, from_widget=True),  # chọn trong menu của widget
                anchor=state["anchor"],
                position=core.get_setting("widget_pos"))
        return state["widget"]

    def set_anchor(anchor, from_widget=False):
        """Đổi điểm neo, lưu vào config.json; widget đã tự áp dụng nếu thay đổi đến từ chính nó."""
        state["anchor"] = anchor
        core.update_config(widget_anchor=anchor)
        if not from_widget and state["widget"] is not None:
            state["widget"].set_anchor(anchor)
        refresh(skip_fetch=True)  # dựng lại menu để dấu chọn đúng

    def set_widget(on):
        state["widget_on"] = on
        core.update_config(widget=on)
        w = get_widget()
        if on:
            w.set_info(_widget_info())
            w.show()
        else:
            w.hide()
        refresh(skip_fetch=True)  # dựng lại menu để dấu tick đúng

    def toggle_reset(_=None, __=None):
        state["abs"] = not state["abs"]
        refresh(skip_fetch=True)

    def prompt_session_key():
        """Hộp thoại dán sessionKey -> lưu vào config.json -> làm mới ngay."""
        try:
            import tkinter as tk
            from tkinter import messagebox, simpledialog
        except Exception:
            state["note"] = "Thiếu tkinter — dán sessionKey vào config.json (xem README)"
            refresh(skip_fetch=True)
            return
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            val = simpledialog.askstring(
                "Claude Usage Bar",
                "Dán giá trị cookie sessionKey của claude.ai\n"
                "(trình duyệt: F12 → Application → Cookies → claude.ai → sessionKey)",
                show="*", parent=root)
            if not val:
                return
            try:
                path = core.save_session_key(val)
            except Exception as e:
                messagebox.showerror("Claude Usage Bar", f"Không lưu được: {e}", parent=root)
                return
        finally:
            root.destroy()
        state["note"] = f"Đã lưu sessionKey ({path})"
        refresh()

    def login_via_browser():
        """Mở cửa sổ Chrome/Edge tạm để đăng nhập claude.ai (tiến trình riêng), rồi làm mới."""
        import os
        import subprocess
        if state["logging_in"]:
            return
        state["logging_in"] = True
        state["note"] = "Đang chờ bạn đăng nhập claude.ai trong cửa sổ vừa mở…"
        refresh(skip_fetch=True)
        try:
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude_usage_login.py")
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            rc = subprocess.call([sys.executable, script], creationflags=flags)
        except Exception as e:
            rc = -1
            state["note"] = f"Lỗi mở cửa sổ đăng nhập: {e}"[:110]
        finally:
            state["logging_in"] = False
        if rc == 0:
            refresh()  # lấy số liệu ngay với phiên vừa đăng nhập
        else:
            if rc == 2:
                state["note"] = "Không thấy Chrome/Edge/Brave — dùng 'Nhập sessionKey…'"
            elif rc != -1:
                state["note"] = "Chưa đăng nhập (đã đóng cửa sổ hoặc hết giờ)"
            refresh(skip_fetch=True)

    def refresh(_=None, __=None, skip_fetch=False):
        if state["logging_in"] and not skip_fetch:
            return  # đang đăng nhập: đừng ghi đè trạng thái bằng lỗi cookie
        if not skip_fetch:
            u = core.fetch_usage()
            if u["ok"]:
                state["good"] = u
                state["note"] = f"Cập nhật: {_now()}"
            else:
                # giữ số cũ, chỉ ghi chú lỗi
                state["note"] = (f"⚠ lỗi lúc {_now()} — giữ số cũ"
                                 if state["good"] else "Lỗi: " + u["error"])
        pct = state["good"]["five"] if state["good"] else None
        icon.icon = _make_image(pct)
        icon.title = title_text()
        if state["widget_on"]:
            w = get_widget()
            w.set_info(_widget_info())
            w.show()
        icon.menu = pystray.Menu(
            # Bấm 2 dòng này để đổi kiểu giờ reset ("còn ..." ↔ "lúc HH:MM")
            pystray.MenuItem(menu_line, toggle_reset),
            pystray.MenuItem(menu_week, toggle_reset),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Làm mới ngay", lambda i, it: refresh()),
            pystray.MenuItem("Hiện số ở góc taskbar",
                             lambda i, it: set_widget(not state["widget_on"]),
                             checked=lambda it: state["widget_on"]),
            pystray.MenuItem("Điểm neo widget", pystray.Menu(*[
                pystray.MenuItem(label, (lambda k: lambda i, it: set_anchor(k))(key),
                                 checked=(lambda k: lambda it: state["anchor"] == k)(key),
                                 radio=True)
                for key, label in ANCHORS])),
            pystray.MenuItem("Đăng nhập claude.ai…",
                             lambda i, it: threading.Thread(target=login_via_browser,
                                                            daemon=True).start()),
            pystray.MenuItem("Nhập sessionKey…",
                             lambda i, it: threading.Thread(target=prompt_session_key,
                                                            daemon=True).start()),
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

    if state["widget_on"]:  # hiện ngay (--%), không đợi lượt tải số liệu đầu tiên
        w = get_widget()
        w.set_info(_widget_info())
        w.show()

    threading.Thread(target=loop, daemon=True).start()
    icon.run()


# ============================================================================ ==

_MUTEX_HANDLES = []  # giữ handle mutex sống suốt vòng đời tiến trình


def _already_running_windows():
    """True nếu đã có một bản app khác đang chạy (tránh 2 icon tray khi bấm run.bat nhiều lần)."""
    import ctypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    handle = k32.CreateMutexW(None, False, "Local\\ClaudeUsageBar")
    _MUTEX_HANDLES.append(handle)
    return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


def _ensure_log_streams():
    """pythonw không có console: sys.stdout/stderr là None nên mọi lỗi runtime bị nuốt mất.
    Chuyển chúng vào file log để còn debug được."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    import os
    import tempfile
    try:
        log = open(os.path.join(tempfile.gettempdir(), "claude-usage-bar.log"), "a",
                   encoding="utf-8", buffering=1)
    except OSError:
        return
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


def main():
    _ensure_log_streams()
    if sys.platform == "win32" and _already_running_windows():
        print("Claude Usage Bar đang chạy rồi — bỏ qua bản thứ hai.")
        return
    if sys.platform == "darwin":
        run_macos()
    else:
        run_tray()


if __name__ == "__main__":
    main()
