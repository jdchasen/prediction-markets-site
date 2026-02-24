#!/usr/bin/env python3
"""
Generate SEO odds pages for prediction markets — zero Claude API cost.

Fetches active high-volume markets from Kalshi + Polymarket, cross-matches
duplicates, and generates markdown content pages with templated body text.

Usage:
  python scripts/generate_odds_pages.py                # full generation
  python scripts/generate_odds_pages.py --update-only  # refresh existing only

Environment variables:
  KALSHI_API_KEY        — required for authenticated Kalshi market data
  KALSHI_PRIVATE_KEY    — base64-encoded RSA private key PEM
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests package not installed. Run: pip install requests")
    sys.exit(1)


CONTENT_DIR = Path(__file__).parent.parent / "src" / "content" / "markets"

KALSHI_REFERRAL = "https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=odds-page&utm_campaign=signup"
POLYMARKET_REFERRAL = "https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=odds-page&utm_campaign=signup"

# Minimum thresholds
MIN_KALSHI_VOLUME = 1_000       # contracts
MIN_POLYMARKET_VOLUME = 10_000  # USD

# Category whitelist (normalized lowercase)
CATEGORY_WHITELIST = {
    "politics", "economics", "crypto", "finance", "sports",
    "tech", "entertainment", "science", "culture", "climate",
    "financial", "economy", "elections", "world", "us politics",
    "pop culture", "technology", "business", "ai",
}

# Title blocklist patterns (skip markets matching these)
TITLE_BLOCKLIST = [
    re.compile(r"(?i)adult"),
    re.compile(r"(?i)porn"),
    re.compile(r"(?i)nsfw"),
    re.compile(r"(?i)sex\b"),
    re.compile(r"(?i)onlyfans"),
    re.compile(r"(?i)death\s+of"),
    re.compile(r"(?i)assassinat"),
    re.compile(r"(?i)suicide"),
]

MAX_PAGES = 150

_BLOG_ARTICLES_CACHE: list[tuple[str, str, list[str]]] | None = None

BLOG_DIR = Path(__file__).parent.parent / "src" / "content" / "blog"


def _scan_blog_articles() -> list[tuple[str, str, list[str]]]:
    """Scan src/content/blog/*.md frontmatter for (path, title, tags).

    Results are cached at module level so repeated calls are free.
    """
    global _BLOG_ARTICLES_CACHE
    if _BLOG_ARTICLES_CACHE is not None:
        return _BLOG_ARTICLES_CACHE

    articles: list[tuple[str, str, list[str]]] = []
    if not BLOG_DIR.exists():
        _BLOG_ARTICLES_CACHE = articles
        return articles

    for md_file in sorted(BLOG_DIR.glob("*.md")):
        text = md_file.read_text(errors="replace")
        # Parse YAML frontmatter between --- fences
        fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not fm_match:
            continue
        fm_text = fm_match.group(1)

        title_m = re.search(r'^title:\s*"(.+)"', fm_text, re.MULTILINE)
        title = title_m.group(1) if title_m else md_file.stem.replace("-", " ").title()

        tags: list[str] = []
        tags_m = re.search(r'^tags:\s*\[(.+)\]', fm_text, re.MULTILINE)
        if tags_m:
            tags = [t.strip().strip('"').strip("'") for t in tags_m.group(1).split(",")]

        slug = md_file.stem
        articles.append((f"/blog/{slug}", title, tags))

    _BLOG_ARTICLES_CACHE = articles
    return articles


# ---------------------------------------------------------------------------
# Kalshi authentication (mirrors daily_roundup.py)
# ---------------------------------------------------------------------------

def _load_kalshi_private_key():
    try:
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return None

    key_b64 = os.environ.get("KALSHI_PRIVATE_KEY", "")
    if key_b64:
        pem_bytes = base64.b64decode(key_b64)
        return serialization.load_pem_private_key(pem_bytes, password=None)

    key_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if key_path and Path(key_path).exists():
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    return None


def _kalshi_headers(api_key: str, private_key, method: str, path: str) -> dict:
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

def fetch_kalshi_markets(limit: int = 200) -> list[dict]:
    """Fetch active markets from Kalshi API with pagination, sorted by volume."""
    api_key = os.environ.get("KALSHI_API_KEY", "")
    private_key = _load_kalshi_private_key()

    if not api_key or not private_key:
        print("  Kalshi credentials not configured, skipping")
        return []

    base_url = "https://trading-api.kalshi.com/trade-api/v2"
    path = "/trade-api/v2/markets"
    all_markets = []
    cursor = None

    while len(all_markets) < limit:
        params = {"limit": 100, "status": "open"}
        if cursor:
            params["cursor"] = cursor

        try:
            headers = _kalshi_headers(api_key, private_key, "GET", path)
            resp = requests.get(f"{base_url}/markets", headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            markets = data.get("markets", [])
            all_markets.extend(markets)
            cursor = data.get("cursor")
            if not cursor or not markets:
                break
        except Exception as e:
            print(f"  Kalshi API error: {e}")
            break

    # Sort by volume descending
    all_markets.sort(key=lambda m: m.get("volume", 0) or 0, reverse=True)

    now = datetime.now(timezone.utc)
    min_expiry = now + timedelta(days=7)

    results = []
    for m in all_markets:
        volume = m.get("volume", 0) or 0
        if volume < MIN_KALSHI_VOLUME:
            continue

        title = m.get("title", "")
        if _is_blocklisted(title):
            continue

        category = (m.get("category", "") or "").lower()
        if category and not _matches_category(category):
            continue

        close_time = m.get("close_time", "")
        if close_time:
            try:
                expiry = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                if expiry < min_expiry:
                    continue
            except ValueError:
                pass

        yes_price = m.get("yes_ask") or m.get("last_price") or 0
        no_price = m.get("no_ask") or (100 - yes_price if yes_price else 0)

        results.append({
            "platform": "kalshi",
            "title": title,
            "subtitle": m.get("subtitle", ""),
            "question": m.get("title", ""),
            "yes_price": yes_price,
            "no_price": no_price,
            "volume": volume,
            "category": m.get("category", "") or "",
            "event_ticker": m.get("event_ticker", ""),
            "ticker": m.get("ticker", ""),
            "close_time": close_time,
            "url": f"https://kalshi.com/markets/{m.get('event_ticker', '')}",
        })

        if len(results) >= limit:
            break

    return results


def fetch_polymarket_markets(limit: int = 200) -> list[dict]:
    """Fetch active markets from Polymarket Gamma API, sorted by volume."""
    url = "https://gamma-api.polymarket.com/markets"
    all_markets = []
    offset = 0
    page_size = 100

    while len(all_markets) < limit:
        params = {
            "limit": page_size,
            "offset": offset,
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            markets = resp.json()
            if not isinstance(markets, list):
                markets = markets.get("data", []) if isinstance(markets, dict) else []
            if not markets:
                break
            all_markets.extend(markets)
            offset += page_size
        except Exception as e:
            print(f"  Polymarket API error: {e}")
            break

    now = datetime.now(timezone.utc)
    min_expiry = now + timedelta(days=7)

    results = []
    for m in all_markets:
        volume = float(m.get("volume", 0) or 0)
        if volume < MIN_POLYMARKET_VOLUME:
            continue

        title = m.get("question", "") or m.get("title", "")
        if _is_blocklisted(title):
            continue

        category = (m.get("category", "") or "").lower()
        if category and not _matches_category(category):
            continue

        end_date = m.get("endDate", "")
        if end_date:
            try:
                expiry = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if expiry < min_expiry:
                    continue
            except ValueError:
                pass

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

        slug = m.get("slug", "")
        results.append({
            "platform": "polymarket",
            "title": title,
            "question": title,
            "yes_price": yes_price,
            "no_price": no_price,
            "volume": volume,
            "category": m.get("category", "") or "",
            "end_date": end_date,
            "slug": slug,
            "url": f"https://polymarket.com/event/{slug}" if slug else "",
        })

        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def _is_blocklisted(title: str) -> bool:
    return any(p.search(title) for p in TITLE_BLOCKLIST)


def _matches_category(category: str) -> bool:
    cat = category.lower().strip()
    return any(w in cat for w in CATEGORY_WHITELIST)


# ---------------------------------------------------------------------------
# Cross-platform matching
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Normalize for fuzzy matching."""
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def cross_match_markets(
    kalshi: list[dict], polymarket: list[dict], threshold: float = 0.6
) -> list[dict]:
    """Match markets across platforms. Returns unified market list.

    Each item has 'kalshi' and/or 'polymarket' sub-dicts, plus merged fields.
    """
    matched = []
    used_poly_indices = set()

    for km in kalshi:
        k_norm = _normalize_title(km["title"])
        best_match = None
        best_ratio = 0
        best_idx = -1

        for i, pm in enumerate(polymarket):
            if i in used_poly_indices:
                continue
            p_norm = _normalize_title(pm["title"])
            ratio = SequenceMatcher(None, k_norm, p_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = pm
                best_idx = i

        if best_ratio >= threshold and best_match is not None:
            used_poly_indices.add(best_idx)
            total_volume = km["volume"] + best_match["volume"]
            matched.append({
                "title": km["title"],
                "question": km.get("question", km["title"]),
                "category": km["category"] or best_match["category"],
                "kalshi": km,
                "polymarket": best_match,
                "total_volume": total_volume,
                "expiry": km.get("close_time") or best_match.get("end_date", ""),
                "multi_platform": True,
            })
        else:
            matched.append({
                "title": km["title"],
                "question": km.get("question", km["title"]),
                "category": km["category"],
                "kalshi": km,
                "polymarket": None,
                "total_volume": km["volume"],
                "expiry": km.get("close_time", ""),
                "multi_platform": False,
            })

    # Remaining unmatched polymarket
    for i, pm in enumerate(polymarket):
        if i not in used_poly_indices:
            matched.append({
                "title": pm["title"],
                "question": pm.get("question", pm["title"]),
                "category": pm["category"],
                "kalshi": None,
                "polymarket": pm,
                "total_volume": pm["volume"],
                "expiry": pm.get("end_date", ""),
                "multi_platform": False,
            })

    # Sort by total volume descending, cap at MAX_PAGES
    matched.sort(key=lambda m: m["total_volume"], reverse=True)
    return matched[:MAX_PAGES]


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s-]+", "-", s)
    s = s.strip("-")
    return s[:80]


# ---------------------------------------------------------------------------
# Body template generation
# ---------------------------------------------------------------------------

def _find_related_articles(market: dict) -> list[tuple[str, str]]:
    """Find 1-2 related blog articles based on keyword matching."""
    title_lower = market["title"].lower()
    cat_lower = (market.get("category") or "").lower()
    scored = []
    for path, label, keywords in _scan_blog_articles():
        score = sum(1 for kw in keywords if kw in title_lower or kw in cat_lower)
        if score > 0:
            scored.append((score, path, label))
    scored.sort(reverse=True)
    return [(p, l) for _, p, l in scored[:2]]


def _probability_text(yes_price: float) -> str:
    """Generate conditional text based on probability range."""
    if yes_price >= 90:
        return "is considered highly likely by the market, with odds strongly favoring a YES outcome"
    elif yes_price >= 70:
        return "is leaning likely according to market pricing, with a solid majority of traders betting YES"
    elif yes_price >= 55:
        return "is a slight favorite according to current odds, though the outcome remains uncertain"
    elif yes_price >= 45:
        return "is essentially a coin flip according to market odds, with neither outcome clearly favored"
    elif yes_price >= 30:
        return "is considered unlikely by the market, with odds leaning toward NO"
    elif yes_price >= 10:
        return "is viewed as quite unlikely by traders, with strong odds favoring a NO outcome"
    else:
        return "is considered extremely unlikely by the market, with minimal chance of a YES resolution"


def _format_volume(volume: float, platform: str) -> str:
    """Format volume with appropriate units."""
    if platform == "polymarket":
        if volume >= 1_000_000:
            return f"${volume / 1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"${volume / 1_000:.0f}K"
        return f"${volume:,.0f}"
    else:
        if volume >= 1_000_000:
            return f"{volume / 1_000_000:.1f}M contracts"
        elif volume >= 1_000:
            return f"{volume / 1_000:.0f}K contracts"
        return f"{volume:,.0f} contracts"


def generate_body(market: dict) -> str:
    """Generate markdown body for a market odds page."""
    title = market["title"]
    question = market.get("question", title)
    km = market.get("kalshi")
    pm = market.get("polymarket")

    # Pick primary odds for text
    if km and pm:
        avg_yes = (km["yes_price"] + pm["yes_price"]) / 2
    elif km:
        avg_yes = km["yes_price"]
    else:
        avg_yes = pm["yes_price"]

    prob_text = _probability_text(avg_yes)
    lines = []

    # Opening paragraph
    lines.append(
        f'**"{question}"** {prob_text}. '
        f"Here's a breakdown of the current odds across prediction market platforms, "
        f"updated as of {date.today().strftime('%B %d, %Y')}."
    )
    lines.append("")

    # Odds comparison table
    lines.append("## Current Odds")
    lines.append("")
    lines.append("| Platform | Yes | No | Volume | Trade |")
    lines.append("|----------|-----|-----|--------|-------|")

    if km:
        k_vol = _format_volume(km["volume"], "kalshi")
        k_url = km.get("url", KALSHI_REFERRAL)
        lines.append(
            f'| Kalshi | {km["yes_price"]}% | {km["no_price"]}% | {k_vol} '
            f'| [Trade on Kalshi]({KALSHI_REFERRAL}) |'
        )
    if pm:
        p_vol = _format_volume(pm["volume"], "polymarket")
        p_url = pm.get("url", POLYMARKET_REFERRAL)
        lines.append(
            f'| Polymarket | {pm["yes_price"]}% | {pm["no_price"]}% | {p_vol} '
            f'| [Trade on Polymarket]({POLYMARKET_REFERRAL}) |'
        )
    lines.append("")

    # Analysis section
    lines.append("## What the Odds Mean")
    lines.append("")

    if avg_yes >= 90:
        lines.append(
            f"At **{avg_yes:.0f}%**, the market is pricing this as a near-certainty. "
            f"However, even high-probability events can surprise — and the potential payout "
            f"for a contrarian NO position reflects that risk."
        )
    elif avg_yes >= 60:
        lines.append(
            f"At **{avg_yes:.0f}%**, the market sees this as more likely than not. "
            f"This probability reflects the collective wisdom of traders who have put real money behind their views. "
            f"The remaining uncertainty means there's still meaningful upside for contrarian positions."
        )
    elif avg_yes >= 40:
        lines.append(
            f"At **{avg_yes:.0f}%**, this market is genuinely uncertain — close to a toss-up. "
            f"These are often the most interesting markets to trade because the potential "
            f"for price movement in either direction is high."
        )
    else:
        lines.append(
            f"At **{avg_yes:.0f}%**, the market considers this outcome unlikely. "
            f"Contrarian YES positions are cheap but high-risk. If you have a strong thesis "
            f"that the market is wrong, these low-probability markets can offer outsized returns."
        )
    lines.append("")

    # Platform comparison if multi-platform
    if km and pm:
        diff = abs(km["yes_price"] - pm["yes_price"])
        lines.append("## Platform Comparison")
        lines.append("")
        if diff >= 5:
            higher = "Kalshi" if km["yes_price"] > pm["yes_price"] else "Polymarket"
            lower = "Polymarket" if higher == "Kalshi" else "Kalshi"
            lines.append(
                f"There's a **{diff:.0f} percentage point spread** between platforms — "
                f"{higher} is pricing YES higher than {lower}. Differences like this can "
                f"reflect different trader demographics, liquidity conditions, or fee structures. "
                f"Sophisticated traders often monitor both platforms for arbitrage opportunities."
            )
        else:
            lines.append(
                f"Both platforms are closely aligned on this market, with only a "
                f"**{diff:.1f} percentage point** difference in YES pricing. "
                f"This consensus suggests the market has efficiently priced this event."
            )
        lines.append("")

    # How to trade section
    lines.append("## How to Trade This Market")
    lines.append("")
    if km:
        lines.append(
            f"On **[Kalshi]({KALSHI_REFERRAL})**, you can buy YES or NO contracts "
            f"denominated in cents (1-99). Kalshi is CFTC-regulated and available to US residents. "
            f"Contracts settle at $1 if the event occurs, $0 if it doesn't."
        )
        lines.append("")
    if pm:
        lines.append(
            f"On **[Polymarket]({POLYMARKET_REFERRAL})**, you trade using USDC on the Polygon blockchain. "
            f"Polymarket offers deep liquidity and a wide range of markets on current events."
        )
        lines.append("")

    # Related articles
    related = _find_related_articles(market)
    if related:
        lines.append("## Learn More")
        lines.append("")
        for path, label in related:
            lines.append(f"- [{label}]({path})")
        lines.append("")

    # FAQ section for schema.org
    lines.append("## Frequently Asked Questions")
    lines.append("")
    lines.append(f"### What are the current odds for \"{question}\"?")
    lines.append("")
    if km and pm:
        lines.append(
            f"As of {date.today().strftime('%B %d, %Y')}, Kalshi prices YES at {km['yes_price']}% "
            f"and Polymarket prices YES at {pm['yes_price']}%. These odds are based on real-money "
            f"trading activity."
        )
    elif km:
        lines.append(
            f"As of {date.today().strftime('%B %d, %Y')}, Kalshi prices YES at {km['yes_price']}%. "
            f"This is based on real-money trading activity."
        )
    else:
        lines.append(
            f"As of {date.today().strftime('%B %d, %Y')}, Polymarket prices YES at {pm['yes_price']}%. "
            f"This is based on real-money trading activity."
        )
    lines.append("")
    lines.append("### Where can I trade on this prediction market?")
    lines.append("")
    platforms = []
    if km:
        platforms.append(f"[Kalshi]({KALSHI_REFERRAL}) (US-regulated)")
    if pm:
        platforms.append(f"[Polymarket]({POLYMARKET_REFERRAL}) (crypto-based)")
    lines.append(f'You can trade this market on {" and ".join(platforms)}.')
    lines.append("")
    lines.append("### How do prediction market odds work?")
    lines.append("")
    lines.append(
        "Prediction market prices represent the market's implied probability of an event occurring. "
        "A YES price of 75% means traders collectively believe there's a 75% chance the event will happen. "
        "You can buy YES (betting it will happen) or NO (betting it won't) and profit if you're correct."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown file generation
# ---------------------------------------------------------------------------

def _parse_expiry(expiry_str: str) -> str:
    """Parse expiry date to YYYY-MM-DD format."""
    if not expiry_str:
        return ""
    try:
        dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _categorize(raw_category: str, title: str = "") -> str:
    """Normalize category to site taxonomy, falling back to title-based inference."""
    cat = raw_category.lower().strip()
    mapping = {
        "us politics": "politics",
        "elections": "politics",
        "world": "politics",
        "financial": "finance",
        "economy": "economics",
        "business": "finance",
        "ai": "tech",
        "technology": "tech",
        "pop culture": "entertainment",
        "culture": "entertainment",
        "climate": "science",
    }
    # Try direct mapping first
    if cat:
        mapped = mapping.get(cat, cat)
        # Verify it's a valid site category
        valid = {"politics", "economics", "crypto", "finance", "sports", "tech", "entertainment", "science"}
        if mapped in valid:
            return mapped

    # Infer from title keywords — use word-boundary regex for short terms
    t = title.lower()

    def _match(kw: str) -> bool:
        if len(kw) <= 4:
            return bool(re.search(r'\b' + re.escape(kw) + r'\b', t))
        return kw in t

    title_rules = [
        (["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "coinbase",
          "mexc", "backpack", "fdv", "usdai", "blockchain", "defi"], "crypto"),
        (["nba", "nfl", "nhl", "mlb", "f1", "masters", "ligue", "premier league",
          "champions league", "world cup", "mavericks", "bucks", "lakers", "celtics",
          "commanders", "rookie of the year", "tiger woods", "hamilton", "lorient",
          "super bowl"], "sports"),
        (["oscar", "academy award", "emmy", "grammy", "golden globe", "best picture",
          "best actor", "best actress", "best director", "best supporting",
          "best costume", "fanning", "elordi", "frankenstein"], "entertainment"),
        (["gdp", "cpi", "inflation", "interest rate", "bank of japan", "fed rate",
          "unemployment", "jobs report", "economic"], "economics"),
        (["stock", "s&p", "spx", "nasdaq", "ipo", "market cap", "tesla deliver",
          "gold", "merger", "alphabet", "discord"], "finance"),
        (["tweet", "elon musk", "spacex"], "tech"),
        (["weather", "snow", "temperature", "hurricane", "rainfall"], "science"),
        (["president", "prime minister", "election", "parliament", "coup",
          "nuclear", "strike", "abraham accords", "putin", "trump", "iran",
          "ukraine", "russia", "venezuela", "colombia", "mexico", "morocco",
          "syria", "israel"], "politics"),
    ]
    for keywords, category in title_rules:
        if any(_match(kw) for kw in keywords):
            return category

    return "politics"


def _generate_tags(market: dict) -> list[str]:
    """Generate tags from market data."""
    tags = set()
    title_lower = market["title"].lower()
    category = market.get("category", "").lower()

    # Platform tags
    if market.get("kalshi"):
        tags.add("kalshi")
    if market.get("polymarket"):
        tags.add("polymarket")

    # Category tag
    norm_cat = _categorize(category, title_lower)
    tags.add(norm_cat)

    # Keyword-based tags
    keyword_tags = {
        "bitcoin": "bitcoin", "btc": "bitcoin", "ethereum": "ethereum", "eth": "ethereum",
        "crypto": "crypto", "trump": "trump", "election": "elections",
        "fed": "federal-reserve", "interest rate": "interest-rates", "rate cut": "interest-rates",
        "s&p": "stocks", "spx": "stocks", "stock": "stocks", "nasdaq": "stocks",
        "gdp": "economics", "inflation": "economics", "cpi": "economics",
        "weather": "weather", "temperature": "weather",
        "ai": "ai", "openai": "ai", "chatgpt": "ai",
        "super bowl": "sports", "nfl": "sports", "nba": "sports",
        "oscar": "entertainment", "emmy": "entertainment",
    }
    for keyword, tag in keyword_tags.items():
        if keyword in title_lower:
            tags.add(tag)

    return sorted(tags)


def _yaml_escape(s: str) -> str:
    """Escape a string for use inside YAML double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate_page(market: dict) -> tuple[str, str]:
    """Generate a markdown page for a market. Returns (filename, content)."""
    title = market["title"]
    slug = slugify(title)
    question = market.get("question", title)
    category = _categorize(market.get("category", ""), title)
    tags = _generate_tags(market)
    today = date.today().isoformat()

    km = market.get("kalshi")
    pm = market.get("polymarket")

    # SEO description (no quotes in description to avoid YAML issues)
    if km and pm:
        avg_yes = (km["yes_price"] + pm["yes_price"]) / 2
        desc = (
            f"Current odds for {question} — "
            f"Kalshi: {km['yes_price']}% YES, Polymarket: {pm['yes_price']}% YES. "
            f"Compare prices and trade."
        )
    elif km:
        desc = f"Current odds for {question} on Kalshi — {km['yes_price']}% YES. Live market data and analysis."
    else:
        desc = f"Current odds for {question} on Polymarket — {pm['yes_price']}% YES. Live market data and analysis."

    # Truncate description to 160 chars
    if len(desc) > 160:
        desc = desc[:157] + "..."

    # Expiry date
    expiry = _parse_expiry(market.get("expiry", ""))

    # Build frontmatter — escape all strings for YAML safety
    tags_yaml = ", ".join(f'"{t}"' for t in tags)
    fm_lines = [
        "---",
        f'title: "{_yaml_escape(title)}"',
        f'description: "{_yaml_escape(desc)}"',
        f'marketQuestion: "{_yaml_escape(question)}"',
        f'category: "{category}"',
        f'status: "active"',
        f"lastUpdated: {today}",
    ]
    if expiry:
        fm_lines.append(f"expiryDate: {expiry}")
    fm_lines.append(f"tags: [{tags_yaml}]")

    if km:
        fm_lines.append(f"kalshiYes: {km['yes_price']}")
        fm_lines.append(f"kalshiNo: {km['no_price']}")
        fm_lines.append(f"kalshiVolume: {int(km['volume'])}")
        fm_lines.append(f'kalshiUrl: "{km.get("url", "")}"')
    if pm:
        fm_lines.append(f"polymarketYes: {pm['yes_price']}")
        fm_lines.append(f"polymarketNo: {pm['no_price']}")
        fm_lines.append(f"polymarketVolume: {int(pm['volume'])}")
        fm_lines.append(f'polymarketUrl: "{pm.get("url", "")}"')

    fm_lines.append("---")

    frontmatter = "\n".join(fm_lines)
    body = generate_body(market)

    content = f"{frontmatter}\n\n{body}\n"
    filename = f"{slug}.md"

    return filename, content


# ---------------------------------------------------------------------------
# Settled market handling
# ---------------------------------------------------------------------------

def update_settled_markets(kalshi_markets: list[dict], poly_markets: list[dict]):
    """Check existing pages and mark settled markets."""
    if not CONTENT_DIR.exists():
        return

    active_titles_lower = set()
    for m in kalshi_markets:
        active_titles_lower.add(m["title"].lower().strip())
    for m in poly_markets:
        active_titles_lower.add(m["title"].lower().strip())

    for md_file in CONTENT_DIR.glob("*.md"):
        content = md_file.read_text()
        # Check if already settled
        if 'status: "settled"' in content:
            continue

        # Extract title from frontmatter
        title_match = re.search(r'^title:\s*"(.+)"', content, re.MULTILINE)
        if not title_match:
            continue

        title = title_match.group(1).lower().strip()
        if title not in active_titles_lower:
            # Market no longer active — mark as settled
            today = date.today().isoformat()
            content = content.replace('status: "active"', 'status: "settled"')
            content = re.sub(
                r"lastUpdated: .+",
                f"lastUpdated: {today}",
                content,
            )
            md_file.write_text(content)
            print(f"  Settled: {md_file.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate SEO odds pages")
    parser.add_argument(
        "--update-only", action="store_true",
        help="Only refresh odds on existing pages, don't create new ones",
    )
    args = parser.parse_args()

    print("Generating odds pages...")

    # Step 1: Fetch market data
    print("  Fetching Kalshi markets...")
    kalshi = fetch_kalshi_markets(limit=200)
    print(f"  Got {len(kalshi)} Kalshi markets (filtered)")

    print("  Fetching Polymarket markets...")
    poly = fetch_polymarket_markets(limit=200)
    print(f"  Got {len(poly)} Polymarket markets (filtered)")

    if not kalshi and not poly:
        print("ERROR: Both APIs returned no data. Exiting.")
        sys.exit(0)

    # Step 2: Cross-match
    print("  Cross-matching markets...")
    unified = cross_match_markets(kalshi, poly)
    print(f"  {len(unified)} unified markets ({sum(1 for m in unified if m['multi_platform'])} cross-platform)")

    # Step 3: Update settled markets
    print("  Checking for settled markets...")
    update_settled_markets(kalshi, poly)

    # Step 4: Generate pages
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    if args.update_only:
        # Only update existing files
        existing_slugs = {f.stem for f in CONTENT_DIR.glob("*.md")}
        count = 0
        for market in unified:
            slug = slugify(market["title"])
            if slug in existing_slugs:
                filename, content = generate_page(market)
                (CONTENT_DIR / filename).write_text(content)
                count += 1
        print(f"  Updated {count} existing pages")
    else:
        count = 0
        for market in unified:
            filename, content = generate_page(market)
            (CONTENT_DIR / filename).write_text(content)
            count += 1
        print(f"  Generated {count} pages")

    print(f"Done! Pages in: {CONTENT_DIR}")


if __name__ == "__main__":
    main()
