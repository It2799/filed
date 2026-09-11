"use client";

import { useEffect, useMemo, useState } from "react";
import Nav from "../Nav";

const PAGE = 25;

function money(n) {
  const v = Number(n) || 0;
  if (!v) return "";
  if (v >= 1e7) return `Rs ${(v / 1e7).toFixed(2)} cr`;
  if (v >= 1e5) return `Rs ${(v / 1e5).toFixed(2)} lakh`;
  return `Rs ${v.toLocaleString("en-IN")}`;
}

// Company size, the way an Indian reader says it. Rs 20 crore into a Rs 200
// crore company is a different piece of news from the same Rs 20 crore into a
// Rs 2 lakh crore one.
function cap(n) {
  const v = Number(n) || 0;
  if (!v) return "";
  if (v >= 100000) return `Rs ${(v / 100000).toFixed(2)} lakh cr`;
  if (v >= 1000) return `Rs ${Math.round(v).toLocaleString("en-IN")} cr`;
  return `Rs ${v.toFixed(0)} cr`;
}

function each(price) {
  const p = Number(price) || 0;
  if (!p) return "";
  return p < 1000
    ? `Rs ${p.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`
    : `Rs ${Math.round(p).toLocaleString("en-IN")}`;
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

export default function DealsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [side, setSide] = useState("all");
  const [kind, setKind] = useState("all");
  const [exch, setExch] = useState("all");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(PAGE);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    const p = new URLSearchParams({ days: "7", side, kind, exchange: exch });
    if (q.trim()) p.set("q", q.trim());
    fetch(`/api/deals?${p}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch(() => alive && setError("Could not load bulk and block deals."))
      .finally(() => alive && setShown(PAGE));
    return () => {
      alive = false;
    };
  }, [side, kind, exch, q]);

  const rows = useMemo(() => (data?.items || []).slice(0, shown), [data, shown]);
  const counts = data?.counts;

  return (
    <>
      <Nav />
      <main className="wrap">
        <header className="head">
          <h1>The big trades, by name</h1>
          <p className="sub">
            When one investor buys or sells a large slice of a company in a
            single day, the exchange has to publish their name. Funds, family
            offices, promoters &mdash; this is who moved, and at what price.
          </p>
          <p className="note">
            Day trading is taken out. Someone who buys and sells the same
            shares in one day gets reported twice and owns nothing by the
            close, so we net each name&rsquo;s trades in a company on a day and
            drop the pure round trips. Tiny deals are left out too &mdash; a
            bulk deal is half a percent of the company, which in a small one
            can be a few lakh rupees.
          </p>
        </header>

        {/* Counts only. A rupee total here would add up purchases across
            dozens of unrelated companies, which is not a number that means
            anything. */}
        {counts ? (
          <section className="tally">
            <div className="t-card buy">
              <span className="t-n">{counts.buys}</span>
              <span className="t-l">bought</span>
            </div>
            <div className="t-card sell">
              <span className="t-n">{counts.sells}</span>
              <span className="t-l">sold</span>
            </div>
            <div className="t-card">
              <span className="t-n">{counts.total}</span>
              <span className="t-l">in the last 7 days</span>
            </div>
          </section>
        ) : null}

        <section className="controls">
          <div className="seg">
            {[
              ["all", "All"],
              ["buy", "Buying"],
              ["sell", "Selling"],
            ].map(([k, l]) => (
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
          <div className="seg">
            {[
              ["all", "Both kinds"],
              ["bulk", "Bulk"],
              ["block", "Block"],
            ].map(([k, l]) => (
              <button
                key={k}
                type="button"
                className={kind === k ? "on" : ""}
                onClick={() => setKind(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <div className="seg">
            {[
              ["all", "Both exchanges"],
              ["NSE", "NSE"],
              ["BSE", "BSE"],
            ].map(([k, l]) => (
              <button
                key={k}
                type="button"
                className={exch === k ? "on" : ""}
                onClick={() => setExch(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <input
            className="search"
            placeholder="Search a company or an investor"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </section>

        {error ? <p className="empty">{error}</p> : null}
        {!error && !data ? <p className="empty">Loading&hellip;</p> : null}
        {data && !data.items.length ? (
          <p className="empty">
            Nothing matches that. Both exchanges publish these after the close,
            so the trading day itself is quiet.
          </p>
        ) : null}

        <ul className="deals">
          {rows.map((d) => (
            <li key={d.id} className={`deal ${d.side?.toLowerCase() || ""}`}>
              <div className="d-top">
                <span className="co">{d.company}</span>
                {d.mcap ? <span className="cap">{cap(d.mcap)}</span> : null}
                <span className="when">{dayLabel(d.day)}</span>
              </div>

              {/* Read left to right the way it is said out loud: what
                  happened, how many, at what price, for how much. */}
              <p className="d-deal">
                <span className={`side ${d.side?.toLowerCase() || ""}`}>
                  {d.side === "Buy" ? "Bought" : "Sold"}
                </span>
                <span className="qty">
                  {Number(d.shares || 0).toLocaleString("en-IN")} shares
                </span>
                {each(d.price) ? (
                  <span className="each">at {each(d.price)}</span>
                ) : null}
                {d.value ? <span className="val">{money(d.value)}</span> : null}
              </p>

              <p className="d-who">
                <strong>{d.who}</strong>
                <span className="tag">
                  {d.kind} deal &middot; {d.exchange}
                </span>
              </p>

              {d.netted ? (
                <p className="d-tail">
                  Net figure &mdash; they also{" "}
                  {d.side === "Buy" ? "sold" : "bought"}{" "}
                  {Number(
                    (d.side === "Buy" ? d.gross_sell : d.gross_buy) || 0
                  ).toLocaleString("en-IN")}{" "}
                  shares the same day.
                </p>
              ) : null}
              {d.remarks ? <p className="d-tail">{d.remarks}</p> : null}
            </li>
          ))}
        </ul>

        {data && data.items.length > shown ? (
          <button
            className="more"
            type="button"
            onClick={() => setShown(shown + PAGE)}
          >
            Show {Math.min(PAGE, data.items.length - shown)} more
          </button>
        ) : null}

        <p className="verify">
          From the bulk and block deal reports NSE and BSE publish each trading
          day. Prices are the weighted average the exchange reports. Nothing
          here is advice.
        </p>
      </main>

      <style jsx>{`
        .wrap { max-width: 900px; margin: 0 auto; padding: 24px 16px 64px; }
        .head h1 { margin: 0 0 8px; font-size: 1.75rem; letter-spacing: -0.01em; }
        .sub { margin: 0 0 8px; color: #444; line-height: 1.55; max-width: 62ch; }
        .note {
          margin: 0 0 20px; color: #6b6b6b; font-size: 0.85rem;
          line-height: 1.55; max-width: 62ch;
          border-left: 2px solid #e8e8e8; padding-left: 11px;
        }
        .tally { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
        .t-card {
          flex: 1 1 130px; border: 1px solid #e8e8e8; border-radius: 12px;
          padding: 12px 14px; display: flex; flex-direction: column; gap: 1px;
        }
        .t-card.buy { border-color: #c6e6cf; background: #f4fbf6; }
        .t-card.sell { border-color: #f2d0d0; background: #fdf6f6; }
        .t-n { font-size: 1.7rem; font-weight: 660; letter-spacing: -0.02em; }
        .t-l { font-size: 0.8rem; color: #666; }
        .controls { display: flex; gap: 9px; flex-wrap: wrap; margin-bottom: 16px; }
        .seg {
          display: inline-flex; border: 1px solid #e2e2e2; border-radius: 9px;
          overflow: hidden;
        }
        .seg button {
          border: 0; background: #fff; padding: 7px 12px; cursor: pointer;
          font-size: 0.85rem; color: #333; border-right: 1px solid #eee;
        }
        .seg button:last-child { border-right: 0; }
        .seg button:hover { background: #f6f6f6; }
        .seg button.on { background: #111; color: #fff; }
        .search {
          flex: 1 1 200px; min-width: 170px; padding: 7px 12px;
          border: 1px solid #e2e2e2; border-radius: 9px; font-size: 0.85rem;
        }
        .deals { list-style: none; margin: 0; padding: 0; }
        .deal {
          border: 1px solid #eee; border-left: 3px solid #e0e0e0;
          border-radius: 10px; padding: 12px 14px; margin-bottom: 9px;
        }
        .deal.buy { border-left-color: #3aa35c; }
        .deal.sell { border-left-color: #cc4b4b; }
        .d-top { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
        .co { font-weight: 630; }
        .cap {
          font-size: 0.71rem; color: #555; background: #f2f2f2;
          padding: 1px 7px; border-radius: 99px; white-space: nowrap;
        }
        .when { margin-left: auto; font-size: 0.76rem; color: #9a9a9a; }
        .d-deal {
          margin: 8px 0 0; display: flex; gap: 9px; align-items: baseline;
          flex-wrap: wrap; font-size: 0.92rem;
        }
        .side {
          font-size: 0.72rem; padding: 2px 8px; border-radius: 99px;
          background: #eee; font-weight: 600; letter-spacing: 0.01em;
        }
        .side.buy { background: #e4f5e9; color: #1e6b38; }
        .side.sell { background: #fbe7e7; color: #8c2b2b; }
        .qty { color: #222; }
        .each { color: #666; }
        .val { margin-left: auto; font-weight: 650; color: #111; }
        .d-who { margin: 6px 0 0; font-size: 0.88rem; color: #333; }
        .tag { margin-left: 8px; font-size: 0.75rem; color: #8a8a8a; }
        .d-tail { margin: 4px 0 0; font-size: 0.8rem; color: #8a8a8a; }
        .more {
          display: block; margin: 14px auto; padding: 9px 18px;
          border: 1px solid #e2e2e2; border-radius: 9px; background: #fff;
          cursor: pointer; font-size: 0.87rem;
        }
        .more:hover { background: #f6f6f6; }
        .empty { color: #777; padding: 18px 0; line-height: 1.55; }
        .verify {
          margin-top: 28px; color: #9a9a9a; font-size: 0.78rem;
          line-height: 1.55; max-width: 66ch;
        }
        @media (prefers-color-scheme: dark) {
          .sub { color: #bbb; }
          .note { color: #8d8d8d; border-left-color: #2c2c2c; }
          .when, .d-tail, .each, .tag { color: #888; }
          .t-card { border-color: #333; }
          .t-card.buy { background: #102114; border-color: #2c5c3a; }
          .t-card.sell { background: #241111; border-color: #5e2b2b; }
          .t-l { color: #999; }
          .deal { border-color: #2a2a2a; border-left-color: #383838; }
          .cap { background: #232323; color: #aaa; }
          .seg { border-color: #333; }
          .seg button {
            background: #161616; color: #ddd; border-right-color: #262626;
          }
          .seg button:hover { background: #1e1e1e; }
          .seg button.on { background: #fff; color: #111; }
          .search { background: #161616; color: #ddd; border-color: #333; }
          .more { background: #161616; color: #ddd; border-color: #333; }
          .more:hover { background: #1e1e1e; }
          .qty { color: #ddd; }
          .val { color: #fff; }
          .d-who { color: #ccc; }
        }
      `}</style>
    </>
  );
}
