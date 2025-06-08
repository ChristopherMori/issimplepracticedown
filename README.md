# Status Snitch

A status checker that can watch multiple websites, records response times, sends alerts, and generates a simple dashboard. It supports Slack and optional email alerts, stores history in a SQLite database, exposes an authenticated API and can be run via Docker.

## Usage

### Running the Checker
```bash
python check_status.py
```
Configuration is read from `config.yaml` by default. Environment variables can override settings such as `SLACK_WEBHOOK_URL` or `API_TOKEN`.

### API Server
```bash
python api.py
```
The API exposes `/status` returning the contents of `status.json`. If `API_TOKEN` is set you must provide the token via an `Authorization` header or `token` query parameter.

### Docker
Build and run the checker using Docker:
```bash
docker build -t status-snitch .
docker run --rm -e SLACK_WEBHOOK_URL=<hook> status-snitch
```
