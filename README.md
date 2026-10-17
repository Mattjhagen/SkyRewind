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
- **Data Source**: dump1090-mutability (ADS-B decoder)

## Prerequisites

- Ubuntu 24.04 (or similar Linux distribution)
- Python 3.8+
- dump1090-mutability installed
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

### 3. Enable and Start dump1090

**IMPORTANT**: dump1090 must be running to collect live ADS-B data.

```bash
# Enable dump1090 to start on boot
sudo systemctl enable dump1090-mutability

# Start dump1090 now
sudo systemctl start dump1090-mutability

# Check status
sudo systemctl status dump1090-mutability
```

**Note**: dump1090 owns the RTL-SDR dongle exclusively. If you need the dongle for other applications, stop dump1090 first:

```bash
sudo systemctl stop dump1090-mutability
```

### 4. Initialize Database

The database will be created automatically when you first run the application, but you can also initialize it manually:

```bash
python backend/app.py  # Starts the web server and initializes DB
```

## Usage

### Starting the Logger

The logger polls `/var/run/dump1090-mutability/aircraft.json` every 10 seconds and stores positions in the SQLite database.

```bash
# From the project root
python logger/adsb_logger.py
```

Keep this running continuously (see Production Deployment below for systemd setup).

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

### Running as systemd Services

Create systemd service files for automatic startup and restart on failure.

#### ADS-B Logger Service

Create `/etc/systemd/system/skyrewind-logger.service`:

```ini
[Unit]
Description=SkyRewind ADS-B Logger
After=network.target dump1090-mutability.service
Requires=dump1090-mutability.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/skyrewind
ExecStart=/path/to/skyrewind/venv/bin/python logger/adsb_logger.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Web Server Service

Create `/etc/systemd/system/skyrewind-web.service`:

```ini
[Unit]
Description=SkyRewind Web Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/skyrewind
Environment="FLASK_ENV=production"
ExecStart=/path/to/skyrewind/venv/bin/python backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable skyrewind-logger skyrewind-web
sudo systemctl start skyrewind-logger skyrewind-web

# Check status
sudo systemctl status skyrewind-logger
sudo systemctl status skyrewind-web
```

### Using Gunicorn (Recommended for Production)

For better performance, use Gunicorn instead of Flask's development server:

```bash
pip install gunicorn
```

Update the web service ExecStart:

```ini
ExecStart=/path/to/skyrewind/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app
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
app.run(host='0.0.0.0', port=8080, debug=True)
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

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
