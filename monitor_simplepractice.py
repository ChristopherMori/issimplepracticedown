#!/usr/bin/env python3
"""
monitor_simplepractice.py

A continuous monitor that checks the latency of
"https://account.simplepractice.com/" every 5 minutes.
It writes the current status to `status.json`, appends each result to `history.json`,
and generates an HTML summary in `index.html`.
"""

import requests
import time
import json
import html
from datetime import datetime, timezone
import os

# =====================================
# === CONFIGURATION & DEFAULTS ===
# =====================================
SITE_URL = "https://account.simplepractice.com/"
TIMEOUT_LIMIT = 15                # seconds before timing out
SLOW_THRESHOLD = 2.0              # above this response time (in seconds) is considered slow
STATE_DB_FILE = "status.json"     # file for current state
HISTORY_FILE = "history.json"     # file for historical records
OUTPUT_HTML = "index.html"        # generated HTML file
CHECK_INTERVAL_MIN = 5            # check interval in minutes
MAX_TIMES_TRACKED = 100           # maximum number of history entries to keep

# =====================================
# === STATUS CATEGORIES & UI INFO ===
# =====================================
STATUS_META = {
    "UP": {"emoji": "✅", "headline": "All Good!"},
    "SLOW": {"emoji": "🐢", "headline": "A Bit Slow..."},
    "ERROR": {"emoji": "⚠️", "headline": "Uh Oh! Error!"},
    "DOWN": {"emoji": "💔", "headline": "It's Down!"},
    "UNKNOWN": {"emoji": "❓", "headline": "Unknown"}
}

# =====================================
# === HELPER FUNCTIONS ===
# =====================================

def load_state(filename: str) -> dict:
    """
    Loads the current state from a JSON file. If not available, returns default state.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("State file does not contain a dictionary")
            data.setdefault('current_status', 'UNKNOWN')
            data.setdefault('stable_streak', 0)
            data.setdefault('degraded_streak', 0)
            data.setdefault('alert_active', False)
            data.setdefault('last_check_utc', None)
            data.setdefault('last_response_time', 0)
            data.setdefault('extra_details', '')
            times = data.get('recent_times', [])
            if not isinstance(times, list):
                times = []
            data['recent_times'] = times[-MAX_TIMES_TRACKED:]
            return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"[ERROR] Failed to load state: {e}")
        return {
            'current_status': 'UNKNOWN',
            'stable_streak': 0,
            'degraded_streak': 0,
            'alert_active': False,
            'last_check_utc': None,
            'last_response_time': 0,
            'extra_details': '',
            'recent_times': []
        }

def save_state(filename: str, state: dict):
    """
    Saves the current state to a JSON file (overwriting previous data).
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        print(f"[ERROR] Could not save state to {filename}: {e}")

def save_history(entry: dict, filename: str = HISTORY_FILE):
    """
    Inserts a new entry at the beginning of the history file.
    """
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        else:
            history = []
        history.insert(0, entry)
        history = history[:MAX_TIMES_TRACKED]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    except OSError as e:
        print(f"[ERROR] Could not save history to {filename}: {e}")

def calc_average_speed(times_list: list) -> float:
    """
    Returns the average of valid response times from a list.
    """
    valid = []
    for t in times_list:
        try:
            val = float(t)
            if 0 < val < TIMEOUT_LIMIT:
                valid.append(val)
        except (ValueError, TypeError):
            pass
    return sum(valid) / len(valid) if valid else 0.0

def generate_status_html(filename: str, state: dict):
    """
    Generates an HTML page summarizing the site status.
    """
    current_status = state.get('current_status', 'UNKNOWN')
    meta = STATUS_META.get(current_status, STATUS_META["UNKNOWN"])

    rt = state.get('last_response_time', 0)
    last_rt_str = f"{rt:.2f} s" if isinstance(rt, (int, float)) and rt > 0 else "-- s"

    times = state.get('recent_times', [])
    avg_speed = calc_average_speed(times)
    avg_str = f"{avg_speed:.2f} s" if avg_speed > 0 else "-- s"

    valid_count = sum(1 for x in times if isinstance(x, (int, float)) and 0 < x < TIMEOUT_LIMIT)

    last_check_utc_str = state.get('last_check_utc') or ''
    last_check_display = "Never"
    if last_check_utc_str:
        try:
            dt_utc = datetime.fromisoformat(last_check_utc_str.replace('Z', '+00:00'))
            last_check_display = dt_utc.astimezone().strftime('%b %d, %Y, %I:%M:%S %p %Z')
        except ValueError:
            pass

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>SimplePractice Monitor</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://rsms.me/" />
  <link rel="stylesheet" href="https://rsms.me/inter/inter.css" />
  <style>
    body {{ font-family: 'Inter', sans-serif; }}
    @keyframes pulse-bg {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.7; }}
    }}
    .animate-pulse-bg {{ animation: pulse-bg 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }}
    .status-emoji {{ font-size: 1.5rem; line-height: 1; margin-right: 0.5rem; display: inline-block; vertical-align: middle; }}
  </style>
</head>
<body class="bg-gray-100 p-4 md:p-8">
  <div class="max-w-2xl mx-auto bg-white rounded-xl shadow-lg p-6 md:p-8">
    <header class="mb-6 text-center">
      <h1 class="text-3xl font-bold text-gray-800 mb-1">SimplePractice Monitor</h1>
      <p class="text-sm text-gray-500">
        Monitoring:
        <code class="bg-gray-100 px-1 rounded font-mono">{html.escape(SITE_URL)}</code>
      </p>
    </header>
    <div id="status-card" class="rounded-lg p-6 mb-6 transition-colors duration-500">
      <div class="flex items-center justify-between mb-4 flex-wrap">
        <h2 id="status-text" class="text-xl font-medium flex items-center mb-2 sm:mb-0">
          <span class="status-emoji">{meta['emoji']}</span>{meta['headline']}
        </h2>
        <span class="text-xs text-gray-500 w-full text-right sm:w-auto">
          Checked:
          <span id="last-checked-display">{html.escape(last_check_display)}</span>
          <span id="last-check-iso" style="display:none;">{html.escape(last_check_utc_str)}</span>
        </span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
          <span class="text-gray-600 block text-xs mb-1">Load Speed (Last)</span>
          <span id="response-time" class="font-semibold text-lg text-gray-800">{html.escape(last_rt_str)}</span>
        </div>
        <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
          <span class="text-gray-600 block text-xs mb-1">Avg. Speed (Last {valid_count})</span>
          <span id="avg-speed" class="font-semibold text-lg text-gray-800">{html.escape(avg_str)}</span>
        </div>
      </div>
    </div>
    <div class="text-center mb-6 text-sm text-gray-600">
      <p>Approx. next check in: <span id="countdown-timer" class="font-semibold">--:--</span></p>
      <p class="text-xs text-gray-500">(Checks occur every {CHECK_INTERVAL_MIN} minutes)</p>
    </div>
    <div class="max-w-2xl mx-auto bg-white rounded-xl shadow-lg p-6 md:p-8 mt-6">
      <h2 class="text-2xl font-bold text-gray-800 mb-4">History</h2>
      <ul id="history-list" class="list-disc pl-5"></ul>
    </div>
    <div class="text-center text-xs text-gray-400 mt-6">
      Status as of: {html.escape(last_check_display)}.
    </div>
  </div>
  <!-- Client-side scripts will update the status and history -->
  <script src="script.js"></script>
</body>
</html>
"""

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_out)
        print(f"[INFO] HTML file generated: {filename}")
    except OSError as e:
        print(f"[ERROR] Could not write HTML output: {e}")

def run_monitor():
    """
    Performs a single check:
      - Loads previous state,
      - Times a request to the site,
      - Determines if the site is UP, SLOW, ERROR, or DOWN,
      - Updates streak counters and alert flags,
      - Saves the new state and appends to history,
      - Generates the HTML page.
    """
    print(f"{'-'*28}\n[INFO] Starting check at UTC {datetime.now(timezone.utc).isoformat()}")
    state = load_state(STATE_DB_FILE)
    stable_streak = state.get('stable_streak', 0)
    degraded_streak = state.get('degraded_streak', 0)
    alert_active = state.get('alert_active', False)
    recent_times = state.get('recent_times', [])

    start_t = time.time()
    new_status = "UNKNOWN"
    response_duration = 0.0
    extra_info = ""

    try:
        resp = requests.get(SITE_URL, timeout=TIMEOUT_LIMIT)
        response_duration = time.time() - start_t
        if resp.status_code == 200:
            new_status = "SLOW" if response_duration > SLOW_THRESHOLD else "UP"
        else:
            new_status = "ERROR"
            extra_info = f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        new_status = "DOWN"
        extra_info = "Request timed out"
    except requests.exceptions.RequestException as e:
        new_status = "DOWN"
        extra_info = f"Network error: {type(e).__name__}"
    except Exception as e:
        new_status = "ERROR"
        extra_info = f"Unknown error: {type(e).__name__}"
        print(f"[ERROR] Unexpected exception: {e}")

    print(f"[INFO] Result -> Status={new_status}, RespTime={response_duration:.2f}s, Info='{extra_info}'")

    record_time = response_duration if new_status in ("UP", "SLOW") else 0
    recent_times.append(record_time)

    if new_status == "UP":
        stable_streak += 1
        degraded_streak = 0
    else:
        degraded_streak += 1
        stable_streak = 0

    if not alert_active and degraded_streak >= 2:
        alert_active = True
        print("[INFO] ENABLE alerts.")
    elif alert_active and stable_streak >= 3:
        alert_active = False
        print("[INFO] DISABLE alerts.")

    new_state = {
        'current_status': new_status,
        'last_response_time': response_duration,
        'extra_details': extra_info,
        'stable_streak': stable_streak,
        'degraded_streak': degraded_streak,
        'alert_active': alert_active,
        'last_check_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'recent_times': recent_times,
    }
    save_state(STATE_DB_FILE, new_state)
    save_history({
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "status": new_status
    })
    generate_status_html(OUTPUT_HTML, new_state)
    print(f"[INFO] Finished check at UTC {datetime.now(timezone.utc).isoformat()}\n{'-'*28}")

if __name__ == "__main__":
    # Run continuously, checking every CHECK_INTERVAL_MIN minutes
    while True:
        run_monitor()
        time.sleep(CHECK_INTERVAL_MIN * 60)
