import type { ReactNode } from "react";
import { tokenizeLine } from "../lib/gherkinTokens";

interface Props {
  text: string;
  /** Accessible name of the block. */
  label?: string;
  /** Number the lines (a whole .feature file); long lines then wrap instead of scrolling. */
  numbered?: boolean;
  /** Extra content at the end of a 1-based line, such as a scenario's case chip. Numbered blocks only. */
  annotations?: Map<number, ReactNode>;
}

/** Gherkin: highlighted, never editable. */
export default function GherkinBlock({ text, label = "Gherkin", numbered = false, annotations }: Props) {
  const lines = text.split("\n");
  if (numbered) {
    return (
      <pre className="gherkin numbered" aria-label={label} tabIndex={0}>
        {lines.map((line, i) => (
          // Each line is a block (copying keeps the breaks); its number is drawn from data-line, so it is neither read out nor copied
          <span key={i} className="gk-line" data-line={i + 1}>
            <span className="gk-code">
              {tokenizeLine(line).map((t, j) => <span key={j} className={`gk-${t.kind}`}>{t.text}</span>)}
            </span>
            {annotations?.has(i + 1) && <span className="gk-note">{annotations.get(i + 1)}</span>}
          </span>
        ))}
      </pre>
    );
  }
  return (
    <pre className="gherkin" aria-label={label} tabIndex={0}>
      {lines.map((line, i) => (
        <span key={i}>
          {tokenizeLine(line).map((t, j) => <span key={j} className={`gk-${t.kind}`}>{t.text}</span>)}
          {i < lines.length - 1 && "\n"}
        </span>
      ))}
    </pre>
  );
}
