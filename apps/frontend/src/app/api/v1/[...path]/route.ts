import { NextRequest, NextResponse } from "next/server";

const BACKEND_INTERNAL_URL = (process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000")
  .trim()
  .replace(/\/+$/, "")
  .replace(/\/api\/v1$/i, "");

async function proxyRequest(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const joined = path.map((seg) => seg.replace(/^\/+|\/+$/g, "")).filter(Boolean).join("/");
  const search = request.nextUrl.search || "";
  const targetUrl = `${BACKEND_INTERNAL_URL}/api/v1/${joined}/${search}`;

  const forwardHeaders = new Headers();
  const passthroughHeaders = [
    "accept",
    "authorization",
    "content-type",
    "cookie",
    "origin",
    "referer",
    "x-csrftoken",
    "x-organization-id",
  ];
  for (const name of passthroughHeaders) {
    const val = request.headers.get(name);
    if (val) forwardHeaders.set(name, val);
  }
  forwardHeaders.set("host", new URL(BACKEND_INTERNAL_URL).host);

  const method = request.method.toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  const backendRes = await fetch(targetUrl, {
    method,
    headers: forwardHeaders,
    body,
    redirect: "manual",
  });

  const responseHeaders = new Headers();
  const contentType = backendRes.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);
  const cacheControl = backendRes.headers.get("cache-control");
  if (cacheControl) responseHeaders.set("cache-control", cacheControl);
  const contentDisposition = backendRes.headers.get("content-disposition");
  if (contentDisposition) responseHeaders.set("content-disposition", contentDisposition);

  const setCookies = backendRes.headers.getSetCookie?.() || [];
  for (const cookie of setCookies) {
    responseHeaders.append("set-cookie", cookie);
  }

  const resBody = await backendRes.arrayBuffer();
  return new NextResponse(resBody, {
    status: backendRes.status,
    headers: responseHeaders,
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
