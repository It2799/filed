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

/**
 * A busy day can exceed the request size limit, so publish.py may have split it
 * into `key:0`, `key:1`… with a `key:parts` counter. This reassembles whichever
 * shape it finds.
 */
async function readKeys(keys) {
  if (!keys.length) return [];

  const partCounts = await redis(["MGET", ...keys.map((k) => `${k}:parts`)]);

  const wanted = [];
  keys.forEach((key, i) => {
    const n = Number(partCounts[i] || 1);
    if (n <= 1) wanted.push({ key, ref: key });
    else for (let p = 0; p < n; p++) wanted.push({ key, ref: `${key}:${p}` });
  });

  const blobs = await redis(["MGET", ...wanted.map((w) => w.ref)]);

  const out = new Map();
  wanted.forEach((w, i) => {
    const rows = parse(blobs[i]) || [];
    if (!out.has(w.key)) out.set(w.key, []);
    out.get(w.key).push(...rows);
  });
  return keys.map((k) => out.get(k) || []);
}

/**
 * Filings from the last 7 days, newest first.
 *
 * scope "important" (default) reads only the filings worth reading, with their
 * summaries. scope "all" also pulls the routine ones, which is a lot more data,
 * so the page only asks for it when someone clicks the All tab.
 */
export async function recent({ scope = "important" } = {}) {
  if (!configured()) return { days: [], items: [], meta: null };

  const [indexRaw, metaRaw] = await redis(["MGET", "mt:index", "mt:meta"]);
  const days = (parse(indexRaw) || []).slice(0, DAYS);
  const meta = parse(metaRaw);

  if (!days.length) return { days: [], items: [], meta };

  const items = [];
  const push = (dayLists) =>
    dayLists.forEach((rows, i) => {
      for (const r of rows) items.push({ ...r, day: days[i] });
    });

  push(await readKeys(days.map((d) => `mt:day:${d}`)));
  if (scope === "all") {
    push(await readKeys(days.map((d) => `mt:all:${d}`)));
  }

  // Highest score first, then most recent.
  items.sort((a, b) => (b.score - a.score) || String(b.time).localeCompare(String(a.time)));

  return { days, items, meta };
}
