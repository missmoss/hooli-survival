import { NextRequest } from 'next/server';

const UPSTREAM_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// Cleanup path: once the proxy becomes the permanent transport layer, revisit this file and
// remove any passthrough/fallback behavior that only exists to keep the old direct path alive.
function buildUpstreamUrl(pathSegments: string[], search: string): string {
  const path = pathSegments.join('/');
  return `${UPSTREAM_BASE}/${path}${search}`;
}

function copyRequestHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  const allowlist = [
    'accept',
    'accept-language',
    'content-type',
    'cookie',
    'referer',
    'origin',
    'user-agent',
    'x-office-sim-browser-id',
    'x-request-id',
  ];

  for (const name of allowlist) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  const forwardedFor = request.headers.get('x-forwarded-for');
  if (forwardedFor) {
    headers.set('x-forwarded-for', forwardedFor);
  }

  return headers;
}

function copyResponseHeaders(upstream: Response): Headers {
  const headers = new Headers();
  const passthrough = [
    'content-type',
    'cache-control',
    'etag',
    'last-modified',
    'set-cookie',
  ];

  for (const name of passthrough) {
    const value = upstream.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  return headers;
}

async function proxy(request: NextRequest, pathSegments: string[]): Promise<Response> {
  const upstreamUrl = buildUpstreamUrl(pathSegments, request.nextUrl.search);
  const headers = copyRequestHeaders(request);
  const body =
    request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.text();

  const upstream = await fetch(upstreamUrl, {
    method: request.method,
    headers,
    body,
    redirect: 'manual',
    cache: 'no-store',
  });

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: copyResponseHeaders(upstream),
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path);
}
