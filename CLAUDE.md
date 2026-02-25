# Project: Master Prediction Markets

Astro static site for prediction market guides, live odds, and trading tools.

## Architecture

- **Framework**: Astro with static site generation
- **Content**: Markdown files in `src/content/blog/` (articles) and `src/content/markets/` (odds pages)
- **Schema**: Defined in `src/content.config.ts` — validates all frontmatter fields at build time
- **Styling**: Tailwind CSS with dark mode support
- **Deployment**: Static build (`npx astro build` outputs to `dist/`)

## Blog Post Requirements

Every blog post in `src/content/blog/` **must** include these frontmatter fields:

```yaml
---
title: "Post Title"
description: "Meta description (150-160 chars, include benefit statement)"
pubDate: 2026-02-25
category: "strategies"        # strategies, kalshi, polymarket, or other defined categories
tags: ["kalshi", "polymarket"] # include platform tags when relevant
affiliate: "kalshi"            # or "polymarket" — determines CTA banner
faqs:                          # REQUIRED: minimum 2 FAQs for rich snippet schema
  - question: "Question text?"
    answer: "Answer text."
  - question: "Another question?"
    answer: "Another answer."
---
```

### FAQ Guidelines

- **Minimum 2 FAQs per post** (enforced by schema validation — build will fail without them)
- FAQs generate FAQPage structured data (JSON-LD) which produces rich snippets in Google search results
- Write questions as a real user would search them (e.g., "How much does Kalshi charge per trade?")
- Answers should be 1-3 sentences, factual, and self-contained (they appear in SERPs)
- Include the most commonly searched question about the topic as FAQ #1

### Referral Links

Every post that mentions Kalshi or Polymarket inline should use the referral link on the **first mention** of the platform name in the body text:

- **Kalshi**: `[Kalshi](https://kalshi.com/sign-up/?referral=f2e21ad4-75b7-4ffb-bfcc-f2fb36e07b21&m=true&utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup)`
- **Polymarket**: `[Polymarket](https://polymarket.us/1762?utm_source=masterpredictionmarkets&utm_medium=blog&utm_campaign=signup)`

Subsequent mentions can link to internal blog posts or be plain text.

### Optional Fields

- `review` — for platform review posts (generates Review schema with star rating)
- `heroImage` — path to hero image
- `updatedDate` — set when significantly updating an existing post

## Structured Data

The site generates JSON-LD for:
- **FAQPage** on all blog posts (from `faqs` frontmatter)
- **Article** on all blog posts (from SEOHead component)
- **Review** on posts with `review` field
- **BreadcrumbList** on blog and odds pages
- **Organization** and **WebSite** on homepage

## Key Files

- `src/content.config.ts` — content collection schemas
- `src/pages/blog/[...slug].astro` — blog post template
- `src/pages/odds/[...slug].astro` — odds page template
- `src/components/SEOHead.astro` — meta tags, OG, Twitter cards
- `src/layouts/BaseLayout.astro` — base page layout
