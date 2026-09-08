"use client";

import { useEffect, useMemo, useState } from "react";

const number = (value) => Number(value || 0).toLocaleString("en-IN");

function when(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function clock(value) {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString("en-IN", {
    hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata",
  });
}

function duration(value) {
  const seconds = Math.max(0, Number(value || 0));
  if (seconds < 60) return seconds ? `${seconds}s` : "<1m";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function todayIndia() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export default function AdminDashboard() {
  const [status, setStatus] = useState("checking");
  const [configured, setConfigured] = useState(true);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [query, setQuery] = useState("");
  const [visibleLimit, setVisibleLimit] = useState(100);
  const [selectedDate, setSelectedDate] = useState(todayIndia);

  async function load(date = selectedDate) {
    setStatus("loading");
    const response = await fetch(`/api/admin/stats?date=${encodeURIComponent(date)}`, { cache: "no-store" });
    if (response.status === 401) {
      setStatus("locked");
      return;
    }
    const body = await response.json();
    if (!response.ok) {
      setError(body.error || "Could not load admin data.");
      setStatus("error");
      return;
    }
    setData(body);
    setStatus("ready");
  }

  useEffect(() => {
    fetch("/api/admin/auth", { cache: "no-store" })
      .then((response) => response.json())
      .then((body) => {
        setConfigured(Boolean(body.configured));
        if (body.authenticated) load();
        else setStatus("locked");
      })
      .catch(() => {
        setError("Could not reach the admin service.");
        setStatus("error");
      });
  }, []);

  async function login(event) {
    event.preventDefault();
    setError("");
    setStatus("signing-in");
    const response = await fetch("/api/admin/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const body = await response.json();
    if (!response.ok) {
      setError(body.error || "Could not sign in.");
      setStatus("locked");
      return;
    }
    setPassword("");
    await load();
  }

  async function logout() {
    await fetch("/api/admin/auth", { method: "DELETE" });
    setData(null);
    setStatus("locked");
  }

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return data?.members || [];
    return (data?.members || []).filter((member) =>
      [member.email, member.phone, ...(member.sources || [])].join(" ").toLowerCase().includes(needle)
    );
  }, [data, query]);

  if (status !== "ready") {
    return (
      <main className="admin-lock">
        <section className="admin-login">
          <div className="admin-brand"><span className="dot" /> Market Tide</div>
          <p className="admin-kicker">Private operations</p>
          <h1>Admin dashboard</h1>
          {status === "checking" || status === "loading" ? (
            <p className="admin-muted">Checking secure access…</p>
          ) : !configured ? (
            <p className="admin-alert">Admin access is disabled. Add ADMIN_PASSWORD in Vercel.</p>
          ) : (
            <form onSubmit={login}>
              <label htmlFor="admin-password">Password</label>
              <input
                id="admin-password"
                type="password"
                autoFocus
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button disabled={status === "signing-in"}>
                {status === "signing-in" ? "Opening…" : "Open dashboard"}
              </button>
            </form>
          )}
          {error && <p className="admin-alert">{error}</p>}
          <a className="admin-home" href="/">Return to Market Tide</a>
        </section>
      </main>
    );
  }

  const cards = [
    ["Unique members", data.totals.members],
    ["Verified logins", data.totals.verified],
    ["Newsletter", data.totals.subscribed],
    ["Phone numbers", data.totals.withPhone],
    ["Unverified", data.totals.members - data.totals.verified],
    ["Live now", data.traffic.live],
    ["Unique visitors", data.traffic.unique],
    ["Total visits", data.traffic.total],
    ["Visitors on date", data.engagement.totals.visitors],
    ["Sessions on date", data.engagement.totals.sessions],
    ["Page views on date", data.engagement.totals.pageViews],
    ["Time on site", duration(data.engagement.totals.durationSeconds)],
  ];

  return (
    <main className="admin-page">
      <header className="admin-top">
        <div>
          <div className="admin-brand"><span className="dot" /> Market Tide</div>
          <h1>Operations dashboard</h1>
          <p>Members, acquisition sources and website traffic in one place.</p>
        </div>
        <div className="admin-top-actions">
          <button onClick={() => load(selectedDate)}>Refresh</button>
          <button className="admin-quiet" onClick={logout}>Log out</button>
        </div>
      </header>

      <section className="admin-cards">
        {cards.map(([label, value]) => (
          <article key={label}><span>{label}</span><b>{typeof value === "number" ? number(value) : value}</b></article>
        ))}
      </section>

      <section className="admin-panel">
        <div className="admin-panel-head admin-engagement-head">
          <div>
            <p className="admin-kicker">Engagement</p>
            <h2>Daily visitor sessions</h2>
          </div>
          <label className="admin-date">
            <span>Choose date</span>
            <input
              type="date"
              value={selectedDate}
              max={todayIndia()}
              onChange={(event) => {
                const next = event.target.value;
                setSelectedDate(next);
                if (next) load(next);
              }}
            />
          </label>
        </div>
        <p className="admin-engagement-summary">
          {number(data.engagement.totals.identifiedVisitors)} signed-in visitors · average session {duration(data.engagement.totals.averageSessionSeconds)}
        </p>
        <div className="admin-top-pages">
          {data.engagement.topPages.map((page) => (
            <span key={page.path}><b>{page.path}</b> {number(page.sessions)} sessions</span>
          ))}
        </div>
        <div className="admin-table-wrap">
          <table className="admin-table admin-engagement-table">
            <thead>
              <tr><th>Visitor</th><th>Visits</th><th>Each session</th><th>Page views</th><th>Whole-day time</th><th>Average</th><th>Longest</th><th>First / last seen</th><th>Pages</th></tr>
            </thead>
            <tbody>
              {data.engagement.visitors.map((visitor) => (
                <tr key={visitor.key}>
                  <td><b>{visitor.email || `Anonymous · ${visitor.visitorId.slice(0, 8)}`}</b></td>
                  <td>{number(visitor.sessions)}</td>
                  <td>
                    <div className="admin-session-times">
                      {visitor.sessionDetails.map((session, index) => (
                        <span key={`${session.startedAt}:${index}`}>{index + 1}. {duration(session.durationSeconds)}</span>
                      ))}
                    </div>
                  </td>
                  <td>{number(visitor.pageViews)}</td>
                  <td>{duration(visitor.durationSeconds)}</td>
                  <td>{duration(visitor.averageSessionSeconds)}</td>
                  <td>{duration(visitor.longestSessionSeconds)}</td>
                  <td>{clock(visitor.firstSeenAt)} / {clock(visitor.lastSeenAt)}</td>
                  <td><div className="admin-tags">{visitor.pages.map((page) => <span key={page}>{page}</span>)}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.engagement.visitors.length && (
            <p className="admin-empty">No tracked sessions for this date.</p>
          )}
        </div>
      </section>

      <section className="admin-panel">
        <div className="admin-panel-head">
          <div><p className="admin-kicker">Acquisition</p><h2>Where members came from</h2></div>
          <span>One member can belong to more than one source.</span>
        </div>
        <div className="admin-sources">
          {Object.entries(data.sourceCounts).sort((a, b) => b[1] - a[1]).map(([source, count]) => (
            <div key={source}><span>{source}</span><b>{number(count)}</b></div>
          ))}
        </div>
      </section>

      <section className="admin-panel">
        <div className="admin-panel-head admin-members-head">
          <div><p className="admin-kicker">Directory</p><h2>All members</h2></div>
          <input
            type="search"
            placeholder="Search email, phone or source…"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setVisibleLimit(100); }}
          />
        </div>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead><tr><th>Member</th><th>Phone</th><th>Sources</th><th>Status</th><th>Joined</th><th>Last activity</th></tr></thead>
            <tbody>
              {shown.slice(0, visibleLimit).map((member) => (
                <tr key={member.email}>
                  <td><b>{member.email}</b></td>
                  <td>{member.phone || "—"}</td>
                  <td><div className="admin-tags">{member.sources.map((source) => <span key={source}>{source}</span>)}</div></td>
                  <td>{member.verified ? "Verified" : "Subscriber"}</td>
                  <td>{when(member.createdAt)}</td>
                  <td>{when(member.lastActivityAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!shown.length && <p className="admin-empty">No members match that search.</p>}
        </div>
        {shown.length > visibleLimit && (
          <button className="admin-more" onClick={() => setVisibleLimit((value) => value + 100)}>
            Show 100 more · {number(shown.length - visibleLimit)} remaining
          </button>
        )}
      </section>
      <p className="admin-updated">Updated {when(data.generatedAt)} · Sensitive member data · Do not share this page.</p>
    </main>
  );
}
