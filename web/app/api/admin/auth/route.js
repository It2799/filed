import {
  adminConfigured,
  adminCookie,
  adminRateLimitKey,
  clearAdminCookie,
  correctAdminPassword,
  createAdminSession,
  isAdmin,
} from "../../../../lib/admin-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function privateJson(body, status = 200, headers = {}) {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private, max-age=0", ...headers },
  });
}

async function limit(request, clear = false) {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return { allowed: true };
  const key = adminRateLimitKey(request);
  const command = clear ? ["DEL", key] : ["INCR", key];
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(command),
      cache: "no-store",
    });
    const count = Number((await response.json()).result || 0);
    if (!clear && count === 1) {
      await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(["EXPIRE", key, 900]),
        cache: "no-store",
      });
    }
    return { allowed: clear || count <= 8, retryMinutes: 15 };
  } catch {
    return { allowed: true };
  }
}

export async function GET(request) {
  return privateJson({ configured: adminConfigured(), authenticated: isAdmin(request) });
}

export async function POST(request) {
  if (!adminConfigured()) return privateJson({ error: "Admin access is not configured." }, 503);
  const rate = await limit(request);
  if (!rate.allowed) {
    return privateJson({ error: "Too many attempts. Try again in 15 minutes." }, 429);
  }
  let password = "";
  try {
    password = String((await request.json()).password || "");
  } catch {
    return privateJson({ error: "Enter the admin password." }, 400);
  }
  if (!correctAdminPassword(password)) {
    return privateJson({ error: "Incorrect password." }, 401);
  }
  await limit(request, true);
  return privateJson(
    { ok: true },
    200,
    { "Set-Cookie": adminCookie(createAdminSession()) }
  );
}

export async function DELETE() {
  return privateJson({ ok: true }, 200, { "Set-Cookie": clearAdminCookie() });
}
