# SimplePractice Status Snitch - GitHub Action Version (with History & EST/EDT)
# Stores history, calculates Avg Speed, updates UI with Eastern Time display.

import requests
import time
from datetime import datetime, timezone, timedelta
import json
import os
import html
import pytz # Import pytz for timezone handling

# === CONFIGURATION ===
URL = "https://account.simplepractice.com/"
TIMEOUT_SECONDS = 15
SLOW_THRESHOLD = 2.0
STATE_FILE = "status.json"
OUTPUT_HTML_FILE = "index.html"
CHECK_INTERVAL_MINUTES = 5
MAX_RESPONSE_TIMES_TO_KEEP = 3
MAX_HISTORY_RECORDS = 50
TARGET_TIMEZONE = 'America/New_York' # Timezone for display

# === STATUS INFO (for display) ===
STATUS_INFO = {
    "UP": {"emoji": "✅", "text": "All Good!", "card_bg_class": "bg-green-100", "text_color": "text-green-700", "history_class": "text-green-600"},
    "SLOW": {"emoji": "🐢", "text": "A Bit Slow...", "card_bg_class": "bg-yellow-100", "text_color": "text-yellow-700", "history_class": "text-yellow-600"},
    "ERROR": {"emoji": "⚠️", "text": "Uh Oh! Error!", "card_bg_class": "bg-orange-100", "text_color": "text-orange-700", "history_class": "text-orange-600"},
    "DOWN": {"emoji": "💔", "text": "It's Down!", "card_bg_class": "bg-red-100", "text_color": "text-red-700", "history_class": "text-red-600"},
    "UNKNOWN": {"emoji": "❓", "text": "Unknown", "card_bg_class": "bg-gray-100", "text_color": "text-gray-700", "history_class": "text-gray-500"},
}

# === HELPER FUNCTIONS ===

def load_previous_state(filename):
    """Loads state including history and recent response times."""
    default_state = {
        'status': 'UNKNOWN', 'stable_count': 0, 'degraded_count': 0, 'alert_mode': False,
        'last_check_timestamp_utc': None, 'response_time': 0, 'extra_info': '',
        'recent_response_times': [], 'history': []
    }
    try:
        if not os.path.exists(filename):
             print(f"State file '{filename}' not found, starting fresh.")
             return default_state
        with open(filename, 'r') as f:
            state = json.load(f)
            for key, default_value in default_state.items(): state.setdefault(key, default_value)
            if not isinstance(state.get('recent_response_times'), list): state['recent_response_times'] = []
            state['recent_response_times'] = state['recent_response_times'][-MAX_RESPONSE_TIMES_TO_KEEP:]
            if not isinstance(state.get('history'), list): state['history'] = []
            state['history'] = state['history'][-MAX_HISTORY_RECORDS:]
            print(f"Loaded previous state (History items: {len(state['history'])})")
            return state
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
        print(f"State file '{filename}' not found or invalid, starting fresh. Error: {e}")
        return default_state

def save_current_state(filename, state_data):
    """Saves the current state (including history) to the state file."""
    try:
        times = state_data.get('recent_response_times', [])
        if not isinstance(times, list): times = []
        state_data['recent_response_times'] = times[-MAX_RESPONSE_TIMES_TO_KEEP:]
        history = state_data.get('history', [])
        if not isinstance(history, list): history = []
        state_data['history'] = history[-MAX_HISTORY_RECORDS:]
        with open(filename, 'w') as f:
            json.dump(state_data, f, indent=2)
        print(f"Saved current state to {filename} (History items: {len(state_data['history'])})")
    except IOError as e:
        print(f"Error saving state file '{filename}': {e}")

def calculate_average_speed(times_list):
    """Calculates average from a list of times, ignoring zeros/timeouts."""
    valid_times = []
    if isinstance(times_list, list):
        for t in times_list:
            try:
                time_float = float(t)
                if time_float > 0 and time_float < TIMEOUT_SECONDS: valid_times.append(time_float)
            except (ValueError, TypeError): continue
    if not valid_times: return 0, 0
    return sum(valid_times) / len(valid_times), len(valid_times)

def generate_html(filename, state_data):
    """Generates the index.html file with current status and history table."""

    # --- Get Timezone Object ---
    try:
        eastern_tz = pytz.timezone(TARGET_TIMEZONE)
    except pytz.UnknownTimeZoneError:
        print(f"Error: Unknown timezone '{TARGET_TIMEZONE}'. Defaulting to UTC.")
        eastern_tz = timezone.utc # Fallback to UTC

    # --- Get Latest Status Data ---
    history = state_data.get('history', [])
    latest_check_data = history[-1] if history else {}
    status = latest_check_data.get('status', 'UNKNOWN')
    info = STATUS_INFO.get(status, STATUS_INFO["UNKNOWN"])
    response_time = latest_check_data.get('response_time', 0)
    response_time_str = f"{response_time:.2f} s" if status != 'UNKNOWN' and isinstance(response_time, (int, float)) and response_time >= 0 else "-- s"

    # --- Calculate Average Speed ---
    recent_times = state_data.get('recent_response_times', [])
    average_speed, valid_avg_count = calculate_average_speed(recent_times)
    average_speed_str = f"{average_speed:.2f} s" if average_speed > 0 else "-- s"

    # --- Prepare Timestamp (Convert to Eastern Time) ---
    last_check_utc_str = latest_check_data.get('timestamp', state_data.get('last_check_timestamp_utc'))
    last_check_local_str = "Never"
    if last_check_utc_str:
        try:
            # Parse ISO string, make it UTC aware
            last_check_dt_utc = datetime.fromisoformat(last_check_utc_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
            # Convert to target timezone
            last_check_dt_local = last_check_dt_utc.astimezone(eastern_tz)
            # Format timestamp nicely (e.g., "Apr 03, 2025, 11:26:15 AM EDT")
            # %Z should correctly show EST or EDT based on the date and pytz data
            last_check_local_str = last_check_dt_local.strftime('%b %d, %Y, %I:%M:%S %p %Z')
        except (ValueError, TypeError) as e:
            print(f"Error formatting main timestamp: {e}")
            last_check_local_str = "Invalid date"

    # --- Generate History Table Rows (Convert to Eastern Time) ---
    history_rows_html = ""
    for check in reversed(history):
        hist_status = check.get('status', 'UNKNOWN')
        hist_info = STATUS_INFO.get(hist_status, STATUS_INFO["UNKNOWN"])
        hist_resp_time = check.get('response_time', 0)
        try:
            hist_resp_time_float = float(hist_resp_time)
            hist_resp_time_str = f"{hist_resp_time_float:.2f} s" if hist_status != 'UNKNOWN' and hist_resp_time_float >= 0 else "-- s"
        except (ValueError, TypeError): hist_resp_time_str = "-- s"

        hist_extra = check.get('extra_info', '')
        hist_ts_str = check.get('timestamp', '')
        hist_local_str_short = "N/A"
        if hist_ts_str:
            try:
                # Parse ISO string, make it UTC aware
                hist_dt_utc = datetime.fromisoformat(hist_ts_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
                # Convert to target timezone
                hist_dt_local = hist_dt_utc.astimezone(eastern_tz)
                # Shorter format for history table (e.g., "Apr 03, 11:26:15 AM EDT")
                hist_local_str_short = hist_dt_local.strftime('%b %d, %I:%M:%S %p %Z')
            except (ValueError, TypeError) as e:
                 print(f"Error formatting history timestamp: {e}")
                 hist_local_str_short = "Invalid Date"

        history_rows_html += f"""
        <tr>
            <td class="whitespace-nowrap px-3 py-2 text-sm text-gray-500">{html.escape(hist_local_str_short)}</td>
            <td class="whitespace-nowrap px-3 py-2 text-sm font-medium {hist_info['history_class']}">
                {hist_info['emoji']} {html.escape(hist_status)}
            </td>
            <td class="whitespace-nowrap px-3 py-2 text-sm text-gray-500">{html.escape(hist_resp_time_str)}</td>
            <td class="px-3 py-2 text-sm text-gray-500">{html.escape(hist_extra or '')}</td>
        </tr>"""

    # --- Main HTML Structure ---
    # (HTML structure remains the same as check_status_py_final, only content changes)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimplePractice Status ✨</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://rsms.me/">
    <link rel="stylesheet" href="https://rsms.me/inter/inter.css">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        @keyframes pulse-bg {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}
        .animate-pulse-bg {{ animation: pulse-bg 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }}
        .status-emoji {{ font-size: 1.5rem; line-height: 1; margin-right: 0.5rem; display: inline-block; vertical-align: middle; }}
        .history-table th, .history-table td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid #e5e7eb; }}
        .history-table th {{ background-color: #f9fafb; text-align: left; font-weight: 500; color: #374151; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        .history-table tr:last-child td {{ border-bottom: none; }}
        .text-green-600 {{ color: #16a34a; }} .text-yellow-600 {{ color: #d97706; }} .text-orange-600 {{ color: #ea580c; }} .text-red-600 {{ color: #dc2626; }} .text-gray-500 {{ color: #6b7280; }}
    </style>
</head>
<body class="bg-gray-100 p-4 md:p-8">
    <div class="max-w-4xl mx-auto bg-white rounded-xl shadow-lg p-6 md:p-8">
        <header class="mb-6 text-center">
            <h1 class="text-3xl font-bold text-gray-800 mb-1">Status Snitch! ✨</h1>
            <p class="text-sm text-gray-500">Keeping an eye on: <code class="bg-gray-100 px-1 rounded font-mono">{html.escape(URL)}</code></p>
        </header>

        <div id="status-card" class="rounded-lg p-6 mb-8 transition-colors duration-500 {info['card_bg_class']} {'animate-pulse-bg' if status in ['SLOW', 'ERROR', 'DOWN'] else ''}">
            <div class="flex items-center justify-between mb-4 flex-wrap">
                <h2 class="text-xl font-medium flex items-center {info['text_color']} mb-2 sm:mb-0">
                    <span class="status-emoji">{info['emoji']}</span>
                    <span>Current Status:</span> <span id="status-text" class="ml-2 font-semibold">{html.escape(info['text'])}</span>
                </h2>
                <span class="text-xs text-gray-500 w-full text-right sm:w-auto">
                    Checked: <span id="last-checked-display">{html.escape(last_check_local_str)}</span>
                </span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                    <span class="text-gray-600 block text-xs mb-1">Load Speed (Last)</span>
                    <span id="response-time" class="font-semibold text-lg text-gray-800">{html.escape(response_time_str)}</span>
                </div>
                <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                    {f'<span class="text-gray-600 block text-xs mb-1">Avg. Speed (Last {valid_avg_count})</span>' if valid_avg_count > 0 else '<span class="text-gray-600 block text-xs mb-1">Avg. Speed</span>'}
                    <span id="avg-speed" class="font-semibold text-lg text-gray-800">{html.escape(average_speed_str)}</span>
                </div>
            </div>
             {f'<div class="text-xs text-center mt-3 {info["text_color"]}"><p>({html.escape(latest_check_data.get("extra_info", ""))})</p></div>' if status in ["ERROR", "DOWN"] and latest_check_data.get("extra_info") else ''}
        </div>

        <section class="mb-6">
            <h2 class="text-xl font-semibold text-gray-700 mb-3">Recent History (Last {len(history)} Checks)</h2>
            {f'<div class="overflow-x-auto rounded-lg border border-gray-200 max-h-96 overflow-y-auto"><table class="min-w-full divide-y divide-gray-200 history-table"><thead><tr><th class="whitespace-nowrap">Timestamp ({TARGET_TIMEZONE})</th><th class="whitespace-nowrap">Status</th><th class="whitespace-nowrap">Load Time</th><th class="whitespace-nowrap">Details</th></tr></thead><tbody class="bg-white divide-y divide-gray-200">{history_rows_html}</tbody></table></div>' if history else '<p class="text-gray-500">No historical data available yet.</p>'}
        </section>

        <div class="text-center text-xs text-gray-400 mt-8">
            Status checks run automatically every {CHECK_INTERVAL_MINUTES} minutes via GitHub Actions. Page data reflects the last completed check.
        </div>
    </div>
</body>
</html>"""

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Generated {filename}")
    except IOError as e:
        print(f"Error writing HTML file '{filename}': {e}")


# === MAIN CHECK LOGIC === (No changes needed from previous history version)
def perform_check():
    """Performs one status check, updates state including history, and generates output."""
    print("-" * 30)
    check_timestamp_utc = datetime.now(timezone.utc)
    print(f"Starting check at {check_timestamp_utc.isoformat()}")
    prev_state = load_previous_state(STATE_FILE)
    recent_times = prev_state.get('recent_response_times', [])
    if not isinstance(recent_times, list): recent_times = []
    history = prev_state.get('history', [])
    if not isinstance(history, list): history = []
    stable_count = prev_state.get('stable_count', 0)
    degraded_count = prev_state.get('degraded_count', 0)
    alert_mode = prev_state.get('alert_mode', False)
    start_time = time.time()
    current_status = "UNKNOWN"
    response_time = 0
    extra_info = None
    try:
        response = requests.get(URL, timeout=TIMEOUT_SECONDS)
        response_time = time.time() - start_time
        status_code = response.status_code
        if status_code == 200:
            current_status = "SLOW" if response_time > SLOW_THRESHOLD else "UP"
        else:
            current_status = "ERROR"; extra_info = f"Status code: {status_code}"
    except requests.exceptions.Timeout:
        current_status = "DOWN"; response_time = 0; extra_info = "Request timed out"
    except requests.exceptions.RequestException as e:
        current_status = "DOWN"; response_time = 0; extra_info = f"Network error: {type(e).__name__}"
    except Exception as e:
        current_status = "ERROR"; response_time = 0; extra_info = f"Unexpected error: {type(e).__name__}"
        print(f"!!! Unexpected error during check: {e}")
    print(f"Check result: Status={current_status}, ResponseTime={response_time:.2f}s, Extra='{extra_info}'")
    current_check_record = {
        'timestamp': check_timestamp_utc.isoformat().replace('+00:00', 'Z'),
        'status': current_status,
        'response_time': float(f"{response_time:.3f}") if isinstance(response_time, (int, float)) else 0.0,
        'extra_info': str(extra_info) if extra_info is not None else None
    }
    history.append(current_check_record)
    history = history[-MAX_HISTORY_RECORDS:]
    current_time_for_avg = response_time if current_status in ["UP", "SLOW"] else 0
    recent_times.append(current_time_for_avg)
    recent_times = recent_times[-MAX_RESPONSE_TIMES_TO_KEEP:]
    if current_status == "UP": stable_count += 1; degraded_count = 0
    else: degraded_count += 1; stable_count = 0
    new_alert_mode = alert_mode
    if not alert_mode and degraded_count >= 2: new_alert_mode = True; print("Condition met to enter ALERT mode.")
    elif alert_mode and stable_count >= 3: new_alert_mode = False; print("Condition met to exit ALERT mode.")
    current_state_data = {
        'status': current_status, 'response_time': response_time, 'extra_info': extra_info,
        'stable_count': stable_count, 'degraded_count': degraded_count, 'alert_mode': new_alert_mode,
        'last_check_timestamp_utc': current_check_record['timestamp'],
        'recent_response_times': recent_times, 'history': history
    }
    save_current_state(STATE_FILE, current_state_data)
    generate_html(OUTPUT_HTML_FILE, current_state_data)
    print(f"Finished check processing at {datetime.now(timezone.utc).isoformat()}")
    print("-" * 30)

# === SCRIPT EXECUTION ===
if __name__ == "__main__":
    perform_check()
