# Status Snitch

A simple status checker that monitors a website, records response times, and generates a web dashboard. Additional features include optional Slack notifications, a lightweight Flask API to expose historical data, and a Dockerfile for easy deployment.

## Usage

### Running the Checker
```bash
python check_status.py
```

Set `EXPECTED_KEYWORD` to ensure the page contains specific text. To receive Slack alerts, provide `SLACK_WEBHOOK_URL`.

### API Server
```bash
python api.py
```
The API exposes `/status` returning the contents of `status.json`.

### Docker
Build and run the checker using Docker:
```bash
docker build -t status-snitch .
docker run --rm -e SLACK_WEBHOOK_URL=<hook> status-snitch
```
