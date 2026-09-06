/** One-time copy of active MongoDB subscribers into Kit. */

import { MongoClient } from "mongodb";

if (!process.env.MONGODB_URI || !process.env.KIT_API_KEY) {
  throw new Error("Set MONGODB_URI and KIT_API_KEY before running this migration.");
}

const client = new MongoClient(process.env.MONGODB_URI);

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function upsert(email) {
  for (let attempt = 1; attempt <= 8; attempt += 1) {
    const response = await fetch("https://api.kit.com/v4/subscribers", {
      method: "POST",
      headers: { "X-Kit-Api-Key": process.env.KIT_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ email_address: email, state: "active" }),
    });
    if (response.ok) return;
    const retryable = response.status === 429 || response.status >= 500;
    const detail = (await response.text()).replace(/\s+/g, " ").slice(0, 100);
    if (!retryable || attempt === 8) throw new Error(`Kit ${response.status}: ${detail}`);
    const retryAfter = Number(response.headers.get("retry-after"));
    await wait(Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : attempt * 5000);
  }
}

await client.connect();
try {
  const users = client.db(process.env.MONGODB_DB || "market_tide").collection("users");
  const rows = await users.find(
    { briefSubscribed: true },
    { projection: { _id: 0, email: 1 } }
  ).toArray();
  let copied = 0;
  let failed = 0;
  for (const row of rows) {
    try {
      await upsert(row.email);
      copied += 1;
    } catch (error) {
      failed += 1;
      console.error(`Record ${copied + failed}/${rows.length} failed: ${error.message}`);
    }
    await wait(650);
    if ((copied + failed) % 50 === 0) console.log(`Processed ${copied + failed}/${rows.length}`);
  }
  console.log(`Kit sync complete: ${copied} accepted, ${failed} failed.`);
  if (failed) process.exitCode = 1;
} finally {
  await client.close();
}
