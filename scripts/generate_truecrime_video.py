#!/usr/bin/env python3
"""
Generate True Crime Video Data — single-case deep dive format.

Uses Claude's knowledge of historic crime cases to create investigative-style
short-form scripts. Each video covers ONE case in depth with 4 narrative beats:
  1. The Victim (who, when, where)
  2. The Crime (what happened)
  3. The Investigation (evidence, suspects, forensics)
  4. The Resolution or Open Question

Focuses on obscure/lesser-known cases, cold cases solved by DNA,
and wrongful convictions.

Usage:
  python scripts/generate_truecrime_video.py                    # generate JSON
  python scripts/generate_truecrime_video.py --render            # generate + render
  python scripts/generate_truecrime_video.py --dry-run           # print JSON, don't save
  python scripts/generate_truecrime_video.py --category dna      # specific category
  python scripts/generate_truecrime_video.py --list-used         # show previously used cases

Categories:
  obscure    — lesser-known historic cases (1950s-2000s), the default
  dna        — cold cases solved by DNA/forensics
  wrongful   — wrongful convictions and exonerations
  angle      — fresh angles on famous cases (unknown victims, overlooked details)

Environment variables (in .env):
  ANTHROPIC_API_KEY     — required for content generation
"""

from __future__ import annotations

import json
import os
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
IMAGE_DIR = Path(__file__).parent.parent / "video" / "public" / "images" / "truecrime"
USED_CASES_FILE = Path(__file__).parent / "truecrime_used_cases.json"

# Content mix weights (used when category is "mix" or unspecified rotation)
CATEGORY_WEIGHTS = {
    "obscure": 60,
    "dna": 25,
    "wrongful": 10,
    "angle": 5,
}

CATEGORY_DESCRIPTIONS = {
    "obscure": (
        "A lesser-known historic criminal case from the 1950s-2000s that most people "
        "have NEVER heard of. Regional crimes that didn't make national headlines. "
        "Unsolved mysteries from small towns. Cases with bizarre twists that fell "
        "through the cracks of media coverage. NOT famous serial killers."
    ),
    "dna": (
        "A cold case that was solved years or decades later through DNA evidence, "
        "genetic genealogy (like GEDmatch/CODIS), or forensic breakthroughs. "
        "Focus on the gap between the crime and the solve — the longer the better. "
        "Cases where the killer lived a normal life for decades before being caught."
    ),
    "wrongful": (
        "A wrongful conviction where an innocent person served years or decades in prison "
        "before being exonerated. Focus on what went wrong — false confessions, "
        "bad forensic science, prosecutorial misconduct, eyewitness misidentification. "
        "Cases with DNA exonerations are ideal."
    ),
    "angle": (
        "A fresh, lesser-known angle on a famous case. NOT retelling Bundy or Dahmer's "
        "story — instead cover: an unknown victim who was never identified, a piece "
        "of evidence that was overlooked, a surviving victim's untold story, a "
        "connection between cases that nobody talks about, or a wrongly accused "
        "suspect in a famous case."
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
    # Keep last 500 to prevent infinite growth
    existing = existing[-500:]
    USED_CASES_FILE.write_text(json.dumps({"cases": existing}, indent=2))


def pick_category(explicit: str | None = None) -> str:
    """Pick a category — explicit choice or weighted random from mix."""
    if explicit and explicit != "mix":
        return explicit

    import random
    categories = list(CATEGORY_WEIGHTS.keys())
    weights = list(CATEGORY_WEIGHTS.values())
    return random.choices(categories, weights=weights, k=1)[0]


def generate_dalle_image(prompt: str, name: str) -> str | None:
    """Generate a cinematic scene image via DALL-E 3 (portrait 1024x1792)."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("    WARNING: OPENAI_API_KEY not set, skipping image generation")
        return None

    if OpenAI is None:
        print("    WARNING: openai package not installed, skipping")
        return None

    safe_name = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    filename = f"{safe_name}.png"
    filepath = IMAGE_DIR / filename

    if filepath.exists() and filepath.stat().st_size > 0:
        print(f"    Image cached: {filename}")
        return f"images/truecrime/{filename}"

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
        return f"images/truecrime/{filename}"

    except Exception as e:
        print(f"    WARNING: DALL-E generation failed for '{name}': {e}")
        return None


def generate_truecrime_json(
    target_date: date,
    category: str,
    used_cases: list[str],
) -> dict:
    """Use Claude to generate a single-case deep-dive true crime video script."""
    date_str = target_date.strftime("%B %d, %Y")
    date_iso = target_date.isoformat()
    category_desc = CATEGORY_DESCRIPTIONS[category]

    # Format used cases for exclusion
    used_str = ""
    if used_cases:
        recent = used_cases[-100:]  # Only send last 100 to save tokens
        used_str = (
            "\n\nCASES ALREADY USED (do NOT repeat any of these):\n"
            + "\n".join(f"- {c}" for c in recent)
        )

    system = (
        "You are an investigative crime reporter creating short-form videos about "
        "historic criminal cases. You draw from your extensive knowledge of true crime "
        "history to surface cases that most viewers have never heard of.\n\n"
        "Tone: serious, measured, building tension. Like a Dateline narrator.\n"
        "Never sensationalize victims. Focus on facts, suspects, and timelines.\n"
        "Use precise language — dates, locations, evidence details.\n"
        "NO filler phrases. Let the facts speak for themselves.\n"
        "The hookLine (YouTube title) must be viscerally provocative. "
        "The voiceover stays measured and factual — the title sells, the narration delivers.\n\n"
        "CRITICAL: Every case you mention must be a REAL case with verifiable facts. "
        "Do NOT fabricate or merge cases. Use real names, real dates, real locations."
    )

    prompt = f"""Create a single-case deep-dive true crime short for: {date_str}

CATEGORY: {category.upper()}
{category_desc}

Pick ONE compelling case and tell its full story across 4 narrative beats.
{used_str}

FORMAT: 4 cards telling ONE story — each card is a chapter of the same case:
  Card 1: THE VICTIM — who they were, age, location, when they were last seen or found
  Card 2: THE CRIME — what happened, the scene, the details that made it unusual
  Card 3: THE INVESTIGATION — evidence, suspects, forensics, what went right or wrong
  Card 4: THE RESOLUTION — how it ended (arrest, conviction, exoneration, or still unsolved)

Each card needs:
  - "title": Chapter heading (e.g. "A Teacher Who Never Came Home", "The DNA Match", "34 Years Later")
  - "stat": Key number/fact for this beat (e.g. "Age 25", "Zero Witnesses", "Solved After 33 Years", "Still Unsolved")
  - "subtitle": One-line context for this chapter
  - "emoji": relevant emoji (🔍 🧬 ⚖️ 🚨 🔎 🏛️ 💀 🔬 👤 🩸 etc.)
  - "dallePrompt": a DALL-E 3 prompt for a cinematic, atmospheric background image.
    Rules for dallePrompt:
    - Style: "Cinematic dark photograph, [scene description]. Moody dramatic lighting, shallow depth of field."
    - NEVER include people, faces, or bodies — only locations, objects, and atmosphere
    - NEVER include text, words, letters, or numbers in the image
    - Card 1 (victim): the location/setting where the victim lived or was last seen
    - Card 2 (crime): the crime scene atmosphere — a dark road, empty room, evidence markers
    - Card 3 (investigation): forensic/detective atmosphere — lab equipment, case files, evidence bags
    - Card 4 (resolution): courtroom, prison exterior, or justice/freedom imagery
    - Keep prompts under 80 words
    - The image will be displayed full-screen at 1080x1920 portrait — compose vertically

Top-level fields:
  - "caseId": unique identifier for tracking (e.g. "christy-mirack-1992-pa")
  - "hookLine": the YouTube title — this determines whether anyone watches.
    Rules for hookLine:
    - Max 50 characters (Shorts truncate on mobile)
    - Use ONE word in ALL CAPS for emphasis
    - Must create visceral curiosity — an intimate, disturbing, or bizarre detail
    - Pattern: [Specific human action/role] + [Shocking outcome]
    - GOOD: "Her Killer KISSED Her Before Strangling Her"
    - GOOD: "She Called 911. The Operator HUNG UP."
    - GOOD: "A Nurse Vanished Inside Her Own HOSPITAL"
    - BAD: "A wife vanished after a morning jog" (too passive, too generic)
    - BAD: "Unsolved murder in rural town" (no human detail)
    - Never start with "A man" or "A woman" — use a specific role (teacher, nurse, mother)
    - Must make someone physically unable to scroll past
  - "ctaLine": "WHAT DO YOU THINK HAPPENED?"
  - "voiceover": the full narration (see structure below)

VOICEOVER STRUCTURE — 6 paragraphs separated by \\n\\n:
  Paragraph 1: HOOK — cold open, 1-2 sentences max. Creates an open loop.
  Paragraph 2: THE VICTIM — 1-2 sentences. Who they were, humanize them briefly.
  Paragraph 3: THE CRIME — 2 sentences max. Key facts only.
  Paragraph 4: THE INVESTIGATION — 1-2 sentences. The critical evidence or failure.
  Paragraph 5: THE RESOLUTION — 1-2 sentences. Land the twist or open question.
  Paragraph 6: CTA — one short engagement question: "What do you think really happened? Comment below."

RULES:
1. Total voiceover: STRICTLY 110-130 words. This is CRITICAL — over 130 words makes the video too long.
   Each paragraph should be 15-25 words. The CTA should be under 10 words.
   Count your words carefully before responding.
2. Written for SPEECH — use spoken numbers, flowing sentences
   NO lists, em-dashes, ellipses, or colons mid-sentence
3. The hook paragraph should be the most gripping moment — NOT "today we're covering..."
   Example: "In 1987, a hiker found a suitcase on the side of Highway 9. Inside was a woman no one has ever identified."
4. Every detail must be REAL and verifiable
5. Do NOT pick heavily-covered YouTube cases (no Bundy, Dahmer, Gacy, Zodiac, JonBenet unless "angle" category)

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown code fences:
{{
  "date": "{date_iso}",
  "channel": "truecrime",
  "category": "{category}",
  "caseId": "unique-case-identifier",
  "hookLine": "COLD OPEN HOOK LINE",
  "cards": [
    {{
      "title": "Chapter Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "dallePrompt": "Cinematic dark photograph, [victim's setting]. Moody dramatic lighting, shallow depth of field."
    }},
    {{
      "title": "Chapter Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "dallePrompt": "Cinematic dark photograph, [crime scene atmosphere]. Moody dramatic lighting, shallow depth of field."
    }},
    {{
      "title": "Chapter Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "dallePrompt": "Cinematic dark photograph, [investigation atmosphere]. Moody dramatic lighting, shallow depth of field."
    }},
    {{
      "title": "Chapter Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "dallePrompt": "Cinematic dark photograph, [resolution atmosphere]. Moody dramatic lighting, shallow depth of field."
    }}
  ],
  "ctaLine": "WHAT DO YOU THINK HAPPENED?",
  "voiceover": "Hook paragraph\\n\\nVictim paragraph\\n\\nCrime paragraph\\n\\nInvestigation paragraph\\n\\nResolution paragraph\\n\\nCTA paragraph"
}}

CRITICAL:
- voiceover MUST have exactly 6 paragraphs (hook + 4 beats + CTA)
- STRICTLY 110-130 words total (count carefully)
- ONE case, told in depth across 4 beats
- Every fact must be REAL and verifiable"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"ERROR: Claude returned invalid JSON: {e}")
        print(f"Response:\n{response_text[:500]}")
        sys.exit(1)

    # Validate structure
    required_keys = ["date", "channel", "hookLine", "cards", "voiceover"]
    for key in required_keys:
        if key not in data:
            print(f"ERROR: Missing required key '{key}' in generated data")
            sys.exit(1)

    if len(data["cards"]) != 4:
        print(f"WARNING: Expected 4 cards, got {len(data['cards'])}")

    # Validate paragraph count
    paragraphs = [p for p in data["voiceover"].split("\n\n") if p.strip()]
    if len(paragraphs) != 6:
        print(f"WARNING: Voiceover has {len(paragraphs)} paragraphs, expected 6")

    return data


def generate_card_images(data: dict) -> dict:
    """Generate DALL-E 3 cinematic images for each card."""
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

        # Remove dallePrompt from output (not needed by renderer)
        card.pop("dallePrompt", None)
    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate true crime video data (single-case deep dive)")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)", default=None)
    parser.add_argument(
        "--category",
        choices=["obscure", "dna", "wrongful", "angle", "mix"],
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

    print(f"Generating true crime video (single-case deep dive)")
    print(f"  Date: {target_date.isoformat()}")
    print(f"  Category: {category}")
    print("=" * 60)

    # Step 1: Load used cases for dedup
    used_cases = load_used_cases()
    print(f"\n  Previously used cases: {len(used_cases)}")

    # Step 2: Generate script via Claude
    print("\nGenerating script with Claude...")
    data = generate_truecrime_json(target_date, category, used_cases)

    case_id = data.get("caseId", "unknown")
    print(f"  Case: {case_id}")
    print(f"  Hook: {data['hookLine']}")
    print(f"  Beats:")
    for i, card in enumerate(data["cards"]):
        print(f"    {i + 1}. {card.get('emoji', '🔍')} {card['title']} — {card['stat']}")

    # Validate and show voiceover
    paragraphs = data["voiceover"].split("\n\n")
    word_count = len(data["voiceover"].split())
    print(f"\n  Voiceover paragraphs: {len(paragraphs)}")
    print(f"  Voiceover words: {word_count} (~{word_count / 2.5:.0f}s spoken)")

    if args.dry_run:
        print(f"\n  [DRY RUN] Generated data:")
        print(json.dumps(data, indent=2))
        return

    # Step 3: Generate DALL-E images (unless --no-images)
    if not args.no_images:
        data = generate_card_images(data)
        image_count = sum(1 for c in data["cards"] if c.get("backgroundImage"))
        print(f"\n  Images generated: {image_count}/4")
        print(f"  DALL-E cost: ${image_count * 0.06:.2f} ({image_count} × $0.06)")
    else:
        print("\nSkipping image generation (--no-images)")
        for card in data["cards"]:
            card.pop("dallePrompt", None)

    # Step 4: Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"truecrime-{category}-{target_date.isoformat()}"
    filename = f"{slug}.json"
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved: {output_path}")

    # Step 5: Log used case
    save_used_case(case_id)
    print(f"  Logged case '{case_id}' to used list")

    # Clean caseId from saved JSON (not needed by renderer)
    data.pop("caseId", None)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    # Step 6: Optionally render
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
