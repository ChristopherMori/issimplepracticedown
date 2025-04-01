# SimplePractice Status Snitch - GitHub Action Version
# Calculates Avg Speed, updates UI, adds estimated countdown.
# Fixes f-string syntax error in HTML generation.

import requests
import time
from datetime import datetime, timezone, timedelta
import json
import os
import html

# === CONFIGURATION ===
URL = "https://account.simplepractice.com/"
TIMEOUT_SECONDS = 15
SLOW_THRESHOLD = 2.0
STATE_FILE = "status.json"
OUTPUT_HTML_FILE = "index.html"
CHECK_INTERVAL_MINUTES = 5
MAX_RESPONSE_TIMES_TO_KEEP = 3

# === STATUS INFO (for display) ===
STATUS_INFO = {
    "UP": {"emoji": "✅", "text": "All Good!", "card_bg_class": "bg-green-100", "text_color": "text-green-700"},
    "SLOW": {"emoji": "🐢", "text": "A Bit Slow...", "card_bg_class": "bg-yellow-100", "text_color": "text-yellow-700"},
    "ERROR": {"emoji": "⚠️", "text": "Uh Oh! Error!", "card_bg_class": "bg-orange-100", "text_color": "text-orange-700"},
    "DOWN": {"emoji": "💔", "text": "It's Down!", "card_bg_class": "bg-red-100", "text_color": "text-red-700"},
    "UNKNOWN": {"emoji": "❓", "text": "Unknown", "card_bg_class": "bg-gray-100", "text_color": "text-gray-700"},
}

# === HELPER FUNCTIONS ===

def load_previous_state(filename):
    """Loads state including the list of recent response times."""
    try:
        with open(filename, 'r') as f:
            state = json.load(f)
            state.setdefault('status', 'UNKNOWN')
            state.setdefault('stable_count', 0)
            state.setdefault('degraded_count', 0)
            state.setdefault('alert_mode', False)
            state.setdefault('last_check_timestamp_utc', None)
            state.setdefault('response_time', 0)
            state.setdefault('extra_info', '')
            times = state.get('recent_response_times', [])
            if not isinstance(times, list): times = []
            state['recent_response_times'] = times[-MAX_RESPONSE_TIMES_TO_KEEP:]
            print(f"Loaded previous state: {state}")
            return state
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"State file '{filename}' not found or invalid, starting fresh. Error: {e}")
        return {
            'status': 'UNKNOWN', 'stable_count': 0, 'degraded_count': 0, 'alert_mode': False,
            'last_check_timestamp_utc': None, 'response_time': 0, 'extra_info': '',
            'recent_response_times': []
        }

def save_current_state(filename, state_data):
    """Saves the current state to the state file."""
    try:
        times = state_data.get('recent_response_times', [])
        if not isinstance(times, list): times = []
        state_data['recent_response_times'] = times[-MAX_RESPONSE_TIMES_TO_KEEP:]
        with open(filename, 'w') as f:
            json.dump(state_data, f, indent=4)
        print(f"Saved current state to {filename}: {state_data}")
    except IOError as e:
        print(f"Error saving state file '{filename}': {e}")

def calculate_average_speed(times_list):
    """Calculates average from a list of times, ignoring zeros/timeouts."""
    valid_times = []
    if isinstance(times_list, list):
        for t in times_list:
            try:
                time_float = float(t)
                if time_float > 0 and time_float < TIMEOUT_SECONDS:
                    valid_times.append(time_float)
            except (ValueError, TypeError): continue
    if not valid_times: return 0
    return sum(valid_times) / len(valid_times)

def generate_html(filename, status_data):
    """Generates the index.html file with updated UI, avg speed, and countdown."""
    status = status_data.get('status', 'UNKNOWN')
    info = STATUS_INFO.get(status, STATUS_INFO["UNKNOWN"])

    response_time = status_data.get('response_time', 0)
    response_time_str = f"{response_time:.2f} s" if status != 'UNKNOWN' and isinstance(response_time, (int, float)) and response_time >= 0 else "-- s"

    recent_times = status_data.get('recent_response_times', [])
    average_speed = calculate_average_speed(recent_times)
    average_speed_str = f"{average_speed:.2f} s" if average_speed > 0 else "-- s"
    valid_times_count = sum(1 for t in recent_times if isinstance(t, (int, float)) and t > 0 and t < TIMEOUT_SECONDS)

    last_check_utc_str = status_data.get('last_check_timestamp_utc', None)
    last_check_dt_utc = None
    last_check_local_str = "Never"
    if last_check_utc_str:
        try:
            last_check_dt_utc = datetime.fromisoformat(last_check_utc_str.replace('Z', '+00:00'))
            last_check_local_str = last_check_dt_utc.astimezone().strftime('%b %d, %Y, %I:%M:%S %p %Z')
        except ValueError:
            last_check_local_str = "Invalid date"

    # --- HTML Structure ---
    # Removed the problematic comment inside the grid div class line
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimplePractice Status Snitch ✨</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://rsms.me/">
    <link rel="stylesheet" href="https://rsms.me/inter/inter.css">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        @keyframes pulse-bg {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}
        .animate-pulse-bg {{ animation: pulse-bg 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }}
        .status-emoji {{ font-size: 1.5rem; line-height: 1; margin-right: 0.5rem; display: inline-block; vertical-align: middle; }}
    </style>
</head>
<body class="bg-gray-100 p-4 md:p-8">
    <div class="max-w-2xl mx-auto bg-white rounded-xl shadow-lg p-6 md:p-8">
        <header class="mb-6 text-center">
            <h1 class="text-3xl font-bold text-gray-800 mb-1">Status Snitch! ✨</h1>
            <p class="text-sm text-gray-500">Keeping an eye on: <code class="bg-gray-100 px-1 rounded font-mono">{html.escape(URL)}</code></p>
        </header>

        <div id="status-card" class="rounded-lg p-6 mb-6 transition-colors duration-500 {info['card_bg_class']} {'animate-pulse-bg' if status in ['SLOW', 'ERROR', 'DOWN'] else ''}">
            <div class="flex items-center justify-between mb-4 flex-wrap">
                <h2 class="text-xl font-medium flex items-center {info['text_color']} mb-2 sm:mb-0">
                    <span class="status-emoji">{info['emoji']}</span>
                    <span>How's it doing?</span> <span id="status-text" class="ml-2 font-semibold">{html.escape(info['text'])}</span>
                </h2>
                <span class="text-xs text-gray-500 w-full text-right sm:w-auto">
                    Checked: <span id="last-checked-display">{html.escape(last_check_local_str)}</span>
                    {f'<span id="last-checked-iso" style="display: none;">{html.escape(last_check_utc_str)}</span>' if last_check_utc_str else ''}
                </span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm"> {/* Removed comment here */}
                <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                    <span class="text-gray-600 block text-xs mb-1">Load Speed (Last)</span>
                    <span id="response-time" class="font-semibold text-lg text-gray-800">{html.escape(response_time_str)}</span>
                </div>
                <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                    <span class="text-gray-600 block text-xs mb-1">Avg. Speed (Last {valid_times_count})</span>
                    <span id="avg-speed" class="font-semibold text-lg text-gray-800">{html.escape(average_speed_str)}</span>
                </div>
            </div>
             {f'<div class="text-xs text-center mt-3 {info["text_color"]}"><p>({html.escape(status_data.get("extra_info", ""))})</p></div>' if status in ["ERROR", "DOWN"] and status_data.get("extra_info") else ''}
        </div>

        <div class="text-center mb-6 text-sm text-gray-600">
            <p>Approx. next check in: <span id="countdown-timer" class="font-semibold">--:--</span></p>
            <p class="text-xs text-gray-500">(Page updates roughly every {CHECK_INTERVAL_MINUTES} min via automation)</p>
        </div>

        <div class="text-center text-xs text-gray-400 mt-6">
            Status as of: {html.escape(last_check_local_str)}.
        </div>
    </div>

    <script>
      // Countdown Timer Logic (same as before)
      const countdownElement = document.getElementById('countdown-timer');
      const lastCheckIsoElement = document.getElementById('last-checked-iso');
      const checkIntervalMillis = {CHECK_INTERVAL_MINUTES} * 60 * 1000;
      function updateCountdown() {{ const lastCheckIso = lastCheckIsoElement ? lastCheckIsoElement.textContent : null; if (!lastCheckIso || !countdownElement || lastCheckIso === 'None' || lastCheckIso === '') {{ countdownElement.textContent = "--:--"; return; }} try {{ const lastCheckTime = new Date(lastCheckIso).getTime(); if (isNaN(lastCheckTime)) {{ countdownElement.textContent = "--:--"; return; }} const nextCheckTime = lastCheckTime + checkIntervalMillis; const now = new Date().getTime(); const timeRemaining = nextCheckTime - now; if (timeRemaining <= 0) {{ countdownElement.textContent = "Updating soon..."; }} else {{ const minutes = Math.floor((timeRemaining % (1000 * 60 * 60)) / (1000 * 60)); const seconds = Math.floor((timeRemaining % (1000 * 60)) / 1000); countdownElement.textContent = `${{String(minutes).padStart(2, '0')}}:${{String(seconds).padStart(2, '0')}}`; }} }} catch (e) {{ console.error("Error calculating countdown:", e); countdownElement.textContent = "Error"; }} }} if (lastCheckIsoElement && lastCheckIsoElement.textContent && lastCheckIsoElement.textContent !== 'None') {{ updateCountdown(); setInterval(updateCountdown, 1000); }} else {{ countdownElement.textContent = "--:--"; }}
    </script>

</body>
</html>"""

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Generated {filename}")
    except IOError as e:
        print(f"Error writing HTML file '{filename}': {e}")


# === MAIN CHECK LOGIC === (No changes needed from V2)
def perform_check():
    """Performs one status check, updates state, and generates output."""
    print("-" * 30)
    print(f"Starting check at {datetime.now(timezone.utc).isoformat()}")
    prev_state = load_previous_state(STATE_FILE)
    recent_times = prev_state.get('recent_response_times', [])
    if not isinstance(recent_times, list): recent_times = []
    stable_count = prev_state['stable_count']
    degraded_count = prev_state['degraded_count']
    alert_mode = prev_state['alert_mode']
    start_time = time.time()
    current_status = "UNKNOWN"
    response_time = 0
    extra_info = None
    status_code_info = ""
    try:
        response = requests.get(URL, timeout=TIMEOUT_SECONDS)
        response_time = time.time() - start_time
        status_code = response.status_code
        status_code_info = f"Status code: {status_code}"
        if status_code == 200:
            current_status = "SLOW" if response_time > SLOW_THRESHOLD else "UP"
        else:
            current_status = "ERROR"; extra_info = status_code_info
    except requests.exceptions.Timeout:
        current_status = "DOWN"; response_time = 0; extra_info = "Request timed out"
    except requests.exceptions.RequestException as e:
        current_status = "DOWN"; response_time = 0; extra_info = f"Network error: {type(e).__name__}"
    except Exception as e:
        current_status = "ERROR"; response_time = 0; extra_info = f"Unexpected error: {type(e).__name__}"
        print(f"!!! Unexpected error during check: {e}")
    print(f"Check result: Status={current_status}, ResponseTime={response_time:.2f}s, Extra='{extra_info}'")
    current_time_for_list = response_time if current_status in ["UP", "SLOW"] else 0
    recent_times.append(current_time_for_list)
    recent_times = recent_times[-MAX_RESPONSE_TIMES_TO_KEEP:]
    if current_status == "UP": stable_count += 1; degraded_count = 0
    else: degraded_count += 1; stable_count = 0
    new_alert_mode = alert_mode
    if not alert_mode and degraded_count >= 2: new_alert_mode = True; print("Condition met to enter ALERT mode (state tracked).")
    elif alert_mode and stable_count >= 3: new_alert_mode = False; print("Condition met to exit ALERT mode (state tracked).")
    current_state_data = {
        'status': current_status, 'response_time': response_time, 'extra_info': extra_info,
        'stable_count': stable_count, 'degraded_count': degraded_count, 'alert_mode': new_alert_mode,
        'last_check_timestamp_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'recent_response_times': recent_times
    }
    save_current_state(STATE_FILE, current_state_data)
    generate_html(OUTPUT_HTML_FILE, current_state_data)
    print(f"Finished check at {datetime.now(timezone.utc).isoformat()}")
    print("-" * 30)

# === SCRIPT EXECUTION ===
if __name__ == "__main__":
    perform_check()
