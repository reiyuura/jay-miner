# JAY Network CLI Miner ⛏️

Unofficial Python CLI miner for **The Jay Network**.

This project is designed around a safe public flow:

1. Open the official JAY mining site in your browser.
2. Copy your WebSocket token from `/api/ws-token`.
3. Save it in `.env`.
4. Run the miner from your terminal.

> Manual `.env` mode is recommended for public/shared usage. The browser automation mode is kept as an optional private/local fallback.

---

## Features

- WebSocket mining client for the JAY pool
- Manual token mode via `.env`, environment variables, or `--token`
- Wallet balance lookup from the JAY LCD API
- Auto reconnect and periodic mining status logs
- Configurable thread count
- Optional `isJayWalletBrowser=true` payload flag
- Optional private Camoufox-based token refresh mode

---

## Requirements

- Python **3.10+**
- A JAY wallet address, for example `yjay...`
- A browser token from `https://mining.thejaynetwork.com`

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/reiyuura/jay-miner.git
cd jay-miner
```

If you already cloned it before, update it with:

```bash
git pull
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your `.env`

```bash
cp .env.example .env
```

Edit `.env` and set your browser token:

```bash
JAY_MINING_TOKEN=your_ws_token_here
```

### 4. Start mining

```bash
python3 jay-miner.py --wallet yjay1abc...xyz
```

Use your real JAY wallet address instead of `yjay1abc...xyz`.

---

## How to Get `JAY_MINING_TOKEN`

1. Open `https://mining.thejaynetwork.com` in a normal browser.
2. Complete any verification/checkpoint if it appears.
3. Wait until the mining page loads.
4. Open browser DevTools.
5. Go to the **Network** tab.
6. Refresh the page.
7. Find the request named `POST /api/ws-token`.
8. Open the response body.
9. Copy the `token` value.
10. Paste it into `.env`:

```bash
JAY_MINING_TOKEN=your_ws_token_here
```

The token is used by the CLI to connect to:

```text
wss://api-pool.winnode.xyz
```

> Do not commit `.env` or share your token publicly.

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

Pass token directly instead of `.env`:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --token your_ws_token_here
```

Enable the optional JAY Wallet browser payload flag:

```bash
python3 jay-miner.py --wallet yjay1abc...xyz --jay-wallet-browser
```

---

## Token Modes

### Recommended: manual `.env` mode

Manual mode is used when any of these are set:

- `JAY_MINING_TOKEN`
- `JAY_WS_TOKEN`
- `JAY_TOKEN`
- `--token your_ws_token_here`

Priority order:

1. `--token`
2. `JAY_MINING_TOKEN`
3. `JAY_WS_TOKEN`
4. `JAY_TOKEN`

`.env` is preferred because it avoids putting tokens in your shell history.

### Optional: private auto mode

If no manual token is found, the miner tries to use the Camoufox browser flow to fetch/refresh tokens automatically.

This mode is intended for private/local use only and may require extra setup:

```bash
pip install camoufox
sudo apt install xvfb
```

For public usage, manual `.env` mode is simpler and more reliable.

---

## Configuration

Supported environment variables:

- `JAY_MINING_TOKEN`: primary WebSocket token variable
- `JAY_WS_TOKEN`: alternate token variable
- `JAY_TOKEN`: alternate token variable
- `JAY_WALLET_BROWSER`: set to `1`, `true`, `yes`, or `on` to send `isJayWalletBrowser=true`

`.env` is loaded from:

- the script directory
- the current working directory

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
```

### Token rejected or expired

Get a fresh token from the mining website and update `.env`.

### Site verification blocks automation

Use manual `.env` mode with a normal browser. You do not need Camoufox for manual mode.

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
- The `isJayWalletBrowser` flag only changes the mining payload; final eligibility/reward decisions are handled by the official server.
- This CLI does not guarantee rewards, multipliers, or acceptance by the pool.

---

## Disclaimer

This is an unofficial community CLI client. Use it at your own risk and follow The Jay Network's current rules, rate limits, and terms.

---

## License

MIT — see [LICENSE](LICENSE).
