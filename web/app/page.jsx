"use client";

import { useEffect, useMemo, useState } from "react";

const SITE = {
  name: "Market Tide",
  phoneDisplay: "+91 82004 40146",
  phoneDigits: "918200440146",
  email: "market.tide27@gmail.com",
  newsletterLink: "https://chat.whatsapp.com/B9cZ0FnmUFxKGUuXaqXG4H?s=cl&p=a&ilr=1",

  // Combined audience across the WhatsApp newsletter and the website list.
  // The website form count alone is served live at /api/waitlist; this is the
  // wider figure you keep by hand, so update it as the group grows.
  readers: "500+",
};

const impactClass = (i) =>
  i === "Positive" ? "pos" : i === "Negative" ? "neg" : "neu";

const prettyDay = (iso) =>
  iso
    ? new Date(iso + "T00:00:00").toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
      })
    : "";

export default function Home() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [scope, setScope] = useState("important");
  const [loading, setLoading] = useState(true);
  const [tag, setTag] = useState(null);
  const [day, setDay] = useState(null);
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(40);

  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [formState, setFormState] = useState("idle");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    let dead = false;
    setLoading(true);
    fetch(`/api/announcements?scope=${scope}`)
      .then((r) => r.json())
      .then((d) => {
        if (dead) return;
        if (d.error) setError(d.error);
        else {
          setData(d);
          setError("");
        }
      })
      .catch(() => !dead && setError("Couldn't load the filings. Please refresh."))
      .finally(() => !dead && setLoading(false));
    return () => {
      dead = true;
    };
  }, [scope]);

  useEffect(() => {
    setLimit(40);
  }, [scope, tag, day, q]);

  const items = data?.items || [];

  const tags = useMemo(
    () => Object.entries(data?.tagCounts || {}).sort((a, b) => b[1] - a[1]),
    [data]
  );

  const shown = useMemo(() => {
    const n = q.toLowerCase().trim();
    return items.filter(
      (it) =>
        (!tag || it.tag === tag) &&
        (!day || it.day === day) &&
        (!n ||
          `${it.company} ${it.ticker} ${it.headline} ${it.summary}`
            .toLowerCase()
            .includes(n))
    );
  }, [items, tag, day, q]);

  const exportUrl = () => {
    const p = new URLSearchParams();
    if (tag) p.set("tag", tag);
    if (day) p.set("day", day);
    if (scope === "all") p.set("scope", "all");
    const qs = p.toString();
    return "/api/announcements/export" + (qs ? `?${qs}` : "");
  };

  async function submit(e) {
    e.preventDefault();
    if (formState === "sending") return;
    setFormState("sending");
    setFormError("");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, phone, company, source: "home" }),
      });
      const d = await res.json();
      if (!res.ok) {
        setFormError(d.error || "Please try again.");
        setFormState("idle");
        return;
      }
      setFormState("done");
    } catch {
      setFormError("Couldn't reach the server. Please try again.");
      setFormState("idle");
    }
  }

  const scanned = data?.meta?.scanned;
  const summarised = data?.summarised || 0;

  return (
    <div className="wrap">
      <div className="brand">
        <span className="dot" /> {SITE.name}
        <span className="pill">Free · updated every evening</span>
      </div>

      <header className="intro">
        <h1>The filings that actually matter</h1>
        <p className="intro-lede">
          Every trading day, companies file hundreds of announcements with NSE
          and BSE. <strong>We read all of them</strong> and write a plain-English
          summary of the ones worth your time. The rest — trading window notices,
          newspaper clippings, duplicate certificates — we throw away.
        </p>

        {scanned ? (
          <div className="howitworks">
            <div className="hiw">
              <b>{Number(scanned).toLocaleString("en-IN")}</b>
              <span>filed in the last 7 days</span>
            </div>
            <div className="hiw-arrow" aria-hidden="true">
              →
            </div>
            <div className="hiw">
              <b>All of them</b>
              <span>read and checked by us</span>
            </div>
            <div className="hiw-arrow" aria-hidden="true">
              →
            </div>
            <div className="hiw done">
              <b>{summarised}</b>
              <span>relevant enough to summarise</span>
            </div>
          </div>
        ) : null}

        <p className="intro-note">
          Free to read. Nothing to sign up for. Every card links to the original
          PDF so you can check it yourself.
        </p>
      </header>

      <div className="controls">
        <div className="tabs">
          <button
            className={`tab ${scope === "important" ? "on" : ""}`}
            onClick={() => {
              setScope("important");
              setTag(null);
            }}
          >
            Worth reading
          </button>
          <button
            className={`tab ${scope === "all" ? "on" : ""}`}
            onClick={() => {
              setScope("all");
              setTag(null);
            }}
          >
            Everything filed
          </button>
          {loading && <span className="tab-loading">loading…</span>}
        </div>

        <div className="control-row">
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search a company…"
            aria-label="Search"
          />
          <a className="dl-btn" href={exportUrl()} download>
            <XlsIcon /> Excel
          </a>
        </div>

        <div className="chips">
          <button className={`chip ${!day ? "on" : ""}`} onClick={() => setDay(null)}>
            All days
          </button>
          {(data?.days || []).map((d) => (
            <button
              key={d}
              className={`chip ${day === d ? "on" : ""}`}
              onClick={() => setDay(day === d ? null : d)}
            >
              {prettyDay(d)}
            </button>
          ))}
        </div>

        {tags.length > 0 && (
          <div className="chips tags">
            <button className={`chip ${!tag ? "on" : ""}`} onClick={() => setTag(null)}>
              Every type
            </button>
            {tags.map(([t, n]) => (
              <button
                key={t}
                className={`chip ${tag === t ? "on" : ""}`}
                onClick={() => setTag(tag === t ? null : t)}
              >
                {t} {n}
              </button>
            ))}
          </div>
        )}
      </div>

      {error ? (
        <div className="empty">{error}</div>
      ) : !data ? (
        <div className="empty">Loading the last 7 days…</div>
      ) : shown.length === 0 ? (
        <div className="empty">Nothing matches that filter.</div>
      ) : (
        <>
          {shown.slice(0, limit).map((it) => (
            <article className="card" key={it.id}>
              <div className="card-top">
                <div>
                  <div className="co">
                    {it.company}{" "}
                    {it.ticker && <span className="meta">{it.ticker}</span>}
                  </div>
                  <div className="meta">
                    {it.exchange} · {it.category} · {it.time}
                  </div>
                </div>
                <div className="badges">
                  <span className="b tag">{it.tag}</span>
                  {it.impact && (
                    <span className={`b ${impactClass(it.impact)}`}>{it.impact}</span>
                  )}
                </div>
              </div>

              {it.summary ? (
                <p className="summary">{it.summary}</p>
              ) : (
                <div className="head">{it.headline}</div>
              )}

              {Array.isArray(it.key_numbers) && it.key_numbers.length > 0 && (
                <div className="nums">
                  {it.key_numbers.map((n, i) => (
                    <span className="num" key={i}>
                      {n}
                    </span>
                  ))}
                </div>
              )}
              {it.why_it_matters && <div className="why">{it.why_it_matters}</div>}

              <div className="card-links">
                {it.pdf_url && (
                  <a href={it.pdf_url} target="_blank" rel="noopener noreferrer">
                    Open the original filing
                  </a>
                )}
              </div>
            </article>
          ))}

          {shown.length > limit && (
            <button className="more" onClick={() => setLimit(limit + 40)}>
              Show more <span className="meta">({shown.length - limit} left)</span>
            </button>
          )}
        </>
      )}

      <section className="section">
        <div className="newsletter">
          <div className="nl-flag">
            <span className="live-dot" /> Already running
          </div>
          <h2 className="nl-title">Get it every morning on WhatsApp</h2>
          <p className="nl-lead">
            You don&apos;t have to come here. Every morning we send the most
            important announcements, key developments and what they mean — free,
            in one short message. Plus weekly deep dives on companies and
            industries.
          </p>
          <p className="nl-tagline">Stay updated. Save time. Stay ahead.</p>
          <a
            className="nl-btn"
            href={SITE.newsletterLink}
            target="_blank"
            rel="noopener noreferrer"
          >
            <WaIcon /> Click here to join for free
          </a>
          <p className="nl-note">
            {SITE.readers} investors already follow Market Tide. Leave any time.
          </p>
        </div>
      </section>

      <section className="section">
        <h2>Prefer email?</h2>
        {formState === "done" ? (
          <div className="done">
            <b>Done — you&apos;re on the list.</b>
          </div>
        ) : (
          <>
            <form onSubmit={submit}>
              <div className="row">
                <input
                  type="email"
                  value={email}
                  required
                  autoComplete="email"
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@email.com"
                  aria-label="Email address"
                />
                <input
                  className="hp"
                  type="text"
                  tabIndex={-1}
                  aria-hidden="true"
                  autoComplete="off"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
              </div>
              <div className="row phone-row">
                <div className="phone-wrap">
                  <span className="cc">+91</span>
                  <input
                    className="phone"
                    type="tel"
                    inputMode="numeric"
                    maxLength={14}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="WhatsApp number (optional)"
                    aria-label="WhatsApp number, optional"
                  />
                </div>
                <button type="submit" disabled={formState === "sending"}>
                  {formState === "sending" ? "Adding…" : "Email me the big ones"}
                </button>
              </div>
              {formError && <p className="err">{formError}</p>}
            </form>
            <p className="note">Optional. The page above is free without it.</p>
          </>
        )}
      </section>

      <footer>
        <div className="footer-links">
          <a href="/terms">Terms</a>
          <a href="/refund">Refunds</a>
          <a href="/privacy">Privacy</a>
          <a href="/contact">Contact</a>
          <a
            href={`https://wa.me/${SITE.phoneDigits}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {SITE.phoneDisplay}
          </a>
        </div>
        <p>
          Market Tide summarises public filings made with NSE and BSE. It is not
          investment advice, and we are not a registered research analyst. Always
          read the original filing before acting on anything.
        </p>
        <p>Summaries are generated by AI and can contain mistakes.</p>
      </footer>
    </div>
  );
}

function XlsIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function WaIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.25-.46-2.38-1.47-.88-.78-1.47-1.75-1.65-2.05-.17-.3-.02-.46.13-.6.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.6-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.47s1.06 2.86 1.21 3.06c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.72 2-1.41.25-.69.25-1.28.17-1.41-.07-.13-.27-.2-.57-.35z" />
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm0 18.15h-.01a8.22 8.22 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23 2.2 0 4.27.86 5.83 2.42a8.18 8.18 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.24 8.23z" />
    </svg>
  );
}
