from flask import Flask, request, jsonify, send_from_directory
import os
import fcntl
from datetime import datetime, timedelta, timezone
import math
from werkzeug.utils import secure_filename

try:
    from database import (
        init_db, get_sightings, get_sighting, insert_sighting,
        get_positions_in_timerange, get_latest_positions, get_db
    )
    from seed_data import seed_demo_data
except ImportError:
    from backend.database import (
        init_db, get_sightings, get_sighting, insert_sighting,
        get_positions_in_timerange, get_latest_positions, get_db
    )
    from backend.seed_data import seed_demo_data

# Configure Flask to serve static files from frontend directory
FRONTEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
app = Flask(__name__, static_folder=FRONTEND_PATH, static_url_path='/static')

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in miles."""
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@app.route('/')
def index():
    """Serve the main frontend."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    return send_from_directory(frontend_path, 'index.html')

@app.route('/manifest.json')
def manifest():
    """Serve PWA manifest."""
    return send_from_directory(FRONTEND_PATH, 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    """Serve service worker at root scope."""
    response = send_from_directory(FRONTEND_PATH, 'sw.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route('/favicon.svg')
def favicon():
    """Serve SVG favicon."""
    return send_from_directory(FRONTEND_PATH, 'favicon.svg', mimetype='image/svg+xml')

@app.route('/icons/<path:filename>')
def icons(filename):
    """Serve PWA icons."""
    return send_from_directory(os.path.join(FRONTEND_PATH, 'icons'), filename)

@app.route('/api/sightings', methods=['GET', 'POST'])
def sightings():
    """Get all sightings or create a new one."""
    if request.method == 'GET':
        return jsonify(get_sightings())

    # POST - create new sighting
    data = request.form if request.files else request.json

    # Validate required fields
    required_fields = ['reporter_name', 'sighting_time', 'lat', 'lon', 'description']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Handle photo upload
    photo_path = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename:
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > MAX_FILE_SIZE:
                return jsonify({'error': 'File size exceeds 10MB limit'}), 413

            if allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now(timezone.utc).timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path = filename

    try:
        sighting_id = insert_sighting(
            reporter_name=data.get('reporter_name'),
            sighting_time=data.get('sighting_time'),
            lat=float(data.get('lat')),
            lon=float(data.get('lon')),
            location_text=data.get('location_text'),
            bearing=float(data.get('bearing')) if data.get('bearing') else None,
            elevation=float(data.get('elevation')) if data.get('elevation') else None,
            description=data.get('description'),
            duration=data.get('duration'),
            photo_path=photo_path
        )
    except (ValueError, TypeError) as e:
        return jsonify({'error': f'Invalid data: {str(e)}'}), 400

    return jsonify({'id': sighting_id, 'success': True}), 201

@app.route('/api/sightings/<int:sighting_id>')
def get_sighting_detail(sighting_id):
    """Get a specific sighting."""
    sighting = get_sighting(sighting_id)
    if not sighting:
        return jsonify({'error': 'Sighting not found'}), 404
    return jsonify(sighting)

@app.route('/api/positions/rewind')
def rewind_positions():
    """Get ADS-B positions for a time range and location."""
    try:
        center_time = request.args.get('time')
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        radius = float(request.args.get('radius', 25))  # miles
        time_window = int(request.args.get('time_window', 10))  # minutes

        # Parse center time
        center_dt = datetime.fromisoformat(center_time.replace('Z', '+00:00'))

        # Get positions within time window
        start_time = (center_dt - timedelta(minutes=time_window)).isoformat()
        end_time = (center_dt + timedelta(minutes=time_window)).isoformat()

        all_positions = get_positions_in_timerange(start_time, end_time)

        # Filter by distance
        filtered_positions = []
        for pos in all_positions:
            distance = haversine_distance(lat, lon, pos['lat'], pos['lon'])
            if distance <= radius:
                pos['distance_miles'] = round(distance, 2)
                filtered_positions.append(pos)

        return jsonify(filtered_positions)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/positions/match')
def match_aircraft():
    """Find candidate aircraft for a sighting."""
    try:
        sighting_id = request.args.get('sighting_id')
        if not sighting_id:
            return jsonify({'error': 'sighting_id required'}), 400

        sighting = get_sighting(int(sighting_id))
        if not sighting:
            return jsonify({'error': 'Sighting not found'}), 404

        # Parse sighting time
        sighting_time = datetime.fromisoformat(sighting['sighting_time'].replace('Z', '+00:00'))

        # Get positions within ±10 minutes
        start_time = (sighting_time - timedelta(minutes=10)).isoformat()
        end_time = (sighting_time + timedelta(minutes=10)).isoformat()

        all_positions = get_positions_in_timerange(start_time, end_time)

        # Default radius: 25 miles
        radius = float(request.args.get('radius', 25))

        # Find closest approach for each aircraft
        candidates = {}
        for pos in all_positions:
            icao = pos['icao_hex']
            distance = haversine_distance(
                sighting['lat'], sighting['lon'],
                pos['lat'], pos['lon']
            )

            if distance <= radius:
                if icao not in candidates or distance < candidates[icao]['closest_distance']:
                    candidates[icao] = {
                        'icao_hex': icao,
                        'callsign': pos['callsign'],
                        'altitude': pos['altitude'],
                        'ground_speed': pos['ground_speed'],
                        'track': pos['track'],
                        'closest_distance': round(distance, 2),
                        'closest_time': pos['timestamp'],
                        'lat': pos['lat'],
                        'lon': pos['lon']
                    }

        # Sort by closest distance
        result = sorted(candidates.values(), key=lambda x: x['closest_distance'])

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/positions/live')
def live_positions():
    """Get current live ADS-B positions."""
    positions = get_latest_positions()
    return jsonify(positions)

@app.route('/api/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded photos."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def auto_seed_if_needed():
    """Auto-seed demo data if SEED_DEMO=1 and database is empty.

    Uses file locking to prevent race conditions when multiple gunicorn
    workers start simultaneously. Only one worker will seed the database.
    """
    if os.environ.get('SEED_DEMO') != '1':
        return

    # Get lock file path (in same directory as database)
    lock_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'seed.lock')
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)

    try:
        # Open lock file and acquire exclusive lock
        with open(lock_path, 'w') as lock_file:
            try:
                # Non-blocking lock - if another worker has it, we skip seeding
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Another worker is seeding, skip
                return

            # We have the lock - check if seeding is still needed
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM adsb_positions')
                count = cursor.fetchone()[0]
                conn.close()

                if count == 0:
                    print(f"SEED_DEMO=1 and database is empty - seeding demo data (PID: {os.getpid()})...")
                    positions, sightings = seed_demo_data()
                    print(f"✓ Seeded {positions} ADS-B positions and {sightings} sightings (PID: {os.getpid()})")
            except Exception as e:
                print(f"Warning: Auto-seed failed: {e}")

            # Lock is automatically released when we exit the with block
    except Exception as e:
        print(f"Warning: Could not acquire seed lock: {e}")


# Initialize database and auto-seed at module level (runs on import under gunicorn)
init_db()
auto_seed_if_needed()


if __name__ == '__main__':
    # When running directly with python, init is already done at module level
    # This is idempotent, so safe to call again
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
