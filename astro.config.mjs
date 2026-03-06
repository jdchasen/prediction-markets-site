// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://masterpredictionmarkets.com',
  integrations: [
    tailwind(),
    sitemap({
      changefreq: 'daily',
      lastmod: new Date(),
      filter(page) {
        // Exclude individual odds pages from sitemap — noindexed thin content.
        // Keep /odds/ index and /odds/[category] pages.
        const ODDS_CATEGORIES = ['politics', 'crypto', 'sports', 'finance', 'entertainment', 'economics', 'tech', 'science'];
        const url = page.replace(/\/$/, '');
        const oddsBase = 'https://masterpredictionmarkets.com/odds';
        if (url === oddsBase) return true; // /odds/ index
        if (url.startsWith(oddsBase + '/')) {
          const slug = url.slice(oddsBase.length + 1).replace(/\/$/, '');
          // Keep category pages, exclude individual market pages
          return ODDS_CATEGORIES.includes(slug);
        }
        return true;
      },
      serialize(item) {
        const pillarSlugs = [
          'what-are-prediction-markets',
          'best-prediction-market-platforms',
          'kalshi-review',
          'polymarket-guide-how-to-trade-crypto-prediction-markets',
          'kalshi-vs-polymarket-which-platform-should-you-use',
          'prediction-market-strategies-finding-edge-as-a-retail-trader',
          'prediction-markets-making-money',
          'what-are-event-contracts',
          'is-kalshi-legal',
          'is-polymarket-legal',
          'prediction-market-arbitrage-guide',
          'how-to-calculate-implied-probability-prediction-markets',
        ];
        const isPillar = pillarSlugs.some(s => item.url.includes(`/blog/${s}`));

        if (item.url === 'https://masterpredictionmarkets.com/') {
          item.priority = 1.0;
          item.changefreq = 'daily';
        } else if (item.url.endsWith('/platforms/') || item.url.endsWith('/platforms')) {
          item.priority = 0.9;
          item.changefreq = 'weekly';
        } else if (item.url.includes('/tools/') || item.url.includes('/compare')) {
          item.priority = 0.9;
          item.changefreq = 'weekly';
        } else if (isPillar) {
          item.priority = 0.85;
          item.changefreq = 'weekly';
        } else if (item.url.endsWith('/blog/') || item.url.includes('/category/')) {
          item.priority = 0.8;
          item.changefreq = 'daily';
        } else if (item.url.endsWith('/odds/')) {
          item.priority = 0.8;
          item.changefreq = 'daily';
        } else if (item.url.includes('/blog/')) {
          item.priority = 0.7;
          item.changefreq = 'weekly';
        } else {
          item.priority = 0.5;
        }
        return item;
      },
    }),
  ],
  markdown: {
    shikiConfig: {
      theme: 'github-dark',
    },
  },
});
