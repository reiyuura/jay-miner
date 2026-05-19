# JAY Network CLI Miner ⛏️

A simple CLI miner for **The Jay Network** that supports:

- **Public/manual mode**: you supply the WebSocket token in `.env`
- **Private/auto mode**: optional Camoufox browser session refreshes the token automatically

## Features

- Connects to the JAY pool over WebSocket
- Supports wallet balance checks
- Manual token mode for public release
- Optional auto token refresh for private usage
- Reconnect handling and periodic status updates

## Requirements

```bash
# Base dependencies for manual/public mode
pip install -r requirements.txt

# Optional: only needed for auto token refresh mode
pip install camoufox --break-system-packages

# Camoufox headless mode also needs Xvfb on Linux
apt install xvfb
```

## Quick Start

1. Copy the example env file:

```bash
cp .env.example .env
```

2. Edit `.env` and set your browser token:

```bash
JAY_MINING_TOKEN=your_ws_token_here
```

3. Run the miner:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz
```

## Usage

```bash
# Show wallet balance only
python3 jay-miner.py --wallet yjay1abc...xyz --info

# Start mining with default 4 threads
python3 jay-miner.py --wallet yjay1abc...xyz

# Use more threads
python3 jay-miner.py --wallet yjay1abc...xyz --threads 8

# Verbose logs
python3 jay-miner.py --wallet yjay1abc...xyz --verbose
```

## How to get the token manually

If you want to obtain the token yourself instead of using Camoufox:

1. Open `https://mining.thejaynetwork.com` in Chrome or Firefox.
2. Complete the site verification / checkpoint if it appears.
3. Wait until the `JAY Mining` page fully loads.
4. Open DevTools → **Network** and refresh the page.
5. Find the `POST /api/ws-token` request.
6. Open it and copy the `token` value from the JSON response.
7. Paste that token into `.env` as `JAY_MINING_TOKEN=...`.
8. Run the miner normally.

That token is used to connect to `wss://api-pool.winnode.xyz`.

## Private auto mode

If you want the miner to refresh the token automatically, install `camoufox` and `xvfb`, then run the script without setting `JAY_MINING_TOKEN`.

This mode is intended for private use. The public release flow is `.env`-based manual token mode.

## Environment Variables

- `JAY_MINING_TOKEN` — WebSocket token copied from `/api/ws-token`
- `JAY_WS_TOKEN` — alternate token name
- `JAY_TOKEN` — alternate token name

## Endpoints

- Pool WebSocket: `wss://api-pool.winnode.xyz`
- Pool API: `https://api-pool.winnode.xyz`
- Chain LCD: `https://api-jayn.winnode.xyz`
- Mining site: `https://mining.thejaynetwork.com`
- RPC: `https://rpc-jayn.winnode.xyz`

## Chain Info

- Chain ID: `thejaynetwork`
- Prefix: `yjay`
- Denom: `ujay` (`1 JAY = 1,000,000 ujay`)
- Coin type: `118`

## Notes

- Tokens expire periodically, so keep `.env` updated if you use manual mode
- The CLI reconnects automatically when needed
- Manual/public mode does not require Camoufox

## License

MIT
