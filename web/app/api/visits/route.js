export const dynamic = "force-dynamic";

/**
 * Visitor counts, kept in the same KV store as everything else.
 *
 *   POST /api/visits   { id }   count this visit, return the totals
 *   GET  /api/visits             just read the totals
 *
 * Three numbers:
 *   mt:visits:total   every page view, ever            (INCR)
 *   mt:visits:uniq    distinct browsers                 (PFADD / PFCOUNT)
 *   mt:visits:live    browsers seen in the last 5 min   (ZADD / ZCOUNT)
 *
 * `id` is a random string the browser makes up and keeps in localStorage. No
 * IP address, no fingerprint, nothing that identifies a person - it only has
 * to be stable enough to tell one browser from another. HyperLogLog then
 * counts the distinct ones in about 12 KB however many there are, and cannot
 * be read back to recover the ids that went into it.
 */

const URL_ = process.env.KV_REST_API_URL;
const TOKEN = process.env.KV_REST_API_TOKEN;

const LIVE_WINDOW_SECONDS = 300;

async function redis(command) {
  if (!URL_ || !TOKEN) return null;
  const r = await fetch(URL_, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(command),
    cache: "no-store",
  });
  if (!r.ok) return null;
  return (await r.json()).result;
}

/** Several commands in one round trip. */
async function pipeline(commands) {
  if (!URL_ || !TOKEN) return [];
  const r = await fetch(`${URL_}/pipeline`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(commands),
    cache: "no-store",
  });
  if (!r.ok) return [];
  const out = await r.json();
  return Array.isArray(out) ? out.map((x) => x.result) : [];
}

function cleanId(v) {
  // Only what the browser is supposed to send, and never more of it than the
  // store should be asked to hold.
  return String(v || "").replace(/[^A-Za-z0-9_-]/g, "").slice(0, 64);
}

async function totals(now) {
  const [total, uniq, live] = await pipeline([
    ["GET", "mt:visits:total"],
    ["PFCOUNT", "mt:visits:uniq"],
    ["ZCOUNT", "mt:visits:live", now - LIVE_WINDOW_SECONDS, "+inf"],
  ]);
  return {
    total: Number(total || 0),
    unique: Number(uniq || 0),
    live: Number(live || 0),
  };
}

export async function GET() {
  if (!URL_ || !TOKEN) return Response.json({ total: 0, unique: 0, live: 0 });
  const now = Math.floor(Date.now() / 1000);
  return Response.json(await totals(now), {
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(request) {
  if (!URL_ || !TOKEN) return Response.json({ total: 0, unique: 0, live: 0 });

  let id = "";
  try {
    id = cleanId((await request.json()).id);
  } catch {
    /* a body we cannot read is still a visit */
  }

  const now = Math.floor(Date.now() / 1000);
  const writes = [["INCR", "mt:visits:total"]];
  if (id) {
    writes.push(["PFADD", "mt:visits:uniq", id]);
    writes.push(["ZADD", "mt:visits:live", now, id]);
    // Anything older than the window is no longer "live", and left alone the
    // set would grow for ever.
    writes.push(["ZREMRANGEBYSCORE", "mt:visits:live", "-inf",
                 now - LIVE_WINDOW_SECONDS]);
  }
  await pipeline(writes);

  return Response.json(await totals(now), {
    headers: { "Cache-Control": "no-store" },
  });
}
