# Changelog

All notable changes to this project are documented here.

## 1.1.0 - 2026-05-20

### Added

- Optional `--jay-wallet-browser` flag.
- Optional `JAY_WALLET_BROWSER=1` environment config.
- `start_mining` can now send `isJayWalletBrowser=true` for users running with an eligible official JAY Wallet browser session/token.

## 1.0.0 - 2026-05-20

### Added

- Public/manual token flow via `.env`.
- Optional `--token` override for quick testing.
- Optional private Camoufox auto-refresh fallback when no manual token is configured.
- `requirements.txt` for predictable dependency installation.
- MIT license.
- `--version` CLI flag.

### Changed

- Removed runtime dependency auto-install behavior.
- Updated README for public release usage and manual token setup.
- Clarified token handling and private automation boundaries.
