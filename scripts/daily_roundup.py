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
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone, timedelta
from html import unescape
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

KALSHI_REFERRAL = "https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup"
POLYMARKET_REFERRAL = "https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup"

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
# News fetching
# ---------------------------------------------------------------------------

def fetch_trending_news(limit: int = 20) -> list[dict]:
    """Fetch top news headlines from Google News RSS — no API key needed."""
    feeds = [
        ("Top Stories", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
        ("Business", "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en"),
        ("World", "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en"),
    ]
    seen_titles = set()
    headlines = []

    for category, url in feeds:
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.iter("item"):
                title_el = item.find("title")
                source_el = item.find("source")
                pub_el = item.find("pubDate")

                if title_el is None:
                    continue

                title = unescape(title_el.text or "").strip()
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                source = source_el.text if source_el is not None else ""
                pub_date = pub_el.text if pub_el is not None else ""

                headlines.append({
                    "title": title,
                    "source": source,
                    "category": category,
                    "pub_date": pub_date,
                })

                if len(headlines) >= limit:
                    break
        except Exception as e:
            print(f"  Google News ({category}) fetch failed: {e}")

    return headlines[:limit]


def format_news_context(headlines: list[dict]) -> str:
    """Format news headlines for the Claude prompt."""
    if not headlines:
        return ""
    lines = [
        "=== TODAY'S TOP NEWS HEADLINES ===",
        "These are the stories dominating the news RIGHT NOW.",
        "Your article MUST connect prediction markets to these stories.",
        "",
    ]
    for i, h in enumerate(headlines, 1):
        source = f" ({h['source']})" if h.get('source') else ""
        lines.append(f"{i}. [{h['category']}] {h['title']}{source}")
    lines.append("")
    return "\n".join(lines)


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

    # Sort by 24h volume descending so the mix changes daily
    markets.sort(key=lambda m: m.get("volume_24h", 0) or 0, reverse=True)
    results = []
    for m in markets[:limit * 3]:  # oversample to compensate for filtering
        yes_price = m.get("yes_ask") or m.get("last_price") or 0
        no_price = m.get("no_ask") or (100 - yes_price if yes_price else 0)
        # Skip markets with extreme odds — essentially already decided
        if yes_price <= 5 or yes_price >= 95:
            continue
        if len(results) >= limit:
            break
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
    for m in markets[:limit * 3]:  # oversample to compensate for filtering
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

        # Skip markets with extreme odds — essentially already decided
        if yes_price <= 5 or yes_price >= 95:
            continue
        if len(results) >= limit:
            break
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


def _load_yesterday_article(article_date: date) -> str:
    """Load yesterday's article body to avoid repetition."""
    yesterday = article_date - timedelta(days=1)
    yesterday_file = CONTENT_DIR / f"daily-market-pulse-{yesterday.isoformat()}.md"
    if yesterday_file.exists():
        content = yesterday_file.read_text()
        # Strip frontmatter
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()[:2000]  # first 2000 chars of body
    return ""


def generate_article(
    article_date: date,
    kalshi_markets: list[dict],
    poly_markets: list[dict],
    news_headlines=None,
) -> tuple[str, str]:
    """Generate the daily roundup article via Claude API.

    Returns (filename, full_markdown_with_frontmatter).
    """
    date_str = article_date.strftime("%B %d, %Y")  # e.g. "February 23, 2026"
    date_iso = article_date.isoformat()

    market_context = build_market_context(kalshi_markets, poly_markets)
    news_context = format_news_context(news_headlines or [])

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

    # Load yesterday's article for differentiation
    yesterday_body = _load_yesterday_article(article_date)
    yesterday_block = ""
    if yesterday_body:
        yesterday_block = f"""
YESTERDAY'S ARTICLE (DO NOT repeat the same framing, lead story, section structure, or angles):
{yesterday_body}
"""

    # Day-of-week for variety hooks
    day_of_week = article_date.strftime("%A")  # e.g. "Monday"

    system = (
        "You are a prediction markets writer for Master Prediction Markets "
        "(masterpredictionmarkets.com). Write like a sharp, opinionated friend "
        "giving the morning briefing — conversational, fun to read, with real takes. "
        "Use short paragraphs (2-3 sentences max), contractions, and personality. "
        "Reference specific prices and volumes but don't drown the reader in data. "
        "Have opinions about what's interesting, surprising, or absurd. "
        "Do NOT fabricate market data — only reference markets from the data provided. "
        "Do NOT use academic language like 'probability cascade' or 'crystallize consensus.' "
        "Each day's article MUST feel distinct — vary your opening style, section themes, "
        "analytical angles, and which markets you lead with.\n\n"
        "CRITICAL — NEWS-FIRST RULE: You will receive today's top news headlines. "
        "Your article MUST lead with the biggest breaking news story and connect it "
        "to relevant prediction markets. If a major world event happened (war, attacks, "
        "political crisis, economic shock, natural disaster), that is ALWAYS the lead — "
        "not just whatever market has the highest volume. Readers are coming to understand "
        "how today's news moves prediction markets. If you ignore the top headline, "
        "the article is useless."
    )

    news_instruction = ""
    if news_context:
        news_instruction = (
            "13. NEWS-FIRST (MANDATORY): The news headlines below are today's top stories. "
            "Your opening paragraph and first H2 section MUST connect to the #1 headline. "
            "You MUST reference at least 3 specific headlines from the list in your article, "
            "connecting each to a relevant prediction market. If a headline describes a major "
            "event that already happened (e.g., military strikes, elections, disasters), "
            "write about the market REACTION and AFTERMATH — not speculation about whether "
            "it will happen. The news is what makes this a daily pulse and not a stale market report."
        )

    prompt = f"""Write a daily prediction market roundup article for {date_str} ({day_of_week}).

{platform_note}

{news_context}
REAL MARKET DATA (use these numbers — do not invent markets):
{market_context}
{yesterday_block}
REQUIREMENTS:
1. Title format: "[Event-focused phrase] | Daily Market Pulse"
   - The event phrase goes FIRST — this is what people search for
   - Keep total title under 55 characters (Google truncates at ~60)
   - Examples: "Iran Strikes Push Markets to 92% | Daily Market Pulse"
   - NEVER start with "Daily Market Pulse:" — that wastes searchable space
   - NEVER use generic phrases like "market movements" or "top forecasts"
   - The title should read like a headline someone would Google
2. Write 800-1000 words covering:
   - LEAD with the prediction market most connected to today's top news headline
   - Group related markets into 3-5 thematic sections with H2 headers
   - For each notable market, mention the current price (as implied probability %) and volume
   - Focus on CONTESTED markets where the outcome is uncertain and there is real debate
   - Do NOT waste space on markets that are essentially settled (near 0% or 100%)
   - Prioritize markets where something changed, prices moved, or there is a genuine decision point
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
11. CRITICAL: If yesterday's article is provided above, you MUST:
    - Use a DIFFERENT opening style (don't start with "The prediction markets landscape...")
    - Lead with a DIFFERENT market or angle than yesterday
    - Use DIFFERENT H2 section names and groupings
    - If the same market appeared yesterday, focus on what CHANGED (price moves, volume shifts)
    - Choose DIFFERENT internal article links than yesterday used
12. Vary your writing approach: some days lead with a single market deep-dive,
    others with a cross-market theme, others with a surprising data point.
    Don't settle into a formula.
{news_instruction}

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

    # Ensure title ends with "Daily Market Pulse" brand suffix
    if "Daily Market Pulse" not in title:
        title = f"{title} | Daily Market Pulse"
    # Truncate to 60 chars for Google SERP display
    if len(title) > 60:
        # Keep the event phrase, trim the suffix if needed
        title = title[:57] + "..."

    # Generate SEO description — must be specific, not generic
    desc_msg = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                f"Write a 150-character meta description for this prediction market article. "
                f"It MUST reference specific events, markets, or probabilities from the article. "
                f"NEVER write generic SEO filler like 'Get the latest prediction market insights' "
                f"or 'Today's top forecasts and market movements.' Instead, be specific: "
                f"'US strikes Iran as Polymarket hits 77% on regime change — plus Bitcoin, Fed odds, and more.' "
                f"Output ONLY the description text, no quotes or labels.\n\n"
                f"TITLE: {title}\n"
                f"ARTICLE OPENING:\n{body[:500]}"
            ),
        }],
    )
    description = desc_msg.content[0].text.strip().strip('"').strip("'")

    # Generate FAQs (required by blog schema)
    faq_msg = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": (
                f"Based on this prediction market roundup article, generate exactly "
                f"3 FAQs as a YAML list. Each FAQ must have a 'question' and 'answer' field. "
                f"Questions should be things a reader would search for. "
                f"Answers should be 1-2 sentences max.\n\n"
                f"ARTICLE TITLE: {title}\n"
                f"ARTICLE BODY:\n{body[:2000]}\n\n"
                f"OUTPUT FORMAT (output ONLY the YAML, no code fences or labels):\n"
                f"  - question: \"...\"\n"
                f"    answer: \"...\"\n"
                f"  - question: \"...\"\n"
                f"    answer: \"...\"\n"
                f"  - question: \"...\"\n"
                f"    answer: \"...\""
            ),
        }],
    )
    faqs_yaml = faq_msg.content[0].text.strip()
    # Strip code fences if present
    faqs_yaml = re.sub(r'^```(?:ya?ml)?\s*', '', faqs_yaml)
    faqs_yaml = re.sub(r'\s*```$', '', faqs_yaml)
    # Ensure proper indentation (each line indented 2 spaces under faqs:)
    faq_lines = faqs_yaml.strip().splitlines()
    faqs_block = "\n".join(f"  {line.strip()}" if line.strip().startswith("-") else f"    {line.strip()}" for line in faq_lines)

    # Build frontmatter
    tags_yaml = '"daily", "kalshi", "polymarket"'
    frontmatter = f'''---
title: "{title}"
description: "{description}"
pubDate: {date_iso}
category: "strategies"
tags: [{tags_yaml}]
affiliate: "kalshi"
faqs:
{faqs_block}
---'''

    full_content = f"{frontmatter}\n\n{body}\n"
    filename = f"daily-market-pulse-{date_iso}.md"

    return filename, full_content


# ---------------------------------------------------------------------------
# Tweet generation + posting
# ---------------------------------------------------------------------------

def generate_tweet(article_date: date, article_body: str) -> str:
    """Generate a punchy tweet for the daily article via Claude API."""
    date_iso = article_date.isoformat()
    article_url = f"https://masterpredictionmarkets.com/blog/daily-market-pulse-{date_iso}"

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": (
                f"Write a tweet (max 200 characters BEFORE the URL and hashtags) "
                f"promoting this daily prediction market roundup article. "
                f"Include 1-2 specific data points from the article (e.g., prices, "
                f"probabilities, volumes). Be punchy and attention-grabbing.\n\n"
                f"ARTICLE:\n{article_body[:2000]}\n\n"
                f"OUTPUT FORMAT (output ONLY this, no quotes):\n"
                f"[tweet text]\n\n"
                f"{article_url}\n\n"
                f"#PredictionMarkets #Kalshi #Polymarket"
            ),
        }],
    )
    tweet = message.content[0].text.strip()

    # Ensure URL and hashtags are present
    if article_url not in tweet:
        tweet = f"{tweet}\n\n{article_url}"
    if "#PredictionMarkets" not in tweet:
        tweet = f"{tweet}\n\n#PredictionMarkets #Kalshi #Polymarket"

    return tweet


def post_tweet(tweet_text: str) -> bool:
    """Post a tweet via Twitter API v2 using tweepy. Returns True on success."""
    api_key = os.environ.get("TWITTER_API_KEY", "")
    api_secret = os.environ.get("TWITTER_API_SECRET", "")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("  Twitter credentials not configured, skipping tweet")
        return False

    try:
        import tweepy
    except ImportError:
        print("  tweepy not installed, skipping tweet")
        return False

    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        response = client.create_tweet(text=tweet_text)
        tweet_id = response.data["id"]
        print(f"  Tweet posted: https://x.com/master_mar686/status/{tweet_id}")
        return True
    except Exception as e:
        print(f"  Twitter API error: {e}")
        return False


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
        # Use ET (UTC-5) so the article date matches the US calendar day,
        # even when the GitHub Actions runner is in UTC.
        et = timezone(timedelta(hours=-5))
        article_date = datetime.now(et).date()

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

    # Step 1b: Fetch trending news
    print("  Fetching trending news...")
    headlines = fetch_trending_news(limit=20)
    print(f"  Got {len(headlines)} news headlines")

    # Step 2: Generate article
    print("  Generating article via Claude API...")
    filename, content = generate_article(article_date, kalshi, poly, headlines)

    # Step 3: Save
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CONTENT_DIR / filename
    filepath.write_text(content)
    print(f"  Saved: {filepath}")

    # Step 4: Generate and post tweet
    print("  Generating tweet via Claude API...")
    tweet_text = generate_tweet(article_date, content)
    print(f"  Tweet:\n{tweet_text}")
    post_tweet(tweet_text)

    print(f"Done! Article: {filename}")


if __name__ == "__main__":
    main()
