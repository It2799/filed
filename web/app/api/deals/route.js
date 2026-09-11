import { bulkBlockDeals, configured, applyFilters } from "../../../lib/deals";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const MAX_DAYS = 30;
const MAX_ROWS = 400;

// Only the fields the page draws.
function publicRow(row) {
  const fields = [
    "id", "day", "kind", "exchange", "symbol", "scrip", "company", "mcap",
    "who", "side", "shares", "price", "value", "netted", "gross_buy",
    "gross_sell", "rows", "remarks", "headline",
  ];
  return Object.fromEntries(fields.map((k) => [k, row[k]]));
}

export async function GET(request) {
  if (!configured()) {
    return Response.json(
      { error: "Bulk and block deal storage isn't configured yet." },
      { status: 503 }
    );
  }

  const url = new URL(request.url);
  const days = Math.min(
    MAX_DAYS,
    Math.max(1, Number(url.searchParams.get("days")) || 7)
  );
  const side = url.searchParams.get("side") || "all";
  const kind = url.searchParams.get("kind") || "all";
  const exchange = url.searchParams.get("exchange") || "all";
  const q = url.searchParams.get("q") || "";

  const { days: held, deals, meta } = await bulkBlockDeals({ days });
  const filtered = applyFilters(deals, { side, kind, exchange, q });

  // Biggest first. A fund putting Rs 300 crore in is the reason to open this
  // page; a Rs 2 crore bulk deal in a micro-cap is not.
  filtered.sort((a, b) => (b.value || 0) - (a.value || 0));

  const buys = filtered.filter((d) => (d.side || "").toLowerCase() === "buy");
  const sells = filtered.filter((d) => (d.side || "").toLowerCase() === "sell");

  return Response.json({
    days: held,
    meta,
    counts: {
      total: filtered.length,
      buys: buys.length,
      sells: sells.length,
      boughtValue: buys.reduce((s, d) => s + (Number(d.value) || 0), 0),
      soldValue: sells.reduce((s, d) => s + (Number(d.value) || 0), 0),
    },
    items: filtered.slice(0, MAX_ROWS).map(publicRow),
  });
}
