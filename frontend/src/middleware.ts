import { NextResponse, type NextRequest } from "next/server";

const COOKIE_NAME = "sentinel_access_token";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname === "/" ||
    pathname.startsWith("/login")
  ) {
    // If already authed and hitting /login, redirect to /dashboard
    if (pathname.startsWith("/login")) {
      const token = req.cookies.get(COOKIE_NAME)?.value;
      if (token) return NextResponse.redirect(new URL("/dashboard", req.url));
    }
    return NextResponse.next();
  }

  const token = req.cookies.get(COOKIE_NAME)?.value;
  if (!token) return NextResponse.redirect(new URL("/login", req.url));
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
