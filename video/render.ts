#!/usr/bin/env tsx
/**
 * Render orchestrator — parses scripts/data and renders to MP4.
 *
 * Usage:
 *   npx tsx render.ts ../scripts/output/videos/shorts/2026-02-28-market-reaction.md
 *   npx tsx render.ts --roundup data/roundup-2026-02-28.json
 *   npx tsx render.ts --roundup   (uses sample data from Root.tsx)
 *   npx tsx render.ts --dry-run ../scripts/output/videos/shorts/2026-02-28-market-reaction.md
 *   npx tsx render.ts --all
 *   npx tsx render.ts --latest
 */

import "dotenv/config";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, unlinkSync } from "fs";
import { resolve, basename, dirname, join } from "path";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { parseScriptFile } from "./src/parse-script";
import { generateAudio, buildSegmentLabels, buildKidsSegmentLabels, buildTopicSegmentLabels } from "./src/generate-audio";
import { estimateAudioDuration } from "./src/generate-audio";
import type { VideoScript, RoundupData, KidsFactsData, TopicVideoData, WordTimestamp, SegmentTiming } from "./src/types";
import type { VoiceProfile } from "./src/generate-audio";

const FPS = 30;
const RENDERED_DIR = resolve(__dirname, "../scripts/output/videos/rendered");
const PUBLIC_AUDIO_DIR = resolve(__dirname, "public", "audio");

/**
 * Clean stale voiceover audio files from public/audio/ before each render.
 * Prevents audio cross-contamination when sequential renders share the directory.
 * Only removes vo-*.mp3 files (generated voiceovers), not music/sfx.
 */
function cleanPublicAudio(): void {
  if (!existsSync(PUBLIC_AUDIO_DIR)) return;
  const files = readdirSync(PUBLIC_AUDIO_DIR).filter(f => f.startsWith("vo-") && f.endsWith(".mp3"));
  for (const file of files) {
    unlinkSync(join(PUBLIC_AUDIO_DIR, file));
  }
  if (files.length > 0) {
    console.log(`  Cleaned ${files.length} stale audio file(s) from public/audio/`);
  }
}

/**
 * Delete webpack cache to force a fresh bundle that includes the latest public/ files.
 */
function clearWebpackCache(): void {
  const cacheDir = resolve(__dirname, "node_modules/.cache/webpack");
  if (existsSync(cacheDir)) {
    rmSync(cacheDir, { recursive: true, force: true });
    console.log(`  Cleared webpack cache`);
  }
}

// ───────────────────────────────────────────────────────────
// Roundup rendering (new multi-market format)
// ───────────────────────────────────────────────────────────

async function renderRoundup(
  jsonPath: string | null,
  dryRun: boolean
): Promise<void> {
  let data: RoundupData;

  if (jsonPath && existsSync(jsonPath)) {
    console.log(`Loading roundup data from: ${jsonPath}`);
    data = JSON.parse(readFileSync(jsonPath, "utf-8"));
  } else {
    // Use sample data — render the default composition
    console.log("Using sample roundup data (no JSON provided)");
    data = null as any; // will use defaultProps from Root.tsx
  }

  const totalMarkets =
    data
      ? data.todayMarkets.length + data.featuredMarkets.length
      : 7; // sample default

  console.log(`\n${"=".repeat(60)}`);
  console.log(`Daily Roundup — ${data?.date || "sample"}`);
  console.log(`  Markets: ${totalMarkets}`);

  // Clean stale audio files
  cleanPublicAudio();

  // Build segment labels for audio-driven timing
  const segmentLabels = data
    ? buildSegmentLabels(data.todayMarkets.length, data.featuredMarkets.length)
    : [];

  // Generate TTS from the voiceover text with segment mapping
  let audioResult: { filePath: string | null; durationSeconds: number; wordTimestamps: WordTimestamp[]; segmentTimings: SegmentTiming[] } = {
    filePath: null, durationSeconds: 60, wordTimestamps: [], segmentTimings: [],
  };
  if (data?.voiceover) {
    const fakeScript: VideoScript = {
      title: "roundup",
      format: "short",
      duration: 60,
      topic: "",
      date: data.date,
      contentType: "roundup",
      sections: [{ name: "VO", timeRange: "", visual: "", textOnScreen: "", voiceover: data.voiceover }],
      productionNotes: { music: "", pacing: "", screenshots: [] },
    };
    audioResult = await generateAudio(fakeScript, resolve(__dirname, "tmp/audio"), segmentLabels);
  }

  // Duration: driven by audio length (since visuals now sync to audio)
  const durationSec = Math.max(audioResult.durationSeconds, 30);
  const durationInFrames = Math.ceil(durationSec * FPS);

  console.log(`  Duration: ${durationSec}s (${durationInFrames} frames)`);

  if (dryRun) {
    console.log(`\n  [DRY RUN] Roundup data:`);
    console.log(JSON.stringify(data, null, 2));
    return;
  }

  const outputPath = join(
    RENDERED_DIR,
    "shorts",
    `${data?.date || "sample"}-daily-roundup.mp4`
  );
  mkdirSync(dirname(outputPath), { recursive: true });

  // Build inputProps — pass word timestamps + segment timings for audio-driven visuals
  const inputProps: Record<string, unknown> = {};
  if (data) inputProps.data = data;
  if (audioResult.filePath) inputProps.audioSrc = audioResult.filePath;
  if (audioResult.wordTimestamps.length > 0) inputProps.wordTimestamps = audioResult.wordTimestamps;
  if (audioResult.segmentTimings.length > 0) inputProps.segmentTimings = audioResult.segmentTimings;

  // Clear webpack cache so the bundle picks up the freshly-generated audio file
  clearWebpackCache();

  console.log(`  Bundling Remotion project...`);
  const bundleLocation = await bundle({
    entryPoint: resolve(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });

  console.log(`  Selecting composition: DailyRoundup`);
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "DailyRoundup",
    inputProps,
  });

  composition.durationInFrames = durationInFrames;
  composition.fps = FPS;

  console.log(`  Rendering to: ${outputPath}`);
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputPath,
    inputProps,
  });

  console.log(`  Done! Output: ${outputPath}`);
}

// ───────────────────────────────────────────────────────────
// Kids "Did You Know?" rendering
// ───────────────────────────────────────────────────────────

async function renderKids(
  jsonPath: string | null,
  dryRun: boolean
): Promise<void> {
  if (!jsonPath || !existsSync(jsonPath)) {
    console.log("Usage: npx tsx render.ts --kids <data.json>");
    console.log("  Provide a kids facts JSON file.");
    process.exit(1);
  }

  console.log(`Loading kids facts data from: ${jsonPath}`);
  const data: KidsFactsData = JSON.parse(readFileSync(jsonPath, "utf-8"));

  console.log(`\n${"=".repeat(60)}`);
  console.log(`Kids Facts — ${data.topic} (${data.date})`);
  console.log(`  Facts: ${data.facts.length}`);

  // Clean stale audio files to prevent cross-contamination between batch renders
  cleanPublicAudio();

  // Build segment labels for audio-driven timing
  const segmentLabels = buildKidsSegmentLabels(data.facts.length);

  // Generate TTS with kids voice
  let audioResult: { filePath: string | null; durationSeconds: number; wordTimestamps: WordTimestamp[]; segmentTimings: SegmentTiming[] } = {
    filePath: null, durationSeconds: 45, wordTimestamps: [], segmentTimings: [],
  };
  if (data.voiceover) {
    const fakeScript: VideoScript = {
      title: "kids-facts",
      format: "short",
      duration: 45,
      topic: data.topic,
      date: data.date,
      contentType: "kids",
      sections: [{ name: "VO", timeRange: "", visual: "", textOnScreen: "", voiceover: data.voiceover }],
      productionNotes: { music: "", pacing: "", screenshots: [] },
    };
    audioResult = await generateAudio(fakeScript, resolve(__dirname, "tmp/audio"), segmentLabels, "kids");
  }

  const durationSec = Math.max(audioResult.durationSeconds, 20);
  const durationInFrames = Math.ceil(durationSec * FPS);

  console.log(`  Duration: ${durationSec}s (${durationInFrames} frames)`);

  if (dryRun) {
    console.log(`\n  [DRY RUN] Kids facts data:`);
    console.log(JSON.stringify(data, null, 2));
    return;
  }

  const slug = data.category.toLowerCase().replace(/\s+/g, "-");
  const outputPath = join(
    RENDERED_DIR,
    "shorts",
    `${data.date}-kids-${slug}.mp4`
  );
  mkdirSync(dirname(outputPath), { recursive: true });

  const inputProps: Record<string, unknown> = { data };
  if (audioResult.filePath) inputProps.audioSrc = audioResult.filePath;
  if (audioResult.wordTimestamps.length > 0) inputProps.wordTimestamps = audioResult.wordTimestamps;
  if (audioResult.segmentTimings.length > 0) inputProps.segmentTimings = audioResult.segmentTimings;

  // Clear webpack cache so the bundle picks up the freshly-generated audio file
  clearWebpackCache();

  console.log(`  Bundling Remotion project...`);
  const bundleLocation = await bundle({
    entryPoint: resolve(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });

  console.log(`  Selecting composition: KidsFacts`);
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "KidsFacts",
    inputProps,
  });

  composition.durationInFrames = durationInFrames;
  composition.fps = FPS;

  console.log(`  Rendering to: ${outputPath}`);
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputPath,
    inputProps,
  });

  console.log(`  Done! Output: ${outputPath}`);
}

// ───────────────────────────────────────────────────────────
// Topic Video rendering (true crime, personal finance, etc.)
// ───────────────────────────────────────────────────────────

async function renderTopic(
  jsonPath: string | null,
  dryRun: boolean
): Promise<void> {
  if (!jsonPath || !existsSync(jsonPath)) {
    console.log("Usage: npx tsx render.ts --topic <data.json>");
    console.log("  Provide a topic video JSON file.");
    process.exit(1);
  }

  console.log(`Loading topic video data from: ${jsonPath}`);
  const data: TopicVideoData = JSON.parse(readFileSync(jsonPath, "utf-8"));

  console.log(`\n${"=".repeat(60)}`);
  console.log(`Topic Video — ${data.channel} (${data.date})`);
  console.log(`  Cards: ${data.cards.length}`);

  // Clean stale audio files
  cleanPublicAudio();

  // Build segment labels for audio-driven timing
  const segmentLabels = buildTopicSegmentLabels(data.cards.length);

  // Voice profile matches channel
  const voiceProfile: VoiceProfile = data.channel === "truecrime" ? "truecrime" : "finance";

  // Generate TTS
  let audioResult: { filePath: string | null; durationSeconds: number; wordTimestamps: WordTimestamp[]; segmentTimings: SegmentTiming[] } = {
    filePath: null, durationSeconds: 60, wordTimestamps: [], segmentTimings: [],
  };
  if (data.voiceover) {
    const fakeScript: VideoScript = {
      title: `topic-${data.channel}`,
      format: "short",
      duration: 60,
      topic: data.channel,
      date: data.date,
      contentType: "topic",
      sections: [{ name: "VO", timeRange: "", visual: "", textOnScreen: "", voiceover: data.voiceover }],
      productionNotes: { music: "", pacing: "", screenshots: [] },
    };
    audioResult = await generateAudio(fakeScript, resolve(__dirname, "tmp/audio"), segmentLabels, voiceProfile);
  }

  const durationSec = Math.max(audioResult.durationSeconds, 20);
  const durationInFrames = Math.ceil(durationSec * FPS);

  console.log(`  Duration: ${durationSec}s (${durationInFrames} frames)`);

  if (dryRun) {
    console.log(`\n  [DRY RUN] Topic video data:`);
    console.log(JSON.stringify(data, null, 2));
    return;
  }

  const slug = data.channel;
  const outputPath = join(
    RENDERED_DIR,
    "shorts",
    `${data.date}-${slug}-topic.mp4`
  );
  mkdirSync(dirname(outputPath), { recursive: true });

  const inputProps: Record<string, unknown> = { data };
  if (audioResult.filePath) inputProps.audioSrc = audioResult.filePath;
  if (audioResult.wordTimestamps.length > 0) inputProps.wordTimestamps = audioResult.wordTimestamps;
  if (audioResult.segmentTimings.length > 0) inputProps.segmentTimings = audioResult.segmentTimings;

  // Clear webpack cache so the bundle picks up the freshly-generated audio file
  clearWebpackCache();

  console.log(`  Bundling Remotion project...`);
  const bundleLocation = await bundle({
    entryPoint: resolve(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });

  console.log(`  Selecting composition: TopicVideo`);
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "TopicVideo",
    inputProps,
  });

  composition.durationInFrames = durationInFrames;
  composition.fps = FPS;

  console.log(`  Rendering to: ${outputPath}`);
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputPath,
    inputProps,
  });

  console.log(`  Done! Output: ${outputPath}`);
}

// ───────────────────────────────────────────────────────────
// Script-based rendering (original ShortForm format)
// ───────────────────────────────────────────────────────────

function findScriptFiles(args: string[]): string[] {
  const all = args.includes("--all");
  const latest = args.includes("--latest");
  const paths = args.filter((a) => !a.startsWith("--"));

  if (paths.length > 0) {
    return paths.map((p) => resolve(p));
  }

  const shortsDir = resolve(__dirname, "../scripts/output/videos/shorts");
  const longformDir = resolve(__dirname, "../scripts/output/videos/longform");
  const scriptFiles: string[] = [];

  for (const dir of [shortsDir, longformDir]) {
    if (!existsSync(dir)) continue;
    const files = readdirSync(dir)
      .filter((f) => f.endsWith(".md"))
      .sort()
      .map((f) => join(dir, f));
    scriptFiles.push(...files);
  }

  if (latest && scriptFiles.length > 0) {
    return [scriptFiles[scriptFiles.length - 1]];
  }

  if (all) {
    return scriptFiles.filter((f) => {
      const outPath = getOutputPath(f);
      return !existsSync(outPath);
    });
  }

  return scriptFiles;
}

function getOutputPath(scriptPath: string): string {
  const name = basename(scriptPath, ".md");
  const isShort = scriptPath.includes("shorts");
  const subDir = isShort ? "shorts" : "longform";
  return join(RENDERED_DIR, subDir, `${name}.mp4`);
}

async function renderScript(
  scriptPath: string,
  dryRun: boolean
): Promise<void> {
  console.log(`\n${"=".repeat(60)}`);
  console.log(`Parsing: ${scriptPath}`);

  const script = parseScriptFile(scriptPath);

  console.log(`  Title: ${script.title}`);
  console.log(`  Format: ${script.format}`);
  console.log(`  Sections: ${script.sections.length}`);
  console.log(`  Content Type: ${script.contentType}`);

  // Clean stale audio files
  cleanPublicAudio();

  const audio = await generateAudio(script, resolve(__dirname, "tmp/audio"));
  const maxSectionEnd = Math.max(
    ...script.sections.map((s) => {
      const m = s.timeRange.match(/\d+\s*-\s*(\d+)/);
      return m ? parseInt(m[1], 10) : 0;
    }),
    0
  );
  const durationSec = Math.max(
    audio.durationSeconds,
    maxSectionEnd,
    script.duration
  );
  const durationInFrames = Math.ceil(durationSec * FPS);

  console.log(`  Duration: ${durationSec}s (${durationInFrames} frames)`);

  if (dryRun) {
    console.log(`\n  [DRY RUN] Parsed script JSON:`);
    console.log(JSON.stringify(script, null, 2));
    return;
  }

  const compositionId = "ShortForm";
  const outputPath = getOutputPath(scriptPath);

  const inputProps: Record<string, unknown> = { script };
  if (audio.filePath) inputProps.audioSrc = audio.filePath;

  mkdirSync(dirname(outputPath), { recursive: true });

  // Clear webpack cache so the bundle picks up the freshly-generated audio file
  clearWebpackCache();

  console.log(`  Bundling Remotion project...`);
  const bundleLocation = await bundle({
    entryPoint: resolve(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });

  console.log(`  Selecting composition: ${compositionId}`);
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: compositionId,
    inputProps,
  });

  composition.durationInFrames = durationInFrames;
  composition.fps = FPS;

  console.log(`  Rendering to: ${outputPath}`);
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputPath,
    inputProps,
  });

  console.log(`  Done! Output: ${outputPath}`);
}

// ───────────────────────────────────────────────────────────
// Main
// ───────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log(`Usage:
  npx tsx render.ts <script.md>              Render a ShortForm script
  npx tsx render.ts --roundup [data.json]    Render Daily Roundup (JSON or sample)
  npx tsx render.ts --kids <data.json>       Render Kids "Did You Know?" video
  npx tsx render.ts --topic <data.json>      Render Topic Video (true crime/finance)
  npx tsx render.ts --all                    Render all unrendered scripts
  npx tsx render.ts --latest                 Render the most recent script
  npx tsx render.ts --dry-run <script.md>    Parse only, print JSON`);
    process.exit(0);
  }

  const dryRun = args.includes("--dry-run");
  const isRoundup = args.includes("--roundup");
  const isKids = args.includes("--kids");
  const isTopic = args.includes("--topic");

  if (isTopic) {
    const jsonPath =
      args.filter((a) => !a.startsWith("--") && a.endsWith(".json"))[0] ||
      null;
    await renderTopic(jsonPath ? resolve(jsonPath) : null, dryRun);
  } else if (isKids) {
    const jsonPath =
      args.filter((a) => !a.startsWith("--") && a.endsWith(".json"))[0] ||
      null;
    await renderKids(jsonPath ? resolve(jsonPath) : null, dryRun);
  } else if (isRoundup) {
    // Find the JSON path (first non-flag arg)
    const jsonPath =
      args.filter((a) => !a.startsWith("--") && a.endsWith(".json"))[0] ||
      null;
    await renderRoundup(jsonPath ? resolve(jsonPath) : null, dryRun);
  } else {
    const scriptFiles = findScriptFiles(args);

    if (scriptFiles.length === 0) {
      console.log("No script files found to render.");
      process.exit(0);
    }

    console.log(
      `Found ${scriptFiles.length} script(s) to ${dryRun ? "parse" : "render"}.`
    );

    for (const scriptPath of scriptFiles) {
      if (!existsSync(scriptPath)) {
        console.error(`File not found: ${scriptPath}`);
        continue;
      }
      await renderScript(scriptPath, dryRun);
    }
  }

  console.log(`\n${"=".repeat(60)}`);
  console.log(`All done!`);
}

main().catch((err) => {
  console.error("Render failed:", err);
  process.exit(1);
});
