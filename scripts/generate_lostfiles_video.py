#!/usr/bin/env python3
"""
Generate Lost Files Video Data — unsolved disappearances & missing mysteries.

Each video covers ONE disappearance in depth with 4 narrative beats:
  1. The Disappearance — who/what vanished, when, where
  2. The Search — what was done to find them
  3. The Evidence — clues, last sightings, theories
  4. The Theory — the most compelling explanation

Usage:
  python scripts/generate_lostfiles_video.py                          # generate JSON
  python scripts/generate_lostfiles_video.py --render                  # generate + render
  python scripts/generate_lostfiles_video.py --dry-run                 # print JSON, don't save
  python scripts/generate_lostfiles_video.py --category missing_persons # specific category
  python scripts/generate_lostfiles_video.py --no-images               # skip DALL-E
  python scripts/generate_lostfiles_video.py --list-used               # show previously used cases

Categories:
  missing_persons, vanished_vessels, lost_expeditions,
  disappeared_towns, aviation_mysteries

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
IMAGE_DIR = Path(__file__).parent.parent / "video" / "public" / "images" / "lostfiles"
USED_CASES_FILE = Path(__file__).parent / "lostfiles_used_cases.json"

CATEGORY_WEIGHTS = {
    "missing_persons": 45,
    "vanished_vessels": 15,
    "lost_expeditions": 15,
    "disappeared_towns": 10,
    "aviation_mysteries": 15,
}

CATEGORY_DESCRIPTIONS = {
    "missing_persons": (
        "A real missing person case that remains unsolved. Someone who vanished "
        "without a trace — no body, no definitive explanation. Focus on cases with "
        "bizarre circumstances that make the disappearance impossible to explain. "
        "NOT well-known cases like Jimmy Hoffa or Amelia Earhart."
    ),
    "vanished_vessels": (
        "A ship, submarine, or boat that disappeared under mysterious circumstances. "
        "Ghost ships found empty, vessels that vanished in calm seas, boats where "
        "the crew disappeared but the ship was found intact. Focus on the eerie details."
    ),
    "lost_expeditions": (
        "An expedition — exploration team, research group, or travelers — that "
        "set out and never returned, or whose fate remains partially unexplained. "
        "Arctic, jungle, desert, or mountain expeditions that went catastrophically wrong."
    ),
    "disappeared_towns": (
        "A town, village, colony, or settlement where the entire population vanished. "
        "Abandoned overnight, evacuated under mysterious circumstances, or simply "
        "found empty with no explanation. Real historical cases only."
    ),
    "aviation_mysteries": (
        "An aircraft that disappeared mid-flight under unexplained circumstances. "
        "Planes that vanished from radar, crashed in impossible locations, or were "
        "found decades later in unexpected places. NOT MH370 (too well-known)."
    ),
}


def load_used_cases() -> list[str]:
    """Load list of previously used case identifiers."""
    if USED_CASES_FILE.exists():
        try:
            data = json.loads(USED_CASES_FILE.read_text())
            return data.get("cases", [])
        except (json.JSONDecodeError, KeyError):
            return []
    return []


def save_used_case(case_id: str):
    """Append a case identifier to the used cases log."""
    existing = load_used_cases()
    existing.append(case_id)
    existing = existing[-500:]
    USED_CASES_FILE.write_text(json.dumps({"cases": existing}, indent=2))


def pick_category(explicit: str | None = None) -> str:
    """Pick a category — explicit choice or weighted random from mix."""
    if explicit and explicit != "mix":
        return explicit
    categories = list(CATEGORY_WEIGHTS.keys())
    weights = list(CATEGORY_WEIGHTS.values())
    return random.choices(categories, weights=weights, k=1)[0]


def generate_dalle_image(prompt: str, name: str) -> str | None:
    """Generate a mysterious atmospheric image via DALL-E 3 (portrait 1024x1792)."""
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
        return f"images/lostfiles/{filename}"

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
        return f"images/lostfiles/{filename}"

    except Exception as e:
        print(f"    WARNING: DALL-E generation failed for '{name}': {e}")
        return None


def generate_card_images(data: dict) -> dict:
    """Generate DALL-E 3 images for each card."""
    print("\nGenerating DALL-E images...")
    case_id = data.get("caseId", "unknown")
    for i, card in enumerate(data.get("cards", [])):
        dalle_prompt = card.get("dallePrompt", "")
        if not dalle_prompt:
            print(f"  Card {i+1}: no dallePrompt, skipping")
            continue

        name = f"{case_id}-card-{i}"
        print(f"  Generating image {i + 1}/{len(data['cards'])}: {dalle_prompt[:80]}...")
        path = generate_dalle_image(dalle_prompt, name)
        if path:
            card["backgroundImage"] = path
        else:
            print(f"  Card {i+1}: image generation failed")

        card.pop("dallePrompt", None)
    return data


def generate_lostfiles_json(
    target_date: date,
    category: str,
    used_cases: list[str],
) -> dict:
    """Use Claude to generate an unsolved disappearance video script."""
    date_str = target_date.strftime("%B %d, %Y")
    date_iso = target_date.isoformat()
    category_desc = CATEGORY_DESCRIPTIONS[category]

    used_str = ""
    if used_cases:
        recent = used_cases[-100:]
        used_str = (
            "\n\nCASES ALREADY USED (do NOT repeat any of these):\n"
            + "\n".join(f"- {c}" for c in recent)
        )

    system = (
        "You are a mystery investigator creating short-form videos about unsolved "
        "disappearances and vanished people, vessels, and places. "
        "Tone: measured, building tension, slightly eerie. Like a campfire story told by a detective. "
        "Focus on the mystery — what makes this disappearance IMPOSSIBLE to explain. "
        "Use precise details — dates, locations, last known sightings. "
        "NO filler phrases. Let the mystery speak for itself. "
        "CRITICAL: Every case must be REAL and verifiable. Do NOT fabricate cases."
    )

    prompt = f"""Create an unsolved disappearance video for: {date_str}

CATEGORY: {category.upper()}
{category_desc}

Pick ONE compelling disappearance and tell its full story across 4 narrative beats.
{used_str}

FORMAT: 4 cards telling ONE mystery:
  Card 1: THE DISAPPEARANCE — who/what vanished, when, where, the last known moment
  Card 2: THE SEARCH — what was done to find them, how far it went, what it turned up
  Card 3: THE EVIDENCE — the clues left behind, witness sightings, forensic details
  Card 4: THE THEORY — the most compelling explanation, or why there IS no explanation

Each card needs:
  - "title": Chapter heading (~5-8 words)
  - "stat": Key fact (e.g. "Last Seen March 1969", "200 Searchers", "Zero Traces", "Still Missing")
  - "subtitle": One-line context
  - "emoji": relevant emoji (🔍 🌊 ✈️ 🏔️ 🗺️ ❓ 👻 🚢 etc.)
  - "dallePrompt": a DALL-E 3 prompt for an atmospheric background image.
    Style: "Cinematic dark photograph, [atmospheric scene]. Fog, mist, moody lighting, shallow depth of field."
    NEVER include people, faces, or text/numbers in the image.
    Card 1: the location where they disappeared — foggy road, empty harbor, dense forest
    Card 2: search atmosphere — flashlights in darkness, search boats, helicopters
    Card 3: evidence — abandoned belongings, empty vessel, cryptic note
    Card 4: the open question — empty landscape, fog, vast ocean, unknown
    Keep prompts under 80 words. Images display full-screen at 1080x1920 portrait.

Top-level fields:
  - "caseId": unique identifier (e.g. "mary-celeste-1872", "springfield-three-1992")
  - "hookLine": the YouTube title — max 50 characters.
    Use ONE word in ALL CAPS for emphasis.
    Pattern: "A Pilot Vanished Over Lake MICHIGAN" / "300 People Disappeared From One VILLAGE"
    Must create instant curiosity about what happened.
  - "ctaLine": "WHAT'S YOUR THEORY?"
  - "voiceover": the full narration (see structure below)

VOICEOVER STRUCTURE — 6 paragraphs separated by \\n\\n:
  Paragraph 1: HOOK — the gripping mystery, 1-2 sentences. Set the scene.
  Paragraph 2: THE DISAPPEARANCE — who they were, the last known moment, 1-2 sentences.
  Paragraph 3: THE SEARCH — what was done, how far it went, 2 sentences max.
  Paragraph 4: THE EVIDENCE — the clues, or the disturbing lack thereof, 1-2 sentences.
  Paragraph 5: THE THEORY — the leading explanation, 1-2 sentences.
  Paragraph 6: CTA — "What's your theory? Comment below."

RULES:
1. Total voiceover: STRICTLY 110-130 words. Count carefully.
2. Written for SPEECH — spoken numbers, flowing sentences, NO lists or em-dashes
3. The hook should be the most haunting moment of the story
4. Every case must be REAL and verifiable
5. Focus on what makes the disappearance UNEXPLAINABLE

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown code fences:
{{
  "date": "{date_iso}",
  "channel": "lostfiles",
  "category": "{category}",
  "caseId": "unique-case-identifier",
  "hookLine": "A Pilot Vanished Over Lake MICHIGAN",
  "cards": [
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "dallePrompt": "Cinematic dark photograph, [scene]. Fog, mist, moody lighting, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔦",
      "dallePrompt": "Cinematic dark photograph, [scene]. Fog, mist, moody lighting, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "❓",
      "dallePrompt": "Cinematic dark photograph, [scene]. Fog, mist, moody lighting, shallow depth of field."
    }},
    {{
      "title": "Card Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "👻",
      "dallePrompt": "Cinematic dark photograph, [scene]. Fog, mist, moody lighting, shallow depth of field."
    }}
  ],
  "ctaLine": "WHAT'S YOUR THEORY?",
  "voiceover": "Hook\\n\\nDisappearance\\n\\nSearch\\n\\nEvidence\\n\\nTheory\\n\\nWhat's your theory? Comment below."
}}

CRITICAL:
- Exactly 4 cards, exactly 6 voiceover paragraphs
- STRICTLY 110-130 words total
- ONE disappearance, told in depth
- Every case must be REAL and verifiable"""

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

    parser = argparse.ArgumentParser(description="Generate Lost Files video data (unsolved disappearances)")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument(
        "--category",
        choices=["missing_persons", "vanished_vessels", "lost_expeditions", "disappeared_towns", "aviation_mysteries", "mix"],
        default="mix",
        help="Case category (default: weighted mix)",
    )
    parser.add_argument("--render", action="store_true", help="Also render the video")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON, don't save")
    parser.add_argument("--no-images", action="store_true", help="Skip DALL-E image generation")
    parser.add_argument("--list-used", action="store_true", help="List previously used cases")
    args = parser.parse_args()

    if args.list_used:
        used = load_used_cases()
        if not used:
            print("No cases used yet.")
        else:
            print(f"{len(used)} cases used:")
            for c in used:
                print(f"  - {c}")
        return

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    category = pick_category(args.category)

    print(f"Generating Lost Files video")
    print(f"  Date: {target_date.isoformat()}")
    print(f"  Category: {category}")
    print("=" * 60)

    used_cases = load_used_cases()
    print(f"\n  Previously used cases: {len(used_cases)}")

    print("\nGenerating script with Claude...")
    data = generate_lostfiles_json(target_date, category, used_cases)

    case_id = data.get("caseId", "unknown")
    print(f"  Case: {case_id}")
    print(f"  Hook: {data['hookLine']}")
    print(f"  Cards:")
    for i, card in enumerate(data["cards"]):
        print(f"    {i + 1}. {card.get('emoji', '🔍')} {card['title']} — {card['stat']}")

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
    slug = f"lostfiles-{category}-{target_date.isoformat()}"
    filename = f"{slug}.json"
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved: {output_path}")

    save_used_case(case_id)
    print(f"  Logged case '{case_id}' to used list")

    # Clean caseId from saved JSON (not needed by renderer)
    data.pop("caseId", None)
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
