import { useId } from "react";

interface Props {
  password: string;
  confirm: string;
  onPassword: (value: string) => void;
  onConfirm: (value: string) => void;
  /** Set by the form on submit; shown under the confirmation field until it changes. */
  mismatch: boolean;
}

export const MIN_PASSWORD_LENGTH = 8;

/** A new password typed twice. The server enforces the minimum length too. */
export default function NewPasswordFields({ password, confirm, onPassword, onConfirm, mismatch }: Props) {
  const hintId = useId();
  const errorId = useId();
  return (
    <>
      <label>
        New password
        <input
          type="password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          autoComplete="new-password"
          aria-describedby={hintId}
          value={password}
          onChange={(e) => onPassword(e.target.value)}
        />
        <span id={hintId} className="muted" style={{ fontWeight: 400 }}>
          At least {MIN_PASSWORD_LENGTH} characters.
        </span>
      </label>
      <label>
        Confirm new password
        <input
          type="password"
          required
          autoComplete="new-password"
          aria-invalid={mismatch || undefined}
          aria-describedby={mismatch ? errorId : undefined}
          value={confirm}
          onChange={(e) => onConfirm(e.target.value)}
        />
        {mismatch && (
          <span id={errorId} className="field-error" role="alert">
            Passwords do not match.
          </span>
        )}
      </label>
    </>
  );
}
