import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useVideoConfig,
  interpolate,
  useCurrentFrame,
} from "remotion";
import type { TopicVideoProps, SegmentTiming } from "../types";
import { getChannelTheme } from "../themes";
import { HookSlide } from "../components/HookSlide";
import { TopicCard } from "../components/TopicCard";
import { TopicCTA } from "../components/TopicCTA";
import { AnimatedCaption } from "../components/AnimatedCaption";
import { GOOGLE_FONTS_CSS, HEADING_FONT } from "../styles/fonts";

/** Clamp a frame range within the composition's total frames. */
function clampDuration(from: number, duration: number, total: number): number {
  return Math.max(1, Math.min(duration, total - from));
}

/** Look up a segment's timing by label. Returns frame-based start/duration. */
function getSegmentFrames(
  segmentTimings: SegmentTiming[],
  label: string,
  fps: number
): { from: number; durationInFrames: number } | null {
  const seg = segmentTimings.find((s) => s.label === label);
  if (!seg) return null;
  return {
    from: Math.round(seg.startTime * fps),
    durationInFrames: Math.max(
      1,
      Math.round((seg.endTime - seg.startTime) * fps)
    ),
  };
}

/**
 * Themed caption wrapper — passes channel-specific highlight color to AnimatedCaption.
 */
const ThemedCaption: React.FC<{
  wordTimestamps: TopicVideoProps["wordTimestamps"];
  highlightColor: string;
}> = ({ wordTimestamps, highlightColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!wordTimestamps || wordTimestamps.length === 0) return null;

  const currentTime = frame / fps;

  let activeIndex = -1;
  for (let i = 0; i < wordTimestamps.length; i++) {
    if (
      currentTime >= wordTimestamps[i].startTime &&
      currentTime < wordTimestamps[i].endTime
    ) {
      activeIndex = i;
      break;
    }
    if (
      i < wordTimestamps.length - 1 &&
      currentTime >= wordTimestamps[i].endTime &&
      currentTime < wordTimestamps[i + 1].startTime
    ) {
      activeIndex = i;
      break;
    }
  }

  if (
    activeIndex === -1 &&
    wordTimestamps.length > 0 &&
    currentTime > wordTimestamps[wordTimestamps.length - 1].endTime
  ) {
    return null;
  }

  if (activeIndex === -1 && currentTime < wordTimestamps[0].startTime) {
    return null;
  }

  if (activeIndex === -1) {
    activeIndex = wordTimestamps.length - 1;
  }

  const WORDS_PER_CHUNK = 6;
  const chunkIndex = Math.floor(activeIndex / WORDS_PER_CHUNK);
  const chunkStart = chunkIndex * WORDS_PER_CHUNK;
  const chunkEnd = Math.min(
    chunkStart + WORDS_PER_CHUNK,
    wordTimestamps.length
  );
  const visibleWords = wordTimestamps.slice(chunkStart, chunkEnd);

  const activeWord = wordTimestamps[activeIndex];
  const wordProgress =
    activeWord.endTime > activeWord.startTime
      ? (currentTime - activeWord.startTime) /
        (activeWord.endTime - activeWord.startTime)
      : 0;
  const activeScale = 1 + Math.max(0, 0.08 * (1 - wordProgress));

  return (
    <div
      style={{
        position: "absolute",
        bottom: 180,
        left: 40,
        right: 40,
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "center",
        gap: 10,
      }}
    >
      {visibleWords.map((wt, i) => {
        const globalIndex = chunkStart + i;
        const isActive = globalIndex === activeIndex;
        const isPast = globalIndex < activeIndex;

        return (
          <span
            key={`${globalIndex}-${wt.word}`}
            style={{
              fontFamily: HEADING_FONT,
              fontWeight: 900,
              fontSize: 52,
              lineHeight: 1.2,
              color: isActive
                ? highlightColor
                : isPast
                  ? "#ffffff"
                  : "rgba(255, 255, 255, 0.35)",
              transform: isActive ? `scale(${activeScale})` : "scale(1)",
              textShadow: isActive
                ? `0 0 20px ${highlightColor}99, 0 2px 8px rgba(0, 0, 0, 0.8)`
                : "0 2px 6px rgba(0, 0, 0, 0.7)",
              transition: "color 0.05s, transform 0.05s",
            }}
          >
            {wt.word}
          </span>
        );
      })}
    </div>
  );
};

/**
 * TopicVideo — generic themed composition for channel-specific short-form videos.
 *
 * Structure: hook → card-0 → card-1 → card-2 → cta
 * Audio-driven segment timing (same pattern as DailyRoundup/KidsFacts).
 * Fallback: 3s hook, 7s per card, 4s CTA.
 */
export const TopicVideo: React.FC<TopicVideoProps> = ({
  data,
  audioSrc,
  wordTimestamps,
  segmentTimings,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();

  const theme = getChannelTheme(data.channel);
  const cardCount = data.cards.length;
  const hasSegments = segmentTimings && segmentTimings.length > 0;

  // --- Background gradient with slow drift ---
  const hueShift = interpolate(frame, [0, durationInFrames], [0, 15], {
    extrapolateRight: "clamp",
  });

  // --- Timing: audio-driven or fixed fallback ---

  // HOOK timing
  const hookSeg = hasSegments
    ? getSegmentFrames(segmentTimings, "hook", fps)
    : null;
  const hookStart = hookSeg ? hookSeg.from : 0;
  const hookDurationFrames = hookSeg
    ? hookSeg.durationInFrames
    : Math.round(3 * fps);
  const hookEnd = hookStart + hookDurationFrames;

  // CARD timings
  const cardTimings = data.cards.map((_, i) => {
    if (hasSegments) {
      const seg = getSegmentFrames(segmentTimings, `card-${i}`, fps);
      if (seg) return seg;
    }
    // Fallback: 7s per card after hook
    const fallbackFrom = hookEnd + i * Math.round(7 * fps);
    return { from: fallbackFrom, durationInFrames: Math.round(7 * fps) };
  });

  // CTA timing
  const ctaSeg = hasSegments
    ? getSegmentFrames(segmentTimings, "cta", fps)
    : null;
  const ctaFrom = ctaSeg
    ? ctaSeg.from
    : (() => {
        const lastCard = cardTimings[cardTimings.length - 1];
        return lastCard
          ? lastCard.from + lastCard.durationInFrames
          : hookEnd;
      })();
  const ctaDuration = ctaSeg
    ? ctaSeg.durationInFrames
    : clampDuration(ctaFrom, Math.round(4 * fps), durationInFrames);

  // Alternating slide directions
  const directions: Array<"left" | "right" | "bottom"> = [
    "right",
    "left",
    "bottom",
    "right",
    "left",
  ];

  return (
    <AbsoluteFill>
      <link rel="stylesheet" href={GOOGLE_FONTS_CSS} />

      {/* Audio track */}
      {audioSrc && <Audio src={staticFile(audioSrc)} />}

      {/* Background — themed dark gradient */}
      <Sequence from={0} durationInFrames={durationInFrames}>
        <AbsoluteFill
          style={{
            background: `linear-gradient(${150 + hueShift}deg, ${theme.gradient[0]} 0%, ${theme.gradient[1]} 100%)`,
          }}
        />
      </Sequence>

      {/* === HOOK === */}
      <Sequence from={hookStart} durationInFrames={hookDurationFrames}>
        <HookSlide
          topLine={data.hookLine}
          bottomLine=""
          accent={theme.accent}
          backgroundImage={data.hookImage}
        />
      </Sequence>

      {/* === CONTENT CARDS (audio-synced) === */}
      {data.cards.map((card, i) => {
        const timing = cardTimings[i];
        const dur = clampDuration(
          timing.from,
          timing.durationInFrames,
          durationInFrames
        );
        if (timing.from >= durationInFrames) return null;
        return (
          <Sequence
            key={`card-${i}`}
            from={timing.from}
            durationInFrames={dur}
          >
            <TopicCard
              card={card}
              index={i}
              totalCards={cardCount}
              theme={theme}
              enterDirection={directions[i % directions.length]}
            />
          </Sequence>
        );
      })}

      {/* === CTA === */}
      {ctaFrom < durationInFrames && (
        <Sequence
          from={ctaFrom}
          durationInFrames={clampDuration(
            ctaFrom,
            ctaDuration,
            durationInFrames
          )}
        >
          <TopicCTA
            ctaLine={data.ctaLine || "Subscribe for more"}
            theme={theme}
          />
        </Sequence>
      )}

      {/* === ANIMATED CAPTIONS (themed highlight color) === */}
      {wordTimestamps && wordTimestamps.length > 0 && (
        <Sequence from={0} durationInFrames={durationInFrames}>
          <ThemedCaption
            wordTimestamps={wordTimestamps}
            highlightColor={theme.captionHighlight}
          />
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
