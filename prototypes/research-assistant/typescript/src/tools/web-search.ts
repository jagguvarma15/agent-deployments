const MOCK_RESULTS = [
  {
    title: "Introduction to Machine Learning",
    url: "https://example.com/ml-intro",
    snippet:
      "Machine learning is a subset of AI that enables systems to learn from data.",
  },
  {
    title: "Deep Learning Fundamentals",
    url: "https://example.com/deep-learning",
    snippet:
      "Deep learning uses neural networks with multiple layers to model complex patterns.",
  },
  {
    title: "Natural Language Processing Overview",
    url: "https://example.com/nlp",
    snippet:
      "NLP combines linguistics and ML to enable computers to understand human language.",
  },
];

export async function webSearch(query: string): Promise<string> {
  return MOCK_RESULTS.map((r) => `**${r.title}**\n${r.url}\n${r.snippet}`).join(
    "\n\n",
  );
}
