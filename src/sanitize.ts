/** Strip tokens, refresh tokens, and long credential-like strings from error messages. */
export function sanitizeErrorMessage(err: unknown): string {
  const msg =
    err instanceof Error
      ? err.message
      : typeof err === "string"
        ? err
        : "An unexpected error occurred";

  return msg
    .replace(/ya29\.[A-Za-z0-9_-]+/g, "[REDACTED_TOKEN]")
    .replace(/1\/[A-Za-z0-9_-]+/g, "[REDACTED_REFRESH]")
    .replace(/[A-Za-z0-9_-]{60,}/g, "[REDACTED]");
}
