#!/usr/bin/env python3
"""
Engagement tweets for @master_mar686 — standalone script that posts
varied, data-driven tweets 5x/day to grow the account.

Usage:
  python scripts/tweet_engagement.py --slot morning       # 10 AM ET
  python scripts/tweet_engagement.py --slot midday        # 2 PM ET
  python scripts/tweet_engagement.py --slot evening       # 7 PM ET
  python scripts/tweet_engagement.py --slot morning --dry-run  # preview only

Environment variables:
  ANTHROPIC_API_KEY         — required for tweet generation
  KALSHI_API_KEY            — for Kalshi market data
  KALSHI_PRIVATE_KEY        — base64-encoded RSA private key PEM
  TWITTER_API_KEY           — required for posting
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_TOKEN_SECRET
"""

import argparse
import hashlib
import random
import sys
from datetime import date

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

# Import shared helpers from daily_roundup (same scripts/ directory)
from daily_roundup import (
    EXISTING_ARTICLES,
    fetch_kalshi_markets,
    fetch_polymarket_markets,
    post_tweet,
)

SITE_BASE = "https://masterpredictionmarkets.com"

TWEET_TYPES = [
    "market_spotlight",
    "question",
    "hot_take",
    "stat_drop",
    "article_tease",
]


def pick_tweet_type(today: date, slot: str) -> str:
    """Deterministically pick a tweet type based on date + slot.
    article_tease shows up ~20% of the time (1 out of 5 types)."""
    seed = hashlib.sha256(f"{today.isoformat()}-{slot}".encode()).hexdigest()
    idx = int(seed, 16) % len(TWEET_TYPES)
    return TWEET_TYPES[idx]


def should_include_hashtag(today: date, slot: str) -> bool:
    """Coin flip — 50% of tweets get a hashtag."""
    seed = hashlib.sha256(f"hashtag-{today.isoformat()}-{slot}".encode()).hexdigest()
    return int(seed, 16) % 2 == 0


def pick_article(today: date, slot: str) -> tuple[str, str]:
    """Pick an evergreen article deterministically."""
    seed = hashlib.sha256(f"article-{today.isoformat()}-{slot}".encode()).hexdigest()
    idx = int(seed, 16) % len(EXISTING_ARTICLES)
    path, title = EXISTING_ARTICLES[idx]
    url = f"{SITE_BASE}{path}"
    return url, title


def build_market_summary(kalshi: list[dict], poly: list[dict]) -> str:
    """Build a concise market data block for the Claude prompt."""
    lines = []
    for i, m in enumerate(kalshi[:5], 1):
        lines.append(
            f"Kalshi {i}. {m['title']}"
            + (f" — {m['subtitle']}" if m.get("subtitle") else "")
            + f" | Yes: {m['yes_price']}¢ | Vol: {m['volume']:,}"
        )
    for i, m in enumerate(poly[:5], 1):
        vol = f"${m['volume']:,.0f}" if m["volume"] > 0 else "N/A"
        lines.append(
            f"Polymarket {i}. {m['title']}"
            + f" | Yes: {m['yes_price']}¢ | Vol: {vol}"
        )
    return "\n".join(lines)


def generate_engagement_tweet(
    today: date,
    slot: str,
    kalshi: list[dict],
    poly: list[dict],
) -> str:
    """Generate a single engagement tweet via Claude API."""
    tweet_type = pick_tweet_type(today, slot)
    use_hashtag = should_include_hashtag(today, slot)
    market_data = build_market_summary(kalshi, poly)

    print(f"  Tweet type: {tweet_type}")
    print(f"  Hashtag: {'yes' if use_hashtag else 'no'}")

    # Build type-specific instructions
    type_instructions = {
        "market_spotlight": (
            "Write a MARKET SPOTLIGHT tweet. Pick one interesting market from the data "
            "and highlight it with specific numbers (price, volume, implied probability). "
            "Make it feel like a trader flagging something noteworthy to a friend. "
            "Do NOT include any URLs."
        ),
        "question": (
            "Write a QUESTION tweet. Pick a market and ask followers a question about it "
            "(e.g. 'Would you buy Yes at 34¢?' or 'What are you seeing that the market isn't?'). "
            "Include at least one specific number from the data. "
            "Do NOT include any URLs."
        ),
        "hot_take": (
            "Write a HOT TAKE tweet. Make a contrarian or sharp observation about one of "
            "these markets. Be opinionated — take a side. Reference specific prices. "
            "Sound like a trader with conviction, not a news bot. "
            "Do NOT include any URLs."
        ),
        "stat_drop": (
            "Write a STAT DROP tweet. Lead with a striking number or data point from the "
            "markets. Let the stat speak for itself — minimal commentary. "
            "Do NOT include any URLs."
        ),
        "article_tease": None,  # handled separately below
    }

    if tweet_type == "article_tease":
        article_url, article_title = pick_article(today, slot)
        print(f"  Article: {article_title}")
        type_instruction = (
            f"Write an ARTICLE TEASE tweet. Connect a live market data point to this "
            f"evergreen article: \"{article_title}\"\n"
            f"End the tweet with this exact URL on its own line: {article_url}\n"
            f"The hook should be timely (use the market data), but the article link "
            f"should feel like a natural 'if you want to go deeper' addition."
        )
    else:
        type_instruction = type_instructions[tweet_type]

    hashtag_instruction = (
        "End with exactly one hashtag: #PredictionMarkets"
        if use_hashtag
        else "Do NOT include any hashtags."
    )

    system = (
        "You are a prediction market trader who tweets about markets. "
        "Casual tone — like a sharp friend who trades, not a corporate account. "
        "No corporate speak. No 'BREAKING:' or 'ALERT:' prefixes. "
        "Sentence fragments are fine. Max 1 emoji per tweet. "
        "Never fabricate data — only use the market data provided."
    )

    prompt = (
        f"LIVE MARKET DATA:\n{market_data}\n\n"
        f"TWEET TYPE: {tweet_type.upper()}\n"
        f"{type_instruction}\n\n"
        f"{hashtag_instruction}\n\n"
        f"HARD LIMIT: The entire tweet must be under 280 characters. "
        f"Aim for 180-250 characters. Output ONLY the tweet text — no quotes, "
        f"no labels, no explanation."
    )

    client = anthropic.Anthropic()

    # First attempt
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    tweet = message.content[0].text.strip()

    # Retry once if over 280 chars
    if len(tweet) > 280:
        print(f"  First attempt too long ({len(tweet)} chars), retrying...")
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=300,
            system=system,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": tweet},
                {
                    "role": "user",
                    "content": (
                        f"That's {len(tweet)} characters — over the 280 limit. "
                        "Rewrite it shorter. Output ONLY the tweet text."
                    ),
                },
            ],
        )
        tweet = message.content[0].text.strip()

    # Final safety truncation (should rarely trigger)
    if len(tweet) > 280:
        print(f"  WARNING: Truncating from {len(tweet)} to 280 chars")
        tweet = tweet[:277] + "..."

    return tweet


def main():
    parser = argparse.ArgumentParser(description="Post engagement tweet")
    parser.add_argument(
        "--slot",
        choices=["morning", "midday", "afternoon", "evening", "night"],
        required=True,
        help="Time slot: morning, midday, or evening (afternoon/night still accepted)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview tweet without posting",
    )
    args = parser.parse_args()

    today = date.today()
    print(f"Engagement tweet for {today.isoformat()} ({args.slot} slot)")

    # Fetch live market data
    print("  Fetching Kalshi markets...")
    kalshi = fetch_kalshi_markets(limit=10)
    print(f"  Got {len(kalshi)} Kalshi markets")

    print("  Fetching Polymarket markets...")
    poly = fetch_polymarket_markets(limit=10)
    print(f"  Got {len(poly)} Polymarket markets")

    if not kalshi and not poly:
        print("ERROR: Both APIs returned no data. Skipping tweet.")
        sys.exit(0)

    # Generate tweet
    print("  Generating tweet via Claude API...")
    tweet = generate_engagement_tweet(today, args.slot, kalshi, poly)
    print(f"  Tweet ({len(tweet)} chars):\n{tweet}")

    if args.dry_run:
        print("\n  DRY RUN — tweet not posted.")
        return

    # Post it
    success = post_tweet(tweet)
    if success:
        print("Done!")
    else:
        print("WARNING: Tweet posting failed — will retry next slot.")
        # Exit 0 so CI doesn't show red on intermittent Twitter API issues
        sys.exit(0)


if __name__ == "__main__":
    main()
