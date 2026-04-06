#!/usr/bin/env python3
"""
Tour Guide Audio Streaming Server
Captures audio from USB sound card and streams via:
  - HLS (HTTP Live Streaming) for reliable background playback on all phones
  - WebSocket raw PCM for low-latency foreground (future use)
  - Admin API via WebSocket
"""

import asyncio
import subprocess
import struct
import signal
import sys
import json
import os
import glob
import tempfile
import shutil
from datetime import datetime, timedelta
from aiohttp import web

import websockets

# --- Configuration ---
HOST = "0.0.0.0"
WS_PORT = 8765
HTTP_PORT = 8766
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 3200  # 100ms of 16-bit mono @ 16kHz
RECORDINGS_DIR = "/home/pi/recordings"
HLS_DIR = "/tmp/tourguide-hls"
HLS_SEGMENT_TIME = 1  # seconds per segment (lower = less latency)
HLS_LIST_SIZE = 2     # keep last 2 segments in playlist
USB_CARD = None

# --- Global state ---
clients = set()
is_streaming = False
is_recording = False
current_recording = None
rec_file = None
pcm_bytes_written = 0
ffmpeg_capture = None
ffmpeg_hls = None


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
    return 2


def _finalize_wav(f, data_size):
    """Patch WAV header with actual data size."""
    try:
        f.seek(4)
        f.write(struct.pack('<I', data_size + 36))  # RIFF chunk size
        f.seek(40)
        f.write(struct.pack('<I', data_size))  # data chunk size
    except Exception:
        pass


def start_recording():
    """Start recording audio to a WAV file."""
    global is_recording, current_recording, rec_file, pcm_bytes_written

    if is_recording:
        return current_recording

    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    current_recording = f"tour_{timestamp}.wav"
    rec_path = os.path.join(RECORDINGS_DIR, current_recording)

    rec_file = open(rec_path, 'wb')
    byte_rate = SAMPLE_RATE * CHANNELS * 2
    block_align = CHANNELS * 2
    rec_file.write(struct.pack('<4sI4s', b'RIFF', 0, b'WAVE'))
    rec_file.write(struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, CHANNELS,
                               SAMPLE_RATE, byte_rate, block_align, 16))
    rec_file.write(struct.pack('<4sI', b'data', 0))
    pcm_bytes_written = 0
    is_recording = True

    print(f"[OK] Recording started: {current_recording}", flush=True)
    return current_recording


def stop_recording():
    """Stop recording and finalize the WAV file."""
    global is_recording, rec_file, pcm_bytes_written, current_recording

    if not is_recording or rec_file is None:
        return None

    _finalize_wav(rec_file, pcm_bytes_written)
    rec_file.close()
    rec_file = None
    is_recording = False

    saved = current_recording
    size_mb = pcm_bytes_written / (1024 * 1024)
    print(f"[OK] Recording saved: {saved} ({size_mb:.1f} MB)", flush=True)
    current_recording = None
    return saved


async def audio_producer():
    """Capture audio from USB and broadcast PCM to WebSocket + feed HLS encoder."""
    global is_streaming, ffmpeg_capture, ffmpeg_hls, pcm_bytes_written

    USB_CARD = detect_usb_card()
    print(f"[OK] USB sound card: card {USB_CARD}")

    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    os.makedirs(HLS_DIR, exist_ok=True)

    # FFmpeg #1: ALSA capture -> raw PCM stdout
    capture_cmd = [
        "ffmpeg", "-nostdin",
        "-f", "alsa", "-channels", str(CHANNELS),
        "-sample_rate", str(SAMPLE_RATE),
        "-i", f"plughw:{USB_CARD},0",
        "-f", "s16le", "-acodec", "pcm_s16le",
        "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "pipe:1",
    ]

    # FFmpeg #2: PCM stdin -> HLS segments
    hls_cmd = [
        "ffmpeg", "-nostdin", "-hide_banner",
        "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
        "-i", "pipe:0",
        "-codec:a", "aac", "-b:a", "64k", "-ac", str(CHANNELS),
        "-f", "hls",
        "-hls_time", str(HLS_SEGMENT_TIME),
        "-hls_list_size", str(HLS_LIST_SIZE),
        "-hls_flags", "delete_segments+append_list+omit_endlist",
        "-hls_segment_filename", os.path.join(HLS_DIR, "seg_%05d.ts"),
        os.path.join(HLS_DIR, "stream.m3u8"),
    ]

    print(f"[OK] Starting audio capture + HLS encoder...")

    while True:
        # Clean HLS dir on start
        for f in glob.glob(os.path.join(HLS_DIR, "*")):
            os.remove(f)

        ffmpeg_capture = await asyncio.create_subprocess_exec(
            *capture_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        ffmpeg_hls = await asyncio.create_subprocess_exec(
            *hls_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        is_streaming = True
        print(f"[OK] HLS streaming to {HLS_DIR}", flush=True)
        print(f"[OK] WebSocket on port {WS_PORT}", flush=True)

        chunks = 0
        try:
            while True:
                data = await ffmpeg_capture.stdout.read(CHUNK_SIZE)
                if not data:
                    break
                chunks += 1
                if chunks == 1:
                    print(f"[OK] First audio chunk: {len(data)} bytes", flush=True)

                # Broadcast raw PCM to WebSocket clients
                if clients:
                    websockets.broadcast(clients, data)

                # Feed PCM to HLS encoder
                try:
                    ffmpeg_hls.stdin.write(data)
                    await ffmpeg_hls.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break

                # Write to recording file if recording is active
                if is_recording and rec_file:
                    rec_file.write(data)
                    pcm_bytes_written += len(data)

        except asyncio.CancelledError:
            is_streaming = False
            stop_recording()
            for proc in [ffmpeg_capture, ffmpeg_hls]:
                if proc:
                    proc.terminate()
                    await proc.wait()
            return
        finally:
            is_streaming = False

        # Restart on failure
        for proc in [ffmpeg_capture, ffmpeg_hls]:
            if proc and proc.returncode is None:
                proc.terminate()
                await proc.wait()

        print(f"[WARN] FFmpeg exited, restarting in 3s...", flush=True)
        await asyncio.sleep(3)


# --- HLS File Server ---
async def handle_hls(request):
    """Serve HLS playlist and segments."""
    filename = request.match_info.get('filename', 'stream.m3u8')

    # Only allow .m3u8 and .ts files
    if not (filename.endswith('.m3u8') or filename.endswith('.ts')):
        return web.Response(status=404)

    filepath = os.path.join(HLS_DIR, filename)
    if not os.path.exists(filepath):
        return web.Response(status=404)

    if filename.endswith('.m3u8'):
        content_type = 'application/vnd.apple.mpegurl'
    else:
        content_type = 'video/MP2T'

    return web.FileResponse(
        filepath,
        headers={
            'Content-Type': content_type,
            'Cache-Control': 'no-cache, no-store',
            'Access-Control-Allow-Origin': '*',
        }
    )


async def handle_client(websocket):
    """Handle a new WebSocket client connection."""
    clients.add(websocket)
    remote = websocket.remote_address
    print(f"[+] Client connected: {remote} (total: {len(clients)})")

    config = json.dumps({
        "type": "config",
        "sampleRate": SAMPLE_RATE,
        "channels": CHANNELS,
        "bitsPerSample": 16,
    })
    await websocket.send(config)

    try:
        async for message in websocket:
            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        print(f"[-] Client disconnected: {remote} (total: {len(clients)})")


async def status_handler(websocket):
    """Handle status/API WebSocket requests."""
    try:
        async for message in websocket:
            try:
                req = json.loads(message)
                action = req.get("action", "")

                if action == "status":
                    resp = {
                        "streaming": is_streaming,
                        "recording": is_recording,
                        "listeners": len(clients),
                        "current_recording": current_recording,
                    }
                    await websocket.send(json.dumps(resp))

                elif action == "start_rec":
                    filename = start_recording()
                    await websocket.send(json.dumps({
                        "recording": True, "filename": filename
                    }))

                elif action == "stop_rec":
                    saved = stop_recording()
                    await websocket.send(json.dumps({
                        "recording": False, "saved": saved
                    }))

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
    print("  Tour Guide Audio Server (HLS)")
    print(f"  ws://0.0.0.0:{WS_PORT}/        (WebSocket audio)")
    print(f"  ws://0.0.0.0:{WS_PORT}/status  (admin API)")
    print(f"  http://0.0.0.0:{HTTP_PORT}/hls/ (HLS stream)")
    print("============================================")

    ws_server = await websockets.serve(handler, HOST, WS_PORT)

    app = web.Application()
    app.router.add_get('/hls/{filename}', handle_hls)
    app.router.add_get('/hls/', lambda r: handle_hls_redirect(r))
    runner = web.AppRunner(app)
    await runner.setup()
    http_site = web.TCPSite(runner, HOST, HTTP_PORT)
    await http_site.start()

    audio_task = asyncio.create_task(audio_producer())

    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        audio_task.cancel()
        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()
        # Clean up HLS files
        shutil.rmtree(HLS_DIR, ignore_errors=True)
        print("\n[OK] Server stopped")


async def handle_hls_redirect(request):
    return web.HTTPFound('/hls/stream.m3u8')


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
