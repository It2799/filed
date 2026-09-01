import { recent, configured } from "../../../lib/announcements";

export const dynamic = "force-dynamic";
export const revalidate = 0;

// "Worth reading" is a few hundred filings, so we can send effectively all of
// them. "Everything" runs to five figures on a results week, so that one stays
// capped and relies on the filters below.
const LIMIT = { important: 1500, all: 600 };

// Market cap bands, in crore. A Rs 400 crore order means something entirely
// different at a Rs 900 crore company than at a Rs 2 lakh crore one, so the
// dashboard can be narrowed to the size of company a reader actually follows.
const BANDS = {
  mega: [100000, Infinity],   // above Rs 1 lakh crore
  large: [50000, 100000],     // Rs 50,000 crore to 1 lakh crore
  mid: [10000, 50000],        // Rs 10,000 to 50,000 crore
  small: [1000, 10000],       // Rs 1,000 to 10,000 crore
  micro: [0, 1000],           // below Rs 1,000 crore
};

function inBand(row, band) {
  const range = BANDS[band];
  if (!range) return true;
  const cap = Number(row.mcap);
  if (!cap) return false;              // unknown size cannot claim a band
  return cap >= range[0] && cap < range[1];
}

export async function GET(request) {
  if (!configured()) {
    return Response.json(
      { error: "Announcements storage isn't configured yet." }, { status: 503 });
  }

  try {
    const url = new URL(request.url);
    const scope = url.searchParams.get("scope") === "all" ? "all" : "important";
    const tag = url.searchParams.get("tag");
    const day = url.searchParams.get("day");
    const q = (url.searchParams.get("q") || "").toLowerCase().trim();
    const band = url.searchParams.get("band");

    const sort = url.searchParams.get("sort") === "important" ? "important" : "latest";
    let { days, items, meta } = await recent({ scope, sort });

    // Worth reading means summarised - one set, not two. A day written before
    // that rule existed can still hold a filing marked important with no
    // summary against it, and showing "661 worth reading, 394 summarised" makes
    // the product look like it gave up halfway. Anything without a summary is
    // not offered as a headline item, whatever the stored data says.
    if (scope === "important") items = items.filter((r) => r.summary);

    // Narrow by day and text first. Whatever survives is the universe the
    // category counts describe, so the sidebar keeps showing every category
    // even while one of them is selected.
    let universe = items;
    if (day) universe = universe.filter((r) => r.day === day);
    if (q) {
      universe = universe.filter((r) =>
        `${r.company} ${r.ticker} ${r.headline} ${r.summary} ${r.category}`
          .toLowerCase()
          .includes(q));
    }

    // Counted here, on the full set, because the browser cannot: what it
    // receives is capped and sorted newest first, so tallying the response
    // showed older days as 0 while clicking them filled the feed. Taken before
    // the day filter, so every day keeps showing its own total while one of
    // them is selected.
    const dayCounts = {};
    for (const r of items) {
      if (r.day) dayCounts[r.day] = (dayCounts[r.day] || 0) + 1;
    }

    // Counts for the size bands are taken before the band filter is applied,
    // so every band keeps showing its total while one of them is selected.
    const bandCounts = {};
    for (const key of Object.keys(BANDS)) {
      bandCounts[key] = universe.filter((r) => inBand(r, key)).length;
    }
    bandCounts.unknown = universe.filter((r) => !Number(r.mcap)).length;

    if (band && BANDS[band]) universe = universe.filter((r) => inBand(r, band));

    const tagCounts = {};
    for (const r of universe) tagCounts[r.tag] = (tagCounts[r.tag] || 0) + 1;

    // Category filter applies after the counts, and crucially before the cut -
    // otherwise picking a small category searches a list it was already
    // truncated out of, and comes back empty.
    let rows = tag ? universe.filter((r) => r.tag === tag) : universe;

    const total = rows.length;
    const summarised = rows.filter((r) => r.summary).length;   // == total when scope is important
    const cap = LIMIT[scope];

    // The order above is the order we keep. Promoting summarised rows here
    // would silently undo a "latest first" sort.
    if (rows.length > cap) rows = rows.slice(0, cap);

    return Response.json(
      {
        days,
        meta,
        scope,
        sort,
        total,
        tagCounts,
        bandCounts,
        dayCounts,
        band: band || null,
        summarised,
        truncated: total > rows.length,
        count: rows.length,
        items: rows,
      },
      // Without this the CDN happily serves yesterday's filings from its edge
      // cache after a fresh scrape has landed.
      { headers: { "Cache-Control": "no-store, max-age=0" } });
  } catch (err) {
    console.error("[announcements]", err);
    return Response.json({ error: "Couldn't load announcements." }, { status: 500 });
  }
}
