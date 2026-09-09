import { createHmac, timingSafeEqual } from "node:crypto";

const PREFIX = "market-tide-brief";

function signingSecret() {
  return process.env.AUTH_SECRET || "";
}

export function briefAccessConfigured() {
  return Boolean(signingSecret());
}

export function briefAccessToken(day) {
  const secret = signingSecret();
  if (!secret) throw new Error("AUTH_SECRET is not configured.");
  return createHmac("sha256", secret).update(`${PREFIX}:${day}`).digest("base64url");
}

export function validBriefAccess(day, candidate) {
  if (!candidate || !briefAccessConfigured()) return false;
  const expected = briefAccessToken(day);
  const supplied = String(candidate);
  if (supplied.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(supplied), Buffer.from(expected));
}

export function directBriefPdfUrl(day) {
  const token = briefAccessToken(day);
  return `https://markettide.in/brief/${day}.pdf?download=1&access=${encodeURIComponent(token)}`;
}
