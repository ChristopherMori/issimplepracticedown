# SimplePractice Status Snitch - GitHub Action Version
# Generates an index.html styled with Tailwind CSS
# Includes a link button to manually trigger the Action workflow

import requests
import time
from datetime import datetime, timezone
import json
import os
import html # For escaping potentially problematic characters if needed

# === CONFIGURATION ===
URL = "https://account.simplepractice.com/" # The website to check
TIMEOUT_SECONDS = 15
SLOW_THRESHOLD = 2.0
NORMAL_LOAD_TIME = 0.5
STATE_FILE = "status.json" # File to store status between runs
OUTPUT_HTML_FILE = "index.html" # HTML file to be served by GitHub Pages

# !!! IMPORTANT: Replace with the URL to your repository's Actions tab !!!
# Example: "https://github.com/YourUsername/YourRepoName/actions/workflows/status_check.yml"
REPO_ACTIONS_URL = "YOUR_REPO_URL_HERE/actions/workflows/status_check.yml"


# === STATUS INFO (for display) ===
STATUS_INFO = {
    "UP": {"emoji": "✅", "text": "All Good!", "card_bg_class": "bg-green-100", "text_color": "text-green-700"},
    "SLOW": {"emoji": "🐢", "text": "A Bit Slow...", "card_bg_class": "bg-yellow-100", "text_color": "text-yellow-700"},
    "ERROR": {"emoji": "⚠️", "text": "Uh Oh! Error!", "card_bg_class": "bg-orange-100", "text_color": "text-orange-700"},
    "DOWN": {"emoji": "💔", "text": "It's Down!", "card_bg_class": "bg-red-100", "text_color": "text-red-700"},
    "UNKNOWN": {"emoji": "❓", "text": "Unknown", "card_bg_class": "bg-gray-100", "text_color": "text-gray-700"},
    "CHECKING": {"emoji": "👀", "text": "Checking...", "card_bg_class": "bg-blue-100", "text_color": "text-blue-700"}
}

# === HELPER FUNCTIONS ===

def load_previous_state(filename):
    """Loads status, counts, and mode from the state file."""
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
            print(f"Loaded previous state: {state}")
            return state
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"State file '{filename}' not found or invalid, starting fresh. Error: {e}")
        return {
            'status': 'UNKNOWN',
            'stable_count': 0,
            'degraded_count': 0,
            'alert_mode': False,
            'last_check_timestamp_utc': None,
            'response_time': 0,
            'extra_info': ''
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
    """Generates the index.html file with the current status, styled with Tailwind."""
    status = status_data.get('status', 'UNKNOWN')
    info = STATUS_INFO.get(status, STATUS_INFO["UNKNOWN"])

    # Prepare metric values
    response_time = status_data.get('response_time', 0)
    response_time_str = f"{response_time:.2f} s" if status != 'UNKNOWN' else "-- s"
    normal_speed_str = f"{NORMAL_LOAD_TIME:.1f} s"

    extra_time = 0
    if status == "SLOW":
        extra_time = max(0, response_time - NORMAL_LOAD_TIME)
        extra_time_str = f"+{extra_time:.1f} s"
    else:
        extra_time_str = "-- s"

    # Prepare timestamp
    last_check_utc_str = status_data.get('last_check_timestamp_utc', 'Never')
    last_check_dt_utc = datetime.fromisoformat(last_check_utc_str.replace('Z', '+00:00')) if last_check_utc_str and last_check_utc_str != 'Never' else None
    last_check_local_str = last_check_dt_utc.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z') if last_check_dt_utc else "Never"

    # --- HTML Structure using Tailwind ---
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimplePractice Status Snitch ✨</title>
    <script src="https://cdn.tailwindcss.com"></script> <link rel="preconnect" href="https://rsms.me/">
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
            <div class="flex items-center justify-between mb-4 flex-wrap"> <h2 class="text-xl font-medium flex items-center {info['text_color']} mb-2 sm:mb-0"> <span class="status-emoji">{info['emoji']}</span>
                    <span>How's it doing?</span> <span id="status-text" class="ml-2 font-semibold">{html.escape(info['text'])}</span>
                </h2>
                <span id="last-checked" class="text-xs text-gray-500 w-full text-right sm:w-auto">Checked: {html.escape(last_check_local_str)}</span> </div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                    <span class="text-gray-600 block text-xs mb-1">Load Speed</span>
                    <span id="response-time" class="font-semibold text-lg text-gray-800">{html.escape(response_time_str)}</span>
                </div>
                <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                    <span class="text-gray-600 block text-xs mb-1">Normal Speed</span>
                    <span id="normal-speed" class="font-semibold text-lg text-gray-800">{html.escape(normal_speed_str)}</span>
                </div>
                <div class="bg-white/60 rounded-lg p-3 text-center shadow-sm">
                    <span class="text-gray-600 block text-xs mb-1">Extra Load Time</span>
                    <span id="extra-time" class="font-semibold text-lg text-gray-800">{html.escape(extra_time_str)}</span>
                </div>
            </div>
             {f'<div class="text-xs text-center mt-3 {info["text_color"]}"><p>({html.escape(status_data.get("extra_info", ""))})</p></div>' if status in ["ERROR", "DOWN"] and status_data.get("extra_info") else ''}
        </div>

        <div class="text-center mt-6">
            <a href="{html.escape(REPO_ACTIONS_URL)}"
               target="_blank"
               rel="noopener noreferrer"
               class="inline-block bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg shadow transition duration-150 ease-in-out text-sm">
                Trigger Manual Check (via GitHub Actions)
            </a>
            <p class="text-xs text-gray-500 mt-2">(Requires repository access)</p>
        </div>

        <div class="text-center text-xs text-gray-400 mt-6">
            This page updates automatically via GitHub Actions. Last check: {html.escape(last_check_local_str)}.
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


# === MAIN CHECK LOGIC ===
# (No changes needed in perform_check, load_previous_state, or save_current_state functions)
def perform_check():
    """Performs one status check, updates state, and generates output."""
    print("-" * 30)
    print(f"Starting check at {datetime.now(timezone.utc).isoformat()}")
    prev_state = load_previous_state(STATE_FILE)
    stable_count = prev_state['stable_count']
    degraded_count = prev_state['degraded_count']
    alert_mode = prev_state['alert_mode']
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
    if current_status == "UP":
        stable_count += 1
        degraded_count = 0
    else:
        degraded_count += 1
        stable_count = 0
    new_alert_mode = alert_mode
    if not alert_mode and degraded_count >= 2:
        new_alert_mode = True
        print("Condition met to enter ALERT mode (state tracked).")
    elif alert_mode and stable_count >= 3:
        new_alert_mode = False
        print("Condition met to exit ALERT mode (state tracked).")
    current_state_data = {
        'status': current_status,
        'response_time': response_time,
        'extra_info': extra_info,
        'stable_count': stable_count,
        'degraded_count': degraded_count,
        'alert_mode': new_alert_mode,
        'last_check_timestamp_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }
    save_current_state(STATE_FILE, current_state_data)
    generate_html(OUTPUT_HTML_FILE, current_state_data)
    print(f"Finished check at {datetime.now(timezone.utc).isoformat()}")
    print("-" * 30)

# === SCRIPT EXECUTION ===
if __name__ == "__main__":
    perform_check()
