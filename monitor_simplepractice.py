#!/usr/bin/env python3
"""
monitor_simplepractice.py

A simple script that checks the load speed and availability of 
"https://account.simplepractice.com/", storing status in `status.json` 
and generating an HTML summary in `index.html`.

Includes:
  - Timeout detection
  - "Slow" threshold logic
  - Rolling average speed
  - Repeated states tracking (stable vs. degraded)
  - Basic HTML generation with Tailwind CSS
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
TIMEOUT_LIMIT = 15                # seconds before we consider it timed out
SLOW_THRESHOLD = 2.0              # threshold above which a response is considered slow
STATE_DB_FILE = "status.json"     # local JSON-based "database" of prior states
OUTPUT_HTML = "index.html"        # output file showing the current status
CHECK_INTERVAL_MIN = 5            # used in the countdown display (not the actual schedule)
MAX_TIMES_TRACKED = 100           # Define the maximum number of history entries to track

# =====================================
# === STATUS CATEGORIES & UI INFO ===
# =====================================
STATUS_META = {
    "UP": {
        "emoji": "✅",
        "headline": "All Good!",
        "bg_class": "bg-green-100",
        "text_class": "text-green-700"
    },
    "SLOW": {
        "emoji": "🐢",
        "headline": "A Bit Slow...",
        "bg_class": "bg-yellow-100",
        "text_class": "text-yellow-700"
    },
    "ERROR": {
        "emoji": "⚠️",
        "headline": "Uh Oh! Error!",
        "bg_class": "bg-orange-100",
        "text_class": "text-orange-700"
    },
    "DOWN": {
        "emoji": "💔",
        "headline": "It's Down!",
        "bg_class": "bg-red-100",
        "text_class": "text-red-700"
    },
    "UNKNOWN": {
        "emoji": "❓",
        "headline": "Unknown",
        "bg_class": "bg-gray-100",
        "text_class": "text-gray-700"
    },
}

# =====================================
# === HELPER FUNCTIONS ===
# =====================================

def load_state(filename: str) -> dict:
    """
    Loads a previously saved state from JSON. If none exists (or it's invalid),
    returns a default state dictionary.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure the data is a dictionary
            if not isinstance(data, dict):
                raise ValueError("State file does not contain a dictionary")
            # Ensure all expected keys exist
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
        # Log the error and return an empty dictionary
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
    Appends the current state dictionary to the JSON file.
    Ensures the list of recent times doesn't exceed MAX_TIMES_TRACKED.
    """
    try:
        # Load existing data if the file exists
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = []
        else:
            existing_data = []

        # Append the new state to the existing data
        existing_data.append(state)

        # Limit the data to the maximum number of entries
        existing_data = existing_data[-MAX_TIMES_TRACKED:]

        # Save the updated data back to the file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2)
    except OSError as e:
        print(f"[ERROR] Could not save state to {filename}. Reason: {e}")


def save_history(entry: dict, filename: str = "history.json"):
    """
    Appends a new entry to the history file.
    """
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        else:
            history = []
        history.insert(0, entry)  # Add the new entry to the beginning
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(history[:MAX_TIMES_TRACKED], f, indent=2)
    except OSError as e:
        print(f"[ERROR] Could not save history to {filename}. Reason: {e}")


def calc_average_speed(times_list: list) -> float:
    """
    Given a list of numeric response times, filter out 0 or invalid entries
    and return the average.
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
    Generates a Tailwind-based HTML page summarizing the SimplePractice site's status.
    """
    current_status = state.get('current_status', 'UNKNOWN')
    meta = STATUS_META.get(current_status, STATUS_META["UNKNOWN"])

    # Format the most recent (last) response time
    rt = state.get('last_response_time', 0)
    if isinstance(rt, (int, float)) and rt > 0:
        last_rt_str = f"{rt:.2f} s"
    else:
        last_rt_str = "-- s"

    # Prepare average info
    times = state.get('recent_times', [])
    avg_speed = calc_average_speed(times)
    avg_str = f"{avg_speed:.2f} s" if avg_speed > 0 else "-- s"

    # Count how many times are valid in the rolling set
    valid_count = sum(1 for x in times if isinstance(x, (int, float)) and 0 < x < TIMEOUT_LIMIT)

    # Attempt to parse the last check time
    last_check_utc_str = state.get('last_check_utc') or ''
    last_check_display = "Never"
    if last_check_utc_str:
        try:
            dt_utc = datetime.fromisoformat(last_check_utc_str.replace('Z', '+00:00'))
            last_check_display = dt_utc.astimezone().strftime('%b %d, %Y, %I:%M:%S %p %Z')
        except ValueError:
            pass

    # Additional info (error messages, status codes, etc.)
    extra = state.get('extra_details', '')

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
    body {{
      font-family: 'Inter', sans-serif;
    }}
    @keyframes pulse-bg {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.7; }}
    }}
    .animate-pulse-bg {{
      animation: pulse-bg 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }}
    .status-emoji {{
      font-size: 1.5rem;
      line-height: 1;
      margin-right: 0.5rem;
      display: inline-block;
      vertical-align: middle;
    }}
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

    <div id="status-card" class="rounded-lg p-6 mb-6 transition-colors duration-500 {meta['bg_class']} {'animate-pulse-bg' if current_status in ['SLOW', 'ERROR', 'DOWN'] else ''}">
      <div class="flex items-center justify-between mb-4 flex-wrap">
        <h2 class="text-xl font-medium flex items-center {meta['text_class']} mb-2 sm:mb-0">
          <span class="status-emoji">{meta['emoji']}</span>
          <span>How's it doing?</span>
          <span id="status-text" class="ml-2 font-semibold">{html.escape(meta['headline'])}</span>
        </h2>
        <span class="text-xs text-gray-500 w-full text-right sm:w-auto">
          Checked:
          <span id="last-checked-display">{html.escape(last_check_display)}</span>
          {f'<span id="last-check-iso" style="display:none;">{html.escape(last_check_utc_str)}</span>' if last_check_utc_str else ''}
        </span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
          <span class="text-gray-600 block text-xs mb-1">Load Speed (Last)</span>
          <span id="response-time" class="font-semibold text-lg text-gray-800">{html.escape(last_rt_str)}</span>
        </div>
        <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
          <span class="text-gray-600 block text-xs mb-1">
            Avg. Speed (Last {valid_count})
          </span>
          <span id="avg-speed" class="font-semibold text-lg text-gray-800">{html.escape(avg_str)}</span>
        </div>
      </div>
      {"".join([
        f'<div class="text-xs text-center mt-3 {meta["text_class"]}"><p>({html.escape(extra)})</p></div>'
      ]) if current_status in ["ERROR", "DOWN"] and extra else ""}
    </div>

    <div class="text-center mb-6 text-sm text-gray-600">
      <p>
        Approx. next check in:
        <span id="countdown-timer" class="font-semibold">--:--</span>
      </p>
      <p class="text-xs text-gray-500">
        (Refreshes roughly every {CHECK_INTERVAL_MIN} min by automation)
      </p>
    </div>

    <div class="text-center text-xs text-gray-400 mt-6">
      Status as of: {html.escape(last_check_display)}.
    </div>
  </div>

  <script>
    const cdEl = document.getElementById('countdown-timer');
    const lastCheckEl = document.getElementById('last-check-iso');
    const intervalMs = {CHECK_INTERVAL_MIN} * 60 * 1000;

    function updateCountdown() {{
      if (!lastCheckEl || !cdEl) {{
        return;
      }}
      const iso = lastCheckEl.textContent;
      if (!iso) {{
        cdEl.textContent = "--:--";
        return;
      }}
      const startMillis = new Date(iso).getTime();
      if (isNaN(startMillis)) {{
        cdEl.textContent = "--:--";
        return;
      }}
      const now = Date.now();
      const nextCheck = startMillis + intervalMs;
      const diff = nextCheck - now;

      if (diff <= 0) {{
        cdEl.textContent = "Soon...";
      }} else {{
        const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const secs = Math.floor((diff % (1000 * 60)) / 1000);
        cdEl.textContent = String(mins).padStart(2, '0') + ":" + String(secs).padStart(2, '0');
      }}
    }}

    updateCountdown();
    setInterval(updateCountdown, 1000);
  </script>
</body>
</html>
"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_out)
        print(f"[INFO] HTML file generated: {filename}")
    except OSError as e:
        print(f"[ERROR] Could not write HTML output. Reason: {e}")


def run_monitor():
    """
    The main check logic:
      - Load prior state
      - Time a request to the site
      - Decide if it's UP, SLOW, ERROR, or DOWN
      - Update streaks and alert flags
      - Save new state, generate fresh HTML
    """
    print(f"{'-' * 28}\n[INFO] Starting check at UTC {datetime.now(timezone.utc).isoformat()}")
    state = load_state(STATE_DB_FILE)

    # Extract prior state data
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
            if response_duration > SLOW_THRESHOLD:
                new_status = "SLOW"
            else:
                new_status = "UP"
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

    # Log the result
    print(f"[INFO] Result -> Status={new_status}, RespTime={response_duration:.2f}s, Info='{extra_info}'")

    # Decide how to record the new response time
    record_time = response_duration if new_status in ("UP", "SLOW") else 0
    recent_times.append(record_time)

    # Update stable/degraded streak counts
    if new_status == "UP":
        stable_streak += 1
        degraded_streak = 0
    else:
        degraded_streak += 1
        stable_streak = 0

    # Manage the "alert_active" flag
    if not alert_active and degraded_streak >= 2:
        alert_active = True
        print("[INFO] Condition met to ENABLE alerts.")
    elif alert_active and stable_streak >= 3:
        alert_active = False
        print("[INFO] Condition met to DISABLE alerts.")

    # Build and save the new state
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

    # Save the history entry
    save_history({
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "status": new_status
    })

    # Generate the HTML
    generate_status_html(OUTPUT_HTML, new_state)

    print(f"[INFO] Finished check at UTC {datetime.now(timezone.utc).isoformat()}")
    print("-" * 28)


if __name__ == "__main__":
    run_monitor()
