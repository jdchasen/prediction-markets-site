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
import { HEADING_FONT } from "../styles/fonts";

interface HookSlideProps {
  topLine: string;
  bottomLine: string;
  accent?: string;
  backgroundImage?: string;
}

export const HookSlide: React.FC<HookSlideProps> = ({
  topLine,
  bottomLine,
  accent = "#6366f1",
  backgroundImage,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // === FLASH BLOOM — bright white flash that fades fast ===
  const flashOpacity = interpolate(frame, [0, 2, 8], [0.9, 0.6, 0], {
    extrapolateRight: "clamp",
  });

  // Background glow — visible from frame 0, builds up
  const bgGlow = interpolate(frame, [0, 3, 15], [0.3, 0.6, 0.8], {
    extrapolateRight: "clamp",
  });

  // === DRAMATIC ENTRANCE — snappy spring, readable by ~0.2s ===
  const topSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 800, mass: 0.15 },
  });

  const bottomSpring = spring({
    frame: Math.max(0, frame - 5),
    fps,
    config: { damping: 14, stiffness: 800, mass: 0.15 },
  });

  const lineSpring = spring({
    frame: Math.max(0, frame - 3),
    fps,
    config: { damping: 16, stiffness: 500, mass: 0.2 },
  });

  // Top text scales from 0.7 → 1.0 (less extreme = faster readability)
  const topScale = interpolate(topSpring, [0, 1], [0.7, 1]);
  const topOpacity = interpolate(topSpring, [0, 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });
  const bottomY = interpolate(bottomSpring, [0, 1], [80, 0]);
  const bottomOpacity = interpolate(bottomSpring, [0, 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });
  const lineWidth = interpolate(lineSpring, [0, 1], [0, 600]);

  // === AGGRESSIVE SHAKE — bigger amplitude, longer duration ===
  const shakeX = frame < 10
    ? interpolate(frame, [0, 2, 4, 6, 8, 10], [0, 8, -6, 4, -2, 0])
    : 0;
  const shakeY = frame < 10
    ? interpolate(frame, [0, 2, 4, 6, 8, 10], [0, -4, 3, -2, 1, 0])
    : 0;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        transform: `translate(${shakeX}px, ${shakeY}px)`,
      }}
    >
      {/* Background image — dimmed and blurred */}
      {backgroundImage && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            overflow: "hidden",
          }}
        >
          <Img
            src={staticFile(backgroundImage)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: "blur(8px) brightness(0.25)",
              transform: "scale(1.1)",
            }}
          />
          {/* Dark gradient overlay for text readability */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "radial-gradient(circle at 50% 45%, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.7) 100%)",
            }}
          />
        </div>
      )}

      {/* Flash bloom overlay */}
      {flashOpacity > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(circle at 50% 45%, rgba(255,255,255,${flashOpacity}) 0%, rgba(255,255,255,${flashOpacity * 0.3}) 40%, transparent 70%)`,
            zIndex: 10,
            pointerEvents: "none",
          }}
        />
      )}

      {/* Radial glow — visible from frame 0, larger and more intense */}
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accent}${Math.round(bgGlow * 25).toString(16).padStart(2, "0")} 0%, ${accent}${Math.round(bgGlow * 8).toString(16).padStart(2, "0")} 40%, transparent 70%)`,
        }}
      />

      <div style={{ textAlign: "center", position: "relative", maxWidth: 940, padding: "0 30px" }}>
        {/* Top line — big hook text */}
        <div
          style={{
            fontFamily: HEADING_FONT,
            fontWeight: 900,
            fontSize: 130,
            color: "#ffffff",
            lineHeight: 1,
            transform: `scale(${topScale})`,
            opacity: topOpacity,
            letterSpacing: "-0.03em",
            textShadow: `0 0 80px ${accent}aa, 0 0 160px ${accent}40, 0 4px 20px rgba(0,0,0,0.5)`,
          }}
        >
          {topLine}
        </div>

        {/* Accent line — thicker, wider */}
        <div
          style={{
            width: lineWidth,
            height: 6,
            background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
            margin: "18px auto",
            borderRadius: 3,
            boxShadow: `0 0 20px ${accent}60`,
          }}
        />

        {/* Bottom line */}
        <div
          style={{
            fontFamily: HEADING_FONT,
            fontWeight: 900,
            fontSize: 56,
            color: "rgba(255,255,255,0.95)",
            lineHeight: 1.1,
            transform: `translateY(${bottomY}px)`,
            opacity: bottomOpacity,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            textShadow: "0 2px 12px rgba(0,0,0,0.5)",
          }}
        >
          {bottomLine}
        </div>
      </div>
    </AbsoluteFill>
  );
};
