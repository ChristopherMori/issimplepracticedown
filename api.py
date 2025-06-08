from flask import Flask, jsonify, request, abort
import json
import os

STATE_FILE = os.environ.get('STATE_FILE', 'status.json')
API_TOKEN = os.environ.get('API_TOKEN')
app = Flask(__name__)

@app.route('/status')
def status():
    if API_TOKEN:
        token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.args.get('token')
        if token != API_TOKEN:
            abort(401)
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
    except Exception:
        data = {}
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
