#!/bin/bash
# ============================================================
# Tour Guide Audio Streamer - Raspberry Pi Setup Script
# ============================================================
# Run this ONCE on a fresh Raspberry Pi OS Lite installation.
# Usage: sudo bash install.sh
#
# Tested on: Raspberry Pi 3B+ / Debian 13 (trixie) / aarch64
# ============================================================

set -e

# --- Configuration ---
STREAM_PASSWORD="tourguide123"
ADMIN_PASSWORD="admin123"
WIFI_SSID="TourGuide"
WIFI_PASSWORD="listen123"
WIFI_CHANNEL=6
STREAM_PORT=8000
ADMIN_PORT=8080
RECORDINGS_DIR="/home/pi/recordings"
WEB_DIR="/home/pi/tourguide-web"
PI_IP="192.168.4.1"  # Static IP when Pi is the hotspot

echo "============================================"
echo "  Tour Guide Audio Streamer - Setup"
echo "============================================"
echo ""
echo "This script will configure your Raspberry Pi as:"
echo "  - WiFi Hotspot (SSID: $WIFI_SSID)"
echo "  - Audio streaming server (Icecast + FFmpeg)"
echo "  - Recording server"
echo "  - Web server for visitor landing page"
echo ""
echo "Press Enter to continue or Ctrl+C to cancel..."
read -r

# --- Step 1: System Update ---
echo "[1/8] Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt update
# Skip upgrade to avoid interactive prompts from packages like rpi-chromium-mods
# apt upgrade -y

# --- Step 2: Install Dependencies ---
echo "[2/8] Installing dependencies..."
apt install -y \
    icecast2 \
    ffmpeg \
    alsa-utils \
    hostapd \
    dnsmasq \
    nginx-light \
    python3 \
    python3-pip \
    qrencode

# --- Step 3: Configure WiFi Hotspot (hostapd) ---
echo "[3/8] Configuring WiFi hotspot..."

# Stop services during config
systemctl stop hostapd 2>/dev/null || true
systemctl stop dnsmasq 2>/dev/null || true

# Configure static IP for wlan0
# Newer Pi OS (Debian 13+) uses NetworkManager, older uses dhcpcd
if [ -f /etc/dhcpcd.conf ]; then
    # dhcpcd-based systems (older Pi OS)
    if ! grep -q "tourguide" /etc/dhcpcd.conf; then
        echo "" >> /etc/dhcpcd.conf
        echo "# --- Tour Guide Hotspot ---" >> /etc/dhcpcd.conf
        echo "interface wlan0" >> /etc/dhcpcd.conf
        echo "    static ip_address=${PI_IP}/24" >> /etc/dhcpcd.conf
        echo "    nohook wpa_supplicant" >> /etc/dhcpcd.conf
    fi
    echo "[OK] dhcpcd configured"
else
    echo "[OK] No dhcpcd.conf found (using NetworkManager)"
fi

# If NetworkManager is present, tell it to ignore wlan0
if systemctl is-active NetworkManager >/dev/null 2>&1; then
    mkdir -p /etc/NetworkManager/conf.d
    cat > /etc/NetworkManager/conf.d/tourguide.conf <<NMEOF
[keyfile]
unmanaged-devices=interface-name:wlan0
NMEOF
    echo "[OK] NetworkManager will ignore wlan0"
fi

# Disable wpa_supplicant (conflicts with hostapd)
systemctl disable wpa_supplicant 2>/dev/null || true
systemctl stop wpa_supplicant 2>/dev/null || true
echo "[OK] wpa_supplicant disabled"

# Configure static IP via systemd-networkd (works on all systems)
mkdir -p /etc/systemd/network
cat > /etc/systemd/network/10-wlan0.network <<NETEOF
[Match]
Name=wlan0

[Network]
Address=${PI_IP}/24
DHCPServer=no
NETEOF
systemctl enable systemd-networkd
echo "[OK] Static IP ${PI_IP} configured"

# hostapd config
cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=${WIFI_SSID}
hw_mode=g
channel=${WIFI_CHANNEL}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${WIFI_PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Point hostapd to config (older systems)
[ -f /etc/default/hostapd ] && sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd || true

# Unmask and enable hostapd
systemctl unmask hostapd 2>/dev/null || true
systemctl enable hostapd
echo "[OK] hostapd configured and enabled"

# dnsmasq config (DHCP server for connected phones)
cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup 2>/dev/null || true
cat > /etc/dnsmasq.conf <<EOF
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.50,255.255.255.0,24h
# Captive portal: redirect all DNS to Pi
address=/#/${PI_IP}
EOF
echo "[OK] dnsmasq configured"

# Enable IP forwarding
touch /etc/sysctl.conf
grep -q "ip_forward=1" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -w net.ipv4.ip_forward=1 2>/dev/null || true
echo "[OK] IP forwarding enabled"

# --- Step 4: Configure Icecast ---
echo "[4/8] Configuring Icecast..."

cat > /etc/icecast2/icecast.xml <<EOF
<icecast>
    <limits>
        <clients>100</clients>
        <sources>4</sources>
        <queue-size>131072</queue-size>
        <client-timeout>30</client-timeout>
        <header-timeout>15</header-timeout>
        <source-timeout>10</source-timeout>
        <burst-on-connect>0</burst-on-connect>
        <burst-size>0</burst-size>
    </limits>

    <authentication>
        <source-password>${STREAM_PASSWORD}</source-password>
        <relay-password>${STREAM_PASSWORD}</relay-password>
        <admin-user>admin</admin-user>
        <admin-password>${ADMIN_PASSWORD}</admin-password>
    </authentication>

    <hostname>localhost</hostname>

    <listen-socket>
        <port>${STREAM_PORT}</port>
        <bind-address>0.0.0.0</bind-address>
    </listen-socket>

    <fileserve>1</fileserve>

    <paths>
        <basedir>/usr/share/icecast2</basedir>
        <logdir>/var/log/icecast2</logdir>
        <webroot>/usr/share/icecast2/web</webroot>
        <adminroot>/usr/share/icecast2/admin</adminroot>
        <alias source="/" destination="/status.xsl"/>
    </paths>

    <logging>
        <accesslog>access.log</accesslog>
        <errorlog>error.log</errorlog>
        <loglevel>3</loglevel>
    </logging>

    <security>
        <chroot>0</chroot>
    </security>
</icecast>
EOF

# Enable Icecast
sed -i 's/ENABLE=false/ENABLE=true/' /etc/default/icecast2
systemctl enable icecast2
echo "[OK] Icecast configured (low-latency: burst disabled, queue 128KB)"

# --- Step 5: Create Directories ---
echo "[5/8] Creating directories..."
mkdir -p "$RECORDINGS_DIR"
mkdir -p "$WEB_DIR"
chown -R pi:pi "$RECORDINGS_DIR"
chown -R pi:pi "$WEB_DIR"

# Fix home directory permissions so nginx (www-data) can serve files
chmod 755 /home/pi
echo "[OK] Directories created, permissions set"

# --- Step 6: Configure Nginx (Web Server for Landing Page + Admin) ---
echo "[6/8] Configuring web server..."

cat > /etc/nginx/sites-available/tourguide <<EOF
server {
    listen 80 default_server;
    server_name _;

    # Visitor landing page
    root ${WEB_DIR};
    index index.html;

    # Proxy audio stream from Icecast
    location /listen {
        proxy_pass http://127.0.0.1:${STREAM_PORT}/listen;
        proxy_set_header Host \$host;
        proxy_buffering off;
        proxy_request_buffering off;
        chunked_transfer_encoding on;
    }

    # Icecast status API (for listener count)
    location /status-json.xsl {
        proxy_pass http://127.0.0.1:${STREAM_PORT}/status-json.xsl;
    }

    # Admin API for recordings
    location /api/ {
        proxy_pass http://127.0.0.1:${ADMIN_PORT}/;
    }

    # Serve recordings for download
    location /recordings/ {
        alias ${RECORDINGS_DIR}/;
        autoindex off;
    }

    # Captive portal: redirect any unknown URL to landing page
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

ln -sf /etc/nginx/sites-available/tourguide /etc/nginx/sites-enabled/tourguide
rm -f /etc/nginx/sites-enabled/default
systemctl enable nginx
echo "[OK] Nginx configured"

# --- Step 7: Create Streaming Service ---
echo "[7/8] Creating streaming service..."

# NOTE: Uses plughw (not hw) for ALSA format conversion (mono mic input)
# NOTE: Uses MP3 for lower latency than Opus/OGG with Icecast
# NOTE: USB sound card is typically card 2, auto-detected below
cat > /usr/local/bin/tourguide-stream.sh <<'SCRIPT'
#!/bin/bash
# Tour Guide Audio Streaming Script
# Streams audio from USB sound card to Icecast via MP3

RECORDINGS_DIR="/home/pi/recordings"
STREAM_PASSWORD="tourguide123"
STREAM_PORT=8000

mkdir -p "$RECORDINGS_DIR"

# Auto-detect USB sound card number
USB_CARD=$(arecord -l 2>/dev/null | grep -i "usb" | head -1 | sed 's/card \([0-9]*\).*/\1/')
if [ -z "$USB_CARD" ]; then
    echo "[ERROR] No USB sound card detected!"
    echo "Available audio devices:"
    arecord -l
    exit 1
fi
echo "[OK] USB sound card found: card $USB_CARD"
echo "[OK] Streaming on port $STREAM_PORT"
echo "[OK] Stream URL: http://192.168.4.1/listen"

# Stream to Icecast using MP3 (low latency)
# - plughw allows ALSA to handle mono conversion
# - channels 1 + sample_rate 44100 for mic input
# - MP3 64k is clear enough for speech
exec ffmpeg -nostdin -f alsa -channels 1 -sample_rate 44100 -thread_queue_size 512 -i "plughw:${USB_CARD},0" -c:a libmp3lame -b:a 64k -ar 44100 -ac 1 -flush_packets 1 -content_type audio/mpeg -f mp3 "icecast://source:${STREAM_PASSWORD}@localhost:${STREAM_PORT}/listen"
SCRIPT

chmod +x /usr/local/bin/tourguide-stream.sh

# Systemd service for auto-start
cat > /etc/systemd/system/tourguide-stream.service <<EOF
[Unit]
Description=Tour Guide Audio Stream
After=network.target icecast2.service
Requires=icecast2.service

[Service]
Type=simple
User=pi
ExecStartPre=/bin/sleep 3
ExecStart=/usr/local/bin/tourguide-stream.sh
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tourguide-stream
echo "[OK] Streaming service created"

# --- Step 8: Create Admin API Server ---
echo "[8/8] Creating admin API server..."

cat > /usr/local/bin/tourguide-admin.py <<'PYEOF'
#!/usr/bin/env python3
"""
Tour Guide Admin API
Serves recording management + stream status endpoints.
Runs on port 8080, proxied via nginx at /api/
"""

import os
import json
import subprocess
import glob
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

RECORDINGS_DIR = "/home/pi/recordings"
STREAM_SERVICE = "tourguide-stream"


class AdminHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/recordings":
            self._list_recordings()
        elif path == "/status":
            self._stream_status()
        elif path == "/disk":
            self._disk_info()
        elif path.startswith("/recordings/delete"):
            params = parse_qs(parsed.query)
            filename = params.get("file", [None])[0]
            self._delete_recording(filename)
        elif path == "/cleanup":
            params = parse_qs(parsed.query)
            days = int(params.get("days", [30])[0])
            self._cleanup_old(days)
        else:
            self._json_response(404, {"error": "Not found"})

    def _list_recordings(self):
        recordings = []
        for f in sorted(glob.glob(f"{RECORDINGS_DIR}/tour_*.ogg"), reverse=True):
            stat = os.stat(f)
            name = os.path.basename(f)
            duration_sec = self._get_duration(f)
            recordings.append({
                "filename": name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "duration_min": round(duration_sec / 60, 1) if duration_sec else None,
                "download_url": f"/recordings/{name}",
            })
        self._json_response(200, {"recordings": recordings, "count": len(recordings)})

    def _stream_status(self):
        result = subprocess.run(
            ["systemctl", "is-active", STREAM_SERVICE],
            capture_output=True, text=True
        )
        is_active = result.stdout.strip() == "active"

        listeners = 0
        try:
            import urllib.request
            resp = urllib.request.urlopen("http://localhost:8000/status-json.xsl", timeout=2)
            data = json.loads(resp.read())
            source = data.get("icestats", {}).get("source")
            if isinstance(source, dict):
                listeners = source.get("listeners", 0)
            elif isinstance(source, list):
                listeners = sum(s.get("listeners", 0) for s in source)
        except Exception:
            pass

        current_recording = None
        ogg_files = sorted(glob.glob(f"{RECORDINGS_DIR}/tour_*.ogg"), reverse=True)
        if ogg_files and is_active:
            current_recording = os.path.basename(ogg_files[0])

        self._json_response(200, {
            "streaming": is_active,
            "listeners": listeners,
            "current_recording": current_recording,
        })

    def _disk_info(self):
        stat = os.statvfs(RECORDINGS_DIR)
        free_gb = round((stat.f_frsize * stat.f_bavail) / (1024 ** 3), 2)
        total_gb = round((stat.f_frsize * stat.f_blocks) / (1024 ** 3), 2)
        self._json_response(200, {"free_gb": free_gb, "total_gb": total_gb})

    def _delete_recording(self, filename):
        if not filename or ".." in filename or "/" in filename:
            self._json_response(400, {"error": "Invalid filename"})
            return
        filepath = os.path.join(RECORDINGS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            self._json_response(200, {"deleted": filename})
        else:
            self._json_response(404, {"error": "File not found"})

    def _cleanup_old(self, days):
        cutoff = datetime.now() - timedelta(days=days)
        deleted = []
        for f in glob.glob(f"{RECORDINGS_DIR}/tour_*.ogg"):
            if datetime.fromtimestamp(os.stat(f).st_ctime) < cutoff:
                os.remove(f)
                deleted.append(os.path.basename(f))
        self._json_response(200, {"deleted": deleted, "count": len(deleted)})

    def _get_duration(self, filepath):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", filepath],
                capture_output=True, text=True, timeout=5
            )
            return float(result.stdout.strip())
        except Exception:
            return None

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass  # Suppress request logs


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8080), AdminHandler)
    print("[OK] Admin API running on port 8080")
    server.serve_forever()
PYEOF

chmod +x /usr/local/bin/tourguide-admin.py

# Systemd service for admin API
cat > /etc/systemd/system/tourguide-admin.service <<EOF
[Unit]
Description=Tour Guide Admin API
After=network.target

[Service]
Type=simple
User=pi
ExecStart=/usr/bin/python3 /usr/local/bin/tourguide-admin.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tourguide-admin

# --- Copy web files if present in home directory ---
[ -f /home/pi/index.html ] && cp /home/pi/index.html "$WEB_DIR/"
[ -f /home/pi/admin.html ] && cp /home/pi/admin.html "$WEB_DIR/"

# --- Generate QR Code ---
echo ""
echo "Generating QR code..."
qrencode -t PNG -o "${WEB_DIR}/qr.png" -s 10 "http://${PI_IP}/"
qrencode -t UTF8 "http://${PI_IP}/"

# --- Set mic input to 40% to reduce background noise ---
USB_CARD=$(arecord -l 2>/dev/null | grep -i "usb" | head -1 | sed 's/card \([0-9]*\).*/\1/')
if [ -n "$USB_CARD" ]; then
    amixer -c "$USB_CARD" sset PCM 40% 2>/dev/null || true
    echo "[OK] USB mic input set to 40%"
fi

# --- Done ---
echo ""
echo "============================================"
echo "  SETUP COMPLETE!"
echo "============================================"
echo ""
echo "  WiFi Network:  $WIFI_SSID"
echo "  WiFi Password: $WIFI_PASSWORD"
echo "  Stream URL:    http://${PI_IP}/listen"
echo "  Landing Page:  http://${PI_IP}/"
echo "  Admin Page:    http://${PI_IP}/admin.html"
echo "  QR Code:       ${WEB_DIR}/qr.png"
echo ""
echo "  Recordings:    $RECORDINGS_DIR"
echo ""
echo "  REBOOT NOW to activate the WiFi hotspot:"
echo "  sudo reboot"
echo ""
echo "  NOTE: After reboot, Pi becomes a WiFi hotspot."
echo "  Connect to '$WIFI_SSID' WiFi to access the Pi."
echo "  SSH: ssh pi@${PI_IP}"
echo ""
echo "============================================"
