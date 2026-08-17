"use client";

import { useEffect, useMemo, useState } from "react";

const impactClass = (i) =>
  i === "Positive" ? "pos" : i === "Negative" ? "neg" : "neu";

function prettyDay(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [tag, setTag] = useState(null);
  const [day, setDay] = useState(null);
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(60);

  useEffect(() => {
    fetch("/api/announcements")
      .then((r) => r.json())
      .then((d) => (d.error ? setError(d.error) : setData(d)))
      .catch(() => setError("Couldn't load announcements. Try again in a moment."));
  }, []);

  const items = data?.items || [];

  const tags = useMemo(() => {
    const counts = {};
    for (const it of items) counts[it.tag] = (counts[it.tag] || 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [items]);

  const shown = useMemo(() => {
    const needle = q.toLowerCase().trim();
    return items.filter(
      (it) =>
        (!tag || it.tag === tag) &&
        (!day || it.day === day) &&
        (!needle ||
          `${it.company} ${it.ticker} ${it.headline} ${it.summary} ${it.category}`
            .toLowerCase()
            .includes(needle))
    );
  }, [items, tag, day, q]);

  const exportUrl = () => {
    const p = new URLSearchParams();
    if (tag) p.set("tag", tag);
    if (day) p.set("day", day);
    const qs = p.toString();
    return "/api/announcements/export" + (qs ? `?${qs}` : "");
  };

  if (error) {
    return (
      <div className="wrap">
        <div className="brand"><span className="dot" /> Market Tide</div>
        <div className="empty">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="wrap">
        <div className="brand"><span className="dot" /> Market Tide</div>
        <div className="empty">Loading the last 7 days…</div>
      </div>
    );
  }

  const positives = items.filter((i) => i.impact === "Positive").length;
  const negatives = items.filter((i) => i.impact === "Negative").length;

  return (
    <div className="wrap">
      <div className="brand">
        <a href="/" className="brand-link"><span className="dot" /> Market Tide</a>
        <span className="pill">Last 7 days</span>
      </div>

      <header className="dash-head">
        <h1 className="dash-title">Corporate announcements</h1>
        <p className="dash-sub">
          {data.meta?.scanned
            ? `${Number(data.meta.scanned).toLocaleString("en-IN")} filings scanned · `
            : ""}
          {items.length} worth reading
          {data.meta?.updated
            ? ` · updated ${new Date(data.meta.updated).toLocaleString("en-IN", {
                day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
              })}`
            : ""}
        </p>
      </header>

      <div className="stats">
        <div className="stat"><b>{items.length}</b><span>Important</span></div>
        <div className="stat"><b>{positives}</b><span>Positive</span></div>
        <div className="stat"><b>{negatives}</b><span>Negative</span></div>
        <div className="stat"><b>{data.days?.length || 0}</b><span>Days</span></div>
      </div>

      <div className="controls">
        <div className="control-row">
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search company, ticker or text…"
            aria-label="Search announcements"
          />
          <a className="dl-btn" href={exportUrl()} download>
            <XlsIcon /> Download Excel
          </a>
        </div>

        <div className="chips">
          <button className={`chip ${!day ? "on" : ""}`} onClick={() => setDay(null)}>
            All days
          </button>
          {(data.days || []).map((d) => (
            <button
              key={d}
              className={`chip ${day === d ? "on" : ""}`}
              onClick={() => setDay(day === d ? null : d)}
            >
              {prettyDay(d)}
            </button>
          ))}
        </div>

        <div className="chips">
          <button className={`chip ${!tag ? "on" : ""}`} onClick={() => setTag(null)}>
            All {items.length}
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
      </div>

      {shown.length === 0 ? (
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
                  <span className="b">{it.score}</span>
                </div>
              </div>

              <div className="head">{it.headline}</div>
              {it.summary && <p className="summary">{it.summary}</p>}

              {Array.isArray(it.key_numbers) && it.key_numbers.length > 0 && (
                <div className="nums">
                  {it.key_numbers.map((n, i) => (
                    <span className="num" key={i}>{n}</span>
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
                {it.page_url && (
                  <a href={it.page_url} target="_blank" rel="noopener noreferrer">
                    Company page
                  </a>
                )}
              </div>
            </article>
          ))}

          {shown.length > limit && (
            <button className="more" onClick={() => setLimit(limit + 60)}>
              Show {Math.min(60, shown.length - limit)} more
              <span className="meta"> ({shown.length - limit} left)</span>
            </button>
          )}
        </>
      )}

      <footer>
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
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}
