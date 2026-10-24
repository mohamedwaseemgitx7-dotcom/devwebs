/**
 * Minimal fetch wrapper.
 * - The access token lives only in memory (never localStorage) so injected scripts cannot read a stored token.
 * - The refresh token is an HttpOnly cookie the browser sends automatically to /api/v1/auth/*.
 * - On a 401 we refresh once (single in-flight promise shared by concurrent callers) and retry.
 * - Every request carries X-Requested-With (CSRF defence) and an X-Request-ID for tracing.
 */
import type { TokenResponse } from "./types";

const BASE = "/api/v1";

let accessToken: string | null = null;
let refreshInFlight: Promise<TokenResponse | null> | null = null;
let onSessionChange: ((session: TokenResponse | null) => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function subscribeSession(listener: (session: TokenResponse | null) => void) {
  onSessionChange = listener;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  requestId: string | null;

  constructor(status: number, detail: unknown, requestId: string | null) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
    this.requestId = requestId;
  }
}

function requestId(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 16);
}

export async function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${BASE}/auth/refresh`, {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-Requested-With": "flashcart", "X-Request-ID": requestId() },
        });
        if (!res.ok) {
          setAccessToken(null);
          onSessionChange?.(null);
          return null;
        }
        const session = (await res.json()) as TokenResponse;
        setAccessToken(session.access_token);
        onSessionChange?.(session);
        return session;
      } catch {
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  query?: Record<string, string | number | boolean | string[] | undefined | null>;
  signal?: AbortSignal;
  retryOn401?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "" || value === false) continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v));
    else params.set(key, String(value));
  }
  const qs = params.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ""}`;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "X-Requested-With": "flashcart",
    "X-Request-ID": requestId(),
    ...opts.headers,
  };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const res = await fetch(buildUrl(path, opts.query), {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    credentials: "same-origin",
    signal: opts.signal,
  });

  if (res.status === 401 && opts.retryOn401 !== false && accessToken && !path.startsWith("/auth/")) {
    const session = await refreshSession();
    if (session) return api<T>(path, { ...opts, retryOn401: false });
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail ?? data ?? res.statusText;
    throw new ApiError(res.status, detail, res.headers.get("x-request-id"));
  }
  return data as T;
}

/** Human-readable message for any error thrown by api(). Never shows stack traces or raw objects. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429) return "Too many requests — please wait a moment and try again.";
    if (err.status >= 500) return "Something went wrong on our side. Please try again.";
    if (typeof err.detail === "string") return err.detail;
    if (Array.isArray(err.detail)) {
      const first = err.detail[0] as { msg?: string; loc?: unknown[] } | undefined;
      const field = first?.loc?.[first.loc.length - 1];
      return first?.msg ? `${field ? `${String(field)}: ` : ""}${first.msg}` : "Please check your input.";
    }
    const message = (err.detail as { message?: string } | null)?.message;
    if (message) return message;
  }
  if (err instanceof TypeError) return "Network error — check your connection.";
  return "Something went wrong. Please try again.";
}
