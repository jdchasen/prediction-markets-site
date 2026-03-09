import React from "react";
import {
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { KIDS_HEADING_FONT, KIDS_BODY_FONT, getCategoryTheme } from "../styles/kids-theme";
import type { KidsFact } from "../types";

interface FactCardProps {
  fact: KidsFact;
  index: number;
  totalFacts: number;
  category: string;
  enterDirection: "left" | "right";
}

/**
 * Individual fact slide with visual phases for retention:
 * Phase 0 (0-2s): Illustration zooms in, no text yet
 * Phase 1 (2s+): Fact card slides up from bottom, illustration shifts up
 *
 * Ken Burns slow zoom on illustration throughout.
 * Giant background number for listicle progress feel.
 */
export const FactCard: React.FC<FactCardProps> = ({
  fact,
  index,
  totalFacts,
  category,
  enterDirection,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const theme = getCategoryTheme(category);

  // Slide-in spring
  const enterSpring = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 250, mass: 0.4 },
  });

  const slideOffset = enterDirection === "left" ? -700 : 700;
  const translateX = interpolate(enterSpring, [0, 1], [slideOffset, 0]);
  const opacity = interpolate(enterSpring, [0, 1], [0, 1]);
  const scale = interpolate(enterSpring, [0, 1], [0.85, 1]);

  // Ken Burns slow zoom on illustration
  const imageZoom = interpolate(frame, [0, durationInFrames], [1.0, 1.15], {
    extrapolateRight: "clamp",
  });

  // Visual phase: text card slides in after ~2s
  const textRevealFrame = Math.round(2 * fps);
  const textSpring = spring({
    frame: Math.max(0, frame - textRevealFrame),
    fps,
    config: { damping: 14, stiffness: 200, mass: 0.4 },
  });
  const textSlideY = interpolate(textSpring, [0, 1], [300, 0]);
  const textOpacity = interpolate(textSpring, [0, 1], [0, 1]);

  // Illustration shrinks from 780→640 when text card appears (bigger thumbnail in frame 0)
  const illustrationSize = interpolate(textSpring, [0, 1], [780, 640]);

  // Illustration shifts up when text appears (starts more centered, moves up for card)
  const illustrationShift = interpolate(textSpring, [0, 1], [160, 0]);

  // Subtle float for illustration
  const floatY = Math.sin(frame * 0.04) * 6;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        transform: `translateX(${translateX}px) scale(${scale})`,
        opacity,
        paddingTop: 60,
        paddingBottom: 340,
      }}
    >
      {/* Giant background number for listicle feel */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          fontSize: 800,
          fontFamily: KIDS_HEADING_FONT,
          color: "rgba(255,255,255,0.06)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      >
        {index + 1}
      </div>

      {/* Progress label at top */}
      <div
        style={{
          position: "absolute",
          top: 80,
          display: "flex",
          alignItems: "center",
          gap: 12,
          zIndex: 2,
        }}
      >
        <span
          style={{
            fontFamily: KIDS_BODY_FONT,
            fontWeight: 800,
            fontSize: 30,
            color: "rgba(255,255,255,0.9)",
            textShadow: "0 2px 8px rgba(0,0,0,0.2)",
            letterSpacing: "0.08em",
          }}
        >
          FACT {index + 1} OF {totalFacts}
        </span>
      </div>

      {/* AI illustration with Ken Burns zoom — starts large for thumbnail, shrinks on text reveal */}
      <div
        style={{
          width: illustrationSize,
          height: illustrationSize,
          borderRadius: 48,
          overflow: "hidden",
          transform: `translateY(${floatY + illustrationShift}px)`,
          boxShadow: `0 16px 48px rgba(0,0,0,0.25), 0 0 80px ${theme.accent}25`,
          border: "6px solid rgba(255,255,255,0.5)",
          flexShrink: 0,
          zIndex: 1,
        }}
      >
        {fact.illustration ? (
          <Img
            src={staticFile(fact.illustration)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${imageZoom})`,
            }}
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              background: `linear-gradient(135deg, ${theme.gradient[0]}, ${theme.gradient[1]})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 180,
              transform: `scale(${imageZoom})`,
            }}
          >
            {fact.emoji}
          </div>
        )}
      </div>

      {/* White card with fact text — slides up after 2s delay */}
      <div
        style={{
          marginTop: 44,
          width: 960,
          background: "rgba(255,255,255,0.95)",
          borderRadius: 36,
          padding: "40px 48px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
          transform: `translateY(${textSlideY}px)`,
          opacity: textOpacity,
          zIndex: 2,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 24,
          }}
        >
          {/* Emoji */}
          <span style={{ fontSize: 64, lineHeight: 1, flexShrink: 0 }}>
            {fact.emoji}
          </span>

          {/* Fact text */}
          <div
            style={{
              fontFamily: KIDS_BODY_FONT,
              fontWeight: 700,
              fontSize: 44,
              color: "#2d3436",
              lineHeight: 1.35,
            }}
          >
            {fact.factText}
          </div>
        </div>
      </div>
    </div>
  );
};
