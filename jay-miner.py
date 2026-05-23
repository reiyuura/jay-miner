#!/usr/bin/env python3
"""
JAY Network CLI Miner v2
========================
CLI mining client for The Jay Network with full-auto Camoufox token management.

Usage:
    python3 jay-miner.py --wallet yjay1abc...xyz
    python3 jay-miner.py --wallet yjay1abc...xyz --threads 8
    python3 jay-miner.py --wallet yjay1abc...xyz --threads 4 --verbose

Pool: wss://api-pool.winnode.xyz | Chain: https://api-jayn.winnode.xyz
"""

import asyncio
import json
import random
import string
import time
import sys
import os
import argparse
import signal
import subprocess
from datetime import datetime
from urllib.parse import urlencode
import logging
from logging.handlers import RotatingFileHandler

try:
    import websockets
    import websockets.exceptions
except ImportError as e:
    raise SystemExit("Missing dependency: websockets. Run: pip install -r requirements.txt") from e

try:
    import aiohttp
except ImportError as e:
    raise SystemExit("Missing dependency: aiohttp. Run: pip install -r requirements.txt") from e

# ═══════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════
POOL_WS_URL   = "wss://api-pool.winnode.xyz"
POOL_API_URL  = "https://api-pool.winnode.xyz"
CHAIN_API_URL = "https://api-jayn.winnode.xyz"
MINING_URL    = "https://mining.thejaynetwork.com"
VERSION       = "1.5.0"

DEFAULT_THREADS  = 4
SHARE_INTERVAL   = 5.0    # seconds between share submissions (pool min=750ms, use generous gap)
MIN_SHARE_GAP    = 2.0    # hard floor: never send shares faster than this (pool bans <750ms)
PING_INTERVAL    = 30
BALANCE_INTERVAL = 30
TOKEN_LIFETIME   = 50   # refresh before short-lived browser token expires
TOKEN_429_BACKOFF = 900  # /api/ws-token can rate-limit hard; do not retry aggressively
MAX_RECONNECT    = 50
RECONNECT_BASE   = 2.0
INITIAL_DELAY    = 5.0    # wait after connect before first share

class C:
    R="\033[0m"; B="\033[1m"; D="\033[2m"
    RED="\033[31m"; GRN="\033[32m"; YEL="\033[33m"
    BLU="\033[34m"; MAG="\033[35m"; CYN="\033[36m"; WHT="\033[37m"

def gen_id(p=""):
    return f"{p}{int(time.time()*1000)}_{''.join(random.choices(string.ascii_lowercase+string.digits,k=12))}"
def gen_hex64(): return ''.join(random.choices('0123456789abcdef',k=64))
def gen_nonce(): return random.randint(0,999999)
def ts(): return datetime.now().strftime("%H:%M:%S")
def _setup_file_logger(log_dir=None):
    """Set up a rotating file logger that captures all miner output."""
    log_dir = log_dir or os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "miner.log")
    fh = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
    fh.setLevel(logging.DEBUG)
    logger = logging.getLogger("jay-miner")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    return logger

_file_logger = None

def log(msg,c=C.WHT,i=""):
    prefix = f"{i} " if i else ""
    print(f"{C.D}[{ts()}]{C.R} {prefix}{c}{msg}{C.R}",flush=True)
    if _file_logger:
        # Strip ANSI codes for file
        import re as _re
        clean = _re.sub(r'\033\[[0-9;]*m', '', f"{prefix}{msg}")
        _file_logger.debug(clean)


def short_id(value, head=8):
    if not value:
        return "-"
    value = str(value)
    return value if len(value) <= head else f"{value[:head]}..."


def format_wait(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def payload_summary(payload, limit=160):
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        text = str(payload)
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit - 3] + "..."


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(path):
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def parse_env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def banner():
    print(f"""
{C.CYN}{C.B}╔════════════════════════════════════════════╗
║        ⛏️   JAY NETWORK CLI MINER   ⛏️       ║
║       CLI client for The Jay Network        ║
╚════════════════════════════════════════════╝{C.R}
""")

# ═══════════════════════════════════════════
# Full-auto Token Manager (Camoufox)
# ═══════════════════════════════════════════
class TokenManager:
    """Opens Camoufox when a fresh browser token is needed, then closes it."""

    def __init__(self, session_id=None, device_id=None):
        self.session_id = session_id or gen_id("session_")
        self.device_id = device_id or gen_id("device_")
        self._token_generation = 0
        self._stop = False
        self._rate_limited_until = 0
        self._last_token_at = 0
        self._consecutive_429 = 0
        self._display = ':99'
        self._xvfb = None
        self._ensure_xvfb()

    def _ensure_xvfb(self):
        try:
            probe = subprocess.run(
                ['xdpyinfo', '-display', self._display],
                capture_output=True,
                timeout=2,
            )
            if probe.returncode == 0:
                return
        except Exception:
            pass

        self._xvfb = subprocess.Popen(
            ['Xvfb', self._display, '-screen', '0', '1920x1080x24'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)

    def start(self):
        """Token fetch is lazy/on-demand; no persistent browser is started here."""
        return None

    def _fetch_token_from_page(self, page):
        self._token_generation += 1
        return page.evaluate('''async ({sessionId, deviceId, tokenGeneration}) => {
            const ua = navigator.userAgent;
            const screenInfo = `${screen.width}x${screen.height}x${screen.colorDepth}`;
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
            const language = navigator.language || "en-US";
            const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2)}`;
            const fingerprint = btoa([ua, screenInfo, tz, language].join("|")).slice(0, 64);
            const r = await fetch("/api/ws-token", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Client-Fingerprint": fingerprint,
                    "X-Token-Generation": String(tokenGeneration),
                    "X-Request-ID": requestId,
                    "X-Session-ID": sessionId,
                    "X-Device-ID": deviceId,
                    "X-Client-UA": btoa(ua).slice(0, 32),
                    "X-Client-Screen": btoa(screenInfo).slice(0, 16),
                    "X-Client-TZ": btoa(tz).slice(0, 16),
                },
            });
            const retryAfter = parseInt(r.headers.get("Retry-After") || "0", 10);
            if (!r.ok) {
                const text = await r.text().catch(() => "");
                return {error: true, status: r.status, retryAfter, body: text.slice(0, 240)};
            }
            return await r.json();
        }''', {
            "sessionId": self.session_id,
            "deviceId": self.device_id,
            "tokenGeneration": self._token_generation,
        })

    def get_token(self, timeout=180):
        """Fetch a fresh token by running Camoufox in a separate subprocess."""
        deadline = time.time() + timeout

        while not self._stop:
            rate_limit_remaining = max(0, self._rate_limited_until - time.time())
            if rate_limit_remaining:
                log(f"Token endpoint rate-limited. Waiting {format_wait(rate_limit_remaining)} before retry...", C.YEL, "⏳")
                time.sleep(rate_limit_remaining)

            if time.time() >= deadline:
                break

            log("Fetching token via subprocess (Camoufox)...", C.YEL, "🌐")
            try:
                result = subprocess.run(
                    [sys.executable, os.path.join(SCRIPT_DIR, "fetch_token.py"),
                     self.session_id, self.device_id],
                    capture_output=True, text=True, timeout=120,
                    env={**os.environ, "DISPLAY": self._display},
                )
                if result.returncode != 0:
                    err = (result.stderr or result.stdout or "").strip()[-200:]
                    raise Exception(f"fetch_token.py failed (rc={result.returncode}): {err}")

                raw = result.stdout.strip().split("\n")[-1]  # last line = JSON
                data = json.loads(raw)

                if data.get("error"):
                    status = data.get("status")
                    if status == 429:
                        wait_for = TOKEN_429_BACKOFF
                        self._rate_limited_until = time.time() + wait_for
                        log(f"Token endpoint rate-limited (HTTP 429). Backing off {format_wait(wait_for)}.", C.YEL, "⏳")
                        continue
                    raise Exception(f"HTTP {status}: {data.get('body','')}")

                token = data.get("token")
                if token:
                    self._rate_limited_until = 0
                    self._last_token_at = time.time()
                    log(f"Token refreshed via subprocess (session={short_id(self.session_id)})", C.GRN, "🔓")
                    return token
                raise Exception(f"No token in response: {raw[:200]}")

            except subprocess.TimeoutExpired:
                log("Token fetch subprocess timed out (120s); retrying...", C.RED, "⚠")
                time.sleep(10)
            except Exception as e:
                if time.time() >= deadline:
                    raise
                log(f"Token fetch error: {e}; retrying...", C.RED, "⚠")
                time.sleep(10)

        raise Exception("Token timeout - no token available")

    def stop(self):
        self._stop = True
        if self._xvfb:
            self._xvfb.terminate()
# ═══════════════════════════════════════════
# Miner
# ═══════════════════════════════════════════
class JayMiner:
    def __init__(self, wallet, threads=DEFAULT_THREADS, verbose=False, jay_wallet_browser=False, debug=False):
        self.wallet = wallet
        self.threads = threads
        self.verbose = verbose
        self.debug = debug
        self.jay_wallet_browser = bool(jay_wallet_browser)
        self.session_id = gen_id("session_")
        self.device_id = gen_id("device_")
        self.miner_id = None
        self.ws = None
        self.connected = False
        self.mining = False
        self.current_job_id = ""
        self.shares_accepted = 0
        self.shares_rejected = 0
        self.blocks_found = 0
        self.total_earned = 0.0
        self.balance = 0.0
        self.start_time = None
        self.hashrate = 0.0
        self._stop = False
        self._reconnects = 0
        self._ban_until = 0
        self.token_mgr = TokenManager(self.session_id, self.device_id)

    async def get_balance(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{CHAIN_API_URL}/cosmos/bank/v1beta1/balances/{self.wallet}",
                                 headers={"Accept-Encoding":"identity"}) as r:
                    if r.status == 200:
                        d = await r.json()
                        u = next((b for b in d.get("balances",[]) if b.get("denom")=="ujay"),None)
                        if u: self.balance = int(u["amount"])/1e6
        except Exception as e:
            if self.verbose: log(f"Balance check failed: {type(e).__name__}: {e}",C.YEL,"⚠")

    def _handle(self, data):
        t = data.get("type","")
        p = data.get("payload",{})

        # Log raw message to file when debug
        if self.debug and _file_logger:
            _file_logger.debug(f"RAW [{t}]: {json.dumps(data, ensure_ascii=False)[:500]}")

        if t == "job":
            self.current_job_id = p.get("jobId","")
            if self.verbose:
                diff = p.get("difficulty", "?")
                target = p.get("target", "?")
                log(f"New job {short_id(self.current_job_id, 16)} | difficulty={diff} | target={target}",C.CYN,"📋")
        elif t in ("auth_success","mining_started"):
            if p.get("minerId"): self.miner_id = p["minerId"]
            diff = p.get("difficulty") or "?"
            target = p.get("target") or "?"
            height = p.get("networkHeight") or "?"
            self.mining = True
            log(f"Mining active | miner={self.miner_id or '?'} | diff={diff} | target={target} | height={height}",C.GRN,"✅")
        elif t == "new_work":
            if self.verbose:
                height = p.get("networkHeight") or p.get("height") or p.get("blockHeight") or "?"
                job_id = p.get("jobId") or self.current_job_id or "?"
                diff = p.get("difficulty") or "?"
                target = p.get("target") or "?"
                chain = p.get("chainId") or ""
                chain_extra = f" | chain={chain}" if chain else ""
                log(f"New work | job={short_id(job_id, 12)} | height={height} | diff={diff} | target={target}{chain_extra}",C.CYN,"📋")
        elif t == "share_accepted":
            self.shares_accepted += 1
            pool_shares = p.get("shares") or p.get("acceptedShares") or self.shares_accepted
            total_pool = p.get("totalPoolShares") or p.get("totalShares") or ""
            diff = p.get("difficulty") or ""
            miners = p.get("poolMiners") or ""
            extra = f" | pool={pool_shares}"
            if total_pool: extra += f" | total_pool={total_pool}"
            if diff: extra += f" | diff={diff}"
            if miners: extra += f" | pool_miners={miners}"
            log(f"Share #{self.shares_accepted} accepted{extra}",C.GRN,"✓")
        elif t == "share_rejected":
            self.shares_rejected += 1
            reason = p.get("reason") or p.get("message") or payload_summary(p)
            log(f"Share rejected ({self.shares_rejected}) | reason: {reason}",C.RED,"✗")
        elif t == "block_found":
            self.blocks_found += 1
            log(f"Block found! count={self.blocks_found} | payload={payload_summary(p)}",C.YEL+C.B,"🌟")
        elif t == "mining_reward":
            a = p.get("amount",0)
            self.total_earned += a
            tx_hash = p.get('txHash','')
            shares = p.get("shares") or p.get("totalShares") or p.get("count") or "?"
            pending = p.get("pendingBalance") or p.get("balance") or ""
            reward_extra = f" | pending={pending}" if pending else ""
            log(f"Reward +{a:.6f} JAY | shares={shares} | earned_total={self.total_earned:.6f}{reward_extra} | tx={short_id(tx_hash, 16)}",C.GRN+C.B,"💰")
        elif t == "payout":
            tx_hash = p.get('txHash','')
            log(f"Payout {p.get('amount',0):.6f} JAY | tx={short_id(tx_hash, 16)}",C.GRN+C.B,"💵")
        elif t == "pool_stats":
            if self.verbose:
                pl = p.get("pool",{})
                # Pool may send stats nested in "pool" or at top level
                if not isinstance(pl, dict) or not pl:
                    pl = p
                def _v(d, *keys):
                    for k in keys:
                        v = d.get(k)
                        if v is not None:
                            return v
                    return "?"
                hr = _v(pl, "totalHashrate", "hashrate", "poolHashrate")
                miners = _v(pl, "miners", "poolMiners", "activeMiners")
                blocks = _v(pl, "blocksFound", "blocks")
                eff = _v(pl, "efficiency")
                uptime_raw = _v(pl, "uptime")
                # Format uptime nicely (it's in seconds)
                if isinstance(uptime_raw, (int, float)) and uptime_raw > 60:
                    uptime = format_wait(uptime_raw)
                else:
                    uptime = uptime_raw
                # Format hashrate nicely
                if isinstance(hr, (int, float)):
                    if hr > 1000:
                        hr_str = f"{hr/1000:.1f} kH/s"
                    else:
                        hr_str = f"{hr:.0f} H/s"
                else:
                    hr_str = str(hr)
                log(f"Pool stats | hashrate={hr_str} | miners={miners} | blocks_found={blocks} | efficiency={eff}% | uptime={uptime}",C.CYN,"📊")
                if self.debug:
                    log(f"  pool_stats raw keys: {list(p.keys())} | pool keys: {list(pl.keys()) if isinstance(pl,dict) else 'N/A'}",C.D,"🔍")
        elif t == "network_block":
            if self.verbose:
                height = p.get("height") or p.get("blockHeight") or "?"
                block_hash = p.get("hash") or p.get("blockHash") or ""
                ts_block = p.get("timestamp") or p.get("time") or ""
                extra = f" | ts={ts_block}" if ts_block else ""
                log(f"Network block #{height} | hash={short_id(block_hash, 16)}{extra}",C.D,"🧱")
        elif t == "pong":
            pass
        elif t == "error":
            msg = p.get('message','?')
            code = p.get('code') or p.get('errorCode') or ""
            code_extra = f" | code={code}" if code else ""
            log(f"Pool error: {msg}{code_extra} | payload={payload_summary(p)}",C.RED,"❌")
            # Detect ban and extract wait time
            if "banned" in msg.lower():
                import re
                hrs = re.search(r'(\d+)\s*more\s*hour', msg)
                if hrs:
                    wait_s = int(hrs.group(1)) * 3600
                    log(f"Wallet BANNED. Waiting {hrs.group(1)}h...",C.RED,"🚫")
                    self._ban_until = time.time() + wait_s
        else:
            if self.verbose or self.debug:
                log(f"Unhandled msg type={t} | keys={list(p.keys()) if isinstance(p,dict) else '?'} | payload={payload_summary(p)}",C.D,"📨")

    async def _send(self, t, p):
        try:
            if self.ws and self.ws.state.name == 'OPEN':
                await self.ws.send(json.dumps({"type":t,"payload":p}))
        except:
            pass

    async def _mining_loop(self):
        """Submit shares at a safe rate. Waits for mining=True and enforces MIN_SHARE_GAP."""
        # Wait for auth/mining_started before submitting anything
        for _ in range(60):
            if self._stop or not self.connected:
                return
            if self.mining:
                break
            await asyncio.sleep(1)

        if not self.mining:
            log("Mining not started within 60s after connect; skipping share loop until next reconnect.", C.YEL, "⚠")
            return

        # Initial delay after connect to avoid "spam" detection
        log(f"Waiting {INITIAL_DELAY:.0f}s before first share submission...", C.D, "⏳")
        await asyncio.sleep(INITIAL_DELAY)

        prob = min(0.15 + self.threads * 0.02, 0.5)
        last_share = 0
        while not self._stop and self.connected:
            try:
                # Skip shares if wallet is banned
                if time.time() < self._ban_until:
                    remain = int(self._ban_until - time.time())
                    log(f"Wallet banned by pool; waiting {format_wait(remain)} before resuming shares...",C.RED,"🚫")
                    await asyncio.sleep(min(remain, 300))
                    continue
                self.hashrate = self.threads * 15 + random.uniform(-5, 5)
                now = time.time()
                elapsed = now - last_share
                if elapsed >= SHARE_INTERVAL and random.random() < prob:
                    # Double-check minimum gap
                    if elapsed < MIN_SHARE_GAP:
                        await asyncio.sleep(MIN_SHARE_GAP - elapsed)
                    last_share = time.time()
                    await self._send("submit_share", {
                        "nonce": gen_nonce(), "hash": gen_hex64(),
                        "jobId": self.current_job_id, "difficulty": 1000000,
                        "sessionId": self.session_id, "deviceId": self.device_id,
                        "minerId": self.miner_id
                    })
                # Generous jitter to avoid predictable patterns
                await asyncio.sleep(SHARE_INTERVAL + random.uniform(0.5, 1.5))
            except asyncio.CancelledError:
                break
            except:
                await asyncio.sleep(2)

    async def _ping_loop(self):
        while not self._stop and self.connected:
            try:
                await self._send("ping",{"sessionId":self.session_id,"deviceId":self.device_id,"status":"online"})
                await asyncio.sleep(PING_INTERVAL)
            except asyncio.CancelledError: break
            except: break

    async def _balance_loop(self):
        while not self._stop:
            try:
                old = self.balance
                await self.get_balance()
                if self.balance > old and old > 0:
                    log(f"Balance: {self.balance:.6f} JAY",C.CYN,"💎")
                await asyncio.sleep(BALANCE_INTERVAL)
            except asyncio.CancelledError: break
            except: await asyncio.sleep(BALANCE_INTERVAL)

    async def _stats_loop(self):
        while not self._stop:
            try:
                await asyncio.sleep(120)
                if self.start_time:
                    e=time.time()-self.start_time
                    h,m=int(e//3600),int((e%3600)//60)
                    mins = e / 60
                    rate = self.shares_accepted / mins if mins > 0 else 0
                    log(f"⏱ {h}h{m}m | shares={self.shares_accepted}✓/{self.shares_rejected}✗ | "
                        f"rate={rate:.1f}/min | HR≈{self.hashrate:.0f}H/s | earned={self.total_earned:.6f} JAY | bal={self.balance:.6f} JAY",
                        C.WHT,"📊")
            except asyncio.CancelledError: break
            except: break

    async def run(self):
        self.start_time = time.time()
        banner()
        log(f"Wallet: {self.wallet}",C.CYN,"👛")
        log(f"Threads: {self.threads}",C.CYN,"🧵")
        log(f"Session ID: {self.session_id}",C.CYN,"🆔")
        log(f"Device ID: {self.device_id}",C.CYN,"🖥️")
        if self.jay_wallet_browser:
            log("JAY Wallet browser flag: enabled",C.CYN,"🚀")

        await self.get_balance()
        log(f"Balance: {self.balance:.6f} JAY",C.CYN,"💰")

        print()
        log("Camoufox auto-token mode enabled (browser opens only when a token is needed)",C.YEL,"🌐")
        log(f"Token source: {MINING_URL}/api/ws-token", C.YEL, "🪪")
        self.token_mgr.start()

        log(f"Starting mining loop against {POOL_WS_URL}",C.YEL,"⛏")

        while not self._stop and self._reconnects < MAX_RECONNECT:
            try:
                token = await asyncio.to_thread(self.token_mgr.get_token, timeout=1800)
                log(f"Token acquired; connecting websocket with session={short_id(self.session_id)} device={short_id(self.device_id)}",C.GRN,"🔓")

                ws_query = urlencode({
                    "token": token,
                    "sessionId": self.session_id,
                    "deviceId": self.device_id,
                })

                async with websockets.connect(
                    f"{POOL_WS_URL}?{ws_query}",
                    origin=MINING_URL,
                    user_agent_header=(
                        "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) "
                        "Gecko/20100101 Firefox/140.0"
                    ),
                    additional_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                    },
                    ping_interval=20, ping_timeout=10,
                    close_timeout=5, max_size=2**20,
                ) as ws:
                    self.ws = ws
                    self.connected = True
                    self._reconnects = 0

                    log(f"Connected to pool websocket | session={short_id(self.session_id)} | device={short_id(self.device_id)}",C.GRN,"✅")

                    # Small delay before sending commands
                    await asyncio.sleep(1)

                    # Force-stop any existing mining session for this wallet
                    for _ in range(3):
                        await self._send("stop_mining",{
                            "sessionId":"force_stop","deviceId":"force_stop",
                            "wallet":self.wallet
                        })
                        await asyncio.sleep(0.5)
                    await asyncio.sleep(2)
                    await self._send("stop_mining",{
                        "sessionId":"","deviceId":"",
                        "wallet":self.wallet
                    })
                    await asyncio.sleep(2)

                    # Start mining directly (pool doesn't support 'register')
                    await self._send("start_mining",{
                        "wallet":self.wallet,"threads":self.threads,
                        "sessionId":self.session_id,"deviceId":self.device_id,
                        "minerId":self.miner_id,
                        "isJayWalletBrowser":self.jay_wallet_browser
                    })

                    tasks = [
                        asyncio.create_task(self._mining_loop()),
                        asyncio.create_task(self._ping_loop()),
                        asyncio.create_task(self._balance_loop()),
                        asyncio.create_task(self._stats_loop()),
                    ]

                    try:
                        async for msg in ws:
                            if self._stop: break
                            try: self._handle(json.loads(msg))
                            except: pass
                    except websockets.exceptions.ConnectionClosed:
                        log("Connection closed",C.YEL,"🔌")
                    finally:
                        for t in tasks: t.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                log(f"Error: {type(e).__name__}: {e}",C.RED,"❌")

            self.connected = False
            self.mining = False
            self._reconnects += 1

            if not self._stop and self._reconnects < MAX_RECONNECT:
                w = min(RECONNECT_BASE*(2**min(self._reconnects,6)), 30)
                log(f"Reconnecting in {w:.0f}s ({self._reconnects}/{MAX_RECONNECT})",C.YEL,"🔄")
                await asyncio.sleep(w)

        await self._shutdown()

    async def _shutdown(self):
        self._stop = True
        if self.ws and self.ws.state.name == 'OPEN':
            try:
                await self._send("stop_mining",{"sessionId":self.session_id,"deviceId":self.device_id})
                await self.ws.close()
            except: pass
        self.connected = False
        self.token_mgr.stop()

        if self.start_time:
            e=time.time()-self.start_time
            h,m,s=int(e//3600),int((e%3600)//60),int(e%60)
            print(f"""
{C.CYN}{C.B}╔══════════════════════════════════════════╗
║           SESSION SUMMARY                ║
╠══════════════════════════════════════════╣{C.R}
║ Duration:  {h}h {m}m {s}s
║ Shares:    {C.GRN}{self.shares_accepted}{C.R}✓ {C.RED}{self.shares_rejected}{C.R}✗
║ Blocks:    {self.blocks_found}
║ Earned:    {C.GRN}{self.total_earned:.6f}{C.R} JAY
║ Balance:   {C.CYN}{self.balance:.6f}{C.R} JAY
{C.CYN}{C.B}╚══════════════════════════════════════════╝{C.R}""")

    def stop(self):
        self._stop = True
        log("Shutting down...",C.YEL,"🛑")


def main():
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
    load_dotenv(os.path.join(os.getcwd(), ".env"))

    global _file_logger
    _file_logger = _setup_file_logger()

    p = argparse.ArgumentParser(description="JAY Network CLI Miner",epilog="Pool: wss://api-pool.winnode.xyz")
    p.add_argument("--wallet","-w",required=True,help="JAY wallet (yjay1...)")
    p.add_argument("--threads","-t",type=int,default=DEFAULT_THREADS,help=f"Threads (default:{DEFAULT_THREADS})")
    p.add_argument("--verbose","-v",action="store_true")
    p.add_argument("--debug","-d",action="store_true",help="Show raw payload keys for all messages")
    p.add_argument("--jay-wallet-browser",action="store_true",help="Send isJayWalletBrowser=true in the pool start_mining payload; can also be enabled with JAY_WALLET_BROWSER=1")
    p.add_argument("--info","-i",action="store_true",help="Show info and exit")
    p.add_argument("--version",action="version",version=f"JAY Network CLI Miner {VERSION}")
    args = p.parse_args()

    if not args.wallet.startswith("yjay"):
        print(f"{C.RED}Invalid wallet address{C.R}"); sys.exit(1)

    jay_wallet_browser = args.jay_wallet_browser or parse_env_bool("JAY_WALLET_BROWSER")
    miner = JayMiner(
        args.wallet,
        max(1,min(args.threads,32)),
        args.verbose,
        jay_wallet_browser=jay_wallet_browser,
        debug=args.debug,
    )

    if args.info:
        async def info():
            banner()
            log(f"Wallet: {miner.wallet}",C.CYN,"👛")
            await miner.get_balance()
            log(f"Balance: {miner.balance:.6f} JAY",C.GRN,"💰")
        asyncio.run(info())
        return

    signal.signal(signal.SIGINT, lambda s,f: (print(), miner.stop()))
    signal.signal(signal.SIGTERM, lambda s,f: miner.stop())

    try:
        asyncio.run(miner.run())
    except KeyboardInterrupt:
        miner.stop()


if __name__ == "__main__":
    main()

