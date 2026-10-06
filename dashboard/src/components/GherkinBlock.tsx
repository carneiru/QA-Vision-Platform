import { tokenizeLine } from "../lib/gherkinTokens";

/** The Gherkin of an imported case: highlighted, never editable. */
export default function GherkinBlock({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <pre className="gherkin" aria-label="Gherkin" tabIndex={0}>
      {lines.map((line, i) => (
        <span key={i}>
          {tokenizeLine(line).map((t, j) => <span key={j} className={`gk-${t.kind}`}>{t.text}</span>)}
          {i < lines.length - 1 && "\n"}
        </span>
      ))}
    </pre>
  );
}
