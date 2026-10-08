import { useState } from "react";
import TextField from "./TextField";

interface Props {
  password: string;
  confirm: string;
  onPassword: (value: string) => void;
  onConfirm: (value: string) => void;
  /** Set by the form on submit; shown under the confirmation field until it changes. */
  mismatch: boolean;
}

export const MIN_PASSWORD_LENGTH = 8;

/** A new password typed twice. The server enforces the minimum length too. Problems show under the field
 *  once it is left, and the mismatch is also checked when the confirmation is left. */
export default function NewPasswordFields({ password, confirm, onPassword, onConfirm, mismatch }: Props) {
  const [confirmTouched, setConfirmTouched] = useState(false);
  const differs = confirm !== "" && confirm !== password;
  return (
    <>
      <TextField
        label="New password"
        type="password"
        required
        minLength={MIN_PASSWORD_LENGTH}
        autoComplete="new-password"
        hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        value={password}
        onChange={onPassword}
        validate={(v) => (v.length > 0 && v.length < MIN_PASSWORD_LENGTH ? `Use at least ${MIN_PASSWORD_LENGTH} characters.` : null)}
      />
      <TextField
        label="Confirm new password"
        type="password"
        required
        autoComplete="new-password"
        value={confirm}
        onChange={(v) => {
          onConfirm(v);
        }}
        onBlur={() => setConfirmTouched(true)}
        error={mismatch || (confirmTouched && differs) ? "Passwords do not match." : null}
      />
    </>
  );
}
