// API base URL
const API_BASE = window.location.origin;

// Map center for Omaha, NE
const DEFAULT_CENTER = [41.25, -95.95];
const DEFAULT_ZOOM = 9;

// Tile layers for light and dark themes
const TILE_LAYERS = {
    light: {
        url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    },
    dark: {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        attribution: 'Esri, HERE, Garmin, FAO, NOAA, USGS, © OpenStreetMap contributors, and the GIS User Community',
        maxZoom: 16
    }
};

// State
let map = null;
let reportMap = null;
let currentTileLayer = null;
let currentReportTileLayer = null;
let markers = {};
let liveInterval = null;
let currentSighting = null;
let sightingMarker = null;
let sightingLine = null;
let reportMarker = null;
let rewindPositions = [];
let currentTheme = 'dark';
let allSightings = [];
let currentFilter = 'all';
let currentSearchTerm = '';
let notificationsEnabled = false;
let lastSeenSightingId = null;
let notificationCheckInterval = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNavigation();
    initMap();
    initModals();
    initSearchFilter();
    initNotifications();
    registerServiceWorker();
    startLiveUpdates();
    loadFeed();
});

// Theme Management
function initTheme() {
    const saved = localStorage.getItem('skyrewind-theme');
    currentTheme = saved || 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);

    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
}

function toggleTheme() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('skyrewind-theme', currentTheme);

    // Update tile layers
    updateMapTiles();
}

function getTileLayerForTheme(theme) {
    const config = TILE_LAYERS[theme];
    return L.tileLayer(config.url, {
        attribution: config.attribution,
        maxZoom: config.maxZoom
    });
}

function updateMapTiles() {
    if (map && currentTileLayer) {
        map.removeLayer(currentTileLayer);
        currentTileLayer = getTileLayerForTheme(currentTheme);
        currentTileLayer.addTo(map);
    }

    if (reportMap && currentReportTileLayer) {
        reportMap.removeLayer(currentReportTileLayer);
        currentReportTileLayer = getTileLayerForTheme(currentTheme);
        currentReportTileLayer.addTo(reportMap);
    }
}

// Navigation
function initNavigation() {
    document.querySelectorAll('.view-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            switchView(view);
        });
    });

    document.getElementById('report-btn').addEventListener('click', openReportModal);
    document.getElementById('info-btn').addEventListener('click', () => {
        document.getElementById('info-modal').classList.add('active');
        document.getElementById('modal-overlay').classList.add('active');
    });
    document.getElementById('info-close-btn').addEventListener('click', () => {
        document.getElementById('info-modal').classList.remove('active');
        document.getElementById('modal-overlay').classList.remove('active');
    });
}

function switchView(viewName) {
    // Update toggle buttons
    document.querySelectorAll('.view-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });

    // Update views
    document.querySelectorAll('.view-content').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`${viewName}-view`).classList.add('active');

    // View-specific actions
    if (viewName === 'map') {
        setTimeout(() => map && map.invalidateSize(), 100);
        if (!currentSighting) {
            startLiveUpdates();
        }
    } else if (viewName === 'feed') {
        stopLiveUpdates();
        loadFeed();
    }
}

// Map Initialization
function initMap() {
    map = L.map('map-container', { scrollWheelZoom: false }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    currentTileLayer = getTileLayerForTheme(currentTheme);
    currentTileLayer.addTo(map);

    // Enable wheel zoom on click, disable on mouseout (wheel scrolls page by default)
    map.on('click', () => map.scrollWheelZoom.enable());
    map.on('mouseout', () => map.scrollWheelZoom.disable());

    // Invalidate size on initial load and window resize
    setTimeout(() => map.invalidateSize(), 100);
    window.addEventListener('resize', () => map.invalidateSize());

    // Load sighting button
    document.getElementById('load-sighting-btn').addEventListener('click', loadSelectedSighting);

    // Time slider
    document.getElementById('time-slider').addEventListener('input', (e) => {
        const offset = parseFloat(e.target.value);
        document.getElementById('time-offset').textContent =
            offset >= 0 ? `+${offset} min` : `${offset} min`;
        updateRewindMap(offset);
    });

    // Radius change
    document.getElementById('search-radius').addEventListener('change', () => {
        if (currentSighting) {
            loadPositionsForSighting();
        }
    });

    // Load sightings for dropdown
    loadSightingsDropdown();
}

// Live Updates
function startLiveUpdates() {
    updateLivePositions();
    if (liveInterval) clearInterval(liveInterval);
    liveInterval = setInterval(updateLivePositions, 10000);
}

function stopLiveUpdates() {
    if (liveInterval) {
        clearInterval(liveInterval);
        liveInterval = null;
    }
}

async function updateLivePositions() {
    try {
        const response = await fetch(`${API_BASE}/api/positions/live`);
        const positions = await response.json();

        const count = positions.length;
        const lastUpdate = new Date().toLocaleTimeString();

        // Update status dot
        document.getElementById('status-dot').classList.add('online');

        // Update receiver card
        const receiverStatus = document.getElementById('receiver-status');
        if (receiverStatus) {
            receiverStatus.textContent = 'LIVE';
            receiverStatus.classList.add('online');
        }
        const receiverAircraft = document.getElementById('receiver-aircraft');
        if (receiverAircraft) receiverAircraft.textContent = count;
        const receiverLastUpdate = document.getElementById('receiver-last-update');
        if (receiverLastUpdate) receiverLastUpdate.textContent = lastUpdate;

        // Update stats row
        const statAircraft = document.getElementById('stat-aircraft');
        if (statAircraft) statAircraft.textContent = count;
        const statUpdated = document.getElementById('stat-updated');
        if (statUpdated) statUpdated.textContent = lastUpdate;

        // Clear old markers
        Object.values(markers).forEach(marker => marker.remove());
        markers = {};

        // Add new markers
        positions.forEach(pos => {
            const icon = L.divIcon({
                className: 'aircraft-icon',
                html: `<div style="transform: rotate(${pos.track || 0}deg);">✈</div>`,
                iconSize: [20, 20]
            });

            const marker = L.marker([pos.lat, pos.lon], { icon })
                .bindPopup(`
                    <strong>${pos.callsign || pos.icao_hex}</strong><br>
                    Altitude: ${pos.altitude || 'N/A'} ft<br>
                    Speed: ${pos.ground_speed || 'N/A'} kts<br>
                    Heading: ${pos.track || 'N/A'}°<br>
                    ICAO: ${pos.icao_hex}
                `)
                .addTo(map);

            markers[pos.icao_hex] = marker;
        });

        // Update live status strip
        document.getElementById('live-count').textContent = `${count} aircraft tracked`;
        document.getElementById('live-last-update').textContent = `Last update: ${lastUpdate}`;

    } catch (error) {
        console.error('Error updating live positions:', error);
        document.getElementById('status-dot').classList.remove('online');
        const receiverStatus = document.getElementById('receiver-status');
        if (receiverStatus) {
            receiverStatus.textContent = 'OFFLINE';
            receiverStatus.classList.remove('online');
        }
    }
}

// Sighting Load & Rewind
async function loadSightingsDropdown() {
    try {
        const response = await fetch(`${API_BASE}/api/sightings`);
        const sightings = await response.json();

        const select = document.getElementById('sighting-select');
        select.innerHTML = '<option value="">Select sighting...</option>';

        sightings.forEach(sighting => {
            const date = new Date(sighting.sighting_time).toLocaleString();
            const option = document.createElement('option');
            option.value = sighting.id;
            option.textContent = `${date} - ${sighting.reporter_name}`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading sightings:', error);
    }
}

async function loadSelectedSighting() {
    const sightingId = document.getElementById('sighting-select').value;
    if (!sightingId) return;

    stopLiveUpdates();

    try {
        const response = await fetch(`${API_BASE}/api/sightings/${sightingId}`);
        currentSighting = await response.json();

        // Hide live status strip, show match panel
        document.getElementById('live-status-strip').style.display = 'none';
        document.getElementById('match-panel').style.display = 'block';

        // Center map on sighting
        map.setView([currentSighting.lat, currentSighting.lon], 11);

        // Clear old markers
        Object.values(markers).forEach(marker => marker.remove());
        markers = {};

        // Add sighting marker
        if (sightingMarker) sightingMarker.remove();
        if (sightingLine) sightingLine.remove();

        sightingMarker = L.marker([currentSighting.lat, currentSighting.lon], {
            icon: L.divIcon({
                className: 'sighting-icon',
                html: '<div></div>',
                iconSize: [16, 16]
            })
        }).bindPopup(`
            <strong>Sighting</strong><br>
            ${currentSighting.reporter_name}<br>
            ${new Date(currentSighting.sighting_time).toLocaleString()}<br>
            ${currentSighting.description}
        `).addTo(map);

        // Draw bearing line if available
        if (currentSighting.bearing !== null) {
            const bearingRad = currentSighting.bearing * Math.PI / 180;
            const distance = 0.5;
            const endLat = currentSighting.lat + distance * Math.cos(bearingRad);
            const endLon = currentSighting.lon + distance * Math.sin(bearingRad) / Math.cos(currentSighting.lat * Math.PI / 180);

            sightingLine = L.polyline([
                [currentSighting.lat, currentSighting.lon],
                [endLat, endLon]
            ], {
                color: '#ef4444',
                weight: 2,
                dashArray: '5, 10'
            }).addTo(map);
        }

        // Reset slider
        document.getElementById('time-slider').value = 0;
        document.getElementById('time-offset').textContent = '±0 min';

        // Load positions and find matches
        await loadPositionsForSighting();
        await findMatches();

    } catch (error) {
        console.error('Error loading sighting:', error);
        showNotification('Error loading sighting', 'error');
    }
}

async function loadPositionsForSighting() {
    if (!currentSighting) return;

    const radius = document.getElementById('search-radius').value;

    try {
        const params = new URLSearchParams({
            time: currentSighting.sighting_time,
            lat: currentSighting.lat,
            lon: currentSighting.lon,
            radius: radius,
            time_window: 10
        });

        const response = await fetch(`${API_BASE}/api/positions/rewind?${params}`);
        rewindPositions = await response.json();

        updateRewindMap(0);
    } catch (error) {
        console.error('Error loading positions:', error);
    }
}

function updateRewindMap(offsetMinutes) {
    if (!currentSighting) return;

    // Clear old markers (keep sighting marker)
    Object.values(markers).forEach(marker => marker.remove());
    markers = {};

    // Calculate target time
    const targetTime = new Date(new Date(currentSighting.sighting_time).getTime() + offsetMinutes * 60000);

    // Filter positions within 30 seconds of target time
    const timeWindow = 30000;
    const relevantPositions = rewindPositions.filter(pos => {
        const posTime = new Date(pos.timestamp);
        return Math.abs(posTime - targetTime) <= timeWindow;
    });

    // Group by aircraft
    const latestByAircraft = {};
    relevantPositions.forEach(pos => {
        if (!latestByAircraft[pos.icao_hex] ||
            new Date(pos.timestamp) > new Date(latestByAircraft[pos.icao_hex].timestamp)) {
            latestByAircraft[pos.icao_hex] = pos;
        }
    });

    // Add markers
    Object.values(latestByAircraft).forEach(pos => {
        const icon = L.divIcon({
            className: 'aircraft-icon',
            html: `<div style="transform: rotate(${pos.track || 0}deg);">✈</div>`,
            iconSize: [20, 20]
        });

        const marker = L.marker([pos.lat, pos.lon], { icon })
            .bindPopup(`
                <strong>${pos.callsign || pos.icao_hex}</strong><br>
                Altitude: ${pos.altitude || 'N/A'} ft<br>
                Speed: ${pos.ground_speed || 'N/A'} kts<br>
                Heading: ${pos.track || 'N/A'}°<br>
                Distance: ${pos.distance_miles.toFixed(1)} mi<br>
                Time: ${new Date(pos.timestamp).toLocaleTimeString()}
            `)
            .addTo(map);

        markers[pos.icao_hex] = marker;
    });
}

async function findMatches() {
    if (!currentSighting) return;

    const radius = document.getElementById('search-radius').value;

    try {
        const params = new URLSearchParams({
            sighting_id: currentSighting.id,
            radius: radius
        });

        const response = await fetch(`${API_BASE}/api/positions/match?${params}`);
        const matches = await response.json();

        const matchList = document.getElementById('match-list');
        matchList.innerHTML = '';

        if (matches.length === 0) {
            matchList.innerHTML = `
                <div class="no-match">
                    <div class="no-match-title">No ADS-B match found</div>
                    <div class="no-match-subtitle">No cooperative aircraft broadcasting ADS-B detected in the specified area and time window</div>
                </div>
            `;
        } else {
            matches.forEach(match => {
                const div = document.createElement('div');
                div.className = 'match-item';
                div.innerHTML = `
                    <div class="callsign">${match.callsign || match.icao_hex}</div>
                    <div class="details">
                        <span><strong>ICAO</strong>${match.icao_hex}</span>
                        <span><strong>Distance</strong>${match.closest_distance} mi</span>
                        <span><strong>Altitude</strong>${match.altitude || 'N/A'} ft</span>
                        <span><strong>Speed</strong>${match.ground_speed || 'N/A'} kts</span>
                        <span><strong>Heading</strong>${match.track || 'N/A'}°</span>
                        <span><strong>Closest at</strong>${new Date(match.closest_time).toLocaleTimeString()}</span>
                    </div>
                `;
                matchList.appendChild(div);
            });
        }
    } catch (error) {
        console.error('Error finding matches:', error);
    }
}

// Search and Filter
function initSearchFilter() {
    const searchInput = document.getElementById('sighting-search');
    const filterPills = document.querySelectorAll('.filter-pill');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearchTerm = e.target.value.toLowerCase();
            filterFeed();
        });
    }

    filterPills.forEach(pill => {
        pill.addEventListener('click', () => {
            filterPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            currentFilter = pill.dataset.filter;
            filterFeed();
        });
    });
}

function filterFeed() {
    const feedCards = document.querySelectorAll('.feed-card');

    feedCards.forEach(card => {
        const sightingId = card.dataset.sightingId;
        const sighting = allSightings.find(s => s.id == sightingId);

        if (!sighting) {
            card.style.display = 'none';
            return;
        }

        // Text search - includes reporter, description, and matched callsigns/ICAOs
        const searchText = `${sighting.reporter_name} ${sighting.description} ${sighting.matchCallsigns || ''}`.toLowerCase();
        const matchesSearch = currentSearchTerm === '' || searchText.includes(currentSearchTerm);

        // Filter by status
        let matchesFilter = true;
        if (currentFilter === 'live') {
            // Live: sightings within last 24 hours (recent, relevant to current traffic)
            const sightingTime = new Date(sighting.sighting_time);
            const now = new Date();
            const hoursSince = (now - sightingTime) / (1000 * 60 * 60);
            matchesFilter = hoursSince <= 24;
        } else if (currentFilter === 'rewind') {
            // Rewind: sightings older than 24 hours (need historical rewind to check)
            const sightingTime = new Date(sighting.sighting_time);
            const now = new Date();
            const hoursSince = (now - sightingTime) / (1000 * 60 * 60);
            matchesFilter = hoursSince > 24;
        } else if (currentFilter === 'nomatch') {
            // No ADS-B match: sighting has been checked and has no matches
            // Note: hasMatches === null/undefined means "not checked yet" - don't count as no-match
            matchesFilter = sighting.hasMatches === false;
        }
        // All filter: show everything (matchesFilter stays true)

        card.style.display = (matchesSearch && matchesFilter) ? 'block' : 'none';
    });

    // Update count
    const visibleCount = Array.from(feedCards).filter(c => c.style.display !== 'none').length;
    const feedCount = document.getElementById('feed-count');
    if (feedCount) {
        feedCount.textContent = `${visibleCount} Sighting${visibleCount === 1 ? '' : 's'}`;
    }
}

// Feed View
async function loadFeed() {
    try {
        const response = await fetch(`${API_BASE}/api/sightings`);
        const sightings = await response.json();
        allSightings = sightings;

        const feedList = document.getElementById('feed-list');
        const feedCount = document.getElementById('feed-count');

        if (sightings.length === 0) {
            feedList.innerHTML = `
                <div class="feed-empty">
                    <div class="feed-empty-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                        </svg>
                    </div>
                    <p class="feed-empty-title">No sighting reports yet</p>
                    <p class="feed-empty-subtitle">Submit the first report to begin tracking</p>
                </div>
            `;
            feedCount.textContent = '0 Sightings';
        } else {
            feedList.innerHTML = '';
            sightings.reverse().forEach(sighting => {
                const card = document.createElement('div');
                card.className = 'feed-card';
                card.dataset.sightingId = sighting.id;
                card.innerHTML = `
                    <div class="feed-card-header">
                        <div class="feed-card-name">${sighting.reporter_name}</div>
                        <div class="feed-card-time">${new Date(sighting.sighting_time).toLocaleString()}</div>
                    </div>
                    <div class="feed-card-description">${sighting.description}</div>
                    <div class="feed-card-location">${sighting.location_text || `${sighting.lat.toFixed(4)}, ${sighting.lon.toFixed(4)}`}</div>
                `;
                card.addEventListener('click', () => {
                    document.getElementById('sighting-select').value = sighting.id;
                    switchView('map');
                    loadSelectedSighting();
                });
                feedList.appendChild(card);
            });
            feedCount.textContent = `${sightings.length} Sighting${sightings.length === 1 ? '' : 's'}`;
        }

        // Check for matches on each sighting, then apply current filter
        await checkSightingMatches();
        filterFeed();
    } catch (error) {
        console.error('Error loading feed:', error);
    }
}

async function checkSightingMatches() {
    // Fetch matches for all sightings in parallel (with caching)
    const fetchPromises = allSightings.map(async (sighting) => {
        // Cache: skip if already checked (hasMatches is true or false, not null/undefined)
        if (sighting.hasMatches === true || sighting.hasMatches === false) {
            return;
        }

        try {
            const params = new URLSearchParams({
                sighting_id: sighting.id,
                radius: 25
            });
            const response = await fetch(`${API_BASE}/api/positions/match?${params}`);
            const matches = await response.json();
            sighting.hasMatches = matches.length > 0;
            // Store matched callsigns/ICAOs for search
            sighting.matchCallsigns = matches.map(m => m.callsign || m.icao_hex || '').filter(c => c).join(' ');
        } catch (error) {
            // On error, set to null (unknown) - not false (no match)
            sighting.hasMatches = null;
            sighting.matchCallsigns = '';
        }
    });

    // Wait for all match checks to complete
    await Promise.all(fetchPromises);
}

// Report Modal
function initModals() {
    const reportModal = document.getElementById('report-modal');
    const modalOverlay = document.getElementById('modal-overlay');
    const closeBtn = document.getElementById('modal-close-btn');
    const form = document.getElementById('sighting-form');

    closeBtn.addEventListener('click', closeReportModal);
    modalOverlay.addEventListener('click', () => {
        closeReportModal();
        document.getElementById('info-modal').classList.remove('active');
    });

    form.addEventListener('submit', handleSightingSubmit);

    // Set default datetime
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    form.sighting_time.value = now.toISOString().slice(0, 16);
}

function openReportModal() {
    const reportModal = document.getElementById('report-modal');
    const modalOverlay = document.getElementById('modal-overlay');

    reportModal.classList.add('active');
    modalOverlay.classList.add('active');

    // Initialize report map if not already done
    if (!reportMap) {
        setTimeout(() => {
            reportMap = L.map('report-map-modal').setView(DEFAULT_CENTER, DEFAULT_ZOOM);
            currentReportTileLayer = getTileLayerForTheme(currentTheme);
            currentReportTileLayer.addTo(reportMap);

            // Set default location
            const form = document.getElementById('sighting-form');
            form.lat.value = DEFAULT_CENTER[0];
            form.lon.value = DEFAULT_CENTER[1];

            reportMarker = L.marker(DEFAULT_CENTER, { draggable: true }).addTo(reportMap);

            reportMarker.on('dragend', () => {
                const pos = reportMarker.getLatLng();
                form.lat.value = pos.lat.toFixed(6);
                form.lon.value = pos.lng.toFixed(6);
            });

            reportMap.on('click', (e) => {
                reportMarker.setLatLng(e.latlng);
                form.lat.value = e.latlng.lat.toFixed(6);
                form.lon.value = e.latlng.lng.toFixed(6);
            });
        }, 100);
    } else {
        setTimeout(() => reportMap.invalidateSize(), 100);
    }
}

function closeReportModal() {
    document.getElementById('report-modal').classList.remove('active');
    document.getElementById('modal-overlay').classList.remove('active');
}

async function handleSightingSubmit(e) {
    e.preventDefault();

    const form = e.target;
    const formData = new FormData(form);

    // Convert local time to UTC
    const localTime = new Date(formData.get('sighting_time'));
    formData.set('sighting_time', localTime.toISOString());

    try {
        const response = await fetch(`${API_BASE}/api/sightings`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            showNotification('Sighting reported successfully!', 'success');
            form.reset();

            // Reset datetime
            const now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            form.sighting_time.value = now.toISOString().slice(0, 16);

            // Reset map
            form.lat.value = DEFAULT_CENTER[0];
            form.lon.value = DEFAULT_CENTER[1];
            if (reportMarker) reportMarker.setLatLng(DEFAULT_CENTER);

            closeReportModal();
            loadSightingsDropdown();
            loadFeed();
        } else {
            showNotification('Error submitting sighting', 'error');
        }
    } catch (error) {
        console.error('Error submitting sighting:', error);
        showNotification('Error submitting sighting', 'error');
    }
}

// Notifications
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type} show`;

    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// Service Worker Registration
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then((registration) => {
                console.log('[SW] Registered:', registration);

                // Check for updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            showNotification('Update available — refresh to get the latest version', 'info');
                        }
                    });
                });

                // Listen for messages from SW
                navigator.serviceWorker.addEventListener('message', (event) => {
                    if (event.data && event.data.action === 'switchToFeed') {
                        switchView('feed');
                    }
                });
            })
            .catch((error) => {
                console.error('[SW] Registration failed:', error);
                // Don't break the app if SW registration fails
            });
    }
}

// Sighting Notifications
function initNotifications() {
    const toggle = document.getElementById('notify-toggle');
    if (!toggle) return;

    // Load saved state
    const saved = localStorage.getItem('skyrewind-notifications');
    notificationsEnabled = saved === 'on';
    updateNotifyToggleUI();

    toggle.addEventListener('click', toggleNotifications);
}

async function toggleNotifications() {
    const toggle = document.getElementById('notify-toggle');

    if (!notificationsEnabled) {
        // Turning ON: request permission (only on user click, never on page load)
        if (!('Notification' in window)) {
            showNotification('Notifications not supported in this browser — using in-app toasts only', 'info');
            notificationsEnabled = true;
            localStorage.setItem('skyrewind-notifications', 'on');
            updateNotifyToggleUI();
            startNotificationPolling();
            return;
        }

        // HTTPS/localhost reality: Notification API may be unavailable on non-secure origins
        // Gracefully degrade to toast-only mode
        if (Notification.permission === 'default') {
            try {
                const permission = await Notification.requestPermission();
                if (permission === 'denied') {
                    showNotification('Notifications blocked in this browser — check site settings', 'info');
                    return;
                }
            } catch (error) {
                // Request failed (non-secure origin) - continue with toast-only
                console.warn('[Notifications] Permission request failed, using toast-only:', error);
            }
        }

        notificationsEnabled = true;
        localStorage.setItem('skyrewind-notifications', 'on');
        updateNotifyToggleUI();

        // Set baseline: don't notify for existing sightings
        await setNotificationBaseline();

        startNotificationPolling();
        showNotification('Sighting notifications enabled', 'success');
    } else {
        // Turning OFF
        notificationsEnabled = false;
        localStorage.setItem('skyrewind-notifications', 'off');
        updateNotifyToggleUI();

        stopNotificationPolling();
        showNotification('Sighting notifications disabled', 'info');
    }
}

function updateNotifyToggleUI() {
    const toggle = document.getElementById('notify-toggle');
    if (notificationsEnabled) {
        toggle.classList.add('active');
        toggle.title = 'Notifications enabled (click to disable)';
    } else {
        toggle.classList.remove('active');
        toggle.title = 'Turn on sighting notifications';
    }
}

async function setNotificationBaseline() {
    try {
        const response = await fetch(`${API_BASE}/api/sightings`);
        const sightings = await response.json();

        // Set baseline to max ID - never notify for sightings at/below baseline
        if (sightings.length > 0) {
            lastSeenSightingId = Math.max(...sightings.map(s => s.id));
            console.log('[Notifications] Baseline set to ID:', lastSeenSightingId);
        } else {
            lastSeenSightingId = 0;
        }
    } catch (error) {
        console.error('[Notifications] Failed to set baseline:', error);
        lastSeenSightingId = 0;
    }
}

function startNotificationPolling() {
    if (notificationCheckInterval) return;

    // Poll every 30 seconds
    notificationCheckInterval = setInterval(checkForNewSightings, 30000);
    console.log('[Notifications] Polling started (every 30s)');
}

function stopNotificationPolling() {
    if (notificationCheckInterval) {
        clearInterval(notificationCheckInterval);
        notificationCheckInterval = null;
        console.log('[Notifications] Polling stopped');
    }
}

async function checkForNewSightings() {
    if (!notificationsEnabled) return;

    try {
        const response = await fetch(`${API_BASE}/api/sightings`);
        const sightings = await response.json();

        // Find sightings with id > lastSeenSightingId
        const newSightings = sightings.filter(s => s.id > lastSeenSightingId);

        if (newSightings.length === 0) return;

        // Sort by ID to notify in order
        newSightings.sort((a, b) => a.id - b.id);

        for (const sighting of newSightings) {
            await notifySighting(sighting);
            lastSeenSightingId = sighting.id; // Advance baseline after each notification
        }
    } catch (error) {
        console.error('[Notifications] Failed to check for new sightings:', error);
    }
}

async function notifySighting(sighting) {
    const time = new Date(sighting.sighting_time).toLocaleString();
    const message = `New sighting: ${sighting.reporter_name} — ${time}`;

    // If tab is visible: use in-app toast (NOT system notification)
    if (document.visibilityState === 'visible') {
        showNotification(message, 'info');
        return;
    }

    // Tab is hidden: try system notification if available
    if ('Notification' in window && Notification.permission === 'granted') {
        try {
            // Try to use service worker notification if available
            if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
                const registration = await navigator.serviceWorker.ready;
                await registration.showNotification('New SkyRewind sighting', {
                    body: `${sighting.reporter_name} — ${sighting.description.slice(0, 100)}`,
                    icon: '/icons/icon-192.png',
                    tag: `sighting-${sighting.id}`,
                    data: { view: 'feed' }
                });
            } else {
                // Fallback to regular Notification API
                new Notification('New SkyRewind sighting', {
                    body: `${sighting.reporter_name} — ${sighting.description.slice(0, 100)}`,
                    icon: '/icons/icon-192.png',
                    tag: `sighting-${sighting.id}`
                });
            }
        } catch (error) {
            // System notification failed - fall back to toast
            console.warn('[Notifications] System notification failed, using toast:', error);
            showNotification(message, 'info');
        }
    } else {
        // Notifications unavailable/denied - fall back to toast
        showNotification(message, 'info');
    }
}
