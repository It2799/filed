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
