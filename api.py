from flask import Flask, jsonify
import json
import os

STATE_FILE = os.environ.get('STATE_FILE', 'status.json')
app = Flask(__name__)

@app.route('/status')
def status():
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
    except Exception:
        data = {}
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
