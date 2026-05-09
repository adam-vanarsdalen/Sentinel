import { cookies } from "next/headers";
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

type ProxyRouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: Request, ctx: ProxyRouteContext) {
  return proxy(req, ctx);
}
export async function POST(req: Request, ctx: ProxyRouteContext) {
  return proxy(req, ctx);
}
export async function PUT(req: Request, ctx: ProxyRouteContext) {
  return proxy(req, ctx);
}
export async function PATCH(req: Request, ctx: ProxyRouteContext) {
  return proxy(req, ctx);
}
export async function DELETE(req: Request, ctx: ProxyRouteContext) {
  return proxy(req, ctx);
}

async function proxy(req: Request, ctx: ProxyRouteContext) {
  const baseUrl = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const token = (await cookies()).get(COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json(errorBody("AUTH_REQUIRED", "Authentication required.", "Unauthenticated"), { status: 401 });
  }

  const url = new URL(req.url);
  const tenantIdFromQuery = url.searchParams.get("tenant_id");
  if (tenantIdFromQuery) url.searchParams.delete("tenant_id");
  const params = await ctx.params;
  const target = new URL(`${baseUrl}/${params.path.join("/")}`);
  target.search = url.search;

  const headers = new Headers(req.headers);
  headers.set("Authorization", `Bearer ${token}`);
  const requestedTenantOverride = tenantIdFromQuery ?? headers.get("X-Tenant-Id");
  if (requestedTenantOverride) {
    // Tenant override must never be allowed for non-super-admin users (UI gating is not sufficient).
    const ok = await isSuperAdmin(baseUrl, token);
    if (!ok) {
      return NextResponse.json(
        errorBody("TENANT_SCOPE_ERROR", "Organization context is required.", "Tenant override not permitted"),
        { status: 403 },
      );
    }
    headers.set("X-Tenant-Id", requestedTenantOverride);
  }
  headers.delete("cookie");
  headers.delete("host");

  const r = await fetch(target.toString(), {
    method: req.method,
    headers,
    body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.text(),
    cache: "no-store",
  });

  const resHeaders = new Headers(r.headers);
  resHeaders.delete("set-cookie");
  const body = await r.arrayBuffer();
  return new NextResponse(body, { status: r.status, headers: resHeaders });
}

async function isSuperAdmin(baseUrl: string, token: string): Promise<boolean> {
  try {
    const r = await fetch(`${baseUrl}/auth/me`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!r.ok) return false;
    const data = (await r.json()) as any;
    return data && typeof data === "object" && data.role === "super_admin";
  } catch {
    return false;
  }
}
