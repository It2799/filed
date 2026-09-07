/** Export MongoDB email addresses for a one-time CSV import. */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { MongoClient } from "mongodb";

if (!process.env.MONGODB_URI) throw new Error("Set MONGODB_URI before exporting.");

const allowedSources = new Set(
  String(process.env.SUBSTACK_IMPORT_SOURCES || "brief")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean)
);
const exportAllEmails = process.argv.includes("--all");
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const outputDir = path.resolve(process.cwd(), "exports");
const outputPath = path.join(
  outputDir,
  exportAllEmails ? "substack-all-emails.csv" : "substack-subscribers.csv"
);

const client = new MongoClient(process.env.MONGODB_URI, { serverSelectionTimeoutMS: 30000 });
await client.connect();
let rows;
try {
  rows = await client
    .db(process.env.MONGODB_DB || "market_tide")
    .collection("users")
    .find(
      exportAllEmails
        ? { email: { $type: "string" } }
        : { briefSubscribed: true, briefSubscriptionSource: { $in: [...allowedSources] } },
      { projection: { _id: 0, email: 1 } }
    )
    .toArray();
} finally {
  await client.close();
}

const emails = [...new Set(rows
  .map((row) => String(row.email || "").trim().toLowerCase())
  .filter((email) => emailPattern.test(email) && email.length <= 254))]
  .sort();

await mkdir(outputDir, { recursive: true });
await writeFile(outputPath, `email\n${emails.join("\n")}\n`, "utf8");
console.log(JSON.stringify({
  exported: emails.length,
  mode: exportAllEmails ? "all-valid-emails" : "confirmed-subscribers",
  ...(exportAllEmails ? {} : { sources: [...allowedSources] }),
  outputPath,
}, null, 2));
