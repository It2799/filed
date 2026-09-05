import { emailConfigured, sendContactMessage } from "../../../lib/notify";
import crypto from "node:crypto";

export const runtime = "nodejs";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

async function tooMany(request) {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return false;
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  const key = `mt:contact:${crypto.createHash("sha256").update(ip).digest("hex").slice(0, 20)}`;
  const call = async (command) => {
    const response = await fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(command),
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`Redis ${response.status}`);
    return (await response.json()).result;
  };
  try {
    const count = Number(await call(["INCR", key]));
    if (count === 1) await call(["EXPIRE", key, "3600"]);
    return count > 5;
  } catch (error) {
    console.error("[contact] rate limit unavailable:", error.message || error);
    return false;
  }
}

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Send a valid message." }, { status: 400 });
  }
  if (body.company) return Response.json({ ok: true });
  if (await tooMany(request)) {
    return Response.json({ error: "Too many messages. Please try again later." }, { status: 429 });
  }

  const name = String(body.name || "").trim();
  const email = String(body.email || "").trim().toLowerCase();
  const message = String(body.message || "").trim();
  if (!name || name.length > 80 || !EMAIL.test(email) || email.length > 254 || message.length < 10 || message.length > 3000) {
    return Response.json({ error: "Check your name, email and message, then try again." }, { status: 400 });
  }
  if (!emailConfigured()) {
    return Response.json({ error: "Email is not connected yet. Please use the email address above." }, { status: 503 });
  }
  try {
    await sendContactMessage({ name, email, message });
    return Response.json({ ok: true });
  } catch (error) {
    console.error("[contact] email failed:", error.message || error);
    return Response.json({ error: "Could not send your message just now. Please try again." }, { status: 502 });
  }
}
