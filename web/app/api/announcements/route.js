import { recent, configured } from "../../../lib/announcements";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request) {
  if (!configured()) {
    return Response.json(
      { error: "Announcements storage isn't configured yet." }, { status: 503 });
  }

  try {
    const { days, items, meta } = await recent();

    // Optional narrowing, so the page can filter without shipping everything twice.
    const url = new URL(request.url);
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

    return Response.json({ days, meta, count: rows.length, items: rows });
  } catch (err) {
    console.error("[announcements]", err);
    return Response.json({ error: "Couldn't load announcements." }, { status: 500 });
  }
}
