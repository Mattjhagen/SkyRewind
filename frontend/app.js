// API base URL
const API_BASE = window.location.origin;

// Map center for Omaha, NE
const DEFAULT_CENTER = [41.25, -95.95];
const DEFAULT_ZOOM = 9;

// State
let map = null;
let markers = {
    sightings: {},
    aircraft: {}
};
let currentSighting = null;
let rewindPositions = [];
let sightingMarker = null;
let sightingLine = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initViewToggle();
    initMap();
    initReportForm();
    initRewindControls();
    loadSightings();
    updateStatusDot();
    setInterval(updateStatusDot, 30000);
});

// View Toggle
function initViewToggle() {
    const toggleBtns = document.querySelectorAll('.view-toggle-btn');
    const views = document.querySelectorAll('.view-content');

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const viewName = btn.dataset.view;

            // Update toggle buttons
            toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update views
            views.forEach(v => v.classList.remove('active'));
            document.getElementById(`${viewName}-view`).classList.add('active');

            // Invalidate map size
            setTimeout(() => {
                if (map) map.invalidateSize();
            }, 100);

            // Refresh feed if switching to feed view
            if (viewName === 'feed') {
                loadSightings();
            }
        });
    });
}

// Initialize Map
function initMap() {
    map = L.map('map-container').setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);

    // Click to set location for report
    map.on('click', (e) => {
        const form = document.getElementById('sighting-form');
        form.lat.value = e.latlng.lat.toFixed(6);
        form.lon.value = e.latlng.lng.toFixed(6);
    });
}

// Report Form
function initReportForm() {
    const reportBtn = document.getElementById('report-btn');
    const modal = document.getElementById('report-modal');
    const overlay = document.getElementById('modal-overlay');
    const closeBtn = document.getElementById('modal-close-btn');
    const cancelBtn = document.getElementById('cancel-form-btn');
    const form = document.getElementById('sighting-form');

    const openModal = () => {
        modal.style.display = 'block';
        overlay.classList.add('active');

        // Set default values
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        form.sighting_time.value = now.toISOString().slice(0, 16);
        form.lat.value = DEFAULT_CENTER[0];
        form.lon.value = DEFAULT_CENTER[1];
    };

    const closeModal = () => {
        modal.style.display = 'none';
        overlay.classList.remove('active');
        form.reset();
    };

    reportBtn.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', closeModal);

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

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
                closeModal();
                loadSightings();
            } else {
                const error = await response.json();
                showNotification(`Error: ${error.error || 'Failed to submit'}`, 'error');
            }
        } catch (error) {
            console.error('Error submitting sighting:', error);
            showNotification('Error submitting sighting', 'error');
        }
    });
}

// Rewind Controls
function initRewindControls() {
    const loadBtn = document.getElementById('load-sighting-btn');
    const slider = document.getElementById('time-slider');
    const radiusInput = document.getElementById('search-radius');

    loadBtn.addEventListener('click', loadSelectedSighting);

    slider.addEventListener('input', (e) => {
        const offset = parseFloat(e.target.value);
        document.getElementById('time-offset').textContent =
            offset >= 0 ? `+${offset} min` : `${offset} min`;

        if (currentSighting) {
            updateRewindMap(offset);
        }
    });

    radiusInput.addEventListener('change', () => {
        if (currentSighting) {
            loadPositionsForSighting();
            findMatches();
        }
    });
}

// Load Sightings
async function loadSightings() {
    try {
        const response = await fetch(`${API_BASE}/api/sightings`);
        const sightings = await response.json();

        // Update select dropdown
        const select = document.getElementById('sighting-select');
        select.innerHTML = '<option value="">Select sighting...</option>';
        sightings.forEach(sighting => {
            const date = new Date(sighting.sighting_time).toLocaleString();
            const option = document.createElement('option');
            option.value = sighting.id;
            option.textContent = `${date} - ${sighting.reporter_name}`;
            select.appendChild(option);
        });

        // Update feed view
        renderFeed(sightings);
    } catch (error) {
        console.error('Error loading sightings:', error);
    }
}

// Render Feed View
function renderFeed(sightings) {
    const feedList = document.getElementById('feed-list');
    const feedCount = document.getElementById('feed-count');

    feedCount.textContent = `${sightings.length} ${sightings.length === 1 ? 'Sighting' : 'Sightings'}`;

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
        return;
    }

    const sortedSightings = [...sightings].sort((a, b) =>
        new Date(b.sighting_time) - new Date(a.sighting_time)
    );

    feedList.innerHTML = sortedSightings.map(sighting => {
        const time = formatRelativeTime(new Date(sighting.sighting_time));
        const location = sighting.location_text || `${sighting.lat.toFixed(4)}, ${sighting.lon.toFixed(4)}`;

        return `
            <button class="feed-card" data-sighting-id="${sighting.id}">
                <div class="feed-card-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                </div>
                <div class="feed-card-content">
                    <div class="feed-card-meta">
                        <span class="feed-card-type">Sighting</span>
                        <div class="feed-card-time">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            ${time}
                        </div>
                    </div>
                    <p class="feed-card-desc">${sighting.description}</p>
                    <div class="feed-card-location">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        ${location}
                    </div>
                </div>
                <div class="feed-card-chevron">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </div>
            </button>
        `;
    }).join('');

    // Add click handlers
    feedList.querySelectorAll('.feed-card').forEach(card => {
        card.addEventListener('click', () => {
            const sightingId = card.dataset.sightingId;
            loadSightingById(sightingId);
        });
    });
}

function formatRelativeTime(date) {
    const diff = Date.now() - date.getTime();
    const minutes = Math.floor(diff / 60000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

// Load Sighting by ID
async function loadSightingById(sightingId) {
    try {
        const response = await fetch(`${API_BASE}/api/sightings/${sightingId}`);
        currentSighting = await response.json();

        // Switch to map view
        document.querySelector('.view-toggle-btn[data-view="map"]').click();

        // Set select dropdown
        document.getElementById('sighting-select').value = sightingId;

        // Load on map
        loadSelectedSighting();
    } catch (error) {
        console.error('Error loading sighting:', error);
    }
}

// Load Selected Sighting
async function loadSelectedSighting() {
    const sightingId = document.getElementById('sighting-select').value;
    if (!sightingId) return;

    try {
        const response = await fetch(`${API_BASE}/api/sightings/${sightingId}`);
        currentSighting = await response.json();

        // Center map on sighting
        map.setView([currentSighting.lat, currentSighting.lon], 11);

        // Add sighting marker
        clearMarkers();

        const sightingIcon = L.divIcon({
            className: 'custom-pin',
            html: `
                <div class="pin-circle sighting">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                </div>
            `,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        sightingMarker = L.marker([currentSighting.lat, currentSighting.lon], { icon: sightingIcon })
            .bindPopup(`
                <strong>Sighting</strong><br>
                ${currentSighting.reporter_name}<br>
                ${new Date(currentSighting.sighting_time).toLocaleString()}<br>
                ${currentSighting.description}
            `)
            .addTo(map);

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

        // Load positions
        await loadPositionsForSighting();

        // Find matches
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

    // Clear old aircraft markers
    Object.values(markers.aircraft).forEach(marker => marker.remove());
    markers.aircraft = {};

    // Calculate target time
    const targetTime = new Date(new Date(currentSighting.sighting_time).getTime() + offsetMinutes * 60000);

    // Filter positions within 30 seconds of target time
    const timeWindow = 30000;
    const relevantPositions = rewindPositions.filter(pos => {
        const posTime = new Date(pos.timestamp);
        return Math.abs(posTime - targetTime) <= timeWindow;
    });

    // Group by aircraft (show latest position per aircraft)
    const latestByAircraft = {};
    relevantPositions.forEach(pos => {
        if (!latestByAircraft[pos.icao_hex] ||
            new Date(pos.timestamp) > new Date(latestByAircraft[pos.icao_hex].timestamp)) {
            latestByAircraft[pos.icao_hex] = pos;
        }
    });

    // Add markers
    Object.values(latestByAircraft).forEach(pos => {
        const aircraftIcon = L.divIcon({
            className: 'custom-pin',
            html: `
                <div class="pin-circle aircraft">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" transform="rotate(${pos.track || 0})">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3l14 9-14 9V3z" />
                    </svg>
                </div>
            `,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        const marker = L.marker([pos.lat, pos.lon], { icon: aircraftIcon })
            .bindPopup(`
                <strong>${pos.callsign || pos.icao_hex}</strong><br>
                Altitude: ${pos.altitude || 'N/A'} ft<br>
                Speed: ${pos.ground_speed || 'N/A'} kts<br>
                Heading: ${pos.track || 'N/A'}°<br>
                Distance: ${pos.distance_miles} mi<br>
                Time: ${new Date(pos.timestamp).toLocaleTimeString()}
            `)
            .addTo(map);

        markers.aircraft[pos.icao_hex] = marker;
    });
}

async function findMatches() {
    if (!currentSighting) return;

    const radius = document.getElementById('search-radius').value;
    const panel = document.getElementById('match-panel');
    const matchList = document.getElementById('match-list');

    try {
        const params = new URLSearchParams({
            sighting_id: currentSighting.id,
            radius: radius
        });

        const response = await fetch(`${API_BASE}/api/positions/match?${params}`);
        const matches = await response.json();

        panel.style.display = 'block';

        if (matches.length === 0) {
            matchList.innerHTML = `
                <div class="no-match">
                    <p class="no-match-title">No ADS-B match found</p>
                    <p class="no-match-subtitle">No cooperative aircraft broadcasting ADS-B detected in the specified area and time window</p>
                </div>
            `;
        } else {
            matchList.innerHTML = matches.map(match => `
                <div class="match-card">
                    <div class="match-card-callsign">${match.callsign || match.icao_hex}</div>
                    <div class="match-card-details">
                        <span><strong>ICAO</strong>${match.icao_hex}</span>
                        <span><strong>Distance</strong>${match.closest_distance} mi</span>
                        <span><strong>Altitude</strong>${match.altitude || 'N/A'} ft</span>
                        <span><strong>Speed</strong>${match.ground_speed || 'N/A'} kts</span>
                        <span><strong>Heading</strong>${match.track || 'N/A'}°</span>
                        <span><strong>Closest at</strong>${new Date(match.closest_time).toLocaleTimeString()}</span>
                    </div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error finding matches:', error);
    }
}

function clearMarkers() {
    if (sightingMarker) {
        sightingMarker.remove();
        sightingMarker = null;
    }
    if (sightingLine) {
        sightingLine.remove();
        sightingLine = null;
    }
    Object.values(markers.aircraft).forEach(marker => marker.remove());
    markers.aircraft = {};
}

// Status Dot
async function updateStatusDot() {
    const dot = document.getElementById('status-dot');
    try {
        const response = await fetch(`${API_BASE}/api/positions/live`);
        if (response.ok) {
            dot.classList.add('online');
        } else {
            dot.classList.remove('online');
        }
    } catch (error) {
        dot.classList.remove('online');
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

// Info button
document.getElementById('info-btn').addEventListener('click', () => {
    showNotification('SkyRewind tracks ADS-B aircraft and correlates sighting reports', 'info');
});
