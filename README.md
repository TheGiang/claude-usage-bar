# Claude Usage Bar

A tiny cross-platform tray app that shows your **Claude usage** — the same numbers
as `claude.ai/settings/usage` — in your menu bar / system tray.

*Ứng dụng nhỏ hiển thị **% usage của Claude** (giống trang `claude.ai/settings/usage`)
ngay trên menu bar (macOS) hoặc system tray (Linux / Windows).*

```
◔ 7%        ← macOS menu bar        [ 7 ]  ← Linux/Windows tray icon

Session (5h): 7%   ·  resets in 4h49m
Week (7d):   38%   ·  resets in 3d10h
Updated: 14:32:07
Refresh now
Quit
```

- **macOS** → text in the menu bar (`○ ◔ ◑ ◕ ●` fills as usage grows).
- **Linux / Windows** → a colored tray icon with the % (green → yellow → red);
  hover for details, right-click for the menu.

## How it works

Calls the same private endpoint the usage page uses:

```
GET https://claude.ai/api/organizations/{org_id}/usage
→ five_hour.utilization  (session 5h %)   +   seven_day.utilization  (weekly %)
```

Auth is automatic: it reads your `claude.ai` login cookie from your browser
(Chrome, Brave, Edge, Chromium, Vivaldi, Opera, Firefox, Safari) via
[`browser-cookie3`](https://github.com/borisbabic/browser_cookie3). Nothing leaves
your machine except the request to claude.ai. Refreshes every 30s.

## Requirements

- Python 3.9+
- Logged in to **claude.ai** in a supported browser
- **macOS**: nothing else
- **Linux**: a system tray (GTK / AppIndicator) — `run.sh` installs the needed
  packages automatically. On **GNOME** enable the
  [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/).

## Quick start (one command)

```bash
git clone <your-repo-url> claude-usage-bar
cd claude-usage-bar
```

**macOS / Linux:**
```bash
./run.sh
```

**Windows** (double-click `run.bat`, or):
```bat
run.bat
```

All of these just call the cross-platform bootstrap `run.py`, which creates a
virtualenv, installs everything (including Linux system packages for the tray), and
launches the app. You can also call it directly on any OS: `python run.py`
(re-install deps with `python run.py --reinstall`).

> On macOS, the first run may ask for **Keychain** access (to read the browser
> cookie) — click **Always Allow**.

## Start automatically at login

```bash
./scripts/install-startup.sh     # macOS: LaunchAgent · Linux: autostart .desktop
./scripts/uninstall-startup.sh   # remove
```

## Configuration (optional)

Everything is auto-detected. Create a config only to override something (e.g. cookie
reading fails, or you use multiple browsers):

```bash
mkdir -p ~/.config/claude-usage
cp config.example.json ~/.config/claude-usage/config.json   # then edit
```

| Field        | Purpose                                                             |
|--------------|---------------------------------------------------------------------|
| `browser`    | Force a browser (`chrome`, `brave`, `firefox`, …)                   |
| `sessionKey` | Paste the claude.ai `sessionKey` cookie manually                    |
| `org_id`     | Force an organization id (default: auto-picks your Claude plan org) |

Or via env: `CLAUDE_USAGE_BROWSER=brave ./run.sh`.

Change the refresh interval by editing `POLL_SECONDS` at the top of `claude_usage_app.py`.

## Project layout

| File | Role |
|------|------|
| `claude_usage_core.py` | cookie + API + formatting (platform-independent) |
| `claude_usage_app.py`  | entry point — picks rumps (macOS) or pystray (Linux/Windows) |
| `run.py`               | cross-platform bootstrap (venv + deps + launch) |
| `run.sh` / `run.bat`   | thin launchers → `run.py` (Unix / Windows) |
| `scripts/*.sh`         | install / uninstall autostart |

## Troubleshooting

- **Shows `⚠︎` / "lỗi"** — you're probably not logged in to claude.ai, or the cookie
  expired → log in again in your browser.
- **`HTTP 401/403`** — `sessionKey` expired; re-login.
- **Can't read cookie** — set `"browser"` in the config, or paste `sessionKey`.
- **Linux: no tray icon** — install/enable an AppIndicator tray (GNOME needs the
  extension above; KDE/XFCE/Cinnamon work out of the box).
- **Logs** — `/tmp/claude-usage-bar.log` (when started via autostart).

## Privacy

Talks only to `claude.ai` using your existing browser session. Your cookie never
leaves your machine. Don't commit your `config.json` — it's gitignored.

## Contributing

Contributions welcome — open an issue or PR. By submitting a contribution you agree
it is licensed to the project under the same license below.

## License

Licensed under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

You may use, modify, and share this software for **any noncommercial purpose**
(personal projects, study, research, nonprofit / educational / government use).
**Commercial or business use is not permitted.** This is a *source-available*
license, not an OSI "open source" license — intentional, so the code stays free to
contribute to but not to be used commercially. Need a commercial license? Open an issue.
