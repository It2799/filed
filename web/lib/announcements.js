/**
 * Reads the announcements that publish.py pushed into Redis.
 *
 * Layout, one key per day so old days expire on their own:
 *   mt:day:2026-08-17  ->  JSON list of that day's important filings
 *   mt:index           ->  JSON list of the days currently held
 *   mt:meta            ->  when it last ran and what it found
 */

const DAYS = 7;

function creds() {
  return {
    url: process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL,
    token: process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN,
  };
}

export function configured() {
  const { url, token } = creds();
  return Boolean(url && token);
}

async function redis(command) {
  const { url, token } = creds();
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(command),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Redis ${res.status}: ${await res.text()}`);
  return (await res.json()).result;
}

function parse(raw) {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** Every important filing from the last 7 days, newest first. */
export async function recent() {
  if (!configured()) return { days: [], items: [], meta: null };

  const [indexRaw, metaRaw] = await redis(["MGET", "mt:index", "mt:meta"]);
  const days = (parse(indexRaw) || []).slice(0, DAYS);
  const meta = parse(metaRaw);

  if (!days.length) return { days: [], items: [], meta };

  // One round trip for every day rather than seven.
  const blobs = await redis(["MGET", ...days.map((d) => `mt:day:${d}`)]);

  const items = [];
  days.forEach((day, i) => {
    const rows = parse(blobs[i]) || [];
    for (const r of rows) items.push({ ...r, day });
  });

  // Highest score first, then most recent.
  items.sort((a, b) => (b.score - a.score) || String(b.time).localeCompare(String(a.time)));

  return { days, items, meta };
}
