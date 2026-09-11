"use client";

import { useEffect, useMemo, useState } from "react";
import Nav from "../Nav";

const PAGE = 25;

const ROLES = [
  ["all", "Everyone"],
  ["promoter", "Promoters"],
  ["director", "Directors"],
  ["kmp", "Key management"],
  ["employee", "Employees"],
  ["relative", "Relatives"],
];

function money(n) {
  const v = Number(n) || 0;
  if (!v) return "";
  if (v >= 1e7) return `Rs ${(v / 1e7).toFixed(2)} cr`;
  if (v >= 1e5) return `Rs ${(v / 1e5).toFixed(2)} lakh`;
  return `Rs ${v.toLocaleString("en-IN")}`;
}

// Company size, the way an Indian reader says it. A promoter putting Rs 2
// crore into a Rs 60 crore company is a different piece of news from the same
// Rs 2 crore going into a Rs 60,000 crore one.
function cap(n) {
  const v = Number(n) || 0;
  if (!v) return "";
  if (v >= 100000) return `Rs ${(v / 100000).toFixed(2)} lakh cr`;
  if (v >= 1000) return `Rs ${Math.round(v).toLocaleString("en-IN")} cr`;
  return `Rs ${v.toFixed(0)} cr`;
}

function dayLabel(iso) {
  if (!iso) return "";
  const dt = new Date(iso + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - dt) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function role(row) {
  const c = (row.category || "").toLowerCase();
  if (c.includes("promoter")) return "promoter";
  if (c.includes("director")) return "director";
  if (c.includes("key managerial") || c.includes("kmp")) return "kmp";
  if (c.includes("relative")) return "relative";
  if (c.includes("employee") || c.includes("designated")) return "employee";
  return "other";
}

export default function InsiderPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [side, setSide] = useState("all");
  const [who, setWho] = useState("all");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(PAGE);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    const p = new URLSearchParams({ days: "7", side, role: who });
    if (q.trim()) p.set("q", q.trim());
    fetch(`/api/insider?${p}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch(() => alive && setError("Could not load insider trades."))
      .finally(() => alive && setShown(PAGE));
    return () => {
      alive = false;
    };
  }, [side, who, q]);

  const rows = useMemo(() => (data?.items || []).slice(0, shown), [data, shown]);
  const counts = data?.counts;

  return (
    <>
      <Nav />
      <main className="wrap">
        <header className="head">
          <h1>Insider trading</h1>
          <p className="sub">
            What promoters, directors and senior staff are doing with their own
            money in their own company&rsquo;s shares &mdash; disclosed to the
            exchange under SEBI&rsquo;s Regulation 7(2).
          </p>
          <p className="note">
            Employee stock options, transfers inside a promoter family and
            company welfare trusts are left out. None of them is a decision
            about what the shares are worth.
          </p>
        </header>

        {counts ? (
          <section className="tally">
            <div className="t-card buy">
              <span className="t-n">{counts.buys}</span>
              <span className="t-l">bought</span>
              <span className="t-v">{money(counts.boughtValue)}</span>
            </div>
            <div className="t-card sell">
              <span className="t-n">{counts.sells}</span>
              <span className="t-l">sold</span>
              <span className="t-v">{money(counts.soldValue)}</span>
            </div>
            <div className="t-card">
              <span className="t-n">{counts.total}</span>
              <span className="t-l">trades, last 7 days</span>
            </div>
          </section>
        ) : null}

        <section className="controls">
          <div className="seg">
            {[["all", "All"], ["buy", "Bought"], ["sell", "Sold"]].map(([k, l]) => (
              <button
                key={k}
                type="button"
                className={side === k ? "on" : ""}
                onClick={() => setSide(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <div className="seg wrapseg">
            {ROLES.map(([k, l]) => (
              <button
                key={k}
                type="button"
                className={who === k ? "on" : ""}
                onClick={() => setWho(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <input
            className="search"
            placeholder="Company or person"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </section>

        {error ? <p className="empty">{error}</p> : null}
        {!error && !data ? <p className="empty">Loading&hellip;</p> : null}
        {data && !data.items.length ? (
          <p className="empty">
            No insider trades match. They arrive through the trading day, so
            early morning is often quiet.
          </p>
        ) : null}

        <ul className="trades">
          {rows.map((t) => (
            <li key={t.id} className={`trade ${t.side?.toLowerCase() || ""}`}>
              <div className="t-top">
                <span className="co">{t.company}</span>
                {t.mcap ? <span className="cap">{cap(t.mcap)}</span> : null}
                {t.symbol ? <span className="sym">{t.symbol}</span> : null}
                <span className={`side ${t.side?.toLowerCase() || ""}`}>
                  {t.side}
                </span>
                <span className="when">{dayLabel(t.day)}</span>
              </div>
              {/* Two shapes of row. The XBRL filing gives fields - who, how
                  many, at what, by what route. Our own scrape of the same
                  filing gives a sentence. Rather than draw a field row full of
                  blanks, a sentence is drawn as a sentence. */}
              {t.who ? (
                <>
                  <div className="t-who">
                    <strong>{t.who}</strong>
                    {t.category ? (
                      <span className={`role ${role(t)}`}>{t.category}</span>
                    ) : null}
                  </div>
                  <div className="t-nums">
                    <span>{Number(t.shares || 0).toLocaleString("en-IN")} shares</span>
                    {t.value ? <span className="val">{money(t.value)}</span> : null}
                    {t.mode ? <span className="mode">{t.mode}</span> : null}
                    {t.after_pct ? <span className="held">holds {t.after_pct}%</span> : null}
                  </div>
                </>
              ) : (
                <p className="t-text">{t.headline}</p>
              )}
            </li>
          ))}
        </ul>

        {data && data.items.length > shown ? (
          <button className="more" type="button" onClick={() => setShown(shown + PAGE)}>
            Show more ({data.items.length - shown} left)
          </button>
        ) : null}

        <p className="verify">
          From the disclosures companies file under SEBI&rsquo;s Regulation
          7(2), on both exchanges. Rows with a named person and a share count
          come from the structured filing; the rest are the same disclosure
          read from the document. Nothing here is advice.
        </p>
      </main>

      <style jsx>{`
        .wrap { max-width: 900px; margin: 0 auto; padding: 24px 16px 64px; }
        .head h1 { margin: 0 0 6px; font-size: 1.7rem; }
        .sub { margin: 0 0 8px; color: #444; line-height: 1.5; }
        .note { margin: 0 0 18px; color: #777; font-size: 0.86rem; line-height: 1.5; }
        .tally { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
        .t-card {
          flex: 1 1 150px; border: 1px solid #e6e6e6; border-radius: 10px;
          padding: 10px 12px; display: flex; flex-direction: column; gap: 2px;
        }
        .t-card.buy { border-color: #b9e2c4; background: #f3fbf5; }
        .t-card.sell { border-color: #f0c8c8; background: #fdf5f5; }
        .t-n { font-size: 1.5rem; font-weight: 650; }
        .t-l { font-size: 0.8rem; color: #666; }
        .t-v { font-size: 0.86rem; color: #333; }
        .controls { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
        .seg { display: inline-flex; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
        .seg.wrapseg { flex-wrap: wrap; }
        .seg button {
          border: 0; background: #fff; padding: 7px 11px; cursor: pointer;
          font-size: 0.85rem; border-right: 1px solid #eee;
        }
        .seg button:last-child { border-right: 0; }
        .seg button.on { background: #111; color: #fff; }
        .search {
          flex: 1 1 180px; min-width: 160px; padding: 7px 11px;
          border: 1px solid #ddd; border-radius: 8px; font-size: 0.85rem;
        }
        .trades { list-style: none; margin: 0; padding: 0; }
        .trade {
          border: 1px solid #eee; border-left: 3px solid #ddd; border-radius: 8px;
          padding: 11px 13px; margin-bottom: 9px;
        }
        .trade.buy { border-left-color: #3aa35c; }
        .trade.sell { border-left-color: #cc4b4b; }
        .t-top { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
        .co { font-weight: 620; }
        .sym { font-size: 0.75rem; color: #888; }
        .cap {
          font-size: 0.72rem; color: #555; background: #f1f1f1;
          padding: 1px 7px; border-radius: 99px;
        }
        .side { font-size: 0.72rem; padding: 1px 7px; border-radius: 99px; background: #eee; }
        .side.buy { background: #e4f5e9; color: #1e6b38; }
        .side.sell { background: #fbe7e7; color: #8c2b2b; }
        .when { margin-left: auto; font-size: 0.76rem; color: #999; }
        .t-who { margin-top: 4px; font-size: 0.92rem; }
        .role { margin-left: 7px; font-size: 0.74rem; color: #666; }
        .role.promoter { color: #7a4bbd; }
        .role.director { color: #1f6fb2; }
        .t-nums {
          margin-top: 5px; display: flex; gap: 12px; flex-wrap: wrap;
          font-size: 0.84rem; color: #555;
        }
        .val { font-weight: 600; color: #222; }
        .t-text { margin: 5px 0 0; font-size: 0.9rem; line-height: 1.5; color: #333; }
        .mode, .held { color: #888; }
        .more {
          display: block; margin: 12px auto; padding: 8px 16px;
          border: 1px solid #ddd; border-radius: 8px; background: #fff; cursor: pointer;
        }
        .empty { color: #777; padding: 18px 0; }
        .verify { margin-top: 26px; color: #999; font-size: 0.78rem; line-height: 1.5; }
        @media (prefers-color-scheme: dark) {
          .sub { color: #bbb; } .note, .when, .mode, .held { color: #888; }
          .t-card { border-color: #333; }
          .t-card.buy { background: #102114; border-color: #2c5c3a; }
          .t-card.sell { background: #241111; border-color: #5e2b2b; }
          .trade { border-color: #2a2a2a; }
          .cap { background: #222; color: #aaa; }
          .seg { border-color: #333; }
          .seg button { background: #161616; color: #ddd; border-right-color: #262626; }
          .seg button.on { background: #fff; color: #111; }
          .search { background: #161616; color: #ddd; border-color: #333; }
          .more { background: #161616; color: #ddd; border-color: #333; }
          .val { color: #eee; }
          .t-text { color: #ccc; }
        }
      `}</style>
    </>
  );
}
