// API base URL
const API_BASE = window.location.origin;

// Map center for Omaha, NE
const DEFAULT_CENTER = [41.25, -95.95];
const DEFAULT_ZOOM = 9;

// State
let maps = {};
let markers = {};
let liveInterval = null;
let sightingMarker = null;
let sightingLine = null;
let rewindPositions = [];
let currentSighting = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initLiveView();
    initReportView();
    initRewindView();
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            switchView(view);
        });
    });
}

function switchView(viewName) {
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });

    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`${viewName}-view`).classList.add('active');

    // View-specific actions
    if (viewName === 'live') {
        startLiveUpdates();
    } else if (viewName === 'rewind') {
        stopLiveUpdates();
        loadSightings();
    } else {
        stopLiveUpdates();
    }

    // Invalidate map size after view switch
    setTimeout(() => {
        if (maps[viewName]) {
            maps[viewName].invalidateSize();
        }
    }, 100);
}

// Live View
function initLiveView() {
    maps.live = L.map('live-map').setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(maps.live);

    markers.live = {};

    startLiveUpdates();
}

function startLiveUpdates() {
    updateLivePositions();
    liveInterval = setInterval(updateLivePositions, 10000); // Every 10 seconds
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

        // Clear old markers
        Object.values(markers.live).forEach(marker => marker.remove());
        markers.live = {};

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
                .addTo(maps.live);

            markers.live[pos.icao_hex] = marker;
        });

        // Update stats
        document.getElementById('live-count').textContent = `${positions.length} aircraft tracked`;
        document.getElementById('live-last-update').textContent =
            `Last update: ${new Date().toLocaleTimeString()}`;

    } catch (error) {
        console.error('Error updating live positions:', error);
    }
}

// Report View
function initReportView() {
    maps.report = L.map('report-map').setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(maps.report);

    // Set default location
    const form = document.getElementById('sighting-form');
    form.lat.value = DEFAULT_CENTER[0];
    form.lon.value = DEFAULT_CENTER[1];

    sightingMarker = L.marker(DEFAULT_CENTER, { draggable: true })
        .addTo(maps.report);

    // Update coordinates when marker is dragged
    sightingMarker.on('dragend', () => {
        const pos = sightingMarker.getLatLng();
        form.lat.value = pos.lat.toFixed(6);
        form.lon.value = pos.lng.toFixed(6);
    });

    // Click to set location
    maps.report.on('click', (e) => {
        sightingMarker.setLatLng(e.latlng);
        form.lat.value = e.latlng.lat.toFixed(6);
        form.lon.value = e.latlng.lng.toFixed(6);
    });

    // Set default datetime to now
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    form.sighting_time.value = now.toISOString().slice(0, 16);

    // Form submission
    form.addEventListener('submit', handleSightingSubmit);
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

            // Reset map marker to default
            const now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            form.sighting_time.value = now.toISOString().slice(0, 16);
            form.lat.value = DEFAULT_CENTER[0];
            form.lon.value = DEFAULT_CENTER[1];
            sightingMarker.setLatLng(DEFAULT_CENTER);
        } else {
            showNotification('Error submitting sighting', 'error');
        }
    } catch (error) {
        console.error('Error submitting sighting:', error);
        showNotification('Error submitting sighting', 'error');
    }
}

// Rewind View
function initRewindView() {
    maps.rewind = L.map('rewind-map').setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(maps.rewind);

    markers.rewind = {};

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

    // Manual time picker change
    document.getElementById('rewind-time').addEventListener('change', (e) => {
        if (currentSighting) {
            // Update currentSighting time to the manually selected time
            const localTime = new Date(e.target.value);
            currentSighting.sighting_time = localTime.toISOString();

            // Reset slider and reload
            document.getElementById('time-slider').value = 0;
            document.getElementById('time-offset').textContent = '±0 min';

            loadPositionsForSighting();
            findMatches();
        }
    });
}

async function loadSightings() {
    try {
        const response = await fetch(`${API_BASE}/api/sightings`);
        const sightings = await response.json();

        const select = document.getElementById('sighting-select');
        select.innerHTML = '<option value="">-- Choose a sighting --</option>';

        sightings.forEach(sighting => {
            const date = new Date(sighting.sighting_time).toLocaleString();
            const option = document.createElement('option');
            option.value = sighting.id;
            option.textContent = `${date} - ${sighting.reporter_name}: ${sighting.description.slice(0, 50)}...`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading sightings:', error);
    }
}

async function loadSelectedSighting() {
    const sightingId = document.getElementById('sighting-select').value;
    if (!sightingId) return;

    try {
        const response = await fetch(`${API_BASE}/api/sightings/${sightingId}`);
        currentSighting = await response.json();

        // Set time picker
        const sightingDate = new Date(currentSighting.sighting_time);
        const localDate = new Date(sightingDate.getTime() - sightingDate.getTimezoneOffset() * 60000);
        document.getElementById('rewind-time').value = localDate.toISOString().slice(0, 16);

        // Center map on sighting
        maps.rewind.setView([currentSighting.lat, currentSighting.lon], 11);

        // Add sighting marker
        if (sightingMarker) sightingMarker.remove();
        if (sightingLine) sightingLine.remove();

        sightingMarker = L.marker([currentSighting.lat, currentSighting.lon], {
            icon: L.divIcon({
                className: 'sighting-icon',
                html: '<div style="background: #e74c3c; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>',
                iconSize: [16, 16]
            })
        }).bindPopup(`
            <strong>Sighting</strong><br>
            ${currentSighting.reporter_name}<br>
            ${new Date(currentSighting.sighting_time).toLocaleString()}<br>
            ${currentSighting.description}
        `).addTo(maps.rewind);

        // Draw bearing line if available
        if (currentSighting.bearing !== null) {
            const bearingRad = currentSighting.bearing * Math.PI / 180;
            const distance = 0.5; // degrees
            const endLat = currentSighting.lat + distance * Math.cos(bearingRad);
            const endLon = currentSighting.lon + distance * Math.sin(bearingRad) / Math.cos(currentSighting.lat * Math.PI / 180);

            sightingLine = L.polyline([
                [currentSighting.lat, currentSighting.lon],
                [endLat, endLon]
            ], {
                color: '#e74c3c',
                weight: 2,
                dashArray: '5, 10'
            }).addTo(maps.rewind);
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

    // Clear old markers
    Object.values(markers.rewind).forEach(marker => marker.remove());
    markers.rewind = {};

    // Calculate target time
    const targetTime = new Date(new Date(currentSighting.sighting_time).getTime() + offsetMinutes * 60000);

    // Filter positions within 30 seconds of target time
    const timeWindow = 30000; // 30 seconds
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
        const icon = L.divIcon({
            className: 'aircraft-icon',
            html: `<div style="transform: rotate(${pos.track || 0}deg); color: #4a90e2; font-size: 16px;">✈</div>`,
            iconSize: [20, 20]
        });

        const marker = L.marker([pos.lat, pos.lon], { icon })
            .bindPopup(`
                <strong>${pos.callsign || pos.icao_hex}</strong><br>
                Altitude: ${pos.altitude || 'N/A'} ft<br>
                Speed: ${pos.ground_speed || 'N/A'} kts<br>
                Heading: ${pos.track || 'N/A'}°<br>
                Distance: ${pos.distance_miles} mi<br>
                Time: ${new Date(pos.timestamp).toLocaleTimeString()}
            `)
            .addTo(maps.rewind);

        markers.rewind[pos.icao_hex] = marker;
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
            matchList.innerHTML = '<div class="no-match">No ADS-B match found</div>';
        } else {
            matches.forEach(match => {
                const div = document.createElement('div');
                div.className = 'match-item';
                div.innerHTML = `
                    <div class="callsign">${match.callsign || match.icao_hex}</div>
                    <div class="details">
                        <span><strong>ICAO:</strong> ${match.icao_hex}</span>
                        <span><strong>Distance:</strong> ${match.closest_distance} mi</span>
                        <span><strong>Altitude:</strong> ${match.altitude || 'N/A'} ft</span>
                        <span><strong>Speed:</strong> ${match.ground_speed || 'N/A'} kts</span>
                        <span><strong>Heading:</strong> ${match.track || 'N/A'}°</span>
                        <span><strong>Closest at:</strong> ${new Date(match.closest_time).toLocaleTimeString()}</span>
                    </div>
                `;
                matchList.appendChild(div);
            });
        }
    } catch (error) {
        console.error('Error finding matches:', error);
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
