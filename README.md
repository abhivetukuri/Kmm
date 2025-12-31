# Soccer Market Maker

A market making bot for soccer markets on Kalshi and Polymarket.

## Features

- Discovers soccer markets from both Kalshi and Polymarket
- Automatically matches identical markets between platforms
- Generates trading configuration for matched markets
- Implements fair price calculation using both venues' data
- Manages risk limits and position controls
- Handles different match phases (pre-match, in-play, stop-quoting)

## Setup

1. Create virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
uv pip install -e .
```

3. Run market discovery:
```bash
python scripts/discover_and_match_markets.py
```

## Configuration

The system generates YAML configuration files:

- `config/markets_soccer.yaml` - Matched market definitions
- `config/params_demo.yaml` - Demo environment parameters  
- `config/params_prod.yaml` - Production environment parameters

## Environment

- Demo: Uses Kalshi demo API and mock data
- Production: Uses live Kalshi and Polymarket APIs

## Safety Features

- Position limits per market and globally
- Fill rate limiting
- Circuit breakers for losses
- Automatic stop before match end
- Settlement rule validation