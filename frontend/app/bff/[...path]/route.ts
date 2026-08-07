import { NextRequest } from "next/server";

const BACKEND =
  process.env.BACKEND_URL ||
  "https://atoms-lite-backend-production.up.railway.app";

export async function proxy(req: NextRequest, method: string) {
  // /bff/* maps to backend /api/*
  const path = req.nextUrl.pathname.replace(/^\/bff\//, "");
  const target = `${BACKEND}/api/${path}${req.nextUrl.search}`;

  const body =
    method !== "GET" && method !== "HEAD" ? req.body : undefined;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");

  const upstream = await fetch(target, {
    method,
    headers,
    body,
    duplex: "half",
    cache: "no-store",
  } as RequestInit);

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = (req: NextRequest) => proxy(req, "GET");
export const POST = (req: NextRequest) => proxy(req, "POST");
export const PUT = (req: NextRequest) => proxy(req, "PUT");
export const DELETE = (req: NextRequest) => proxy(req, "DELETE");
export const PATCH = (req: NextRequest) => proxy(req, "PATCH");
