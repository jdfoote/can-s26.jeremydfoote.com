// Bluesky authenticated proxy - Cloudflare Worker
// Secrets required (set via `wrangler secret put`):
//   BSKY_HANDLE
//   BSKY_APP_PASS

let cachedToken = null;
let tokenExpiry = 0;

const BSKY_BASE = 'https://bsky.social/xrpc';

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

async function login(env) {
  const res = await fetch(`${BSKY_BASE}/com.atproto.server.createSession`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier: env.BSKY_HANDLE, password: env.BSKY_APP_PASS }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Bluesky login failed (${res.status}): ${body}`);
  }

  const data = await res.json();
  cachedToken = data.accessJwt;
  tokenExpiry = Date.now() + 90 * 60 * 1000;
  return cachedToken;
}

async function getToken(env) {
  if (cachedToken && Date.now() < tokenExpiry) {
    return cachedToken;
  }
  return login(env);
}

async function proxyRequest(endpoint, env, retry = true) {
  const token = await getToken(env);
  const res = await fetch(`${BSKY_BASE}/${endpoint}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'User-Agent': 'Mozilla/5.0',
    },
  });

  if ((res.status === 400 || res.status === 401) && retry) {
    const body = await res.text();
    if (/expiredToken|invalidToken|auth|jwt/i.test(body)) {
      cachedToken = null;
      return proxyRequest(endpoint, env, false);
    }
    return new Response(JSON.stringify({ error: `Bluesky returned ${res.status}`, details: body }), {
      status: res.status,
      headers: { 'Content-Type': 'application/json', ...CORS },
    });
  }

  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { 'Content-Type': 'application/json', ...CORS },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS });
    }

    if (url.pathname !== '/api/bsky') {
      return new Response('Not found', { status: 404, headers: CORS });
    }

    const endpoint = url.searchParams.get('endpoint');
    if (!endpoint) {
      return new Response(JSON.stringify({ error: 'missing endpoint' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...CORS },
      });
    }

    try {
      return await proxyRequest(endpoint, env);
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 502,
        headers: { 'Content-Type': 'application/json', ...CORS },
      });
    }
  },
};
