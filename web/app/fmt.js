// Market cap comes through in crores. Big numbers are easier to read in lakh
// crore than as "17,38,119 Cr", so anything past a lakh crore switches units.
export function mcapLabel(cr) {
  if (!cr || cr <= 0) return null;
  if (cr >= 100000) return `₹${(cr / 100000).toFixed(2)} L Cr`;
  if (cr >= 1000) return `₹${Math.round(cr).toLocaleString("en-IN")} Cr`;
  return `₹${Math.round(cr)} Cr`;
}

// Rough size bucket, used only to tint the figure so a 200 Cr microcap and a
// 2 lakh crore giant don't look identical at a glance.
export function mcapTier(cr) {
  if (!cr) return "";
  if (cr >= 20000) return "lg";
  if (cr >= 5000) return "md";
  return "sm";
}

// ---------------------------------------------------------------------------
// Money, quantities and dates, in one place.
//
// The insider and bulk-deal pages each had their own copy of all of this, and
// the copies had already drifted - one wrote "Rs 47.45 cr" and the other
// "₹47 Cr" for the same figure, on two pages one click apart. Anything a
// reader compares across pages belongs here.
// ---------------------------------------------------------------------------

// 1234567 -> 12,34,567. Intl gives Indian grouping for free with en-IN.
export function count(n) {
  return (Number(n) || 0).toLocaleString("en-IN");
}

// The exchanges shout. "SOUTH WEST PINNACLE EXPLORATION LIMITED" is how the
// feed spells it, and a page of that is genuinely harder to read - capitals
// remove the word shapes the eye uses to skim.
//
// Only touches names that are ENTIRELY capitals, so anything already written
// properly is left exactly as it is. Words of three letters or fewer keep
// their capitals, because those are the acronyms: JSW, NCL, TTK, IRB, GMR.
// "Limited" becomes "Ltd" - the same word, a third of the width, and nobody
// reads the long one anyway.
// ...except these. They are short enough to look like acronyms and are not.
const NOT_ACRONYMS = new Set(["ltd", "inc", "plc", "llp", "co", "and", "the",
  "of", "for", "pvt", "llc"]);

export function name(s) {
  let raw = (s || "").trim();
  if (!raw) return "";
  // BSE tags some scrips "NCL INDUSTRIES LTD-$". The marker is for their own
  // surveillance groups and means nothing to a reader.
  raw = raw.replace(/\s*-\s*[$*#]+\s*$/, "").trim();

  const cased = /[a-z]/.test(raw)
    ? raw
    : raw.toLowerCase().replace(/[\w'&.]+/g, (w) =>
        w.length <= 3 && !NOT_ACRONYMS.has(w)
          ? w.toUpperCase()
          : w[0].toUpperCase() + w.slice(1)
      );
  return cased
    .replace(/\bLimited\b\.?/gi, "Ltd")
    .replace(/\bPrivate\b/gi, "Pvt")
    .replace(/\s+/g, " ")
    .trim();
}

// A rupee figure, in the unit an Indian reader thinks in.
export function money(n) {
  const v = Number(n) || 0;
  if (!v) return "";
  // toFixed on its own gives "₹1160.00 Cr" for a Rs 1,160 crore block. Past a
  // thousand crore the grouping is what makes the figure readable at a glance.
  const two = (x) =>
    x.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  if (v >= 1e7) return `₹${two(v / 1e7)} Cr`;
  if (v >= 1e5) return `₹${two(v / 1e5)} L`;
  return `₹${Math.round(v).toLocaleString("en-IN")}`;
}

// A share price, with the paise where a reader would look for them. A block
// really is priced at ₹872.50, so rounding that to ₹872 throws away a real
// number; above a thousand rupees nobody quotes the paise.
export function price(p) {
  const v = Number(p) || 0;
  if (!v) return "";
  return v < 1000
    ? `₹${v.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`
    : `₹${Math.round(v).toLocaleString("en-IN")}`;
}

// 0.0238% is not four decimals of precision.
export function pct(v) {
  const n = Number(String(v ?? "").replace("%", ""));
  if (!n) return "";
  return n < 0.01 ? "under 0.01%" : `${n.toFixed(2)}%`;
}

export function dayLabel(iso) {
  if (!iso) return "";
  const dt = new Date(iso + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - dt) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return dt.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    weekday: "short",
  });
}

// Rows come back sorted by size, newest and oldest interleaved. Grouping them
// under a date gives the eye something to hold on to on a page three hundred
// rows long.
//
// Note this cannot walk the list looking for a change of day - the days are
// not adjacent. It buckets, then puts the buckets in date order, and the
// biggest-first order the API chose survives inside each one.
export function byDay(rows) {
  const buckets = new Map();
  for (const r of rows) {
    const k = r.day || "";
    if (!buckets.has(k)) buckets.set(k, []);
    buckets.get(k).push(r);
  }
  return [...buckets.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0))
    .map(([day, list]) => ({ day, rows: list }));
}
