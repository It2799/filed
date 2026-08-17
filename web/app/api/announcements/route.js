import { recent, configured } from "../../../lib/announcements";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const LIMIT = 500;

export async function GET(request) {
  if (!configured()) {
    return Response.json(
      { error: "Announcements storage isn't configured yet." }, { status: 503 });
  }

  try {
    const url = new URL(request.url);
    const scope = url.searchParams.get("scope") === "all" ? "all" : "important";
    const { days, items, meta } = await recent({ scope });

    // Optional narrowing, so the page can filter without shipping everything twice.
    const tag = url.searchParams.get("tag");
    const day = url.searchParams.get("day");
    const q = (url.searchParams.get("q") || "").toLowerCase().trim();

    let rows = items;
    if (tag) rows = rows.filter((r) => r.tag === tag);
    if (day) rows = rows.filter((r) => r.day === day);
    if (q) {
      rows = rows.filter((r) =>
        `${r.company} ${r.ticker} ${r.headline} ${r.summary} ${r.category}`
          .toLowerCase()
          .includes(q));
    }

    // Count categories over everything that matched, not just the slice we send,
    // otherwise the chips would under-report on a busy week.
    const tagCounts = {};
    for (const r of rows) tagCounts[r.tag] = (tagCounts[r.tag] || 0) + 1;

    // On a heavy results day there can be thousands of filings over 7 days.
    // Shipping all of them would be a multi-megabyte page load. On the Important
    // tab the summarised ones lead, since they're the point of the product; the
    // All tab keeps its chronological order. The Excel export has every row.
    const total = rows.length;
    const summarised = rows.filter((r) => r.summary);
    rows =
      scope === "all"
        ? rows.slice(0, LIMIT)
        : [...summarised, ...rows.filter((r) => !r.summary)].slice(0, LIMIT);

    return Response.json({
      days,
      meta,
      scope,
      total,
      tagCounts,
      summarised: summarised.length,
      truncated: total > rows.length,
      count: rows.length,
      items: rows,
    });
  } catch (err) {
    console.error("[announcements]", err);
    return Response.json({ error: "Couldn't load announcements." }, { status: 500 });
  }
}
