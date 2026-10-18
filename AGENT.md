# AGENT.md — SkyRewind (for Claude)

Read this file first, before any other work in this repo. It is the standing
handoff from 2026-10-17. It tells you what this app is, what you must never
claim, how the server is wired, and how to land work without breaking the
deploy. Matty (the repo owner) works in a scaffolding style: he runs the
commands you give him, pastes back real output, and checks your claims
against real logs, real APIs, and screenshots. Do not cheerlead. Cite
evidence. If you did not see a log, a test run, or a screenshot, say so.

## 1. What SkyRewind is

- Web app for **Nebraska / Iowa MUFON** sky-watch.
- Purpose: log a sighting report, then rewind ADS-B aircraft traffic to
  cross-check whether the reported object matches a **known cooperative
  aircraft broadcasting ADS-B**.
- Production: Dell server `r410` (LAN `192.168.0.169`), repo cloned at
  `~/SkyRewind`, deployed to `/opt/skyrewind` via `sudo ./deploy.sh`.
- Public URL: `https://uap.mattjhagen.xyz` (Cloudflare Tunnel, see §5).
- Local URL: `http://192.168.0.169:5000` (gunicorn, 4 workers).
- Sister site on the same tunnel: `https://mattjhagen.xyz` (Mattys-SDR-Blog,
  Node on `:3001`). Do not touch the blog repo from this repo.

## 2. Honest-wording rules — NON-NEGOTIABLE

These are the trust contract with the MUFON group. Violating them is worse
than a bug.

- The app cross-checks against **cooperative aircraft broadcasting ADS-B**.
  It does NOT query the FAA registry. It does NOT look up registrations.
- Military / non-broadcasting aircraft often will not show.
- `No ADS-B match found` means exactly this: **no cooperative aircraft
  broadcasting ADS-B was detected in that area and time window**.
  It is NOT proof of a UAP. Never write, imply, or illustrate otherwise.
- Never present fake / mock / concept data as live data. Concept art must
  carry the verbatim caption:
  `Artist concept — not live data. Vision for the Midwest UAP tracking view.`
- Never claim the app identifies UAPs, proves anomalous objects, tracks
  objects with radar, or shows live UAP tracks. It does not.
- Never add UFO imagery, alien wording, or sensational claims.
- Keep the existing `No ADS-B match found` wording and the Terminology Note
  meaning wherever they appear.
- Keep the MUFON wording verbatim where it exists:
  - Hero eyebrow: `NEBRASKA / IOWA MUFON • UAP / UFO SKY-WATCH • ADS-B`
  - Hero description: `Built for Nebraska / Iowa MUFON sky-watch. Log a
    sighting, then rewind ADS-B traffic to cross-check it against known
    cooperative aircraft — so the group can tell a known plane from a
    sighting worth a closer look.`

## 3. Repo layout (main branch)

- `frontend/` — vanilla HTML/CSS/JS only. No frameworks. `index.html`,
  `style.css`, `app.js`, `manifest.json`, `sw.js`, `favicon.svg`,
  `favicon.ico`, `icons/`, `assets/` (see §7 for the two new images).
- `backend/app.py` — Flask. Serves `frontend/` under `/static/`, plus
  `/manifest.json`, `/sw.js`, `/favicon.svg`, `/icons/<path>` routes so the
  service worker controls `/` scope. API: `/api/sightings`,
  `/api/positions/live`, `/api/positions/match`, etc. Do not change API
  shapes without an explicit ask.
- `decoder/rtl_adsb_bridge.py` — bridge: spawns `rtl_adsb`, parses `*...;`
  hex lines with pyModeS, CPR-decodes positions, writes
  `/var/run/dump1090-mutability/aircraft.json` in dump1090 format.
  The output path name keeps `dump1090-mutability` for compatibility with
  the logger + dashboard. The dump1090 *program* is gone (see §4).
- `logger/adsb_logger.py` — polls `aircraft.json`, writes DB.
- `server-dashboard/` — separate LAN-only Flask app on `:5001`. See §6.
- `systemd/` — units for `skyrewind-adsb-bridge`, `skyrewind-logger`,
  `skyrewind-web`, `skyrewind-dashboard`, plus `tmpfiles.d/skyrewind.conf`.
- `deploy.sh` — rsyncs repo to `/opt/skyrewind`, builds venv, pip install,
  init DB, installs units + tmpfiles, restarts services. Read it before
  changing it. It uses `systemctl restart`.
- `requirements.txt` — Flask 3.0.0, Werkzeug 3.0.1, gunicorn 21.2.0,
  pytest 8.2.0, **pyModeS==2.22.0** (2.13 does NOT exist on PyPI — do not
  regress this pin).
- `test_frontend_manual.md` — manual frontend checklist. Update it when
  you change the frontend. Backend tests in `tests/` (pytest).

## 4. ADS-B pipeline — current state (2026-10-17 night)

Chain: RTL-SDR dongle (RTLSDRBlog V4L, R820T) → `rtl_adsb` → bridge →
`aircraft.json` → logger → DB → API → map.

- **dump1090-mutability is DEAD and must stay dead.** It is stopped,
  disabled, AND masked (`systemctl mask dump1090-mutability`). It held the
  dongle exclusively (`usb_claim_interface error -6`) and starved the
  bridge. **Never unmask, enable, start, or re-add a dependency on it.**
  The logger unit previously had `Requires=dump1090-mutability.service`
  — that was removed in commit `cee5270` because the mask + Requires
  conflict broke the logger restart. Do not re-add it.
- **Bridge CPR fix landed** in commit `717d34a` ("Fix SkyRewind bridge
  CPR decoding + make manual fixes permanent"): stores even/odd hex +
  timestamps, global `position(even_hex, odd_hex, …)` first, falls back
  to `position_with_ref(hex, RECEIVER_LAT, RECEIVER_LON)`, sanity check
  within 10° of receiver (41.25, -95.95). Also added stderr capture
  (no more `DEVNULL`), rapid-death backoff (5s after 3 deaths <2s),
  and permanent deploy fixes (plugdev, dump1090 stop/disable, tmpfiles).
- **KNOWN OPEN BUG (top priority, see §8):** as of the last check
  (2026-10-17 ~23:54 UTC), the bridge was alive with the dongle to
  itself (`rtl_adsb` child PID alive, no `died` messages, `dump1090 gone`)
  but still **`0 with position`** at 16–25 msgs, 2 aircraft. Earlier,
  an older bridge instance also showed `0 with position` at 222 msgs,
  14 aircraft. CPR has NOT yet produced a position in production.
  Possible causes: weak outdoor feedline delivering only one CPR parity
  (even OR odd, never both within 10s), or a remaining bug in the fix.
  Do not declare CPR fixed until a live Status line shows `Z with
  position` with Z > 0 AND `aircraft.json` has entries with `lat`/`lon`.
- **KNOWN BUG in the new stderr logging:** journalctl showed 20×
  `last stderr: Found 1 device(s):` — that is the FIRST stderr line,
  not the error line. The reader must keep the LAST non-empty stderr
  line (or the last line matching `/error|failed|usb_/i`). Fix this when
  you next touch the bridge.
- **Antenna note:** outdoor 1090 feedline is weak/degraded, not dead.
  Earlier A/B: outdoor ~10 frames/20s vs a test antenna ~29/20s.
  Expect *some* planes near Eppley/Offutt, not full sky, until the
  feedline is improved. Dongle itself is proven good.
- **Service user:** `skyrewind` (uid 996) is in `plugdev` (gid 46) —
  required for USB dongle access. `deploy.sh` adds it idempotently.
- **Output dir:** `/var/run/dump1090-mutability/` is tmpfs (resets on
  reboot). Ownership is restored by `systemd/tmpfiles.d/skyrewind.conf`
  (`d /var/run/dump1090-mutability 0775 skyrewind skyrewind -`) which
  `deploy.sh` installs to `/etc/tmpfiles.d/` + `systemd-tmpfiles --create`.
  Do not move the output path — logger + dashboard read it.
- **Deploy command (on r410, from `~/SkyRewind`):**
  `sudo ./deploy.sh` then verify with
  `journalctl -u skyrewind-adsb-bridge --since "2 minutes ago" | grep -E "Status|ERROR|died|backing"`
  and `cat /var/run/dump1090-mutability/aircraft.json`.

## 5. Tunnel + sister site — DO NOT BREAK

- Tunnel `mattys-sdr-blog`, ID `9e4555f7-5b16-4fac-ba58-93919648ce6c`,
  CLI / locally-managed. Config: `~/.cloudflared/config.yml`:
  `mattjhagen.xyz` → `http://localhost:3001`,
  `www.mattjhagen.xyz` → `http://localhost:3001`,
  `uap.mattjhagen.xyz` → `http://localhost:5000`, catch-all 404.
- DNS CNAMEs must be `<tunnel-id>.cfargotunnel.com` (bare ID = Error 1016).
- **Persistence is now systemd (2026-10-17 night):**
  `/etc/systemd/system/cloudflared.service` (User=matt,
  `ExecStart=/usr/local/bin/cloudflared tunnel --config
  /home/matt/.cloudflared/config.yml run mattys-sdr-blog`,
  Restart=always, enabled) and
  `/etc/systemd/system/mattys-sdr-blog.service` (User=matt,
  `WorkingDirectory=/home/matt/Mattys-SDR-Blog`,
  `ExecStart=/usr/bin/node server.js`, `PORT=3001`, Restart=always,
  enabled). Do NOT run a second foreground `cloudflared` — two
  connectors flap the tunnel. Do NOT use the old `/tmp/*.service` files
  from the blog `deploy.sh` without verifying they match this config.
- Error guide: 1033 = tunnel connector down; 502 = tunnel up, origin
  down (check the origin service on `:5000` / `:3001`); 1016 = DNS
  CNAME content wrong.

## 6. Server dashboard (LAN-only)

- Separate Flask app: `server-dashboard/app.py`, bind `0.0.0.0:5001`.
- **LAN-only by design. NEVER add a dashboard hostname to
  `~/.cloudflared/config.yml`.** It exposes service status + log lines.
- `GET /` = kiosk page, `GET /api/status` = JSON (services, pipeline,
  system, ports, last 5 bridge log lines truncated). No query params,
  no `shell=True`, fixed allowlist, 3s timeouts, failure → "unknown".
- `looping` = ≥5 `rtl_adsb died` in last 100 journal lines in 2 min.
- Read-only v1: no restart buttons, no shell buttons, no auth form.
- Verify on LAN: `curl -s http://localhost:5001/api/status | python3 -m json.tool`
  must show real 2026 timestamps. (A 2024-dated JSON blob once appeared
  in a pasted session — that was mock/example output, not live data.)

## 7. Images (2026-10-17 night — NOT YET WIRED)

Two source images are already in the repo at `frontend/assets/` and are
deployed to `/opt/skyrewind` by `deploy.sh`, but are NOT yet referenced
by any HTML/CSS. Wire them per the prompt in §8, Job 2.

- `frontend/assets/hero-banner.jpg` (898K → compress to ~1920px / <500K
  as part of the job) — AetherWatch concept art: dense dashboard mock
  with radar rings, fake flight labels, and a fake `[OBJECT 047 (UAP)]`
  box (84,800 FT, 1,920 KTS). **It is NOT live data. Never use it as a
  hero background behind the title** (text-on-text clash, wrong brand
  "AetherWatch", fake UAP track). Use ONLY as a concept card BELOW the
  hero stats row, with the verbatim caption from §2.
- `frontend/assets/favicon-source.jpg` (284K) — teal crosshair / radar
  target on dark navy, glowing cyan center dot. Clean: no text, no fake
  data. This REPLACES the gold-play favicon + PWA icons from commit
  `e21478f`. Do not leave two favicon designs. Do NOT recolor it gold
  (teal vs site gold #FBBF24 mismatch is accepted for now).
- Delete any duplicate copies: originals `headerimg.jpeg` /
  `favicon.jpeg` were removed from the repo root. Commit only the
  `frontend/assets/` copies + generated icons.

## 8. Tomorrow's work (in order)

### Job 1 — Prove or fix bridge CPR (TOP PRIORITY, backend)
1. On r410, wait 2 min after the current bridge start, then check:
   `journalctl -u skyrewind-adsb-bridge --since "3 minutes ago" | grep -E "Status|ERROR|died|backing"`
   and `cat /var/run/dump1090-mutability/aircraft.json`.
2. PASS = Status line from the CURRENT bridge PID with `Z with position`,
   Z > 0, AND `aircraft.json` entries with `lat`/`lon`. Then hard-refresh
   `https://uap.mattjhagen.xyz` — planes should draw.
3. FAIL = still `0 with position` at 100+ msgs. Then diagnose: is the
   bridge receiving BOTH even and odd CPR frames for the same ICAO within
   10s? Add a debug counter/log (even-only vs odd-only vs paired aircraft)
   or inspect raw `rtl_adsb` output for `oe_flag` distribution. Fix the
   pairing/fallback logic, add/extend `tests/test_bridge_cpr.py` (known
   pyModeS pair `8D40621D58C382D690C8AC2863A7` /
   `8D40621D58C386435CC412692AD6`, ICAO `40621D`), and also fix the
   stderr-logging bug from §4 (log LAST stderr line, not first).
4. Constraints: no frontend changes, no API changes, no new deps,
   pyModeS stays 2.22.0, `to_dict()` still omits aircraft with no
   position, never crash on a bad frame / `position()` exception /
   missing output dir. Do NOT unmask dump1090. Do NOT re-add
   `Requires=dump1090` anywhere.

### Job 2 — Wire the two images (frontend-only)
Starting point: `frontend/assets/hero-banner.jpg` + `frontend/assets/favicon-source.jpg`
already in repo. Replace (do not duplicate) the `e21478f` favicon.
- **Concept card:** after `.stats-row`, before `#map-view`, add
  `<figure class="concept-banner">` with `<img src="assets/hero-banner.jpg"
  alt="Artist concept of a Midwest UAP tracking view over Omaha at night"
  onerror="this.closest('figure').style.display='none'">` + verbatim
  `<figcaption>` from §2. CSS per the prompt Matty holds (max-width
  1400px, 20px radius, muted caption). Do NOT add a background image to
  `.hero-section`. Do NOT change hero text/palette. Compress hero-banner
  to ~1920px / <500K with PIL, same filename.
- **Favicon:** generate from `favicon-source.jpg` with PIL:
  `frontend/favicon.ico` (16/32/48), `frontend/favicon-32.png`,
  `frontend/icons/icon-192.png`, `frontend/icons/icon-512.png`
  (maskable, mark inside central 80%), `frontend/icons/apple-touch-icon.png`
  (180×180). Update `index.html` head links (remove old gold-play
  `favicon.svg` file + link if present), update `manifest.json` icons[]
  (same names, new content, validate with `python3 -m json.tool`).
  Keep name/short_name/display/background/theme. Do NOT recolor gold.
- **Flask/static check:** favicon/icons/hero must resolve at
  `/favicon.ico`, `/favicon-32.png`, `/icons/*.png`,
  `/static/assets/hero-banner.jpg`. Add minimal routes only if needed.
  Update `deploy.sh` only if it excludes `frontend/assets/` or
  `frontend/icons/`.
- **Constraints:** no backend API changes, no new deps, no wording
  changes except the new figcaption. No hero/palette/filter/map changes.

### Job 3 — Verify the earlier landings (read-only checks)
These commits landed but their on-device verification is incomplete.
Check each on `https://uap.mattjhagen.xyz` (hard refresh) + LAN:
- `836d9c3` map/scroll: page scrolls top-to-footer, map 600px desktop /
  420px mobile, wheel scrolls page before click / zooms after click,
  status strip BELOW map (not floating).
- MUFON wording: hero eyebrow + hero description + About modal +
  README match §2 verbatim.
- `e21478f` PWA/notifications (superseded in part by Job 2 favicon):
  manifest valid JSON, SW registered at `/sw.js`, notify toggle works
  (toast when visible / system when hidden, no duplicates, old sightings
  do NOT notify on first enable). Test install on `localhost:5000` or
  HTTPS — plain `http://192.168.0.169:5000` may refuse install (expected,
  not a bug). Group chat is NOT built — README roadmap only.
- `e5dd1f8` dashboard: `curl localhost:5001/api/status` shows real
  2026 timestamps, kiosk fits 1080p, 10s refresh, dashboard NOT reachable
  via `uap.mattjhagen.xyz` (verify 404/no route).

## 9. Working rules

- **One job = one commit.** Frontend, backend, and deploy fixes do not
  share a commit unless the job genuinely spans them.
- **Before pushing:** `git pull --rebase` first. Remote moves while
  Matty works. **Never `push --force`.** If a rebase conflicts on a line
  you did not intend to touch, stop and ask.
- **Do not commit unrelated files.** Check `git status --short` and
  `git diff` before every commit. `requirements.txt`, units, and deploy
  scripts change only when the job says so.
- **Proof block (every commit):** paste FULL `python -m pytest tests/ -q`
  output; paste the `grep` checks the job specified; paste
  `git log --oneline -3` + `git status` clean; list every file changed.
  Never claim "all tests pass" without the log. Never claim a deploy
  succeeded without deploy output. Never present mock/example JSON as
  live `curl` output.
- **No secrets in chat, code, or commits.** No passwords, API keys,
  tokens, or credential values. Credential setup stays machine-local.
- **No bookings, purchases, cancellations, money movement, or trading
  activity** without Matty's explicit per-action go-ahead.
- **Frontend:** vanilla only, keep all element IDs and API endpoints,
  keep theme toggle + tiles + responsive 375px/1400px + modal 90vh
  scroll. Gold/navy palette: dark accent `#FBBF24`, hover `#F59E0B`,
  bg `#0B1220`/`#111A2E`/`#16213A`; light accent `#B45309`.
  No WordPress/Elementor (Matty builds from source).
- **When in doubt, stop and ask Matty.** A stopped job with a clear
  question beats a pushed guess.

## 10. Quick reference

- Repo: `https://github.com/Mattjhagen/SkyRewind` (public, MIT, main).
- r410 checkout: `~/SkyRewind`. Deploy: `sudo ./deploy.sh` from repo root.
- Services: `skyrewind-adsb-bridge`, `skyrewind-logger`, `skyrewind-web`
  (`:5000`), `skyrewind-dashboard` (`:5001`), `cloudflared`,
  `mattys-sdr-blog` (`:3001`).
- Receiver: lat 41.25, lon -95.95 (Omaha, EN09xv).
- Bridge output: `/var/run/dump1090-mutability/aircraft.json`.
- Tunnel config: `~/.cloudflared/config.yml`.
- Recent commits (newest first at handoff): `cee5270` (remove dump1090
  Requires from logger), `beb9a68` (pyModeS 2.13 → 2.22.0),
  `717d34a` (bridge CPR + permanent fixes), `e5dd1f8` (dashboard),
  `e21478f` (favicon/PWA/notifications), `836d9c3` (map/scroll),
  `ef5570b` (filter/search fixes), `ed91899` (SDR Blog look),
  `118eb51` (theme merge), `ca14436` (bridge).
