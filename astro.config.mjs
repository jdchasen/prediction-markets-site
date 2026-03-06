// @ts-check
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://masterpredictionmarkets.com',
  redirects: {
    '/blog/will-khamenei-lose-power-market-says-100': '/blog/khamenei-prediction-market-999-odds-explained',
    '/blog/will-khamenei-lose-power-market-shows-999-odds': '/blog/khamenei-prediction-market-999-odds-explained',
  },
  integrations: [
    tailwind(),
    sitemap({
      changefreq: 'daily',
      lastmod: new Date(),
      filter(page) {
        const url = page.replace(/\/$/, '');

        // Exclude individual odds pages — noindexed thin content.
        // Keep /odds/ index and /odds/[category] pages.
        const ODDS_CATEGORIES = ['politics', 'crypto', 'sports', 'finance', 'entertainment', 'economics', 'tech', 'science'];
        const oddsBase = 'https://masterpredictionmarkets.com/odds';
        if (url === oddsBase) return true;
        if (url.startsWith(oddsBase + '/')) {
          const slug = url.slice(oddsBase.length + 1).replace(/\/$/, '');
          return ODDS_CATEGORIES.includes(slug);
        }

        // Exclude old daily pulse articles — only latest is indexed.
        if (url.includes('/blog/daily-market-pulse-')) {
          return false;
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
