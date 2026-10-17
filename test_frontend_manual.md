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
