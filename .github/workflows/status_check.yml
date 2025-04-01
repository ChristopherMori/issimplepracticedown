name: "SimplePractice Status Check"

on:
  schedule:
    # This cron runs every 5 minutes. Adjust as needed.
    - cron: "*/5 * * * *"
  # Allow manual dispatch
  workflow_dispatch:

jobs:
  check-status:
    runs-on: ubuntu-latest
    
    steps:
      - name: Check out repository
        uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: |
          pip install requests

      - name: Run the SimplePractice Status Snitch
        run: |
          python check_status.py
