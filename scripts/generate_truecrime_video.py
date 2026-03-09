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


def fetch_wikipedia_image(query: str, name: str) -> str | None:
    """Fetch a Wikipedia image for a topic and download it locally."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "TrueCrimeBot/1.0"}

    try:
        title = query.replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        img_url = data.get("originalimage", {}).get("source", "") or data.get("thumbnail", {}).get("source", "")

        if not img_url or ".svg" in img_url.lower():
            return None

        # Download
        safe_name = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        ext = ".png" if ".png" in img_url.lower() else ".jpg"
        filename = f"{safe_name}{ext}"
        filepath = IMAGE_DIR / filename

        if filepath.exists() and filepath.stat().st_size > 0:
            return f"images/truecrime/{filename}"

        img_resp = requests.get(img_url, headers=headers, timeout=15)
        img_resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(img_resp.content)

        return f"images/truecrime/{filename}"
    except Exception as e:
        print(f"  WARNING: Wikipedia image failed for '{query}': {e}")
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
        "NO filler phrases. NO 'shocking twist' or 'you won't believe'.\n"
        "Let the facts speak for themselves.\n\n"
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
  - "imageQueries": list of 2-3 Wikipedia article titles to try for an inline image for THIS beat.
    Each card should search for something relevant to its chapter:
      Card 1 (victim): victim's full name, memorial/tribute page, their school/workplace
      Card 2 (crime): the city or town, the street/neighborhood, a landmark near the scene
      Card 3 (investigation): forensic technique used (e.g. "Genetic genealogy"), the police department or agency
      Card 4 (resolution): perpetrator's full name (mugshots are public domain), the court case, the prison
    Mugshots and public domain photos make the best images.

Top-level fields:
  - "caseId": unique identifier for tracking (e.g. "christy-mirack-1992-pa")
  - "hookLine": cold open — the most dramatic moment of the case, under 10 words
  - "ctaLine": "Follow for cases the mainstream forgot"
  - "voiceover": the full narration (see structure below)

VOICEOVER STRUCTURE — 6 paragraphs separated by \\n\\n:
  Paragraph 1: HOOK — cold open, 1-2 sentences max. Creates an open loop.
  Paragraph 2: THE VICTIM — 1-2 sentences. Who they were, humanize them briefly.
  Paragraph 3: THE CRIME — 2 sentences max. Key facts only.
  Paragraph 4: THE INVESTIGATION — 1-2 sentences. The critical evidence or failure.
  Paragraph 5: THE RESOLUTION — 1-2 sentences. Land the twist or open question.
  Paragraph 6: CTA — one sentence: "Follow Cold Trail for cases the mainstream forgot."

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
      "imageQueries": ["Victim Full Name", "Victim School or Workplace"]
    }},
    {{
      "title": "Chapter Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "imageQueries": ["City, State", "Neighborhood or Landmark"]
    }},
    {{
      "title": "Chapter Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "imageQueries": ["Forensic Technique", "Police Department"]
    }},
    {{
      "title": "Chapter Title",
      "stat": "Key Stat",
      "subtitle": "Context line",
      "emoji": "🔍",
      "imageQueries": ["Perpetrator Full Name", "Court Case Name"]
    }}
  ],
  "ctaLine": "Follow Cold Trail for cases the mainstream forgot",
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


def fetch_images_for_data(data: dict) -> dict:
    """Fetch Wikipedia images for each card, trying multiple queries in priority order."""
    print("\nFetching images...")
    case_id = data.get("caseId", "unknown")
    for i, card in enumerate(data.get("cards", [])):
        queries = card.get("imageQueries", [])
        if not queries:
            print(f"  Card {i+1}: no image queries provided")
            continue

        found = False
        for query in queries:
            path = fetch_wikipedia_image(query, f"{case_id}-card-{i}-{query}")
            if path:
                card["backgroundImage"] = path
                print(f"  Card {i+1}: {path} (from '{query}')")
                found = True
                break
            else:
                print(f"  Card {i+1}: no image for '{query}', trying next...")

        if not found:
            print(f"  Card {i+1}: no image found from any query")

        # Remove imageQueries from output (not needed by renderer)
        card.pop("imageQueries", None)
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

    # Step 3: Fetch images
    data = fetch_images_for_data(data)

    # Validate and show voiceover
    paragraphs = data["voiceover"].split("\n\n")
    word_count = len(data["voiceover"].split())
    print(f"\n  Voiceover paragraphs: {len(paragraphs)}")
    print(f"  Voiceover words: {word_count} (~{word_count / 2.5:.0f}s spoken)")

    if args.dry_run:
        print(f"\n  [DRY RUN] Generated data:")
        print(json.dumps(data, indent=2))
        return

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
