/**
 * ElevenLabs TTS integration with word-level timestamps and segment mapping.
 *
 * Uses convertWithTimestamps to get character-level alignment data,
 * groups characters into words, maps words to voiceover segments,
 * and returns audio + word timestamps + segment timings for
 * audio-driven visual sync.
 */

import { writeFileSync, mkdirSync } from "fs";
import { join, resolve } from "path";
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
import type { VideoScript, WordTimestamp, SegmentTiming } from "./types";

export interface AudioResult {
  filePath: string | null;
  durationSeconds: number;
  wordTimestamps: WordTimestamp[];
  segmentTimings: SegmentTiming[];
}

export type VoiceProfile = "default" | "kids" | "truecrime" | "finance" | "braindrop" | "mindtrap" | "lostfiles" | "redacted";

// Voice IDs
const VOICE_ID_DEFAULT = "TxGEqnHWrfWFTfGW9XjX"; // Josh — male, young, fast-paced
const VOICE_ID_KIDS = "EXAVITQu4vr4xnSDxMaL"; // Bella — warm, enthusiastic, female
const VOICE_ID_TRUECRIME = "pNInz6obpgDQGcFmaJgB"; // Adam — deep, dramatic male
const VOICE_ID_FINANCE = "TxGEqnHWrfWFTfGW9XjX"; // Josh — confident, authoritative

function getVoiceConfig(profile: VoiceProfile) {
  if (profile === "kids") {
    return {
      voiceId: VOICE_ID_KIDS,
      settings: {
        stability: 0.55,
        similarityBoost: 0.75,
        style: 0.3, // more expressive for kids
        useSpeakerBoost: true,
      },
    };
  }
  if (profile === "truecrime" || profile === "mindtrap" || profile === "lostfiles" || profile === "redacted") {
    return {
      voiceId: VOICE_ID_TRUECRIME,
      settings: {
        stability: 0.7,
        similarityBoost: 0.75,
        style: 0.4, // dramatic, measured delivery
        useSpeakerBoost: true,
      },
    };
  }
  if (profile === "braindrop") {
    return {
      voiceId: VOICE_ID_DEFAULT,
      settings: {
        stability: 0.4,
        similarityBoost: 0.75,
        style: 0.3, // confident, energetic, faster pace
        useSpeakerBoost: true,
      },
    };
  }
  if (profile === "finance") {
    return {
      voiceId: VOICE_ID_FINANCE,
      settings: {
        stability: 0.65,
        similarityBoost: 0.75,
        style: 0.2, // confident, authoritative
        useSpeakerBoost: true,
      },
    };
  }
  return {
    voiceId: VOICE_ID_DEFAULT,
    settings: {
      stability: 0.6,
      similarityBoost: 0.75,
      style: 0.1,
      useSpeakerBoost: true,
    },
  };
}

/**
 * Estimate voiceover duration from word count.
 * Average speaking pace: ~150 words per minute (2.5 words/sec).
 */
export function estimateAudioDuration(script: VideoScript): number {
  const totalWords = script.sections
    .map((s) => s.voiceover.split(/\s+/).filter(Boolean).length)
    .reduce((a, b) => a + b, 0);
  return Math.max(10, Math.ceil(totalWords / 2.5));
}

/**
 * Build the full voiceover text from all sections.
 */
function buildVoiceoverText(script: VideoScript): string {
  return script.sections
    .map((s) => s.voiceover)
    .filter(Boolean)
    .join("\n\n");
}

/**
 * Group character-level alignment data into word-level timestamps.
 */
function groupCharactersIntoWords(
  characters: string[],
  startTimes: number[],
  endTimes: number[]
): WordTimestamp[] {
  const words: WordTimestamp[] = [];
  let currentWord = "";
  let wordStartTime = 0;
  let wordEndTime = 0;

  for (let i = 0; i < characters.length; i++) {
    const char = characters[i];

    if (char === " " || char === "\n" || char === "\r" || char === "\t") {
      if (currentWord.length > 0) {
        words.push({
          word: currentWord,
          startTime: wordStartTime,
          endTime: wordEndTime,
        });
        currentWord = "";
      }
    } else {
      if (currentWord.length === 0) {
        wordStartTime = startTimes[i];
      }
      currentWord += char;
      wordEndTime = endTimes[i];
    }
  }

  if (currentWord.length > 0) {
    words.push({
      word: currentWord,
      startTime: wordStartTime,
      endTime: wordEndTime,
    });
  }

  return words;
}

/**
 * Map word timestamps back to voiceover segments.
 *
 * The voiceover text is split by \n\n into segments.
 * We count words per segment and assign word timestamps
 * sequentially to build per-segment timing data.
 *
 * @param voText Full voiceover text (segments separated by \n\n)
 * @param wordTimestamps Word-level timestamps from TTS
 * @param segmentLabels Labels for each segment (hook, market-0, etc.)
 */
function mapWordsToSegments(
  voText: string,
  wordTimestamps: WordTimestamp[],
  segmentLabels: string[]
): SegmentTiming[] {
  const paragraphs = voText.split(/\n\n+/).filter((p) => p.trim().length > 0);
  const segments: SegmentTiming[] = [];
  let wordIndex = 0;

  for (let i = 0; i < paragraphs.length; i++) {
    const paragraphWords = paragraphs[i].split(/\s+/).filter(Boolean);
    const wordCount = paragraphWords.length;
    const label = i < segmentLabels.length ? segmentLabels[i] : `segment-${i}`;

    const segmentWords = wordTimestamps.slice(wordIndex, wordIndex + wordCount);
    wordIndex += wordCount;

    if (segmentWords.length > 0) {
      segments.push({
        label,
        startTime: segmentWords[0].startTime,
        endTime: segmentWords[segmentWords.length - 1].endTime,
        words: segmentWords,
      });
    }
  }

  return segments;
}

/**
 * Build segment labels from roundup data structure.
 * Order: hook, market-0..N, featured-0..M, cta
 */
export function buildSegmentLabels(
  todayCount: number,
  featuredCount: number
): string[] {
  const labels: string[] = ["hook"];
  for (let i = 0; i < todayCount; i++) labels.push(`market-${i}`);
  for (let i = 0; i < featuredCount; i++) labels.push(`featured-${i}`);
  labels.push("cta");
  return labels;
}

/**
 * Build segment labels for kids facts composition.
 * Order: hook, fact-0..N, cta
 */
export function buildKidsSegmentLabels(factCount: number): string[] {
  const labels: string[] = [];
  for (let i = 0; i < factCount; i++) labels.push(`fact-${i}`);
  labels.push("cta");
  return labels;
}

/**
 * Build segment labels for topic video composition.
 * Order: hook, card-0..N, cta
 */
export function buildTopicSegmentLabels(cardCount: number): string[] {
  const labels: string[] = ["hook"];
  for (let i = 0; i < cardCount; i++) labels.push(`card-${i}`);
  labels.push("cta");
  return labels;
}

/**
 * Get MP3 duration from the buffer size.
 */
function estimateMp3Duration(buffer: Buffer): number {
  const bitrate = 128000;
  return (buffer.length * 8) / bitrate;
}

/**
 * Collect ReadableStream<Uint8Array> into a single Buffer.
 */
async function streamToBuffer(
  stream: ReadableStream<Uint8Array>
): Promise<Buffer> {
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) chunks.push(value);
  }
  return Buffer.concat(chunks);
}

/**
 * Generate voiceover audio via ElevenLabs TTS with word timestamps.
 *
 * @param script VideoScript with voiceover text
 * @param outputDir Temp output directory
 * @param segmentLabels Optional segment labels for audio-driven visual sync
 * @param voiceProfile Voice selection: "default" (Josh) or "kids" (Bella)
 */
export async function generateAudio(
  script: VideoScript,
  outputDir: string,
  segmentLabels?: string[],
  voiceProfile: VoiceProfile = "default"
): Promise<AudioResult> {
  const apiKey = process.env.ELEVENLABS_API_KEY;

  if (!apiKey) {
    console.log("[audio] No ELEVENLABS_API_KEY — falling back to duration estimate");
    return {
      filePath: null,
      durationSeconds: estimateAudioDuration(script),
      wordTimestamps: [],
      segmentTimings: [],
    };
  }

  const voText = buildVoiceoverText(script);
  if (!voText.trim()) {
    console.log("[audio] No voiceover text found in script");
    return { filePath: null, durationSeconds: estimateAudioDuration(script), wordTimestamps: [], segmentTimings: [] };
  }

  const wordCount = voText.split(/\s+/).length;
  console.log(
    `[audio] Generating TTS with timestamps (${wordCount} words)...`
  );
  console.log(`[audio] Voiceover preview: "${voText.slice(0, 80)}..."`);

  mkdirSync(outputDir, { recursive: true });

  const client = new ElevenLabsClient({ apiKey });
  const voiceConfig = getVoiceConfig(voiceProfile);

  const publicDir = resolve(__dirname, "..", "public", "audio");
  mkdirSync(publicDir, { recursive: true });
  const filename = `vo-${script.date}-${Date.now()}.mp3`;
  const filePath = join(publicDir, filename);

  // Retry logic for ElevenLabs rate limiting
  const MAX_RETRIES = 3;
  const RETRY_DELAY_MS = 5000;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await client.textToSpeech.convertWithTimestamps(voiceConfig.voiceId, {
        text: voText,
        modelId: "eleven_turbo_v2_5",
        outputFormat: "mp3_44100_128",
        voiceSettings: voiceConfig.settings,
      });

      const audioBuffer = Buffer.from(response.audioBase64, "base64");
      if (audioBuffer.length < 1000) {
        throw new Error(`Audio buffer suspiciously small (${audioBuffer.length} bytes) — possible empty/cached response`);
      }
      const durationSeconds = Math.round(estimateMp3Duration(audioBuffer));

      let wordTimestamps: WordTimestamp[] = [];
      let segmentTimings: SegmentTiming[] = [];

      if (response.alignment) {
        wordTimestamps = groupCharactersIntoWords(
          response.alignment.characters,
          response.alignment.characterStartTimesSeconds,
          response.alignment.characterEndTimesSeconds
        );
        console.log(`[audio] Got ${wordTimestamps.length} word timestamps`);

        if (segmentLabels && segmentLabels.length > 0) {
          segmentTimings = mapWordsToSegments(voText, wordTimestamps, segmentLabels);
          console.log(`[audio] Mapped ${segmentTimings.length} segments:`);
          for (const seg of segmentTimings) {
            console.log(`  ${seg.label}: ${seg.startTime.toFixed(1)}s - ${seg.endTime.toFixed(1)}s (${seg.words.length} words)`);
          }
        }
      }

      writeFileSync(filePath, audioBuffer);
      console.log(
        `[audio] Saved ${(audioBuffer.length / 1024).toFixed(0)}KB → ${filePath} (~${durationSeconds}s)`
      );

      return {
        filePath: `audio/${filename}`,
        durationSeconds,
        wordTimestamps,
        segmentTimings,
      };
    } catch (err) {
      if (attempt < MAX_RETRIES) {
        console.log(`[audio] Attempt ${attempt}/${MAX_RETRIES} failed: ${err}`);
        console.log(`[audio] Retrying in ${RETRY_DELAY_MS / 1000}s...`);
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS));
        continue;
      }

      console.log(`[audio] All ${MAX_RETRIES} attempts with timestamps failed, falling back to convert: ${err}`);

      const audioStream = await client.textToSpeech.convert(voiceConfig.voiceId, {
        text: voText,
        modelId: "eleven_turbo_v2_5",
        outputFormat: "mp3_44100_128",
        voiceSettings: voiceConfig.settings,
      });

      const audioBuffer = await streamToBuffer(audioStream);
      if (audioBuffer.length < 1000) {
        throw new Error(`Fallback audio buffer suspiciously small (${audioBuffer.length} bytes) — TTS generation failed`);
      }
      const durationSeconds = Math.round(estimateMp3Duration(audioBuffer));

      writeFileSync(filePath, audioBuffer);
      console.log(
        `[audio] Saved ${(audioBuffer.length / 1024).toFixed(0)}KB → ${filePath} (~${durationSeconds}s)`
      );

      return {
        filePath: `audio/${filename}`,
        durationSeconds,
        wordTimestamps: [],
        segmentTimings: [],
      };
    }
  }

  // Should never reach here, but TypeScript needs a return
  throw new Error("Audio generation failed after all retries");
}
