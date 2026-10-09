import { ApiError } from "../api/http";

export default function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const detail =
    error instanceof ApiError
      ? error.status === 429
        ? "Too many requests — please retry shortly."
        : error.detail
      : "Something went wrong.";
  return (
    <div className="error-banner" role="alert">
      <span>{detail}</span>
      {onRetry && <button type="button" onClick={onRetry}>Retry</button>}
    </div>
  );
}
