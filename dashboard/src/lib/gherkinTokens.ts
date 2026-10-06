// Read-only highlighting for imported cases. Keyword lists cover English and Portuguese, the
// languages in use; other languages still render, just without keyword colour.
export type TokenKind = "keyword" | "tag" | "table" | "docstring" | "comment" | "text";
export interface Token { kind: TokenKind; text: string }

const HEADINGS = ["Scenario Outline:", "Scenario Template:", "Scenario:", "Example:", "Examples:", "Background:", "Rule:", "Feature:",
  "Esquema do Cenário:", "Cenário:", "Exemplos:", "Contexto:", "Regra:", "Funcionalidade:"];
const STEPS = ["Given ", "When ", "Then ", "And ", "But ", "* ", "Dado ", "Dada ", "Quando ", "Então ", "E ", "Mas "];

export function tokenizeLine(line: string): Token[] {
  const indent = line.match(/^\s*/)![0];
  const rest = line.slice(indent.length);
  const lead: Token[] = indent ? [{ kind: "text", text: indent }] : [];
  if (rest.startsWith("#")) return [...lead, { kind: "comment", text: rest }];
  if (rest.startsWith("@")) return [...lead, { kind: "tag", text: rest }];
  if (rest.startsWith("|")) return [...lead, { kind: "table", text: rest }];
  if (rest.startsWith('"""') || rest.startsWith("```")) return [...lead, { kind: "docstring", text: rest }];
  const keyword = [...HEADINGS, ...STEPS].find((k) => rest.startsWith(k));
  if (!keyword) return [...lead, { kind: "text", text: rest }];
  const tail = rest.slice(keyword.length);
  return [...lead, { kind: "keyword", text: keyword }, ...(tail ? [{ kind: "text" as const, text: tail }] : [])];
}
