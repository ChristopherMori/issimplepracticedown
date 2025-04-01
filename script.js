// ...existing code...
const historyListEl = document.getElementById('history-list'); // Reference the history list element
const historyLimit = 10; // Limit to the last 10 results
const history = []; // Array to store historical data
const statusJsonUrl = '/history.json'; // Path to the JSON file containing historical data

async function loadHistoryFromJson() {
  try {
    const response = await fetch(statusJsonUrl);
    if (!response.ok) {
      console.error('Failed to fetch history from status.json');
      return;
    }
    const data = await response.json();
    const entries = data.slice(0, historyLimit); // Get the last 10 entries
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
  history.unshift(entry);

  // Limit the history to the last 10 entries
  if (history.length > historyLimit) {
    history.pop();
  }

  // Update the history list in the DOM
  renderHistory();
}

function renderHistory() {
  if (!historyListEl) {
    return;
  }

  // Clear the current list
  historyListEl.innerHTML = '';

  // Add each history entry to the list
  history.forEach((entry) => {
    const li = document.createElement('li');
    li.textContent = entry;
    historyListEl.appendChild(li);
  });
}

// Load history from status.json on page load
loadHistoryFromJson();
// ...existing code...
