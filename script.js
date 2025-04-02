// References the history list element (make sure your HTML includes an element with id="history-list")
const historyListEl = document.getElementById('history-list');
const historyLimit = 10; // Limit to the last 10 entries
const historyEntries = []; // Array to store historical entries
const historyJsonUrl = '/history.json'; // Path to the JSON file containing history data

async function loadHistoryFromJson() {
  try {
    const response = await fetch(historyJsonUrl);
    if (!response.ok) {
      console.error('Failed to fetch history from history.json');
      return;
    }
    const data = await response.json();
    // Use the latest entries (assuming data is ordered with newest first)
    const entries = data.slice(0, historyLimit);
    entries.forEach((entry) => {
      const localTime = new Date(entry.timestamp).toLocaleString();
      addToHistory(`Checked at: ${localTime} - Status: ${entry.status}`);
    });
  } catch (error) {
    console.error('Error loading history:', error);
  }
}

function addToHistory(entry) {
  // Add the new entry to the beginning of the history array
  historyEntries.unshift(entry);
  // Limit the history to the last historyLimit entries
  if (historyEntries.length > historyLimit) {
    historyEntries.pop();
  }
  renderHistory();
}

function renderHistory() {
  if (!historyListEl) {
    return;
  }
  // Clear the current list
  historyListEl.innerHTML = '';
  // Render each history entry
  historyEntries.forEach((entry) => {
    const li = document.createElement('li');
    li.textContent = entry;
    historyListEl.appendChild(li);
  });
}

// Load history from history.json on page load
loadHistoryFromJson();
