#!/usr/bin/env python3
"""
Generate Kids "Did You Know?" Video Data — uses Claude to generate fun facts
and DALL-E 3 for cartoon illustrations.

Usage:
  python scripts/generate_kids_video.py "Animals"              # generate JSON + images
  python scripts/generate_kids_video.py "Space" --render        # generate + render
  python scripts/generate_kids_video.py "Dinosaurs" --facts 4   # 4 facts instead of 3
  python scripts/generate_kids_video.py "Ocean" --no-images     # skip DALL-E (fast test)

Environment variables (in .env):
  ANTHROPIC_API_KEY     — required for fact generation
  OPENAI_API_KEY        — required for DALL-E 3 illustrations
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
    print("Error: openai package not installed. Run: pip install openai")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent.parent / "video" / "data"
IMAGES_DIR = Path(__file__).parent.parent / "video" / "public" / "images" / "kids"


def generate_dalle_image(prompt: str, name: str) -> str | None:
    """Generate a cartoon illustration via DALL-E 3 and save it locally."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("    WARNING: OPENAI_API_KEY not set, skipping image generation")
        return None

    safe_name = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    filename = f"{safe_name}.png"
    filepath = IMAGES_DIR / filename

    if filepath.exists() and filepath.stat().st_size > 0:
        print(f"    Image cached: {filename}")
        return f"images/kids/{filename}"

    try:
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
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
        return f"images/kids/{filename}"

    except Exception as e:
        print(f"    WARNING: DALL-E generation failed for '{name}': {e}")
        return None


def generate_fact_images(facts: list[dict], category: str, today: str) -> list[str]:
    """Generate DALL-E 3 cartoon illustrations for each fact."""
    paths = []

    for i, fact in enumerate(facts):
        dalle_prompt = fact.get("dallePrompt", "")
        if not dalle_prompt:
            print(f"  Fact {i}: No dallePrompt, skipping")
            paths.append("")
            continue

        print(f"  Generating image {i + 1}/{len(facts)}: {dalle_prompt[:80]}...")
        slug = category.lower().replace(" ", "-")
        name = f"{today}-{slug}-fact-{i}"
        path = generate_dalle_image(dalle_prompt, name)
        paths.append(path or "")

    return paths


def get_used_facts(category: str) -> list[str]:
    """Scan all kids-{slug}-*.json for this category, return list of used factText strings."""
    slug = category.lower().replace(" ", "-")
    used = []
    for path in OUTPUT_DIR.glob(f"kids-{slug}-*.json"):
        try:
            with open(path) as f:
                data = json.load(f)
            for fact in data.get("facts", []):
                text = fact.get("factText", "")
                if text:
                    used.append(text)
        except (json.JSONDecodeError, OSError):
            continue
    return used


def generate_kids_facts(category: str, num_facts: int = 3) -> dict:
    """Use Claude to generate fun kids facts with voiceover and DALL-E prompts."""
    today = date.today().isoformat()

    system = (
        "You are a kids educator creating short-form video scripts "
        "for YouTube Shorts. Your audience is kids aged 8-12. "
        "Keep facts accurate and age-appropriate. Use simple words an 8-year-old can understand. "
        "NEVER use filler phrases like 'How cool is that!', 'That's amazing!', 'Can you believe it?', "
        "'Isn't that wild?'. Every sentence must teach something new. "
        "Move fast — each fact voiceover should add a bonus detail or context, not just restate the on-screen text. "
        "Put the MOST mind-blowing fact FIRST. It's the hook — if it doesn't make a kid say 'WAIT WHAT?!' it belongs later. "
        "For the FIRST fact's voiceover, start with a dramatic STATEMENT of the fact. "
        "NO 'Did you know', 'Get ready', 'Here's something', or any other warm-up. Just state the amazing thing."
    )

    prompt = f"""Create {num_facts} amazing "Did You Know?" facts about: {category}

For each fact, provide:
1. A short, punchy on-screen text (max 15 words)
2. An emoji that represents the fact
3. A voiceover script (2 sentences, spoken naturally to a kid). Each sentence must add NEW information — no filler, no reactions, no restating the on-screen text. Keep each fact voiceover 15-18 words.
4. A dallePrompt — a simple, clean prompt for DALL-E 3 to generate a cartoon illustration. Follow these rules EXACTLY:
   - Start with: "Simple 3D cartoon illustration of"
   - Describe ONE single subject (one animal, one planet, one object) — never multiple
   - End with: "Solid pastel background. No text, no words, no letters, no numbers."
   - Keep it SHORT (under 25 words). Less detail = better results.
   - NEVER ask for comparisons, size references, or multiple objects side by side
   - NEVER mention "Earth for scale" or "surrounded by" — DALL-E duplicates objects
   - Good: "Simple 3D cartoon illustration of a friendly smiling Venus planet with a clock. Solid pastel background. No text, no words, no letters, no numbers."
   - Bad: "A Venus planet next to Earth with a clock showing time passing and stars around it"

Also provide:
- A "title" field: Rewrite the most surprising fact as a punchy YouTube Shorts title (max 40 chars — Shorts truncate after 40 on mobile). Use CAPS for ONE key word. Statement format, not a question. Do NOT include #shorts or hashtags.
  Good: "Ketchup Was Once Sold as MEDICINE"
  Good: "Popsicles Were Invented by an 11-Year-Old"
  Bad: "Did You Know About Ketchup? #shorts"
  Bad: "AMAZING INCREDIBLE Food Facts You MUST See"
- A topic title (e.g., "Amazing Animals", "Incredible Space Facts")
- A hook subtitle (e.g., "Amazing Animal Facts!")
- A full voiceover that combines all fact voiceovers with a hook and CTA

OUTPUT FORMAT — respond with ONLY valid JSON, no markdown code fences:
{{
  "date": "{today}",
  "title": "Most Surprising Fact as Clickbait Title Here",
  "topic": "Topic Title Here",
  "category": "{category}",
  "hookLine": "DID YOU KNOW?",
  "hookSubtitle": "Exciting subtitle about {category}!",
  "facts": [
    {{
      "factText": "Short on-screen fact text",
      "emoji": "relevant emoji",
      "voiceover": "Spoken version for TTS — 2-3 sentences, enthusiastic and fun",
      "dallePrompt": "Simple 3D cartoon illustration of a friendly smiling [subject]. Solid pastel background. No text, no words, no letters, no numbers."
    }}
  ],
  "ctaLine": "FOLLOW FOR MORE!",
  "voiceover": "Fact 1 voiceover\\n\\nFact 2 voiceover\\n\\nFact 3 voiceover\\n\\nCTA paragraph"
}}

IMPORTANT:
- The FIRST fact must be the MOST surprising, mind-blowing one. It's the hook.
- The FIRST fact's voiceover must start with a dramatic STATEMENT — NO "Did you know", "Get ready", "Here's something". Just state the amazing thing directly.
- voiceover MUST have exactly {num_facts + 1} paragraphs separated by \\n\\n
  ({num_facts} facts + 1 CTA). NO hook paragraph — the first fact IS the hook.
- CTA paragraph: 1 short sentence (under 6 words), e.g. "Follow for more facts!"
- The full voiceover should be ~55-65 words total (~22-26 seconds spoken). This is critical — videos over 30s lose viewers.
- dallePrompt MUST follow the exact format: "Simple 3D cartoon illustration of [ONE subject]. Solid pastel background. No text, no words, no letters, no numbers."
- ONE subject only — never two objects, never comparisons, never "surrounded by"
- Under 25 words total. Simpler = better."""

    # Dedup: inject previously used facts so Claude avoids repeats
    used_facts = get_used_facts(category)
    if used_facts:
        dedup_block = "\n\nAVOID repeating these previously used facts:\n"
        dedup_block += "\n".join(f"- {f}" for f in used_facts)
        dedup_block += "\nGenerate completely NEW facts not on this list."
        prompt += dedup_block

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
    required_keys = ["date", "title", "topic", "category", "hookLine", "hookSubtitle", "facts", "voiceover"]
    for key in required_keys:
        if key not in data:
            print(f"ERROR: Missing required key '{key}' in generated data")
            sys.exit(1)

    if len(data["facts"]) != num_facts:
        print(f"WARNING: Expected {num_facts} facts, got {len(data['facts'])}")

    # Validate paragraph count (facts + CTA, no hook)
    paragraphs = [p for p in data["voiceover"].split("\n\n") if p.strip()]
    expected = len(data["facts"]) + 1
    if len(paragraphs) != expected:
        print(f"WARNING: Voiceover has {len(paragraphs)} paragraphs, expected {expected}")

    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate kids 'Did You Know?' video data")
    parser.add_argument("category", help="Topic category (e.g., Animals, Space, Dinosaurs)")
    parser.add_argument("--facts", type=int, default=3, help="Number of facts (default: 3)")
    parser.add_argument("--no-images", action="store_true", help="Skip DALL-E image generation")
    parser.add_argument("--render", action="store_true", help="Also render the video after generating data")
    args = parser.parse_args()

    today = date.today()
    category = args.category

    print(f"Generating kids facts video: {category}")
    print(f"  Date: {today.isoformat()}")
    print(f"  Facts: {args.facts}")
    print("=" * 60)

    # Step 1: Generate facts via Claude
    print("\nGenerating facts with Claude...")
    data = generate_kids_facts(category, num_facts=args.facts)

    print(f"  Topic: {data['topic']}")
    print(f"  Facts generated: {len(data['facts'])}")
    for i, fact in enumerate(data["facts"]):
        print(f"    {i + 1}. {fact['emoji']} {fact['factText']}")

    # Step 2: Generate DALL-E illustrations (unless --no-images)
    if not args.no_images:
        print("\nGenerating DALL-E 3 illustrations...")
        image_paths = generate_fact_images(data["facts"], category, today.isoformat())

        # Update fact illustrations
        for i, path in enumerate(image_paths):
            data["facts"][i]["illustration"] = path
    else:
        print("\nSkipping image generation (--no-images)")
        for fact in data["facts"]:
            fact["illustration"] = ""

    # Clean up dallePrompt from output (not needed by renderer)
    for fact in data["facts"]:
        fact.pop("dallePrompt", None)
        fact.pop("imageQuery", None)

    # Step 3: Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = category.lower().replace(" ", "-")
    output_path = OUTPUT_DIR / f"kids-{slug}-{today.isoformat()}.json"
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved: {output_path}")

    # Show voiceover preview
    paragraphs = data["voiceover"].split("\n\n")
    word_count = len(data["voiceover"].split())
    print(f"  Voiceover paragraphs: {len(paragraphs)}")
    print(f"  Voiceover words: {word_count} (~{word_count / 2.5:.0f}s spoken)")
    print(f"  Hook: {data['hookLine']}")
    print(f"  Subtitle: {data['hookSubtitle']}")

    # Cost estimate
    image_count = sum(1 for f in data["facts"] if f.get("illustration"))
    cost = image_count * 0.04
    print(f"  DALL-E cost: ${cost:.2f} ({image_count} images × $0.04)")

    # Step 4: Optionally render
    if args.render:
        import subprocess
        print("\nRendering video...")
        video_dir = Path(__file__).parent.parent / "video"
        result = subprocess.run(
            ["npx", "tsx", "render.ts", "--kids", str(output_path)],
            cwd=str(video_dir),
            capture_output=False,
        )
        if result.returncode != 0:
            print("ERROR: Video render failed")
            sys.exit(1)

    print("\nDone!")


if __name__ == "__main__":
    main()
