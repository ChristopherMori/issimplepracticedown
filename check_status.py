# SimplePractice Status Snitch - GitHub Action Version
# This script reads previous state, performs one check, updates state,
# and generates an index.html file with the status.

import requests
import time
from datetime import datetime, timezone
import json
import os

# === CONFIGURATION ===
URL = "https://account.simplepractice.com/" # The website to check
TIMEOUT_SECONDS = 15
SLOW_THRESHOLD = 2.0
NORMAL_LOAD_TIME = 0.5
STATE_FILE = "status.json" # File to store status between runs
OUTPUT_HTML_FILE = "index.html" # HTML file to be served by GitHub Pages

# === STATUS INFO (for display) ===
STATUS_INFO = {
    "UP": {"emoji": "✅", "text": "All Good!", "color": "#22c55e"},
    "SLOW": {"emoji": "🐢", "text": "A Bit Slow...", "color": "#facc15"},
    "ERROR": {"emoji": "⚠️", "text": "Uh Oh! Error!", "color": "#f97316"},
    "DOWN": {"emoji": "💔", "text": "It's Down!", "color": "#ef4444"},
    "UNKNOWN": {"emoji": "❓", "text": "Unknown", "color": "#6b7280"},
}

# === HELPER FUNCTIONS ===

def load_previous_state(filename):
    """Loads status, counts, and mode from the state file."""
    try:
        with open(filename, 'r') as f:
            state = json.load(f)
            # Provide defaults if keys are missing from older files
            state.setdefault('status', 'UNKNOWN')
            state.setdefault('stable_count', 0)
            state.setdefault('degraded_count', 0)
            state.setdefault('alert_mode', False) # Keep track of alert mode for context if needed
            state.setdefault('last_check_timestamp_utc', None)
            print(f"Loaded previous state: {state}")
            return state
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"State file '{filename}' not found or invalid, starting fresh. Error: {e}")
        # Return default initial state
        return {
            'status': 'UNKNOWN',
            'stable_count': 0,
            'degraded_count': 0,
            'alert_mode': False,
            'last_check_timestamp_utc': None
        }

def save_current_state(filename, state_data):
    """Saves the current status, counts, mode, and timestamp to the state file."""
    try:
        with open(filename, 'w') as f:
            json.dump(state_data, f, indent=4)
        print(f"Saved current state to {filename}: {state_data}")
    except IOError as e:
        print(f"Error saving state file '{filename}': {e}")


def generate_html(filename, status_data):
    """Generates the index.html file with the current status."""
    status = status_data.get('status', 'UNKNOWN')
    info = STATUS_INFO.get(status, STATUS_INFO["UNKNOWN"])
    response_time_str = f"{status_data.get('response_time', 0):.2f}s" if status != 'UNKNOWN' else "-- s"
    extra_info_str = status_data.get('extra_info', '')
    last_check_utc_str = status_data.get('last_check_timestamp_utc', 'Never')
    last_check_dt_utc = datetime.fromisoformat(last_check_utc_str.replace('Z', '+00:00')) if last_check_utc_str and last_check_utc_str != 'Never' else None
    last_check_local_str = last_check_dt_utc.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z') if last_check_dt_utc else "Never" # Convert to local time for display

    # Simple HTML structure - can be enhanced with CSS
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300"> <title>SimplePractice Status</title>
    <style>
        body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 90vh; background-color: #f0f0f0; }}
        .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; }}
        .status {{ font-size: 2.5em; font-weight: bold; color: {info['color']}; margin-bottom: 15px; }}
        .details span {{ display: inline-block; margin: 0 10px; color: #555; }}
        .timestamp {{ margin-top: 20px; font-size: 0.8em; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>SimplePractice Status</h1>
        <div class="status">{info['emoji']} {info['text']}</div>
        <div class="details">
            <span>Load: {response_time_str}</span>
            {'<span>(' + extra_info_str + ')</span>' if extra_info_str else ''}
        </div>
        <div class="timestamp">Last Checked: {last_check_local_str}</div>
    </div>
</body>
</html>"""

    try:
        with open(filename, 'w') as f:
            f.write(html_content)
        print(f"Generated {filename}")
    except IOError as e:
        print(f"Error writing HTML file '{filename}': {e}")


# === MAIN CHECK LOGIC ===
def perform_check():
    """Performs one status check, updates state, and generates output."""
    print("-" * 30)
    print(f"Starting check at {datetime.now(timezone.utc).isoformat()}")

    # Load previous state (including counts and mode)
    prev_state = load_previous_state(STATE_FILE)
    stable_count = prev_state['stable_count']
    degraded_count = prev_state['degraded_count']
    alert_mode = prev_state['alert_mode'] # We might not use alert_mode actively, but good to track

    # --- Perform the check ---
    start_time = time.time()
    current_status = "UNKNOWN"
    response_time = 0
    extra_info = None

    try:
        response = requests.get(URL, timeout=TIMEOUT_SECONDS)
        response_time = time.time() - start_time
        status_code = response.status_code

        if status_code == 200:
            if response_time > SLOW_THRESHOLD:
                current_status = "SLOW"
                extra_time = max(0, response_time - NORMAL_LOAD_TIME)
                extra_info = f"+{extra_time:.1f}s extra"
            else:
                current_status = "UP"
        else:
            current_status = "ERROR"
            extra_info = f"Status code: {status_code}"

    except requests.exceptions.Timeout:
        current_status = "DOWN"
        response_time = TIMEOUT_SECONDS
        extra_info = "Request timed out"
    except requests.exceptions.RequestException as e:
        current_status = "DOWN"
        response_time = time.time() - start_time
        extra_info = f"Network error: {type(e).__name__}"
    except Exception as e:
        current_status = "ERROR"
        response_time = time.time() - start_time
        extra_info = f"Unexpected error: {type(e).__name__}"
        print(f"!!! Unexpected error during check: {e}")

    print(f"Check result: Status={current_status}, ResponseTime={response_time:.2f}s, Extra='{extra_info}'")

    # --- Update State Counters ---
    if current_status == "UP":
        stable_count += 1
        degraded_count = 0
    else: # SLOW, ERROR, or DOWN
        degraded_count += 1
        stable_count = 0

    # --- Update Alert Mode (Optional - mainly for context/logging now) ---
    new_alert_mode = alert_mode # Assume current mode unless changed
    if not alert_mode and degraded_count >= 2:
        new_alert_mode = True
        print("Condition met to enter ALERT mode (if intervals were adaptive).")
    elif alert_mode and stable_count >= 3:
        new_alert_mode = False
        print("Condition met to exit ALERT mode (if intervals were adaptive).")

    # --- Prepare data for saving ---
    current_state_data = {
        'status': current_status,
        'response_time': response_time,
        'extra_info': extra_info,
        'stable_count': stable_count,
        'degraded_count': degraded_count,
        'alert_mode': new_alert_mode,
        'last_check_timestamp_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z') # Use ISO format UTC
    }

    # --- Save state and generate HTML ---
    save_current_state(STATE_FILE, current_state_data)
    generate_html(OUTPUT_HTML_FILE, current_state_data)

    print(f"Finished check at {datetime.now(timezone.utc).isoformat()}")
    print("-" * 30)

# === SCRIPT EXECUTION ===
if __name__ == "__main__":
    perform_check()
