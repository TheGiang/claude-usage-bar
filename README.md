# Claude Usage Bar

A tiny cross-platform tray app that shows your **Claude usage** — the same numbers
as `claude.ai/settings/usage` — in your menu bar (macOS), system tray, or taskbar widget (Windows / Linux).

*Ứng dụng nhỏ gọn hiển thị **% token usage của Claude** (giống trang `claude.ai/settings/usage`)
ngay trên menu bar (macOS), khay hệ thống system tray hoặc thanh taskbar (Windows / Linux).*

<p align="center">
  <img src="docs/screenshot-macos.png" alt="Claude Usage Bar on the macOS menu bar" width="420">
</p>

- **macOS** → percentage in the menu bar (`○ ◔ ◑ ◕ ●` fills as usage grows; turns **red** above 80%).
- **Windows / Linux** → a colored tray icon showing the exact % (green → yellow → red); hover for details, right-click for full menu.
- **Windows Taskbar Widget** → an elegant floating widget directly on your taskbar (e.g. next to the Start button / Weather): `✦ Session 33% ▬ | 📅 Week 69% ▬  ⌄`. Click to open a full token details panel.
- **Click the Session / Week line** to toggle reset time between relative (`còn 4h52m`) and absolute (`lúc 02:40 11/10`) — the menu stays open.

---

## How it works

Calls the same private endpoint the usage page uses:

```
GET https://claude.ai/api/organizations/{org_id}/usage
→ five_hour.utilization  (session 5h %)   +   seven_day.utilization  (weekly %)
```

Auth is automatic: it reads your `claude.ai` login cookie from your browser
(Chrome, Brave, Edge, Chromium, Vivaldi, Opera, Firefox, Safari) via
[`browser-cookie3`](https://github.com/borisbabic/browser_cookie3). Nothing leaves
your machine except the direct request to `claude.ai`. Refreshes every 30s.

> **Windows Note:** Chrome & Edge on Windows protect cookies using *App-Bound Encryption*. If reading cookies from your default browser is blocked, you can easily log in via the app's built-in login tool (right-click tray → **Đăng nhập claude.ai…**) or paste your `sessionKey` once.

---

## Requirements

- **Python 3.9+**
- Logged in to **claude.ai** in a supported browser (or provide a `sessionKey`)

**Platform details:**
- **Windows**: Windows 10 hoặc 11. Cần cài đặt Python 3.9+ từ [python.org](https://www.python.org/downloads/) (nhớ tích chọn **"Add python.exe to PATH"** khi cài đặt). Không cần cài đặt C++ Build Tools (hệ thống tự động xử lý fallback nếu thiếu wheel binary `lz4`).
- **macOS**: Python 3.9+ — không cần cài gì thêm.
- **Linux**: Hỗ trợ khay hệ thống (GTK / AppIndicator) — `run.sh` sẽ tự động cài các gói cần thiết. Trên **GNOME**, hãy bật [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/).

---

## Quick start (Khởi động nhanh)

Clone repository về máy:
```bash
git clone <your-repo-url> claude-usage-bar
cd claude-usage-bar
```

### Windows
Chỉ cần **double-click vào file `run.bat`**, hoặc chạy trong terminal:

**Trong Command Prompt (cmd):**
```bat
run.bat
```

**Trong PowerShell:**
```powershell
.\run.bat
```

- `run.bat` sẽ tự động thiết lập môi trường ảo riêng `.venv-win`, cài đặt dependencies và khởi chạy ứng dụng **hoàn toàn chạy nền** (không giữ cửa sổ console).
- Cửa sổ cmd sẽ tự tắt sau vài giây. Hãy tìm icon ứng dụng ở khay hệ thống (góc dưới bên phải taskbar — nếu không thấy, hãy bấm vào mũi tên **`^`** để xem các icon ẩn).
- Gặp lỗi có thể xem log tại: `%TEMP%\claude-usage-bar.log`.

### macOS / Linux
Chạy script:
```bash
./run.sh
```

Tất cả các launcher đều gọi script bootstrap đa nền tảng `run.py`. Script này sẽ kiểm tra môi trường, tạo virtualenv (`.venv` trên macOS/Linux, `.venv-win` trên Windows), tự động cài đặt thư viện và khởi động app. Bạn cũng có thể gọi trực tiếp: `python run.py` (hoặc `python run.py --reinstall` để cài lại toàn bộ thư viện).

> Trên macOS, trong lần chạy đầu tiên hệ thống có thể hỏi quyền truy cập **Keychain** (để đọc cookie trình duyệt) — hãy chọn **Always Allow**.

---

## Windows Guide & Features (Chi tiết dành cho Windows)

### 1. System Tray Icon (Khay hệ thống)
- Nằm ở góc dưới bên phải màn hình (Notification Area).
- Hiển thị trực tiếp con số % session hiện tại với màu sắc thông minh: **Xanh lá** (< 75%) → **Vàng** (75-89%) → **Đỏ** (≥ 90%).
- **Rê chuột (Hover)** qua icon để xem tóm tắt thông số session 5h và tuần 7d.
- **Chuột phải** vào icon để mở menu:
  - Xem chi tiết % và thời gian reset của Session 5h & Giới hạn tuần.
  - Bấm vào dòng Session/Tuần để chuyển đổi giữa thời gian đếm ngược (`còn 3h20m`) và mốc giờ chính xác (`lúc 18:30`).
  - **Hiện số ở góc taskbar**: Bật/tắt thanh Taskbar Widget.
  - **Điểm neo widget**: Chọn vị trí gắn widget trên màn hình.
  - **Khởi động cùng Windows**: Bật/tắt tự khởi động cùng máy tính (có dấu tick hiển thị trạng thái).
  - **Đăng nhập claude.ai…**: Mở cửa sổ đăng nhập tự động.
  - **Nhập sessionKey…**: Nhập thủ công sessionKey từ trình duyệt.
  - **Làm mới ngay**: Cập nhật chỉ số token tức thì.
  - **Thoát**: Tắt hoàn toàn ứng dụng.

### 2. Floating Taskbar Widget (Hiện số ở góc taskbar)
Trên Windows, khay hệ thống chỉ nằm ở góc phải, vì vậy ứng dụng tích hợp sẵn một **Taskbar Widget** nổi tinh tế:
- **Cách bật**: Chuột phải icon tray → tick chọn **Hiện số ở góc taskbar**.
- **Hiển thị trực tiếp trên taskbar**: Widget vẽ đè trực tiếp lên thanh taskbar không nền, không viền: `✦ Session 33% ▬ | 📅 Week 69% ▬  ⌄`.
- **Thanh tiến trình (Progress bar)**: Màu xanh dương / xanh lá bình thường, chuyển sang **vàng từ 75%** và **đỏ từ 90%** (có thể tuỳ chỉnh `WARN_AT` / `DANGER_AT` trong `claude_usage_widget.py`).
- **Click vào widget để mở Flyout Panel**:
  - Dòng tiêu đề có thể click để mở thẳng trang `claude.ai/settings/usage`.
  - Hiển thị chi tiết *Phiên hiện tại* và *Giới hạn tuần*. Bấm vào dòng thời gian để đổi giữa đếm ngược (`Còn 4h30m`) và giờ reset (`Lúc 17:45`).
  - Các nút tác vụ nhanh: *Làm mới ngay*, *Cài đặt* (Đăng nhập, Dán sessionKey, Đổi điểm neo, Ẩn widget, Thoát).
  - Bấm ra ngoài cửa sổ để tự động đóng panel.
- **Điểm neo (Anchoring)**:
  - Chọn điểm neo trong menu *Cài đặt → Điểm neo* của panel, hoặc chuột phải vào widget / tray menu:
    - **bottom-left**: Nằm góc trái dưới cạnh nút Start / widget Thời tiết (mặc định).
    - **bottom-right**: Nằm góc phải dưới, ngay cạnh khay hệ thống.
    - **top-left / top-right**: Nằm ở góc trên màn hình (thích hợp cho ai để taskbar ở trên).
    - **Tự do (free)**: Cho phép dùng chuột trái kéo thả widget tới bất kỳ vị trí nào trên màn hình (vị trí sẽ được lưu lại).
  - Khi được ghim theo điểm neo, widget sẽ tự căn chỉnh lại vị trí khi thay đổi độ phân giải màn hình hoặc kích thước taskbar.
- **Tính năng thông minh**:
  - Tự động ẩn khi có ứng dụng chạy toàn màn hình (chơi game, xem phim full screen).
  - Tự động đổi màu chữ sáng/tối phù hợp với màu nền taskbar của Windows (hỗ trợ cả Light mode và Dark mode).

### 3. Đăng nhập & Xác thực trên Windows

Do Google Chrome và Microsoft Edge trên Windows mã hoá cookie bằng *App-Bound Encryption*, việc tự động đọc cookie có thể yêu cầu quyền Administrator. Ứng dụng cung cấp 2 giải pháp đơn giản:

#### Cách 1: Đăng nhập trực tiếp từ ứng dụng (Khuyên dùng - Đơn giản nhất)
1. Chuột phải icon tray hoặc chọn từ menu của widget → bấm **Đăng nhập claude.ai…**.
2. Ứng dụng sẽ tự mở một cửa sổ trình duyệt (Chrome/Edge/Brave) với một *profile tạm thời* (hoàn toàn không ảnh hưởng tới dữ liệu trình duyệt chính của bạn).
3. Đăng nhập tài khoản Claude bình thường (Google, email hoặc mã OTP).
4. Ngay khi đăng nhập xong, ứng dụng sẽ tự động trích xuất session lưu vào `config.json`, đóng cửa sổ tạm và làm mới số liệu ngay.

#### Cách 2: Nhập sessionKey thủ công (Hoạt động trên mọi OS)
1. Mở trình duyệt đang đăng nhập `claude.ai` → bấm `F12` (DevTools).
2. Chuyển sang tab **Application** (Chrome/Edge) hoặc **Storage** (Firefox) → **Cookies** → chọn `https://claude.ai`.
3. Tìm cookie `sessionKey` và copy giá trị của nó (dạng `sk-ant-sid01-...`).
4. Chuột phải icon tray → chọn **Nhập sessionKey…** và dán vào. Ứng dụng sẽ tự động lưu và làm mới.

*(Bạn cũng có thể tự dán vào file `%USERPROFILE%\.config\claude-usage\config.json` theo định dạng `{"sessionKey": "sk-ant-sid01-..."}`).*

---

## Start automatically at login (Khởi động cùng máy tính / Windows)

### 1. Bật/tắt trực tiếp trong ứng dụng (Đơn giản nhất - Khuyên dùng)
- **Từ khay hệ thống (System Tray)**: Chuột phải vào icon tray → tick chọn **Khởi động cùng Windows**.
- **Từ Taskbar Widget**: Click vào widget → chọn *Cài đặt* (hoặc chuột phải lên widget) → tick chọn **Khởi động cùng Windows**.
- Khi được bật, ứng dụng sẽ tự động tạo shortcut chạy ngầm trong thư mục Startup của Windows. Bỏ chọn để gỡ bỏ.

### 2. Sử dụng script đi kèm
Bạn cũng có thể chạy các file script có sẵn trong thư mục `scripts/`:

**Chạy bằng cách double-click hoặc qua terminal (CMD / PowerShell):**
```bat
# Cài đặt tự khởi động cùng Windows
scripts\install-startup.bat

# Gỡ bỏ tự khởi động và tắt ứng dụng
scripts\uninstall-startup.bat
```

### 3. Cài đặt thủ công (Không bắt buộc)
Nhấn tổ hợp phím `Win + R` → gõ `shell:startup` → bấm `Enter`. Thư mục Startup của Windows sẽ mở ra. Tạo một shortcut trỏ tới file `run.bat` của dự án và dán vào thư mục này.

---

### Khởi động cùng hệ thống trên macOS / Linux
```bash
./scripts/install-startup.sh     # macOS: LaunchAgent · Linux: autostart .desktop
./scripts/uninstall-startup.sh   # Gỡ bỏ tự khởi động
```

---

## Configuration (Cấu hình nâng cao - Tuỳ chọn)

Mặc định ứng dụng tự động dò tìm cấu hình. Bạn chỉ cần tạo file `config.json` khi muốn ghi đè cài đặt (chọn trình duyệt cố định, đổi điểm neo, ...):

**Vị trí file cấu hình:**
- **Windows**: `%USERPROFILE%\.config\claude-usage\config.json`
- **macOS / Linux**: `~/.config/claude-usage/config.json`

**Cách tạo file cấu hình mẫu:**
- **Windows (PowerShell):**
  ```powershell
  New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\claude-usage"
  Copy-Item config.example.json "$env:USERPROFILE\.config\claude-usage\config.json"
  ```
- **Windows (Command Prompt):**
  ```cmd
  if not exist "%USERPROFILE%\.config\claude-usage" mkdir "%USERPROFILE%\.config\claude-usage"
  copy config.example.json "%USERPROFILE%\.config\claude-usage\config.json"
  ```
- **macOS / Linux:**
  ```bash
  mkdir -p ~/.config/claude-usage
  cp config.example.json ~/.config/claude-usage/config.json
  ```

| Trường          | Ý nghĩa                                                              |
|-----------------|----------------------------------------------------------------------|
| `browser`       | Chỉ định trình duyệt lấy cookie (`chrome`, `edge`, `brave`, `firefox`, …) |
| `sessionKey`    | Điền thủ công chuỗi cookie `sessionKey`                              |
| `org_id`        | Chỉ định organization ID (mặc định tự nhận org theo plan của bạn)    |
| `widget`        | `true` / `false` để bật/tắt widget taskbar                            |
| `widget_anchor` | Điểm neo widget: `"bottom-left"`, `"bottom-right"`, `"top-left"`, `"top-right"`, `"free"` |

**Thiết lập qua biến môi trường:**
- **Windows (PowerShell):** `$env:CLAUDE_USAGE_BROWSER="brave"; .\run.bat`
- **Windows (CMD):** `set CLAUDE_USAGE_BROWSER=brave && run.bat`
- **macOS / Linux:** `CLAUDE_USAGE_BROWSER=brave ./run.sh`

Bạn cũng có thể thay đổi chu kỳ làm mới bằng cách chỉnh giá trị `POLL_SECONDS` (mặc định 30s) ở đầu file `claude_usage_app.py`.

---

## Project layout (Cấu trúc dự án)

| Tệp tin | Vai trò |
|---------|---------|
| `claude_usage_core.py` | Lõi xử lý API Claude, đọc cookie & định dạng dữ liệu (đa nền tảng) |
| `claude_usage_app.py`  | Điểm khởi chạy chính — tự động chọn rumps (macOS) hoặc pystray (Windows / Linux) |
| `claude_usage_widget.py`| Floating Taskbar Widget trong suốt & Flyout panel chi tiết (Windows / Linux) |
| `claude_usage_login.py`| Cửa sổ đăng nhập tạm thời qua Chrome/Edge để tự động lưu session |
| `run.py`               | Bootstrap script tự động tạo venv, cài dependencies phù hợp và khởi chạy |
| `run.bat` / `run.sh`   | File chạy nhanh tiện lợi (Windows batch / Unix shell script) |
| `scripts/`             | Script cài đặt/gỡ tự khởi động (`.bat` cho Windows, `.sh` cho macOS/Linux) |

---

## Troubleshooting (Xử lý sự cố)

- **Hiển thị biểu tượng `⚠︎` hoặc "lỗi"**:
  - Bạn chưa đăng nhập `claude.ai` hoặc cookie đã hết hạn. Hãy đăng nhập lại trên trình duyệt, hoặc chuột phải icon tray chọn **Đăng nhập claude.ai…**.
- **Lỗi `HTTP 401/403`**:
  - `sessionKey` đã hết hạn. Hãy đăng nhập lại hoặc dán sessionKey mới.
- **Không đọc được cookie trên Windows (Chrome / Edge)**:
  - Do cơ chế bảo mật *App-Bound Encryption* của Chrome/Edge.
  - **Khắc phục**: Dùng tính năng **Đăng nhập claude.ai…** từ icon tray (tiện nhất), hoặc chọn **Nhập sessionKey…**, hoặc chạy Command Prompt bằng quyền **Run as Administrator**, hoặc dùng Firefox.
- **Windows: Không thấy icon khay hệ thống**:
  - Windows mặc định ẩn các icon mới. Bấm vào mũi tên **`^`** ở góc phải taskbar để xem icon ẩn. Kéo thả icon Claude Usage ra ngoài taskbar để luôn hiển thị.
- **Linux: Không hiện icon tray**:
  - Cần môi trường hỗ trợ AppIndicator. Trên GNOME, hãy cài đặt extension [AppIndicator Support](https://extensions.gnome.org/extension/615/appindicator-support/).
- **Xem file log chi tiết khi gặp sự cố**:
  - **Windows**: `%TEMP%\claude-usage-bar.log` (có thể mở bằng Notepad hoặc chạy `Get-Content $env:TEMP\claude-usage-bar.log -Tail 50` trong PowerShell).
  - **macOS / Linux**: `/tmp/claude-usage-bar.log`.
  - Có thể bật chế độ debug cho widget bằng cách đặt biến môi trường `CLAUDE_USAGE_DEBUG=1`.

---

## Privacy (Quyền riêng tư)

Ứng dụng chỉ kết nối trực tiếp tới `https://claude.ai` bằng phiên đăng nhập của chính bạn trên máy. Cookie và thông tin tài khoản không bao giờ bị gửi đi bất kỳ đâu khác ngoài máy tính của bạn. File cấu hình `config.json` chứa `sessionKey` đã được cấu hình trong `.gitignore` để không bị đẩy lên kho lưu trữ code.

---

## Contributing

Mọi đóng góp (pull request, báo lỗi, góp ý tính năng) đều được hoan nghênh. Khi đóng góp mã nguồn, bạn đồng ý áp dụng giấy phép mã nguồn bên dưới cho các đóng góp của mình.

---

## License

Phát hành theo giấy phép **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

Bạn được quyền sử dụng, sửa đổi và chia sẻ phần mềm này cho **mục đích phi thương mại** (dự án cá nhân, học tập, nghiên cứu, tổ chức phi lợi nhuận / giáo dục). **Nghiêm cấm sử dụng cho mục đích thương mại hoặc kinh doanh.**
