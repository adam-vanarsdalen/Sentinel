import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const baseUrl = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const body = await req.text();

  const r = await fetch(`${baseUrl}/public/trial-requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    cache: "no-store",
  });

  const text = await r.text();
  const data = text ? safeJsonParse(text) : null;
  if (!r.ok) {
    return NextResponse.json(data ?? { detail: "Request failed" }, { status: r.status });
  }
  return NextResponse.json(data ?? { ok: true });
}

function safeJsonParse(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

