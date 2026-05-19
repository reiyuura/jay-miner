# JAY Network CLI Miner ⛏️

CLI mining client for **The Jay Network** blockchain (Cosmos SDK), reverse-engineered from the official web miner at `mining.thejaynetwork.com`.

## Prerequisites

```bash
# Core deps for manual mode
pip install websockets aiohttp --break-system-packages

# Optional: only needed for auto token refresh mode
pip install camoufox --break-system-packages
# Camoufox also needs Xvfb for headless rendering:
apt install xvfb
```

## Usage

```bash
# Check wallet info
python3 jay-miner.py --wallet yjay1abc...xyz --info

# Start mining (default 4 threads)
python3 jay-miner.py --wallet yjay1abc...xyz

# Custom threads
python3 jay-miner.py --wallet yjay1abc...xyz --threads 8

# Verbose mode
python3 jay-miner.py --wallet yjay1abc...xyz --threads 4 --verbose

# Manual token mode (no Camoufox)
python3 jay-miner.py --wallet yjay1abc...xyz --token <ws-token>
```

## How It Works

1. **Token Acquisition**: Uses Camoufox (anti-fingerprinting Firefox) to obtain a WebSocket authentication token from the mining site's `/api/ws-token` endpoint.

2. **WebSocket Connection**: Connects to `wss://api-pool.winnode.xyz` with the token.

3. **Mining Loop**: Sends `start_mining` with wallet address, then periodically submits shares (`submit_share`) with nonce + hash.

4. **Rewards**: The pool accepts shares and periodically distributes JAY rewards.

## Manual Browser Token Flow

If you want to do the token step yourself in a normal browser instead of letting Camoufox handle it:

1. Open `https://mining.thejaynetwork.com` in Chrome or Firefox.
2. Complete the site verification / checkpoint if it appears.
3. Wait until the `JAY Mining` page fully loads.
4. Open DevTools → **Network** and refresh the page.
5. Look for the `POST /api/ws-token` request.
6. Open that request and copy the `token` value from the JSON response.

That token is what the miner uses to connect to `wss://api-pool.winnode.xyz`. The current CLI miner fetches it automatically, but this manual flow is useful for debugging or for custom clients.

For public sharing, use `--token` mode. Keep the Camoufox auto-refresh mode for your private setup only.

## Architecture

```
┌──────────────┐     Token     ┌──────────────────┐
│  Camoufox    │ ──────────── │  mining.thejaynetwork  │
│  (Xvfb)     │              │  /api/ws-token        │
└──────┬───────┘              └──────────────────┘
       │ token
       ▼
┌──────────────┐   WebSocket   ┌──────────────────┐
│  CLI Miner   │ ──────────── │  api-pool.winnode.xyz │
│  (Python)    │              │  Mining Pool          │
└──────┬───────┘              └──────────────────┘
       │ balance query
       ▼
┌──────────────┐
│ api-jayn.winnode.xyz │
│ Chain LCD API        │
└──────────────┘
```

## Key Endpoints

- **Pool WebSocket**: `wss://api-pool.winnode.xyz`
- **Pool API**: `https://api-pool.winnode.xyz`
- **Chain LCD**: `https://api-jayn.winnode.xyz`
- **Mining Site**: `https://mining.thejaynetwork.com`
- **RPC**: `https://rpc-jayn.winnode.xyz`

## Chain Info

- **Chain ID**: `thejaynetwork`
- **Prefix**: `yjay`
- **Denom**: `ujay` (1 JAY = 1,000,000 ujay)
- **Coin Type**: 118 (BIP44)
- **Block Time**: ~5 seconds

## WebSocket Protocol

### Client → Server
- `start_mining` — Start mining with wallet + threads config
- `submit_share` — Submit a share (nonce, hash, jobId, difficulty)
- `stop_mining` — Stop mining session
- `ping` — Keepalive
- `status` — Update miner status (online/away/offline)

### Server → Client
- `job` / `new_work` — New mining job (jobId, target)
- `auth_success` / `mining_started` — Mining confirmed (minerId)
- `share_accepted` — Share accepted ✓
- `share_rejected` — Share rejected ✗
- `mining_reward` — Reward received (amount, shares, txHash)
- `block_found` — Block found!
- `payout` — Payout sent
- `pool_stats` — Pool statistics
- `pong` — Keepalive response

## Notes

- Token expires every 60 seconds; the miner auto-refreshes via persistent Camoufox session
- Camoufox is needed because `mining.thejaynetwork.com` is behind Vercel Security Checkpoint (blocks all HTTP clients and headless browsers)
- Shares are simulated (matching the web miner's behavior — not actual PoW)
- Pool fee: 1.5%
