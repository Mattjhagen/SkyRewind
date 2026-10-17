// Dashboard auto-refresh - fetches /api/status every 10s

let lastSuccessfulFetch = null;
let fetchFailed = false;

// Update clock every second
function updateClock() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('clock').textContent = `${hours}:${mins}:${secs}`;
}

setInterval(updateClock, 1000);
updateClock();

// Fetch and update dashboard
async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        lastSuccessfulFetch = data.time;
        fetchFailed = false;

        // Hide error banner
        document.getElementById('error-banner').style.display = 'none';

        // Update all sections
        updateServices(data.services);
        updatePipeline(data.pipeline);
        updateSystem(data.system);
        updatePorts(data.ports);
        updateBridgeLog(data.bridge_log);

        // Update footer timestamp
        const updateTime = new Date(data.time);
        document.getElementById('last-update').textContent = updateTime.toLocaleTimeString();

    } catch (error) {
        console.error('Failed to fetch status:', error);
        fetchFailed = true;

        // Show error banner
        document.getElementById('error-banner').style.display = 'block';

        // Keep last values but show stale indicator
        if (lastSuccessfulFetch) {
            document.getElementById('last-update').textContent =
                `${new Date(lastSuccessfulFetch).toLocaleTimeString()} (STALE)`;
        }
    }
}

function updateServices(services) {
    const container = document.getElementById('services-list');
    container.innerHTML = '';

    services.forEach(svc => {
        const row = document.createElement('div');
        row.className = 'service-row';

        const name = document.createElement('div');
        name.className = 'service-name';
        name.textContent = svc.name;

        const status = document.createElement('div');
        status.className = 'service-status';

        // Determine status
        if (svc.looping) {
            status.textContent = 'LOOPING';
            status.classList.add('status-looping');
        } else if (svc.active === true && svc.sub === 'running') {
            status.textContent = 'RUNNING';
            status.classList.add('status-running');
        } else if (svc.active === true) {
            status.textContent = svc.sub?.toUpperCase() || 'ACTIVE';
            status.classList.add('status-running');
        } else if (svc.active === false) {
            status.textContent = svc.sub?.toUpperCase() || 'FAILED';
            status.classList.add('status-failed');
        } else {
            status.textContent = 'UNKNOWN';
            status.classList.add('status-down');
        }

        row.appendChild(name);
        row.appendChild(status);
        container.appendChild(row);
    });
}

function updatePipeline(pipeline) {
    // Aircraft count
    const aircraft = pipeline.aircraft !== null ? pipeline.aircraft : '--';
    document.getElementById('pipeline-aircraft').textContent = aircraft;

    // Messages
    const messages = pipeline.messages !== null ? pipeline.messages.toLocaleString() : '--';
    document.getElementById('pipeline-messages').textContent = messages;

    // Last update time
    let lastUpdate = '--';
    if (pipeline.last_write) {
        const date = new Date(pipeline.last_write);
        lastUpdate = date.toLocaleTimeString();
    }
    document.getElementById('pipeline-last').textContent = lastUpdate;

    // JSON age
    let age = '--';
    if (pipeline.aircraft_json_age_sec !== null) {
        const sec = pipeline.aircraft_json_age_sec;
        if (sec < 60) {
            age = `${sec}s ago`;
        } else if (sec < 3600) {
            age = `${Math.floor(sec / 60)}m ago`;
        } else {
            age = `${Math.floor(sec / 3600)}h ago`;
        }
    } else if (!pipeline.aircraft_json_exists) {
        age = 'missing';
    }
    document.getElementById('pipeline-age').textContent = age;
}

function updateSystem(system) {
    document.getElementById('system-uptime').textContent = system.uptime || '--';
    document.getElementById('system-load').textContent = system.load || '--';

    const mem = system.mem_used_pct !== null ? `${system.mem_used_pct}%` : '--%';
    document.getElementById('system-mem').textContent = mem;

    const disk = system.disk_used_pct !== null ? `${system.disk_used_pct}%` : '--%';
    document.getElementById('system-disk').textContent = disk;

    const temp = system.temp_c !== null ? `${system.temp_c}°C` : '--°C';
    document.getElementById('system-temp').textContent = temp;
}

function updatePorts(ports) {
    const container = document.getElementById('ports-list');
    container.innerHTML = '';

    const portMap = {
        '5000_web': 'SkyRewind :5000',
        '3001_blog': 'SDR Blog :3001',
        '5001_dashboard': 'Dashboard :5001'
    };

    Object.entries(ports).forEach(([key, value]) => {
        const row = document.createElement('div');
        row.className = 'port-row';

        const name = document.createElement('div');
        name.className = 'port-name';
        name.textContent = portMap[key] || key;

        const status = document.createElement('div');
        status.className = 'port-status';
        status.textContent = value.toUpperCase();
        status.classList.add(value === 'up' ? 'status-up' : 'status-down');

        row.appendChild(name);
        row.appendChild(status);
        container.appendChild(row);
    });
}

function updateBridgeLog(logLines) {
    const container = document.getElementById('bridge-log');
    container.innerHTML = '';

    if (!logLines || logLines.length === 0) {
        container.textContent = '(no log lines)';
        return;
    }

    logLines.forEach(line => {
        const div = document.createElement('div');
        div.className = 'log-line';
        div.textContent = line;
        container.appendChild(div);
    });
}

// Initial fetch and set up 10s interval
fetchStatus();
setInterval(fetchStatus, 10000);
