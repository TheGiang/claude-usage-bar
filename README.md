# Claude Usage Bar

A tiny macOS menu bar app that shows your **Claude usage** — the same numbers as
`claude.ai/settings/usage` — right in your menu bar.

*Ứng dụng menu bar macOS hiển thị **% usage của Claude** (giống trang `claude.ai/settings/usage`) ngay trên thanh menu.*

```
◔ 7%        ← menu bar (session 5h + fill glyph)

Session (5h): 7%   ·  resets in 4h49m
Week (7d):   38%   ·  resets in 3d10h
Updated: 14:32:07
Refresh now
Quit
```

The glyph fills up as usage grows: `○ ◔ ◑ ◕ ●`.

## How it works

Calls the same private endpoint the usage page uses:

```
GET https://claude.ai/api/organizations/{org_id}/usage
→ { "five_hour": {"utilization": N, "resets_at": ...},
    "seven_day": {"utilization": N, "resets_at": ...} }
```

- **`five_hour.utilization`** → the 5-hour session window %
- **`seven_day.utilization`** → the weekly %

Auth is automatic: the app reads your `claude.ai` login cookie straight from your
browser (Chrome, Brave, Edge, Chromium, Vivaldi, Opera, Firefox, or Safari) using
[`browser-cookie3`](https://github.com/borisbabic/browser_cookie3). Nothing is sent
anywhere except claude.ai. Refreshes every 30s.

## Requirements

- macOS
- Python 3.9+
- A supported browser where you are **logged in to claude.ai**

## Quick start

```bash
git clone <your-repo-url> claude-usage-bar
cd claude-usage-bar
./run.sh
```

`run.sh` creates a virtualenv, installs deps, and launches the app. Look at the
right side of your menu bar — you'll see `◔ 7%`.

> On first run macOS may ask for **Keychain** access (to read the browser cookie).
> Click **Always Allow**.

## Start automatically at login

```bash
./scripts/install-startup.sh     # install + start now
./scripts/uninstall-startup.sh   # remove
```

The install script auto-detects the repo path, so it works from wherever you cloned it.

## Configuration (optional)

Everything is auto-detected. Only create a config if you need to override something —
e.g. cookie reading fails, or you use multiple browsers:

```bash
mkdir -p ~/.config/claude-usage
cp config.example.json ~/.config/claude-usage/config.json
# then edit it
```

| Field        | Purpose                                                              |
|--------------|----------------------------------------------------------------------|
| `browser`    | Force a specific browser (`chrome`, `brave`, `firefox`, …)           |
| `sessionKey` | Paste the claude.ai `sessionKey` cookie manually                     |
| `org_id`     | Force an organization id (default: auto-picks your Claude plan org)  |

You can also force the browser via env: `CLAUDE_USAGE_BROWSER=brave ./run.sh`.

## Change the refresh interval

Edit `POLL_SECONDS` at the top of `claude_usage_bar.py` (default `30`).

## Troubleshooting

- **Menu bar shows `⚠︎`** — open the menu to read the error. Usually you're not logged
  in to claude.ai, or the cookie expired → log in again in your browser.
- **`HTTP 401/403`** — `sessionKey` expired; re-login to claude.ai.
- **Can't read cookie** — set `"browser"` in the config, or paste `sessionKey` manually.
- **Logs** — `/tmp/claude-usage-bar.log` (when started via the launch agent).

## Privacy

The app talks only to `claude.ai`, using your existing browser session. Your cookie
never leaves your machine. Do **not** commit your `config.json` — it's gitignored.

## Contributing

Contributions are welcome — open an issue or PR. By submitting a contribution you
agree it is licensed to the project under the same license below.

## License

Licensed under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

You may use, modify, and share this software for **any noncommercial purpose**
(personal projects, study, research, and nonprofit / educational / government use).
**Commercial or business use is not permitted.** This is a *source-available*
license, not an OSI "open source" license — that's intentional, so the code stays
free to contribute to but not to be used commercially. Need a commercial license?
Open an issue.
