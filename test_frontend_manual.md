# SkyRewind Frontend Manual Test Checklist

## Theme Toggle Tests
- [ ] Page loads with dark theme by default (gold #FBBF24 accent on deep navy #0B1220 bg)
- [ ] Click theme toggle button - switches to light theme (dark gold #B45309 accent on white)
- [ ] Verify light theme uses OSM standard tiles (tile.openstreetmap.org)
- [ ] Verify dark theme uses Esri dark tiles (ArcGIS World_Dark_Gray_Base)
- [ ] Reload page - theme persists (checks localStorage key: skyrewind-theme)
- [ ] Theme toggle icon switches between sun and moon
- [ ] Both themes have proper contrast (gold colors pass WCAG)

## Hero + Receiver Card Tests
- [ ] Hero section displays: "SKY WATCH • ADS-B • OMAHA, NE" eyebrow in gold
- [ ] Hero title: "Live Sky Over Omaha" displays properly
- [ ] Hero description displays the 30-day rewind explainer
- [ ] Receiver card shows on right side of hero
- [ ] Receiver status badge shows "OFFLINE" on load, "LIVE" when data arrives
- [ ] Receiver card "Aircraft" count matches live map count
- [ ] Receiver card "Last update" matches live strip last update
- [ ] Receiver card shows static values: "RTL-SDR" and "Outdoor 1090"
- [ ] Hero stacks properly on mobile (receiver card below title at <800px)

## Stats Row Tests
- [ ] Stats row displays below hero with 3 stat cards
- [ ] "Aircraft Tracked" stat matches live count
- [ ] "Last Update" stat matches live update time
- [ ] "Location" stat shows "Omaha, NE / Grid EN09xv"
- [ ] Stats update when live positions update (every 10s)
- [ ] Stats cards have rounded corners (20px border-radius)

## Search + Filter Pills Tests
- [ ] Search input appears above feed view with placeholder text
- [ ] Typing in search filters feed cards by reporter name or description
- [ ] "All" pill is active by default (gold background)
- [ ] Clicking "Live" pill filters to sightings with matches
- [ ] Clicking "Rewind" pill filters to sightings with matches
- [ ] Clicking "No ADS-B match" pill filters to sightings without matches
- [ ] Filter pills have rounded pill shape (border-radius 9999px)
- [ ] Active pill has gold background with dark navy text
- [ ] Feed count updates based on visible filtered results

## Rounded Cards Tests
- [ ] Match items (.match-item) have 20px border-radius
- [ ] Feed cards (.feed-card) have 20px border-radius
- [ ] First match item has accent gold left border
- [ ] Cards have proper spacing (16px padding)
- [ ] Cards use theme background and border colors

## Gold CTA Button Tests
- [ ] "Report Sighting" button has gold background (#FBBF24 dark, #B45309 light)
- [ ] Button has dark navy text (#0B1220)
- [ ] Button has pill shape (border-radius 9999px)
- [ ] Button opens report modal when clicked
- [ ] Button hover state uses accent-hover color

## Existing Features Still Work
- [ ] MAP/FEED toggle switches views
- [ ] Control bar: Sighting select works
- [ ] Control bar: Load button loads sighting
- [ ] Control bar: Radius input filters results
- [ ] Control bar: Time slider adjusts from -10 to +10 minutes
- [ ] Time offset displays correctly (±N min)
- [ ] Live updates every 10 seconds
- [ ] Status dot turns green when live
- [ ] Aircraft markers appear with correct rotation
- [ ] Sighting marker appears with bearing line (if bearing set)
- [ ] Match panel displays "Rewind & Match" header
- [ ] "No ADS-B match found" displays with exact wording
- [ ] Match panel subtitle: "No cooperative aircraft broadcasting ADS-B detected in the specified area and time window"
- [ ] Feed cards are clickable and load sighting in map view
- [ ] Report modal opens and fully scrolls at 375px height
- [ ] Report modal map picker works (click to set location)
- [ ] Form submission creates new sighting
- [ ] Footer displays: "Data: ADS-B via rtl_adsb • © OpenStreetMap contributors"
- [ ] Info button opens info modal
- [ ] All existing IDs preserved (no broken functionality)

## Responsive Tests
- [ ] Test at 1400px width - hero, stats, cards all visible and aligned
- [ ] Test at 800px width - hero stacks (receiver card below title)
- [ ] Test at 375px width - all elements visible, no horizontal scroll
- [ ] Control bar wraps properly on narrow screens
- [ ] Stats row becomes 2 columns at narrow width
- [ ] Search bar full width on mobile
- [ ] Filter pills wrap properly

## Console Tests
- [ ] No JavaScript errors in console
- [ ] No 404s for static assets
- [ ] API calls succeed (/api/positions/live, /api/sightings, /api/positions/match)
- [ ] Theme switching updates both CSS and Leaflet tiles

## Color Palette Verification
- [ ] Dark theme: Page bg #0B1220, card bg #111A2E
- [ ] Dark theme: Accent gold #FBBF24, hover #F59E0B
- [ ] Light theme: Page bg #FFFFFF, card bg #F8FAFC
- [ ] Light theme: Accent dark gold #B45309 (not #FBBF24 on white)
- [ ] No blue accent colors visible (old #3b82f6 / #1d4ed8 removed)
- [ ] Gold accent visible on eyebrow, pills, buttons, badges

## Filter/Search Bug Fixes (ed91899 → next commit)

### Bug 1: Live vs Rewind Pills Now Distinct
- [ ] **Live pill rule**: Shows sightings from last 24 hours (recent, relevant to current traffic)
- [ ] **Rewind pill rule**: Shows sightings older than 24 hours (need historical rewind)
- [ ] Create test sighting with current time → appears under Live, not Rewind
- [ ] Create test sighting with 2-day-old time → appears under Rewind, not Live
- [ ] Hover each pill shows tooltip explaining its rule
- [ ] Live ≠ Rewind verified (at least one sighting differs between the two)

### Bug 2: Callsign Search Now Works
- [ ] Search for a known callsign from a matched aircraft → sighting appears
- [ ] Search for a known ICAO hex → sighting appears
- [ ] Search for reporter name → sighting appears
- [ ] Search for description text → sighting appears
- [ ] Search is case-insensitive
- [ ] Sightings without matches yet (hasMatches undefined/null) don't crash search
- [ ] matchCallsigns field populated after matches resolve

### Bug 3: Match Fetching Fixed (N+1 + Await + Unknown State)
- [ ] **Caching**: Matches fetched once per sighting per page load (not on every filterFeed())
- [ ] **Await**: loadFeed() awaits checkSightingMatches() before calling filterFeed()
- [ ] **Unknown state**: Sightings with hasMatches=null/undefined show under "All" pill
- [ ] **Unknown state**: "No ADS-B match" pill only shows hasMatches===false, not null/undefined
- [ ] Click "No ADS-B match" before matches resolve → doesn't incorrectly hide all cards
- [ ] After matches resolve, filterFeed() auto-applies current pill/search
- [ ] Check browser network tab: only 1 fetch to /api/positions/match per sighting per load
- [ ] Reload page with same sightings → new fetches (cache doesn't persist across loads, only within load)

## Map/Scroll Fix (ef5570b → next commit)

### Page Scrolling
- [ ] Page scrolls with mouse wheel from hero to footer (no locked viewport)
- [ ] Page scrolls with touch drag on mobile
- [ ] Header stays sticky at top during scroll
- [ ] Body has overflow-y: auto (not overflow: hidden)
- [ ] .main-container has height: auto, overflow: visible (not fixed height)

### Map Height and Layout
- [ ] Map height is 600px on desktop (≥769px width)
- [ ] Map height is 420px on mobile (≤768px width)
- [ ] Map has explicit height + min-height (not flex: 1 only)
- [ ] Map displays full content without collapsing
- [ ] Live status strip sits BELOW map in normal flow (not floating/absolute)
- [ ] Map does not overlay footer
- [ ] Status strip does not overlay map

### Wheel Zoom Behavior
- [ ] Mouse wheel over map scrolls PAGE by default (before clicking map)
- [ ] Click anywhere on map → wheel now zooms map instead of scrolling page
- [ ] Mouse leaves map area → wheel goes back to scrolling page
- [ ] Map zoom still works via +/- buttons
- [ ] Map zoom still works via double-click
- [ ] Map zoom still works via pinch on mobile

### Map Resize Handling
- [ ] Toggle Map → Feed → Map: map resizes correctly (invalidateSize)
- [ ] Resize browser window: map adjusts correctly
- [ ] Initial page load: map sized correctly (100ms timeout invalidateSize)

### Feed View
- [ ] Feed list still has its own scroll (overflow-y: auto)
- [ ] Feed cards fully reachable by page scroll
- [ ] No layout breaks when switching views

## PWA + Notifications (836d9c3 → next commit)

### PWA Installation & Offline
- [ ] On HTTPS or localhost: install prompt appears (Add to Home Screen)
- [ ] Favicon displays in browser tab (gold square + white triangle)
- [ ] Install as PWA: launches in standalone mode with proper icon
- [ ] Offline: reload page shows cached shell (/, style.css, app.js)
- [ ] Offline: API calls fail gracefully (no crash)
- [ ] Online: service worker updates show "Update available" notification
- [ ] Manifest valid: `python3 -m json.tool frontend/manifest.json` succeeds

### Notification Toggle
- [ ] Notification bell button appears in header (before theme toggle)
- [ ] Click bell → requests permission (only on first click, never on page load)
- [ ] Permission granted → toggle turns gold/active, "Notifications enabled" toast
- [ ] Permission denied → "Notifications blocked" toast, toggle stays off
- [ ] Toggle state persists across page reloads (localStorage)
- [ ] Turning off → stops polling, "Notifications disabled" toast

### New Sighting Notifications
- [ ] **Baseline set**: enabling notifications with existing sightings does NOT notify for old ones
- [ ] **New sighting created**: within 30s, notification appears
- [ ] **Tab visible**: new sighting → in-app toast only (NOT system notification)
- [ ] **Tab hidden** (switch to another tab): new sighting → system notification with icon
- [ ] **System notification click**: focuses/opens app, switches to Feed view
- [ ] **No duplicates**: same sighting never notifies twice (dedupe by ID)
- [ ] **Toggle off**: new sightings do NOT notify
- [ ] **HTTP/non-secure**: gracefully degrades to toast-only (no crash)

### Service Worker Behavior
- [ ] /api/* requests: never cached (network-first)
- [ ] Static shell (/, style.css, app.js): cached (cache-first)
- [ ] Leaflet CDN: not cached (always network)
- [ ] Cache version updates: old cache deleted on activate

### Group Chat Absence (Roadmap Only)
- [ ] No chat UI or button in the app
- [ ] README has "Roadmap" section explaining group chat is planned but not built
- [ ] Explanation mentions needs: accounts, moderation, real-time channel
- [ ] No fake chat messages or endpoints

## Server Dashboard (e21478f → next commit)

### Dashboard Display (LAN-only, read-only v1)
- [ ] Dashboard accessible at http://localhost:5001 or http://192.168.0.169:5001 from LAN
- [ ] **NOT accessible via uap.mattjhagen.xyz** (verify 404/no route - tunnel config unchanged)
- [ ] Page displays "r410 — SkyRewind Server" title in gold
- [ ] Clock in top-right updates every second
- [ ] Dashboard fits 1920×1080 without scrolling (kiosk-friendly)
- [ ] Dark theme (#0B1220 background, #FBBF24 gold accents) matches SkyRewind
- [ ] Readable from 10 feet away (large fonts: 48px title, 72px big numbers)

### Auto-refresh (10s polling)
- [ ] Dashboard auto-fetches /api/status every 10 seconds
- [ ] Updates all cards in place (no full-page reload)
- [ ] Last updated timestamp shown in footer
- [ ] If API unreachable: red "DASHBOARD API UNREACHABLE" banner appears
- [ ] Stale data kept visible with "(STALE)" indicator when API fails
- [ ] Banner disappears when API recovers

### Services Card
- [ ] Shows: skyrewind-web, skyrewind-logger, skyrewind-adsb-bridge, cloudflared, SDR Blog
- [ ] Green "RUNNING" pill for active services
- [ ] Red "FAILED" pill for stopped services
- [ ] Orange pulsing "LOOPING" pill for bridge when restart count >= 5 in last 2 min
- [ ] LOOPING state detected from journalctl (counts "rtl_adsb died" in last 100 lines)
- [ ] While bridge loops, shows LOOPING even though systemd says Active

### Pipeline Card
- [ ] Aircraft count (big 72px gold number)
- [ ] Messages count
- [ ] Last update time (from aircraft.json write time)
- [ ] JSON age (Xs ago, Xm ago, Xh ago, or "missing")
- [ ] Shows "--" or null values gracefully if aircraft.json doesn't exist

### System Card
- [ ] Uptime (Xd Xh Xm format)
- [ ] Load average (1min 5min 15min)
- [ ] Memory used percentage
- [ ] Disk used percentage
- [ ] CPU temperature (°C)

### Ports Card
- [ ] SkyRewind :5000 - UP/DOWN
- [ ] SDR Blog :3001 - UP/DOWN
- [ ] Dashboard :5001 - always UP (self-check)

### Bridge Log Card
- [ ] Last 5 lines of journalctl -u skyrewind-adsb-bridge
- [ ] Monospace font, auto-truncated to 160 chars per line
- [ ] Scrollable if lines wrap
- [ ] Shows "(journal unavailable)" if journalctl fails

### Read-only v1
- [ ] No restart buttons (read-only)
- [ ] No shell command inputs
- [ ] No authentication form
- [ ] No controls that change server state

### API Security
- [ ] /api/status takes no query params (injection-proof)
- [ ] All subprocess calls use fixed allowlist (no user input)
- [ ] No shell=True anywhere
- [ ] 3s timeout on all subprocess calls
- [ ] Never crashes on missing files/failed commands (returns "unknown")

### Tests
- [ ] pytest tests/ includes tests/test_dashboard.py
- [ ] /api/status returns JSON with all expected keys
- [ ] / returns 200 + contains "r410"
- [ ] API ignores query params (no injection surface)
- [ ] API never crashes when resources missing
