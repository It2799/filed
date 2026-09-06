import crypto from "node:crypto";

const COOKIE = "mt_admin_session";
const MAX_AGE = 60 * 60 * 12;

function secret() {
  return process.env.ADMIN_SESSION_SECRET || process.env.AUTH_SECRET || "";
}

export function adminConfigured() {
  return Boolean(process.env.ADMIN_PASSWORD && secret());
}

function digest(value) {
  return crypto.createHash("sha256").update(String(value || "")).digest();
}

export function correctAdminPassword(given) {
  if (!adminConfigured()) return false;
  return crypto.timingSafeEqual(digest(given), digest(process.env.ADMIN_PASSWORD));
}

function sign(payload) {
  return crypto.createHmac("sha256", secret()).update(payload).digest("base64url");
}

export function createAdminSession() {
  const payload = Buffer.from(JSON.stringify({ exp: Date.now() + MAX_AGE * 1000 }))
    .toString("base64url");
  return `${payload}.${sign(payload)}`;
}

function readCookie(request) {
  const header = request.headers.get("cookie") || "";
  const part = header.split(";").map((value) => value.trim())
    .find((value) => value.startsWith(`${COOKIE}=`));
  try {
    return part ? decodeURIComponent(part.slice(COOKIE.length + 1)) : "";
  } catch {
    return "";
  }
}

export function isAdmin(request) {
  if (!adminConfigured()) return false;
  const token = readCookie(request);
  const dot = token.lastIndexOf(".");
  if (dot < 1) return false;
  const payload = token.slice(0, dot);
  const signature = token.slice(dot + 1);
  if (!crypto.timingSafeEqual(digest(signature), digest(sign(payload)))) return false;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    return Number(data.exp) > Date.now();
  } catch {
    return false;
  }
}

function cookieParts(value, maxAge) {
  const parts = [
    `${COOKIE}=${encodeURIComponent(value)}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Strict",
    `Max-Age=${maxAge}`,
  ];
  if (process.env.NODE_ENV === "production") parts.push("Secure");
  return parts.join("; ");
}

export function adminCookie(token) {
  return cookieParts(token, MAX_AGE);
}

export function clearAdminCookie() {
  return cookieParts("", 0);
}

export function adminRateLimitKey(request) {
  const ip = request.headers.get("x-real-ip")
    || (request.headers.get("x-forwarded-for") || "unknown").split(",")[0].trim();
  return `mt:admin:attempt:${crypto.createHmac("sha256", secret() || "disabled").update(ip).digest("hex").slice(0, 24)}`;
}
