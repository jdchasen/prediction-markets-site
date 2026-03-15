#!/usr/bin/env python3
"""
Generate BrainDrop Video Data — single mind-blowing fact for adults.

Each video covers ONE fact in depth with 4 narrative beats:
  1. The Fact — the surprising claim
  2. Why It Happens — the mechanism
  3. The Science — the research/evidence
  4. The Twist — the unexpected implication

Usage:
  python scripts/generate_braindrop_video.py                    # generate JSON
  python scripts/generate_braindrop_video.py --render            # generate + render
  python scripts/generate_braindrop_video.py --dry-run           # print JSON, don't save
  python scripts/generate_braindrop_video.py --topic biology     # specific category
  python scripts/generate_braindrop_video.py --no-images         # skip DALL-E

Categories:
  biology, physics, space, psychology, history,
  food_science, technology, ocean, human_body, animals

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
IMAGE_DIR = Path(__file__).parent.parent / "video" / "public" / "images" / "braindrop"
USED_TOPICS_FILE = Path(__file__).parent.parent / "video" / "data" / ".braindrop_used_topics.json"

TOPIC_CATEGORIES = [
    "biology",
    "physics",
    "space",
    "psychology",
    "history",
    "food_science",
    "technology",
    "ocean",
    "human_body",
    "animals",
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
    """Generate a cinematic image via DALL-E 3 (portrait 1024x1792)."""
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
        return f"images/braindrop/{filename}"

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
        return f"images/braindrop/{filename}"

    except Exception as e:
        print(f"    WARNING: DALL-E generation failed for '{name}': {e}")
        return None


def generate_card_images(data: dict) -> dict:
    """Generate DALL-E 3 cinematic images for each card."""
    print("\nGenerating DALL-E images...")
    topic = data.get("topic_category", "braindrop")
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


def generate_braindrop_json(
    target_date: date,
    topic_category: str,
) -> dict:
    """Use Claude to generate a single mind-blowing fact video script."""
    date_str = target_date.strftime("%B %d, %Y")
    date_iso = target_date.isoformat()

    category_labels = {
        "biology": "biology and living organisms",
        "physics": "physics and the laws of nature",
        "space": "space, astronomy, and the cosmos",
        "psychology": "psychology and how the mind works",
        "history": "surprising historical facts most people don't know",
        "food_science": "food science and what's really in your food",
        "technology": "technology and how everyday things actually work",
        "ocean": "the ocean and deep sea mysteries",
        "human_body": "the human body and what it's secretly doing",
        "animals": "animals and their insane abilities",
    }
    topic_label = category_labels.get(topic_category, topic_category)

    system = (
        "You are an enthusiastic science communicator creating short-form videos "
        "about mind-blowing facts for adults. Think Vsauce meets TikTok. "
        "Tone: energetic, confident, conversational — like explaining something "
        "incredible to a friend at a bar. "
        "Use vivid language and analogies. Make complex ideas feel simple. "
        "NO filler phrases. Get straight to the mind-blowing part. "
        "Every fact must be REAL and scientifically accurate. "
        "The hookLine must make someone physically unable to scroll past."
    )

    prompt = f"""Create a mind-blowing fact video for adults for: {date_str}
Topic category: {topic_label}

Pick ONE genuinely surprising fact that most adults don't know.
NOT basic trivia — something that makes you go "wait, WHAT?"

FORMAT: 4 cards telling one story — each card deepens the fact:
  Card 1: THE FACT — the mind-blowing claim, stated simply
  Card 2: WHY IT HAPPENS — the mechanism or cause
  Card 3: THE SCIENCE — the research, numbers, or evidence
  Card 4: THE TWIST — the unexpected implication or "it gets weirder" moment

Each card needs:
  - "title": Beat heading (~5-8 words)
  - "stat": Key number/fact (e.g. "100 Billion Neurons", "2x Faster Than Light", "Since 1952")
  - "subtitle": One-line context
  - "emoji": relevant emoji
  - "dallePrompt": a DALL-E 3 prompt for a cinematic background image.
    Style: "Vibrant cinematic photograph, [subject]. Dramatic lighting, vivid colors, shallow depth of field."
    NEVER include people, faces, or text/numbers in the image.
    Keep prompts under 80 words. Images display full-screen at 1080x1920 portrait.

Top-level fields:
  - "hookLine": the YouTube title — max 50 characters.
    Use ONE word in ALL CAPS for emphasis.
    Pattern: "Your BRAIN [does something shocking]" / "[Subject] Can Actually KILL You"
    Must create instant curiosity.
  - "ctaLine": "DID YOU ALREADY KNOW THIS?"
  - "voiceover": the full narration (see structure below)

VOICEOVER STRUCTURE — 6 paragraphs separated by \\n\\n:
  Paragraph 1: HOOK — bold claim, 1-2 sentences. Create an open loop.
  Paragraph 2: THE FACT — state it clearly, 1-2 sentences.
  Paragraph 3: WHY — explain the mechanism, 2 sentences max.
  Paragraph 4: THE SCIENCE — evidence or numbers, 1-2 sentences.
  Paragraph 5: THE TWIST — the "it gets weirder" moment, 1-2 sentences.
  Paragraph 6: CTA — "Did you already know this? Comment below!"

RULES:
1. Total voiceover: STRICTLY 90-110 words. Count carefully.
2. Written for SPEECH — spoken numbers, flowing sentences, NO lists or em-dashes
3. The hook should be the most mind-blowing moment
4. Every fact must be REAL and scientifically verifiable
5. Target ADULTS — no dumbing down, no "did you know kids?"

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown code fences:
{{
  "date": "{date_iso}",
  "channel": "braindrop",
  "topic_category": "{topic_category}",
  "hookLine": "Your BRAIN Does This While You SLEEP",
  "cards": [
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🧠",
      "dallePrompt": "Vibrant cinematic photograph, [subject]. Dramatic lighting, vivid colors, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔬",
      "dallePrompt": "Vibrant cinematic photograph, [subject]. Dramatic lighting, vivid colors, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "📊",
      "dallePrompt": "Vibrant cinematic photograph, [subject]. Dramatic lighting, vivid colors, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🤯",
      "dallePrompt": "Vibrant cinematic photograph, [subject]. Dramatic lighting, vivid colors, shallow depth of field."
    }}
  ],
  "ctaLine": "DID YOU ALREADY KNOW THIS?",
  "voiceover": "Hook\\n\\nFact\\n\\nWhy\\n\\nScience\\n\\nTwist\\n\\nDid you already know this? Comment below!"
}}

CRITICAL:
- Exactly 4 cards, exactly 6 voiceover paragraphs
- STRICTLY 90-110 words total
- ONE fact, explored in depth
- Every claim must be REAL and verifiable"""

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

    parser = argparse.ArgumentParser(description="Generate BrainDrop video data (mind-blowing facts for adults)")
    parser.add_argument("--topic", help="Force a specific topic category", default=None)
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument("--render", action="store_true", help="Also render the video")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON, don't save")
    parser.add_argument("--no-images", action="store_true", help="Skip DALL-E image generation")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    topic_category = pick_topic_category(args.topic)

    print(f"Generating BrainDrop video")
    print(f"  Date: {target_date.isoformat()}")
    print(f"  Topic: {topic_category}")
    print("=" * 60)

    print("\nGenerating script with Claude...")
    data = generate_braindrop_json(target_date, topic_category)

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
    filename = f"braindrop-{topic_category}-{target_date.isoformat()}.json"
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
