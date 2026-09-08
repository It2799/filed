import { scheduleDailyBriefBroadcast, kitBroadcastConfigured } from "../../../../../lib/kit-broadcast";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const IST_OFFSET = "+05:30";
const STATUS_TTL_SECONDS = 90 * 86400;

function response(body, status = 200) {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private, max-age=0" },
  });
}

function authorized(request) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return false;
  const bearer = request.headers.get("authorization") === `Bearer ${secret}`;
  const query = request.nextUrl.searchParams.get("key") === secret;
  return bearer || query;
}

function todayIST() {
  return new Date(Date.now() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);
}

function eightAmOrSoon(day) {
  const eightAm = new Date(`${day}T08:00:00${IST_OFFSET}`);
  return (eightAm.getTime() > Date.now() + 60000 ? eightAm : new Date(Date.now() + 60000)).toISOString();
}

async function redis(command) {
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error("Redis is not configured.");
  const result = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(command),
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!result.ok) throw new Error(`Redis ${result.status}`);
  return (await result.json()).result;
}

async function handler(request) {
  if (!authorized(request)) return new Response("Not found.", { status: 404 });
  if (!kitBroadcastConfigured()) return response({ error: "Kit broadcast delivery is not configured." }, 503);

  const day = todayIST();
  const statusKey = `mt:brief:${day}:kit-broadcast`;
  try {
    const rawIndex = await redis(["GET", "mt:brief:index"]);
    const index = JSON.parse(rawIndex || "[]");
    const parts = Number(await redis(["GET", `mt:brief:${day}:parts`]) || 0);
    if (!Array.isArray(index) || index[0] !== day || parts < 1) {
      return response({
        ok: false,
        retry: true,
        error: "Today’s report is not ready yet. Retry this endpoint in two minutes.",
        day,
      }, 409);
    }

    const lock = await redis(["SET", statusKey, JSON.stringify({ state: "creating", at: new Date().toISOString() }), "NX", "EX", "600"]);
    if (lock !== "OK") {
      const existing = await redis(["GET", statusKey]);
      let detail = existing;
      try { detail = JSON.parse(existing); } catch {}
      return response({ ok: true, duplicatePrevented: true, day, broadcast: detail });
    }

    try {
      const broadcast = await scheduleDailyBriefBroadcast({ day, sendAt: eightAmOrSoon(day) });
      await redis(["SET", statusKey, JSON.stringify({ state: "scheduled", ...broadcast }), "EX", String(STATUS_TTL_SECONDS)]);
      return response({
        ok: true,
        day,
        audience: "all active Kit subscribers",
        broadcast,
      });
    } catch (error) {
      await redis(["DEL", statusKey]).catch(() => {});
      throw error;
    }
  } catch (error) {
    console.error("[brief send cron] failed:", error.message || error);
    return response({ error: "Could not schedule today’s Kit broadcast." }, 502);
  }
}

export const GET = handler;
export const POST = handler;
