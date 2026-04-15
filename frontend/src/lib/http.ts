export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class HttpError extends Error {
  status: number;
  body: unknown;
  code?: string;
  detail?: string | null;
  requestId?: string | null;
  retryable?: boolean;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
    const parsed = getApiError(body);
    this.code = parsed?.code;
    this.detail = parsed?.detail ?? null;
    this.requestId = parsed?.request_id ?? null;
    this.retryable = parsed?.retryable;
  }
}

export type ApiErrorInfo = {
  code?: string;
  message?: string;
  detail?: string | null;
  request_id?: string | null;
  retryable?: boolean;
};

export async function fetchJson<T>(
  input: RequestInfo | URL,
  init: RequestInit & { method?: HttpMethod } = {},
): Promise<T> {
  const r = await fetch(input, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  const text = await r.text();
  const body = text ? safeJsonParse(text) : null;

  if (!r.ok) {
    const msg = extractErrorMessage(body, r.status);
    throw new HttpError(r.status, msg, body);
  }

  return body as T;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function getApiError(body: unknown): ApiErrorInfo | null {
  if (!body || typeof body !== "object") return null;
  if (!("error" in (body as any))) return null;
  const error = (body as any).error;
  if (!error || typeof error !== "object") return null;
  return {
    code: typeof error.code === "string" ? error.code : undefined,
    message: typeof error.message === "string" ? error.message : undefined,
    detail: typeof error.detail === "string" ? error.detail : null,
    request_id: typeof error.request_id === "string" ? error.request_id : null,
    retryable: typeof error.retryable === "boolean" ? error.retryable : undefined,
  };
}

function extractErrorMessage(body: unknown, status: number): string {
  const apiError = getApiError(body);
  if (apiError?.message) return apiError.message;
  if (typeof body === "string") return body;
  if (body && typeof body === "object" && "detail" in (body as any)) {
    const detail = (body as any).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (first && typeof first === "object" && "msg" in (first as any)) return String((first as any).msg);
      return JSON.stringify(first);
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }
  return `HTTP ${status}`;
}
