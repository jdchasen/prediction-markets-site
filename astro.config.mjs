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
      serialize(item) {
        if (item.url === 'https://masterpredictionmarkets.com/') {
          item.priority = 1.0;
          item.changefreq = 'daily';
        } else if (item.url.endsWith('/platforms/') || item.url.endsWith('/platforms')) {
          item.priority = 0.9;
          item.changefreq = 'weekly';
        } else if (item.url.includes('/tools/')) {
          item.priority = 0.9;
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
        } else if (item.url.includes('/odds/')) {
          item.priority = 0.6;
          item.changefreq = 'daily';
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
