#!/usr/bin/env python3
"""
Low-latency WebSocket Audio Streaming Server
Captures audio from USB sound card and streams raw PCM via WebSocket.
Clients use Web Audio API for immediate playback (~200-500ms latency).
"""

import asyncio
import subprocess
import signal
import sys
import json
import os
import glob
from datetime import datetime, timedelta

# pip install websockets (included in install)
import websockets

# --- Configuration ---
HOST = "0.0.0.0"
WS_PORT = 8765
SAMPLE_RATE = 16000  # 16kHz is plenty for speech
CHANNELS = 1
CHUNK_SIZE = 3200  # 100ms of 16-bit mono @ 16kHz (16000 * 2 * 0.1)
RECORDINGS_DIR = "/home/pi/recordings"
USB_CARD = None  # Auto-detected

# --- Global state ---
clients = set()
is_streaming = False
current_recording = None
ffmpeg_process = None


def detect_usb_card():
    """Auto-detect USB sound card number."""
    try:
        result = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "USB" in line.upper():
                card_num = line.split("card ")[1].split(":")[0]
                return int(card_num)
    except Exception:
        pass
    return 2  # Default fallback


async def audio_producer():
    """Capture audio from USB sound card and broadcast to all WebSocket clients."""
    global is_streaming, ffmpeg_process, current_recording

    USB_CARD = detect_usb_card()
    print(f"[OK] USB sound card: card {USB_CARD}")

    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    current_recording = f"tour_{timestamp}.wav"
    rec_path = os.path.join(RECORDINGS_DIR, current_recording)

    # FFmpeg: capture from USB mic, output raw PCM to stdout
    cmd = [
        "ffmpeg", "-nostdin",
        "-f", "alsa", "-channels", str(CHANNELS),
        "-sample_rate", str(SAMPLE_RATE),
        "-i", f"plughw:{USB_CARD},0",
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "pipe:1",
    ]

    print(f"[OK] Starting audio capture...")
    print(f"[OK] Recording to: {rec_path}")

    ffmpeg_process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    is_streaming = True
    print(f"[OK] WebSocket streaming on port {WS_PORT}")

    try:
        while True:
            data = await ffmpeg_process.stdout.read(CHUNK_SIZE)
            if not data:
                break

            # Broadcast to all connected clients
            if clients:
                dead = set()
                for ws in clients:
                    try:
                        await ws.send(data)
                    except websockets.exceptions.ConnectionClosed:
                        dead.add(ws)
                clients -= dead
    except asyncio.CancelledError:
        pass
    finally:
        is_streaming = False
        if ffmpeg_process:
            ffmpeg_process.terminate()
            await ffmpeg_process.wait()


async def handle_client(websocket):
    """Handle a new WebSocket client connection."""
    clients.add(websocket)
    remote = websocket.remote_address
    print(f"[+] Client connected: {remote} (total: {len(clients)})")

    # Send audio config as first message
    config = json.dumps({
        "type": "config",
        "sampleRate": SAMPLE_RATE,
        "channels": CHANNELS,
        "bitsPerSample": 16,
    })
    await websocket.send(config)

    try:
        # Keep connection alive, handle any client messages
        async for message in websocket:
            # Client can send control messages (future use)
            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        print(f"[-] Client disconnected: {remote} (total: {len(clients)})")


async def status_handler(websocket):
    """Handle status/API WebSocket requests on /status path."""
    try:
        async for message in websocket:
            try:
                req = json.loads(message)
                action = req.get("action", "")

                if action == "status":
                    resp = {
                        "streaming": is_streaming,
                        "listeners": len(clients),
                        "current_recording": current_recording,
                    }
                    await websocket.send(json.dumps(resp))

                elif action == "disk":
                    stat = os.statvfs(RECORDINGS_DIR)
                    free_gb = round((stat.f_frsize * stat.f_bavail) / (1024**3), 2)
                    total_gb = round((stat.f_frsize * stat.f_blocks) / (1024**3), 2)
                    await websocket.send(json.dumps({
                        "free_gb": free_gb, "total_gb": total_gb
                    }))

                elif action == "recordings":
                    recordings = []
                    for f in sorted(glob.glob(f"{RECORDINGS_DIR}/tour_*.*"), reverse=True):
                        stat_info = os.stat(f)
                        recordings.append({
                            "filename": os.path.basename(f),
                            "size_mb": round(stat_info.st_size / (1024 * 1024), 2),
                            "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                            "download_url": f"/recordings/{os.path.basename(f)}",
                        })
                    await websocket.send(json.dumps({
                        "recordings": recordings, "count": len(recordings)
                    }))

                elif action == "delete":
                    filename = req.get("file", "")
                    if filename and ".." not in filename and "/" not in filename:
                        filepath = os.path.join(RECORDINGS_DIR, filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            await websocket.send(json.dumps({"deleted": filename}))
                        else:
                            await websocket.send(json.dumps({"error": "Not found"}))
                    else:
                        await websocket.send(json.dumps({"error": "Invalid filename"}))

                elif action == "cleanup":
                    days = req.get("days", 30)
                    cutoff = datetime.now() - timedelta(days=days)
                    deleted = []
                    for f in glob.glob(f"{RECORDINGS_DIR}/tour_*.*"):
                        if datetime.fromtimestamp(os.stat(f).st_ctime) < cutoff:
                            os.remove(f)
                            deleted.append(os.path.basename(f))
                    await websocket.send(json.dumps({
                        "deleted": deleted, "count": len(deleted)
                    }))

            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass


async def handler(websocket):
    """Route WebSocket connections based on path."""
    path = websocket.request.path if hasattr(websocket, 'request') else '/'

    if path == "/status":
        await status_handler(websocket)
    else:
        await handle_client(websocket)


async def main():
    print("============================================")
    print("  Tour Guide WebSocket Audio Server")
    print(f"  ws://0.0.0.0:{WS_PORT}/        (audio stream)")
    print(f"  ws://0.0.0.0:{WS_PORT}/status  (admin API)")
    print("============================================")

    # Start WebSocket server (websockets v16 API)
    server = await websockets.serve(handler, HOST, WS_PORT)

    # Start audio capture in background
    audio_task = asyncio.create_task(audio_producer())

    # Run forever until killed
    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        audio_task.cancel()
        server.close()
        await server.wait_closed()
        print("\n[OK] Server stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
