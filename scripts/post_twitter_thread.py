#!/usr/bin/env python3
"""
Post a prediction markets thread to Twitter/X from a trending video JSON.

Takes the same JSON files used for video rendering and converts them into
a punchy Twitter thread with market data.

Usage:
  python scripts/post_twitter_thread.py video/data/trending-iran-war-2026-03-03.json
  python scripts/post_twitter_thread.py video/data/trending-stock-market-crash-2026-03-03.json --dry-run

Environment variables (in .env):
  TWITTER_API_KEY
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_TOKEN_SECRET
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

try:
    import tweepy
except ImportError:
    print("Error: tweepy not installed. Run: pip install tweepy")
    sys.exit(1)

# Referral links
KALSHI_REFERRAL = "https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21"
POLYMARKET_REFERRAL = "https://polymarket.us/1762"


def build_thread(data: dict) -> list[str]:
    """Convert video JSON into a list of tweets for a thread."""
    tweets = []
    markets = data.get("todayMarkets", [])
    hook = data.get("hookLine", "")
    date = data.get("date", "")

    # Tweet 1: Hook — attention grabber
    hook_tweet = f"🚨 {hook}\n\nHere's what the money says ({date}):\n\n🧵👇"
    tweets.append(hook_tweet)

    # Tweets 2-N: One per market
    for i, market in enumerate(markets):
        title = market.get("title", "")
        prob = market.get("probability", 0)
        volume = market.get("volume", "")
        platform = market.get("platform", "").capitalize()
        change = market.get("change", 0)
        resolves = market.get("resolvesAt", "")

        # Build change string
        if change > 0:
            change_str = f"(↑{change}%)"
        elif change < 0:
            change_str = f"(↓{abs(change)}%)"
        else:
            change_str = ""

        # Resolved markets
        if prob == 100:
            prob_str = "✅ RESOLVED YES"
        elif prob == 0:
            prob_str = "❌ RESOLVED NO"
        else:
            prob_str = f"{prob}% {change_str}".strip()

        tweet = f"{title}\n\n📊 {prob_str}\n💰 {volume} traded on {platform}"
        if resolves and resolves != "Resolved":
            tweet += f"\n⏰ Resolves: {resolves}"

        tweets.append(tweet)

    # Final tweet: CTA + referral links
    cta_tweet = (
        f"Trade these markets yourself:\n\n"
        f"→ Polymarket: {POLYMARKET_REFERRAL}\n"
        f"→ Kalshi: {KALSHI_REFERRAL}\n\n"
        f"Follow for daily prediction market threads."
    )
    tweets.append(cta_tweet)

    return tweets


def post_thread(tweets: list[str], dry_run: bool = False) -> list[str]:
    """Post a thread to Twitter/X. Returns list of tweet URLs."""
    if dry_run:
        print("\n=== DRY RUN — Thread preview ===\n")
        for i, tweet in enumerate(tweets):
            chars = len(tweet)
            print(f"--- Tweet {i + 1}/{len(tweets)} ({chars} chars) ---")
            print(tweet)
            print()
        return []

    # Authenticate
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("ERROR: Missing Twitter credentials in .env")
        missing = []
        if not api_key: missing.append("TWITTER_API_KEY")
        if not api_secret: missing.append("TWITTER_API_SECRET")
        if not access_token: missing.append("TWITTER_ACCESS_TOKEN")
        if not access_secret: missing.append("TWITTER_ACCESS_TOKEN_SECRET")
        print(f"  Missing: {', '.join(missing)}")
        sys.exit(1)

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )

    urls = []
    last_tweet_id = None

    for i, tweet in enumerate(tweets):
        try:
            response = client.create_tweet(
                text=tweet,
                in_reply_to_tweet_id=last_tweet_id,
            )
            tweet_id = response.data["id"]
            last_tweet_id = tweet_id
            urls.append(f"https://x.com/i/status/{tweet_id}")
            print(f"  Posted tweet {i + 1}/{len(tweets)} (id: {tweet_id})")

            # Small delay between tweets to avoid rate limits
            if i < len(tweets) - 1:
                time.sleep(1)

        except tweepy.TweepyException as e:
            print(f"ERROR posting tweet {i + 1}: {e}")
            if urls:
                print(f"  Thread started at: {urls[0]}")
            sys.exit(1)

    return urls


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Post prediction markets thread to Twitter/X")
    parser.add_argument("json_file", help="Path to trending video JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Preview thread without posting")
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"ERROR: File not found: {json_path}")
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    print(f"Building thread from: {json_path.name}")
    print(f"  Hook: {data.get('hookLine', '?')}")
    print(f"  Markets: {len(data.get('todayMarkets', []))}")

    tweets = build_thread(data)

    # Validate tweet lengths
    for i, tweet in enumerate(tweets):
        if len(tweet) > 280:
            print(f"WARNING: Tweet {i + 1} is {len(tweet)} chars (max 280)")

    if args.dry_run:
        post_thread(tweets, dry_run=True)
    else:
        print(f"\nPosting {len(tweets)}-tweet thread...")
        urls = post_thread(tweets)
        print(f"\nThread posted! {len(urls)} tweets")
        print(f"Thread URL: {urls[0]}")


if __name__ == "__main__":
    main()
