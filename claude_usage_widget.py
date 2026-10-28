#!/usr/bin/env python3
"""
Widget nổi hiển thị usage ở góc trái taskbar (Windows; có chạy thử được trên Linux).

Dạng gọn (nằm thẳng trên taskbar, không nền):   ✦ Session 33% ▬ | 📅 Week 69% ▬  ⌄
Bấm vào: mở panel mở rộng phía trên taskbar (Chi tiết sử dụng token, Phiên hiện tại,
Giới hạn tuần, Làm mới ngay, Cài đặt).

Icon tray của Windows chỉ nằm được ở khay thông báo phía phải taskbar, nên muốn hiện ở
góc trái thì cần cửa sổ riêng: không viền, luôn nổi trên cùng, nền trong suốt thật
(cửa sổ nhiều lớp alpha theo từng điểm ảnh, UpdateLayeredWindow).

- Kéo thả bằng chuột trái để đặt vị trí (được nhớ lại); bấm (không kéo) để mở/đóng panel.
- Tự ẩn khi có cửa sổ toàn màn hình (xem phim, chơi game).

Tkinter chạy trong thread riêng; các lời gọi từ thread khác đi qua hàng đợi (thread-safe).
"""

import ctypes
import math
import os
import queue
import sys
import threading
import time
import webbrowser

USAGE_URL = "https://claude.ai/settings/usage"

# ----------------------------------------------------------------------------- kích thước ----
CW, CH = 258, 44          # widget gọn (px logic; nhân tỉ lệ DPI khi vẽ)
FW, FH = 296, 372         # panel mở rộng (không tính vùng đổ bóng)
FM = 14                   # lề quanh panel cho bóng đổ
SS_COMPACT, SS_FLYOUT = 3, 2   # siêu lấy mẫu: vẽ gấp N lần rồi thu nhỏ cho nét mịn
TICK_MS = 400
CLICK_SLOP = 4            # kéo quá số px này thì coi là kéo thả, không phải bấm

# Ngưỡng đổi màu: >= WARN_AT vàng, >= DANGER_AT đỏ
WARN_AT = 75
DANGER_AT = 90

# ------------------------------------------------------------------------------- màu sắc ----
SPARK = (96, 165, 250)
SPARK_PANEL = (88, 196, 230)
CAL_OK = (32, 214, 166)
YELLOW = (245, 184, 46)
RED = (255, 90, 106)
BAR_SESSION = ((56, 189, 248), (59, 130, 246))   # gradient xanh dương
BAR_WEEK = ((52, 224, 170), (16, 185, 129))      # gradient xanh lá
PANEL_FILL = (20, 44, 56)
PANEL_ALPHA = 246
PANEL_BORDER = (150, 200, 215)
WHITE = (255, 255, 255)
PANEL_MUTED = (165, 186, 196)


def _dbg(*a):
    """Nhật ký sự kiện widget (bật bằng biến môi trường CLAUDE_USAGE_DEBUG=1) -> stderr / file log."""
    import os
    if os.environ.get("CLAUDE_USAGE_DEBUG"):
        print("[widget]", *a, file=sys.stderr, flush=True)


def _level(p):
    if p is None:
        return "none"
    if p >= DANGER_AT:
        return "danger"
    if p >= WARN_AT:
        return "warn"
    return "ok"


def _bar_colors(level, grad):
    return {"warn": (YELLOW, YELLOW), "danger": (RED, RED)}.get(level, grad)


def _pct_text(p):
    return "--%" if p is None else f"{int(round(p))}%"


# --------------------------------------------------------------------------------- bộ vẽ ----
def _font(px, weight="regular"):
    from PIL import ImageFont
    names = {"semibold": ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"),
             "regular": ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")}[weight]
    for n in names:
        try:
            return ImageFont.truetype(n, max(1, round(px)))
        except Exception:
            continue
    return ImageFont.load_default()


class _Painter:
    """
    Vẽ lên ảnh RGBA nền trong suốt, toạ độ theo px logic. Mỗi thao tác vẽ vào một mặt nạ 'L'
    nhỏ (chỉ trong khung bao của nó) rồi tô màu qua mặt nạ -> alpha thẳng, không viền đen.
    """

    def __init__(self, w, h, scale, ss, margin=0):
        from PIL import Image
        self.scale, self.ss, self.dx = scale, ss, margin
        self.u = scale * ss
        self.W = round((w + 2 * margin) * self.u)
        self.H = round((h + 2 * margin) * self.u)
        self.out = (round((w + 2 * margin) * scale), round((h + 2 * margin) * scale))
        self.img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))

    def _bbox(self, x0, y0, x1, y1, pad=2):
        u, d = self.u, self.dx
        return (max(0, math.floor((x0 + d) * u) - pad), max(0, math.floor((y0 + d) * u) - pad),
                min(self.W, math.ceil((x1 + d) * u) + pad), min(self.H, math.ceil((y1 + d) * u) + pad))

    def shape(self, bbox, draw, color, alpha=255, gradient=None):
        """draw(d, T): T(x, y) đổi toạ độ logic -> px cục bộ của mặt nạ."""
        from PIL import Image, ImageDraw
        x0, y0, x1, y1 = self._bbox(*bbox)
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0:
            return
        u, d0 = self.u, self.dx
        mask = Image.new("L", (w, h), 0)
        draw(ImageDraw.Draw(mask), lambda x, y: ((x + d0) * u - x0, (y + d0) * u - y0))
        if alpha < 255:
            mask = mask.point(lambda v, a=alpha: v * a // 255)
        if gradient:
            c1, c2 = gradient
            g = Image.new("RGB", (w, 1))
            for i in range(w):
                t = i / max(1, w - 1)
                g.putpixel((i, 0), tuple(round(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))
            layer = g.resize((w, h)).convert("RGBA")
        else:
            layer = Image.new("RGBA", (w, h), tuple(color) + (255,))
        layer.putalpha(mask)
        region = self.img.crop((x0, y0, x1, y1))
        self.img.paste(Image.alpha_composite(region, layer), (x0, y0))

    # ---- hình cơ bản -------------------------------------------------------------------
    def rrect(self, x0, y0, x1, y1, r, color, alpha=255, gradient=None):
        u = self.u
        self.shape((x0, y0, x1, y1),
                   lambda d, T: d.rounded_rectangle([T(x0, y0), T(x1, y1)], radius=r * u, fill=255),
                   color, alpha, gradient)

    def ring(self, x0, y0, x1, y1, r, color, width, alpha=255):
        u = self.u
        self.shape((x0, y0, x1, y1),
                   lambda d, T: d.rounded_rectangle([T(x0, y0), T(x1, y1)], radius=r * u,
                                                    outline=255, width=max(1, round(width * u))),
                   color, alpha)

    def line(self, pts, color, width, alpha=255):
        u = self.u
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.shape((min(xs) - width, min(ys) - width, max(xs) + width, max(ys) + width),
                   lambda d, T: d.line([T(*p) for p in pts], fill=255,
                                       width=max(1, round(width * u)), joint="curve"),
                   color, alpha)

    def polygon(self, pts, color, alpha=255):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.shape((min(xs), min(ys), max(xs), max(ys)),
                   lambda d, T: d.polygon([T(*p) for p in pts], fill=255), color, alpha)

    def text(self, x, y, s, font, color, alpha=255, anchor="ls"):
        from PIL import Image, ImageDraw
        u, d0 = self.u, self.dx
        px, py = (x + d0) * u, (y + d0) * u
        l, t, r, b = font.getbbox(s, anchor=anchor)
        x0, y0 = max(0, math.floor(px + l) - 2), max(0, math.floor(py + t) - 2)
        x1, y1 = min(self.W, math.ceil(px + r) + 2), min(self.H, math.ceil(py + b) + 2)
        if x1 <= x0 or y1 <= y0:
            return
        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(mask).text((px - x0, py - y0), s, font=font, fill=255, anchor=anchor)
        if alpha < 255:
            mask = mask.point(lambda v, a=alpha: v * a // 255)
        layer = Image.new("RGBA", mask.size, tuple(color) + (255,))
        layer.putalpha(mask)
        self.img.paste(Image.alpha_composite(self.img.crop((x0, y0, x1, y1)), layer), (x0, y0))

    def text_width(self, s, font):
        return font.getlength(s) / self.u

    # ---- biểu tượng --------------------------------------------------------------------
    def sparkle(self, cx, cy, r, color):
        """Ngôi sao 4 cánh lõm."""
        pts = []
        for i in range(8):
            a = math.radians(i * 45 - 90)
            rr = r if i % 2 == 0 else r * 0.30
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        self.polygon(pts, color)

    def calendar(self, x, y, s, color):
        lw = s * 0.09
        top = y + s * 0.16
        self.ring(x, top, x + s, y + s, s * 0.22, color, lw)
        hy = top + s * 0.27
        self.line([(x, hy), (x + s, hy)], color, lw)
        for fx in (0.28, 0.66):
            rx = x + s * fx
            self.rrect(rx - lw / 2, y, rx + lw / 2, top + s * 0.14, lw / 2, color)
        cell = s * 0.12
        for r in range(3):
            for c in range(3):
                cx0, cy0 = x + s * (0.17 + 0.27 * c), hy + s * (0.13 + 0.20 * r)
                self.rrect(cx0, cy0, cx0 + cell, cy0 + cell, 0, color)

    def chevron(self, cx, cy, color, direction="down", size=4.5, width=1.5):
        k = size
        if direction == "down":
            pts = [(cx - k, cy - k * 0.5), (cx, cy + k * 0.5), (cx + k, cy - k * 0.5)]
        else:  # right
            pts = [(cx - k * 0.5, cy - k), (cx + k * 0.5, cy), (cx - k * 0.5, cy + k)]
        self.line(pts, color, width)

    def refresh_icon(self, cx, cy, r, color, width=1.5):
        u = self.u

        def draw(d, T):
            a, b = T(cx - r, cy - r), T(cx + r, cy + r)
            d.arc([a, b], 25, 305, fill=255, width=max(1, round(width * u)))

        self.shape((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), draw, color)
        # đầu mũi tên ở cuối cung (305°), hướng theo tiếp tuyến chiều kim đồng hồ
        ang = math.radians(305)
        px, py = cx + r * math.cos(ang), cy + r * math.sin(ang)
        tx, ty = -math.sin(ang), math.cos(ang)
        nx, ny = -ty, tx
        s = r * 0.62
        self.polygon([(px + tx * s * 1.1, py + ty * s * 1.1),
                      (px + nx * s * 0.8, py + ny * s * 0.8),
                      (px - nx * s * 0.8, py - ny * s * 0.8)], color)

    def gear(self, cx, cy, r, color):
        u = self.u

        def draw(d, T):
            (x0, y0), (x1, y1) = T(cx - r * 0.60, cy - r * 0.60), T(cx + r * 0.60, cy + r * 0.60)
            d.ellipse([x0, y0, x1, y1], fill=255)
            for i in range(8):
                a = math.radians(i * 45)
                ca, sa = math.cos(a), math.sin(a)
                w = r * 0.14
                pts = [(cx + ca * r * 0.5 - sa * w, cy + sa * r * 0.5 + ca * w),
                       (cx + ca * r - sa * w * 0.8, cy + sa * r + ca * w * 0.8),
                       (cx + ca * r + sa * w * 0.8, cy + sa * r - ca * w * 0.8),
                       (cx + ca * r * 0.5 + sa * w, cy + sa * r * 0.5 - ca * w)]
                d.polygon([T(*p) for p in pts], fill=255)
            (hx0, hy0), (hx1, hy1) = T(cx - r * 0.34, cy - r * 0.34), T(cx + r * 0.34, cy + r * 0.34)
            d.ellipse([hx0, hy0, hx1, hy1], fill=0)

        self.shape((cx - r, cy - r, cx + r, cy + r), draw, color)

    def finish(self):
        from PIL import Image
        return self.img.resize(self.out, Image.LANCZOS)


# --------------------------------------------------------------------------- widget gọn ----
def render_compact(five, seven, scale=1.0, light=False):
    """Widget gọn trên taskbar: nền trong suốt (alpha=1 để vẫn bấm được), chữ theo nền taskbar."""
    p = _Painter(CW, CH, scale, SS_COMPACT)
    if light:
        ink, label, track, track_a, divider = (20, 24, 32), (70, 80, 96), (0, 0, 0), 38, (0, 0, 0)
    else:
        ink, label, track, track_a, divider = WHITE, (200, 207, 218), WHITE, 42, WHITE
    f_label, f_pct = _font(11 * p.u), _font(17.5 * p.u, "semibold")
    lv5, lv7 = _level(five), _level(seven)

    p.sparkle(20, 23, 11, SPARK)
    p.sparkle(30.5, 11.5, 4.2, SPARK)
    p.calendar(126, 13, 19, RED if lv7 == "danger" else CAL_OK)

    def column(x0, name, val, level, grad):
        dim = val is None
        p.text(x0, 14.5, name, f_label, label, alpha=170 if dim else 255)
        p.text(x0, 31, _pct_text(val), f_pct, ink, alpha=130 if dim else 255)
        p.rrect(x0, 35.5, x0 + 62, 39.5, 2, track, alpha=track_a)
        if not dim:
            fw = max(4.0, 62 * min(1.0, val / 100.0))
            c1, c2 = _bar_colors(level, grad)
            p.rrect(x0, 35.5, x0 + fw, 39.5, 2, c1, gradient=(c1, c2))

    column(44, "Session", five, lv5, BAR_SESSION)
    column(154, "Week", seven, lv7, BAR_WEEK)

    p.line([(116, 9), (116, 35)], divider, 1, alpha=46)
    p.chevron(242, 23, label, "down", 4.5, 1.5)

    img = p.finish()
    img.putalpha(img.getchannel("A").point(lambda v: v if v else 1))  # alpha=1: bấm được, vẫn vô hình
    return img


# ------------------------------------------------------------------------------- panel mở ----
def render_flyout(info, scale=1.0, show_abs=False):
    """
    Panel mở rộng. Trả về (ảnh RGBA, rects) với rects = {tên: (x0, y0, x1, y1)} theo px thật.
    """
    from PIL import Image, ImageFilter

    five, seven = info.get("five"), info.get("seven")
    p = _Painter(FW, FH, scale, SS_FLYOUT, margin=FM)
    u = p.u

    # bóng đổ mềm phía sau panel
    sh = Image.new("L", (p.W, p.H), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(sh).rounded_rectangle(
        [FM * u, (FM + 4) * u, (FM + FW) * u, (FM + FH + 4) * u], radius=12 * u, fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(7 * u))
    shadow = Image.new("RGBA", (p.W, p.H), (0, 0, 0, 255))
    shadow.putalpha(sh)
    p.img = Image.alpha_composite(p.img, shadow)

    # thân panel: kính tối ngả xanh
    p.rrect(0, 0, FW, FH, 12, PANEL_FILL, alpha=PANEL_ALPHA)
    p.ring(0.5, 0.5, FW - 0.5, FH - 0.5, 12, PANEL_BORDER, 1, alpha=62)

    f_title, f_sub = _font(15 * u, "semibold"), _font(12 * u)
    f_blk, f_big, f_unit = _font(14.5 * u), _font(27 * u, "semibold"), _font(15 * u)
    f_rst, f_row = _font(12.5 * u), _font(14.5 * u)
    pad = 16
    sep = lambda y: p.line([(0, y), (FW, y)], WHITE, 1, alpha=26)

    # ---- đầu đề: bấm để mở trang usage ----
    p.sparkle(30, 32, 11, SPARK_PANEL)
    p.sparkle(40, 21, 4.2, SPARK_PANEL)
    p.text(56, 29, "Chi tiết sử dụng token", f_title, WHITE)
    p.text(56, 48, "Xem đầy đủ thông tin", f_sub, PANEL_MUTED)
    p.chevron(FW - 24, 33, PANEL_MUTED, "right", 5, 1.5)
    sep(65)

    def block(top, title, val, rel, absolute, grad):
        lv = _level(val)
        p.text(pad, top + 26, title, f_blk, WHITE)
        big = _pct_text(val)
        p.text(pad, top + 58, big, f_big, WHITE, alpha=140 if val is None else 255)
        p.text(pad + p.text_width(big, f_big) + 6, top + 58, "đã sử dụng", f_unit, WHITE)
        w = FW - 2 * pad
        p.rrect(pad, top + 69, pad + w, top + 74, 2.5, WHITE, alpha=36)
        if val is not None:
            c1, c2 = _bar_colors(lv, grad)
            p.rrect(pad, top + 69, pad + max(5.0, w * min(1.0, val / 100.0)), top + 74, 2.5,
                    c1, gradient=(c1, c2))
        text = ((("Đặt lại " + absolute) if show_abs and absolute else rel)
                or ("Chưa có dữ liệu · Cài đặt › Đăng nhập" if val is None else "—"))
        p.text(pad, top + 96, text, f_rst, PANEL_MUTED)

    block(66, "Phiên hiện tại", five, info.get("five_long"), info.get("five_abs"), BAR_SESSION)
    sep(174)
    block(175, "Giới hạn tuần", seven, info.get("seven_long"), info.get("seven_abs"), BAR_WEEK)
    sep(283)

    # ---- hàng hành động ----
    p.refresh_icon(pad + 11, 303, 7.5, WHITE)
    p.text(56, 308, "Làm mới ngay", f_row, WHITE)
    p.gear(pad + 11, 343, 8.5, WHITE)
    p.text(56, 348, "Cài đặt", f_row, WHITE)

    img = p.finish()

    s = scale
    rects = {
        "header": (0, 0, FW, 65),
        "reset_five": (pad, 66 + 82, FW - pad, 66 + 104),
        "reset_seven": (pad, 175 + 82, FW - pad, 175 + 104),
        "refresh": (0, 284, FW, 324),
        "settings": (0, 324, FW, 364),
    }
    # panel nằm lệch FM so với góc ảnh (chừa chỗ cho bóng đổ) -> dời toạ độ rồi đổi sang px thật
    rects = {k: tuple(round((v + FM) * s) for v in r) for k, r in rects.items()}

    return img, rects


def apply_hover(img, rects, hover, scale=1.0):
    """Tô sáng hàng đang rê chuột lên một bản sao ảnh nền (rẻ hơn nhiều so với vẽ lại cả panel)."""
    from PIL import Image, ImageDraw
    if hover not in ("header", "refresh", "settings"):
        return img
    x0, y0, x1, y1 = rects[hover]
    inset = round(6 * scale)
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle([x0 + inset, y0 + round(2 * scale), x1 - inset, y1 - round(2 * scale)],
                                         radius=round(7 * scale), fill=(255, 255, 255, 20))
    return Image.alpha_composite(img, hl)


# ----------------------------------------------------------------- cửa sổ nhiều lớp (Win32) ----
class _Win:
    """Gói ctypes cho cửa sổ nhiều lớp alpha theo từng điểm ảnh (UpdateLayeredWindow)."""
    ok = sys.platform == "win32"

    if ok:
        from ctypes import wintypes as _wt

        class _BLEND(ctypes.Structure):
            _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

        class _BMIH(ctypes.Structure):
            _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                        ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                        ("biClrImportant", ctypes.c_uint32)]

        u32 = ctypes.WinDLL("user32", use_last_error=True)
        g32 = ctypes.WinDLL("gdi32", use_last_error=True)
        _vp = ctypes.c_void_p
        u32.GetDC.argtypes, u32.GetDC.restype = [_vp], _vp
        u32.ReleaseDC.argtypes = [_vp, _vp]
        u32.GetParent.argtypes, u32.GetParent.restype = [_vp], _vp
        u32.GetWindowLongPtrW.argtypes, u32.GetWindowLongPtrW.restype = [_vp, ctypes.c_int], ctypes.c_ssize_t
        u32.SetWindowLongPtrW.argtypes = [_vp, ctypes.c_int, ctypes.c_ssize_t]
        u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        u32.UpdateLayeredWindow.argtypes = [_vp, _vp, ctypes.POINTER(_wt.POINT), ctypes.POINTER(_wt.SIZE),
                                            _vp, ctypes.POINTER(_wt.POINT), ctypes.c_uint32,
                                            ctypes.POINTER(_BLEND), ctypes.c_uint32]
        u32.UpdateLayeredWindow.restype = ctypes.c_int
        g32.CreateCompatibleDC.argtypes, g32.CreateCompatibleDC.restype = [_vp], _vp
        g32.CreateDIBSection.argtypes = [_vp, _vp, ctypes.c_uint, ctypes.POINTER(_vp), _vp, ctypes.c_uint]
        g32.CreateDIBSection.restype = _vp
        g32.SelectObject.argtypes, g32.SelectObject.restype = [_vp, _vp], _vp
        g32.DeleteObject.argtypes = [_vp]
        g32.DeleteDC.argtypes = [_vp]

    @classmethod
    def hwnd(cls, tk_window):
        """HWND của khung ngoài của cửa sổ Tk (cái thật sự có kiểu cửa sổ/vị trí)."""
        inner = tk_window.winfo_id()
        return cls.u32.GetParent(inner) or inner

    @classmethod
    def rect(cls, hwnd):
        """(left, top, width, height) thật của cửa sổ."""
        r = cls._wt.RECT()
        cls.u32.GetWindowRect(hwnd, ctypes.byref(r))
        return r.left, r.top, r.right - r.left, r.bottom - r.top

    @classmethod
    def own_by_taskbar(cls, hwnd):
        """Đặt taskbar làm 'chủ' (owner) của cửa sổ. Cửa sổ có owner luôn nằm TRÊN owner trong z-order,
        kể cả khi taskbar Win11 đổi lớp sau khi bấm Start bằng chuột (topmost thường bị chìm xuống dưới)."""
        try:
            tray = cls.u32.FindWindowW("Shell_TrayWnd", None)
            if not tray:
                return False
            cls.u32.GetWindowLongPtrW.argtypes = [cls._vp, ctypes.c_int]
            cls.u32.SetWindowLongPtrW.argtypes = [cls._vp, ctypes.c_int, ctypes.c_ssize_t]
            if cls.u32.GetWindowLongPtrW(hwnd, -8) != tray:        # GWLP_HWNDPARENT
                cls.u32.SetWindowLongPtrW(hwnd, -8, tray)
                return True
        except Exception:
            pass
        return False

    @classmethod
    def make_layered(cls, hwnd, noactivate=False):
        GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = -20, 0x80000, 0x80, 0x08000000
        style = cls.u32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | (WS_EX_NOACTIVATE if noactivate else 0)
        cls.u32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)

    @classmethod
    def update(cls, hwnd, img, x=None, y=None):
        """Đặt nội dung cửa sổ = ảnh RGBA (alpha thẳng) qua UpdateLayeredWindow."""
        from PIL import Image
        w, h = img.size
        r, g, b, a = img.convert("RGBa").split()          # RGBa = nhân sẵn alpha (yêu cầu của Win32)
        data = Image.merge("RGBA", (b, g, r, a)).tobytes()  # thứ tự byte BGRA

        hdc_screen = cls.u32.GetDC(None)
        memdc = cls.g32.CreateCompatibleDC(hdc_screen)
        bmi = cls._BMIH(40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)   # -h: ảnh từ trên xuống
        bits = ctypes.c_void_p()
        hbmp = cls.g32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        try:
            ctypes.memmove(bits, data, len(data))
            old = cls.g32.SelectObject(memdc, hbmp)
            size = cls._wt.SIZE(w, h)
            src = cls._wt.POINT(0, 0)
            blend = cls._BLEND(0, 0, 255, 1)                  # AC_SRC_OVER, dùng alpha của từng điểm
            dst = None if x is None else ctypes.byref(cls._wt.POINT(x, y))
            ok = cls.u32.UpdateLayeredWindow(hwnd, hdc_screen, dst, ctypes.byref(size), memdc,
                                             ctypes.byref(src), 0, ctypes.byref(blend), 2)  # ULW_ALPHA
            cls.g32.SelectObject(memdc, old)
            return bool(ok)
        finally:
            cls.g32.DeleteObject(hbmp)
            cls.g32.DeleteDC(memdc)
            cls.u32.ReleaseDC(None, hdc_screen)


def _enable_thread_dpi_awareness():
    """Cho riêng thread của widget nhận biết DPI -> vẽ theo px thật, nét sắc thay vì bị phóng mờ."""
    if sys.platform != "win32":
        return
    try:
        fn = ctypes.windll.user32.SetThreadDpiAwarenessContext
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = ctypes.c_void_p
        fn(ctypes.c_void_p(-4))  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    except Exception:
        pass


def _dpi_scale():
    if sys.platform != "win32":
        return 1.0
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:
        return 1.0


def _taskbar_light():
    """Taskbar đang ở giao diện sáng? (để chọn chữ tối thay vì chữ trắng)"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except Exception:
        return False


def _work_area(sw, sh):
    """(left, top, right, bottom) vùng làm việc (không gồm taskbar), px thật."""
    if sys.platform == "win32":
        try:
            from ctypes import wintypes
            r = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
            return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
    return 0, 0, sw, sh


def _foreground_fullscreen():
    """True nếu cửa sổ đang ở foreground phủ kín cả màn hình (phim, game...)."""
    if sys.platform != "win32":
        return False
    try:
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return False
        cls = ctypes.create_unicode_buffer(64)
        u32.GetClassNameW(hwnd, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                         "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow",
                         "TopLevelWindowForOverflowXamlIsland"):
            return False  # desktop / taskbar / Start, Search, trung tâm thông báo không tính
        if not u32.IsWindowVisible(hwnd):
            return False
        cloaked = ctypes.c_int(0)   # DWMWA_CLOAKED: cửa sổ UWP "ẩn" vẫn còn là foreground sau khi đóng
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4) == 0 and cloaked.value:
            return False
        rect = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(rect))
        sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        return rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh
    except Exception:
        return False


def _cursor_and_button():
    """(x, y, đang giữ chuột trái?) theo px thật; None nếu không hỗ trợ."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        return pt.x, pt.y, down
    except Exception:
        return None


def _default_position(sw, sh, w, h, scale):
    """Góc trái taskbar (taskbar ở dưới), ngay sau widget thời tiết; không rõ thì góc trái dưới."""
    l, t, r, b = _work_area(sw, sh)
    tb_h = sh - b
    if tb_h > 0 and t == 0 and l == 0 and r == sw:
        return round(200 * scale), b + (tb_h - h) // 2
    return round(8 * scale), sh - h - round(8 * scale)


# Điểm neo: dính vào một góc (luôn giữ đúng chỗ) hoặc "free" = kéo thả vị trí bất kỳ
ANCHORS = (("bottom-left", "Dưới trái (taskbar, cạnh widget thời tiết)"),
           ("bottom-right", "Dưới phải (taskbar, cạnh khay hệ thống)"),
           ("top-left", "Trên trái"),
           ("top-right", "Trên phải"),
           ("free", "Tự do (kéo thả)"))
ANCHOR_KEYS = tuple(k for k, _ in ANCHORS)


def _tray_left(sw, sh):
    """Mép trái của khay hệ thống trên taskbar (px thật), hoặc None nếu không tìm được."""
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        u32.FindWindowW.restype = ctypes.c_void_p
        u32.FindWindowExW.restype = ctypes.c_void_p
        u32.FindWindowExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
        bar = u32.FindWindowW("Shell_TrayWnd", None)
        tray = u32.FindWindowExW(bar, None, "TrayNotifyWnd", None) if bar else None
        if not tray:
            return None
        rect = wintypes.RECT()
        u32.GetWindowRect(ctypes.c_void_p(tray), ctypes.byref(rect))
        return rect.left if 0 < rect.left < sw and rect.right > rect.left else None
    except Exception:
        return None


def _anchor_position(anchor, sw, sh, w, h, scale):
    """Toạ độ (x, y) của widget theo điểm neo; None nếu 'free' (dùng vị trí do người dùng đặt)."""
    if anchor not in ANCHOR_KEYS or anchor == "free":
        return None
    l, t, r, b = _work_area(sw, sh)
    m = round(8 * scale)
    tb_h = sh - b
    taskbar_bottom = tb_h > 0 and t == 0 and l == 0 and r == sw
    if anchor == "bottom-left":
        return _default_position(sw, sh, w, h, scale)
    if anchor == "bottom-right":
        if taskbar_bottom:
            tray = _tray_left(sw, sh)
            x = (tray - m) if tray else (sw - round(360 * scale))
            return x - w, b + (tb_h - h) // 2
        return r - w - m, b - h - m
    if anchor == "top-left":
        return l + m, t + m
    return r - w - m, t + m          # top-right


# ----------------------------------------------------------------------------------- widget ----
class Widget:
    def __init__(self, on_refresh=None, on_login=None, on_session_key=None, on_quit=None,
                 on_hide=None, on_move=None, on_anchor=None, on_autostart_toggle=None,
                 autostart_status=None, position=None, anchor="bottom-left"):
        """
        Callback (chạy trong thread của widget; app nên tự đưa việc nặng sang thread khác):
        on_refresh / on_login / on_session_key / on_quit / on_hide / on_move((x, y)) /
        on_anchor(tên điểm neo mới, do người dùng chọn trong menu của widget)
        anchor: một trong ANCHOR_KEYS. Khác "free" thì widget bị khoá ở góc đó (không kéo được).
        position: (x, y) đã lưu (px thật) cho chế độ "free"; None để dùng vị trí mặc định
        """
        self._cb = dict(refresh=on_refresh, login=on_login, session_key=on_session_key,
                        quit=on_quit, hide=on_hide, move=on_move, anchor=on_anchor,
                        autostart_toggle=on_autostart_toggle, autostart_status=autostart_status)
        self._anchor = anchor if anchor in ANCHOR_KEYS else "bottom-left"
        self._position = tuple(position) if position else None
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self._thread = None
        self._info = {"five": None, "seven": None}
        self._show_abs = False
        self._wanted = False
        self._shown = False
        self._last_fs = None

    # ---- gọi được từ thread bất kỳ ---------------------------------------------------
    def show(self):
        self._start()
        self._q.put(("show", None))

    def hide(self):
        if self._thread:
            self._q.put(("hide", None))

    def set_info(self, info):
        """info: dict five, seven, five_long, five_abs, seven_long, seven_abs"""
        self._info = dict(info)
        if self._thread:
            self._q.put(("info", self._info))

    def set_anchor(self, anchor):
        """Đổi điểm neo từ bên ngoài (vd. menu tray). Không gọi lại on_anchor."""
        if anchor in ANCHOR_KEYS:
            self._anchor = anchor
            if self._thread:
                self._q.put(("anchor", anchor))

    def stop(self):
        if self._thread:
            self._q.put(("stop", None))

    # ---- nội bộ -----------------------------------------------------------------------
    def _start(self):
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run_safely, daemon=True)
                self._thread.start()

    def _run_safely(self):
        try:
            self._run()
        except Exception as e:  # lỗi Tk/Win32... -> ghi ra log (stderr) rồi cho phép khởi động lại
            import traceback
            print("widget lỗi:", e, file=sys.stderr)
            traceback.print_exc()
        finally:
            with self._lock:
                self._thread = None
            self._shown = False

    def _call(self, name):
        cb = self._cb.get(name)
        if cb:
            cb()

    def _run(self):
        import tkinter as tk

        _enable_thread_dpi_awareness()  # phải gọi trước khi tạo cửa sổ Tk
        scale = _dpi_scale()
        cw, ch = round(CW * scale), round(CH * scale)

        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()

        def target_pos():
            """Vị trí cần có: theo điểm neo, hoặc (chế độ tự do) vị trí đã lưu / mặc định."""
            pos = _anchor_position(self._anchor, sw, sh, cw, ch, scale)
            if pos:
                return pos
            x, y = self._position or (None, None)
            if x is None or not (0 <= x <= sw - cw and 0 <= y <= sh - ch):
                return _default_position(sw, sh, cw, ch, scale)
            return x, y

        x, y = target_pos()
        root.geometry(f"{cw}x{ch}+{x}+{y}")
        root.update_idletasks()
        hwnd = _Win.hwnd(root)
        _Win.make_layered(hwnd, noactivate=False)

        compact = {"img": None}

        def draw_compact(rerender=True):
            """rerender=False: chỉ đẩy lại ảnh đã vẽ (rẻ) -- dùng để 'vỗ về' DWM sau khi hiện cửa sổ."""
            if rerender or compact["img"] is None:
                compact["img"] = render_compact(self._info.get("five"), self._info.get("seven"),
                                                scale, light=_taskbar_light())
            ok = _Win.update(hwnd, compact["img"])
            _dbg("vẽ widget gọn:", "OK" if ok else f"THẤT BẠI (lỗi Win32 {ctypes.get_last_error()})")

        # ================= panel mở rộng =================
        fly = {"win": None, "hwnd": None, "rects": {}, "hover": None, "rect": None, "base": None}
        # Menu Win32 chạy vòng lặp riêng nhưng bộ đếm giờ của Tk vẫn kích hoạt bên trong nó.
        # Cú bấm vào mục menu nằm ngoài panel -> poll_outside sẽ đóng panel và HUỶ menu trước khi
        # lệnh kịp chạy. Cờ này làm poll_outside đứng yên trong lúc có menu mở.
        menu_state = {"open": False}

        def show_menu(m, x_root, y_root):
            menu_state["open"] = True
            try:
                m.tk_popup(x_root, y_root)
            finally:
                m.grab_release()
                menu_state["open"] = False
                fly["was_down"] = True  # cú bấm vừa chọn menu đừng bị tính là "bấm ra ngoài"

        def fly_render(rebuild=True):
            """Ảnh panel hiện tại. rebuild=False: dùng lại ảnh nền đã vẽ, chỉ đổi lớp tô sáng hover."""
            if rebuild or fly["base"] is None:
                fly["base"], fly["rects"] = render_flyout(self._info, scale, self._show_abs)
            return apply_hover(fly["base"], fly["rects"], fly["hover"], scale)

        def open_flyout():
            if fly["win"] is not None:
                return
            win = tk.Toplevel(root)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            img = fly_render()
            fw, fh = img.size
            off = round(FM * scale)
            pw = fw - 2 * off
            ph = fh - 2 * off
            l, t, r, b = _work_area(sw, sh)
            wx, wy = root.winfo_x(), root.winfo_y()
            gap = round(8 * scale)
            # Căn mép trái panel với widget nếu widget ở nửa trái màn hình, ngược lại căn mép phải
            if wx + cw / 2 < sw / 2:
                panel_x = wx
            else:
                panel_x = wx + cw - pw
            panel_x = min(max(panel_x, l + gap), r - pw - gap)
            # Widget ở nửa dưới -> mở lên trên (ngay trên taskbar); ở nửa trên -> mở xuống dưới
            if wy + ch / 2 >= sh / 2:
                panel_y = min(wy, b) - ph - gap
            else:
                panel_y = max(wy + ch, t) + gap
            panel_y = min(max(panel_y, t + gap), b - ph - gap)
            win.geometry(f"{fw}x{fh}+{panel_x - off}+{panel_y - off}")
            win.update_idletasks()
            fhwnd = _Win.hwnd(win)
            _Win.make_layered(fhwnd)
            _Win.update(fhwnd, img)         # nội dung trước, rồi mới hiện (xem ghi chú ở tick)
            win.deiconify()
            win.after(150, lambda: fly["win"] is win and _Win.update(fhwnd, fly_render(rebuild=False)))
            fly.update(win=win, hwnd=fhwnd, hover=None,
                       rect=(panel_x - off, panel_y - off, panel_x - off + fw, panel_y - off + fh))
            win.bind("<Motion>", fly_motion)
            win.bind("<Leave>", lambda e: set_hover(None))
            win.bind("<ButtonRelease-1>", fly_click)
            root.after(60, poll_outside)

        def close_flyout():
            win = fly["win"]
            _dbg("close_flyout, đang mở =", win is not None)
            if win is None:
                return
            fly.update(win=None, hwnd=None, hover=None)
            try:
                win.destroy()
            except Exception:
                pass

        def fly_refresh_image():
            if fly["win"] is not None:
                _Win.update(fly["hwnd"], fly_render())

        def hit(ex, ey):
            for name, (x0, y0, x1, y1) in fly["rects"].items():
                if x0 <= ex < x1 and y0 <= ey < y1:
                    return name
            return None

        def set_hover(name):
            if name != fly["hover"] and fly["win"] is not None:
                fly["hover"] = name
                _Win.update(fly["hwnd"], fly_render(rebuild=False))

        def fly_motion(e):
            n = hit(e.x, e.y)
            set_hover(n if n in ("header", "refresh", "settings") else None)

        def move_to_target():
            x, y = target_pos()
            if (x, y) != (root.winfo_x(), root.winfo_y()):
                _dbg("di chuyển widget", (root.winfo_x(), root.winfo_y()), "->", (x, y),
                     "neo =", self._anchor)
                root.geometry(f"+{x}+{y}")
                root.update_idletasks()
                _dbg("vị trí thật của cửa sổ sau khi dời:", _Win.rect(hwnd))

        def apply_anchor(new, notify=True):
            """Đổi điểm neo. notify=False khi thay đổi đến từ bên ngoài (app đã biết rồi)."""
            _dbg("apply_anchor", new, "notify =", notify)
            self._anchor = new
            close_flyout()
            if new == "free":
                # giữ nguyên chỗ đang đứng để widget không bị nhảy; coi đó là vị trí tự do đã lưu
                cur = (root.winfo_x(), root.winfo_y())
                self._position = cur
                if notify and self._cb.get("move"):
                    self._cb["move"](cur)
            else:
                move_to_target()
            if notify and self._cb.get("anchor"):
                self._cb["anchor"](new)

        def add_anchor_menu(m):
            sub = tk.Menu(m, tearoff=0)
            var = tk.StringVar(master=root, value=self._anchor)
            m._anchor_var = var  # giữ tham chiếu kẻo biến bị thu hồi khi menu còn mở
            for key, label in ANCHORS:
                sub.add_radiobutton(label=label, variable=var, value=key,
                                    command=lambda k=key: apply_anchor(k))
            m.add_cascade(label="Điểm neo", menu=sub)

        def settings_menu(x_root, y_root):
            m = tk.Menu(root, tearoff=0)

            def later(name):  # đóng panel rồi chạy việc (việc nặng do app tự đưa sang thread khác)
                return lambda: (close_flyout(), self._call(name))

            m.add_command(label="Đăng nhập claude.ai…", command=later("login"))
            m.add_command(label="Nhập sessionKey…", command=later("session_key"))
            m.add_separator()
            add_anchor_menu(m)
            if self._cb.get("autostart_status") and self._cb.get("autostart_toggle"):
                lbl = "Khởi động cùng Windows" if sys.platform == "win32" else "Khởi động cùng hệ thống"
                auto_var = tk.BooleanVar(master=root, value=bool(self._cb["autostart_status"]()))
                m._auto_var = auto_var
                m.add_checkbutton(label=lbl, variable=auto_var,
                                  command=lambda: (close_flyout(), self._call("autostart_toggle")))
            m.add_command(label="Ẩn widget", command=lambda: (close_flyout(), hide_cmd()))
            m.add_command(label="Thoát", command=later("quit"))
            show_menu(m, x_root, y_root)

        def fly_click(e):
            n = hit(e.x, e.y)
            if n == "header":
                webbrowser.open(USAGE_URL)
                close_flyout()
            elif n in ("reset_five", "reset_seven"):
                self._show_abs = not self._show_abs
                fly_refresh_image()
            elif n == "refresh":
                self._call("refresh")
            elif n == "settings":
                settings_menu(e.x_root, e.y_root)

        def poll_outside():
            """Bấm chuột ra ngoài panel/widget -> đóng panel."""
            if fly["win"] is None:
                return
            if menu_state["open"]:          # đang có menu mở: không xử lý "bấm ra ngoài"
                root.after(60, poll_outside)
                return
            cur = _cursor_and_button()
            if cur:
                cx, cy, down = cur
                if down and not fly.get("was_down"):
                    fx0, fy0, fx1, fy1 = fly["rect"]
                    in_fly = fx0 <= cx < fx1 and fy0 <= cy < fy1
                    in_wid = (root.winfo_x() <= cx < root.winfo_x() + cw
                              and root.winfo_y() <= cy < root.winfo_y() + ch)
                    if not in_fly and not in_wid:
                        close_flyout()
                        return
                fly["was_down"] = down
            root.after(60, poll_outside)

        def toggle_flyout():
            if fly["win"] is None:
                fly["was_down"] = True  # lần bấm này đang diễn ra, đừng tính là "bấm ra ngoài"
                open_flyout()
            else:
                close_flyout()

        # ================= tương tác widget gọn =================
        def hide_cmd():
            self._wanted = False
            self._call("hide")

        drag = {}

        def press(e):
            _dbg("press", e.x_root, e.y_root)
            drag.update(sx=e.x_root, sy=e.y_root, dx=e.x_root - root.winfo_x(),
                        dy=e.y_root - root.winfo_y(), moved=False)

        def motion(e):
            if not drag:
                _dbg("motion bỏ qua (chưa có press)")
                return
            if not drag["moved"] and max(abs(e.x_root - drag["sx"]), abs(e.y_root - drag["sy"])) < CLICK_SLOP:
                return
            if self._anchor != "free":
                # đã neo vào góc -> khoá, không dời widget; nhưng thử kéo thì không phải cú bấm
                drag["dragged_locked"] = True
                return
            if not drag["moved"]:
                close_flyout()
            drag["moved"] = True
            root.geometry(f"+{e.x_root - drag['dx']}+{e.y_root - drag['dy']}")
            root.update_idletasks()  # Tk hay trì hoãn geometry tới lúc rảnh -> ép áp dụng ngay

        def release(_e):
            _dbg("release moved=", drag.get("moved"), "drag=", bool(drag))
            if not drag:
                return
            if drag["moved"]:
                cb = self._cb.get("move")
                if cb:
                    cb((root.winfo_x(), root.winfo_y()))
            elif not drag.get("dragged_locked"):
                toggle_flyout()
            drag.clear()

        def popup_small(e):
            m = tk.Menu(root, tearoff=0)
            if self._cb.get("refresh"):
                m.add_command(label="Làm mới ngay", command=lambda: self._call("refresh"))
            add_anchor_menu(m)
            if self._cb.get("autostart_status") and self._cb.get("autostart_toggle"):
                lbl = "Khởi động cùng Windows" if sys.platform == "win32" else "Khởi động cùng hệ thống"
                auto_var = tk.BooleanVar(master=root, value=bool(self._cb["autostart_status"]()))
                m._auto_var = auto_var
                m.add_checkbutton(label=lbl, variable=auto_var,
                                  command=lambda: self._call("autostart_toggle"))
            m.add_command(label="Ẩn widget", command=hide_cmd)
            show_menu(m, e.x_root, e.y_root)

        root.bind("<ButtonPress-1>", press)
        root.bind("<B1-Motion>", motion)
        root.bind("<ButtonRelease-1>", release)
        root.bind("<Button-3>", popup_small)

        # ---- vòng lặp: xử lý lệnh, giữ cửa sổ nổi trên taskbar, ẩn khi toàn màn hình ----
        tick_n = {"n": 0}
        kick = {"fg": None, "n": 0}

        def tick():
            redraw = False
            try:
                while True:
                    cmd, arg = self._q.get_nowait()
                    if cmd == "show":
                        self._wanted = True
                    elif cmd == "hide":
                        self._wanted = False
                    elif cmd == "info":
                        redraw = True
                    elif cmd == "anchor":
                        apply_anchor(arg, notify=False)
                    elif cmd == "stop":
                        root.destroy()
                        return
            except queue.Empty:
                pass
            fs = _foreground_fullscreen()
            if fs != self._last_fs:
                _dbg("toàn màn hình ở foreground =", fs)
                self._last_fs = fs
            if self._wanted and not fs:
                if not self._shown:
                    _dbg("hiện widget")
                    draw_compact()          # đặt nội dung TRƯỚC khi hiện: tránh lúc được lúc mất do đua với DWM
                    root.deiconify()
                    self._shown = True
                    redraw = False
                    root.after(150, lambda: draw_compact(rerender=False))   # đẩy lại sau khi cửa sổ đã hiện
                    root.after(600, lambda: draw_compact(rerender=False))
                if _Win.ok:
                    # Kéo lên lại khi cửa sổ đang dùng đổi (Start mở/đóng, bấm icon taskbar...) và định kỳ
                    # ~3 s. SetWindowPos không kích hoạt cửa sổ; không làm mỗi tick để khỏi giành z-order
                    # với taskbar (gây nháy khi bấm icon).
                    fg = _Win.u32.GetForegroundWindow()
                    kick["n"] += 1
                    owner_changed = _Win.own_by_taskbar(_Win.hwnd(root))   # explorer khởi động lại -> HWND mới
                    if owner_changed or fg != kick["fg"] or kick["n"] % 8 == 0:
                        kick["fg"] = fg
                        _Win.u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 5
                        _Win.u32.SetWindowPos(_Win.hwnd(root), -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # TOPMOST|NOSIZE|NOMOVE|NOACTIVATE
                        # DWM có thể bỏ nội dung cửa sổ nhiều lớp khi Start che qua -> đẩy hình lại
                        draw_compact(rerender=False)
                        root.after(200, lambda: draw_compact(rerender=False))
                        root.after(700, lambda: draw_compact(rerender=False))
                else:
                    root.attributes("-topmost", True)
                    root.lift()
                # Đã neo: tự đặt lại đúng góc khi bố cục đổi (taskbar, độ phân giải, độ rộng khay...)
                tick_n["n"] += 1
                if self._anchor != "free" and tick_n["n"] % 5 == 0 and fly["win"] is None:
                    move_to_target()
                if redraw:
                    draw_compact()
                    fly_refresh_image()
            elif self._shown:
                _dbg("ẩn widget (wanted=", self._wanted, ", fullscreen=", fs, ")")
                close_flyout()
                root.withdraw()
                self._shown = False
            root.after(TICK_MS, tick)

        root.after(50, tick)
        root.mainloop()
