#!/usr/bin/env python3
"""
Submit new/updated blog URLs to search engines via IndexNow.

IndexNow instantly notifies Bing, Yandex, and participating search engines
about new or updated content. Google is testing support.

Usage:
  python scripts/submit_indexnow.py                    # auto-detect new posts from git
  python scripts/submit_indexnow.py --urls url1 url2   # submit specific URLs
  python scripts/submit_indexnow.py --sitemap           # submit full sitemap URL
  python scripts/submit_indexnow.py --dry-run           # preview without submitting
"""

import argparse
import json
import ssl
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = None

SITE_URL = "https://masterpredictionmarkets.com"
INDEXNOW_KEY = "5b9796dc9230cb4c802f0f3b9e93b956"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"


def get_new_blog_urls() -> list[str]:
    """Detect new/modified blog posts from recent git changes."""
    urls = []

    # Check staged + last commit for new blog files
    try:
        # Files changed in the last commit
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        changed_files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Also check unstaged changes
        result2 = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        changed_files += result2.stdout.strip().split("\n") if result2.stdout.strip() else []

        for f in changed_files:
            if f.startswith("src/content/blog/") and f.endswith(".md"):
                slug = Path(f).stem
                urls.append(f"{SITE_URL}/blog/{slug}/")
            elif f.startswith("src/content/markets/") and f.endswith(".md"):
                slug = Path(f).stem
                urls.append(f"{SITE_URL}/odds/{slug}/")

    except Exception as e:
        print(f"Warning: Could not detect git changes: {e}")

    return list(set(urls))


def submit_urls(urls: list[str], dry_run: bool = False) -> bool:
    """Submit URLs to IndexNow API."""
    if not urls:
        print("No URLs to submit.")
        return True

    print(f"\nSubmitting {len(urls)} URL(s) to IndexNow:")
    for url in urls:
        print(f"  → {url}")

    if dry_run:
        print("\n[DRY RUN] Would submit to IndexNow. Skipping.")
        return True

    payload = {
        "host": "masterpredictionmarkets.com",
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls,
    }

    try:
        req = Request(
            INDEXNOW_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        response = urlopen(req, timeout=10, context=SSL_CONTEXT)
        status = response.getcode()

        if status in (200, 202):
            print(f"\nIndexNow accepted ({status}). URLs queued for indexing.")
            return True
        else:
            print(f"\nIndexNow returned unexpected status: {status}")
            return False

    except URLError as e:
        print(f"\nIndexNow submission failed: {e}")
        return False


def submit_sitemap(dry_run: bool = False) -> bool:
    """Ping search engines with sitemap URL."""
    sitemap_url = f"{SITE_URL}/sitemap-index.xml"
    ping_urls = [
        f"https://www.bing.com/indexnow?url={sitemap_url}&key={INDEXNOW_KEY}",
    ]

    print(f"\nPinging sitemap: {sitemap_url}")

    if dry_run:
        print("[DRY RUN] Would ping search engines. Skipping.")
        return True

    for ping_url in ping_urls:
        try:
            req = Request(ping_url, method="GET")
            response = urlopen(req, timeout=10, context=SSL_CONTEXT)
            print(f"  Bing: {response.getcode()}")
        except URLError as e:
            print(f"  Bing failed: {e}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Submit URLs to IndexNow for fast indexing")
    parser.add_argument("--urls", nargs="+", help="Specific URLs to submit")
    parser.add_argument("--sitemap", action="store_true", help="Ping sitemap instead of individual URLs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without submitting")
    args = parser.parse_args()

    print(f"IndexNow URL Submission — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    if args.sitemap:
        submit_sitemap(dry_run=args.dry_run)
    elif args.urls:
        submit_urls(args.urls, dry_run=args.dry_run)
    else:
        # Auto-detect from git
        urls = get_new_blog_urls()
        if urls:
            submit_urls(urls, dry_run=args.dry_run)
        else:
            print("No new blog URLs detected in recent git changes.")
            # Still ping sitemap as fallback
            submit_sitemap(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
