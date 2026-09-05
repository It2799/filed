/** MongoDB-backed reader profiles. OTPs remain short-lived in Redis; MongoDB
 * stores only the durable details we need between sign-ins. */

import { MongoClient } from "mongodb";

let clientPromise;
let indexesReady;

export function configured() {
  return Boolean(process.env.MONGODB_URI);
}

async function collection() {
  if (!configured()) throw new Error("MONGODB_URI is not configured");
  if (!clientPromise) {
    const client = new MongoClient(process.env.MONGODB_URI, {
      serverSelectionTimeoutMS: 6000,
    });
    clientPromise = client.connect();
  }
  const client = await clientPromise;
  const users = client.db(process.env.MONGODB_DB || "market_tide").collection("users");
  if (!indexesReady) indexesReady = users.createIndex({ email: 1 }, { unique: true });
  await indexesReady;
  return users;
}

export async function findByEmail(email) {
  const users = await collection();
  return users.findOne(
    { email },
    { projection: { _id: 0, email: 1, phone: 1, emailVerifiedAt: 1 } }
  );
}

export async function saveVerifiedUser({ email, phone }) {
  const users = await collection();
  const now = new Date();
  const before = await users.findOne(
    { email },
    { projection: { _id: 0, emailVerifiedAt: 1 } }
  );
  await users.updateOne(
    { email },
    {
      $set: {
        email,
        ...(phone ? { phone } : {}),
        emailVerifiedAt: now,
        lastLoginAt: now,
      },
      $setOnInsert: { createdAt: now },
    },
    { upsert: true }
  );
  return { email, phone: phone || null, firstVerification: !before?.emailVerifiedAt };
}

/** Mark an email as subscribed without creating duplicate users. */
export async function subscribeUser({ email, phone = null, source = "brief" }) {
  const users = await collection();
  const now = new Date();
  const current = await users.findOne(
    { email },
    { projection: { _id: 0, briefSubscribed: 1 } }
  );
  const alreadySubscribed = Boolean(current?.briefSubscribed);

  await users.updateOne(
    { email },
    {
      $set: {
        email,
        ...(phone ? { phone } : {}),
        briefSubscribed: true,
        briefSubscriptionSource: source,
        briefSubscriptionUpdatedAt: now,
        updatedAt: now,
        ...(!alreadySubscribed ? { briefSubscribedAt: now } : {}),
      },
      $setOnInsert: { createdAt: now },
    },
    { upsert: true }
  );

  return { email, alreadySubscribed };
}

export async function closeUsersConnection() {
  if (!clientPromise) return;
  const client = await clientPromise;
  await client.close();
  clientPromise = undefined;
  indexesReady = undefined;
}
