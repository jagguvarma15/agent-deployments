export function citeSources(facts: string[]): string {
  if (facts.length === 0) return "No facts to cite.";
  return facts.map((fact, i) => `[${i + 1}] ${fact}`).join("\n");
}
