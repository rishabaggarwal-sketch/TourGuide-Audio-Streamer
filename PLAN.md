# Tour Guide Audio Streaming System

## Project Plan & Configuration Guide

**Problem:** Limited Sennheiser tour guide receivers — some visitors are left without audio.

**Solution:** A portable streaming bridge that captures the speaker's RF audio and broadcasts it over local WiFi, so visitors can listen on their own phones (via QR code + browser) using any headset.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Hardware Shopping List](#2-hardware-shopping-list)
3. [Physical Configuration](#3-physical-configuration)
4. [Software Setup (Raspberry Pi)](#4-software-setup-raspberry-pi)
5. [Visitor Experience (QR Code + Browser)](#5-visitor-experience)
6. [Recording System](#6-recording-system)
7. [Admin Panel (Guide's View)](#7-admin-panel)
8. [Deployment Checklist](#8-deployment-checklist)
9. [Troubleshooting](#9-troubleshooting)
10. [Reference Links](#10-reference-links)

---

## 1. System Overview

### The Problem

```
  Speaker with Sennheiser Transmitter
        |
        |  RF Signal (863-928 MHz)
        v
  +-----------+   +-----------+   +-----------+   +===============+
  | Receiver 1|   | Receiver 2|   | Receiver 3|   || Visitor 4   ||
  | [Visitor] |   | [Visitor] |   | [Visitor] |   || NO RECEIVER!||
  | Can hear  |   | Can hear  |   | Can hear  |   || Can't hear  ||
  +-----------+   +-----------+   +-----------+   +===============+
```

### The Solution

```
  Speaker with Sennheiser Transmitter
        |
        |  RF Signal
        v
  +-----------------------------------------------------+
  |              STREAMING BRIDGE BOX                     |
  |              (fits in a small pouch)                  |
  |                                                       |
  |  +----------+    +-----------+    +--------------+   |
  |  |Sennheiser|--->|USB Sound  |--->|Raspberry Pi  |   |
  |  |Receiver  |3.5 |Card       |USB |(HLS +        |   |
  |  |(1 unit)  |mm  |(audio in) |    | FFmpeg +     |   |
  |  +----------+    +-----------+    | WiFi Hotspot |   |
  |                                    | + Recording) |   |
  |                                    +------+-------+   |
  |                                           | WiFi      |
  +-------------------------------------------+-----------+
                                              | Signal
                    +-------------------------+-------------------------+
                    |                         |                         |
              +-----+-----+           +------+----+           +--------+--+
              |  Phone 1  |           |  Phone 2  |           |  Phone N  |
              |  + Headset|           |  + Headset|           |  + Headset|
              |  (Browser)|           |  (Browser)|           |  (Browser)|
              |  Scan QR  |           |  Scan QR  |           |  Scan QR  |
              +-----------+           +-----------+           +-----------+
```

**Key Simplifications:**
- The Raspberry Pi IS the WiFi router — no separate router needed
- Uses HLS streaming (not Icecast) for reliable background/lock-screen playback on all phones
- Headset/earphones REQUIRED — phone speaker causes acoustic feedback to wireless mic

### How It Works (5 Steps)

```
Step 1: Sennheiser receiver picks up speaker's voice (like any other receiver)
            |
Step 2: Audio cable carries sound to USB sound card plugged into Pi
            |
Step 3: Raspberry Pi captures audio, streams via HLS, and optionally records to file
            |
Step 4: Pi's built-in WiFi creates "TourGuide" hotspot (no internet needed)
            |
Step 5: Visitors scan QR code -> browser opens -> tap Play -> listen!
```

---

## 2. Hardware Shopping List

### Only 4 Items Needed (+ 1 Sennheiser receiver from your stock)

```
+-----+----------------------------+----------+---------------------+
|  #  |  Item                      | Est Cost | Where to Buy        |
+-----+----------------------------+----------+---------------------+
|  1  | Raspberry Pi 3 Model B+   | Rs 3,500 | Amazon/Robu.in      |
|     | + MicroSD Card (128GB)    | Rs   800 |                     |
+-----+----------------------------+----------+---------------------+
|  2  | USB Sound Card             | Rs   350 | Amazon              |
|     | (with mic-in / line-in)    |          | Search: "USB sound  |
|     |                            |          |  card mic input"    |
+-----+----------------------------+----------+---------------------+
|  3  | 3.5mm Male-to-Male         | Rs   100 | Amazon/local        |
|     | Aux Cable                  |          |                     |
+-----+----------------------------+----------+---------------------+
|  4  | Power Bank (10000mAh+)    | Rs   800 | Amazon              |
|     | Must support 5V/3A output  |          | (for Pi 4)          |
+-----+----------------------------+----------+---------------------+
|     | Micro-USB cable for Pi     | Rs   100 | (you likely have one)|
|     | Small carrying pouch       | Rs   200 | Amazon/local        |
+-----+----------------------------+----------+---------------------+
|     | TOTAL                      |~Rs 5,550 |                     |
+-----+----------------------------+----------+---------------------+

  + 1 Sennheiser receiver (from your existing stock)

  NOTE: No separate WiFi router needed! Pi creates its own hotspot.
```

### Component Details

#### A. Raspberry Pi 3 B+ Model B

```
  +-------------------------------------------+
  |  RASPBERRY PI 4 MODEL B                   |
  |                                           |
  |  +-----+  +--++--+  +--------------+     |
  |  |HDMI |  |US||US|  |  Ethernet    |     |
  |  |(x2) |  |B ||B |  |  (unused)    |     |
  |  +-----+  +--++--+  +--------------+     |
  |                                           |
  |   +-------------------------------------+ |
  |   |         CPU + RAM                   | |
  |   |   Broadcom BCM2711, 2GB+            | |
  |   |   Built-in WiFi (for hotspot)       | |
  |   +-------------------------------------+ |
  |                                           |
  |  +--++--+  +----+  +------+  o PWR       |
  |  |US||US|  |WiFi|  |3.5mm |  (Micro-USB)     |
  |  |B ||B |  |BT  |  |Audio |  5V/3A       |
  |  +--++--+  +----+  |(OUT) |              |
  |                     +------+              |
  +-------------------------------------------+

  Why Pi 4 specifically:
  - Built-in WiFi can act as hotspot (hostapd)
  - 4x USB ports for sound card
  - Runs headless (no monitor needed)
  - Micro-USB power from any power bank
  - MicroSD for OS + recordings storage

  NOTE: Pi has audio OUT but NO audio IN.
  That's why we need the USB sound card.
```

#### B. USB Sound Card

```
  +-----------------------------+
  |    USB SOUND CARD           |
  |                             |
  |  +-------+                  |
  |  |  USB  |<-- Plugs into   |
  |  |Connect|    Raspberry Pi  |
  |  +-------+                  |
  |                             |
  |  +-------+  +-------+      |
  |  |  MIC  |  | AUDIO |      |
  |  |  IN   |  |  OUT  |      |
  |  | (Pink)|  |(Green)|      |
  |  +---+---+  +-------+      |
  |      |                      |
  +------+----------------------+
         |
         | 3.5mm cable from
         | Sennheiser receiver
         v

  WHY NEEDED:
  - Pi has audio OUT but NO audio IN
  - USB sound card adds a microphone/line-in port
  - Plug-and-play on Linux (no drivers needed)
  - Look for one with a PINK (mic-in) jack
  - Cost: ~Rs 350 on Amazon India
```

#### C. Audio Cable Connection

```
  +---------------+         3.5mm Aux Cable          +--------------+
  |  Sennheiser   |  +-----------------------------+ |  USB Sound   |
  |  Receiver     |  |                             | |  Card        |
  |               |  |   +-+             +-+       | |              |
  |  HEADPHONE ---+--+   |o|-------------|o|   +---+--> MIC IN     |
  |  OUT (3.5mm)  |  |   +-+             +-+       | |  (Pink jack) |
  |               |  |  Male              Male      | |              |
  +---------------+  +-----------------------------+ +--------------+

  IMPORTANT:
  - Use the HEADPHONE OUT on the Sennheiser receiver
  - Plug into the MIC IN (pink) port on USB sound card
  - Standard 3.5mm male-to-male aux cable
  - Keep receiver volume at ~60-70% to avoid distortion
```

---

## 3. Physical Configuration

### Complete Assembly Diagram

```
                         THE STREAMING BRIDGE
  +--------------------------------------------------------------+
  |                                                              |
  |   +---------------+    3.5mm     +--------------+            |
  |   |  Sennheiser   |----cable--->|  USB Sound   |            |
  |   |  Receiver     |  (aux out   |  Card        |            |
  |   |               |   to mic in)|              |            |
  |   |  [Tuned to    |             +------+-------+            |
  |   |   speaker's   |                    | USB                |
  |   |   channel]    |                    |                    |
  |   +---------------+             +------+-------+            |
  |                                 |              |            |
  |   +---------------+    Micro-USB    | Raspberry    |            |
  |   |  Power Bank   |----cable-->| Pi 4         |            |
  |   |  10000 mAh    |  (power)   |              |            |
  |   |               |            | Running:     |            |
  |   |  [Powers Pi   |            | - WiFi Hotspot            |
  |   |   for 4-6hr]  |            | - HLS Stream |            |
  |   +---------------+            | - FFmpeg x2  |            |
  |                                 | - Admin API  |            |
  |                                 | - Web Server |            |
  |                                 +--------------+            |
  |                                        |                    |
  |                              WiFi Hotspot Signal            |
  |                              SSID: "TourGuide"             |
  |                              Pass: "listen123"             |
  +--------------------------------------------------------------+
                                       |
                    +------------------+------------------+
                    |                  |                  |
              +-----+-----+    +------+----+    +--------+--+
              |  Phone 1  |    |  Phone 2  |    |  Phone N  |
              |  Scan QR  |    |  Scan QR  |    |  Scan QR  |
              |  Tap Play |    |  Tap Play |    |  Tap Play |
              +-----------+    +-----------+    +-----------+
```

### Step-by-Step Assembly

```
  STEP 1: Prepare the Sennheiser Receiver
  ========================================

  +----------------------+
  |   Sennheiser EK      |
  |   2020-D / EK 1039   |
  |                       |
  |   Channel: [  3  ]   |<-- Set to speaker's transmitter channel
  |   Volume:  [====  ]  |<-- Set to 60-70% (avoid distortion)
  |                       |
  |   +--------------+   |
  |   |  3.5mm Jack  |---+--> Connect aux cable here
  |   |  (Headphone) |   |
  |   +--------------+   |
  +----------------------+


  STEP 2: Connect Audio Path
  ===========================

  Sennheiser                     USB Sound Card
  Receiver                       (plugged into Pi)
  +--------+                     +--------+
  |  HEAD  |     +---------+     |  MIC   |
  |  PHONE +---->| 3.5mm   +---->|  IN    |
  |  OUT   |     | Aux     |     | (PINK) |
  +--------+     | Cable   |     +--------+
                 +---------+


  STEP 3: Power Up
  =================

  Power Bank                    Raspberry Pi
  +--------+     Micro-USB cable    +--------+
  |        +--------------------->| PWR    |
  | 10000  |                    |        |
  |  mAh   |                    | Boots  |
  |        |                    | ~45sec |
  +--------+                    +--------+

  Pi auto-creates WiFi hotspot + starts streaming on boot.


  STEP 4: Verify
  ===============

  On your phone:
  1. Connect to WiFi "TourGuide" (pass: listen123)
  2. Open browser: http://192.168.4.1/
  3. Tap Play -> you should hear the speaker
```

### Carrying Configuration

```
  +-----------------------------------------+
  |          CARRYING POUCH LAYOUT          |
  |         (small messenger bag or         |
  |          belt pouch / fanny pack)       |
  |                                         |
  |  +-------------+  +-------------+      |
  |  | Raspberry   |  | Power Bank  |      |
  |  | Pi 4        |  | 10000mAh    |      |
  |  | + USB Sound |  |             |      |
  |  |   Card      |  |             |      |
  |  +-------------+  +-------------+      |
  |                                         |
  |  +-------------+                        |
  |  | Sennheiser  |   Aux cable connects   |
  |  | Receiver    |   receiver to Pi       |
  |  +-------------+                        |
  |                                         |
  |  Total Size: ~15cm x 12cm x 5cm        |
  |  Total Weight: ~400 grams              |
  |  Battery Life: 4-6 hours               |
  +-----------------------------------------+

  Can be carried by guide or placed on a table.
  WiFi range: ~30-50 meters indoors.
```

---

## 4. Software Setup (Raspberry Pi)

### One-Command Install

Everything is automated. After flashing Raspberry Pi OS Lite to the SD card:

```bash
# 1. Flash Raspberry Pi OS Lite to MicroSD
#    Use Raspberry Pi Imager: https://www.raspberrypi.com/software/
#    During flashing, enable SSH + set password

# 2. First boot: connect Pi to your home WiFi or via ethernet
#    SSH in:
ssh pi@raspberrypi.local

# 3. Copy and run the install script:
sudo bash install.sh

# 4. Reboot:
sudo reboot

# Done! Pi now boots as a WiFi hotspot with auto-streaming.
```

### Actual Software Architecture (Deployed)

The original plan called for Icecast, but HLS was chosen instead for reliable background/lock-screen playback on all phones.

```
  ws_stream_server.py — single Python process running on Pi:
  +----------------------------------------------------------+
  |                                                          |
  |  FFmpeg #1: ALSA capture -> raw PCM stdout               |
  |    (captures audio from USB sound card)                  |
  |           |                                              |
  |  FFmpeg #2: PCM stdin -> HLS segments                    |
  |    (encodes AAC, writes .ts segments + .m3u8 playlist)   |
  |           |                                              |
  |  aiohttp HTTP server (port 8766):                        |
  |    - /hls/{filename} — serves HLS segments + playlist    |
  |    - /api/upload-map — tour map upload                   |
  |    - /api/delete-map — tour map delete                   |
  |           |                                              |
  |  websockets server (port 8765):                          |
  |    - /        — raw PCM broadcast to WebSocket clients   |
  |    - /status  — admin API (status, recording, disk, etc) |
  |           |                                              |
  |  Recording: manual start/stop from admin page            |
  |    - WAV format with proper header patching              |
  |    - Saved to /home/pi/recordings/                       |
  +----------------------------------------------------------+
```

### Services Running on Pi

```
  +---------------------+--------+--------------------------------------------+
  | Service             | Port   | Purpose                                    |
  +---------------------+--------+--------------------------------------------+
  | hostapd             | -      | WiFi hotspot "TourGuide"                   |
  | dnsmasq             | 53     | DHCP + DNS for connected phones            |
  | tourguide-ws        | 8765   | WebSocket server (audio + admin API)       |
  |                     | 8766   | HTTP server (HLS segments + map API)       |
  | nginx               | 80     | Reverse proxy + web files                  |
  +---------------------+--------+--------------------------------------------+

  systemd service: tourguide-ws (auto-starts on boot, auto-restarts on failure)
  Server binary: /usr/local/bin/tourguide-ws-server.py
```

### Network Architecture

```
  +--------------------------------------------------+
  |           RASPBERRY PI                            |
  |  WiFi Hotspot: 192.168.4.1 (TourGuide/listen123) |
  |  Ethernet:     192.168.1.96 (for SSH from laptop) |
  |                                                   |
  |  +--------+  +------------------+  +--------+    |
  |  |hostapd |  | tourguide-ws     |  | nginx  |    |
  |  |WiFi AP |  | :8765 (WS)      |  |  :80   |    |
  |  |        |  | :8766 (HTTP/HLS) |  |        |    |
  |  +--------+  +--------+---------+  +---+----+    |
  |                        |               |          |
  +--------------------------------------------------+
                           |               |
                   +-------+---------------+
                   |
           Visitor's Phone (192.168.4.x)
           +-------------------------------+
           | Browser: http://192.168.4.1/  |
           |                               |
           |  nginx routes:                |
           |  /         -> static web files|
           |  /ws       -> WS audio :8765  |
           |  /ws/status-> WS admin :8765  |
           |  /hls/     -> HLS segs :8766  |
           |  /api/     -> HTTP API :8766  |
           |  /recordings/ -> file listing |
           +-------------------------------+

  EVERYTHING IS LOCAL. NO INTERNET NEEDED.
```

### ALSA Audio Settings (Persisted)

```
  USB Sound Card (card 2):
  - Mic Capture: 7% (-9dB) — optimal for Sennheiser line-out
  - Speaker: 0% (muted) — prevents acoustic feedback
  - Saved with: alsactl store 2
  - Persists across reboots via /var/lib/alsa/asound.state
```

---

## 5. Visitor Experience

### Flow: QR Code to Listening

```
  VISITOR FLOW (3 STEPS):
  ========================

  Step 1                    Step 2                    Step 3
  +------------------+     +------------------+     +------------------+
  |                  |     |                  |     |                  |
  |  Scan QR Code    |---->|  Connect to WiFi |---->|  Tap Play        |
  |  (at entrance    |     |  "TourGuide"     |     |  in browser      |
  |   or on card)    |     |  Pass: listen123 |     |                  |
  |                  |     |                  |     |  Audio plays     |
  |  +----------+   |     |  Phone may auto  |     |  through their   |
  |  | QR CODE  |   |     |  open the page   |     |  headphones!     |
  |  | (points  |   |     |  (captive portal)|     |                  |
  |  |  to Pi)  |   |     |                  |     |                  |
  |  +----------+   |     |                  |     |                  |
  +------------------+     +------------------+     +------------------+

  Total time: ~30 seconds
  No app install needed!
```

### What Visitors See in Browser

```
  +-----------------------------------+
  |  Tour Audio Guide                 |
  |  Developed by PC-K Department     |
  |  Connect headphones and tap play  |
  |                                   |
  |  +----+ Stream: * Live            |
  |  +----+ WiFi: * Connected         |
  |                                   |
  |         +----------+              |
  |         |          |              |
  |         |  > PLAY  |  <-- Big green button
  |         |          |              |
  |         +----------+              |
  |                                   |
  |      Tap to listen                |
  |      [Ready / Listening...]       |
  |                                   |
  |      12 listening                 |
  |                                   |
  |  Volume: =========o 80%          |
  |                                   |
  |  +------+ +------+ +------+      |
  |  | Info | | Map  | | Help |      |
  |  +------+ +------+ +------+      |
  |                                   |
  |  +-----------------------------+  |
  |  | Welcome to the Guided Tour  |  |
  |  | You are listening to a live |  |
  |  | audio feed from your guide. |  |
  |  +-----------------------------+  |
  |                                   |
  |  +-----------------------------+  |
  |  | Tips:                       |  |
  |  | - Use headphones            |  |
  |  | - Screen off saves battery  |  |
  |  | - Stay within 50m range     |  |
  |  +-----------------------------+  |
  +-----------------------------------+

  Features:
  - Play/Pause with one tap
  - Volume slider
  - Live listener count
  - Auto-reconnect on WiFi drop
  - Info tab (tour details)
  - Map tab (floor map image)
  - Help tab (connection troubleshooting)
```

### Captive Portal (Auto-Redirect)

When visitors connect to the "TourGuide" WiFi, most phones will **automatically** pop up the landing page (like airport WiFi login pages). This is because:

- dnsmasq redirects ALL DNS queries to the Pi's IP
- Phone detects "no internet" and opens captive portal
- Landing page loads automatically — no URL typing needed!

### QR Code Card (Print and Laminate)

```
  +-----------------------------------+
  |                                   |
  |   AUDIO GUIDE                     |
  |   ---------------                 |
  |                                   |
  |   1. Connect to WiFi:             |
  |      Name: TourGuide              |
  |      Password: listen123          |
  |                                   |
  |   2. Scan this QR code:           |
  |      +-------------+              |
  |      | [QR CODE]   |              |
  |      | generated   |              |
  |      | by setup    |              |
  |      | script      |              |
  |      +-------------+              |
  |                                   |
  |   3. Plug in your headphones      |
  |      and tap Play!                |
  |                                   |
  |   Enjoy the tour!                 |
  |                                   |
  +-----------------------------------+

  QR code image is auto-generated at:
  /home/pi/tourguide-web/qr.png

  Print this, laminate it, hand out or post at entrance.
```

---

## 6. Recording System

### How Recording Works

Recording is **manual** — the guide starts/stops recording from the admin page. This avoids filling the SD card with silence during idle time.

```
                              +------------------+
                              |  FFmpeg captures  |
                              |  audio and sends  |
  Sennheiser --> USB Sound -->|  to TWO places    |
  Receiver       Card         |  simultaneously:  |
                              |                   |
                              |  1. HLS encoder --+--> Visitors' phones (live)
                              |     (always on)   |
                              |                   |
                              |  2. WAV file -----+--> /home/pi/recordings/
                              |     (manual       |    (saved on SD card)
                              |      start/stop)  |
                              +------------------+

  Streaming is always on. Recording is only when guide presses
  "Start Recording" on the admin page.
```

### Recording Storage

```
  /home/pi/recordings/
  +-- tour_2026-04-03_10-15-30.wav   (Morning tour, 45 min, ~82 MB)
  +-- tour_2026-04-03_14-30-00.wav   (Afternoon tour, 60 min, ~110 MB)
  +-- ...

  Storage math:
  - PCM 16-bit mono @ 16kHz = ~1.9 MB per minute
  - 1 hour tour  = ~110 MB
  - 128 GB SD card = ~900+ hours of recordings
  - Auto-cleanup available: delete older than N days from admin page
```

### Naming & Format

Guide presses "Start Recording" → file created with timestamp. Presses "Stop Recording" → WAV header finalized.

```
  tour_YYYY-MM-DD_HH-MM-SS.wav

  Examples:
  tour_2026-04-03_10-15-30.wav   (started at 10:15:30 AM)
  tour_2026-04-03_14-30-00.wav   (started at 2:30 PM)
```

### Retrieving Recordings

Three ways to get your recordings:

```
  Option 1: Admin page (easiest)
  ==============================
  Open http://192.168.4.1/admin.html on guide's phone
  -> Tap "Download" next to any recording


  Option 2: Remove SD card
  ========================
  Power off Pi -> remove MicroSD -> plug into laptop
  -> Browse to /home/pi/recordings/


  Option 3: SSH/SFTP (technical)
  ==============================
  From any computer on TourGuide WiFi:
  scp pi@192.168.4.1:/home/pi/recordings/*.ogg ./
```

---

## 7. Admin Panel

### Guide's Admin Page

The guide accesses `http://192.168.4.1/admin.html` on their phone (while on TourGuide WiFi):

```
  +-----------------------------------+
  |  Tour Guide - Admin               |
  |  Developed by Admin: Rishab       |
  |  Aggarwal (DPM PC-K)             |
  |                                   |
  |  LIVE STATUS                      |
  |  +------------+ +------------+    |
  |  |    12      | |   14.2     |    |
  |  | Listeners  | |  GB Free   |    |
  |  +------------+ +------------+    |
  |                                   |
  |  Stream: * LIVE                   |
  |                                   |
  |  RECORDING CONTROL                |
  |  +-----------------------------+  |
  |  |  [ Start Recording ]        |  |  <-- Manual start/stop
  |  |  (red pulsing when active)  |  |
  |  +-----------------------------+  |
  |                                   |
  |  TOUR MAP                         |
  |  +-----------------------------+  |
  |  |  [Upload Map Image]         |  |  <-- Upload/delete map.jpg
  |  |  [Delete Map]               |  |
  |  +-----------------------------+  |
  |                                   |
  |  VISITOR QR CODE                  |
  |  +-----------------------------+  |
  |  |        [QR IMAGE]           |  |
  |  |   http://192.168.4.1/       |  |
  |  |   Show to visitors          |  |
  |  +-----------------------------+  |
  |                                   |
  |  PAST RECORDINGS                  |
  |  +-----------------------------+  |
  |  | tour_2026-04-03_10-15.wav   |  |
  |  | 3 Apr, 10:15 | 82 MB       |  |
  |  | [Download]  [Delete]        |  |
  |  +-----------------------------+  |
  |                                   |
  |  [Delete recordings > 30 days]    |
  +-----------------------------------+
```

### Admin API (WebSocket + HTTP)

```
  WebSocket API (ws://192.168.4.1/ws/status):
  ============================================
  { "action": "status"    } -> { streaming, recording, listeners, current_recording }
  { "action": "start_rec" } -> { recording: true, filename: "tour_..." }
  { "action": "stop_rec"  } -> { recording: false, saved: "tour_..." }
  { "action": "disk"      } -> { free_gb, total_gb }
  { "action": "recordings"} -> { recordings: [...], count: N }
  { "action": "delete", "file": "tour_..." } -> { deleted: "..." }
  { "action": "cleanup", "days": 30 }        -> { deleted: [...], count: N }

  HTTP API (http://192.168.4.1/api/):
  ====================================
  POST /api/upload-map   (multipart form, field "map") -> { ok: true, size_kb }
  POST /api/delete-map                                 -> { ok: true }
```

---

## 8. Deployment Checklist

### Before Each Tour

```
  PRE-TOUR CHECKLIST
  ===================

  [ ]  Charge power bank (full charge night before)
  [ ]  Charge Sennheiser receiver battery
  [ ]  Print QR code cards (laminate for reuse)
  [ ]  Ensure visitors have earphones/headsets (REQUIRED — no speaker use!)
  [ ]  Optional: Upload tour map via admin page

  SETUP TIME: ~2 MINUTES
  =======================

  1. Plug Micro-USB cable from power bank to Pi      [5 sec]
  2. Turn on Sennheiser receiver                  [5 sec]
  3. Connect aux cable (receiver -> USB sound card) [5 sec]
  4. Wait for Pi to boot + stream starts          [~45 sec]
  5. Test on your phone:                          [30 sec]
     - Connect to "TourGuide" WiFi
     - Open http://192.168.4.1/
     - Tap Play -> hear speaker
  6. Hand out QR code cards to visitors           [Ready!]

  TEARDOWN: Unplug power bank. Done.
```

### Customization

You can customize the experience by editing files on the Pi:

```
  /home/pi/tourguide-web/
  +-- index.html       <- Visitor page ("Developed by PC-K Department")
  +-- admin.html       <- Admin page ("Developed by Admin: Rishab Aggarwal (DPM PC-K)")
  +-- hls.min.js       <- Bundled hls.js library (for Android HLS support)
  +-- map.jpg          <- Tour map image (uploaded via admin page)
  +-- qr.png           <- QR code (if generated)

  To customize:
  - Edit web/index.html on laptop, deploy via SCP or Paramiko
  - Upload tour map via admin page (no SSH needed)
  - Credits can be changed in the HTML header sections
```

---

## 9. Troubleshooting

| Problem | Solution |
|---------|----------|
| No audio from stream | Check aux cable is in MIC IN (pink), not audio out (green) |
| Audio is distorted/clipping | Lower mic capture: `amixer -c 2 sset Mic capture 5%` then `alsactl store 2` |
| Echo/voice repeating | Phone speaker feeds back to wireless mic — **use earphones/headset** |
| Phone can't find "TourGuide" WiFi | Wait 45 sec after powering Pi; check power bank charge |
| Page doesn't load after WiFi connect | Try http://192.168.4.1/ in browser manually |
| Audio has ~3-4s delay | This is normal for HLS. Reduce with HLS_SEGMENT_TIME=1, HLS_LIST_SIZE=2 |
| Audio stops when app minimized | Make sure using HLS player (not WebSocket). iOS: native HLS. Android: hls.js |
| Pi won't boot | Check power bank supports 5V/2.5A output, try different Micro-USB cable |
| Stream cuts out | Power bank may be low; move closer to Pi (within 50m) |
| "USB sound card not detected" | Unplug and replug USB sound card; check with `arecord -l` |
| HLS segments not generating | Check `/tmp/tourguide-hls/` ownership: `sudo chown pi:pi /tmp/tourguide-hls` |
| Captive portal doesn't appear | Different phones handle this differently — share QR code as backup |
| Recordings not saving | Check SD card space: `df -h` on Pi |
| Map upload fails | Check nginx `client_max_body_size` is 10m; check `/home/pi/tourguide-web/` writable |

### Managing the Pi Remotely

SSH into the Pi (via WiFi hotspot or Ethernet):

```bash
# Via WiFi hotspot
ssh pi@192.168.4.1

# Via Ethernet (when Pi connected to router)
ssh pi@192.168.1.96

# Password: tourguide

# Check stream status
sudo systemctl status tourguide-ws

# Restart stream
sudo systemctl restart tourguide-ws

# Check recordings
ls -la /home/pi/recordings/

# Check disk space
df -h

# View stream logs
journalctl -u tourguide-ws -f

# Check/adjust mic gain
amixer -c 2 sget Mic      # View current
amixer -c 2 sset Mic capture 7%  # Adjust
alsactl store 2            # Persist across reboots
```

---

## 10. Reference Links

### Hardware Guides
- [USB Audio Cards with Raspberry Pi (Adafruit)](https://learn.adafruit.com/usb-audio-cards-with-a-raspberry-pi)
- [Using USB Audio Device with Raspberry Pi](https://www.raspberrypi-spy.co.uk/2019/06/using-a-usb-audio-device-with-the-raspberry-pi/)
- [Sennheiser EK 2020-D II Specs](https://www.sennheiser.com/en-us/catalog/products/visitor-guidance/ew-2020-d-ii/ek-2020-d-ii-us-504795)
- [Sennheiser Tour Guide System Overview](https://www.tourguidesystem.co.uk/tourguide/sennheiser-tourguide-system)

### Streaming Setup Guides
- [Icecast on Raspberry Pi (peppe8o)](https://peppe8o.com/icecast-raspberry-pi/)
- [Build Internet Radio with Pi + Icecast (Maker Pro)](https://maker.pro/raspberry-pi/projects/how-to-build-an-internet-radio-station-with-raspberry-pi-darkice-and-icecast)
- [Raspberry Pi Vinyl Streamer (GitHub — similar project)](https://github.com/quebulm/Raspberry-Pi-Vinyl-Streamer)
- [Stream Audio from Pi to Local Network (Hackster.io)](https://www.hackster.io/Shilleh/stream-audio-from-raspberry-pi-to-local-computer-02c7f0)

### WiFi Hotspot Setup
- [Raspberry Pi WiFi Hotspot Guide](https://www.raspberrypi.com/documentation/computers/configuration.html)

---

## Architecture Decisions

### Why QR + Browser (not a native app)?

| Factor | Native App | QR + Browser |
|--------|-----------|--------------|
| Visitor friction | Must download + install | Scan + tap — 30 seconds |
| Platform support | Need iOS + Android builds | Works on every phone |
| Updates | App store review cycle | Edit HTML on Pi, instant |
| Maintenance | SDK updates, store accounts | Zero maintenance |
| Offline | Must pre-install | Works (local WiFi, no internet) |

### Why Pi as Hotspot (not separate router)?

| Factor | Separate Router | Pi as Hotspot |
|--------|----------------|---------------|
| Devices to carry | 5 | 4 (one less!) |
| Cost | +Rs 1,200 | Free (built-in WiFi) |
| Setup complexity | Configure two devices | One device does everything |
| Failure points | Router battery, connection | Just the Pi |
| Range | ~50m | ~30-50m (sufficient) |
| Max clients | 10-32 | ~20 (sufficient for tours) |

### Why HLS + FFmpeg? (Changed from original Icecast plan)

| Considered | Verdict | Reason |
|------------|---------|--------|
| HLS + FFmpeg | **CHOSEN** | Works in background/lock screen on ALL phones (iOS native, Android via hls.js). ~3-4s latency acceptable for tours |
| Icecast + FFmpeg | Originally planned | Background playback unreliable on iOS/Android — browser stops audio when minimized |
| WebSocket + PCM | Tried first | Low latency (~100ms) but no background playback — Web Audio API suspended when tab hidden |
| MP3 HTTP streaming | Tried | Echo/repetition issues with per-client encoders, Safari double-request bugs |
| WebRTC | Rejected | Complex setup, overkill for one-way broadcast audio |
| Bluetooth Broadcast | Rejected | Needs newest phones, ~10m range only |
| Cloud Streaming | Rejected | Needs internet, per-minute cost, higher latency |

**Key lesson:** Background audio playback on mobile browsers requires `<audio>` element with a standard streaming protocol (HLS). Web Audio API and WebSocket-based approaches are killed by the OS when the browser is backgrounded.

---

## File Structure

```
TourGuide_Audio_Streamer/
+-- PLAN.md                          <- This document
+-- qr_tourguide.png                 <- QR code for visitor page
+-- qr_admin.png                     <- QR code for admin page
+-- qr_card.html                     <- Printable QR card
+-- setup/
|   +-- install.sh                   <- Pi setup script (hostapd, dnsmasq, deps)
|   +-- ws_stream_server.py          <- Main server (deployed to Pi)
|   +-- pi-config/
|       +-- nginx-tourguide.conf     <- Backup of Pi nginx config
|       +-- tourguide-ws.service     <- Backup of systemd service file
|       +-- asound.state             <- Backup of ALSA mixer state
+-- web/
    +-- index.html                   <- Visitor landing page
    +-- admin.html                   <- Guide admin page
```

### Key Pi Paths

```
/usr/local/bin/tourguide-ws-server.py   <- Server binary (copied from setup/)
/home/pi/tourguide-web/                  <- Web root (index.html, admin.html, map.jpg, hls.min.js)
/home/pi/recordings/                     <- Tour recordings (WAV files)
/tmp/tourguide-hls/                      <- HLS segments (ephemeral, auto-cleaned)
/etc/nginx/sites-enabled/tourguide       <- Nginx config
/etc/systemd/system/tourguide-ws.service <- systemd service
/var/lib/alsa/asound.state               <- ALSA mixer persistence
```

### Deploying Updates from Laptop

Uses Paramiko SSH/SFTP from Windows to Pi:

```bash
# Server code: upload to /home/pi/ then sudo cp to /usr/local/bin/
# Web files: upload directly to /home/pi/tourguide-web/
# Then: sudo systemctl restart tourguide-ws

# Or manually via SCP:
scp setup/ws_stream_server.py pi@192.168.1.96:/home/pi/
ssh pi@192.168.1.96 "sudo cp /home/pi/ws_stream_server.py /usr/local/bin/tourguide-ws-server.py && sudo systemctl restart tourguide-ws"
scp web/index.html web/admin.html pi@192.168.1.96:/home/pi/tourguide-web/
```

---

## Future Enhancements (v2)

1. **Multi-language** — Multiple receivers on different channels, each streaming to `/listen-en`, `/listen-hi`, `/listen-fr`
2. **Push-to-talk Q&A** — Visitors ask questions through the app (WebRTC)
3. **Tour scheduling** — Pre-set tour times, auto-start/stop recording
4. **Analytics** — Track peak listeners, average session duration
5. **Multiple venues** — Different SSID/config profiles per venue

---

*Document created: 2026-03-31*
*Last updated: 2026-04-07*
