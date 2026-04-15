import { NextResponse } from "next/server";

const COOKIE_NAME = "sentinel_access_token";

function errorBody(code: string, message: string, detail: string, retryable = false) {
  return {
    error: {
      code,
      message,
      detail,
      request_id: null,
      retryable,
    },
    detail,
  };
}

export async function POST(req: Request) {
  const baseUrl = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const body = await req.json();

  const r = await fetch(`${baseUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  const text = await r.text();
  const data = text ? safeJsonParse(text) : null;
  if (!r.ok) {
    return NextResponse.json(data ?? errorBody("AUTH_REQUIRED", "Authentication failed.", "Login failed"), { status: r.status });
  }

  const token = (data as any)?.access_token;
  if (!token) {
    return NextResponse.json(errorBody("INTERNAL_ERROR", "An unexpected error occurred.", "Missing access_token"), { status: 502 });
  }

  const res = NextResponse.json({ ok: true });
  const url = new URL(req.url);
  const proto = req.headers.get("x-forwarded-proto") ?? url.protocol.replace(":", "");
  const secureCookie = proto === "https" || process.env.COOKIE_SECURE === "1";
  res.cookies.set({
    name: COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookie,
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  return res;
}

function safeJsonParse(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return errorBody("INTERNAL_ERROR", "An unexpected error occurred.", text);
  }
}
