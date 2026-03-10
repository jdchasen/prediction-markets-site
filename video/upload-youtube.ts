#!/usr/bin/env tsx
/**
 * Upload a rendered video to YouTube as a Short.
 *
 * Channel is auto-detected from JSON content:
 *   - JSON with "facts" array  → FactZap channel (YOUTUBE_KIDS_REFRESH_TOKEN)
 *   - JSON with "todayMarkets" → MPM channel (YOUTUBE_REFRESH_TOKEN)
 *
 * Usage:
 *   npx tsx upload-youtube.ts data/roundup-2026-02-28.json
 *   npx tsx upload-youtube.ts data/kids-animals-2026-03-04.json
 *   npx tsx upload-youtube.ts --latest            (latest roundup)
 *   npx tsx upload-youtube.ts --latest-kids        (latest kids)
 *
 * Environment variables (in video/.env):
 *   YOUTUBE_CLIENT_ID
 *   YOUTUBE_CLIENT_SECRET
 *   YOUTUBE_REFRESH_TOKEN          (MPM channel)
 *   YOUTUBE_KIDS_REFRESH_TOKEN     (FactZap channel)
 */

import "dotenv/config";
import { existsSync, readFileSync, createReadStream, readdirSync } from "fs";
import { resolve, join, basename } from "path";
import { google } from "googleapis";
import type { RoundupData, KidsFactsData, TopicVideoData } from "./src/types";

const RENDERED_DIR = resolve(__dirname, "../scripts/output/videos/rendered/shorts");
const DATA_DIR = resolve(__dirname, "data");

const KALSHI_REFERRAL = "https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21";
const POLYMARKET_REFERRAL = "https://polymarket.us/1762";

// ─── Auto-detect content type from JSON ───

type ContentType = "roundup" | "kids" | "truecrime" | "finance";

function detectContentType(data: Record<string, unknown>): ContentType {
  // Topic video channels (true crime / finance)
  if ("cards" in data && Array.isArray(data.cards) && "channel" in data) {
    const channel = data.channel as string;
    if (channel === "truecrime") return "truecrime";
    if (channel === "finance") return "finance";
  }

  if ("facts" in data && Array.isArray(data.facts)) return "kids";
  if ("todayMarkets" in data && Array.isArray(data.todayMarkets)) return "roundup";

  // Fallback: check filename-style keys
  if ("category" in data && "hookSubtitle" in data) return "kids";

  throw new Error(
    "Cannot determine content type from JSON. " +
    "Expected 'cards' (topic), 'facts' (kids), or 'todayMarkets' (roundup) field."
  );
}

// ─── Metadata builders ───

function buildRoundupMetadata(data: RoundupData) {
  const allMarkets = [...data.todayMarkets, ...data.featuredMarkets];
  const categories = [...new Set(allMarkets.map((m) => m.category).filter(Boolean))];

  const title = `${data.hookLine} | ${data.date}`;

  const marketLines = allMarkets
    .map((m) => `${m.title} → ${m.probability}% on ${m.platform}`)
    .join("\n");

  const description = [
    `Daily prediction market roundup for ${data.date}.`,
    "",
    marketLines,
    "",
    `Trade on Kalshi: ${KALSHI_REFERRAL}`,
    `Trade on Polymarket: ${POLYMARKET_REFERRAL}`,
    "",
    "Full analysis: https://masterpredictionmarkets.com",
    "",
    "#predictionmarkets #kalshi #polymarket #trading #finance #shorts",
    categories.map((c) => `#${c!.toLowerCase()}`).join(" "),
  ].join("\n");

  const tags = [
    "prediction markets",
    "kalshi",
    "polymarket",
    "trading",
    "finance",
    "shorts",
    "daily markets",
    ...categories.map((c) => c!.toLowerCase()),
    ...allMarkets.slice(0, 3).map((m) => {
      const words = m.title.split(" ").slice(0, 4).join(" ");
      return words.toLowerCase();
    }),
  ];

  return { title, description, tags };
}

function buildKidsMetadata(data: KidsFactsData) {
  // Use Claude-generated clickbait title if available, fallback to old format
  // Shorts truncate at ~40 chars on mobile — keep base title tight
  const baseTitle = data.title
    ? data.title.slice(0, 50)
    : `${data.topic} | Did You Know?`;
  const title = `${baseTitle} #shorts`;

  const factLines = data.facts
    .map((f) => `${f.emoji} ${f.factText}`)
    .join("\n");

  const description = [
    `${data.hookSubtitle}`,
    "",
    factLines,
    "",
    "Subscribe for more amazing facts every day!",
    "",
    `#didyouknow #funfacts #${data.category.toLowerCase()} #scienceforkids #factsyoudidntknow #shorts #factzap`,
  ].join("\n");

  const tags = [
    "did you know",
    "fun facts for kids",
    "mind blowing facts",
    "facts you didn't know",
    "science for kids",
    "learn something new",
    data.category.toLowerCase(),
    "fun facts",
    "amazing facts",
    "shorts",
    "factzap",
    ...data.facts.slice(0, 3).map((f) => {
      const words = f.factText.split(" ").slice(0, 4).join(" ");
      return words.toLowerCase();
    }),
  ];

  return { title, description, tags };
}

function buildTrueCrimeMetadata(data: TopicVideoData) {
  const title = `${data.hookLine} #shorts`;

  const cardLines = data.cards
    .map((c) => `${c.emoji || "🔍"} ${c.title} — ${c.stat}`)
    .join("\n");

  const description = [
    data.hookLine,
    "",
    cardLines,
    "",
    "Cold Trail — the cases nobody talks about. New case every day.",
    "",
    "#truecrime #coldcase #coldtrail #unsolved #dna #crime #documentary #shorts",
  ].join("\n");

  const tags = [
    "true crime",
    "cold case",
    "cold trail",
    "unsolved murders",
    "crime documentary",
    "DNA cold case",
    "shorts",
    ...data.cards.slice(0, 3).map((c) => c.title.toLowerCase().slice(0, 30)),
  ];

  return { title, description, tags };
}

function buildFinanceMetadata(data: TopicVideoData) {
  const title = `${data.hookLine} #shorts`;

  const cardLines = data.cards
    .map((c) => `${c.emoji || "💰"} ${c.title} — ${c.stat}`)
    .join("\n");

  const description = [
    data.hookLine,
    "",
    cardLines,
    "",
    "Money Minute — daily money tips that actually work. New tip every weekday.",
    "",
    "#personalfinance #money #moneyminute #investing #savings #budget #moneytips #shorts",
  ].join("\n");

  const tags = [
    "personal finance",
    "money",
    "money minute",
    "finance",
    "investing",
    "savings",
    "budget",
    "money tips",
    "shorts",
    ...data.cards.slice(0, 3).map((c) => c.title.toLowerCase().slice(0, 30)),
  ];

  return { title, description, tags };
}

// ─── File finders ───

function findVideoFile(dateStr: string, type: ContentType, category?: string): string | null {
  if (type === "truecrime" || type === "finance") {
    const expected = join(RENDERED_DIR, `${dateStr}-${type}-topic.mp4`);
    if (existsSync(expected)) return expected;
  } else if (type === "kids" && category) {
    const slug = category.toLowerCase().replace(/\s+/g, "-");
    const expected = join(RENDERED_DIR, `${dateStr}-kids-${slug}.mp4`);
    if (existsSync(expected)) return expected;
  } else {
    const expected = join(RENDERED_DIR, `${dateStr}-daily-roundup.mp4`);
    if (existsSync(expected)) return expected;
  }

  if (existsSync(RENDERED_DIR)) {
    const keyword = type === "kids" ? "kids" : type === "truecrime" ? "truecrime" : type === "finance" ? "finance" : "roundup";
    const files = readdirSync(RENDERED_DIR)
      .filter((f) => f.includes(dateStr) && f.includes(keyword) && f.endsWith(".mp4"))
      .sort();
    if (files.length > 0) return join(RENDERED_DIR, files[files.length - 1]);
  }

  return null;
}

function findLatestData(prefix: string): string | null {
  if (!existsSync(DATA_DIR)) return null;
  const files = readdirSync(DATA_DIR)
    .filter((f) => f.startsWith(prefix) && f.endsWith(".json"))
    .sort();
  if (files.length === 0) return null;
  return join(DATA_DIR, files[files.length - 1]);
}

// ─── Main ───

async function main() {
  const args = process.argv.slice(2);

  // Parse --schedule flag (e.g., --schedule "2026-03-05T09:00:00-05:00")
  let scheduledAt: string | null = null;
  const schedIdx = args.indexOf("--schedule");
  if (schedIdx !== -1 && args[schedIdx + 1]) {
    scheduledAt = args[schedIdx + 1];
    // Validate it parses as a date
    if (isNaN(new Date(scheduledAt).getTime())) {
      console.error(`Invalid --schedule date: ${scheduledAt}`);
      console.error(`Use ISO format: --schedule "2026-03-05T09:00:00-05:00"`);
      process.exit(1);
    }
  }

  // Find the JSON
  let jsonPath: string | null = null;

  if (args.includes("--latest-truecrime")) {
    jsonPath = findLatestData("truecrime-");
    if (!jsonPath) {
      console.error("No truecrime JSON files found in data/");
      process.exit(1);
    }
  } else if (args.includes("--latest-finance")) {
    jsonPath = findLatestData("finance-");
    if (!jsonPath) {
      console.error("No finance JSON files found in data/");
      process.exit(1);
    }
  } else if (args.includes("--latest-kids")) {
    jsonPath = findLatestData("kids-");
    if (!jsonPath) {
      console.error("No kids JSON files found in data/");
      process.exit(1);
    }
  } else if (args.includes("--latest")) {
    jsonPath = findLatestData("roundup-");
    if (!jsonPath) {
      console.error("No roundup JSON files found in data/");
      process.exit(1);
    }
  } else {
    jsonPath = args.find((a) => a.endsWith(".json")) || null;
    if (jsonPath) jsonPath = resolve(jsonPath);
  }

  if (!jsonPath || !existsSync(jsonPath)) {
    console.error("Usage:");
    console.error("  npx tsx upload-youtube.ts data/roundup-YYYY-MM-DD.json       (MPM channel)");
    console.error("  npx tsx upload-youtube.ts data/kids-animals-YYYY-MM-DD.json  (FactZap channel)");
    console.error("  npx tsx upload-youtube.ts data/truecrime-YYYY-MM-DD.json     (True Crime channel)");
    console.error("  npx tsx upload-youtube.ts data/finance-YYYY-MM-DD.json       (Finance channel)");
    console.error("  npx tsx upload-youtube.ts --latest                           (latest roundup → MPM)");
    console.error("  npx tsx upload-youtube.ts --latest-kids                      (latest kids → FactZap)");
    console.error("  npx tsx upload-youtube.ts --latest-truecrime                 (latest true crime)");
    console.error("  npx tsx upload-youtube.ts --latest-finance                   (latest finance)");
    console.error("\nChannel is auto-detected from JSON content. No flags needed.");
    process.exit(1);
  }

  // Load and auto-detect
  const rawData = JSON.parse(readFileSync(jsonPath, "utf-8"));
  const contentType = detectContentType(rawData);

  const CHANNEL_NAMES: Record<ContentType, string> = {
    roundup: "MPM",
    kids: "FactZap",
    truecrime: "True Crime",
    finance: "Money Minute",
  };
  const channelName = CHANNEL_NAMES[contentType];

  console.log(`\n${"=".repeat(60)}`);
  console.log(`  Content type: ${contentType.toUpperCase()}`);
  console.log(`  Channel:      ${channelName}`);
  console.log(`  Source:       ${basename(jsonPath)}`);
  console.log(`${"=".repeat(60)}\n`);

  // Get the right credentials — each channel can have its own OAuth tokens
  const clientId = contentType === "truecrime"
    ? (process.env.YOUTUBE_TC_CLIENT_ID || process.env.YOUTUBE_CLIENT_ID)
    : contentType === "finance"
      ? (process.env.YOUTUBE_FIN_CLIENT_ID || process.env.YOUTUBE_CLIENT_ID)
      : process.env.YOUTUBE_CLIENT_ID;
  const clientSecret = contentType === "truecrime"
    ? (process.env.YOUTUBE_TC_CLIENT_SECRET || process.env.YOUTUBE_CLIENT_SECRET)
    : contentType === "finance"
      ? (process.env.YOUTUBE_FIN_CLIENT_SECRET || process.env.YOUTUBE_CLIENT_SECRET)
      : process.env.YOUTUBE_CLIENT_SECRET;

  const TOKEN_MAP: Record<ContentType, { envVar: string; label: string }> = {
    roundup: { envVar: "YOUTUBE_REFRESH_TOKEN", label: "YOUTUBE_REFRESH_TOKEN" },
    kids: { envVar: "YOUTUBE_KIDS_REFRESH_TOKEN", label: "YOUTUBE_KIDS_REFRESH_TOKEN" },
    truecrime: { envVar: "YOUTUBE_TC_REFRESH_TOKEN", label: "YOUTUBE_TC_REFRESH_TOKEN" },
    finance: { envVar: "YOUTUBE_FIN_REFRESH_TOKEN", label: "YOUTUBE_FIN_REFRESH_TOKEN" },
  };
  const tokenInfo = TOKEN_MAP[contentType];
  const refreshToken = process.env[tokenInfo.envVar];
  const tokenName = tokenInfo.label;

  if (!clientId || !clientSecret || !refreshToken) {
    console.error("Missing YouTube credentials in .env:");
    if (!clientId) console.error("  - YOUTUBE_CLIENT_ID");
    if (!clientSecret) console.error("  - YOUTUBE_CLIENT_SECRET");
    if (!refreshToken) console.error(`  - ${tokenName} (run: npx tsx auth-youtube.ts)`);
    process.exit(1);
  }

  // Authenticate
  const oauth2Client = new google.auth.OAuth2(clientId, clientSecret);
  oauth2Client.setCredentials({ refresh_token: refreshToken });
  const youtube = google.youtube({ version: "v3", auth: oauth2Client });

  if (contentType === "truecrime" || contentType === "finance") {
    const data = rawData as TopicVideoData;
    console.log(`${contentType}: ${data.hookLine} (${data.date})`);
    console.log(`Cards: ${data.cards.length}`);

    const videoPath = findVideoFile(data.date, contentType);
    if (!videoPath) {
      console.error(`No rendered ${contentType} video found for ${data.date}`);
      process.exit(1);
    }
    console.log(`Video: ${videoPath}`);

    const metadataBuilder = contentType === "truecrime" ? buildTrueCrimeMetadata : buildFinanceMetadata;
    const { title, description, tags } = metadataBuilder(data);
    // True crime → News (25) or Entertainment (24); Finance → Education (27)
    const categoryId = contentType === "truecrime" ? "25" : "27";

    console.log(`\nTitle: ${title}`);
    console.log(`Tags: ${tags.slice(0, 5).join(", ")}...`);

    const action = scheduledAt ? `Scheduling on YouTube → ${channelName}` : `Uploading to YouTube → ${channelName}`;
    console.log(`\n${action}...`);
    if (scheduledAt) console.log(`  Publish at: ${new Date(scheduledAt).toLocaleString()}`);

    const response = await youtube.videos.insert({
      part: ["snippet", "status"],
      requestBody: {
        snippet: {
          title,
          description,
          tags,
          categoryId,
          defaultLanguage: "en",
        },
        status: {
          privacyStatus: scheduledAt ? "private" : "public",
          selfDeclaredMadeForKids: false,
          containsSyntheticMedia: true,
          ...(scheduledAt ? { publishAt: new Date(scheduledAt).toISOString() } : {}),
        },
      },
      media: {
        body: createReadStream(videoPath),
      },
    });

    const videoId = response.data.id;
    if (scheduledAt) {
      console.log(`\nScheduled on ${channelName}! Video ID: ${videoId}`);
      console.log(`Publishes: ${new Date(scheduledAt).toLocaleString()}`);
    } else {
      console.log(`\nUploaded to ${channelName}! Video ID: ${videoId}`);
    }
    console.log(`URL: https://youtube.com/shorts/${videoId}`);
  } else if (contentType === "kids") {
    const data = rawData as KidsFactsData;
    console.log(`Topic: ${data.topic} (${data.date})`);
    console.log(`Facts: ${data.facts.length}`);

    const videoPath = findVideoFile(data.date, "kids", data.category);
    if (!videoPath) {
      console.error(`No rendered kids video found for ${data.date}`);
      process.exit(1);
    }
    console.log(`Video: ${videoPath}`);

    const { title, description, tags } = buildKidsMetadata(data);
    console.log(`\nTitle: ${title}`);
    console.log(`Tags: ${tags.slice(0, 5).join(", ")}...`);

    const action = scheduledAt ? `Scheduling on YouTube → ${channelName}` : `Uploading to YouTube → ${channelName}`;
    console.log(`\n${action}...`);
    if (scheduledAt) console.log(`  Publish at: ${new Date(scheduledAt).toLocaleString()}`);

    const response = await youtube.videos.insert({
      part: ["snippet", "status"],
      requestBody: {
        snippet: {
          title,
          description,
          tags,
          categoryId: "27", // Education
          defaultLanguage: "en",
        },
        status: {
          privacyStatus: scheduledAt ? "private" : "public",
          selfDeclaredMadeForKids: false,
          containsSyntheticMedia: true,
          ...(scheduledAt ? { publishAt: new Date(scheduledAt).toISOString() } : {}),
        },
      },
      media: {
        body: createReadStream(videoPath),
      },
    });

    const videoId = response.data.id;
    if (scheduledAt) {
      console.log(`\nScheduled on ${channelName}! Video ID: ${videoId}`);
      console.log(`Publishes: ${new Date(scheduledAt).toLocaleString()}`);
    } else {
      console.log(`\nUploaded to ${channelName}! Video ID: ${videoId}`);
    }
    console.log(`URL: https://youtube.com/shorts/${videoId}`);
  } else {
    const data = rawData as RoundupData;
    console.log(`Roundup: ${data.date} — ${data.hookLine}`);

    const videoPath = findVideoFile(data.date, "roundup");
    if (!videoPath) {
      console.error(`No rendered video found for ${data.date}`);
      process.exit(1);
    }
    console.log(`Video: ${videoPath}`);

    const { title, description, tags } = buildRoundupMetadata(data);
    console.log(`\nTitle: ${title}`);
    console.log(`Tags: ${tags.slice(0, 5).join(", ")}...`);

    const action = scheduledAt ? `Scheduling on YouTube → ${channelName}` : `Uploading to YouTube → ${channelName}`;
    console.log(`\n${action}...`);
    if (scheduledAt) console.log(`  Publish at: ${new Date(scheduledAt).toLocaleString()}`);

    const response = await youtube.videos.insert({
      part: ["snippet", "status"],
      requestBody: {
        snippet: {
          title,
          description,
          tags,
          categoryId: "25", // News & Politics
          defaultLanguage: "en",
        },
        status: {
          privacyStatus: scheduledAt ? "private" : "public",
          selfDeclaredMadeForKids: false,
          containsSyntheticMedia: true,
          ...(scheduledAt ? { publishAt: new Date(scheduledAt).toISOString() } : {}),
        },
      },
      media: {
        body: createReadStream(videoPath),
      },
    });

    const videoId = response.data.id;
    if (scheduledAt) {
      console.log(`\nScheduled on ${channelName}! Video ID: ${videoId}`);
      console.log(`Publishes: ${new Date(scheduledAt).toLocaleString()}`);
    } else {
      console.log(`\nUploaded to ${channelName}! Video ID: ${videoId}`);
    }
    console.log(`URL: https://youtube.com/shorts/${videoId}`);
  }
}

main().catch((err) => {
  console.error("Upload failed:", err.message || err);
  process.exit(1);
});
