#!/usr/bin/env python3
"""Standalone token fetcher - runs Camoufox in isolation (no asyncio conflicts)."""
import sys
import os
import json
import time
import random
import string
import base64

MINING_URL = "https://mining.thejaynetwork.com"

def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else f"session_{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase+string.digits,k=12))}"
    device_id = sys.argv[2] if len(sys.argv) > 2 else f"device_{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase+string.digits,k=12))}"

    # Ensure Xvfb
    display = ":99"
    os.environ["DISPLAY"] = display
    try:
        r = os.popen(f"xdpyinfo -display {display} 2>/dev/null").read()
        if "name of display" not in r:
            os.system(f"Xvfb {display} -screen 0 1920x1024x24 &")
            time.sleep(1)
    except:
        pass

    from camoufox.sync_api import Camoufox

    with Camoufox(headless=False, humanize=True, geoip=False) as browser:
        page = browser.new_page()
        page.goto(MINING_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(25000)
        title = page.title()
        if "JAY Mining" not in title:
            page.wait_for_timeout(15000)
            title = page.title()
        if "JAY Mining" not in title:
            print(json.dumps({"error": True, "msg": f"Bad title: {title!r}"}))
            sys.exit(1)

        result = page.evaluate('''({sessionId, deviceId}) => {
            const ua = navigator.userAgent;
            const screenInfo = `${screen.width}x${screen.height}x${screen.colorDepth}`;
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
            const language = navigator.language || "en-US";
            const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2)}`;
            const fingerprint = btoa([ua, screenInfo, tz, language].join("|")).slice(0, 64);
            // These must be returned for the caller to use with fetch
            return {
                ua, screenInfo, tz, language, requestId, fingerprint,
                sessionId, deviceId
            };
        }''', {"sessionId": session_id, "deviceId": device_id})

        # Now do the fetch with all required headers
        result = page.evaluate('''async (params) => {
            const {ua, screenInfo, tz, language, requestId, fingerprint, sessionId, deviceId} = params;
            const r = await fetch("/api/ws-token", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Client-Fingerprint": fingerprint,
                    "X-Token-Generation": "1",
                    "X-Request-ID": requestId,
                    "X-Session-ID": sessionId,
                    "X-Device-ID": deviceId,
                    "X-Client-UA": btoa(ua).slice(0, 32),
                    "X-Client-Screen": btoa(screenInfo).slice(0, 16),
                    "X-Client-TZ": btoa(tz).slice(0, 16),
                },
            });
            if (!r.ok) {
                const text = await r.text().catch(() => "");
                return {error: true, status: r.status, body: text.slice(0, 240)};
            }
            return await r.json();
        }''', result)

        print(json.dumps(result))

if __name__ == "__main__":
    main()
