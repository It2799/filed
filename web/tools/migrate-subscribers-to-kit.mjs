/** One-time copy of active MongoDB subscribers into Kit. */

import { MongoClient } from "mongodb";

if (!process.env.MONGODB_URI || !process.env.KIT_API_KEY) {
  throw new Error("Set MONGODB_URI and KIT_API_KEY before running this migration.");
}

const client = new MongoClient(process.env.MONGODB_URI);
await client.connect();
try {
  const users = client.db(process.env.MONGODB_DB || "market_tide").collection("users");
  const rows = await users.find(
    { briefSubscribed: true },
    { projection: { _id: 0, email: 1 } }
  ).toArray();
  let copied = 0;
  for (const row of rows) {
    const response = await fetch("https://api.kit.com/v4/subscribers", {
      method: "POST",
      headers: { "X-Kit-Api-Key": process.env.KIT_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ email_address: row.email, state: "active" }),
    });
    if (!response.ok) throw new Error(`Kit ${response.status} for ${row.email}: ${(await response.text()).slice(0, 120)}`);
    copied += 1;
    if (copied % 50 === 0) console.log(`Copied ${copied}/${rows.length}`);
  }
  console.log(`Copied ${copied} active subscriber(s) to Kit.`);
} finally {
  await client.close();
}
