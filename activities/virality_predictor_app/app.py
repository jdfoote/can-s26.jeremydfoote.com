from flask import Flask, jsonify, request, send_from_directory
import urllib.request
import urllib.error
import json
import os
import sys

app = Flask(__name__)

BSKY_BASE = "https://bsky.social/xrpc"
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

# Load .env file if present

def load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


load_dotenv()

BSKY_HANDLE = os.environ.get("BSKY_HANDLE", "")
BSKY_APP_PASS = os.environ.get("BSKY_APP_PASS", "")
_access_token = None


class BlueskyAPIError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def login():
    global _access_token
    if not BSKY_HANDLE or not BSKY_APP_PASS:
        raise RuntimeError(
            "Bluesky credentials missing. Set BSKY_HANDLE and BSKY_APP_PASS in .env."
        )

    payload = json.dumps({
        "identifier": BSKY_HANDLE,
        "password": BSKY_APP_PASS,
    }).encode()
    req = urllib.request.Request(
        f"{BSKY_BASE}/com.atproto.server.createSession",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    _access_token = data["accessJwt"]
    print(f"  Logged in as {data['handle']}")


def should_refresh_auth(status_code, body):
    if status_code not in (400, 401):
        return False
    lowered = body.lower()
    return any(token in lowered for token in ["expiredtoken", "invalidtoken", "auth", "jwt"])


def authed_request(url, retry=True):
    global _access_token
    if not _access_token:
        login()

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {_access_token}",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if retry and should_refresh_auth(e.code, body):
            login()
            return authed_request(url, retry=False)
        raise BlueskyAPIError(e.code, body) from e


def json_response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers.update(CORS_HEADERS)
    return response


@app.route("/health")
def health():
    return json_response({"status": "ok", "handle": BSKY_HANDLE})


@app.route("/api/bsky", methods=["GET", "OPTIONS"])
def bsky_proxy():
    if request.method == "OPTIONS":
        return ("", 204, CORS_HEADERS)

    endpoint = request.args.get("endpoint", "")
    if not endpoint:
        return json_response({"error": "missing endpoint"}, 400)
    url = f"{BSKY_BASE}/{endpoint}"
    try:
        data = authed_request(url)
        return json_response(data)
    except BlueskyAPIError as e:
        return json_response({"error": f"Bluesky returned {e.status_code}", "details": e.message}, e.status_code)
    except Exception as e:
        return json_response({"error": str(e)}, 500)


@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "virality_game.html")


if __name__ == "__main__":
    print("\nLogging in to Bluesky...")
    try:
        login()
    except Exception as e:
        print(f"  ERROR: {e}\n")
        sys.exit(1)
    print("Starting server at http://localhost:5001\n")
    app.run(debug=False, port=5001)
