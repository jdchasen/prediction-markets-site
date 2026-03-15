#!/usr/bin/env python3
"""
Generate MindTrap Video Data — dark psychology tactics & cognitive biases.

Each video covers ONE tactic in depth with 4 narrative beats:
  1. The Tactic — what it is
  2. How It Works — the psychology behind it
  3. Real-World Example — where you see it
  4. How to Defend — how to recognize and resist it

Usage:
  python scripts/generate_mindtrap_video.py                    # generate JSON
  python scripts/generate_mindtrap_video.py --render            # generate + render
  python scripts/generate_mindtrap_video.py --dry-run           # print JSON, don't save
  python scripts/generate_mindtrap_video.py --topic gaslighting # specific category
  python scripts/generate_mindtrap_video.py --no-images         # skip DALL-E

Categories:
  persuasion, gaslighting, authority_bias, social_proof, anchoring,
  scarcity, mirroring, dark_triad, love_bombing, foot_in_door,
  sunk_cost, framing

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
IMAGE_DIR = Path(__file__).parent.parent / "video" / "public" / "images" / "mindtrap"
USED_TOPICS_FILE = Path(__file__).parent.parent / "video" / "data" / ".mindtrap_used_topics.json"

TOPIC_CATEGORIES = [
    "persuasion",
    "gaslighting",
    "authority_bias",
    "social_proof",
    "anchoring",
    "scarcity",
    "mirroring",
    "dark_triad",
    "love_bombing",
    "foot_in_door",
    "sunk_cost",
    "framing",
]


def load_used_topics() -> list[str]:
    """Load previously used topic categories."""
    if USED_TOPICS_FILE.exists():
        try:
            return json.loads(USED_TOPICS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_used_topic(topic: str):
    """Save a used topic category. Resets after all categories used."""
    used = load_used_topics()
    used.append(topic)
    if len(used) >= len(TOPIC_CATEGORIES):
        used = [topic]
    USED_TOPICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_TOPICS_FILE.write_text(json.dumps(used))


def pick_topic_category(explicit: str | None = None) -> str:
    """Pick a topic category that hasn't been used recently."""
    if explicit:
        return explicit
    used = load_used_topics()
    available = [t for t in TOPIC_CATEGORIES if t not in used]
    if not available:
        available = TOPIC_CATEGORIES
    return random.choice(available)


def generate_dalle_image(prompt: str, name: str) -> str | None:
    """Generate a dark atmospheric image via DALL-E 3 (portrait 1024x1792)."""
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
        return f"images/mindtrap/{filename}"

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
        return f"images/mindtrap/{filename}"

    except Exception as e:
        print(f"    WARNING: DALL-E generation failed for '{name}': {e}")
        return None


def generate_card_images(data: dict) -> dict:
    """Generate DALL-E 3 images for each card."""
    print("\nGenerating DALL-E images...")
    topic = data.get("topic_category", "mindtrap")
    for i, card in enumerate(data.get("cards", [])):
        dalle_prompt = card.get("dallePrompt", "")
        if not dalle_prompt:
            print(f"  Card {i+1}: no dallePrompt, skipping")
            continue

        name = f"{topic}-card-{i}"
        print(f"  Generating image {i + 1}/{len(data['cards'])}: {dalle_prompt[:80]}...")
        path = generate_dalle_image(dalle_prompt, name)
        if path:
            card["backgroundImage"] = path
        else:
            print(f"  Card {i+1}: image generation failed")

        card.pop("dallePrompt", None)
    return data


def generate_mindtrap_json(
    target_date: date,
    topic_category: str,
) -> dict:
    """Use Claude to generate a dark psychology tactic video script."""
    date_str = target_date.strftime("%B %d, %Y")
    date_iso = target_date.isoformat()

    category_labels = {
        "persuasion": "persuasion techniques and influence tactics",
        "gaslighting": "gaslighting — making someone doubt their own reality",
        "authority_bias": "authority bias — why we obey without thinking",
        "social_proof": "social proof — why we follow the crowd",
        "anchoring": "anchoring — how the first number controls your decisions",
        "scarcity": "scarcity — why 'limited time' makes you buy",
        "mirroring": "mirroring — how people copy you to manipulate you",
        "dark_triad": "dark triad personalities — narcissism, Machiavellianism, psychopathy",
        "love_bombing": "love bombing — overwhelming affection as control",
        "foot_in_door": "foot-in-the-door — small yeses leading to big commitments",
        "sunk_cost": "sunk cost fallacy — why you can't walk away",
        "framing": "framing — how word choice controls your decisions",
    }
    topic_label = category_labels.get(topic_category, topic_category)

    system = (
        "You are a psychology educator creating short-form videos about dark psychology "
        "and manipulation tactics. Your goal is to teach viewers to RECOGNIZE these tactics, "
        "NOT to use them. This is educational content — like a self-defense class for the mind. "
        "Tone: measured, slightly ominous, building tension. Like you're revealing a secret. "
        "Use specific, vivid examples. Make it feel personal — 'this has happened to YOU.' "
        "NO filler phrases. Every sentence should make the viewer feel uneasy in a good way. "
        "Every tactic must be based on REAL psychology research."
    )

    prompt = f"""Create a dark psychology video for: {date_str}
Topic category: {topic_label}

Pick ONE specific tactic or bias and break it down across 4 narrative beats.

FORMAT: 4 cards telling one story:
  Card 1: THE TACTIC — name it, define it in one visceral sentence
  Card 2: HOW IT WORKS — the psychology mechanism, why your brain falls for it
  Card 3: REAL-WORLD EXAMPLE — a specific scenario where this happens (sales, relationships, politics)
  Card 4: HOW TO DEFEND — the specific counter-move to resist it

Each card needs:
  - "title": Beat heading (~5-8 words)
  - "stat": Key fact (e.g. "93% Fall For This", "Used By Every Salesperson", "3-Step Defense")
  - "subtitle": One-line context
  - "emoji": relevant emoji (🧠 🎭 ⚠️ 🛡️ 🔒 👁️ 🕸️ etc.)
  - "dallePrompt": a DALL-E 3 prompt for a dark atmospheric background image.
    Style: "Dark atmospheric photograph, [abstract representation]. Dramatic shadows, moody blue-black lighting, shallow depth of field."
    NEVER include people, faces, or text/numbers in the image.
    Keep prompts under 80 words. Images display full-screen at 1080x1920 portrait.

Top-level fields:
  - "hookLine": the YouTube title — max 50 characters.
    Use ONE word in ALL CAPS for emphasis.
    The hook MUST name a specific tactic, trick, or concrete detail — NOT a vague observation.
    Pattern: [Specific trick/word/technique] + [Shocking effect on YOU]
    GOOD: "The Word That Makes People Say YES" (specific: one word)
    GOOD: "Salespeople Use This SILENCE Trick on You" (specific: silence trick)
    GOOD: "Why a $10 Gift Makes You Spend THOUSANDS" (specific: $10 gift → spend)
    GOOD: "Narcissists Always Say These 3 WORDS" (specific: 3 words)
    BAD: "Why You Can't Walk Away From Bad Situations" (too generic, no specific detail)
    BAD: "How People Manipulate You Without Knowing" (vague, no tactic named)
    BAD: "The Dark Truth About Human Behavior" (clickbait with no substance)
    The viewer should think "wait, WHAT word/trick/thing?" and NEED to watch.
  - "ctaLine": "HAVE YOU EVER FALLEN FOR THIS?"
  - "voiceover": the full narration (see structure below)

VOICEOVER STRUCTURE — 6 paragraphs separated by \\n\\n:
  Paragraph 1: HOOK — the unsettling claim, 1-2 sentences. "There's a word that..."
  Paragraph 2: THE TACTIC — name and define it, 1-2 sentences.
  Paragraph 3: HOW IT WORKS — the mechanism, 2 sentences max.
  Paragraph 4: REAL EXAMPLE — vivid scenario, 1-2 sentences.
  Paragraph 5: THE DEFENSE — how to counter it, 1-2 sentences.
  Paragraph 6: CTA — "Have you ever fallen for this? Comment below."

RULES:
1. Total voiceover: STRICTLY 100-120 words. Count carefully.
2. Written for SPEECH — spoken numbers, flowing sentences, NO lists or em-dashes
3. Educational tone — teach recognition, NOT instruction for manipulation
4. Every claim must be based on REAL psychology research
5. Make it feel personal and slightly uncomfortable

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown code fences:
{{
  "date": "{date_iso}",
  "channel": "mindtrap",
  "topic_category": "{topic_category}",
  "hookLine": "The Word That Makes People Say YES",
  "cards": [
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🧠",
      "dallePrompt": "Dark atmospheric photograph, [abstract scene]. Dramatic shadows, moody blue-black lighting, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "⚠️",
      "dallePrompt": "Dark atmospheric photograph, [abstract scene]. Dramatic shadows, moody blue-black lighting, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "👁️",
      "dallePrompt": "Dark atmospheric photograph, [abstract scene]. Dramatic shadows, moody blue-black lighting, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🛡️",
      "dallePrompt": "Dark atmospheric photograph, [abstract scene]. Dramatic shadows, moody blue-black lighting, shallow depth of field."
    }}
  ],
  "ctaLine": "HAVE YOU EVER FALLEN FOR THIS?",
  "voiceover": "Hook\\n\\nTactic\\n\\nMechanism\\n\\nExample\\n\\nDefense\\n\\nHave you ever fallen for this? Comment below."
}}

CRITICAL:
- Exactly 4 cards, exactly 6 voiceover paragraphs
- STRICTLY 100-120 words total
- Educational — teach RECOGNITION, not exploitation
- Every claim backed by real psychology"""

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

    parser = argparse.ArgumentParser(description="Generate MindTrap video data (dark psychology)")
    parser.add_argument("--topic", help="Force a specific topic category", default=None)
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument("--render", action="store_true", help="Also render the video")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON, don't save")
    parser.add_argument("--no-images", action="store_true", help="Skip DALL-E image generation")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    topic_category = pick_topic_category(args.topic)

    print(f"Generating MindTrap video")
    print(f"  Date: {target_date.isoformat()}")
    print(f"  Topic: {topic_category}")
    print("=" * 60)

    print("\nGenerating script with Claude...")
    data = generate_mindtrap_json(target_date, topic_category)

    print(f"  Hook: {data['hookLine']}")
    print(f"  Cards: {len(data['cards'])}")
    for i, card in enumerate(data["cards"]):
        print(f"    {i + 1}. {card.get('emoji', '🧠')} {card['title']} — {card['stat']}")

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
    filename = f"mindtrap-{topic_category}-{target_date.isoformat()}.json"
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved: {output_path}")

    save_used_topic(topic_category)

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
