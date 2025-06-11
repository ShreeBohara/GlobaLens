import { NewsPoint } from '../types';

const words = [
  'crime', 'politics', 'sports', 'war', 'economy', 'tech',
  'health', 'environment', 'culture', 'education'
];

function randomLat() {
  return Math.random() * 180 - 90;        // [-90, 90]
}
function randomLng() {
  return Math.random() * 360 - 180;       // [-180, 180]
}
function randomChoice<T>(arr: T[]) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export const sampleNews: NewsPoint[] = Array.from({ length: 120 }).map((_, i) => {
  const category = randomChoice(words);
  return {
    id: `np-${i}`,
    title: `${category.toUpperCase()} headline #${i}`,
    summary: `Short summary about ${category} event number ${i}.`,
    url: 'https://example.com/news/' + i,
    latitude: randomLat(),
    longitude: randomLng(),
    timestamp: new Date(
      Date.now() - Math.random() * 1000 * 60 * 60 * 24 * 30 // last 30 days
    ).toISOString(),
    categories: [category]
  };
});
