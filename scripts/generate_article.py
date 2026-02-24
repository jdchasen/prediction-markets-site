#!/usr/bin/env python3
from __future__ import annotations
"""
Content generation pipeline for Master Prediction Markets.

Usage:
  Single article:
    python generate_article.py --topic "How to Trade Weather Markets on Kalshi" \
                               --category kalshi \
                               --words 2000

  Batch mode (CSV):
    python generate_article.py --csv keywords.csv

CSV format:
  topic,category,words,affiliate[,market_url]
  "How to Trade Weather Markets on Kalshi",kalshi,2000,kalshi
  "Polymarket Guide for Beginners",polymarket,1500,polymarket
  "Will Bitcoin Hit $75K?",strategies,1500,kalshi,will-bitcoin-reach-75000-by-december-31-2026
"""

import argparse
import csv
import os
import re
import sys
from datetime import date
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

CONTENT_DIR = Path(__file__).parent.parent / "src" / "content" / "blog"
SITE_URL = "https://masterpredictionmarkets.com"

SYSTEM_PROMPT = """You are an expert content writer for Master Prediction Markets, a site about prediction markets (Kalshi, Polymarket, event contracts). You write authoritative, SEO-optimized articles backed by real trading experience.

Writing guidelines:
- Write in a professional but accessible tone — like a knowledgeable friend explaining to a smart beginner
- Use concrete examples and specific numbers where possible
- Structure articles with clear H2 and H3 headings for scanability
- Include actionable takeaways — readers should learn something they can apply
- Naturally incorporate the target keyword in the title, first paragraph, headings, and throughout
- Do NOT use generic filler or fluff. Every paragraph should provide value.
- Do NOT start the article with the title — just begin with an engaging opening paragraph
- Use markdown formatting: **bold** for emphasis, bullet lists where appropriate
- End with a clear conclusion/summary section

You are writing from the perspective of active prediction market traders who run automated trading systems. Reference real market mechanics, platform features, and trading concepts accurately."""

ARTICLE_PROMPT = """Write a {words}-word SEO article for the topic: "{topic}"

Category: {category}
Target keyword: {keyword}

Requirements:
1. Start with an engaging opening paragraph that naturally includes the target keyword
2. Use 4-6 H2 sections with descriptive headings that include related keywords
3. Include H3 subsections where it aids readability
4. Where relevant, mention specific platform features, market types, or trading concepts
5. Include a "Key Takeaways" or "Bottom Line" section near the end
6. Do NOT include a title line — just the article body in markdown
7. Do NOT include frontmatter — just the article content
8. Aim for exactly {words} words
{market_url_instruction}
Write the article now in markdown:"""


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def extract_keyword(topic: str) -> str:
    """Extract primary keyword from topic (simplified)."""
    # Remove common filler words for keyword extraction
    stop_words = {'how', 'to', 'the', 'a', 'an', 'is', 'are', 'what', 'why',
                  'in', 'on', 'for', 'with', 'your', 'complete', 'guide',
                  'ultimate', 'best', 'top'}
    words = topic.lower().split()
    keywords = [w for w in words if w not in stop_words]
    return ' '.join(keywords[:4])


def generate_article(
    topic: str,
    category: str,
    words: int = 1500,
    affiliate: str | None = None,
    tags: list[str] | None = None,
    market_url: str | None = None,
) -> tuple[str, str]:
    """Generate an article using the Claude API.

    Returns (filename, full_markdown_with_frontmatter).
    """
    client = anthropic.Anthropic()
    keyword = extract_keyword(topic)

    market_url_instruction = ""
    if market_url:
        urls = [u.strip() for u in market_url.split("|")]
        links = " and ".join(f"{SITE_URL}/odds/{u}" for u in urls)
        market_url_instruction = f"\n9. Naturally include a link to the live odds page(s): {links} — weave it into the article body (e.g. \"check the latest odds\" or \"see current market pricing\"), don't just drop a raw URL."

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": ARTICLE_PROMPT.format(
                words=words,
                topic=topic,
                category=category,
                keyword=keyword,
                market_url_instruction=market_url_instruction,
            ),
        }],
    )

    body = message.content[0].text.strip()

    # Generate SEO meta description
    meta_msg = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f'Write a 150-character SEO meta description for this article titled "{topic}". Output ONLY the description, no quotes or labels.',
        }],
    )
    description = meta_msg.content[0].text.strip().strip('"')

    # Auto-detect tags from content if not provided
    if not tags:
        tags = [category]
        tag_candidates = {
            'kalshi': 'kalshi', 'polymarket': 'polymarket', 'weather': 'weather',
            'crypto': 'crypto', 'api': 'api', 'automated': 'automation',
            'strategy': 'strategies', 'beginner': 'beginners', 'pricing': 'pricing',
            'probability': 'probability', 'sports': 'sports', 'election': 'politics',
            'economic': 'economics',
        }
        body_lower = body.lower()
        for keyword_tag, tag_value in tag_candidates.items():
            if keyword_tag in body_lower and tag_value not in tags:
                tags.append(tag_value)
        tags = tags[:5]  # Limit to 5 tags

    # Build frontmatter
    slug = slugify(topic)
    today = date.today().isoformat()
    tags_yaml = ', '.join(f'"{t}"' for t in tags)

    frontmatter = f"""---
title: "{topic}"
description: "{description}"
pubDate: {today}
category: "{category}"
tags: [{tags_yaml}]
affiliate: "{affiliate or category}"
---"""

    full_content = f"{frontmatter}\n\n{body}\n"
    filename = f"{slug}.md"

    return filename, full_content


def save_article(filename: str, content: str) -> Path:
    """Save article to the content directory."""
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CONTENT_DIR / filename
    filepath.write_text(content)
    return filepath


def process_csv(csv_path: str) -> list[dict]:
    """Read keyword CSV and return list of article configs."""
    articles = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            config = {
                'topic': row['topic'].strip(),
                'category': row['category'].strip(),
                'words': int(row.get('words', 1500)),
                'affiliate': row.get('affiliate', '').strip() or None,
            }
            if row.get('market_url', '').strip():
                config['market_url'] = row['market_url'].strip()
            articles.append(config)
    return articles


def main():
    parser = argparse.ArgumentParser(description='Generate SEO articles for Master Prediction Markets')
    parser.add_argument('--topic', type=str, help='Article topic/title')
    parser.add_argument('--category', type=str, choices=['kalshi', 'polymarket', 'strategies', 'beginners'],
                        help='Article category')
    parser.add_argument('--words', type=int, default=1500, help='Target word count (default: 1500)')
    parser.add_argument('--affiliate', type=str, help='Affiliate platform for CTAs')
    parser.add_argument('--csv', type=str, help='Path to CSV file for batch generation')
    parser.add_argument('--dry-run', action='store_true', help='Print config without generating')

    args = parser.parse_args()

    if args.csv:
        articles = process_csv(args.csv)
    elif args.topic and args.category:
        articles = [{
            'topic': args.topic,
            'category': args.category,
            'words': args.words,
            'affiliate': args.affiliate,
        }]
    else:
        parser.error('Provide either --topic and --category, or --csv')
        return

    if args.dry_run:
        for i, a in enumerate(articles, 1):
            print(f"{i}. [{a['category']}] {a['topic']} ({a['words']} words)")
        return

    for i, a in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] Generating: {a['topic']}...")
        try:
            filename, content = generate_article(**a)
            filepath = save_article(filename, content)
            print(f"  Saved: {filepath}")
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    print(f"\nDone! Generated {len(articles)} article(s).")


if __name__ == '__main__':
    main()
