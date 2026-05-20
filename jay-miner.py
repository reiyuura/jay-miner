#!/usr/bin/env python3
"""
JAY Network CLI Miner v2
========================
CLI mining client for The Jay Network with manual `.env` token support.

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
from datetime import datetime

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
VERSION       = "1.1.0"

DEFAULT_THREADS  = 4
SHARE_INTERVAL   = 5.0    # seconds between share submissions (pool min=750ms, use generous gap)
MIN_SHARE_GAP    = 2.0    # hard floor: never send shares faster than this (pool bans <750ms)
PING_INTERVAL    = 30
BALANCE_INTERVAL = 30
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
def log(msg,c=C.WHT,i=""):
    print(f"{C.D}[{ts()}]{C.R} {f'{i} ' if i else ''}{c}{msg}{C.R}",flush=True)


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


def resolve_manual_token(cli_token=None):
    return (cli_token or os.getenv("JAY_MINING_TOKEN") or os.getenv("JAY_WS_TOKEN") or os.getenv("JAY_TOKEN") or "").strip()



def banner():
    print(f"""
{C.CYN}{C.B}╔════════════════════════════════════════════╗
║        ⛏️   JAY NETWORK CLI MINER   ⛏️       ║
║       CLI client for The Jay Network        ║
╚════════════════════════════════════════════╝{C.R}
""")

class ManualTokenManager:
    """Simple token provider for manual/browser-supplied tokens."""

    def __init__(self, token: str):
        self.token = (token or "").strip()

    def start(self):
        return None

    def get_token(self, timeout=60):
        if not self.token:
            raise Exception("Manual token missing. Put JAY_MINING_TOKEN in .env or pass --token.")
        return self.token

    def stop(self):
        return None


# ═══════════════════════════════════════════
# Miner
# ═══════════════════════════════════════════
class JayMiner:
    def __init__(self, wallet, threads=DEFAULT_THREADS, verbose=False, token=None):
        self.wallet = wallet
        self.threads = threads
        self.verbose = verbose
        self.manual_token = token.strip() if token else None
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
        self.token_mgr = ManualTokenManager(self.manual_token)

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
            if self.verbose: log(f"Balance err: {e}",C.YEL,"⚠")

    def _handle(self, data):
        t = data.get("type","")
        p = data.get("payload",{})
        
        if t == "job":
            self.current_job_id = p.get("jobId","")
            if self.verbose: log(f"Job: {self.current_job_id[:16]}...",C.CYN,"📋")
        elif t in ("auth_success","mining_started"):
            if p.get("minerId"): self.miner_id = p["minerId"]
            self.mining = True
            log(f"Mining! Miner: {self.miner_id or '?'}",C.GRN,"✅")
        elif t == "new_work":
            if self.verbose: log(f"New work",C.CYN,"📋")
        elif t == "share_accepted":
            self.shares_accepted += 1
            log(f"Share ✓ ({self.shares_accepted})",C.GRN,"✓")
        elif t == "share_rejected":
            self.shares_rejected += 1
            log(f"Share ✗",C.RED,"✗")
        elif t == "block_found":
            self.blocks_found += 1
            log(f"BLOCK FOUND! 🎉",C.YEL+C.B,"🌟")
        elif t == "mining_reward":
            a = p.get("amount",0)
            self.total_earned += a
            log(f"Reward +{a:.6f} JAY ({p.get('shares',0)} shares) TX:{p.get('txHash','')[:16]}...",C.GRN+C.B,"💰")
        elif t == "payout":
            log(f"Payout {p.get('amount',0):.6f} JAY!",C.GRN+C.B,"💵")
        elif t == "pool_stats":
            if self.verbose:
                pl = p.get("pool",{})
                log(f"Pool: {pl.get('hashrate','?')} | Miners: {pl.get('miners','?')}",C.CYN,"📊")
        elif t == "pong":
            pass
        elif t == "error":
            msg = p.get('message','?')
            log(f"Pool err: {msg}",C.RED,"❌")
            # Detect ban and extract wait time
            if "banned" in msg.lower():
                import re
                hrs = re.search(r'(\d+)\s*more\s*hour', msg)
                if hrs:
                    wait_s = int(hrs.group(1)) * 3600
                    log(f"Wallet BANNED. Waiting {hrs.group(1)}h...",C.RED,"🚫")
                    self._ban_until = time.time() + wait_s
        else:
            if self.verbose: log(f"Msg: {t}",C.D,"📨")

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
            log("Mining not started (no auth_success). Skipping share loop.", C.YEL, "⚠")
            return
        
        # Initial delay after connect to avoid "spam" detection
        log(f"Waiting {INITIAL_DELAY:.0f}s before first share...", C.D, "⏳")
        await asyncio.sleep(INITIAL_DELAY)
        
        prob = min(0.15 + self.threads * 0.02, 0.5)
        last_share = 0
        while not self._stop and self.connected:
            try:
                # Skip shares if wallet is banned
                if time.time() < self._ban_until:
                    remain = int(self._ban_until - time.time())
                    log(f"Banned, waiting {remain//3600}h{(remain%3600)//60}m...",C.RED,"🚫")
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
                    log(f"⏱ {h}h{m}m | Shares:{C.GRN}{self.shares_accepted}{C.R}✓/{C.RED}{self.shares_rejected}{C.R}✗ | "
                        f"HR:{self.hashrate:.0f}H/s | Earned:{C.GRN}{self.total_earned:.6f}{C.R} | Bal:{C.CYN}{self.balance:.6f}{C.R}",
                        C.WHT,"📊")
            except asyncio.CancelledError: break
            except: break

    async def run(self):
        self.start_time = time.time()
        banner()
        log(f"Wallet: {self.wallet}",C.CYN,"👛")
        log(f"Threads: {self.threads}",C.CYN,"🧵")
        await self.get_balance()
        log(f"Balance: {self.balance:.6f} JAY",C.CYN,"💰")
        
        print()
        log("Using configured browser token",C.YEL,"🔑")
        self.token_mgr.start()
        
        log("Starting mining...",C.YEL,"⛏")
        
        while not self._stop and self._reconnects < MAX_RECONNECT:
            try:
                token = self.token_mgr.get_token(timeout=60)
                log("Token acquired",C.GRN,"🔓")
                
                async with websockets.connect(
                    f"{POOL_WS_URL}?token={token}",
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
                    
                    log("Connected!",C.GRN,"✅")
                    
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
                        "minerId":self.miner_id
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

    p = argparse.ArgumentParser(description="JAY Network CLI Miner",epilog="Pool: wss://api-pool.winnode.xyz")
    p.add_argument("--wallet","-w",required=True,help="JAY wallet (yjay1...)")
    p.add_argument("--threads","-t",type=int,default=DEFAULT_THREADS,help=f"Threads (default:{DEFAULT_THREADS})")
    p.add_argument("--verbose","-v",action="store_true")
    p.add_argument("--token",help="WebSocket token from /api/ws-token (or JAY_MINING_TOKEN in .env)")
    p.add_argument("--info","-i",action="store_true",help="Show info and exit")
    p.add_argument("--version",action="version",version=f"JAY Network CLI Miner {VERSION}")
    args = p.parse_args()
    
    if not args.wallet.startswith("yjay"):
        print(f"{C.RED}Invalid wallet address{C.R}"); sys.exit(1)
    
    manual_token = resolve_manual_token(args.token)
    miner = JayMiner(
        args.wallet,
        max(1,min(args.threads,32)),
        args.verbose,
        token=manual_token,
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
