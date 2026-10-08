import { Eye, EyeOff } from "lucide-react";
import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "onChange" | "value" | "id"> {
  label: ReactNode;
  value: string;
  onChange: (value: string) => void;
  /** Persistent help under the field */
  hint?: ReactNode;
  /** An error the form decided on (a failed submit); shown until the field changes */
  error?: string | null;
  /** Checked when the field loses focus; return the message to show, or null */
  validate?: (value: string) => string | null;
}

/** A labelled field whose error sits under it, linked with aria-describedby, and appears when the field is left
 *  (not while typing). A password field gets a Show/Hide toggle; the toggle is outside the label so it never
 *  becomes part of the field's name. */
export default function TextField({ label, value, onChange, hint, error, validate, type = "text", className, onBlur, ...rest }: Props) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const [blurError, setBlurError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const message = error ?? blurError;
  const isPassword = type === "password";
  const describedBy = [hint ? hintId : null, message ? errorId : null, rest["aria-describedby"]].filter(Boolean).join(" ") || undefined;

  function check(input: HTMLInputElement) {
    const text = typeof label === "string" ? label : "This field";
    if (input.validity.valueMissing || (rest.required && input.value.trim() === "")) return `${text} is required.`;
    if (input.validity.typeMismatch && type === "email") return "Enter an email address like name@example.com.";
    return validate?.(input.value) ?? null;
  }

  const input = (
    <input
      {...rest}
      id={id}
      type={isPassword && revealed ? "text" : type}
      className={className}
      value={value}
      aria-invalid={message ? true : undefined}
      aria-describedby={describedBy}
      onChange={(e) => {
        onChange(e.target.value);
        // A shown error is rechecked as the person fixes it, so it clears as soon as it is true
        if (blurError) setBlurError(check(e.target));
      }}
      onBlur={(e) => {
        setBlurError(check(e.target));
        onBlur?.(e);
      }}
    />
  );

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {isPassword ? (
        <div className="password-row">
          {input}
          <button
            type="button"
            className="ghost password-toggle"
            aria-pressed={revealed}
            aria-controls={id}
            onClick={() => setRevealed((v) => !v)}
          >
            {revealed ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
            <span className="sr-only">Show {typeof label === "string" ? label.toLowerCase() : "password"}</span>
          </button>
        </div>
      ) : (
        input
      )}
      {hint && <span id={hintId} className="field-hint muted">{hint}</span>}
      {message && <span id={errorId} className="field-error" role="alert">{message}</span>}
    </div>
  );
}
