---
title: "Prediction Market API Python Tutorial (2026): Your First Trading Script"
description: "Step-by-step Python tutorial for the Kalshi and Polymarket APIs. Build a price-monitoring script and place your first automated order with working code."
pubDate: 2026-02-22
category: "strategies"
tags: ["strategies", "api", "automation", "kalshi"]
affiliate: "kalshi"
howToSteps:
  - name: "Set up API keys and Python environment"
    text: "Install Python 3.9+, the requests library, then generate Kalshi API keys from your account settings and store them as environment variables."
  - name: "Authenticate with the Kalshi API"
    text: "Send your credentials to the login endpoint to receive a session token, then attach it as a Bearer token to all subsequent API requests."
  - name: "Fetch live market data"
    text: "Call the /markets endpoint to retrieve active contracts with current bid, ask, and volume. Filter by series ticker to focus on specific categories."
  - name: "Parse the order book"
    text: "Fetch the order book for a specific market to see liquidity at each price level. Use this to decide between limit and market orders."
  - name: "Place your first limit order"
    text: "Submit a POST request to the /portfolio/orders endpoint with the ticker, side (yes/no), price in cents, and contract count."
  - name: "Build a scheduled price checker"
    text: "Combine market fetching with a watchlist and the schedule library to monitor prices periodically and flag opportunities."
faqs:
  - question: "How do I connect to the Kalshi API with Python?"
    answer: "Use the requests library to make authenticated HTTP calls to Kalshi's REST API. You need an API key and RSA private key for authentication, then you can fetch markets, check prices, and place orders programmatically."
  - question: "Can beginners build a prediction market trading bot?"
    answer: "Yes. If you know basic Python (HTTP requests, JSON parsing, loops), you can build a simple bot that fetches market data and places orders. Start with a read-only script that monitors prices before adding order execution."
  - question: "What is the Polymarket API?"
    answer: "Polymarket's CLOB (Central Limit Order Book) API allows programmatic trading using USDC on the Polygon blockchain. It requires managing crypto wallets and signing transactions, adding complexity compared to Kalshi's traditional REST API."
---

If you have been trading prediction markets manually -- refreshing pages, eyeballing prices, clicking buy buttons -- you are leaving money on the table. The edge in prediction markets often comes from speed and consistency: checking dozens of markets every few minutes, spotting mispriced contracts before the crowd, and executing without hesitation. You cannot do that by hand. You need code.

This tutorial walks you through building a practical Python script that connects to the [Kalshi](https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) API, fetches live market data, analyzes prices, and places orders. By the end, you will have a working price-checker that runs on a schedule and a foundation you can extend into a full trading bot.

We run automated trading systems on prediction markets every day. This guide reflects the patterns and pitfalls we have encountered in production. No toy examples -- everything here is designed to actually work.

## Prerequisites

Before you start, you will need:

- **Python 3.9+** installed
- **A Kalshi account** with API access enabled
- **Basic Python knowledge** (variables, functions, HTTP requests)
- The `requests` and `schedule` libraries (`pip install requests schedule`)

## Step 1: Setting Up Your Kalshi API Keys

Kalshi provides a REST API that allows you to read market data, manage positions, and place orders programmatically. To get started:

1. Log in to your [Kalshi account](https://kalshi.com)
2. Navigate to your account settings or profile
3. Find the API section and generate an API key pair
4. You will receive an **API key** (sometimes called email) and **API secret** (your password or private key depending on the auth method)

**Security note:** Never hardcode your API credentials in your script. Use environment variables or a `.env` file.

```python
import os

KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_EMAIL = os.environ.get("KALSHI_EMAIL")
KALSHI_PASSWORD = os.environ.get("KALSHI_PASSWORD")
```

Set your environment variables before running:

```bash
export KALSHI_EMAIL="your-email@example.com"
export KALSHI_PASSWORD="your-api-password"
```

## Step 2: Authenticating with the Kalshi API

Kalshi uses token-based authentication. You log in with your credentials and receive a session token that you include in subsequent requests.

```python
import requests

def get_kalshi_token():
    """Authenticate with Kalshi and return a session token."""
    url = f"{KALSHI_API_BASE}/login"
    payload = {
        "email": KALSHI_EMAIL,
        "password": KALSHI_PASSWORD
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()

    data = response.json()
    token = data["token"]
    member_id = data["member_id"]

    print(f"Authenticated successfully. Member ID: {member_id}")
    return token

# Create a session with auth headers
def create_session():
    """Create a requests session with authentication."""
    token = get_kalshi_token()
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    return session
```

**Important:** Tokens expire. In production, you should handle token refresh -- catch 401 responses and re-authenticate automatically.

## Step 3: Fetching Market Data

Now let's pull live market data. Kalshi organizes markets into **events** (e.g., "S&P 500 range on Feb 22") and **markets** (individual contracts within that event, like "Will S&P 500 close above 6,000?").

```python
def get_markets(session, status="open", limit=100, cursor=None):
    """Fetch a list of markets from Kalshi."""
    url = f"{KALSHI_API_BASE}/markets"
    params = {
        "status": status,
        "limit": limit,
    }
    if cursor:
        params["cursor"] = cursor

    response = session.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    markets = data.get("markets", [])
    next_cursor = data.get("cursor", None)

    return markets, next_cursor


def get_market(session, ticker):
    """Fetch a single market by its ticker."""
    url = f"{KALSHI_API_BASE}/markets/{ticker}"

    response = session.get(url)
    response.raise_for_status()

    return response.json().get("market", {})
```

Let's try it out:

```python
session = create_session()

# Fetch the first batch of open markets
markets, cursor = get_markets(session, limit=10)

for market in markets:
    ticker = market["ticker"]
    title = market["title"]
    yes_bid = market.get("yes_bid", 0)
    yes_ask = market.get("yes_ask", 0)
    volume = market.get("volume", 0)

    print(f"{ticker}: {title}")
    print(f"  Yes Bid: ${yes_bid/100:.2f} | Yes Ask: ${yes_ask/100:.2f} | Volume: {volume}")
    print()
```

This gives you a snapshot of live markets with their current prices. The `yes_bid` and `yes_ask` values are in cents (integers), so divide by 100 for dollar amounts.

## Step 4: Parsing the Order Book

To understand the depth of liquidity at each price level, fetch the order book for a specific market:

```python
def get_orderbook(session, ticker):
    """Fetch the order book for a specific market."""
    url = f"{KALSHI_API_BASE}/markets/{ticker}/orderbook"

    response = session.get(url)
    response.raise_for_status()

    return response.json().get("orderbook", {})


def display_orderbook(orderbook):
    """Display the order book in a readable format."""
    yes_bids = orderbook.get("yes", [])
    no_bids = orderbook.get("no", [])

    print("YES side (bids to buy Yes):")
    for level in yes_bids:
        price = level[0]
        quantity = level[1]
        print(f"  ${price/100:.2f} - {quantity} contracts")

    print("\nNO side (bids to buy No):")
    for level in no_bids:
        price = level[0]
        quantity = level[1]
        print(f"  ${price/100:.2f} - {quantity} contracts")
```

The order book tells you where the real liquidity sits. Thin books with wide spreads mean you should use limit orders. Thick books with tight spreads are safer for market orders. Understanding [order book dynamics and pricing](/blog/understanding-event-contract-pricing-and-probability) is critical for profitable trading.

## Step 5: Placing a Limit Order

Now for the part that matters -- placing an actual order. **Start with paper trading or very small sizes until you are confident your code is correct.** A bug in order placement code can drain your account fast.

```python
def place_order(session, ticker, side, price_cents, count):
    """
    Place a limit order on Kalshi.

    Args:
        session: Authenticated requests session
        ticker: Market ticker (e.g., 'KXBTC-26FEB22-T50000')
        side: 'yes' or 'no'
        price_cents: Price in cents (1-99)
        count: Number of contracts

    Returns:
        Order response dict
    """
    url = f"{KALSHI_API_BASE}/portfolio/orders"

    payload = {
        "ticker": ticker,
        "action": "buy",
        "side": side,
        "type": "limit",
        "count": count,
        "yes_price": price_cents if side == "yes" else None,
        "no_price": price_cents if side == "no" else None,
    }

    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}

    print(f"Placing order: {side.upper()} {count}x {ticker} @ ${price_cents/100:.2f}")

    response = session.post(url, json=payload)
    response.raise_for_status()

    order = response.json().get("order", {})
    print(f"Order placed successfully. Order ID: {order.get('order_id')}")
    return order
```

**Example usage:**

```python
# Buy 10 Yes contracts at $0.45 each
order = place_order(session, "KXSPX-26FEB22-A6000", "yes", 45, 10)
```

### Canceling an Order

Always implement a cancel function. You will need it more often than you think.

```python
def cancel_order(session, order_id):
    """Cancel an open order."""
    url = f"{KALSHI_API_BASE}/portfolio/orders/{order_id}"

    response = session.delete(url)

    if response.status_code == 200:
        print(f"Order {order_id} cancelled successfully.")
    elif response.status_code == 404:
        print(f"Order {order_id} not found -- may have already filled or been cancelled.")
    else:
        response.raise_for_status()
```

## Step 6: Checking Your Positions

After placing orders, you need to know what you are holding:

```python
def get_positions(session):
    """Fetch all open positions."""
    url = f"{KALSHI_API_BASE}/portfolio/positions"

    response = session.get(url)
    response.raise_for_status()

    positions = response.json().get("market_positions", [])

    for pos in positions:
        ticker = pos.get("ticker", "")
        yes_count = pos.get("position", 0)
        avg_cost = pos.get("total_cost", 0)

        if yes_count != 0:
            print(f"{ticker}: {yes_count} contracts, cost basis: ${avg_cost/100:.2f}")

    return positions
```

## Step 7: Building a Price Checker That Runs Every 5 Minutes

Let's put it all together into a script that monitors specific markets and alerts you when prices cross a threshold:

```python
import schedule
import time
from datetime import datetime

# Markets to watch: (ticker, fair_value_cents, threshold_cents)
WATCHLIST = [
    ("KXBTC-26FEB28-T100000", 55, 8),   # Alert if price is 8+ cents from fair value
    ("KXSPX-26FEB28-A6100", 40, 10),     # Alert if price is 10+ cents from fair value
]

def check_prices(session):
    """Check prices for watchlist markets and alert on opportunities."""
    print(f"\n--- Price Check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    for ticker, fair_value, threshold in WATCHLIST:
        try:
            market = get_market(session, ticker)
            yes_bid = market.get("yes_bid", 0)
            yes_ask = market.get("yes_ask", 0)

            if yes_ask == 0 or yes_bid == 0:
                print(f"{ticker}: No active quotes")
                continue

            midpoint = (yes_bid + yes_ask) / 2
            edge = fair_value - midpoint

            title = market.get("title", ticker)
            print(f"{title}")
            print(f"  Bid: ${yes_bid/100:.2f} | Ask: ${yes_ask/100:.2f} | "
                  f"Mid: ${midpoint/100:.2f} | Your Fair: ${fair_value/100:.2f} | "
                  f"Edge: {edge:+.1f}c")

            # Alert if edge exceeds threshold
            if abs(edge) >= threshold:
                side = "YES" if edge > 0 else "NO"
                print(f"  >>> OPPORTUNITY: Buy {side} -- {abs(edge):.0f} cent edge <<<")

        except requests.exceptions.HTTPError as e:
            print(f"Error fetching {ticker}: {e}")
        except Exception as e:
            print(f"Unexpected error for {ticker}: {e}")


def run_monitor():
    """Main monitoring loop."""
    session = create_session()

    # Run immediately on start
    check_prices(session)

    # Schedule to run every 5 minutes
    schedule.every(5).minutes.do(check_prices, session)

    print("\nMonitor running. Checking every 5 minutes. Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_monitor()
```

Save this as `kalshi_monitor.py` and run it:

```bash
export KALSHI_EMAIL="your-email@example.com"
export KALSHI_PASSWORD="your-api-password"
python kalshi_monitor.py
```

The script will check your watchlist every 5 minutes and flag any markets where the current price deviates significantly from your fair value estimate.

## Error Handling in Production

The code above works for learning, but production trading scripts need more robust error handling. Here are the patterns we use:

### Retry Logic

```python
import time

def api_call_with_retry(func, *args, max_retries=3, **kwargs):
    """Retry API calls with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                wait_time = 2 ** attempt * 5
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
            elif e.response.status_code == 401:  # Token expired
                print("Token expired. Re-authenticating...")
                # Re-create session
                raise  # Let caller handle re-auth
            else:
                raise
        except requests.exceptions.ConnectionError:
            wait_time = 2 ** attempt
            print(f"Connection error. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise Exception(f"Failed after {max_retries} retries")
```

### Rate Limiting

Kalshi's API has rate limits. If you are polling many markets frequently, space out your requests:

```python
import time

def fetch_all_markets_throttled(session, tickers, delay=0.2):
    """Fetch multiple markets with a delay between requests."""
    results = {}
    for ticker in tickers:
        results[ticker] = get_market(session, ticker)
        time.sleep(delay)  # 200ms between requests
    return results
```

## Connecting to Polymarket (Brief Overview)

[Polymarket](https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup) uses a different architecture -- it is built on the Polygon blockchain, so interacting with it programmatically involves crypto libraries rather than simple REST calls. The basic setup:

```python
# Polymarket uses the CLOB (Central Limit Order Book) API
# You'll need: pip install py-clob-client

from py_clob_client.client import ClobClient

POLYMARKET_HOST = "https://clob.polymarket.com"
POLYMARKET_KEY = os.environ.get("POLYMARKET_API_KEY")
CHAIN_ID = 137  # Polygon mainnet

client = ClobClient(
    POLYMARKET_HOST,
    key=POLYMARKET_KEY,
    chain_id=CHAIN_ID
)

# Fetch markets
markets = client.get_markets()
for market in markets[:5]:
    print(f"{market.question} - {market.condition_id}")
```

Polymarket's API documentation is available on their GitHub. The [full guide to Polymarket](/blog/polymarket-guide-how-to-trade-crypto-prediction-markets) covers the platform in more detail.

## What to Build Next

This tutorial gives you the foundation. Here are practical next steps:

1. **Automated fair value models.** Replace the hardcoded fair values in the watchlist with models that pull external data (weather forecasts, financial data, polls) and calculate probabilities dynamically.

2. **Auto-execution.** When the price checker detects an opportunity above your edge threshold, have it automatically place a limit order instead of just printing an alert.

3. **Position management.** Build a loop that monitors your open positions and automatically places sell orders when your profit target is hit or when your model's fair value shifts against you.

4. **Multi-market scanning.** Instead of a static watchlist, scan all open markets on Kalshi, filter for categories you understand, and rank them by estimated edge.

5. **Logging and P&L tracking.** Log every trade, every price check, and every decision to a file or database. You cannot improve what you cannot measure.

If you are serious about building a trading system, study the [strategies that work in prediction markets](/blog/prediction-market-strategies-finding-edge-as-a-retail-trader) before writing code to automate them. Automating a bad strategy just helps you lose money faster.

## Common Pitfalls

- **Testing with real money.** Use small sizes (1-2 contracts) until your code is battle-tested. A loop that places orders instead of canceling them can drain your account in seconds.
- **Ignoring fees.** Every order costs $0.02 per contract. Your code needs to account for fees when calculating expected profit. A trade that looks profitable before fees might be a loser after them.
- **Not handling API errors.** Networks fail, tokens expire, rate limits hit. Every API call should have error handling. Silent failures are worse than loud crashes.
- **Over-trading.** It is easy to build a bot that trades constantly. It is hard to build one that only trades when there is genuine edge. Restraint is a feature, not a limitation.

## The Bottom Line

Automating your prediction market trading is the single highest-leverage thing you can do as a retail trader. The API gives you the ability to monitor more markets, react faster, and execute more consistently than any manual trader can. Start with the price checker in this guide, make sure it runs reliably, and gradually add execution logic as you gain confidence.

The code here is a starting point, not a finished product. The traders making real money in prediction markets are the ones who [build, test, and iterate](/blog/5-common-prediction-market-mistakes-to-avoid) relentlessly. Your first script will be rough. Your tenth will be profitable.
