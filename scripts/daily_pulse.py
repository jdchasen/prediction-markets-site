#!/usr/bin/env python3
"""Generate daily market pulse blog post using live market data and Claude API."""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
POLY_GAMMA = "https://gamma-api.polymarket.com"
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"

KALSHI_REFERRAL = "https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true"
POLY_REFERRAL = "https://polymarket.us/1762"

REPO_ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = REPO_ROOT / "src" / "content" / "blog"

INTERNAL_LINKS = {
    "probability calculator": "/tools/probability-calculator",
    "kelly calculator": "/tools/kelly-calculator",
    "arbitrage scanner": "/tools/arbitrage-scanner",
    "portfolio calculator": "/tools/portfolio-calculator",
    "event contract pricing": "/blog/understanding-event-contract-pricing-and-probability",
    "finding edge": "/blog/prediction-market-strategies-finding-edge-as-a-retail-trader",
    "kalshi fees": "/blog/kalshi-fees-explained",
    "kalshi vs polymarket": "/blog/kalshi-vs-polymarket-which-platform-should-you-use",
    "weather markets": "/blog/how-to-trade-weather-markets-on-kalshi",
    "implied probability": "/blog/how-to-calculate-implied-probability-prediction-markets",
    "kelly criterion": "/blog/kelly-criterion-prediction-markets-guide",
    "arbitrage guide": "/blog/prediction-market-arbitrage-guide",
    "common mistakes": "/blog/5-common-prediction-market-mistakes-to-avoid",
    "what are prediction markets": "/blog/what-are-prediction-markets",
    "what are event contracts": "/blog/what-are-event-contracts",
    "prediction markets vs sports betting": "/blog/prediction-markets-vs-sports-betting-key-differences",
    "api trading": "/blog/how-to-use-apis-for-automated-prediction-market-trading",
    "kalshi review": "/blog/kalshi-review",
    "polymarket guide": "/blog/polymarket-guide-how-to-trade-crypto-prediction-markets",
}

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_polymarket_events(limit: int = 15) -> list[dict]:
    """Fetch top Polymarket events by 24h volume."""
    try:
        resp = requests.get(
            f"{POLY_GAMMA}/events",
            params={
                "active": "true",
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false",
                "limit": str(limit),
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[WARN] Polymarket events fetch failed: {e}", file=sys.stderr)
        return []


def fetch_polymarket_markets(limit: int = 30) -> list[dict]:
    """Fetch top individual Polymarket markets by 24h volume."""
    try:
        resp = requests.get(
            f"{POLY_GAMMA}/markets",
            params={
                "active": "true",
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false",
                "limit": str(limit),
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[WARN] Polymarket markets fetch failed: {e}", file=sys.stderr)
        return []


def fetch_kalshi_events(limit: int = 20) -> list[dict]:
    """Fetch Kalshi events with nested markets."""
    try:
        resp = requests.get(
            f"{KALSHI_API}/events",
            params={
                "limit": str(limit),
                "status": "open",
                "with_nested_markets": "true",
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception as e:
        print(f"[WARN] Kalshi events fetch failed: {e}", file=sys.stderr)
        return []


def fetch_kalshi_markets_by_series(series_tickers: list[str], limit: int = 10) -> dict[str, list[dict]]:
    """Fetch Kalshi markets for specific series (e.g. KXINX, KXBTC)."""
    results = {}
    for i, ticker in enumerate(series_tickers):
        if i > 0:
            time.sleep(1)  # Avoid Kalshi rate limiting
        try:
            resp = requests.get(
                f"{KALSHI_API}/markets",
                params={
                    "limit": str(limit),
                    "status": "open",
                    "series_ticker": ticker,
                },
                timeout=15,
            )
            resp.raise_for_status()
            markets = resp.json().get("markets", [])
            markets.sort(key=lambda m: m.get("volume_24h", 0), reverse=True)
            results[ticker] = markets[:limit]
        except Exception as e:
            print(f"[WARN] Kalshi series {ticker} fetch failed: {e}", file=sys.stderr)
    return results


# ---------------------------------------------------------------------------
# Data formatting for the prompt
# ---------------------------------------------------------------------------

def format_polymarket_data(events: list[dict], markets: list[dict]) -> str:
    """Format Polymarket data into a readable summary for Claude."""
    lines = ["## POLYMARKET DATA\n"]

    lines.append("### Top Events by 24h Volume\n")
    for e in events:
        vol_total = e.get("volume", 0)
        vol_24h = e.get("volume24hr", 0)
        title = e.get("title", "Unknown")
        lines.append(f"**{title}**")
        lines.append(f"  Total volume: ${vol_total:,.0f} | 24h volume: ${vol_24h:,.0f}")

        sub_markets = e.get("markets", [])
        # Sort sub-markets by 24h volume
        sub_markets.sort(key=lambda m: m.get("volume24hr", 0), reverse=True)
        for m in sub_markets[:8]:
            prices = json.loads(m.get("outcomePrices", "[]"))
            yes_price = prices[0] if prices else "N/A"
            group_title = m.get("groupItemTitle", "") or m.get("question", "")[:80]
            m_vol24 = m.get("volume24hr", 0)
            m_vol = m.get("volumeNum", 0)
            lines.append(f"  - {group_title}: YES={yes_price} | 24h vol=${m_vol24:,.0f} | total vol=${m_vol:,.0f}")
        lines.append("")

    lines.append("\n### Top Individual Markets by 24h Volume\n")
    for m in markets[:20]:
        prices = json.loads(m.get("outcomePrices", "[]"))
        yes_price = prices[0] if prices else "N/A"
        title = m.get("groupItemTitle", "") or m.get("question", "")[:80]
        event_info = m.get("events", [{}])
        event_title = event_info[0].get("title", "") if event_info else ""
        vol_24h = m.get("volume24hr", 0)
        vol_total = m.get("volumeNum", 0)
        lines.append(f"- {title} [{event_title}]: YES={yes_price} | 24h=${vol_24h:,.0f} | total=${vol_total:,.0f}")

    return "\n".join(lines)


def format_kalshi_data(events: list[dict], series_data: dict[str, list[dict]]) -> str:
    """Format Kalshi data into a readable summary for Claude."""
    lines = ["## KALSHI DATA\n"]

    lines.append("### Events\n")
    for e in events[:15]:
        title = e.get("title", "Unknown")
        ticker = e.get("event_ticker", "")
        category = e.get("category", "")
        sub_markets = e.get("markets", [])
        sub_markets.sort(key=lambda m: m.get("volume_24h", 0), reverse=True)
        top_vol = sum(m.get("volume_24h", 0) for m in sub_markets)
        lines.append(f"**{title}** (category: {category}, ticker: {ticker}, combined 24h vol: {top_vol})")
        for m in sub_markets[:5]:
            lines.append(
                f"  - {m.get('title', '')[:80]} | "
                f"price={m.get('last_price', 0)} | "
                f"vol24h={m.get('volume_24h', 0)} | "
                f"yes_bid={m.get('yes_bid', 0)} yes_ask={m.get('yes_ask', 0)}"
            )
        lines.append("")

    for series, markets in series_data.items():
        lines.append(f"\n### Series: {series}\n")
        for m in markets[:5]:
            lines.append(
                f"- {m.get('title', '')[:80]} | "
                f"price={m.get('last_price', 0)} | "
                f"vol24h={m.get('volume_24h', 0)}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are the editorial writer for Master Prediction Markets (masterpredictionmarkets.com). You write the "Daily Market Pulse" — a morning briefing covering the biggest prediction market moves from the past 24 hours.

## Your voice
- Conversational, sharp, and opinionated — like a smart friend giving you the morning rundown over coffee.
- Have a take. Don't just report what happened — tell the reader why it's interesting, funny, surprising, or important.
- Use specific numbers (prices, volumes, probabilities) but weave them into readable sentences. Don't drown the reader in data.
- Short paragraphs. 2-3 sentences max. White space is your friend.
- Use humor and personality where it fits. Prediction markets are inherently entertaining — lean into that.
- Use contractions (don't, isn't, can't). Write like a human, not a Bloomberg terminal.
- Be honest about uncertainty — if a market move has no obvious catalyst, say so. If a contract is absurd, call it absurd.
- Do NOT over-explain how prediction markets work. Assume the reader gets the basics.
- Do NOT use academic phrases like "probability cascade," "crystallize consensus," or "mathematical elegance." Just talk normally.
- When mentioning a contract at a very low price (under 5%), say what it means plainly: "the market thinks this is basically impossible" or "traders are giving this a 3% shot."

## Frontmatter (EXACT format required)
The file MUST begin with this exact frontmatter structure (replace values in angle brackets):
```
---
title: "Daily Market Pulse: <Month Day, Year>"
description: "<One punchy sentence summarizing the top 2-3 storylines. Make someone want to click.>"
pubDate: <YYYY-MM-DD>
category: "strategies"
tags: ["daily", "kalshi", "polymarket"]
affiliate: "kalshi"
---
```

## Structure
After the frontmatter closing `---`, the body starts DIRECTLY with an opening paragraph. Do NOT include an H1 header — the title is rendered from frontmatter by the site template.

1. **Opening paragraph** (2-3 sentences): Lead with the most interesting or surprising storyline. Hook the reader. First mention of Kalshi should link to the referral URL. First mention of Polymarket should link to the referral URL.
2. **3-5 H2 sections**: Each covering a distinct market theme (geopolitics, economics, crypto, sports, policy, etc.). Pick the most newsworthy/highest-volume themes from the data. Each section should:
   - Lead with why it's interesting, then bring in the numbers
   - Use markdown tables when comparing related contracts (keep tables clean and simple)
   - Give the reader a quick opinion or takeaway — don't just dump data
   - Where relevant, link to an internal article or tool (see list below)
3. **Final H2: "What to Watch"**: 3-4 bullet points of upcoming catalysts. Keep them punchy — one sentence each if possible.

## Rules
- NEVER invent data. Every price, volume, and probability MUST come from the data provided below. If data is missing for a market you want to mention, skip it.
- Use percentage notation in running text (e.g., "19.5%"). Use dollar notation for prices in tables (e.g., "$0.195").
- Always include at least one markdown table.
- Include 2-4 internal links per post, chosen contextually.
- Do NOT include sports game-by-game results unless there's a genuinely interesting storyline.
- Focus on markets that matter: geopolitics, economics, crypto, policy, elections. Sports only if the volume or story is notable.
- Skip markets with near-zero volume or that have already resolved.
- Do NOT include an H1 (#) header in the body. Start with a paragraph, then use only H2 (##) headers.
- Keep the total post concise — aim for engaging, not exhaustive. Cut any section that feels like filler.

## Affiliate links (use EXACTLY these URLs)
- Kalshi: {kalshi_ref}
- Polymarket: {poly_ref}

## Internal links available (use markdown links contextually, 2-4 per post)
{internal_links}

## Tools pages (link when the context fits)
- Probability Calculator: /tools/probability-calculator
- Kelly Calculator: /tools/kelly-calculator
- Arbitrage Scanner: /tools/arbitrage-scanner
- Portfolio Calculator: /tools/portfolio-calculator
"""

USER_PROMPT_TEMPLATE = """\
Today's date: {date_str} ({day_of_week})

Write the Daily Market Pulse for {formatted_date}. Here is today's market data:

{polymarket_data}

{kalshi_data}

Output ONLY the complete markdown file including frontmatter. Start with --- and end after the last line of content. Do not wrap in code fences.
"""


def generate_pulse(
    polymarket_data: str,
    kalshi_data: str,
    pub_date: datetime,
) -> str:
    """Call Claude API to generate the daily pulse."""
    client = anthropic.Anthropic()

    internal_links_str = "\n".join(
        f"- [{name}]({path})" for name, path in sorted(INTERNAL_LINKS.items())
    )

    system = SYSTEM_PROMPT.format(
        kalshi_ref=KALSHI_REFERRAL,
        poly_ref=POLY_REFERRAL,
        internal_links=internal_links_str,
    )

    day_of_week = pub_date.strftime("%A")
    formatted_date = pub_date.strftime("%B %d, %Y").replace(" 0", " ")
    date_str = pub_date.strftime("%Y-%m-%d")

    user_msg = USER_PROMPT_TEMPLATE.format(
        date_str=date_str,
        day_of_week=day_of_week,
        formatted_date=formatted_date,
        polymarket_data=polymarket_data,
        kalshi_data=kalshi_data,
    )

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    return message.content[0].text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Determine publication date (today in ET)
    et_offset = timedelta(hours=-5)  # ET = UTC-5 (EDT) or UTC-4 — use -5 for EST
    now_et = datetime.now(timezone(et_offset))
    pub_date = now_et.replace(hour=0, minute=0, second=0, microsecond=0)

    date_str = pub_date.strftime("%Y-%m-%d")
    filename = f"daily-market-pulse-{date_str}.md"
    output_path = BLOG_DIR / filename

    # Check if already exists
    if output_path.exists():
        print(f"[SKIP] {filename} already exists. Delete it first to regenerate.")
        return

    print(f"[INFO] Generating daily pulse for {date_str}...")

    # Fetch data
    print("[INFO] Fetching Polymarket data...")
    poly_events = fetch_polymarket_events(limit=15)
    poly_markets = fetch_polymarket_markets(limit=30)

    print("[INFO] Fetching Kalshi data...")
    kalshi_events = fetch_kalshi_events(limit=20)
    kalshi_series = fetch_kalshi_markets_by_series(
        ["KXINX", "KXBTC", "KXFED", "KXCPI"],
        limit=10,
    )

    if not poly_events and not poly_markets and not kalshi_events:
        print("[ERROR] No market data available from any source. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Format data
    polymarket_data = format_polymarket_data(poly_events, poly_markets)
    kalshi_data = format_kalshi_data(kalshi_events, kalshi_series)

    print(f"[INFO] Polymarket: {len(poly_events)} events, {len(poly_markets)} markets")
    print(f"[INFO] Kalshi: {len(kalshi_events)} events, {len(kalshi_series)} series")

    # Generate with Claude
    print("[INFO] Calling Claude API...")
    content = generate_pulse(polymarket_data, kalshi_data, pub_date)

    # Validate output
    if not content.startswith("---"):
        print("[ERROR] Generated content doesn't start with frontmatter. Aborting.", file=sys.stderr)
        print(f"[DEBUG] First 200 chars: {content[:200]}", file=sys.stderr)
        sys.exit(1)

    if content.count("---") < 2:
        print("[ERROR] Generated content missing frontmatter closing. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Validate required frontmatter fields
    frontmatter = content.split("---")[1]
    required = ["pubDate:", "category:", "tags:", "affiliate:"]
    missing = [f for f in required if f not in frontmatter]
    if missing:
        print(f"[WARN] Missing frontmatter fields: {missing}. Injecting defaults.", file=sys.stderr)
        # Inject missing fields before the closing ---
        inject = ""
        if "pubDate:" in missing:
            inject += f'\npubDate: {date_str}'
        if "category:" in missing:
            inject += '\ncategory: "strategies"'
        if "tags:" in missing:
            inject += '\ntags: ["daily", "kalshi", "polymarket"]'
        if "affiliate:" in missing:
            inject += '\naffiliate: "kalshi"'
        # Insert before closing ---
        parts = content.split("---", 2)
        content = f"---{parts[1]}{inject}\n---{parts[2]}"

    # Strip any H1 header that might appear right after frontmatter
    body_start = content.index("---", 3) + 3
    body = content[body_start:].lstrip("\n")
    if body.startswith("# "):
        # Remove the H1 line
        body = body[body.index("\n") + 1:].lstrip("\n")
        content = content[:body_start] + "\n\n" + body

    # Write file
    output_path.write_text(content)
    print(f"[OK] Written to {output_path}")


if __name__ == "__main__":
    main()
