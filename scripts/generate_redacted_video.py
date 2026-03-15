#!/usr/bin/env python3
"""
Generate Redacted Video Data — declassified government secrets & proven conspiracies.

Each video covers ONE real government program/event with 4 narrative beats:
  1. The Secret — what was hidden
  2. The Evidence — documents, testimony, proof
  3. The Cover-Up — how it was concealed
  4. The Truth — what we now know

ONLY covers programs/events with REAL declassified documents or confirmed
government admissions. NO speculation, NO unproven theories.

Usage:
  python scripts/generate_redacted_video.py                    # generate JSON
  python scripts/generate_redacted_video.py --render            # generate + render
  python scripts/generate_redacted_video.py --dry-run           # print JSON, don't save
  python scripts/generate_redacted_video.py --topic mkultra     # specific category
  python scripts/generate_redacted_video.py --no-images         # skip DALL-E
  python scripts/generate_redacted_video.py --list-used         # show previously used topics

Categories:
  mkultra, paperclip, cointelpro, tuskegee, gulf_of_tonkin,
  area51_declassified, nsa_surveillance, iran_contra,
  project_mockingbird, operation_northwoods

Environment variables (in .env):
  ANTHROPIC_API_KEY     — required for content generation
  OPENAI_API_KEY        — required for DALL-E image generation
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from datetime import date
from pathlib import Path

import requests

# Load .env from project root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("Warning: openai package not installed. DALL-E images will be skipped.")
    OpenAI = None  # type: ignore

OUTPUT_DIR = Path(__file__).parent.parent / "video" / "data"
IMAGE_DIR = Path(__file__).parent.parent / "video" / "public" / "images" / "redacted"
USED_TOPICS_FILE = Path(__file__).parent / "redacted_used_topics.json"

TOPIC_CATEGORIES = [
    "mkultra",
    "paperclip",
    "cointelpro",
    "tuskegee",
    "gulf_of_tonkin",
    "area51_declassified",
    "nsa_surveillance",
    "iran_contra",
    "project_mockingbird",
    "operation_northwoods",
]

CATEGORY_DESCRIPTIONS = {
    "mkultra": (
        "CIA's MK-Ultra program — mind control experiments, LSD testing on unwitting "
        "subjects, university research programs, and the mass document destruction in 1973. "
        "Pick a SPECIFIC sub-program, experiment, or victim — not the general overview."
    ),
    "paperclip": (
        "Operation Paperclip — the US recruitment of Nazi scientists after WWII. "
        "Whitewashed war crime records, scientists who built the US space program, "
        "and the ethical compromises made in the name of the Cold War."
    ),
    "cointelpro": (
        "FBI's COINTELPRO — illegal surveillance and disruption of civil rights groups, "
        "anti-war movements, and political organizations in the 1950s-1970s. "
        "Infiltration, blackmail, and assassination attempts."
    ),
    "tuskegee": (
        "The Tuskegee syphilis experiment — the US government's 40-year study that "
        "deliberately withheld treatment from Black men with syphilis. "
        "The cover-up, the whistleblower, and the aftermath."
    ),
    "gulf_of_tonkin": (
        "The Gulf of Tonkin incident — the fabricated attack that justified the "
        "Vietnam War. Declassified NSA documents proving the second attack never happened."
    ),
    "area51_declassified": (
        "Area 51 — what was ACTUALLY being tested there according to declassified CIA "
        "documents. U-2 spy planes, OXCART program, nuclear testing, and why the "
        "government let UFO rumors persist as cover."
    ),
    "nsa_surveillance": (
        "NSA mass surveillance programs revealed by Snowden and others — PRISM, "
        "XKeyscore, bulk phone metadata collection. Programs that spied on millions "
        "of Americans, confirmed by declassified FISA court documents."
    ),
    "iran_contra": (
        "The Iran-Contra affair — the Reagan administration secretly sold weapons to "
        "Iran and used the profits to fund Nicaraguan rebels, in direct violation of "
        "Congressional law. Oliver North, the shredding, the pardons."
    ),
    "project_mockingbird": (
        "Operation Mockingbird — the CIA's infiltration of American media. Journalists "
        "on the CIA payroll, news stories planted by intelligence agencies, and the "
        "Church Committee revelations."
    ),
    "operation_northwoods": (
        "Operation Northwoods — the Joint Chiefs' 1962 proposal for false flag attacks "
        "on American soil to justify invading Cuba. Hijacking planes, sinking boats, "
        "bombing US cities — all signed by the Joint Chiefs, rejected by Kennedy."
    ),
}


def load_used_topics() -> list[str]:
    """Load list of previously used topic identifiers."""
    if USED_TOPICS_FILE.exists():
        try:
            data = json.loads(USED_TOPICS_FILE.read_text())
            return data.get("topics", [])
        except (json.JSONDecodeError, KeyError):
            return []
    return []


def save_used_topic(topic_id: str):
    """Append a topic identifier to the used topics log."""
    existing = load_used_topics()
    existing.append(topic_id)
    existing = existing[-500:]
    USED_TOPICS_FILE.write_text(json.dumps({"topics": existing}, indent=2))


def pick_category(explicit: str | None = None) -> str:
    """Pick a topic category that hasn't been used recently."""
    if explicit:
        return explicit
    used = load_used_topics()
    # Extract base category from topic IDs (e.g. "mkultra-lsd-experiment" → "mkultra")
    used_categories = set()
    for t in used:
        for cat in TOPIC_CATEGORIES:
            if t.startswith(cat):
                used_categories.add(cat)
    available = [t for t in TOPIC_CATEGORIES if t not in used_categories]
    if not available:
        available = TOPIC_CATEGORIES
    return random.choice(available)


def generate_dalle_image(prompt: str, name: str) -> str | None:
    """Generate a classified-document-aesthetic image via DALL-E 3 (portrait 1024x1792)."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("    WARNING: OPENAI_API_KEY not set, skipping image generation")
        return None

    if OpenAI is None:
        print("    WARNING: openai package not installed, skipping")
        return None

    safe_name = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:80]
    filename = f"{safe_name}.png"
    filepath = IMAGE_DIR / filename

    if filepath.exists() and filepath.stat().st_size > 0:
        print(f"    Image cached: {filename}")
        return f"images/redacted/{filename}"

    try:
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1792",
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(img_resp.content)

        size_kb = filepath.stat().st_size / 1024
        print(f"    Generated: {filename} ({size_kb:.0f}KB)")
        return f"images/redacted/{filename}"

    except Exception as e:
        print(f"    WARNING: DALL-E generation failed for '{name}': {e}")
        return None


def generate_card_images(data: dict) -> dict:
    """Generate DALL-E 3 images for each card."""
    print("\nGenerating DALL-E images...")
    topic_id = data.get("topicId", "unknown")
    for i, card in enumerate(data.get("cards", [])):
        dalle_prompt = card.get("dallePrompt", "")
        if not dalle_prompt:
            print(f"  Card {i+1}: no dallePrompt, skipping")
            continue

        name = f"{topic_id}-card-{i}"
        print(f"  Generating image {i + 1}/{len(data['cards'])}: {dalle_prompt[:80]}...")
        path = generate_dalle_image(dalle_prompt, name)
        if path:
            card["backgroundImage"] = path
        else:
            print(f"  Card {i+1}: image generation failed")

        card.pop("dallePrompt", None)
    return data


def generate_redacted_json(
    target_date: date,
    category: str,
    used_topics: list[str],
) -> dict:
    """Use Claude to generate a declassified government secrets video script."""
    date_str = target_date.strftime("%B %d, %Y")
    date_iso = target_date.isoformat()
    category_desc = CATEGORY_DESCRIPTIONS[category]

    used_str = ""
    if used_topics:
        recent = used_topics[-100:]
        used_str = (
            "\n\nTOPICS ALREADY COVERED (do NOT repeat any of these):\n"
            + "\n".join(f"- {t}" for t in recent)
        )

    system = (
        "You are a documentary journalist creating short-form videos about declassified "
        "government programs and proven conspiracies. "
        "Tone: authoritative, matter-of-fact, letting the facts be shocking on their own. "
        "Like a news anchor reading declassified documents. "
        "ONLY cover programs and events with REAL declassified documents or confirmed "
        "government admissions. NO speculation, NO unproven theories. "
        "The truth is shocking enough — you don't need to embellish. "
        "Use precise details — document numbers, dates, names, agencies. "
        "NO filler phrases. Every sentence should make the viewer's jaw drop."
    )

    prompt = f"""Create a declassified government secrets video for: {date_str}

CATEGORY: {category.upper()}
{category_desc}

Pick ONE specific aspect, sub-program, or incident within this category.
Go deep on a SPECIFIC detail — not a general overview.
{used_str}

FORMAT: 4 cards telling ONE story:
  Card 1: THE SECRET — what was hidden, stated in one shocking sentence
  Card 2: THE EVIDENCE — the documents, testimony, or proof that exposed it
  Card 3: THE COVER-UP — how the government tried to hide it, who knew
  Card 4: THE TRUTH — what we now know, the aftermath, accountability (or lack thereof)

Each card needs:
  - "title": Beat heading (~5-8 words)
  - "stat": Key fact (e.g. "Ran For 20 Years", "80 Universities Involved", "20,000 Pages Destroyed")
  - "subtitle": One-line context
  - "emoji": relevant emoji (📂 🔒 🏛️ ⚠️ 🔍 🗂️ 📋 etc.)
  - "dallePrompt": a DALL-E 3 prompt for a classified-document-aesthetic background image.
    Style: "Dark photograph with green-tinted film grain, [government/military scene]. Surveillance camera aesthetic, harsh fluorescent lighting."
    NEVER include people, faces, or text/numbers in the image.
    Card 1: government building, laboratory, military facility exterior
    Card 2: filing cabinets, stacks of documents, microfilm reels
    Card 3: shredded documents, locked safe, empty office at night
    Card 4: congressional hearing room, press conference podium, memorial
    Keep prompts under 80 words. Images display full-screen at 1080x1920 portrait.

Top-level fields:
  - "topicId": unique identifier (e.g. "mkultra-midnight-climax", "paperclip-von-braun")
  - "hookLine": the YouTube title — max 50 characters.
    Use ONE word in ALL CAPS for emphasis.
    Pattern: "The CIA Tested LSD on UNWITTING Citizens" / "NASA Erased the ORIGINAL Moon Landing Tapes"
    Must create instant outrage or disbelief.
  - "ctaLine": "DO YOU BELIEVE THE OFFICIAL STORY?"
  - "voiceover": the full narration (see structure below)

VOICEOVER STRUCTURE — 6 paragraphs separated by \\n\\n:
  Paragraph 1: HOOK — the shocking reveal, 1-2 sentences. Hit them immediately.
  Paragraph 2: THE SECRET — what was being done, 1-2 sentences.
  Paragraph 3: THE EVIDENCE — the proof, 2 sentences max.
  Paragraph 4: THE COVER-UP — how it was hidden, 1-2 sentences.
  Paragraph 5: THE TRUTH — what we now know, 1-2 sentences.
  Paragraph 6: CTA — "Do you believe the official story? Comment below."

RULES:
1. Total voiceover: STRICTLY 100-120 words. Count carefully.
2. Written for SPEECH — spoken numbers, flowing sentences, NO lists or em-dashes
3. ONLY REAL declassified/confirmed events — no speculation
4. Use specific document references, dates, and names when possible
5. Let the facts speak — no editorializing or conspiracy theorizing

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown code fences:
{{
  "date": "{date_iso}",
  "channel": "redacted",
  "category": "{category}",
  "topicId": "unique-topic-identifier",
  "hookLine": "The CIA Tested LSD on UNWITTING Citizens",
  "cards": [
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "📂",
      "dallePrompt": "Dark photograph with green-tinted film grain, [scene]. Surveillance camera aesthetic, harsh fluorescent lighting."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "dallePrompt": "Dark photograph with green-tinted film grain, [scene]. Surveillance camera aesthetic, harsh fluorescent lighting."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔒",
      "dallePrompt": "Dark photograph with green-tinted film grain, [scene]. Surveillance camera aesthetic, harsh fluorescent lighting."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🏛️",
      "dallePrompt": "Dark photograph with green-tinted film grain, [scene]. Surveillance camera aesthetic, harsh fluorescent lighting."
    }}
  ],
  "ctaLine": "DO YOU BELIEVE THE OFFICIAL STORY?",
  "voiceover": "Hook\\n\\nSecret\\n\\nEvidence\\n\\nCoverUp\\n\\nTruth\\n\\nDo you believe the official story? Comment below."
}}

CRITICAL:
- Exactly 4 cards, exactly 6 voiceover paragraphs
- STRICTLY 100-120 words total
- ONLY REAL declassified/confirmed events
- Every claim must be verifiable with real documents"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    if response_text.startswith("```"):
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Claude returned invalid JSON: {e}")
        print(f"Response:\n{response_text[:500]}")
        sys.exit(1)

    required_keys = ["date", "channel", "hookLine", "cards", "voiceover"]
    for key in required_keys:
        if key not in data:
            print(f"ERROR: Missing required key '{key}' in generated data")
            sys.exit(1)

    if len(data["cards"]) != 4:
        print(f"WARNING: Expected 4 cards, got {len(data['cards'])}")

    paragraphs = [p for p in data["voiceover"].split("\n\n") if p.strip()]
    if len(paragraphs) != 6:
        print(f"WARNING: Voiceover has {len(paragraphs)} paragraphs, expected 6")

    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate Redacted video data (declassified government secrets)")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument("--topic", help="Force a specific topic category", default=None)
    parser.add_argument("--render", action="store_true", help="Also render the video")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON, don't save")
    parser.add_argument("--no-images", action="store_true", help="Skip DALL-E image generation")
    parser.add_argument("--list-used", action="store_true", help="List previously used topics")
    args = parser.parse_args()

    if args.list_used:
        used = load_used_topics()
        if not used:
            print("No topics used yet.")
        else:
            print(f"{len(used)} topics used:")
            for t in used:
                print(f"  - {t}")
        return

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    category = pick_category(args.topic)

    print(f"Generating Redacted video")
    print(f"  Date: {target_date.isoformat()}")
    print(f"  Category: {category}")
    print("=" * 60)

    used_topics = load_used_topics()
    print(f"\n  Previously used topics: {len(used_topics)}")

    print("\nGenerating script with Claude...")
    data = generate_redacted_json(target_date, category, used_topics)

    topic_id = data.get("topicId", "unknown")
    print(f"  Topic: {topic_id}")
    print(f"  Hook: {data['hookLine']}")
    print(f"  Cards:")
    for i, card in enumerate(data["cards"]):
        print(f"    {i + 1}. {card.get('emoji', '📂')} {card['title']} — {card['stat']}")

    paragraphs = data["voiceover"].split("\n\n")
    word_count = len(data["voiceover"].split())
    print(f"\n  Voiceover paragraphs: {len(paragraphs)}")
    print(f"  Voiceover words: {word_count} (~{word_count / 2.5:.0f}s spoken)")

    if args.dry_run:
        print(f"\n  [DRY RUN] Generated data:")
        print(json.dumps(data, indent=2))
        return

    if not args.no_images:
        data = generate_card_images(data)
        image_count = sum(1 for c in data["cards"] if c.get("backgroundImage"))
        print(f"\n  Images generated: {image_count}/4")
        print(f"  DALL-E cost: ${image_count * 0.06:.2f} ({image_count} × $0.06)")
    else:
        print("\nSkipping image generation (--no-images)")
        for card in data["cards"]:
            card.pop("dallePrompt", None)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"redacted-{category}-{target_date.isoformat()}"
    filename = f"{slug}.json"
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved: {output_path}")

    save_used_topic(topic_id)
    print(f"  Logged topic '{topic_id}' to used list")

    # Clean topicId from saved JSON (not needed by renderer)
    data.pop("topicId", None)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    if args.render:
        import subprocess
        print("\nRendering video...")
        video_dir = Path(__file__).parent.parent / "video"
        result = subprocess.run(
            ["npx", "tsx", "render.ts", "--topic", str(output_path)],
            cwd=str(video_dir),
            capture_output=False,
        )
        if result.returncode != 0:
            print("ERROR: Video render failed")
            sys.exit(1)

    print("\nDone!")


if __name__ == "__main__":
    main()
