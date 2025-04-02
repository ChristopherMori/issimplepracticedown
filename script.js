// Polling intervals in milliseconds
const POLL_INTERVAL = 10000; // every 10 seconds for new data
const COUNTDOWN_INTERVAL = 1000; // update countdown every second
const CHECK_INTERVAL_MIN = 5; // checks occur every 5 minutes

// DOM elements for current status
const statusTextEl = document.getElementById('status-text');
const lastCheckedDisplayEl = document.getElementById('last-checked-display');
const lastCheckIsoEl = document.getElementById('last-check-iso');
const responseTimeEl = document.getElementById('response-time');
const avgSpeedEl = document.getElementById('avg-speed');
const statusCardEl = document.getElementById('status-card');
const historyListEl = document.getElementById('history-list');
const countdownTimerEl = document.getElementById('countdown-timer');

// Update status meta info based on status
const STATUS_META = {
  "UP": {
    emoji: "✅",
    headline: "All Good!",
    bg_class: "bg-green-100",
    text_class: "text-green-700"
  },
  "SLOW": {
    emoji: "🐢",
    headline: "A Bit Slow...",
    bg_class: "bg-yellow-100",
    text_class: "text-yellow-700"
  },
  "ERROR": {
    emoji: "⚠️",
    headline: "Uh Oh! Error!",
    bg_class: "bg-orange-100",
    text_class: "text-orange-700"
  },
  "DOWN": {
    emoji: "💔",
    headline: "It's Down!",
    bg_class: "bg-red-100",
    text_class: "text-red-700"
  },
  "UNKNOWN": {
    emoji: "❓",
    headline: "Unknown",
    bg_class: "bg-gray-100",
    text_class: "text-gray-700"
  }
};

// Fetch and update the current status from status.json
async function fetchStatus() {
  try {
    const response = await fetch('status.json');
    if (!response.ok) {
      console.error('Failed to fetch status.json');
      return;
    }
    const data = await response.json();
    updateStatusDOM(data);
  } catch (error) {
    console.error('Error fetching status:', error);
  }
}

// Update the status part of the page using the data
function updateStatusDOM(data) {
  const currentStatus = data.current_status || "UNKNOWN";
  const meta = STATUS_META[currentStatus] || STATUS_META["UNKNOWN"];

  // Update text and CSS classes for the status card
  if (statusCardEl) {
    statusCardEl.className = `rounded-lg p-6 mb-6 transition-colors duration-500 ${meta.bg_class} ${["SLOW", "ERROR", "DOWN"].includes(currentStatus) ? "animate-pulse-bg" : ""}`;
  }
  if (statusTextEl) {
    statusTextEl.textContent = meta.headline;
  }

  // Update last check times and response time info
  if (lastCheckedDisplayEl) {
    let lastCheckDisplay = "Never";
    if (data.last_check_utc) {
      const dt = new Date(data.last_check_utc);
      lastCheckDisplay = dt.toLocaleString();
    }
    lastCheckedDisplayEl.textContent = lastCheckDisplay;
  }
  if (lastCheckIsoEl) {
    lastCheckIsoEl.textContent = data.last_check_utc || "";
  }
  if (responseTimeEl) {
    const rt = data.last_response_time;
    responseTimeEl.textContent = (typeof rt === "number" && rt > 0) ? `${rt.toFixed(2)} s` : "-- s";
  }
  if (avgSpeedEl) {
    const times = data.recent_times || [];
    const validTimes = times.filter(t => typeof t === "number" && t > 0 && t < CHECK_INTERVAL_MIN * 60);
    const avg = validTimes.length > 0 ? validTimes.reduce((a, b) => a + b, 0) / validTimes.length : 0;
    avgSpeedEl.textContent = avg > 0 ? `${avg.toFixed(2)} s` : "-- s";
  }
}

// Fetch and update the history from history.json
async function fetchHistory() {
  try {
    const response = await fetch('history.json');
    if (!response.ok) {
      console.error('Failed to fetch history.json');
      return;
    }
    const data = await response.json();
    updateHistoryDOM(data);
  } catch (error) {
    console.error('Error fetching history:', error);
  }
}

function updateHistoryDOM(historyData) {
  if (!historyListEl) return;
  // Clear current history
  historyListEl.innerHTML = '';
  // Assuming historyData is an array with the newest first
  historyData.forEach(entry => {
    const li = document.createElement('li');
    const dt = new Date(entry.timestamp);
    li.textContent = `Checked at: ${dt.toLocaleString()} - Status: ${entry.status}`;
    historyListEl.appendChild(li);
  });
}

// Countdown timer for next check (based on last_check_utc and fixed interval)
function updateCountdown() {
  if (!countdownTimerEl || !lastCheckIsoEl) return;
  const iso = lastCheckIsoEl.textContent;
  if (!iso) {
    countdownTimerEl.textContent = "--:--";
    return;
  }
  const lastCheckTime = new Date(iso).getTime();
  const nextCheckTime = lastCheckTime + CHECK_INTERVAL_MIN * 60 * 1000;
  const now = Date.now();
  let diff = nextCheckTime - now;
  if (diff < 0) diff = 0;
  const mins = Math.floor(diff / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  countdownTimerEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// Poll for status and history updates periodically
function pollUpdates() {
  fetchStatus();
  fetchHistory();
}

// Start polling and countdown updates
pollUpdates();
setInterval(pollUpdates, POLL_INTERVAL);
setInterval(updateCountdown, COUNTDOWN_INTERVAL);
