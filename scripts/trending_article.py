#!/usr/bin/env python3
"""
Generate standalone SEO articles for trending prediction markets.

Targets search queries like "Iran prediction market odds" with keyword-optimized
titles. Runs daily alongside the daily pulse but produces separate, event-specific
content that captures breaking news search traffic.

Usage:
  python scripts/trending_article.py
  python scripts/trending_article.py --date 2026-02-28

Environment variables:
  ANTHROPIC_API_KEY  — required for article generation
"""

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone, timedelta
from html import unescape
from pathlib import Path

import anthropic
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
POLY_GAMMA = "https://gamma-api.polymarket.com"
REPO_ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = REPO_ROOT / "src" / "content" / "blog"

KALSHI_REFERRAL = (
    "https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21"
    "&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup"
)
POLY_REFERRAL = (
    "https://polymarket.us/1762?utm_source=masterpredictionmarkets"
    "&utm_medium=blog&utm_campaign=signup"
)

INTERNAL_LINKS = {
    "probability calculator": "/tools/probability-calculator",
    "kelly calculator": "/tools/kelly-calculator",
    "arbitrage scanner": "/tools/arbitrage-scanner",
    "what are prediction markets": "/blog/what-are-prediction-markets",
    "what are event contracts": "/blog/what-are-event-contracts",
    "finding edge": "/blog/prediction-market-strategies-finding-edge-as-a-retail-trader",
    "kalshi fees": "/blog/kalshi-fees-explained",
    "kalshi vs polymarket": "/blog/kalshi-vs-polymarket-which-platform-should-you-use",
    "implied probability": "/blog/how-to-calculate-implied-probability-prediction-markets",
    "common mistakes": "/blog/5-common-prediction-market-mistakes-to-avoid",
    "kalshi review": "/blog/kalshi-review",
    "polymarket guide": "/blog/polymarket-guide-how-to-trade-crypto-prediction-markets",
}

# Minimum 24h volume to qualify as "trending" (in dollars)
MIN_VOLUME_24H = 500_000

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_polymarket_events(limit=15):
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
        print(f"  Polymarket events fetch failed: {e}", file=sys.stderr)
        return []


def fetch_trending_news(limit=20):
    """Fetch top news headlines from Google News RSS."""
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
                if title_el is None:
                    continue
                title = unescape(title_el.text or "").strip()
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                source_el = item.find("source")
                headlines.append({
                    "title": title,
                    "source": source_el.text if source_el is not None else "",
                    "category": category,
                })
                if len(headlines) >= limit:
                    break
        except Exception as e:
            print(f"  Google News ({category}) fetch failed: {e}")
    return headlines[:limit]


def pick_trending_event(events, existing_slugs):
    """Pick the top event that qualifies and hasn't been covered recently."""
    for event in events:
        vol_24h = event.get("volume24hr", 0) or 0
        if vol_24h < MIN_VOLUME_24H:
            continue

        title = event.get("title", "")
        slug = slugify(title)

        # Skip if we already have an article with a similar slug
        if any(slug in existing for existing in existing_slugs):
            continue

        # Build market details
        sub_markets = event.get("markets", [])
        sub_markets.sort(key=lambda m: m.get("volume24hr", 0) or 0, reverse=True)

        markets_data = []
        for m in sub_markets[:10]:
            prices = json.loads(m.get("outcomePrices", "[]"))
            yes_price = prices[0] if prices else "0"
            try:
                yp = float(yes_price)
            except (ValueError, TypeError):
                yp = 0
            markets_data.append({
                "question": m.get("groupItemTitle", "") or m.get("question", ""),
                "yes_price": yp,
                "volume_24h": m.get("volume24hr", 0) or 0,
                "volume_total": m.get("volumeNum", 0) or 0,
            })

        return {
            "title": title,
            "slug": slug,
            "volume_24h": vol_24h,
            "volume_total": event.get("volume", 0) or 0,
            "markets": markets_data,
        }

    return None


def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60].rstrip('-')


# ---------------------------------------------------------------------------
# Article generation
# ---------------------------------------------------------------------------

def generate_article(event, headlines, article_date):
    """Generate a standalone SEO article for the trending event."""
    client = anthropic.Anthropic()

    date_str = article_date.strftime("%B %d, %Y")
    date_iso = article_date.isoformat()

    # Format market data
    market_lines = []
    for m in event["markets"]:
        pct = round(m["yes_price"] * 100, 1)
        vol_24h = f"${m['volume_24h']:,.0f}" if m["volume_24h"] else "N/A"
        vol_total = f"${m['volume_total']:,.0f}" if m["volume_total"] else "N/A"
        market_lines.append(
            f"- {m['question']}: YES={pct}% | 24h vol={vol_24h} | total vol={vol_total}"
        )
    market_context = "\n".join(market_lines)

    # Format news
    news_lines = []
    for h in headlines[:10]:
        source = f" ({h['source']})" if h.get("source") else ""
        news_lines.append(f"- [{h['category']}] {h['title']}{source}")
    news_context = "\n".join(news_lines)

    internal_links_str = "\n".join(
        f"- [{name}]({path})" for name, path in sorted(INTERNAL_LINKS.items())
    )

    system = (
        "You are a prediction markets writer for Master Prediction Markets "
        "(masterpredictionmarkets.com). You write standalone, SEO-optimized deep-dive "
        "articles about trending prediction markets. Write like a sharp, knowledgeable "
        "friend explaining what's happening and what the odds mean. "
        "Conversational tone, short paragraphs (2-3 sentences), contractions, personality. "
        "Do NOT fabricate data — only use the market data provided. "
        "Do NOT use academic language. Write for someone who just googled this topic."
    )

    prompt = f"""Write a standalone deep-dive article about this trending prediction market:

EVENT: {event['title']}
Total volume: ${event['volume_total']:,.0f}
24h volume: ${event['volume_24h']:,.0f}

MARKET DATA:
{market_context}

TODAY'S NEWS HEADLINES (connect to these where relevant):
{news_context}

REQUIREMENTS:
1. SEO TITLE (CRITICAL):
   - Must target what someone would actually Google about this topic
   - Examples: "Iran Prediction Market Odds: What Traders Are Betting"
   - Or: "Will Khamenei Lose Power? Polymarket Odds Explained"
   - Keep under 55 characters total
   - Do NOT include dates in the title
   - Do NOT start with "Daily Market Pulse"
   - Think: what would someone type into Google right now about this event?

2. Write 600-900 words covering:
   - What's happening (connect to today's news headlines)
   - What prediction markets are saying (specific odds, volumes)
   - Why the odds are where they are (analysis)
   - How to think about betting on this (risk/reward, which side looks interesting)
   - What catalysts could move the price next

3. Include EXACTLY one Kalshi referral link: [Kalshi]({KALSHI_REFERRAL})
4. Include EXACTLY one Polymarket referral link: [Polymarket]({POLY_REFERRAL})
5. Include 2-3 internal links from this list:
{internal_links_str}

6. DESCRIPTION: One punchy sentence (under 155 chars) that includes the key search term
   and a specific number from the article. Example:
   "Polymarket traders give Iran regime change 77% odds after US strikes — here's what the money says."

7. FAQs: Include 3-4 FAQs that match likely Google searches about this topic.
   Example questions: "What are the odds of [X]?" "How much money is being bet on [X]?"

8. Do NOT include frontmatter — just the article body in markdown
9. Do NOT start with the title — begin with an engaging opening paragraph
10. Use H2 (##) for sections

OUTPUT FORMAT — output these THREE sections separated by ===SECTION===:

TITLE: [your title here]
===SECTION===
DESCRIPTION: [your description here]
===SECTION===
ARTICLE BODY:
[full markdown article]
===SECTION===
FAQS:
- question: "[Q1]"
  answer: "[A1]"
- question: "[Q2]"
  answer: "[A2]"
- question: "[Q3]"
  answer: "[A3]"
"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    # Parse sections
    sections = raw.split("===SECTION===")
    if len(sections) < 4:
        print(f"  [WARN] Expected 4 sections, got {len(sections)}. Using fallback parsing.")
        # Fallback: treat entire output as article body
        title = f"{event['title'][:40]} | Prediction Market Odds"
        description = f"Latest prediction market odds on {event['title'][:60]}."
        body = raw
        faqs_yaml = '  - question: "What are prediction markets saying about this?"\n    answer: "See the full article for current odds and analysis."'
    else:
        title = sections[0].replace("TITLE:", "").strip().strip('"')
        description = sections[1].replace("DESCRIPTION:", "").strip().strip('"')
        body = sections[2].replace("ARTICLE BODY:", "").strip()
        faqs_raw = sections[3].replace("FAQS:", "").strip()

        # Clean up FAQs
        faqs_raw = re.sub(r'^```(?:ya?ml)?\s*', '', faqs_raw)
        faqs_raw = re.sub(r'\s*```$', '', faqs_raw)
        faq_lines = faqs_raw.strip().splitlines()
        faqs_yaml = "\n".join(
            f"  {line.strip()}" if line.strip().startswith("-")
            else f"    {line.strip()}"
            for line in faq_lines
            if line.strip()
        )

    # Truncate title for SEO
    if len(title) > 60:
        title = title[:57] + "..."

    # Strip H1 if present
    body = re.sub(r'^#\s+.+\n+', '', body).strip()

    # Build slug from title
    slug = slugify(title)
    filename = f"{slug}.md"

    # Ensure description is under 160 chars
    if len(description) > 160:
        description = description[:157] + "..."

    # Build frontmatter
    frontmatter = f'''---
title: "{title}"
description: "{description}"
pubDate: {date_iso}
category: "strategies"
tags: ["trending", "polymarket", "prediction-markets"]
affiliate: "polymarket"
faqs:
{faqs_yaml}
---'''

    content = f"{frontmatter}\n\n{body}\n"
    return filename, content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate trending market article")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Article date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    if args.date:
        article_date = date.fromisoformat(args.date)
    else:
        et = timezone(timedelta(hours=-5))
        article_date = datetime.now(et).date()

    print(f"Generating trending article for {article_date.isoformat()}...")

    # Get existing article slugs to avoid duplicates
    existing_slugs = set()
    for f in BLOG_DIR.glob("*.md"):
        existing_slugs.add(f.stem)

    # Fetch data
    print("  Fetching Polymarket events...")
    events = fetch_polymarket_events(limit=15)
    print(f"  Got {len(events)} events")

    if not events:
        print("  No events available. Skipping.")
        sys.exit(0)

    print("  Fetching trending news...")
    headlines = fetch_trending_news(limit=15)
    print(f"  Got {len(headlines)} headlines")

    # Pick the top trending event
    event = pick_trending_event(events, existing_slugs)
    if not event:
        print("  No qualifying trending event found (need $500k+ 24h volume). Skipping.")
        sys.exit(0)

    print(f"  Trending event: {event['title']}")
    print(f"  24h volume: ${event['volume_24h']:,.0f}")

    # Generate article
    print("  Generating article via Claude API...")
    filename, content = generate_article(event, headlines, article_date)

    # Save
    filepath = BLOG_DIR / filename
    if filepath.exists():
        print(f"  [SKIP] {filename} already exists.")
        sys.exit(0)

    filepath.write_text(content)
    print(f"  Saved: {filepath}")
    print(f"  Done! Article: {filename}")


if __name__ == "__main__":
    main()
