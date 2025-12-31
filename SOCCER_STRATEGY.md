# Soccer Market Making Strategy

## Overview

This strategy implements a sophisticated market-making bot for Kalshi soccer markets that:

1. **Uses Polymarket as fair value signal** - Polls Polymarket REST API for best bid/ask
2. **Combines with Kalshi microprice** - Uses Kalshi orderbook to refine fair value
3. **Dynamic fair price calculation** - Weights Polymarket vs Kalshi based on spread, depth, and match phase
4. **Intelligent quoting** - Places bid/ask around fair with spreads that account for fees and adverse selection
5. **Risk management** - Position limits, fill rate limits, drawdown circuit breakers
6. **State machine** - Per-market state tracking (INIT → WAIT_DATA → QUOTING → PAUSED → FLATTENING → DONE)
7. **Match phase awareness** - Different behavior pre-match vs in-play vs stop-quoting

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              SoccerMarketMakerStrategy                  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Polymarket   │  │ Market Data  │  │ Fair Price   │ │
│  │ Client       │→ │ Store        │→ │ Calculator   │ │
│  │ (REST poll)  │  │ (Kalshi+Poly)│  │ (Dynamic w)  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Quoting      │← │ Risk Manager  │  │ State Machine│ │
│  │ Engine       │  │ (Limits)     │  │ (Per Market) │ │
│  │ (Spread calc)│  └──────────────┘  └──────────────┘ │
│  └──────────────┘                                        │
│         ↓                                                │
│  DesiredQuotes → Engine → Gateway                       │
└──────────────────────────────────────────────────────────┘
```

## Components

### 1. **PolymarketClient** (`soccer/polymarket_client.py`)
- REST API client for Polymarket market data
- Polls best bid/ask for specified tokens
- Phase 1: REST polling only
- Phase 2: WebSocket support (future)

### 2. **MarketDataStore** (`soccer/market_data_store.py`)
- Combines Kalshi and Polymarket data into unified snapshots
- Tracks data staleness per venue
- Updates on both Kalshi WebSocket events and Polymarket polls

### 3. **FairPriceCalculator** (`soccer/fair_price.py`)
- Calculates fair price using dynamic weights:
  - Base weight: 70% Polymarket pre-match, 85% in-play
  - Adjustments based on spread (narrow = +5%, wide = -10%)
  - Stale data detection (weight = 0 if stale)
- Shock detection using EWMA of price changes
- Pauses quoting on shocks (score >= 3.0)

### 4. **QuotingEngine** (`soccer/quoting.py`)
- Calculates bid/ask prices around fair:
  - Half-spread = base + adverse selection buffer + fee buffer
  - Base: 3% pre-match, 6% in-play
  - Post-only guards (don't cross the book)
- Calculates order sizes:
  - Capped by notional ($3 demo, $1 live)
  - Capped by contracts (25 demo, 10 live)
  - Capped by visible depth (25% of book)

### 5. **RiskManager** (`soccer/risk_manager.py`)
- Position limits per market ($25 demo, $10 live)
- Total notional limit ($125 demo, $50 live)
- Fill rate limiter (pauses for 120s if exceeded)
- Drawdown circuit breaker (stops trading if breached)

### 6. **State Machine** (`soccer/state_machine.py`)
- Per-market state tracking:
  - `INIT` → `WAIT_DATA` → `QUOTING` → `PAUSED` → `FLATTENING` → `DONE`
- Warmup period before quoting (5 seconds)
- Pause/resume logic based on data freshness and risk limits

### 7. **Match Phase Detection** (`soccer/match_phase.py`)
- `PREMATCH`: Before match start
- `INPLAY`: During match (until stop-quoting time)
- `STOP_QUOTING`: 10 minutes before scheduled end
- Different parameters for each phase

### 8. **Fee Model** (`soccer/fee_model.py`)
- Conservative fee estimation (10% taker fee worst case)
- Fee buffer added to spreads
- Used to ensure profitable quotes

## Configuration

See `config/markets_soccer.yaml` for configuration format.

### Market Configuration
```yaml
markets:
  - id: "market_id"
    league: EPL
    match_name: "Team A vs Team B"
    start_time_utc: "2025-01-15T20:00:00Z"
    scheduled_end_time_utc: "2025-01-15T21:45:00Z"
    kalshi:
      env: demo
      ticker: "KXSOCCER0125D21"
    polymarket:
      market_slug: "market-slug"
      token_ids:
        home: "0x1234..."
    settlement_equivalence:
      rules_hash: "abc123..."
```

### Strategy Parameters
All parameters are configurable in the `params` section:
- Fair price weights
- Spread parameters
- Risk limits
- Polling intervals
- Match phase timing

## Usage

### 1. Configure Markets
Edit `config/markets_soccer.yaml` with actual market data:
- Kalshi tickers
- Polymarket slugs and token IDs
- Settlement rules hash (SHA256 of normalized text)

### 2. Set Environment Variables
```bash
export KALSHI_KEY_ID="your-key-id"
export KALSHI_PRIVATE_KEY_PATH="/path/to/key.key"
export KALSHI_ENV="demo"  # or "prod"
```

### 3. Run Strategy
```bash
python -m kalshi_trader.cli run --config config/markets_soccer.yaml
```

## Data Flow

### Market Update Flow
1. **Kalshi WebSocket** → Market listener → Engine → Strategy `on_market_event()`
2. **Polymarket REST** → Background polling → Data store update
3. Strategy combines both → Calculates fair price → Generates quotes
4. Engine compares desired vs live → Cancels/replaces as needed

### State Transitions
- `INIT` → `WAIT_DATA`: On start
- `WAIT_DATA` → `QUOTING`: When both venues have fresh data + warmup complete
- `QUOTING` → `PAUSED`: On stale data, shock, or risk limit
- `PAUSED` → `QUOTING`: When data fresh and cooldown expired
- Any → `DONE`: When match phase = STOP_QUOTING

## Risk Controls

1. **Position Limits**: Max $25 per market (demo)
2. **Total Notional**: Max $125 across all markets (demo)
3. **Fill Rate**: Max $20/minute per market (demo), pauses 120s if exceeded
4. **Drawdown**: Max $50 drawdown (demo), stops trading if breached
5. **Data Staleness**: Pauses if data stale (10s pre-match, 3s in-play)
6. **Shock Detection**: Pauses 10s on price shocks

## Match Phase Behavior

### PREMATCH
- Polymarket weight: 70%
- Half-spread: 3%
- Polling: Every 2 seconds
- Stale threshold: 10 seconds

### INPLAY
- Polymarket weight: 85%
- Half-spread: 6%
- Polling: Every 500ms
- Stale threshold: 3 seconds

### STOP_QUOTING
- No new quotes
- Cancel all resting orders
- Optionally flatten positions

## Future Enhancements

1. **Polymarket WebSocket**: Replace REST polling with WebSocket for lower latency
2. **Position Access**: Expose positions to strategy for position-aware quoting
3. **Historical Data**: Track price history for better fair value
4. **Analytics**: PnL attribution, spread capture metrics
5. **Multi-order Support**: Ladder strategies with multiple orders per side
6. **Flattening Logic**: Intelligent position flattening when limits breached

## Testing

### Demo Mode
- Uses demo API endpoints
- Mock funds
- Lower risk limits
- Good for integration testing

### Production
- Live API endpoints
- Real funds
- Stricter risk limits
- Requires careful monitoring

## Notes

- **Settlement Equivalence**: Critical to validate that Kalshi and Polymarket markets settle identically
- **Token IDs**: Must match actual Polymarket token IDs for the market
- **Polling Rate**: Adjust based on Polymarket rate limits
- **Fee Model**: Conservative estimate - may need calibration based on actual fees
- **Shock Detection**: EWMA parameters may need tuning based on market volatility

## Troubleshooting

### "No Polymarket data"
- Check token IDs are correct
- Verify Polymarket API is accessible
- Check rate limits

### "Data stale"
- Increase polling frequency
- Check network connectivity
- Verify match phase timing

### "Risk limit exceeded"
- Reduce position sizes
- Check if positions need flattening
- Review risk parameters

### "Shock detected"
- Normal during fast information moves
- Strategy pauses automatically
- Resumes after cooldown

