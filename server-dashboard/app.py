#!/usr/bin/env python3
"""
SkyRewind Server Dashboard - LAN-only monitoring for r410
Read-only v1: displays service status, pipeline health, system metrics
DO NOT expose publicly - bind to LAN only, no auth, shows service logs
"""

from flask import Flask, render_template, jsonify
import subprocess
import json
import os
import shutil
from datetime import datetime, timezone
import socket

app = Flask(__name__)

# Fixed command allowlist - no user input, no shell=True
SYSTEMD_SERVICES = [
    'skyrewind-web',
    'skyrewind-logger',
    'skyrewind-adsb-bridge'
]

def safe_subprocess(cmd, timeout=3):
    """Run subprocess with fixed command, timeout, no shell. Never crash."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return result.stdout, result.stderr, result.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        return '', str(e), -1

def get_systemd_service_status(service_name):
    """Get systemd service status: active, sub-state, restart count."""
    try:
        # Get active state
        stdout, _, code = safe_subprocess(['systemctl', 'is-active', service_name])
        active = code == 0

        # Get sub-state (running/exited/failed)
        stdout_sub, _, _ = safe_subprocess(['systemctl', 'show', service_name, '--property=SubState'])
        sub = stdout_sub.split('=')[1].strip() if '=' in stdout_sub else 'unknown'

        # Get restart count in last 2 minutes
        restarts = 0
        if service_name == 'skyrewind-adsb-bridge':
            stdout_log, _, _ = safe_subprocess([
                'journalctl', '-u', service_name, '--since', '2 minutes ago', '-n', '100'
            ])
            restarts = stdout_log.count('Started')

        return {
            'name': service_name,
            'active': active,
            'sub': sub,
            'restarts_2min': restarts if service_name == 'skyrewind-adsb-bridge' else None
        }
    except Exception:
        return {
            'name': service_name,
            'active': False,
            'sub': 'unknown',
            'restarts_2min': None
        }

def check_bridge_looping():
    """Detect if bridge is in restart loop: >= 5 'rtl_adsb died' in last 2 min."""
    try:
        stdout, _, _ = safe_subprocess([
            'journalctl', '-u', 'skyrewind-adsb-bridge', '--since', '2 minutes ago', '-n', '100'
        ])
        died_count = stdout.count('rtl_adsb died')
        return died_count >= 5
    except Exception:
        return False

def get_cloudflared_status():
    """Check if cloudflared process is running."""
    try:
        stdout, _, code = safe_subprocess(['pgrep', '-x', 'cloudflared'])
        return code == 0
    except Exception:
        return False

def check_port(port):
    """Check if a port is listening."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False

def get_pipeline_status():
    """Read aircraft.json and extract metrics."""
    aircraft_json_path = '/var/run/dump1090-mutability/aircraft.json'

    try:
        if not os.path.exists(aircraft_json_path):
            return {
                'aircraft_json_exists': False,
                'aircraft_json_age_sec': None,
                'messages': None,
                'aircraft': None,
                'last_write': None
            }

        # Get file age
        stat = os.stat(aircraft_json_path)
        age_sec = int(datetime.now(timezone.utc).timestamp() - stat.st_mtime)
        last_write = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        # Parse JSON
        with open(aircraft_json_path, 'r') as f:
            data = json.load(f)
            messages = data.get('messages', 0)
            aircraft = len(data.get('aircraft', []))

        return {
            'aircraft_json_exists': True,
            'aircraft_json_age_sec': age_sec,
            'messages': messages,
            'aircraft': aircraft,
            'last_write': last_write
        }
    except Exception:
        return {
            'aircraft_json_exists': os.path.exists(aircraft_json_path),
            'aircraft_json_age_sec': None,
            'messages': None,
            'aircraft': None,
            'last_write': None
        }

def get_system_stats():
    """Get system uptime, load, memory, disk, temperature."""
    stats = {
        'uptime': 'unknown',
        'load': 'unknown',
        'mem_used_pct': None,
        'disk_used_pct': None,
        'temp_c': None
    }

    # Uptime
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_sec = int(float(f.read().split()[0]))
            days = uptime_sec // 86400
            hours = (uptime_sec % 86400) // 3600
            mins = (uptime_sec % 3600) // 60
            stats['uptime'] = f"{days}d {hours}h {mins}m"
    except Exception:
        pass

    # Load average
    try:
        with open('/proc/loadavg', 'r') as f:
            load_parts = f.read().split()
            stats['load'] = f"{load_parts[0]} {load_parts[1]} {load_parts[2]}"
    except Exception:
        pass

    # Memory
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
            total = meminfo.get('MemTotal', 0)
            available = meminfo.get('MemAvailable', 0)
            if total > 0:
                used = total - available
                stats['mem_used_pct'] = round((used / total) * 100, 1)
    except Exception:
        pass

    # Disk
    try:
        usage = shutil.disk_usage('/')
        stats['disk_used_pct'] = round((usage.used / usage.total) * 100, 1)
    except Exception:
        pass

    # Temperature
    try:
        thermal_zones = ['/sys/class/thermal/thermal_zone0/temp']
        for zone in thermal_zones:
            if os.path.exists(zone):
                with open(zone, 'r') as f:
                    temp = int(f.read().strip()) / 1000
                    stats['temp_c'] = round(temp, 1)
                    break
    except Exception:
        pass

    return stats

def get_bridge_log():
    """Get last 5 lines of bridge journal, truncated to 160 chars each."""
    try:
        stdout, _, _ = safe_subprocess([
            'journalctl', '-u', 'skyrewind-adsb-bridge', '-n', '5', '--no-pager'
        ])
        lines = stdout.strip().split('\n')
        # Truncate each line to 160 chars
        truncated = [line[:160] for line in lines if line.strip()]
        return truncated[-5:]  # Last 5 only
    except Exception:
        return ['(journal unavailable)']

@app.route('/')
def index():
    """Serve dashboard page."""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """
    Get server status - no params, no user input.
    Returns JSON with services, pipeline, system, ports, bridge log.
    """
    # Services
    services = []

    # Systemd services
    for svc in SYSTEMD_SERVICES:
        svc_status = get_systemd_service_status(svc)
        if svc == 'skyrewind-adsb-bridge':
            svc_status['looping'] = check_bridge_looping()
        services.append(svc_status)

    # Cloudflared
    services.append({
        'name': 'cloudflared (tunnel)',
        'active': get_cloudflared_status(),
        'sub': None,
        'restarts_2min': None
    })

    # SDR Blog
    services.append({
        'name': 'SDR Blog node :3001',
        'active': check_port(3001),
        'sub': None,
        'restarts_2min': None
    })

    # Pipeline
    pipeline = get_pipeline_status()

    # System
    system = get_system_stats()

    # Ports
    ports = {
        '5000_web': 'up' if check_port(5000) else 'down',
        '3001_blog': 'up' if check_port(3001) else 'down',
        '5001_dashboard': 'up'  # This endpoint responding = dashboard is up
    }

    # Bridge log
    bridge_log = get_bridge_log()

    return jsonify({
        'time': datetime.now(timezone.utc).isoformat(),
        'services': services,
        'pipeline': pipeline,
        'system': system,
        'ports': ports,
        'bridge_log': bridge_log
    })

if __name__ == '__main__':
    # Bind to 0.0.0.0:5001 for LAN access
    # WARNING: LAN-only, no auth, shows service logs - DO NOT expose publicly
    app.run(host='0.0.0.0', port=5001, debug=False)
