#!/usr/bin/env python3
"""
Generate True Crime Video Data — uses Claude's knowledge of historic crime cases
to create investigative-style short-form scripts. Focuses on obscure/lesser-known
cases, cold cases solved by DNA, and wrongful convictions.

Usage:
  python scripts/generate_truecrime_video.py                    # generate JSON
  python scripts/generate_truecrime_video.py --render            # generate + render
  python scripts/generate_truecrime_video.py --dry-run           # print JSON, don't save
  python scripts/generate_truecrime_video.py --cards 4           # 4 cases instead of 3
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
        "Lesser-known historic criminal cases from the 1950s-2000s that most people "
        "have NEVER heard of. Regional crimes that didn't make national headlines. "
        "Unsolved mysteries from small towns. Cases with bizarre twists that fell "
        "through the cracks of media coverage. NOT famous serial killers."
    ),
    "dna": (
        "Cold cases that were solved years or decades later through DNA evidence, "
        "genetic genealogy (like GEDmatch/CODIS), or forensic breakthroughs. "
        "Focus on the gap between the crime and the solve — the longer the better. "
        "Cases where the killer lived a normal life for decades before being caught."
    ),
    "wrongful": (
        "Wrongful convictions where innocent people served years or decades in prison "
        "before being exonerated. Focus on what went wrong — false confessions, "
        "bad forensic science, prosecutorial misconduct, eyewitness misidentification. "
        "Cases with DNA exonerations are ideal."
    ),
    "angle": (
        "Fresh, lesser-known angles on famous cases. NOT retelling Bundy or Dahmer's "
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


def save_used_case(case_ids: list[str]):
    """Append case identifiers to the used cases log."""
    existing = load_used_cases()
    existing.extend(case_ids)
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
    num_cards: int = 3,
) -> dict:
    """Use Claude to generate a true crime video script from its knowledge base."""
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

    prompt = f"""Create a true crime short-form video for: {date_str}

CATEGORY FOR THIS VIDEO: {category.upper()}
{category_desc}

Pick {num_cards} compelling cases from your knowledge that fit this category.
{used_str}

RULES:
1. Each card = one real historic case
2. "hookLine" — dramatic but factual, under 8 words. e.g. "3 CASES NOBODY TALKS ABOUT"
3. Each card needs:
   - "title": Case name (victim or case name, ~5-8 words)
   - "stat": Key number/fact (e.g. "Solved After 33 Years", "12 Years Wrongfully Imprisoned", "Body Never Found")
   - "subtitle": One-line context (year, location, what happened)
   - "emoji": relevant emoji (🔍 🧬 ⚖️ 🚨 🔎 🏛️ 💀 🔬 etc.)
   - "caseId": A unique identifier for tracking (e.g. "doe-network-case-4567" or "green-river-unknown-victim-3")
   - "imageQueries": A list of 4 Wikipedia article titles to try for background images, in priority order:
     1. The perpetrator's full name (most likely to have a mugshot/photo on Wikipedia)
     2. The case name as a Wikipedia article (e.g. "Murder of April Tinsley")
     3. The victim's full name
     4. The city or location name as a fallback (e.g. "Idaho Falls, Idaho")
     Mugshots and court photos are public domain and make the best backgrounds.
4. "voiceover" — connected narrative, paragraphs separated by \\n\\n
   - Paragraph 1: Hook — one punchy sentence that creates an open loop
   - Paragraphs 2-{num_cards+1}: One paragraph per card, building tension
     * Lead with the victim as a person, not just a crime statistic
     * Include at least one specific detail (date, age, location)
     * End each card paragraph with an unresolved element when possible
   - Last paragraph: CTA — "Subscribe for cases the mainstream missed."
   - TOTAL = {num_cards + 2} paragraphs
5. Keep total voiceover under 100 words (~40 seconds spoken)
6. Written for SPEECH — use spoken numbers, flowing sentences
   NO lists, em-dashes, ellipses, or colons mid-sentence

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown code fences:
{{
  "date": "{date_iso}",
  "channel": "truecrime",
  "category": "{category}",
  "hookLine": "DRAMATIC SHORT HOOK",
  "cards": [
    {{
      "title": "Case Title Here",
      "stat": "Key Stat",
      "subtitle": "Year, location — what happened",
      "emoji": "🔍",
      "caseId": "unique-case-identifier",
      "imageQueries": ["Perpetrator Full Name", "Murder of Victim Name", "Victim Full Name", "City, State"]
    }}
  ],
  "ctaLine": "Subscribe for cases the mainstream missed",
  "voiceover": "Hook paragraph\\n\\nCard 1 paragraph\\n\\nCard 2 paragraph\\n\\nCard 3 paragraph\\n\\nCTA paragraph"
}}

CRITICAL:
- voiceover paragraph count MUST equal 1 + {num_cards} + 1 = {num_cards + 2}
- Under 100 words total
- Every case must be REAL and verifiable
- Do NOT pick cases that have been heavily covered on YouTube (no Bundy, Dahmer, Gacy, Zodiac, JonBenet unless using the "angle" category with a genuinely fresh take)"""

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

    if len(data["cards"]) != num_cards:
        print(f"WARNING: Expected {num_cards} cards, got {len(data['cards'])}")

    # Validate paragraph count
    paragraphs = [p for p in data["voiceover"].split("\n\n") if p.strip()]
    expected = 1 + len(data["cards"]) + 1
    if len(paragraphs) != expected:
        print(f"WARNING: Voiceover has {len(paragraphs)} paragraphs, expected {expected}")

    return data


def fetch_images_for_data(data: dict) -> dict:
    """Fetch Wikipedia images for each card, trying multiple queries in priority order."""
    print("\nFetching images...")
    for i, card in enumerate(data.get("cards", [])):
        queries = card.get("imageQueries", [])
        # Fallback to single imageQuery if present (backwards compat)
        if not queries and card.get("imageQuery"):
            queries = [card["imageQuery"]]
        if not queries:
            print(f"  Card {i+1}: no image queries provided")
            continue

        found = False
        for query in queries:
            path = fetch_wikipedia_image(query, f"card-{i}-{query}")
            if path:
                card["backgroundImage"] = path
                print(f"  Card {i+1}: {path} (from '{query}')")
                found = True
                break
            else:
                print(f"  Card {i+1}: no image for '{query}', trying next...")

        if not found:
            print(f"  Card {i+1}: no image found from any query")

        # Remove image queries from output (not needed by renderer)
        card.pop("imageQueries", None)
        card.pop("imageQuery", None)
    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate true crime video data")
    parser.add_argument("--cards", type=int, default=3, help="Number of cases (default: 3)")
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

    print(f"Generating true crime video")
    print(f"  Date: {target_date.isoformat()}")
    print(f"  Category: {category}")
    print(f"  Cards: {args.cards}")
    print("=" * 60)

    # Step 1: Load used cases for dedup
    used_cases = load_used_cases()
    print(f"\n  Previously used cases: {len(used_cases)}")

    # Step 2: Generate script via Claude
    print("\nGenerating script with Claude...")
    data = generate_truecrime_json(target_date, category, used_cases, num_cards=args.cards)

    print(f"  Hook: {data['hookLine']}")
    print(f"  Cards: {len(data['cards'])}")
    for i, card in enumerate(data["cards"]):
        print(f"    {i + 1}. {card.get('emoji', '🔍')} {card['title']} — {card['stat']}")

    # Step 3: Fetch images
    data = fetch_images_for_data(data)

    # Step 4: Track used cases
    new_case_ids = [card.get("caseId", card["title"]) for card in data["cards"]]

    # Clean caseId from output (not needed by renderer)
    for card in data["cards"]:
        card.pop("caseId", None)

    # Validate and show voiceover
    paragraphs = data["voiceover"].split("\n\n")
    word_count = len(data["voiceover"].split())
    print(f"\n  Voiceover paragraphs: {len(paragraphs)}")
    print(f"  Voiceover words: {word_count} (~{word_count / 2.5:.0f}s spoken)")

    if args.dry_run:
        print(f"\n  [DRY RUN] Generated data:")
        print(json.dumps(data, indent=2))
        return

    # Step 5: Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"truecrime-{category}-{target_date.isoformat()}"
    filename = f"{slug}.json"
    output_path = OUTPUT_DIR / filename
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved: {output_path}")

    # Step 6: Log used cases
    save_used_case(new_case_ids)
    print(f"  Logged {len(new_case_ids)} cases to used list")

    # Step 7: Optionally render
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
