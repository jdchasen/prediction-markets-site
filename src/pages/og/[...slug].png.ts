import type { APIRoute, GetStaticPaths } from "astro";
import { getCollection } from "astro:content";
import satori from "satori";
import sharp from "sharp";
import fs from "node:fs";

const categoryColors: Record<string, string> = {
  politics: "#dc2626",
  economics: "#ca8a04",
  crypto: "#9333ea",
  finance: "#16a34a",
  sports: "#ea580c",
  tech: "#2563eb",
  entertainment: "#db2777",
  science: "#0d9488",
  strategies: "#1e40af",
  daily: "#0f766e",
};

let fontCache: ArrayBuffer | null = null;
async function loadFont(): Promise<ArrayBuffer> {
  if (fontCache) return fontCache;

  const candidates = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
  ];
  for (const fontPath of candidates) {
    if (fs.existsSync(fontPath)) {
      fontCache = fs.readFileSync(fontPath).buffer as ArrayBuffer;
      return fontCache;
    }
  }

  const resp = await fetch(
    "https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap",
    { headers: { "User-Agent": "Mozilla/5.0" } }
  );
  const css = await resp.text();
  const urlMatch = css.match(/src:\s*url\(([^)]+)\)/);
  if (urlMatch) {
    const fontResp = await fetch(urlMatch[1]);
    fontCache = await fontResp.arrayBuffer();
    return fontCache;
  }

  throw new Error("No font available for OG image generation");
}

export const getStaticPaths: GetStaticPaths = async () => {
  const posts = await getCollection("blog");
  return posts.map((post) => ({
    params: { slug: post.id },
    props: { post },
  }));
};

export const GET: APIRoute = async ({ props }) => {
  const { post } = props as { post: any };
  const title: string = post.data.title;
  const category: string = post.data.category || "strategies";
  const date = post.data.pubDate
    ? new Date(post.data.pubDate).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "";
  const accentColor = categoryColors[category] || "#1e40af";
  const isDaily = post.id.startsWith("daily-market-pulse-");
  const label = isDaily ? "DAILY PULSE" : category.toUpperCase();

  const fontData = await loadFont();

  const svg = await satori(
    {
      type: "div",
      props: {
        style: {
          width: "1200px",
          height: "630px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "60px",
          background: `linear-gradient(135deg, #0f172a 0%, #1e293b 50%, ${accentColor}22 100%)`,
          fontFamily: "Arial, sans-serif",
        },
        children: [
          {
            type: "div",
            props: {
              style: { display: "flex", alignItems: "center", gap: "16px" },
              children: [
                {
                  type: "span",
                  props: {
                    style: {
                      background: accentColor,
                      color: "white",
                      padding: "6px 16px",
                      borderRadius: "20px",
                      fontSize: "20px",
                      fontWeight: 700,
                      letterSpacing: "1px",
                    },
                    children: label,
                  },
                },
                {
                  type: "span",
                  props: {
                    style: { color: "#94a3b8", fontSize: "20px" },
                    children: date,
                  },
                },
              ],
            },
          },
          {
            type: "div",
            props: {
              style: {
                display: "flex",
                color: "white",
                fontSize: title.length > 60 ? "42px" : "52px",
                fontWeight: 700,
                lineHeight: 1.2,
                overflow: "hidden",
              },
              children: title,
            },
          },
          {
            type: "div",
            props: {
              style: {
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              },
              children: [
                {
                  type: "span",
                  props: {
                    style: {
                      color: "#e2e8f0",
                      fontSize: "24px",
                      fontWeight: 700,
                    },
                    children: "masterpredictionmarkets.com",
                  },
                },
                {
                  type: "span",
                  props: {
                    style: { color: "#94a3b8", fontSize: "18px" },
                    children: "Live Odds & Analysis",
                  },
                },
              ],
            },
          },
        ],
      },
    },
    {
      width: 1200,
      height: 630,
      fonts: [
        {
          name: "Arial",
          data: fontData,
          weight: 400,
          style: "normal" as const,
        },
      ],
    }
  );

  const png = await sharp(Buffer.from(svg)).png().toBuffer();

  return new Response(png, {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "public, max-age=31536000, immutable",
    },
  });
};
