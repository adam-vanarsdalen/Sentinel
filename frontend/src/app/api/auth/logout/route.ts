import { NextResponse } from "next/server";

const COOKIE_NAME = "sentinel_access_token";

export async function POST(req: Request) {
  const res = NextResponse.json({ ok: true });
  const url = new URL(req.url);
  const proto = req.headers.get("x-forwarded-proto") ?? url.protocol.replace(":", "");
  const secureCookie = proto === "https" || process.env.COOKIE_SECURE === "1";
  res.cookies.set({
    name: COOKIE_NAME,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookie,
    path: "/",
    maxAge: 0,
  });
  return res;
}
