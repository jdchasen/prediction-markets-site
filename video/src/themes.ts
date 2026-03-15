/**
 * Channel themes for TopicVideo composition.
 *
 * Each channel gets a distinct visual identity: gradient background,
 * accent color, card background, and caption highlight color.
 */

export interface ChannelTheme {
  gradient: [string, string]; // dark gradient stops
  accent: string; // primary accent color
  cardBg: string; // semi-transparent card background
  captionHighlight: string; // active word color in captions
  channelName: string; // display name for CTA
  musicTrack?: string; // background music file in public/music/
}

export const CHANNEL_THEMES: Record<string, ChannelTheme> = {
  truecrime: {
    gradient: ["#1a0000", "#330000"], // dark blood red
    accent: "#ef4444", // red
    cardBg: "rgba(200, 0, 0, 0.15)",
    captionHighlight: "#ff4444",
    channelName: "Cold Trail",
    musicTrack: "music/topic-dark.mp3",
  },
  finance: {
    gradient: ["#001a0a", "#003314"], // dark money green
    accent: "#22c55e", // green
    cardBg: "rgba(0, 200, 80, 0.15)",
    captionHighlight: "#4ade80",
    channelName: "Money Minute",
    musicTrack: "music/topic-bright.mp3",
  },
  braindrop: {
    gradient: ["#0a001a", "#1a0033"], // deep purple
    accent: "#a855f7", // vivid purple
    cardBg: "rgba(168, 85, 247, 0.15)",
    captionHighlight: "#c084fc",
    channelName: "BrainDrop",
    musicTrack: "music/topic-bright.mp3",
  },
  mindtrap: {
    gradient: ["#0a0a0a", "#1a1a2e"], // near-black with blue tint
    accent: "#f59e0b", // amber/gold
    cardBg: "rgba(245, 158, 11, 0.15)",
    captionHighlight: "#fbbf24",
    channelName: "MindTrap",
    musicTrack: "music/topic-dark.mp3",
  },
  lostfiles: {
    gradient: ["#001a1a", "#003333"], // dark teal
    accent: "#06b6d4", // cyan
    cardBg: "rgba(6, 182, 212, 0.15)",
    captionHighlight: "#22d3ee",
    channelName: "Lost Files",
    musicTrack: "music/topic-dark.mp3",
  },
  redacted: {
    gradient: ["#1a1a00", "#333300"], // dark olive/classified-doc feel
    accent: "#eab308", // yellow/gold (classified stamp)
    cardBg: "rgba(234, 179, 8, 0.15)",
    captionHighlight: "#facc15",
    channelName: "Black File",
    musicTrack: "music/topic-dark.mp3",
  },
};

export function getChannelTheme(channel: string): ChannelTheme {
  return CHANNEL_THEMES[channel] || CHANNEL_THEMES.finance;
}
