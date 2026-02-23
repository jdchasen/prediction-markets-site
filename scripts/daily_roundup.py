#!/usr/bin/env python3
"""
Daily Market Pulse — automated daily roundup for Master Prediction Markets.

Fetches trending markets from Kalshi + Polymarket APIs, generates a
news-style roundup via Claude API, and saves the markdown article.

Usage:
  python scripts/daily_roundup.py              # generates today's article
  python scripts/daily_roundup.py --date 2026-02-23  # specific date

Environment variables:
  ANTHROPIC_API_KEY     — required for article generation
  KALSHI_API_KEY        — optional, for authenticated Kalshi market data
  KALSHI_PRIVATE_KEY    — optional, base64-encoded RSA private key PEM
"""

import base64
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests package not installed. Run: pip install requests")
    sys.exit(1)


CONTENT_DIR = Path(__file__).parent.parent / "src" / "content" / "blog"

KALSHI_REFERRAL = "https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true"
POLYMARKET_REFERRAL = "https://polymarket.us/1762"

EXISTING_ARTICLES = [
    ("/blog/what-are-prediction-markets", "What Are Prediction Markets"),
    ("/blog/kalshi-review", "Kalshi Review"),
    ("/blog/polymarket-guide-how-to-trade-crypto-prediction-markets", "Polymarket Guide"),
    ("/blog/kalshi-vs-polymarket-which-platform-should-you-use", "Kalshi vs Polymarket"),
    ("/blog/how-to-trade-weather-markets-on-kalshi", "How to Trade Weather Markets on Kalshi"),
    ("/blog/prediction-market-strategies-finding-edge-as-a-retail-trader", "Prediction Market Strategies"),
    ("/blog/understanding-event-contract-pricing-and-probability", "Understanding Event Contract Pricing"),
    ("/blog/kalshi-fees-explained", "Kalshi Fees Explained"),
    ("/blog/how-to-use-apis-for-automated-prediction-market-trading", "APIs for Automated Trading"),
    ("/blog/best-prediction-market-platforms", "Best Prediction Market Platforms"),
    ("/blog/prediction-markets-making-money", "Making Money with Prediction Markets"),
    ("/blog/kalshi-spx-trading", "Kalshi SPX Trading"),
    ("/blog/what-are-event-contracts", "What Are Event Contracts"),
    ("/blog/prediction-markets-vs-sports-betting-key-differences", "Prediction Markets vs Sports Betting"),
    ("/blog/polymarket-election-trading", "Polymarket Election Trading"),
    ("/blog/5-common-prediction-market-mistakes-to-avoid", "Common Prediction Market Mistakes"),
    ("/blog/prediction-market-api-python", "Prediction Market API Python"),
    ("/blog/kalshi-tax-reporting", "Kalshi Tax Reporting"),
    ("/blog/kalshi-withdrawal", "Kalshi Withdrawal Guide"),
    ("/blog/is-kalshi-legal", "Is Kalshi Legal"),
    ("/blog/how-to-deposit-on-polymarket", "How to Deposit on Polymarket"),
]

# ---------------------------------------------------------------------------
# Kalshi authentication
# ---------------------------------------------------------------------------

def _load_kalshi_private_key():
    """Load RSA private key from KALSHI_PRIVATE_KEY env var (base64-encoded PEM)
    or from KALSHI_PRIVATE_KEY_PATH file path."""
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return None

    # Option 1: base64-encoded PEM in env var (for GitHub Actions)
    key_b64 = os.environ.get("KALSHI_PRIVATE_KEY", "")
    if key_b64:
        pem_bytes = base64.b64decode(key_b64)
        return serialization.load_pem_private_key(pem_bytes, password=None)

    # Option 2: file path (for local development)
    key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if key_path and Path(key_path).exists():
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    return None


def _kalshi_headers(api_key: str, private_key, method: str, path: str) -> dict:
    """Build authenticated headers for Kalshi API using RSA-PSS signing."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    timestamp_ms = int(time.time() * 1000)
    message = f"{timestamp_ms}{method}{path}"
    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "Content-Type": "application/json",
        "KALSHI-ACCESS-KEY": api_key,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
    }


# ---------------------------------------------------------------------------
# Market data fetching
# ---------------------------------------------------------------------------

def fetch_kalshi_markets(limit: int = 10) -> list[dict]:
    """Fetch active markets from Kalshi API, sorted by volume.
    Requires KALSHI_API_KEY and KALSHI_PRIVATE_KEY env vars."""
    api_key = os.environ.get("KALSHI_API_KEY", "")
    private_key = _load_kalshi_private_key()

    if not api_key or not private_key:
        print("  Kalshi credentials not configured (KALSHI_API_KEY + KALSHI_PRIVATE_KEY), skipping")
        return []

    base_url = "https://trading-api.kalshi.com/trade-api/v2"
    path = "/trade-api/v2/markets"
    params = {
        "limit": 100,
        "status": "open",
    }
    try:
        headers = _kalshi_headers(api_key, private_key, "GET", path)
        resp = requests.get(f"{base_url}/markets", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        markets = data.get("markets", [])
    except Exception as e:
        print(f"  Kalshi API error: {e}")
        return []

    # Sort by volume descending, take top N
    markets.sort(key=lambda m: m.get("volume", 0) or 0, reverse=True)
    results = []
    for m in markets[:limit]:
        yes_price = m.get("yes_ask") or m.get("last_price") or 0
        no_price = m.get("no_ask") or (100 - yes_price if yes_price else 0)
        results.append({
            "platform": "Kalshi",
            "title": m.get("title", ""),
            "subtitle": m.get("subtitle", ""),
            "yes_price": yes_price,
            "no_price": no_price,
            "volume": m.get("volume", 0) or 0,
            "volume_24h": m.get("volume_24h", 0) or 0,
            "category": m.get("category", ""),
            "event_ticker": m.get("event_ticker", ""),
            "close_time": m.get("close_time", ""),
        })
    return results


def fetch_polymarket_markets(limit: int = 10) -> list[dict]:
    """Fetch active markets from Polymarket Gamma API, sorted by volume."""
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "limit": 100,
        "active": "true",
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        markets = resp.json()
        if not isinstance(markets, list):
            markets = markets.get("data", []) if isinstance(markets, dict) else []
    except Exception as e:
        print(f"  Polymarket API error: {e}")
        return []

    results = []
    for m in markets[:limit]:
        outcomes = m.get("outcomePrices", "")
        yes_price = 0
        no_price = 0
        if outcomes:
            try:
                prices = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                if len(prices) >= 2:
                    yes_price = round(float(prices[0]) * 100, 1)
                    no_price = round(float(prices[1]) * 100, 1)
                elif len(prices) == 1:
                    yes_price = round(float(prices[0]) * 100, 1)
                    no_price = round(100 - yes_price, 1)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        results.append({
            "platform": "Polymarket",
            "title": m.get("question", "") or m.get("title", ""),
            "yes_price": yes_price,
            "no_price": no_price,
            "volume": float(m.get("volume", 0) or 0),
            "volume_24h": float(m.get("volume24hr", 0) or 0),
            "category": m.get("category", "") or "",
            "end_date": m.get("endDate", ""),
        })
    return results


# ---------------------------------------------------------------------------
# Article generation
# ---------------------------------------------------------------------------

def build_market_context(kalshi: list[dict], poly: list[dict]) -> str:
    """Format market data into a text block for the Claude prompt."""
    lines = []

    if kalshi:
        lines.append("=== KALSHI TOP MARKETS (by volume) ===")
        for i, m in enumerate(kalshi, 1):
            lines.append(
                f"{i}. {m['title']}"
                + (f" — {m['subtitle']}" if m.get('subtitle') else "")
                + f"  |  Yes: {m['yes_price']}¢  No: {m['no_price']}¢"
                + f"  |  Vol: {m['volume']:,}  24h Vol: {m['volume_24h']:,}"
                + f"  |  Category: {m['category']}"
            )
        lines.append("")

    if poly:
        lines.append("=== POLYMARKET TOP MARKETS (by 24h volume) ===")
        for i, m in enumerate(poly, 1):
            vol_str = f"${m['volume']:,.0f}" if m['volume'] > 0 else "N/A"
            vol24_str = f"${m['volume_24h']:,.0f}" if m['volume_24h'] > 0 else "N/A"
            lines.append(
                f"{i}. {m['title']}"
                + f"  |  Yes: {m['yes_price']}¢  No: {m['no_price']}¢"
                + f"  |  Vol: {vol_str}  24h: {vol24_str}"
                + f"  |  Category: {m['category']}"
            )
        lines.append("")

    return "\n".join(lines)


def generate_article(
    article_date: date,
    kalshi_markets: list[dict],
    poly_markets: list[dict],
) -> tuple[str, str]:
    """Generate the daily roundup article via Claude API.

    Returns (filename, full_markdown_with_frontmatter).
    """
    date_str = article_date.strftime("%B %d, %Y")  # e.g. "February 23, 2026"
    date_iso = article_date.isoformat()

    market_context = build_market_context(kalshi_markets, poly_markets)

    internal_links = "\n".join(
        f"- [{title}]({path})" for path, title in EXISTING_ARTICLES
    )

    platform_note = ""
    if kalshi_markets and poly_markets:
        platform_note = "Cover markets from BOTH Kalshi and Polymarket."
    elif kalshi_markets:
        platform_note = "Only Kalshi data is available today — focus on Kalshi markets."
    else:
        platform_note = "Only Polymarket data is available today — focus on Polymarket markets."

    system = (
        "You are a prediction markets analyst writing a daily roundup for "
        "Master Prediction Markets (masterpredictionmarkets.com). Write in a "
        "professional, data-driven tone — like a Bloomberg terminal meets "
        "a knowledgeable friend. Reference specific prices and volumes. "
        "Do NOT fabricate market data — only reference markets from the data provided."
    )

    prompt = f"""Write a daily prediction market roundup article for {date_str}.

{platform_note}

REAL MARKET DATA (use these numbers — do not invent markets):
{market_context}

REQUIREMENTS:
1. Title format: "Daily Market Pulse: {date_str} — [catchy subtitle about the day's top story]"
2. Write 800-1000 words covering:
   - Lead with the day's biggest mover or most interesting market
   - Group related markets into 3-5 thematic sections with H2 headers
   - For each notable market, mention the current price (as implied probability %) and volume
   - Highlight any contracts trading near extreme levels (>90% or <10%)
   - Note any interesting new markets or unusual categories
3. Include EXACTLY one Kalshi referral link: [Kalshi]({KALSHI_REFERRAL})
   — weave it naturally into text (e.g. "you can trade these markets on [Kalshi](...)")
4. Include EXACTLY one Polymarket referral link: [Polymarket]({POLYMARKET_REFERRAL})
   — weave it naturally into text
5. Include 1-2 internal links to relevant existing articles from this list:
{internal_links}
6. End with a brief "What to Watch" section about upcoming events/catalysts
7. Do NOT include frontmatter — just the article body in markdown
8. Do NOT start with the title — just begin with an engaging opening paragraph
9. Use H2 (##) for main sections, H3 (###) for subsections if needed
10. Do NOT use the word "meme" to describe any markets

OUTPUT ONLY the markdown article body."""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    body = message.content[0].text.strip()

    # Extract title from the article body (first H1 or generate one)
    title_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        # Remove the H1 line from body since frontmatter has the title
        body = body[:title_match.start()] + body[title_match.end():]
        body = body.strip()
    else:
        title = f"Daily Market Pulse: {date_str}"

    # Ensure title starts with "Daily Market Pulse:"
    if not title.startswith("Daily Market Pulse:"):
        title = f"Daily Market Pulse: {date_str} — {title}"

    # Generate SEO description
    desc_msg = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                f"Write a 150-character SEO meta description for a daily prediction "
                f"market roundup article titled \"{title}\". Output ONLY the "
                f"description text, no quotes or labels."
            ),
        }],
    )
    description = desc_msg.content[0].text.strip().strip('"').strip("'")

    # Build frontmatter
    tags_yaml = '"daily", "kalshi", "polymarket"'
    frontmatter = f'''---
title: "{title}"
description: "{description}"
pubDate: {date_iso}
category: "strategies"
tags: [{tags_yaml}]
affiliate: "kalshi"
---'''

    full_content = f"{frontmatter}\n\n{body}\n"
    filename = f"daily-market-pulse-{date_iso}.md"

    return filename, full_content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate daily market roundup")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Article date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    if args.date:
        article_date = date.fromisoformat(args.date)
    else:
        article_date = date.today()

    print(f"Generating Daily Market Pulse for {article_date.isoformat()}...")

    # Step 1: Fetch market data
    print("  Fetching Kalshi markets...")
    kalshi = fetch_kalshi_markets(limit=10)
    print(f"  Got {len(kalshi)} Kalshi markets")

    print("  Fetching Polymarket markets...")
    poly = fetch_polymarket_markets(limit=10)
    print(f"  Got {len(poly)} Polymarket markets")

    if not kalshi and not poly:
        print("ERROR: Both APIs returned no data. Skipping article generation.")
        sys.exit(0)  # exit 0 so CI doesn't fail

    # Step 2: Generate article
    print("  Generating article via Claude API...")
    filename, content = generate_article(article_date, kalshi, poly)

    # Step 3: Save
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CONTENT_DIR / filename
    filepath.write_text(content)
    print(f"  Saved: {filepath}")
    print(f"Done! Article: {filename}")


if __name__ == "__main__":
    main()
