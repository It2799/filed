/** First-party, privacy-limited session analytics for the private admin view. */

import { MongoClient } from "mongodb";

const RETENTION_SECONDS = 60 * 60 * 24 * 90;
let clientPromise;
let indexesReady;

function dateInIndia(value = new Date()) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function validDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""));
}

async function collection() {
  if (!process.env.MONGODB_URI) return null;
  if (!clientPromise) {
    clientPromise = new MongoClient(process.env.MONGODB_URI, {
      serverSelectionTimeoutMS: 6000,
    }).connect();
  }
  const client = await clientPromise;
  const sessions = client
    .db(process.env.MONGODB_DB || "market_tide")
    .collection("visit_sessions");
  if (!indexesReady) {
    indexesReady = Promise.all([
      sessions.createIndex({ sessionKey: 1 }, { unique: true }),
      sessions.createIndex({ date: 1, lastSeenAt: -1 }),
      sessions.createIndex({ email: 1, date: 1 }),
      sessions.createIndex({ lastSeenAt: 1 }, { expireAfterSeconds: RETENTION_SECONDS }),
    ]);
  }
  await indexesReady;
  return sessions;
}

export async function recordEngagement({ visitorId, sessionId, email, path, event }) {
  const sessions = await collection();
  if (!sessions || !visitorId || !sessionId) return false;

  const now = new Date();
  const date = dateInIndia(now);
  const sessionKey = `${sessionId}:${date}`;
  const existing = await sessions.findOne(
    { sessionKey },
    { projection: { _id: 0, lastSeenAt: 1 } }
  );
  const elapsed = existing?.lastSeenAt && event !== "resume"
    ? Math.max(0, Math.min(90, Math.round((now - new Date(existing.lastSeenAt)) / 1000)))
    : 0;
  const pageView = event === "pageview" ? 1 : 0;

  await sessions.updateOne(
    { sessionKey },
    {
      $set: {
        visitorId,
        ...(email ? { email } : {}),
        date,
        lastSeenAt: now,
      },
      $setOnInsert: { sessionKey, sessionId, startedAt: now },
      $inc: { durationSeconds: elapsed, pageViews: pageView },
      ...(pageView && path ? { $addToSet: { pages: path } } : {}),
    },
    { upsert: true }
  );
  return true;
}

export async function dailyEngagement(requestedDate) {
  const sessions = await collection();
  const date = validDate(requestedDate) ? requestedDate : dateInIndia();
  if (!sessions) return empty(date);

  const records = await sessions.find(
    { date },
    {
      projection: {
        _id: 0,
        email: 1,
        visitorId: 1,
        startedAt: 1,
        lastSeenAt: 1,
        durationSeconds: 1,
        pageViews: 1,
        pages: 1,
      },
    }
  ).limit(10000).toArray();

  const visitors = new Map();
  const pageCounts = {};
  let totalSeconds = 0;
  let totalPageViews = 0;

  for (const record of records) {
    const key = record.email || `browser:${record.visitorId}`;
    if (!visitors.has(key)) {
      visitors.set(key, {
        key,
        email: record.email || null,
        visitorId: record.visitorId,
        sessions: 0,
        pageViews: 0,
        durationSeconds: 0,
        longestSessionSeconds: 0,
        firstSeenAt: null,
        lastSeenAt: null,
        pages: new Set(),
        sessionDetails: [],
      });
    }
    const visitor = visitors.get(key);
    const seconds = Math.max(0, Number(record.durationSeconds || 0));
    const views = Math.max(0, Number(record.pageViews || 0));
    visitor.sessions += 1;
    visitor.pageViews += views;
    visitor.durationSeconds += seconds;
    visitor.longestSessionSeconds = Math.max(visitor.longestSessionSeconds, seconds);
    const started = record.startedAt ? new Date(record.startedAt).toISOString() : null;
    const seen = record.lastSeenAt ? new Date(record.lastSeenAt).toISOString() : null;
    if (started && (!visitor.firstSeenAt || started < visitor.firstSeenAt)) visitor.firstSeenAt = started;
    if (seen && (!visitor.lastSeenAt || seen > visitor.lastSeenAt)) visitor.lastSeenAt = seen;
    visitor.sessionDetails.push({
      startedAt: started,
      lastSeenAt: seen,
      durationSeconds: seconds,
      pageViews: views,
      pages: record.pages || [],
    });
    for (const page of record.pages || []) {
      visitor.pages.add(page);
      pageCounts[page] = (pageCounts[page] || 0) + 1;
    }
    totalSeconds += seconds;
    totalPageViews += views;
  }

  const rows = [...visitors.values()].map((visitor) => ({
    ...visitor,
    averageSessionSeconds: visitor.sessions
      ? Math.round(visitor.durationSeconds / visitor.sessions)
      : 0,
    pages: [...visitor.pages],
    sessionDetails: visitor.sessionDetails.sort((a, b) =>
      String(a.startedAt || "").localeCompare(String(b.startedAt || ""))
    ),
  })).sort((a, b) => b.durationSeconds - a.durationSeconds || b.pageViews - a.pageViews);

  return {
    date,
    totals: {
      visitors: rows.length,
      identifiedVisitors: rows.filter((row) => row.email).length,
      sessions: records.length,
      pageViews: totalPageViews,
      durationSeconds: totalSeconds,
      averageSessionSeconds: records.length ? Math.round(totalSeconds / records.length) : 0,
    },
    topPages: Object.entries(pageCounts)
      .map(([path, sessions]) => ({ path, sessions }))
      .sort((a, b) => b.sessions - a.sessions)
      .slice(0, 10),
    visitors: rows,
  };
}

function empty(date) {
  return {
    date,
    totals: {
      visitors: 0,
      identifiedVisitors: 0,
      sessions: 0,
      pageViews: 0,
      durationSeconds: 0,
      averageSessionSeconds: 0,
    },
    topPages: [],
    visitors: [],
  };
}
