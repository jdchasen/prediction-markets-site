import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { HEADING_FONT, BODY_FONT } from "../styles/fonts";
import type { TopicCard as TopicCardType } from "../types";
import type { ChannelTheme } from "../themes";

interface TopicCardCinematicProps {
  card: TopicCardType;
  index: number;
  totalCards: number;
  theme: ChannelTheme;
  enterDirection?: "left" | "right" | "bottom";
}

/**
 * Cinematic TopicCard — full-screen atmospheric image background
 * with text overlay. No card container, no PowerPoint vibes.
 *
 * The DALL-E image fills the entire 1080x1920 frame (dimmed),
 * with a slow Ken Burns zoom. Text sits in the lower third
 * over a heavy gradient for readability.
 */
export const TopicCardCinematic: React.FC<TopicCardCinematicProps> = ({
  card,
  index,
  totalCards,
  theme,
  enterDirection = "right",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // --- Ken Burns slow zoom on background image ---
  const kenBurnsScale = interpolate(
    frame,
    [0, durationInFrames],
    [1.0, 1.12],
    { extrapolateRight: "clamp" }
  );
  // Slight pan direction based on card index
  const panX = interpolate(
    frame,
    [0, durationInFrames],
    index % 2 === 0 ? [0, -15] : [-10, 5],
    { extrapolateRight: "clamp" }
  );

  // --- Text entrance animations ---
  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 180, mass: 0.4 },
  });
  const statSpring = spring({
    frame: Math.max(0, frame - 6),
    fps,
    config: { damping: 16, stiffness: 160, mass: 0.5 },
  });
  const subtitleSpring = spring({
    frame: Math.max(0, frame - 10),
    fps,
    config: { damping: 18, stiffness: 140, mass: 0.4 },
  });

  // Title slides up from bottom
  const titleY = interpolate(titleSpring, [0, 1], [60, 0]);
  const titleOpacity = interpolate(titleSpring, [0, 0.4], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Stat scales in
  const statScale = interpolate(statSpring, [0, 1], [0.6, 1]);
  const statOpacity = interpolate(statSpring, [0, 0.4], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Subtitle fades in
  const subtitleOpacity = interpolate(subtitleSpring, [0, 0.5], [0, 1], {
    extrapolateRight: "clamp",
  });
  const subtitleY = interpolate(subtitleSpring, [0, 1], [30, 0]);

  // Accent line grows
  const lineWidth = interpolate(
    spring({
      frame: Math.max(0, frame - 4),
      fps,
      config: { damping: 14, stiffness: 200, mass: 0.3 },
    }),
    [0, 1],
    [0, 500]
  );

  // --- Exit animation: fade out in last 8 frames ---
  const exitStart = durationInFrames - 8;
  const exitProgress = frame >= exitStart
    ? interpolate(frame, [exitStart, durationInFrames], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;
  const exitOpacity = 1 - exitProgress;
  const exitScale = interpolate(exitProgress, [0, 1], [1, 0.97]);

  return (
    <AbsoluteFill>
      {/* === FULL-SCREEN BACKGROUND IMAGE (keeps Ken Burns through exit) === */}
      {card.backgroundImage && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            overflow: "hidden",
          }}
        >
          <Img
            src={staticFile(card.backgroundImage)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${kenBurnsScale}) translateX(${panX}px)`,
              filter: "brightness(0.35)",
            }}
          />
        </div>
      )}

      {/* === GRADIENT OVERLAYS for text readability === */}
      {/* Bottom-heavy gradient — text lives here */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(to bottom, transparent 20%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.85) 80%, rgba(0,0,0,0.95) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Accent color vignette — subtle channel identity */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 50% 90%, ${theme.accent}15 0%, transparent 60%)`,
          pointerEvents: "none",
        }}
      />

      {/* === Exit transition wrapper — fades/shrinks all content === */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: exitOpacity,
          transform: `scale(${exitScale})`,
        }}
      >
        {/* === SEGMENTED PROGRESS BAR === */}
        <div
          style={{
            position: "absolute",
            top: 60,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            gap: 8,
            opacity: subtitleOpacity,
          }}
        >
          {Array.from({ length: totalCards }).map((_, segIdx) => {
            const isCurrent = segIdx === index;
            const isPast = segIdx < index;
            return (
              <div
                key={segIdx}
                style={{
                  width: 80,
                  height: 4,
                  borderRadius: 2,
                  background: isCurrent
                    ? theme.accent
                    : isPast
                      ? "rgba(255,255,255,0.6)"
                      : "rgba(255,255,255,0.25)",
                  boxShadow: isCurrent
                    ? `0 0 10px ${theme.accent}80, 0 0 20px ${theme.accent}40`
                    : "none",
                }}
              />
            );
          })}
        </div>

        {/* === TEXT CONTENT — lower third === */}
        <div
          style={{
            position: "absolute",
            bottom: 220,
            left: 50,
            right: 50,
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          {/* Emoji + Title */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              transform: `translateY(${titleY}px)`,
              opacity: titleOpacity,
            }}
          >
            {card.emoji && (
              <span style={{ fontSize: 52, filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.6))" }}>
                {card.emoji}
              </span>
            )}
            <div
              style={{
                fontFamily: HEADING_FONT,
                fontWeight: 900,
                fontSize: 48,
                color: "#ffffff",
                lineHeight: 1.1,
                letterSpacing: "-0.02em",
                textShadow: "0 2px 12px rgba(0,0,0,0.8), 0 0 40px rgba(0,0,0,0.5)",
                flex: 1,
              }}
            >
              {card.title}
            </div>
          </div>

          {/* Accent line */}
          <div
            style={{
              width: lineWidth,
              height: 4,
              background: `linear-gradient(90deg, ${theme.accent}, ${theme.accent}80, transparent)`,
              borderRadius: 2,
              boxShadow: `0 0 15px ${theme.accent}50`,
            }}
          />

          {/* Key stat */}
          <div
            style={{
              fontFamily: HEADING_FONT,
              fontWeight: 900,
              fontSize: 80,
              color: theme.accent,
              lineHeight: 1,
              letterSpacing: "-0.03em",
              transform: `scale(${statScale})`,
              transformOrigin: "left center",
              opacity: statOpacity,
              textShadow: `0 0 40px ${theme.accent}60, 0 2px 16px rgba(0,0,0,0.8)`,
            }}
          >
            {card.stat}
          </div>

          {/* Subtitle */}
          <div
            style={{
              fontFamily: BODY_FONT,
              fontWeight: 600,
              fontSize: 30,
              color: "rgba(255,255,255,0.85)",
              lineHeight: 1.35,
              letterSpacing: "0.01em",
              transform: `translateY(${subtitleY}px)`,
              opacity: subtitleOpacity,
              textShadow: "0 2px 8px rgba(0,0,0,0.7)",
              maxWidth: 900,
            }}
          >
            {card.subtitle}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
