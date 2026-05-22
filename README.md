# JAY Network CLI Miner ⛏️

Unofficial Python CLI miner for **The Jay Network**.

Default mode is now **full-auto**: the miner briefly opens the official mining page with Camoufox only when a fresh `/api/ws-token` is needed, closes the browser after the token is fetched, then mines through the CLI/WebSocket client.

A manual token mode is still available via `.env` or `--token` for machines where browser automation is not available.

---

## Features

- Full-auto on-demand token refresh through Camoufox browser automation
- WebSocket mining client for `wss://api-pool.winnode.xyz`
- Auto reconnect and rate-limit backoff for token refresh
- Optional watchdog script for long-running public/server usage
- Manual token fallback via `.env`, environment variables, or `--token`
- Wallet balance lookup from the JAY LCD API
- Configurable thread count
- Optional `isJayWalletBrowser=true` payload flag

---

## Requirements

- Python **3.10+**
- A JAY wallet address, for example `yjay...`
- Linux display tooling for auto mode:
  - `xvfb`
  - Camoufox browser files

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install/fetch Camoufox browser files:

```bash
python3 -m camoufox fetch
```

On Debian/Ubuntu servers, install Xvfb if it is missing:

```bash
sudo apt update
sudo apt install -y xvfb x11-utils
```

---

## Quick Start: Full Auto

### 1. Clone the repo

```bash
git clone https://github.com/reiyuura/jay-miner.git
cd jay-miner
```

If you already cloned it before:

```bash
git pull
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
python3 -m camoufox fetch
```

### 3. Start mining

```bash
python3 jay-miner.py --wallet yjay1abc...xyz
```

Replace `yjay1abc...xyz` with your real JAY wallet address.

By default, if `JAY_MINING_TOKEN` / `--token` is not set, the miner uses Camoufox full-auto mode. If a stale manual token exists in `.env`, use `--auto-token` or `JAY_AUTO_TOKEN=1` to force full-auto mode.

---

## Public Watchdog Mode

The included watchdog restarts the miner automatically if the process exits.

### 1. Create `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```bash
JAY_WALLET=yjay1abc...xyz
JAY_THREADS=4
```

Leave `JAY_MINING_TOKEN=` empty for full-auto mode. If you keep a token in `.env` but want private full-auto mode, add `JAY_AUTO_TOKEN=1`.

### 2. Start watchdog

```bash
./scripts/watchdog.sh
```

Logs are written to:

```text
logs/jay-miner-watchdog.log
```

Useful watchdog variables:

- `JAY_WALLET`: required wallet address for watchdog mode
- `JAY_THREADS`: miner threads, default `4`
- `JAY_RESTART_DELAY`: delay before restart, default `15`
- `JAY_MAX_RESTARTS`: `0` means restart forever
- `JAY_LOG_DIR`: log directory, default `logs`
- `JAY_EXTRA_ARGS`: optional extra CLI args, for example `--verbose --jay-wallet-browser`
- `JAY_AUTO_TOKEN`: set `1` to force Camoufox full-auto mode even if a manual token is present

---

## Manual Token Fallback

Manual mode is used when any token source is set:

- `--token your_ws_token_here`
- `JAY_MINING_TOKEN`
- `JAY_WS_TOKEN`
- `JAY_TOKEN`

Example `.env`:

```bash
JAY_MINING_TOKEN=your_ws_token_here
```

Then run:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz
```

### How to get the token manually

1. Open `https://mining.thejaynetwork.com` in a browser.
2. Complete any verification/checkpoint if it appears.
3. Open DevTools → **Network**.
4. Refresh the page.
5. Find `POST /api/ws-token`.
6. Copy the `token` value from the JSON response.
7. Paste it into `.env` as `JAY_MINING_TOKEN`.

Do not commit `.env` or share your token publicly.

---

## Common Commands

Show help:

```bash
python3 jay-miner.py --help
```

Show version:

```bash
python3 jay-miner.py --version
```

Check wallet balance only:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --info
```

Start mining with default threads:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz
```

Start mining with more threads:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --threads 8
```

Enable verbose logs:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --verbose
```

Pass token directly instead of auto mode:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --token your_ws_token_here
```

Send the optional JAY Wallet browser payload flag:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --jay-wallet-browser
```

---

## Configuration

`.env` is loaded from:

- the script directory
- the current working directory

Supported environment variables:

- `JAY_WALLET`: wallet for `scripts/watchdog.sh`
- `JAY_THREADS`: thread count for `scripts/watchdog.sh`
- `JAY_MINING_TOKEN`: optional manual WebSocket token
- `JAY_WS_TOKEN`: alternate token variable
- `JAY_TOKEN`: alternate token variable
- `JAY_WALLET_BROWSER`: set to `1`, `true`, `yes`, or `on` to send `isJayWalletBrowser=true`
- `JAY_RESTART_DELAY`: watchdog restart delay in seconds
- `JAY_MAX_RESTARTS`: watchdog max restarts, `0` for forever
- `JAY_LOG_DIR`: watchdog log directory
- `JAY_EXTRA_ARGS`: extra CLI args passed by the watchdog

---

## Network Endpoints

- Mining site: `https://mining.thejaynetwork.com`
- Pool WebSocket: `wss://api-pool.winnode.xyz`
- Pool API: `https://api-pool.winnode.xyz`
- Chain LCD: `https://api-jayn.winnode.xyz`
- RPC: `https://rpc-jayn.winnode.xyz`

---

## Chain Info

- Chain ID: `thejaynetwork`
- Address prefix: `yjay`
- Denom: `ujay`
- Conversion: `1 JAY = 1,000,000 ujay`
- Coin type: `118`

---

## Troubleshooting

### `Missing dependency`

Install requirements again:

```bash
pip install -r requirements.txt
python3 -m camoufox fetch
```

### `Xvfb` or display errors

Install Xvfb:

```bash
sudo apt install -y xvfb x11-utils
```

### Token endpoint rate-limited

The miner backs off automatically on HTTP 429. Do not restart aggressively; use the watchdog delay defaults.

### Too many disconnects

Try fewer threads first:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --threads 2
```

Then increase slowly if shares are accepted and the connection stays stable.

---

## Safety Notes

- Never commit `.env`.
- Never share your WebSocket token publicly.
- `isJayWalletBrowser=true` only changes the `start_mining` payload. Any reward eligibility is decided by the official server/pool.
- This CLI does not guarantee rewards, multipliers, or acceptance by the pool.

---

## Disclaimer

This is an unofficial community CLI client. Use it at your own risk and follow The Jay Network's current rules, rate limits, and terms.

---

## License

MIT — see [LICENSE](LICENSE).
