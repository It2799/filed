/** Schedule the approved one-time welcome email for every active Kit subscriber. */

import { MongoClient } from "mongodb";
import { WELCOME_EMAIL } from "../lib/notify.js";

const API = "https://api.kit.com/v4";
const SUBJECT = WELCOME_EMAIL.subject;

if (!process.env.KIT_API_KEY || !process.env.KIT_FROM_EMAIL || !process.env.MONGODB_URI) {
  throw new Error("Set KIT_API_KEY, KIT_FROM_EMAIL, and MONGODB_URI before running this tool.");
}
if (process.env.SEND_WELCOME_BROADCAST !== "1") {
  throw new Error("Set SEND_WELCOME_BROADCAST=1 to confirm this one-time bulk send.");
}

async function kit(path, options = {}) {
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        "X-Kit-Api-Key": process.env.KIT_API_KEY,
        "Content-Type": "application/json",
        ...options.headers,
      },
      signal: AbortSignal.timeout(20000),
    });
    if (response.ok) return response.json();
    const retryable = response.status === 429 || response.status >= 500;
    const detail = (await response.text()).replace(/\s+/g, " ").slice(0, 200);
    if (!retryable || attempt === 5) throw new Error(`Kit ${response.status}: ${detail}`);
    await new Promise((resolve) => setTimeout(resolve, attempt * 1500));
  }
}

async function listAll(path, key) {
  const rows = [];
  let after;
  do {
    const separator = path.includes("?") ? "&" : "?";
    const query = `${path}${separator}per_page=1000${after ? `&after=${encodeURIComponent(after)}` : ""}`;
    const page = await kit(query);
    rows.push(...(page[key] || []));
    after = page.pagination?.has_next_page ? page.pagination.end_cursor : undefined;
  } while (after);
  return rows;
}

const priorBroadcasts = await listAll("/broadcasts", "broadcasts");
const duplicate = priorBroadcasts.find(
  (broadcast) => broadcast.subject === SUBJECT && broadcast.status !== "aborted"
);
if (duplicate) {
  throw new Error(`Welcome broadcast already exists (broadcast ${duplicate.id}); refusing a duplicate send.`);
}

const subscribers = await listAll("/subscribers?status=active", "subscribers");
if (!subscribers.length) throw new Error("Kit has no active subscribers; nothing was scheduled.");

const sendAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();
const created = await kit("/broadcasts", {
  method: "POST",
  body: JSON.stringify({
    subject: SUBJECT,
    preview_text: "Your free Market Tide member access is ready.",
    description: "One-time welcome for existing Market Tide members",
    content: WELCOME_EMAIL.html,
    public: false,
    send_at: sendAt,
    email_address: process.env.KIT_FROM_EMAIL,
  }),
});

const broadcast = created.broadcast || created;
if (!broadcast?.id) throw new Error("Kit accepted the request but did not return a broadcast ID.");

console.log(JSON.stringify({
  broadcastId: broadcast.id,
  scheduledFor: broadcast.send_at || sendAt,
  activeKitAudience: subscribers.length,
  status: broadcast.status,
}));

let finalStatus = broadcast.status;
for (let check = 0; check < 80 && !["sent", "published", "completed", "aborted"].includes(finalStatus); check += 1) {
  await new Promise((resolve) => setTimeout(resolve, 15000));
  const result = await kit(`/broadcasts/${broadcast.id}/stats`);
  finalStatus = result.broadcast?.stats?.status || result.stats?.status || finalStatus;
}
if (finalStatus === "aborted") {
  throw new Error(`Kit aborted broadcast ${broadcast.id} before sending; no member records were marked.`);
}
if (!["sent", "published", "completed"].includes(finalStatus)) {
  throw new Error(`Broadcast ${broadcast.id} is still ${finalStatus}; no member records were marked yet.`);
}

const activeEmails = subscribers
  .map((subscriber) => subscriber.email_address?.trim().toLowerCase())
  .filter(Boolean);
const client = new MongoClient(process.env.MONGODB_URI);
await client.connect();
let marked = 0;
try {
  const result = await client.db(process.env.MONGODB_DB || "market_tide").collection("users").updateMany(
    { email: { $in: activeEmails } },
    { $set: { welcomeEmailSentAt: new Date(), welcomeEmailVia: `kit-broadcast:${broadcast.id}` } }
  );
  marked = result.modifiedCount;
} finally {
  await client.close();
}

console.log(JSON.stringify({
  broadcastId: broadcast.id,
  status: finalStatus,
  memberRecordsMarked: marked,
}));
