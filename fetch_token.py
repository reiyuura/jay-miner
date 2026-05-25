#!/usr/bin/env python3
"""
Token fetcher for JAY Mining Pool.

v3: No Camoufox needed! Just HTTP POST with proper browser-like headers.
The /api/ws-token endpoint requires Origin, Referer, User-Agent, and Sec-Fetch-* headers.
NO request body — just headers.
"""
import sys
import json
import time
import random
import string
import base64
import urllib.request
import urllib.error

MINING_URL = "https://mining.thejaynetwork.com"
TOKEN_ENDPOINT = f"{MINING_URL}/api/ws-token"


def gen_id(prefix=""):
    return f"{prefix}{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=12))}"


def gen_fingerprint(ua, screen_info, tz, language):
    raw = f"{ua}|{screen_info}|{tz}|{language}"
    return base64.b64encode(raw.encode()).decode()[:64]


def fetch_token(session_id=None, device_id=None):
    """Fetch a WS token from the mining API using proper browser-like headers.

    Returns dict with 'token', 'wsUrl', 'expiresIn' on success.
    Returns dict with 'error' on failure.
    """
    if not session_id:
        session_id = gen_id("session_")
    if not device_id:
        device_id = gen_id("device_")

    ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    screen_info = "1920x1080x24"
    tz = "Asia/Jakarta"
    language = "en-US"
    fingerprint = gen_fingerprint(ua, screen_info, tz, language)
    request_id = f"req_{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"

    headers = {
        "Content-Type": "application/json",
        "Origin": MINING_URL,
        "Referer": f"{MINING_URL}/",
        "User-Agent": ua,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Client-Fingerprint": fingerprint,
        "X-Token-Generation": "1",
        "X-Request-ID": request_id,
        "X-Session-ID": session_id,
        "X-Device-ID": device_id,
        "X-Client-UA": base64.b64encode(ua.encode()).decode()[:32],
        "X-Client-Screen": base64.b64encode(screen_info.encode()).decode()[:16],
        "X-Client-TZ": base64.b64encode(tz.encode()).decode()[:16],
    }

    req = urllib.request.Request(TOKEN_ENDPOINT, method="POST", headers=headers)
    # IMPORTANT: no body! The server rejects requests with a body.

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if "token" in data:
                return data
            return {"error": f"Unexpected response: {data}"}
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def main():
    """CLI entry point. Prints JSON result to stdout."""
    session_id = sys.argv[1] if len(sys.argv) > 1 else None
    device_id = sys.argv[2] if len(sys.argv) > 2 else None

    result = fetch_token(session_id, device_id)
    print(json.dumps(result))

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
