import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    category: z.string(),
    tags: z.array(z.string()).default([]),
    affiliate: z.string().optional(),
    heroImage: z.string().optional(),
    faqs: z.array(z.object({
      question: z.string(),
      answer: z.string(),
    })).min(2, "Every blog post must have at least 2 FAQs for rich snippet schema"),
    howToSteps: z.array(z.object({
      name: z.string(),
      text: z.string(),
    })).optional(),
    review: z.object({
      itemName: z.string(),
      itemType: z.string().default("Product"),
      rating: z.number(),
    }).optional(),
  }),
});

const markets = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/markets' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    marketQuestion: z.string(),
    category: z.string(),
    status: z.enum(['active', 'settled']).default('active'),
    outcome: z.string().optional(),
    lastUpdated: z.coerce.date(),
    expiryDate: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    kalshiYes: z.number().optional(),
    kalshiNo: z.number().optional(),
    kalshiVolume: z.number().optional(),
    kalshiUrl: z.string().optional(),
    polymarketYes: z.number().optional(),
    polymarketNo: z.number().optional(),
    polymarketVolume: z.number().optional(),
    polymarketUrl: z.string().optional(),
  }),
});

export const collections = { blog, markets };
