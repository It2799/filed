import { insiderTrades, configured, applyFilters } from "../../../lib/insider";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const MAX_DAYS = 30;
const MAX_ROWS = 400;

// Only the fields the page draws. The stored row also carries the XBRL's own
// bookkeeping - ISIN, scrip code, the filing's file name - which is worth
// keeping for later and not worth moving through Vercel on every request.
function publicRow(row) {
  const fields = [
    "id", "day", "company", "symbol", "exchange", "who", "category",
    "side", "mode", "shares", "value", "before_n", "before_pct",
    "after_n", "after_pct", "traded_on", "filed_on", "headline",
    "regulation", "revised", "url",
  ];
  return Object.fromEntries(fields.map((k) => [k, row[k]]));
}

export async function GET(request) {
  if (!configured()) {
    return Response.json(
      { error: "Insider trading storage isn't configured yet." },
      { status: 503 }
    );
  }

  const url = new URL(request.url);
  const days = Math.min(
    MAX_DAYS,
    Math.max(1, Number(url.searchParams.get("days")) || 7)
  );
  const side = url.searchParams.get("side") || "all";
  const role = url.searchParams.get("role") || "all";
  const q = url.searchParams.get("q") || "";

  const { days: held, trades, meta } = await insiderTrades({ days });
  const filtered = applyFilters(trades, { side, role, q });

  // Biggest first. A promoter putting Rs 20 crore in is the reason to open
  // this page; five hundred shares changing hands is not.
  filtered.sort((a, b) => (b.value || 0) - (a.value || 0));

  const buys = filtered.filter((t) => (t.side || "").toLowerCase() === "buy");
  const sells = filtered.filter((t) => (t.side || "").toLowerCase() === "sell");

  return Response.json({
    days: held,
    meta,
    counts: {
      total: filtered.length,
      buys: buys.length,
      sells: sells.length,
      boughtValue: buys.reduce((s, t) => s + (Number(t.value) || 0), 0),
      soldValue: sells.reduce((s, t) => s + (Number(t.value) || 0), 0),
    },
    items: filtered.slice(0, MAX_ROWS).map(publicRow),
  });
}
