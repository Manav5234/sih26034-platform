/**
 * API URL configuration — single source of truth for API base URL resolution.
 *
 * Client components should use getApiUrl() (reads NEXT_PUBLIC_API_URL env var).
 * Server components should use getServerApiUrl() (reads internal API_URL env var).
 * Falls back to "http://localhost:8000" in both cases.
 */
export function getApiUrl(): string {
  // Client: use NEXT_PUBLIC_API_URL (prefixed for Next.js client access)
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export function getServerApiUrl(): string {
  // Server: use internal API_URL (not prefixed, not exposed to client)
  return process.env.API_URL || "http://localhost:8000";
}