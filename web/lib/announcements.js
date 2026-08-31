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

// Company names differ between the exchanges - "Mankind Pharma Ltd" on one,
// "Mankind Pharma Limited" on the other - so the suffixes come off before
// anything is compared.
const NAME_NOISE =
  /\b(limited|ltd|private|pvt|the|and|company|co|corporation|corp|india|indian|inc)\b/g;

function normCompany(name) {
  return String(name || "").toLowerCase().replace(NAME_NOISE, " ").replace(/[^a-z0-9]/g, "");
}

/**
 * One company, one day, one kind of news - one entry.
 *
 * The scraper folds duplicates too, but a day written by an older run still
 * holds its own, and re-reading a week of PDFs takes over an hour. Doing it
 * here as well means the site is right straight away and stays right even if
 * a future run writes something twice. It costs a few milliseconds.
 */
// One board meeting is filed under whichever headings apply, and they are
// rarely the same heading twice. Happiest Minds' merger with ITC Infotech
// came through as both "Scheme of Arrangement" and "Acquisition"; Kiri's
// warrant issue as both "Rights Issue" and "Pref". The summaries describe the
// same event but share almost no wording - "board approved amalgamation with
// ITC Infotech" against "announced a merger with ITC Infotech" - so word
// overlap cannot catch them either.
//
// Grouping the headings by the kind of news does. A company restructuring and
// a company raising money on the same day are still two entries, because
// those are two families; the same restructuring filed four ways is one.
const FAMILY = {
  "Scheme Of Arrangement": "restructure",
  Acquisition: "restructure",
  "Open Offer": "restructure",
  Qip: "raise",
  "Qip Allotment": "raise",
  Pref: "raise",
  Warrants: "raise",
  "Rights Issue": "raise",
  "Fund Raising": "raise",
  Results: "results",
  Outcome: "results",
  Concall: "results",
  Presentation: "results",
  "Board Meeting": "results",
  Dividend: "payout",
  Buyback: "payout",
  Bonus: "payout",
  Split: "payout",
  "Change In Management": "people",
  Resignation: "people",
};

const family = (tag) => FAMILY[tag] || null;

function summaryWords(text) {
  return new Set(
    String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9 ]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 3)
  );
}

function overlap(a, b) {
  if (!a.size || !b.size) return 0;
  let shared = 0;
  for (const w of a) if (b.has(w)) shared += 1;
  return shared / Math.min(a.size, b.size);
}

/**
 * One company, one day, one piece of news - one entry.
 *
 * A single board meeting is filed several times over, each copy under a
 * different heading. Happiest Minds' merger with ITC Infotech arrived as
 * "Scheme of Arrangement", "Acquisition", "Press Release", "Change in
 * Registered Office Address" and more - seven entries, one event. Matching on
 * the heading cannot collapse those, because the headings are precisely what
 * differ.
 *
 * The summaries, though, say the same thing in nearly the same words, and by
 * the time anything is served they have been written. So filings from one
 * company on one day are compared on their summaries: near-identical ones
 * fold together, genuinely different news stays apart. Two filings under the
 * same heading are treated as the same event whatever their wording, which is
 * the old rule kept intact.
 */
function foldDuplicates(items) {
  const byCompanyDay = new Map();
  const out = [];

  for (const r of items) {
    const key = `${normCompany(r.company)}|${r.day}`;
    const seen = byCompanyDay.get(key) || [];
    const words = summaryWords(r.summary || r.headline);

    // Same heading, or the same kind of news, is the same event. Failing
    // both, the summaries have to agree.
    const match = seen.find(
      (e) =>
        e.row.tag === r.tag ||
        (family(e.row.tag) && family(e.row.tag) === family(r.tag)) ||
        overlap(words, e.words) >= 0.55
    );

    if (match) {
      match.row.also_filed = (match.row.also_filed || 0) + 1;
      if (r.pdf_url && (match.row.also_pdfs || []).length < 4) {
        match.row.also_pdfs = [...(match.row.also_pdfs || []), r.pdf_url];
      }
      // Keep every heading the event was filed under, so nothing is hidden.
      const tags = new Set([...(match.row.also_tags || []), r.tag]);
      tags.delete(match.row.tag);
      match.row.also_tags = [...tags];
      continue;
    }

    const copy = { ...r };
    out.push(copy);
    seen.push({ row: copy, words });
    byCompanyDay.set(key, seen);
  }
  return out;
}

/**
 * Filings from the last 7 days, newest first.
 *
 * scope "important" (default) reads only the filings worth reading, with their
 * summaries. scope "all" also pulls the routine ones, which is a lot more data,
 * so the page only asks for it when someone clicks the All tab.
 */
export async function recent({ scope = "important", sort = "latest" } = {}) {
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

  // Newest first by default. Someone opening the dashboard wants to know what
  // has just landed, not what scored highest across the whole week - a buyback
  // from Tuesday should not sit above this evening's filings.
  const byLatest = (a, b) =>
    String(b.day).localeCompare(String(a.day)) ||
    String(b.time).localeCompare(String(a.time));

  const byImportance = (a, b) =>
    (b.score - a.score) || byLatest(a, b);

  items.sort(sort === "important" ? byImportance : byLatest);

  // Sorted first, so the entry that survives a fold is the best one under the
  // order the reader actually asked for.
  return { days, items: foldDuplicates(items), meta };
}
