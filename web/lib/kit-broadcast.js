/** Schedule the published Daily Brief to every active subscriber in Kit. */

const API = "https://api.kit.com/v4";

function prettyDay(day) {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(`${day}T00:00:00+05:30`));
}

export function kitBroadcastConfigured() {
  return Boolean(process.env.KIT_API_KEY && process.env.KIT_FROM_EMAIL);
}

export async function scheduleDailyBriefBroadcast({ day, sendAt }) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(day || ""))) throw new Error("Invalid brief date.");
  if (!kitBroadcastConfigured()) throw new Error("KIT_API_KEY or KIT_FROM_EMAIL is not configured.");

  const dayText = prettyDay(day);
  const link = `https://markettide.in/brief/${day}`;
  const response = await fetch(`${API}/broadcasts`, {
    method: "POST",
    headers: {
      "X-Kit-Api-Key": process.env.KIT_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      subject: `The morning brief - ${dayText}`,
      preview_text: "Today’s important NSE and BSE filings, explained in plain English.",
      description: `Market Tide Daily Brief for ${dayText}`,
      content:
        `<p>The morning brief for <strong>${dayText}</strong> is ready.</p>`
        + "<p>We reviewed the latest NSE and BSE announcements and selected the filings that matter.</p>"
        + `<p><a href="${link}">Read today’s Daily Brief</a></p>`
        + "<p>Market Tide summarises public exchange filings. It is not investment advice. Always read the original filing before acting.</p>",
      public: false,
      published_at: new Date().toISOString(),
      send_at: sendAt,
      email_address: process.env.KIT_FROM_EMAIL,
    }),
    cache: "no-store",
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) {
    const detail = (await response.text()).replace(/\s+/g, " ").slice(0, 240);
    throw new Error(`Kit ${response.status}: ${detail}`);
  }
  const body = await response.json();
  const broadcast = body.broadcast || body;
  if (!broadcast?.id) throw new Error("Kit accepted the request without returning a broadcast ID.");
  return {
    id: broadcast.id,
    status: broadcast.status || "scheduled",
    sendAt: broadcast.send_at || sendAt,
  };
}
