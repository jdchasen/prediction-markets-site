#!/usr/bin/env python3
"""
Batch-generate 3 kids "Did You Know?" videos per day with category rotation.

Picks 3 categories not used in the last 3 days, generates facts + DALL-E images,
renders via Remotion, and uploads to YouTube with staggered scheduling (9AM, 1PM, 5PM ET).

Usage:
  python scripts/batch_kids_videos.py                              # full pipeline: generate, render, upload
  python scripts/batch_kids_videos.py --dry-run                    # generate JSON only, no render/upload
  python scripts/batch_kids_videos.py --categories "Space,Ocean,Food"  # override category selection
  python scripts/batch_kids_videos.py --no-upload                  # generate + render, skip upload
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent))
from generate_kids_video import generate_kids_facts, generate_fact_images

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "video" / "data"
VIDEO_DIR = PROJECT_ROOT / "video"

# Tier 1 (3x weight) — proven performers, universal curiosity
TIER_1 = ["Animals", "Space", "Ocean", "Food", "Weather", "Dinosaurs", "Insects"]

# Tier 2 (1x weight) — decent topics, less data
TIER_2 = ["Sharks", "Planets", "Rainforest", "Arctic", "Inventions", "Robots", "Candy"]

# Removed: Volcanoes, Bones, Sports Science, Ancient Egypt, Human Body, Magnets
CATEGORY_POOL = TIER_1 * 3 + TIER_2  # Tier 1 appears 3x in shuffle pool

# Staggered publish times in ET
SCHEDULE_HOURS_ET = [9, 13, 17]  # 9 AM, 1 PM, 5 PM ET
ET = ZoneInfo("America/New_York")


def get_recent_categories(days: int = 3) -> set[str]:
    """Scan kids-*.json files from the last N days to find recently used categories."""
    recent = set()
    today = date.today()

    for d in range(days):
        check_date = today - timedelta(days=d)
        date_str = check_date.isoformat()
        for path in DATA_DIR.glob(f"kids-*-{date_str}.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                cat = data.get("category", "")
                if cat:
                    recent.add(cat)
            except (json.JSONDecodeError, OSError):
                continue

    return recent


def pick_categories(count: int = 3, override: list[str] | None = None) -> list[str]:
    """Pick categories not used in the last 3 days. Falls back to least-recent if pool exhausted."""
    if override:
        return override[:count]

    recent = get_recent_categories(days=3)
    available = [c for c in CATEGORY_POOL if c not in recent]

    if len(available) < count:
        # Pool exhausted — expand to full pool, shuffle
        available = list(CATEGORY_POOL)

    random.shuffle(available)
    return available[:count]


def compute_schedule_times(count: int) -> list[str]:
    """Return ISO-8601 publish times for today/tomorrow's staggered slots."""
    now = datetime.now(ET)
    times: list[str] = []

    for hour in SCHEDULE_HOURS_ET[:count]:
        slot = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        # If slot already passed, shift to tomorrow
        if slot <= now:
            slot += timedelta(days=1)
        times.append(slot.isoformat())

    return times


def generate_video_data(category: str, today_str: str) -> Path:
    """Generate facts + images and save JSON. Returns path to JSON file."""
    print(f"\n{'='*60}")
    print(f"  Generating: {category}")
    print(f"{'='*60}")

    # Generate facts via Claude
    print("  Generating facts with Claude...")
    data = generate_kids_facts(category, num_facts=3)

    print(f"  Title: {data.get('title', '(none)')}")
    print(f"  Topic: {data['topic']}")
    for i, fact in enumerate(data["facts"]):
        print(f"    {i + 1}. {fact['emoji']} {fact['factText']}")

    # Generate DALL-E illustrations
    print("  Generating DALL-E 3 illustrations...")
    image_paths = generate_fact_images(data["facts"], category, today_str)
    for i, path in enumerate(image_paths):
        data["facts"][i]["illustration"] = path

    # Clean up dallePrompt from output
    for fact in data["facts"]:
        fact.pop("dallePrompt", None)
        fact.pop("imageQuery", None)

    # Save JSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    slug = category.lower().replace(" ", "-")
    output_path = DATA_DIR / f"kids-{slug}-{today_str}.json"
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    # Cost summary
    image_count = sum(1 for fact in data["facts"] if fact.get("illustration"))
    cost = image_count * 0.04
    word_count = len(data.get("voiceover", "").split())
    print(f"  Saved: {output_path.name}")
    print(f"  Words: {word_count} (~{word_count / 2.5:.0f}s spoken)")
    print(f"  DALL-E cost: ${cost:.2f} ({image_count} images)")

    return output_path


def render_video(json_path: Path) -> bool:
    """Render video via Remotion. Returns True on success."""
    print(f"  Rendering: {json_path.name}...")
    result = subprocess.run(
        ["npx", "tsx", "render.ts", "--kids", str(json_path)],
        cwd=str(VIDEO_DIR),
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  ERROR: Render failed for {json_path.name}")
        return False
    print(f"  Render complete: {json_path.name}")
    return True


def upload_video(json_path: Path, schedule_time: str) -> bool:
    """Upload to YouTube with scheduled publish time. Returns True on success."""
    print(f"  Uploading: {json_path.name} (publish at {schedule_time})...")
    result = subprocess.run(
        [
            "npx", "tsx", "upload-youtube.ts",
            str(json_path),
            "--schedule", schedule_time,
        ],
        cwd=str(VIDEO_DIR),
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  ERROR: Upload failed for {json_path.name}")
        return False
    print(f"  Upload complete: {json_path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Batch-generate 3 kids videos per day")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate JSON only — no render or upload",
    )
    parser.add_argument(
        "--no-upload", action="store_true",
        help="Generate + render, but skip upload",
    )
    parser.add_argument(
        "--categories",
        help='Comma-separated category override (e.g., "Space,Ocean,Food")',
    )
    parser.add_argument(
        "--count", type=int, default=3,
        help="Number of videos to generate (default: 3)",
    )
    args = parser.parse_args()

    today_str = date.today().isoformat()
    override = [c.strip() for c in args.categories.split(",")] if args.categories else None
    categories = pick_categories(count=args.count, override=override)
    schedule_times = compute_schedule_times(count=len(categories))

    print(f"FactZap Batch — {today_str}")
    print(f"  Categories: {', '.join(categories)}")
    print(f"  Schedule:   {', '.join(schedule_times)}")
    print(f"  Mode:       {'DRY RUN' if args.dry_run else 'no-upload' if args.no_upload else 'FULL (generate + render + upload)'}")
    print(f"  Est. cost:  ${len(categories) * 0.14:.2f} (DALL-E + Claude)")

    json_paths: list[Path] = []
    total_cost = 0.0

    # Step 1: Generate all JSON + images
    for category in categories:
        try:
            path = generate_video_data(category, today_str)
            json_paths.append(path)
            total_cost += 0.14  # ~$0.04*3 images + ~$0.02 Claude
        except Exception as e:
            print(f"  ERROR generating {category}: {e}")
            continue

    if not json_paths:
        print("\nNo videos generated. Exiting.")
        sys.exit(1)

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"  DRY RUN COMPLETE — {len(json_paths)} JSON files created")
        print(f"  Total est. cost: ${total_cost:.2f}")
        for p in json_paths:
            print(f"    {p.name}")
        print(f"{'='*60}")
        return

    # Step 2: Render all videos
    print(f"\n{'='*60}")
    print("  RENDERING VIDEOS")
    print(f"{'='*60}")

    rendered: list[tuple[Path, str]] = []
    for i, (path, sched) in enumerate(zip(json_paths, schedule_times)):
        if render_video(path):
            rendered.append((path, sched))
        # Delay between renders to avoid ElevenLabs TTS rate limiting
        if i < len(json_paths) - 1:
            import time
            print("  Waiting 3s before next render (rate limit safety)...")
            time.sleep(3)

    if not rendered:
        print("\nNo videos rendered. Exiting.")
        sys.exit(1)

    if args.no_upload:
        print(f"\n{'='*60}")
        print(f"  RENDER COMPLETE — {len(rendered)} videos ready")
        print(f"{'='*60}")
        return

    # Step 3: Upload with scheduled times
    print(f"\n{'='*60}")
    print("  UPLOADING TO YOUTUBE")
    print(f"{'='*60}")

    uploaded = 0
    for path, sched in rendered:
        if upload_video(path, sched):
            uploaded += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  BATCH COMPLETE")
    print(f"  Generated: {len(json_paths)}")
    print(f"  Rendered:  {len(rendered)}")
    print(f"  Uploaded:  {uploaded}")
    print(f"  Cost:      ~${total_cost:.2f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
