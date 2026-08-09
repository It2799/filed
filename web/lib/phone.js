/**
 * Indian mobile numbers, tidied into one shape: +91XXXXXXXXXX
 *
 * People type these every possible way - "98765 43210", "+91-9876543210",
 * "09876543210", "919876543210". All of those are the same person, so we
 * normalise before storing, otherwise the same number joins the list twice.
 */

export function normalisePhone(raw) {
  if (!raw) return null;

  let d = String(raw).replace(/\D/g, "");

  if (d.length === 12 && d.startsWith("91")) d = d.slice(2);   // 91XXXXXXXXXX
  else if (d.length === 11 && d.startsWith("0")) d = d.slice(1); // 0XXXXXXXXXX
  else if (d.length === 13 && d.startsWith("091")) d = d.slice(3);

  // Indian mobiles are 10 digits and start 6, 7, 8 or 9.
  if (!/^[6-9]\d{9}$/.test(d)) return null;

  return "+91" + d;
}
