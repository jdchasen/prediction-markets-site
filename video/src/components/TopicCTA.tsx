import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { HEADING_FONT, BODY_FONT } from "../styles/fonts";
import type { ChannelTheme } from "../themes";

interface TopicCTAProps {
  ctaLine: string;
  theme: ChannelTheme;
}

export const TopicCTA: React.FC<TopicCTAProps> = ({ ctaLine, theme }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const enterSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 200, mass: 0.4 },
  });

  const scale = interpolate(enterSpring, [0, 1], [0.85, 1]);
  const opacity = interpolate(enterSpring, [0, 1], [0, 1]);

  const glowPulse = interpolate(
    (frame % 30) / 30,
    [0, 0.5, 1],
    [0.4, 0.8, 0.4]
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity,
        transform: `scale(${scale})`,
        paddingBottom: 100,
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 900, padding: "0 40px" }}>
        {/* CTA text */}
        <div
          style={{
            fontFamily: BODY_FONT,
            fontWeight: 700,
            fontSize: 34,
            color: "rgba(255,255,255,0.8)",
            marginBottom: 28,
            letterSpacing: "0.03em",
          }}
        >
          {ctaLine}
        </div>

        {/* Channel name — glowing accent */}
        <div
          style={{
            fontFamily: HEADING_FONT,
            fontWeight: 900,
            fontSize: 52,
            color: "#ffffff",
            textShadow: `0 0 30px ${theme.accent}${Math.round(glowPulse * 255).toString(16).padStart(2, "0")}, 0 0 60px ${theme.accent}${Math.round(glowPulse * 100).toString(16).padStart(2, "0")}`,
            letterSpacing: "-0.01em",
          }}
        >
          {theme.channelName}
        </div>

        {/* Engagement sub-text */}
        <div
          style={{
            fontFamily: BODY_FONT,
            fontWeight: 600,
            fontSize: 22,
            color: "rgba(255,255,255,0.45)",
            marginTop: 20,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          {theme.channelName === "Cold Trail"
            ? "Drop your theory below"
            : theme.channelName === "Money Minute"
              ? "Comment yes or no"
              : theme.channelName === "BrainDrop"
                ? "Did you know? Tell me below"
                : theme.channelName === "MindTrap"
                  ? "Have you seen this? Tell me"
                  : theme.channelName === "Lost Files"
                    ? "Drop your theory below"
                    : theme.channelName === "Black File"
                      ? "Believe the story? Tell me"
                      : "Subscribe for more"}
        </div>
      </div>

      {/* Loop fade overlay — cross-fades for seamless loop */}
      {(() => {
        const loopFade = interpolate(
          frame,
          [durationInFrames - 20, durationInFrames],
          [0, 0.6],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );
        return loopFade > 0 ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(0,0,0,0.15)",
              opacity: loopFade,
              pointerEvents: "none",
            }}
          />
        ) : null;
      })()}
    </AbsoluteFill>
  );
};
