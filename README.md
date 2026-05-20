# JAY Network CLI Miner ⛏️

A lightweight Python CLI miner for **The Jay Network**.

The public release flow is intentionally simple:

1. Get a WebSocket token from the official mining website in your browser.
2. Put the token in `.env`.
3. Run the miner from your terminal.

Private browser automation is still available as an optional fallback, but manual `.env` mode is the recommended mode for public/shared usage.

## Features

- Connects to the JAY mining pool over WebSocket
- Manual token mode via `.env` or `--token`
- Wallet balance lookup via the JAY LCD API
- Reconnect handling and periodic status output
- Optional private Camoufox token refresh mode

## Requirements

- Python 3.10+
- A JAY wallet address (`yjay...`)
- A browser token copied from `https://mining.thejaynetwork.com`

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Quick Start

1. Clone/install dependencies, then copy the environment template:

```bash
cp .env.example .env
```

2. Edit `.env` and add your token:

```bash
JAY_MINING_TOKEN=your_ws_token_here
```

3. Start mining:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz
```

## Usage

```bash
# Show help
python3 jay-miner.py --help

# Show version
python3 jay-miner.py --version

# Show wallet balance only
python3 jay-miner.py --wallet yjay1abc...xyz --info

# Start mining with default 4 threads
python3 jay-miner.py --wallet yjay1abc...xyz

# Use more threads
python3 jay-miner.py --wallet yjay1abc...xyz --threads 8

# Verbose logs
python3 jay-miner.py --wallet yjay1abc...xyz --verbose

# Optional direct token override; .env is preferred
python3 jay-miner.py --wallet yjay1abc...xyz --token your_ws_token_here
```

## How to Get the Token Manually

1. Open `https://mining.thejaynetwork.com` in Chrome, Firefox, or another modern browser.
2. Complete any site verification/checkpoint if it appears.
3. Wait until the `JAY Mining` page fully loads.
4. Open DevTools → **Network**.
5. Refresh the page.
6. Find the `POST /api/ws-token` request.
7. Open the request and copy the `token` value from the JSON response.
8. Paste it into `.env`:

```bash
JAY_MINING_TOKEN=your_ws_token_here
```

The token is used to connect to `wss://api-pool.winnode.xyz`.

## Token Modes

### Public/manual mode recommended

Manual mode is used when one of these is set:

- `JAY_MINING_TOKEN` in `.env` or your shell environment
- `JAY_WS_TOKEN` in `.env` or your shell environment
- `JAY_TOKEN` in `.env` or your shell environment
- `--token your_ws_token_here`

`--token` overrides `.env`, but `.env` is preferred because it avoids putting tokens in shell history.

### Private/auto mode optional

If no manual token is found, the miner falls back to the Camoufox browser flow and tries to refresh tokens automatically.

This mode is intended for private/local use only. It requires extra dependencies and may need Linux display tooling such as Xvfb:

```bash
pip install camoufox
# Debian/Ubuntu, if needed:
sudo apt install xvfb
```

## Configuration

Supported environment variables:

- `JAY_MINING_TOKEN`: WebSocket token copied from `/api/ws-token`
- `JAY_WS_TOKEN`: alternate token variable name
- `JAY_TOKEN`: alternate token variable name

`.env` is loaded from both:

- the script directory
- the current working directory

## Network Endpoints

- Mining site: `https://mining.thejaynetwork.com`
- Pool WebSocket: `wss://api-pool.winnode.xyz`
- Pool API: `https://api-pool.winnode.xyz`
- Chain LCD: `https://api-jayn.winnode.xyz`
- RPC: `https://rpc-jayn.winnode.xyz`

## Chain Info

- Chain ID: `thejaynetwork`
- Address prefix: `yjay`
- Denom: `ujay` (`1 JAY = 1,000,000 ujay`)
- Coin type: `118`

## Notes

- Tokens can expire periodically; update `.env` if the pool rejects your token.
- The CLI automatically reconnects on connection drops.
- Manual mode does not require Camoufox or Xvfb.
- Do not commit `.env` or share your token publicly.

## Disclaimer

This is an unofficial community CLI client. Use it at your own risk and follow The Jay Network's current rules, rate limits, and terms.

## License

MIT — see [LICENSE](LICENSE).
