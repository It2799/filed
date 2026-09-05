import { listEmails } from "../lib/store.js";
import { closeUsersConnection, subscribeUser } from "../lib/users.js";

const rows = await listEmails();
let migrated = 0;
let failed = 0;

for (const row of rows) {
  try {
    await subscribeUser({
      email: String(row.email || "").trim().toLowerCase(),
      phone: row.phone || null,
      source: row.source || row.via || "legacy-waitlist",
    });
    migrated += 1;
  } catch {
    failed += 1;
  }
}

console.log(JSON.stringify({ found: rows.length, migrated, failed }));
await closeUsersConnection();
if (failed) process.exitCode = 1;
