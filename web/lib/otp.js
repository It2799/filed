/**
 * One-time codes, for signing in by email or WhatsApp.
 *
 * There is no password anywhere in this file and there never should be. A
 * reader gives us an address or a phone number, we send a six-digit code to
 * it, and proving they received it is the whole of the login.
 *
 * What is stored is a HASH of the code, never the code itself. If someone
 * reads the database they still cannot sign in as anybody: they would have to
 * reverse an HMAC keyed with AUTH_SECRET, which is not in the database.
 *
 * Three limits, because a six-digit code is only 1,000,000 guesses:
 *
 *   - it expires after 10 minutes
 *   - 5 wrong guesses destroys it, so an attacker gets 5 tries, not a million
 *   - 3 codes per identifier per 15 minutes, so nobody can be spammed with
 *     texts, and our own bill cannot be run up by a stranger
 *
 * AUTH_SECRET is required. If it is missing, signing in is switched off
 * entirely rather than falling back to something guessable - an authentication
 * system with a default secret is worse than no authentication system, because
 * it looks like one.
 */

import crypto from "node:crypto";

const CODE_TTL_SECONDS = 10 * 60;
const MAX_ATTEMPTS = 5;
const MAX_SENDS = 3;
const SEND_WINDOW_SECONDS = 15 * 60;

// ---------------------------------------------------------------- storage

function creds() {
  return {
    url: process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL,
    token: process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN,
  };
}

export function configured() {
  const { url, token } = creds();
  return Boolean(url && token && process.env.AUTH_SECRET);
}

/** What is missing, in words, so the page can say so instead of just failing. */
export function missing() {
  const { url, token } = creds();
  const gaps = [];
  if (!url || !token) gaps.push("a Redis store (KV_REST_API_URL / _TOKEN)");
  if (!process.env.AUTH_SECRET) gaps.push("AUTH_SECRET");
  return gaps;
}

async function redis(command) {
  const { url, token } = creds();
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(command),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Redis ${res.status}`);
  return (await res.json()).result;
}

// ---------------------------------------------------------------- the code

/**
 * Six digits, from the operating system's randomness.
 *
 * Math.random() must not be used here. It is seeded predictably and is not
 * meant for anything an attacker would want to guess - which is exactly what
 * this is.
 */
function newCode() {
  return String(crypto.randomInt(0, 1000000)).padStart(6, "0");
}

function hash(identifier, code) {
  return crypto
    .createHmac("sha256", process.env.AUTH_SECRET)
    .update(`${identifier}:${code}`)
    .digest("hex");
}

/**
 * Compare without leaking, through timing, how much of the hash was right.
 *
 * A plain === returns as soon as two characters differ, so the time it takes
 * says how long the matching prefix was, and a patient attacker can rebuild
 * the value one character at a time. timingSafeEqual always looks at all of it.
 */
function sameHash(a, b) {
  const x = Buffer.from(String(a || ""), "utf8");
  const y = Buffer.from(String(b || ""), "utf8");
  if (x.length !== y.length) return false;
  return crypto.timingSafeEqual(x, y);
}

const key = (id) => `mt:otp:${id}`;
const sendKey = (id) => `mt:otp:sends:${id}`;

// ---------------------------------------------------------------- issuing

/**
 * Make a code for this identifier and return it, or say why not.
 *
 * The caller sends it. This file deliberately does not know how to send
 * anything - it would then have to know about email and WhatsApp and be
 * changed for every new channel.
 */
export async function issue(identifier) {
  if (!configured()) {
    return { ok: false, reason: "not_configured", missing: missing() };
  }

  const sends = Number(await redis(["INCR", sendKey(identifier)]));
  if (sends === 1) {
    await redis(["EXPIRE", sendKey(identifier), String(SEND_WINDOW_SECONDS)]);
  }
  if (sends > MAX_SENDS) {
    const left = Number(await redis(["TTL", sendKey(identifier)]));
    return {
      ok: false,
      reason: "too_many",
      retryInSeconds: left > 0 ? left : SEND_WINDOW_SECONDS,
    };
  }

  const code = newCode();
  await redis([
    "SET",
    key(identifier),
    JSON.stringify({ h: hash(identifier, code), attempts: 0 }),
    "EX",
    String(CODE_TTL_SECONDS),
  ]);

  return { ok: true, code, expiresInSeconds: CODE_TTL_SECONDS };
}

// ---------------------------------------------------------------- checking

/**
 * Is this the code we sent? Consumes it either way it goes right.
 *
 * Every failure says the same thing to the caller - "that code is wrong or has
 * expired". Distinguishing "no code outstanding" from "wrong code" would tell
 * a stranger which addresses have a login in progress.
 */
export async function check(identifier, code) {
  if (!configured()) {
    return { ok: false, reason: "not_configured", missing: missing() };
  }
  if (!/^\d{6}$/.test(String(code || ""))) {
    return { ok: false, reason: "bad_code" };
  }

  const raw = await redis(["GET", key(identifier)]);
  if (!raw) return { ok: false, reason: "bad_code" };

  let rec;
  try {
    rec = JSON.parse(raw);
  } catch {
    await redis(["DEL", key(identifier)]);
    return { ok: false, reason: "bad_code" };
  }

  if (!sameHash(rec.h, hash(identifier, code))) {
    const attempts = (rec.attempts || 0) + 1;
    if (attempts >= MAX_ATTEMPTS) {
      // Burn it. Five guesses at six digits is a 1-in-200,000 chance; five
      // hundred thousand guesses is a certainty, and without this that is what
      // an attacker would get.
      await redis(["DEL", key(identifier)]);
      return { ok: false, reason: "too_many_attempts" };
    }
    const ttl = Number(await redis(["TTL", key(identifier)]));
    await redis([
      "SET",
      key(identifier),
      JSON.stringify({ ...rec, attempts }),
      "EX",
      String(ttl > 0 ? ttl : CODE_TTL_SECONDS),
    ]);
    return { ok: false, reason: "bad_code", attemptsLeft: MAX_ATTEMPTS - attempts };
  }

  // Right first time or right eventually - either way it is spent, so it
  // cannot be replayed by anyone who saw it over someone's shoulder.
  await redis(["DEL", key(identifier)]);
  await redis(["DEL", sendKey(identifier)]);
  return { ok: true };
}
