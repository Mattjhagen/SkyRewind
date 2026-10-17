# SkyRewind

A web application for logging ADS-B aircraft traffic and correlating sighting reports with known aircraft positions. Built for sky-watch groups to quickly determine if a reported object matches tracked aircraft.

## Features

- **Live View**: Real-time aircraft tracking with auto-refreshing map
- **Sighting Reports**: Submit detailed reports with location, bearing, time, and photos
- **Rewind & Match**: Replay historical ADS-B data around a sighting to identify candidate aircraft
- **30-Day History**: Automatic retention and pruning of position data
- **Match Analysis**: Sort candidates by closest approach distance and time

## Tech Stack

- **Backend**: Python 3, Flask, SQLite
- **Frontend**: Vanilla HTML/CSS/JavaScript, Leaflet maps
- **Decoder**: RTL-ADS-B Bridge (rtl_adsb + pyModeS)

## Prerequisites

- Ubuntu 24.04 (or similar Linux distribution)
- Python 3.8+
- rtl-sdr package (provides rtl_adsb)
- RTL-SDR USB dongle

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Mattjhagen/SkyRewind.git
cd SkyRewind
```

### 2. Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Install rtl-sdr Tools

**IMPORTANT**: The rtl_adsb decoder is required to collect live ADS-B data.

```bash
# Install rtl-sdr package (includes rtl_adsb)
sudo apt-get update
sudo apt-get install rtl-sdr

# Verify rtl_adsb is available
which rtl_adsb
```

**Note**: The RTL-ADS-B bridge owns the RTL-SDR dongle exclusively while running. Stop the bridge service if you need the dongle for other applications.

### 4. Initialize Database

The database will be created automatically when you first run the application, but you can also initialize it manually:

```bash
python backend/app.py  # Starts the web server and initializes DB
```

## Usage

### Starting the Components

**ADS-B Bridge** (decodes rtl_adsb output and writes aircraft.json):

```bash
# From the project root
python decoder/rtl_adsb_bridge.py
```

**Logger** (reads aircraft.json every 10 seconds and stores in SQLite):

```bash
# From the project root
python logger/adsb_logger.py
```

Keep both running continuously (see Production Deployment below for systemd setup).

### Starting the Web Server

```bash
# From the project root
python backend/app.py
```

The web interface will be available at `http://localhost:5000`

Access it from other devices on your network using the server's IP address: `http://<server-ip>:5000`

### Demo Mode (Testing Without Live Data)

If dump1090 is not running or you want to test with sample data:

```bash
python logger/seed_demo_data.py
```

This generates:
- 2 hours of historical ADS-B positions for 8 sample aircraft
- 3 sample sighting reports
- A mock `aircraft.json` file for testing the logger

To use the mock data with the logger, edit `logger/adsb_logger.py` and change:

```python
AIRCRAFT_JSON_PATH = '/path/to/skyrewind/data/mock_aircraft.json'
```

## Server Dashboard (LAN-only)

Monitor r410 server status on a physical display:

```bash
# Open on the server or from LAN
chromium --kiosk http://localhost:5001
# or from another LAN device:
chromium --kiosk http://192.168.0.169:5001
```

**Dashboard displays:**
- Service status (web, logger, bridge, tunnel, SDR Blog)
- Bridge loop detection (shows LOOPING when rtl_adsb restarts >= 5 times in 2 min)
- Pipeline health (aircraft count, messages, last update)
- System metrics (uptime, load, memory, disk, temperature)
- Port status (5000 web, 3001 blog, 5001 dashboard)
- Bridge journal (last 5 log lines)

**⚠️ WARNING: DO NOT EXPOSE PUBLICLY**
- Dashboard is LAN-only by design (binds 0.0.0.0:5001)
- Shows service logs and system status without authentication
- **DO NOT** add a dashboard hostname to `~/.cloudflared/config.yml`
- If you need public monitoring, build a separate authenticated dashboard

**Note:** Dashboard shows when the bridge is LOOPING but does not fix it. The loop is a known issue with rtl_adsb dying and systemd restarting it continuously.

## Configuration

### Default Settings

- **Map Center**: Omaha, NE (41.25°N, 95.95°W)
- **Timezone**: America/Chicago (all timestamps stored in UTC)
- **Search Radius**: 25 miles (configurable in UI)
- **Time Window**: ±10 minutes around sighting time
- **Data Retention**: 30 days (automatic pruning)
- **Poll Interval**: 10 seconds

### Customization

Edit these constants in the source files:

**Frontend** (`frontend/app.js`):
```javascript
const DEFAULT_CENTER = [41.25, -95.95];  // [latitude, longitude]
const DEFAULT_ZOOM = 9;
```

**Logger** (`logger/adsb_logger.py`):
```python
POLL_INTERVAL = 10  # seconds
PRUNE_INTERVAL_HOURS = 24  # how often to prune old data
```

**Database** (`backend/database.py`):
```python
def prune_old_positions(days=30):  # data retention period
```

## Production Deployment

### Automated Deployment

Use the included deployment script for a complete production setup:

```bash
sudo ./deploy.sh
```

This script will:
- Create a dedicated `skyrewind` service user
- Install SkyRewind to `/opt/skyrewind`
- Set up a Python virtual environment and install dependencies (including Gunicorn)
- Initialize the database
- Install and enable systemd service units
- Start both the logger and web server

The systemd service files are included in the `systemd/` directory:
- `systemd/skyrewind-adsb-bridge.service` - RTL-ADS-B decoder bridge
- `systemd/skyrewind-logger.service` - ADS-B position logger
- `systemd/skyrewind-web.service` - Gunicorn web server (4 workers)

After deployment, access the application at `http://<server-ip>:5000`

### Manual Service Management

```bash
# Check service status
sudo systemctl status skyrewind-adsb-bridge
sudo systemctl status skyrewind-logger
sudo systemctl status skyrewind-web

# Restart services
sudo systemctl restart skyrewind-adsb-bridge
sudo systemctl restart skyrewind-logger
sudo systemctl restart skyrewind-web

# View logs
sudo journalctl -u skyrewind-adsb-bridge -f
sudo journalctl -u skyrewind-logger -f
sudo journalctl -u skyrewind-web -f
```

### Nginx Reverse Proxy (Optional)

For HTTPS and better performance, configure Nginx as a reverse proxy:

```nginx
server {
    listen 80;
    server_name skyrewind.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Project Structure

```
skyrewind/
├── backend/
│   ├── app.py          # Flask API server
│   └── database.py     # SQLite database functions
├── frontend/
│   ├── index.html      # Main HTML
│   ├── style.css       # Styling
│   └── app.js          # Frontend logic
├── logger/
│   ├── adsb_logger.py      # ADS-B position logger
│   └── seed_demo_data.py   # Demo data generator
├── data/               # SQLite DB and uploads (not in git)
├── requirements.txt    # Python dependencies
├── .gitignore
└── README.md
```

## API Endpoints

### Sightings

- `GET /api/sightings` - List all sightings
- `POST /api/sightings` - Create new sighting
- `GET /api/sightings/<id>` - Get specific sighting

### Positions

- `GET /api/positions/live` - Current aircraft positions
- `GET /api/positions/rewind?time=<iso>&lat=<lat>&lon=<lon>&radius=<miles>` - Historical positions
- `GET /api/positions/match?sighting_id=<id>&radius=<miles>` - Find matching aircraft

## Terminology Note

This application identifies cooperative aircraft broadcasting ADS-B signals. Absence of a match means **no cooperative aircraft** was detected in the specified area and time window—it does not imply the object was anomalous or unidentified. Many aircraft do not broadcast ADS-B, and coverage depends on receiver range and line-of-sight.

## Troubleshooting

### No Aircraft Showing in Live View

1. Check dump1090 is running: `sudo systemctl status dump1090-mutability`
2. Verify aircraft.json exists: `ls -l /var/run/dump1090-mutability/aircraft.json`
3. Check if aircraft.json has data: `cat /var/run/dump1090-mutability/aircraft.json`
4. Ensure the RTL-SDR dongle is connected and recognized: `lsusb | grep RTL`
5. Check dump1090 logs: `sudo journalctl -u dump1090-mutability -f`

### Logger Not Recording Positions

1. Verify the aircraft.json path in `logger/adsb_logger.py`
2. Check file permissions
3. Run logger with verbose output to see errors
4. Verify database file is writable: `ls -l data/skyrewind.db`

### No Historical Data in Rewind View

1. Ensure the logger has been running for some time
2. Check database has data: `sqlite3 data/skyrewind.db "SELECT COUNT(*) FROM adsb_positions;"`
3. Verify timestamps are in UTC
4. Check the time range and radius settings

### Port 5000 Already in Use

Change the port in `backend/app.py`:

```python
debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
app.run(host='0.0.0.0', port=8080, debug=debug_mode)
```

## Contributing

This project is designed for a specific use case but can be adapted for other locations and requirements. Key areas for customization:

- Map center and zoom level
- Time window for matching (currently ±10 minutes)
- Search radius options
- Data retention period
- Additional aircraft data fields

## License

MIT License - See LICENSE file for details

## Acknowledgments

- dump1090-mutability for ADS-B decoding
- Leaflet for mapping
- OpenStreetMap for map tiles
- The sky-watch community

## Roadmap

### Group Chat (Planned, Not Built)

MUFON members will be able to discuss sightings in-app. Requires:
- User accounts and authentication
- Moderation tools and reporting system
- Message retention rules and privacy controls
- Real-time communication channel (WebSocket or polling)

**Why not shipped yet:** Intentionally not built as anonymous unmoderated chat. A proper group chat feature needs identity, moderation, and abuse prevention mechanisms to maintain a productive community discussion space.

### PWA Features

- **Regenerate icons:** `python3 generate_icons.py`
- Service worker provides offline support for app shell
- System notifications for new sightings (requires HTTPS/localhost)
- Install prompt on supported devices

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
