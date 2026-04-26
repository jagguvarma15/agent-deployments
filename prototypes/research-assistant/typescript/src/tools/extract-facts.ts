const MOCK_FACTS = [
  "Machine learning enables systems to learn from data without explicit programming.",
  "Deep learning uses multi-layer neural networks for pattern recognition.",
  "NLP combines computational linguistics with statistical methods.",
  "Transformer architectures revolutionized language understanding in 2017.",
];

export function extractFacts(_text: string): string[] {
  return MOCK_FACTS.slice(0, 3);
}
