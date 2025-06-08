# SimplePractice Status Snitch - GitHub Action Version (with History & EST/EDT)
# Stores history, calculates Avg Speed, updates UI with Eastern Time display.

import requests
import time
from datetime import datetime, timezone
import json
import os
import html
import pytz  # Import pytz for timezone handling
import yaml
import sqlite3
import smtplib
from email.mime.text import MIMEText

# === CONFIGURATION ===
CONFIG_FILE = os.environ.get('CONFIG_FILE', 'config.yaml')
try:
    with open(CONFIG_FILE, 'r') as f:
        _CFG = yaml.safe_load(f) or {}
except Exception:
    _CFG = {}

URLS = _CFG.get('urls', [{'url': os.environ.get('URL', 'https://account.simplepractice.com/'),
                          'expected_keyword': os.environ.get('EXPECTED_KEYWORD')}])
TIMEOUT_SECONDS = _CFG.get('timeout_seconds', int(os.environ.get('TIMEOUT_SECONDS', 15)))
SLOW_THRESHOLD = _CFG.get('slow_threshold', float(os.environ.get('SLOW_THRESHOLD', 2.0)))
STATE_FILE = _CFG.get('state_file', os.environ.get('STATE_FILE', 'status.json'))
DB_FILE = _CFG.get('db_file', os.environ.get('DB_FILE', 'status.db'))
OUTPUT_HTML_FILE = _CFG.get('output_html_file', os.environ.get('OUTPUT_HTML_FILE', 'index.html'))
CHECK_INTERVAL_MINUTES = _CFG.get('check_interval_minutes', int(os.environ.get('CHECK_INTERVAL_MINUTES', 5)))
MAX_RESPONSE_TIMES_TO_KEEP = 3
MAX_HISTORY_RECORDS = 50
TARGET_TIMEZONE = _CFG.get('timezone', os.environ.get('TARGET_TIMEZONE', 'America/New_York'))
SLACK_WEBHOOK_URL = _CFG.get('slack_webhook_url', os.environ.get('SLACK_WEBHOOK_URL'))
EMAIL_CFG = _CFG.get('email', {})

# === STATUS INFO (for display) ===
STATUS_INFO = {
    "UP": {"emoji": "✅", "text": "All Good!", "card_bg_class": "bg-green-100", "text_color": "text-green-700", "history_class": "text-green-600"},
    "SLOW": {"emoji": "🐢", "text": "A Bit Slow...", "card_bg_class": "bg-yellow-100", "text_color": "text-yellow-700", "history_class": "text-yellow-600"},
    "ERROR": {"emoji": "⚠️", "text": "Uh Oh! Error!", "card_bg_class": "bg-orange-100", "text_color": "text-orange-700", "history_class": "text-orange-600"},
    "DOWN": {"emoji": "💔", "text": "It's Down!", "card_bg_class": "bg-red-100", "text_color": "text-red-700", "history_class": "text-red-600"},
    "UNKNOWN": {"emoji": "❓", "text": "Unknown", "card_bg_class": "bg-gray-100", "text_color": "text-gray-700", "history_class": "text-gray-500"},
}

DEFAULT_STATE = {
    'status': 'UNKNOWN', 'stable_count': 0, 'degraded_count': 0, 'alert_mode': False,
    'last_check_timestamp_utc': None, 'response_time': 0, 'extra_info': '',
    'recent_response_times': [], 'history': []
}

# === HELPER FUNCTIONS ===

def load_previous_state(filename):
    """Loads state including history and recent response times."""
    state = DEFAULT_STATE.copy()
    try:
        if not os.path.exists(filename):
            print(f"State file '{filename}' not found, starting fresh.")
            return state
        with open(filename, 'r') as f:
            data = json.load(f)
        for key, default_value in DEFAULT_STATE.items():
            state[key] = data.get(key, default_value)
        if not isinstance(state.get('recent_response_times'), list):
            state['recent_response_times'] = []
        state['recent_response_times'] = state['recent_response_times'][-MAX_RESPONSE_TIMES_TO_KEEP:]
        if not isinstance(state.get('history'), list):
            state['history'] = []
        state['history'] = state['history'][-MAX_HISTORY_RECORDS:]
        print(f"Loaded previous state (History items: {len(state['history'])})")
        return state
    except Exception as e:
        print(f"State file '{filename}' not found or invalid, starting fresh. Error: {e}")
        return DEFAULT_STATE.copy()

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

def send_slack_notification(message):
    """Send a message to Slack if webhook URL configured."""
    if not SLACK_WEBHOOK_URL or not message:
        return
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=5)
        if resp.status_code != 200:
            print(f"Slack notification failed: {resp.status_code}")
    except Exception as e:
        print(f"Slack notification error: {e}")

def send_email_notification(subject, body):
    """Send an email alert using settings from config."""
    if not EMAIL_CFG.get('host') or not EMAIL_CFG.get('recipient'):
        return
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_CFG.get('username', '')
        msg['To'] = EMAIL_CFG['recipient']
        with smtplib.SMTP(EMAIL_CFG.get('host'), int(EMAIL_CFG.get('port', 587))) as smtp:
            smtp.starttls()
            if EMAIL_CFG.get('username'):
                smtp.login(EMAIL_CFG.get('username'), EMAIL_CFG.get('password', ''))
            smtp.send_message(msg)
    except Exception as e:
        print(f"Email notification error: {e}")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS history (
        url TEXT,
        timestamp TEXT,
        status TEXT,
        response_time REAL,
        extra_info TEXT
    )"""
    )
    conn.commit()
    conn.close()

def record_to_db(url, record):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO history (url, timestamp, status, response_time, extra_info) VALUES (?, ?, ?, ?, ?)",
            (url, record.get('timestamp'), record.get('status'), record.get('response_time'), record.get('extra_info')),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB insert error: {e}")

def load_all_states(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading state file '{filename}': {e}")
        return {}

def save_all_states(filename, states):
    try:
        with open(filename, 'w') as f:
            json.dump(states, f, indent=2)
    except Exception as e:
        print(f"Error saving state file '{filename}': {e}")

def generate_html(filename, states):
    """Generate a simple HTML dashboard summarizing multiple URLs."""

    rows = []
    try:
        tz = pytz.timezone(TARGET_TIMEZONE)
    except Exception:
        tz = timezone.utc

    for url, st in states.items():
        hist = st.get('history', [])
        latest = hist[-1] if hist else {}
        status = latest.get('status', 'UNKNOWN')
        info = STATUS_INFO.get(status, STATUS_INFO['UNKNOWN'])
        ts = latest.get('timestamp')
        local_ts = 'N/A'
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00')).replace(tzinfo=timezone.utc).astimezone(tz)
                local_ts = dt.strftime('%Y-%m-%d %H:%M:%S %Z')
            except Exception:
                pass
        resp = latest.get('response_time', 0)
        rows.append(f"<tr><td class='px-3 py-2'>{html.escape(url)}</td><td class='px-3 py-2'>{info['emoji']} {html.escape(status)}</td><td class='px-3 py-2'>{resp:.2f}s</td><td class='px-3 py-2'>{html.escape(local_ts)}</td></tr>")

    table_html = "\n".join(rows)
    html_content = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Status</title><link rel='stylesheet' href='https://cdn.tailwindcss.com'></head>
<body class='p-4'>
<h1 class='text-2xl font-bold mb-4'>Status Snitch</h1>
<table class='min-w-full divide-y divide-gray-200 border'>
<thead><tr><th class='px-3 py-2 text-left'>URL</th><th class='px-3 py-2 text-left'>Status</th><th class='px-3 py-2 text-left'>Load Time</th><th class='px-3 py-2 text-left'>Checked</th></tr></thead>
<tbody>{table_html}</tbody>
</table>
</body></html>"""

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Generated {filename}")
    except IOError as e:
        print(f"Error writing HTML file '{filename}': {e}")


# === MAIN CHECK LOGIC === (No changes needed from previous history version)
def perform_checks():
    """Perform checks for all configured URLs."""
    print("-" * 30)
    check_timestamp_utc = datetime.now(timezone.utc)
    print(f"Starting check at {check_timestamp_utc.isoformat()}")
    init_db()
    states = load_all_states(STATE_FILE)

    for cfg in URLS:
        url = cfg.get('url')
        expected = cfg.get('expected_keyword')
        st = states.get(url, DEFAULT_STATE.copy())
        history = st.get('history', [])
        recent_times = st.get('recent_response_times', [])
        stable_count = st.get('stable_count', 0)
        degraded_count = st.get('degraded_count', 0)
        alert_mode = st.get('alert_mode', False)

        start_time = time.time()
        current_status = 'UNKNOWN'
        response_time = 0
        extra_info = None
        try:
            resp = requests.get(url, timeout=TIMEOUT_SECONDS)
            response_time = time.time() - start_time
            status_code = resp.status_code
            if status_code == 200:
                if expected and expected not in resp.text:
                    current_status = 'ERROR'; extra_info = 'Keyword missing'
                else:
                    current_status = 'SLOW' if response_time > SLOW_THRESHOLD else 'UP'
            else:
                current_status = 'ERROR'; extra_info = f'Status code: {status_code}'
        except requests.exceptions.Timeout:
            current_status = 'DOWN'; extra_info = 'Request timed out'
        except requests.exceptions.RequestException as e:
            current_status = 'DOWN'; extra_info = f'Network error: {type(e).__name__}'
        except Exception as e:
            current_status = 'ERROR'; extra_info = f'Unexpected error: {type(e).__name__}'

        print(f"{url} -> {current_status} ({response_time:.2f}s)")

        record = {
            'timestamp': check_timestamp_utc.isoformat().replace('+00:00', 'Z'),
            'status': current_status,
            'response_time': float(f"{response_time:.3f}") if isinstance(response_time, (int, float)) else 0.0,
            'extra_info': extra_info
        }
        history.append(record)
        history = history[-MAX_HISTORY_RECORDS:]
        recent_times.append(response_time if current_status in ['UP', 'SLOW'] else 0)
        recent_times = recent_times[-MAX_RESPONSE_TIMES_TO_KEEP:]

        if current_status == 'UP':
            stable_count += 1; degraded_count = 0
        else:
            degraded_count += 1; stable_count = 0

        new_alert_mode = alert_mode
        if not alert_mode and degraded_count >= 2:
            new_alert_mode = True
        elif alert_mode and stable_count >= 3:
            new_alert_mode = False

        if current_status != st.get('status'):
            msg = f"{url} status changed to {current_status} ({response_time:.2f}s)"
            send_slack_notification(msg)
            send_email_notification('Status change', msg)
        if new_alert_mode and not alert_mode:
            send_slack_notification(f"{url} entering ALERT mode")
            send_email_notification('Alert mode', f'{url} entering ALERT mode')
        if alert_mode and not new_alert_mode:
            send_slack_notification(f"{url} alert resolved")
            send_email_notification('Alert resolved', f'{url} alert resolved')

        st.update({
            'status': current_status,
            'response_time': response_time,
            'extra_info': extra_info,
            'stable_count': stable_count,
            'degraded_count': degraded_count,
            'alert_mode': new_alert_mode,
            'last_check_timestamp_utc': record['timestamp'],
            'recent_response_times': recent_times,
            'history': history
        })

        states[url] = st
        record_to_db(url, record)

    save_all_states(STATE_FILE, states)
    generate_html(OUTPUT_HTML_FILE, states)
    print(f"Finished check processing at {datetime.now(timezone.utc).isoformat()}")
    print("-" * 30)


# === SCRIPT EXECUTION ===
if __name__ == "__main__":
    perform_checks()
