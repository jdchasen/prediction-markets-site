import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

export const GET: APIRoute = async ({ site }) => {
  const now = new Date();
  const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);

  const posts = (await getCollection('blog'))
    .filter((post) => {
      const pubDate = post.data.pubDate;
      return pubDate.valueOf() <= now.valueOf() && pubDate.valueOf() >= twoDaysAgo.valueOf();
    })
    .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());

  const siteUrl = site?.href || 'https://masterpredictionmarkets.com';

  const items = posts.map((post) => {
    const pubDate = post.data.pubDate.toISOString();
    const url = `${siteUrl}blog/${post.id}/`;
    const title = post.data.title.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    return `  <url>
    <loc>${url}</loc>
    <news:news>
      <news:publication>
        <news:name>Master Prediction Markets</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>${pubDate}</news:publication_date>
      <news:title>${title}</news:title>
    </news:news>
  </url>`;
  });

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
${items.join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml',
    },
  });
};
