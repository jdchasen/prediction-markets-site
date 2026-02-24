#!/usr/bin/env python3
"""
Weekly Newsletter — sends a digest of the past week's Daily Market Pulse articles.

Scans src/content/blog/daily-market-pulse-*.md for the past 7 days, generates
a newsletter subject + HTML body via Claude API, and sends via Buttondown API.

Usage:
  python scripts/send_newsletter.py                  # creates draft in Buttondown
  python scripts/send_newsletter.py --dry-run        # prints HTML, does not send
  python scripts/send_newsletter.py --send-immediately  # sends immediately (no draft)

Environment variables:
  ANTHROPIC_API_KEY    — required for newsletter generation
  BUTTONDOWN_API_KEY   — required for sending (not needed with --dry-run)
"""

import argparse
import os
import re
import sys
from datetime import date, timedelta
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
SITE_URL = "https://masterpredictionmarkets.com"


def find_weekly_articles(end_date: date, days: int = 7) -> list[dict]:
    """Find daily-market-pulse articles from the past `days` days."""
    articles = []
    for i in range(days):
        d = end_date - timedelta(days=i)
        filename = f"daily-market-pulse-{d.isoformat()}.md"
        filepath = CONTENT_DIR / filename
        if filepath.exists():
            text = filepath.read_text()
            # Extract frontmatter fields
            title = ""
            description = ""
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                t = re.search(r'^title:\s*"(.+?)"', fm, re.MULTILINE)
                if t:
                    title = t.group(1)
                d_match = re.search(r'^description:\s*"(.+?)"', fm, re.MULTILINE)
                if d_match:
                    description = d_match.group(1)

            # Body is everything after frontmatter
            body = text[fm_match.end():].strip() if fm_match else text.strip()

            slug = filename.replace(".md", "")
            articles.append({
                "date": d,
                "title": title,
                "description": description,
                "body": body,
                "url": f"{SITE_URL}/blog/{slug}",
            })

    # Sort oldest first
    articles.sort(key=lambda a: a["date"])
    return articles


def generate_newsletter(articles: list[dict]) -> tuple[str, str]:
    """Generate newsletter subject line and HTML body via Claude API.

    Returns (subject, html_body).
    """
    start = articles[0]["date"].strftime("%b %d")
    end = articles[-1]["date"].strftime("%b %d, %Y")

    # Build summaries for the prompt
    summaries = []
    for a in articles:
        # Truncate body to keep prompt manageable
        body_preview = a["body"][:1500]
        summaries.append(
            f"### {a['title']} ({a['date'].strftime('%A, %b %d')})\n"
            f"URL: {a['url']}\n"
            f"{body_preview}\n"
        )

    articles_text = "\n---\n".join(summaries)

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=(
            "You are a newsletter writer for Master Prediction Markets "
            "(masterpredictionmarkets.com). Write concise, data-driven "
            "weekly digests that highlight the most interesting prediction "
            "market moves. Professional but approachable tone."
        ),
        messages=[{
            "role": "user",
            "content": f"""Write a weekly newsletter digest covering {start} – {end}.

ARTICLES FROM THIS WEEK:
{articles_text}

REQUIREMENTS:
1. Subject line: "Weekly Prediction Markets Digest: {start} – {end}" followed by a dash and the week's top story in a few words
2. HTML email body (simple, inline-styled HTML — no external CSS):
   - Brief 2-3 sentence intro summarizing the week
   - For each article, include: linked title, 1-2 sentence summary with a specific data point
   - End with a brief sign-off and link to the site
   - Use inline styles only. Keep it clean and readable.
   - Link color: #2563eb (brand blue)
3. Output format:
   SUBJECT: [subject line]
   ---
   [HTML body]
""",
        }],
    )

    text = message.content[0].text.strip()

    # Parse subject and body
    subject = ""
    html_body = text
    if text.startswith("SUBJECT:"):
        parts = text.split("---", 1)
        subject = parts[0].replace("SUBJECT:", "").strip()
        html_body = parts[1].strip() if len(parts) > 1 else ""
    else:
        subject = f"Weekly Prediction Markets Digest: {start} – {end}"

    return subject, html_body


def send_via_buttondown(
    subject: str,
    html_body: str,
    send_immediately: bool = False,
) -> bool:
    """Send newsletter via Buttondown API. Returns True on success."""
    api_key = os.environ.get("BUTTONDOWN_API_KEY", "")
    if not api_key:
        print("Error: BUTTONDOWN_API_KEY not set")
        return False

    payload = {
        "subject": subject,
        "body": html_body,
        "status": "draft",
    }
    if send_immediately:
        payload["status"] = "about_to_send"

    resp = requests.post(
        "https://api.buttondown.com/v1/emails",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        status = "sent" if send_immediately else "saved as draft"
        print(f"  Newsletter {status} in Buttondown")
        return True
    else:
        print(f"  Buttondown API error {resp.status_code}: {resp.text}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send weekly prediction markets newsletter")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate newsletter but do not send",
    )
    parser.add_argument(
        "--send-immediately", action="store_true",
        help="Send immediately instead of saving as draft",
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    end_date = date.fromisoformat(args.date) if args.date else date.today()

    print(f"Looking for articles from {(end_date - timedelta(days=6)).isoformat()} to {end_date.isoformat()}...")
    articles = find_weekly_articles(end_date)

    if not articles:
        print("No daily pulse articles found for this week. Nothing to send.")
        sys.exit(0)

    print(f"  Found {len(articles)} article(s)")

    print("  Generating newsletter via Claude API...")
    subject, html_body = generate_newsletter(articles)
    print(f"  Subject: {subject}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Subject: {subject}\n")
        print(html_body)
        print("--- END DRY RUN ---")
        return

    success = send_via_buttondown(subject, html_body, args.send_immediately)
    if not success:
        sys.exit(1)

    print("Done!")


if __name__ == "__main__":
    main()
