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

interface TopicCardProps {
  card: TopicCardType;
  index: number;
  totalCards: number;
  theme: ChannelTheme;
  enterDirection?: "left" | "right" | "bottom";
}

export const TopicCard: React.FC<TopicCardProps> = ({
  card,
  index,
  totalCards,
  theme,
  enterDirection = "right",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // --- Entrance spring ---
  const enterSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 200, mass: 0.4 },
  });

  const translateX =
    enterDirection === "left"
      ? interpolate(enterSpring, [0, 1], [-600, 0])
      : enterDirection === "right"
        ? interpolate(enterSpring, [0, 1], [600, 0])
        : 0;
  const translateY =
    enterDirection === "bottom"
      ? interpolate(enterSpring, [0, 1], [400, 0])
      : 0;
  const opacity = interpolate(enterSpring, [0, 0.4], [0, 1], {
    extrapolateRight: "clamp",
  });

  // --- Stat count-up effect ---
  const statSpring = spring({
    frame: Math.max(0, frame - 8),
    fps,
    config: { damping: 20, stiffness: 100, mass: 0.5 },
  });
  const statScale = interpolate(statSpring, [0, 1], [0.5, 1]);
  const statOpacity = interpolate(statSpring, [0, 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });

  // --- Image fade-in (slightly delayed) ---
  const imgSpring = spring({
    frame: Math.max(0, frame - 6),
    fps,
    config: { damping: 18, stiffness: 150, mass: 0.4 },
  });
  const imgOpacity = interpolate(imgSpring, [0, 0.5], [0, 1], {
    extrapolateRight: "clamp",
  });
  const imgScale = interpolate(imgSpring, [0, 1], [0.95, 1]);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity,
        transform: `translate(${translateX}px, ${translateY}px)`,
      }}
    >
      {/* Card content */}
      <div
        style={{
          position: "relative",
          width: 940,
          padding: "48px 40px",
          borderRadius: 32,
          background: theme.cardBg,
          backdropFilter: "blur(20px)",
          border: `2px solid ${theme.accent}30`,
          boxShadow: `0 16px 48px rgba(0,0,0,0.4), 0 0 60px ${theme.accent}15`,
        }}
      >
        {/* Accent bar at top */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 40,
            right: 40,
            height: 4,
            borderRadius: 2,
            background: `linear-gradient(90deg, transparent, ${theme.accent}, transparent)`,
          }}
        />

        {/* Emoji + Title row */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
          {card.emoji && (
            <span style={{ fontSize: 48 }}>{card.emoji}</span>
          )}
          <div
            style={{
              fontFamily: HEADING_FONT,
              fontWeight: 900,
              fontSize: 44,
              color: "#ffffff",
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              textShadow: "0 2px 8px rgba(0,0,0,0.5)",
              flex: 1,
            }}
          >
            {card.title}
          </div>
        </div>

        {/* Inline image */}
        {card.backgroundImage && (
          <div
            style={{
              width: "100%",
              height: 340,
              borderRadius: 16,
              overflow: "hidden",
              marginBottom: 20,
              opacity: imgOpacity,
              transform: `scale(${imgScale})`,
              border: `1px solid ${theme.accent}20`,
            }}
          >
            <Img
              src={staticFile(card.backgroundImage)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          </div>
        )}

        {/* Key stat — big and bold */}
        <div
          style={{
            fontFamily: HEADING_FONT,
            fontWeight: 900,
            fontSize: 72,
            color: theme.accent,
            lineHeight: 1,
            letterSpacing: "-0.03em",
            marginBottom: 16,
            transform: `scale(${statScale})`,
            opacity: statOpacity,
            textShadow: `0 0 40px ${theme.accent}60`,
          }}
        >
          {card.stat}
        </div>

        {/* Subtitle */}
        <div
          style={{
            fontFamily: BODY_FONT,
            fontWeight: 600,
            fontSize: 28,
            color: "rgba(255,255,255,0.7)",
            lineHeight: 1.3,
            letterSpacing: "0.01em",
          }}
        >
          {card.subtitle}
        </div>
      </div>

      {/* Progress label */}
      <div
        style={{
          position: "absolute",
          top: 80,
          fontFamily: BODY_FONT,
          fontWeight: 700,
          fontSize: 16,
          color: "rgba(255,255,255,0.4)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}
      >
        {index + 1} OF {totalCards}
      </div>
    </AbsoluteFill>
  );
};
