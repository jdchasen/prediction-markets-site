---
title: "Build a Prediction Market Trading Bot (2026): Developer's Guide"
description: "Build an automated prediction market trading bot with Kalshi and Polymarket APIs. Includes Python code, system architecture, and risk management patterns."
pubDate: 2026-02-22
category: "strategies"
tags: ["strategies", "api", "automation", "kalshi"]
affiliate: "kalshi"
howToSteps:
  - name: "Set up API authentication"
    text: "Generate API key pairs from your Kalshi account settings or configure wallet signing for Polymarket's CLOB API. Store credentials securely."
  - name: "Build data feed integrations"
    text: "Connect to external data sources like the NWS weather API, forex feeds, or financial market APIs to provide inputs for your pricing model."
  - name: "Implement the strategy layer"
    text: "Write fair value calculation logic that converts data feed inputs into probability estimates for each market."
  - name: "Build the execution layer"
    text: "Create order placement functions that submit limit orders via the API, with retry logic and duplicate-position guards."
  - name: "Add risk management controls"
    text: "Set maximum position sizes per market, cap total exposure, implement convergence exit logic, and guard against unintended shorts."
  - name: "Deploy and monitor"
    text: "Run your bot on a cloud instance. Periodically reconcile your local position tracker with the exchange to prevent state drift."
faqs:
  - question: "What APIs do prediction markets offer for automated trading?"
    answer: "Kalshi provides a REST API with WebSocket support for real-time market data, order placement, and portfolio management. Polymarket offers a CLOB API for its central limit order book, though it requires interacting with smart contracts on Polygon."
  - question: "What programming language is best for prediction market bots?"
    answer: "Python is the most popular choice due to its rich ecosystem of libraries for HTTP requests, data analysis, and async programming. The key libraries are requests or httpx for API calls, and asyncio for running concurrent data feeds."
  - question: "How much does it cost to run a prediction market trading bot?"
    answer: "The infrastructure cost is minimal -- a basic VPS or cloud instance costs $5-20 per month. The real cost is the trading capital you deploy and the fees on each transaction. Most bots need at least $500-2,000 in trading capital to diversify effectively."
---

Manual trading on prediction markets works fine when you're watching one or two contracts. But the moment you want to monitor dozens of weather markets, scan hundreds of Kalshi range contracts for mispriced strikes, or react to a forex data feed in real time, you hit a wall. The human refresh-and-click loop can't compete with a script that polls an API every five seconds and executes in milliseconds. That's why every serious prediction market trader eventually ends up writing code. This guide walks through the practical reality of building automated trading systems on [Kalshi](https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) and [Polymarket](https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) -- the APIs, the architecture, the code, and the mistakes that cost real money.

## Why Automate Prediction Market Trading?

The case for automation goes beyond convenience. There are structural reasons why bots outperform manual traders in prediction markets.

### Speed and Consistency

When the National Weather Service updates its forecast and shifts Chicago's expected high by two degrees, the fair value of a dozen Kalshi weather contracts changes instantly. (We detail this exact strategy in our guide on [trading weather markets on Kalshi](/blog/how-to-trade-weather-markets-on-kalshi).) A bot monitoring the NWS API detects the shift, recalculates probabilities, and places orders within seconds. A manual trader checking the same forecast on a website might not notice for an hour -- by which time the market has already adjusted.

### Scale

Kalshi lists hundreds of contracts on any given day across weather, economics, crypto, and financial markets. No human can monitor all of them simultaneously. An automated system can scan every active market, compute a fair value for each, and flag only the ones with a tradeable edge. This is how you find the two or three mispriced contracts hiding among hundreds of fairly priced ones.

### 24/7 Operation and Discipline

Markets move overnight. Economic data drops at 8:30 AM ET. Weather forecasts update at 4 AM. An automated system doesn't sleep, doesn't get bored, and doesn't make impulsive trades because a contract "feels" cheap. It follows the rules you define, every time, without exception.

## Kalshi REST API Overview

Kalshi provides a well-documented REST API that covers everything you need for automated trading: market discovery, order management, position tracking, and account information. The API uses standard HTTPS requests with JSON payloads and requires API key authentication.

### Authentication

Kalshi uses an API key pair (key ID and private key) for authentication. You generate these from your account settings. Every request must include a signed authentication header.

```python
import requests
import time
import hashlib
import hmac

class KalshiClient:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self, key_id: str, private_key: str):
        self.key_id = key_id
        self.private_key = private_key
        self.session = requests.Session()

    def _get_auth_headers(self, method: str, path: str):
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method}{path}"
        signature = self._sign(message)
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
        }

    def get_markets(self, series_ticker: str):
        path = "/markets"
        params = {"series_ticker": series_ticker}
        headers = self._get_auth_headers("GET", path)
        resp = self.session.get(
            f"{self.BASE_URL}{path}",
            headers=headers,
            params=params
        )
        return resp.json()["markets"]
```

### Fetching Markets and Prices

The `/markets` endpoint returns active contracts with their current best bid, best ask, volume, and settlement details. You can filter by series ticker (e.g., `KXHIGHNY` for New York temperature markets) or by event ticker for a specific day.

```python
# Fetch all active weather markets for New York
markets = client.get_markets(series_ticker="KXHIGHNY")

for market in markets:
    ticker = market["ticker"]
    yes_bid = market["yes_bid"]    # best bid for Yes side
    yes_ask = market["yes_ask"]    # best ask for Yes side
    print(f"{ticker}: bid={yes_bid}c, ask={yes_ask}c")
```

### Placing Orders

Orders are submitted via POST to the `/orders` endpoint. You specify the ticker, side (yes or no), quantity, price in cents, and order type (limit or market).

```python
def place_order(self, ticker: str, side: str, price: int, count: int):
    path = "/orders"
    payload = {
        "ticker": ticker,
        "action": "buy",
        "side": side,       # "yes" or "no"
        "type": "limit",
        "yes_price": price,  # price in cents
        "count": count,
    }
    headers = self._get_auth_headers("POST", path)
    resp = self.session.post(
        f"{self.BASE_URL}{path}",
        headers=headers,
        json=payload
    )
    return resp.json()
```

## Polymarket API Overview

Polymarket operates on the Polygon blockchain using a central limit order book (CLOB). Its API is different from Kalshi's -- you interact with both a REST API for market data and order management, and the blockchain for settlement. Orders are signed using your Ethereum wallet's private key.

### Market Data

Polymarket's CLOB API provides endpoints for fetching markets, order books, and prices. Market discovery starts with the `/markets` endpoint, and order book depth is available per token.

```python
import requests

CLOB_URL = "https://clob.polymarket.com"

def get_polymarket_markets(tag: str = None):
    """Fetch active markets, optionally filtered by tag."""
    params = {"active": True}
    if tag:
        params["tag"] = tag
    resp = requests.get(f"{CLOB_URL}/markets", params=params)
    return resp.json()

def get_order_book(token_id: str):
    """Fetch the order book for a specific outcome token."""
    resp = requests.get(f"{CLOB_URL}/book", params={"token_id": token_id})
    return resp.json()
```

### Placing Orders on Polymarket

Polymarket orders require cryptographic signing with your wallet's private key. The `py-clob-client` library handles the signing and order submission. Each order specifies a token ID (representing a Yes or No outcome), price, size, and side (buy or sell).

```python
from py_clob_client.client import ClobClient

clob_client = ClobClient(
    host=CLOB_URL,
    key="your-private-key",
    chain_id=137  # Polygon mainnet
)

# Create and submit a limit order
order = clob_client.create_and_post_order(
    token_id="0xabc123...",  # outcome token ID
    price=0.45,               # price per share
    size=100,                  # number of shares
    side="BUY"
)
```

## Architecture of an Automated Trading Bot

A production trading bot isn't a single script. It's a system with distinct components that communicate through well-defined interfaces. Here's the architecture that works.

### Data Feeds

Your bot needs real-time or near-real-time data from external sources to calculate fair values. The specific feeds depend on which markets you trade:

- **Weather**: National Weather Service API, Open-Meteo, or commercial providers like Tomorrow.io. These give you forecast temperatures, uncertainty ranges, and hourly breakdowns.
- **Forex**: WebSocket feeds from providers like Twelve Data (for EUR/USD) or Yahoo Finance (for fallback and additional pairs like USD/JPY). Forex data drives pricing for Kalshi's currency range markets.
- **Financial markets**: SPX spot prices from Chainlink on-chain oracles or exchange APIs. Used for S&P 500 range contract pricing.
- **Sports**: Odds feeds from providers that aggregate lines across sportsbooks. Useful for cross-referencing Kalshi sports markets.
- **Economic calendar**: APIs that track FOMC dates, CPI releases, jobs reports, and other scheduled data drops.

### Strategy Layer

The strategy layer takes data feed inputs and calculates fair value for each market. This is where your edge lives. A weather strategy might model temperature as a normal distribution centered on the forecast with a calibrated standard deviation. A range strategy might use implied volatility from spot price feeds to price each strike bucket.

```python
from scipy.stats import norm

def calculate_fair_value(forecast_high: float, sigma: float, strike: float):
    """Calculate the probability that actual temp exceeds strike."""
    z_score = (strike - forecast_high) / sigma
    prob_above = 1 - norm.cdf(z_score)
    return prob_above
```

The strategy also decides position sizing. A fractional Kelly criterion approach works well: bet proportional to your edge, but scale it down to reduce variance.

### Execution Layer

The execution layer translates strategy signals into actual orders. It handles order placement, cancellation, and modification. Critical details here:

- **Check existing positions** before placing new orders. You don't want to double up accidentally.
- **Use limit orders**, not market orders. Market orders on thin prediction market order books will fill at terrible prices.
- **Implement retry logic** for failed API calls. Networks are unreliable. A dropped order submission should be retried, not silently ignored.

### Risk Management

Risk management isn't optional. At minimum, your bot needs:

- **Maximum position size per market.** Cap the number of contracts in any single market.
- **Maximum total exposure.** Limit the total capital deployed across all positions.
- **Convergence exit logic.** As settlement approaches and a contract is deep in the money, sell to lock in profit rather than waiting for settlement. This frees capital and avoids settlement fees.
- **Short position prevention.** If a sell order fills but the position tracker doesn't update correctly, the bot might keep selling into a short position. This is a real failure mode that can drain an account quickly. Build explicit guards against it.

## Common Pitfalls

### Ignoring Fees in Edge Calculations

A contract trading at 60 cents when your model says fair value is 64 cents looks like a 4-cent edge. After Kalshi's round-trip fees of approximately 7 cents, that trade is a loser. Always compute net expected profit after fees before executing. Many apparent edges evaporate once fees are included. This is one of the [5 costly mistakes](/blog/5-common-prediction-market-mistakes-to-avoid) that drain new trader accounts.

### Rate Limits

Both Kalshi and Polymarket enforce rate limits on their APIs. Kalshi allows approximately 10 requests per second for most endpoints. Polymarket's CLOB has similar constraints. If your bot exceeds these limits, requests will be rejected with 429 status codes.

The fix is straightforward: implement a rate limiter in your client and batch requests where possible. Fetch all markets in a single paginated call rather than hitting the API once per ticker.

```python
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()

    def wait_if_needed(self):
        now = time.time()
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            time.sleep(max(0, sleep_time))
        self.calls.append(time.time())
```

### Stale Data Leading to Phantom Edges

If your data feed lags or your bot uses cached prices, it may calculate edges that no longer exist. A weather forecast that updated 30 minutes ago might have already moved the market. Always compare the timestamp of your data against the current time, and skip trades when your data is stale.

### Not Handling Order State Correctly

The most dangerous bugs in trading bots are order state management issues. An order that shows as "pending" in your system but has already filled on the exchange will cause your position tracker to diverge from reality. When the tracker says you own 10 contracts but you actually own zero, your bot might sell 10 more contracts -- putting you into a short position. Always reconcile your local state with the exchange's state by periodically fetching your actual positions from the API.

## Key Takeaways

- **Automation gives you speed, scale, and discipline** that manual trading can't match. If you're trading more than a handful of contracts, code isn't optional -- it's the baseline.
- **Kalshi's REST API** provides clean endpoints for market discovery, order placement, and position management. Authentication uses signed API key headers.
- **Polymarket's CLOB API** offers similar functionality but requires cryptographic wallet signing for order submission. The `py-clob-client` library simplifies this.
- **A production bot has four layers**: data feeds (weather, forex, financial, sports), strategy (fair value calculation and sizing), execution (order management with retries), and risk management (position limits and exit logic).
- **Always calculate edge after fees.** Kalshi's fee structure eliminates many trades that look profitable on a gross basis. If your net expected value isn't clearly positive, skip the trade.
- **Respect rate limits** by implementing client-side throttling. Batch your API calls and avoid polling more frequently than necessary.
- **Order state management is where bots blow up.** Reconcile your local position tracker with the exchange regularly, and build explicit guards against unintended short positions.
- **Start with one market category** (weather is ideal due to clean data and fast feedback loops), prove your system works, then expand to other categories.

Building an automated prediction market trading system is a serious engineering project, but the prediction market API landscape has matured enough that the infrastructure is no longer the hard part. The hard part is the same as it has always been: finding a genuine edge in your pricing model and managing risk while you exploit it. For the strategy side of the equation, see our guide on [prediction market strategies that actually work](/blog/prediction-market-strategies-finding-edge-as-a-retail-trader).
