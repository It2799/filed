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
  ["relative", "Family"],
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

// What one share went for. The filing states a total and never a price, so
// older stored rows have no `price` field and it is worked out here instead.
// It is the number you can hold against what the share trades at today.
function each(row) {
  const p =
    Number(row.price) ||
    (Number(row.shares) ? Number(row.value) / Number(row.shares) : 0);
  if (!p) return "";
  return p < 1000
    ? `Rs ${p.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`
    : `Rs ${Math.round(p).toLocaleString("en-IN")}`;
}

// The form's wording, in English. "Market Purchase" is a field name.
const HOWS = [
  ["market purchase", "on the open market"],
  ["market sale", "on the open market"],
  ["open market", "on the open market"],
  ["off market", "off market"],
  ["inheritance", "by inheritance"],
  ["gift", "as a gift"],
  ["allotment", "through an allotment"],
  ["conversion", "on conversion"],
  ["preferential", "through a preferential issue"],
  ["rights", "through a rights issue"],
  ["pledge", ""],
  ["invocation", ""],
  ["other", ""],
];

function how(mode) {
  const m = (mode || "").trim().toLowerCase();
  if (!m) return "";
  const hit = HOWS.find(([k]) => m.includes(k));
  return hit ? hit[1] : m;
}

// Who the person is, in words rather than in the exchange's shorthand.
const ROLE_WORDS = [
  ["promoter and director", "promoter and director"],
  ["promoter group", "promoter group"],
  ["promoter", "promoter"],
  ["immediate relative", "family of an insider"],
  ["relative", "family of an insider"],
  ["key managerial", "senior management"],
  ["designated", "senior employee"],
  ["director", "director"],
  ["employee", "employee"],
  ["trust", "trust"],
];

function roleWords(category) {
  const c = (category || "").trim().toLowerCase();
  if (!c) return "";
  const hit = ROLE_WORDS.find(([k]) => c.includes(k));
  return hit ? hit[1] : c;
}

// The chip beside the company. The filing says "Pledge Revoke"; a reader
// should see "Pledge released".
const SIDES = [
  ["pledge revoke", "Pledge released"],
  ["pledge release", "Pledge released"],
  ["pledge invoke", "Pledge invoked"],
  ["pledge creation", "Pledged"],
  ["revoke", "Pledge released"],
  ["invoke", "Pledge invoked"],
  ["encumbrance", "Encumbered"],
  ["pledge", "Pledged"],
  ["buy", "Bought"],
  ["sell", "Sold"],
  ["acquisition", "Bought"],
  ["disposal", "Sold"],
];

function sideLabel(side) {
  const s = (side || "").trim().toLowerCase();
  if (!s) return "Traded";
  const hit = SIDES.find(([k]) => s.includes(k));
  return hit ? hit[1] : side;
}

// A pledge is not a purchase. Nobody paid Rs 70.38 a share to pledge shares
// they already own, so quoting a price on a pledge row would be a lie - the
// same rule the sentence in insider.py follows.
function isPledge(side) {
  const s = (side || "").toLowerCase();
  return s.includes("pledge") || s.includes("encumbr") ||
    s.includes("revoke") || s.includes("invoke");
}

// 0.0238% is not four decimals of precision.
function stake(pct) {
  const v = Number(String(pct ?? "").replace("%", ""));
  if (!v) return "";
  return v < 0.01 ? "under 0.01%" : `${v.toFixed(2)}%`;
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
          <h1>Who&rsquo;s buying their own shares</h1>
          <p className="sub">
            When a promoter, a director or senior staff buy or sell shares in
            their own company, they have to tell the exchange. This is that
            list &mdash; who, how many, and at what price.
          </p>
          <p className="note">
            Left out on purpose: employee stock schemes, company welfare
            trusts, and shares moving between members of one promoter family.
            None of those is anyone deciding what the shares are worth.
          </p>
        </header>

        {/* Counts only. The rupee totals that used to sit here added up
            purchases across two hundred different companies, which is not a
            number that means anything - Rs 177 crore of "buying" can be one
            block in one company or two hundred small ones. */}
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
            placeholder="Search a company or a person"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </section>

        {error ? <p className="empty">{error}</p> : null}
        {!error && !data ? <p className="empty">Loading&hellip;</p> : null}
        {data && !data.items.length ? (
          <p className="empty">
            Nothing matches that. Companies file these through the trading day,
            so mornings are often quiet.
          </p>
        ) : null}

        <ul className="trades">
          {rows.map((t) => (
            <li key={t.id} className={`trade ${t.side?.toLowerCase() || ""}`}>
              <div className="t-top">
                <span className="co">{t.company}</span>
                {t.mcap ? <span className="cap">{cap(t.mcap)}</span> : null}
                <span className="when">{dayLabel(t.day)}</span>
              </div>

              {/* Two shapes of row. The XBRL filing gives fields - who, how
                  many, at what, by what route. Our own scrape of the same
                  filing gives a sentence. Rather than draw a field row full of
                  blanks, a sentence is drawn as a sentence. */}
              {t.who ? (
                <>
                  {/* The money line, read left to right the way it is said
                      out loud: what happened, how much of it, at what price. */}
                  <p className="t-deal">
                    <span className={`side ${t.side?.toLowerCase() || ""}`}>
                      {sideLabel(t.side)}
                    </span>
                    <span className="qty">
                      {Number(t.shares || 0).toLocaleString("en-IN")} shares
                    </span>
                    {each(t) && !isPledge(t.side) ? (
                      <span className="each">at {each(t)}</span>
                    ) : null}
                    {t.value ? (
                      <span className="val">
                        {isPledge(t.side) ? "worth " : ""}
                        {money(t.value)}
                      </span>
                    ) : null}
                  </p>
                  <p className="t-who">
                    <strong>{t.who}</strong>
                    {roleWords(t.category) ? (
                      <span className={`role ${role(t)}`}>
                        {roleWords(t.category)}
                      </span>
                    ) : null}
                  </p>
                  {how(t.mode) || stake(t.after_pct) ? (
                    <p className="t-tail">
                      {how(t.mode)}
                      {how(t.mode) && stake(t.after_pct) ? " · " : ""}
                      {stake(t.after_pct)
                        ? `holds ${stake(t.after_pct)} after this`
                        : ""}
                    </p>
                  ) : null}
                </>
              ) : (
                <p className="t-text">{t.headline}</p>
              )}
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
          Straight from what companies file with NSE and BSE under SEBI&rsquo;s
          Regulation 7(2). Rows with a named person and a share count come from
          the structured filing; the rest are the same disclosure read from the
          document. Nothing here is advice.
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
        .seg.wrapseg { flex-wrap: wrap; }
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
        .trades { list-style: none; margin: 0; padding: 0; }
        .trade {
          border: 1px solid #eee; border-left: 3px solid #e0e0e0;
          border-radius: 10px; padding: 12px 14px; margin-bottom: 9px;
        }
        .trade.buy { border-left-color: #3aa35c; }
        .trade.sell { border-left-color: #cc4b4b; }
        .t-top {
          display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap;
        }
        .co { font-weight: 630; }
        .cap {
          font-size: 0.71rem; color: #555; background: #f2f2f2;
          padding: 1px 7px; border-radius: 99px; white-space: nowrap;
        }
        .when { margin-left: auto; font-size: 0.76rem; color: #9a9a9a; }
        .t-deal {
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
        .t-who { margin: 6px 0 0; font-size: 0.88rem; color: #333; }
        .role { margin-left: 7px; font-size: 0.75rem; color: #777; }
        .role.promoter { color: #7a4bbd; }
        .role.director { color: #1f6fb2; }
        .t-tail { margin: 4px 0 0; font-size: 0.8rem; color: #8a8a8a; }
        .t-text { margin: 7px 0 0; font-size: 0.9rem; line-height: 1.55; color: #333; }
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
          .when, .t-tail, .each, .role { color: #888; }
          .t-card { border-color: #333; }
          .t-card.buy { background: #102114; border-color: #2c5c3a; }
          .t-card.sell { background: #241111; border-color: #5e2b2b; }
          .t-l { color: #999; }
          .trade { border-color: #2a2a2a; border-left-color: #383838; }
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
          .t-who { color: #ccc; }
          .t-text { color: #ccc; }
        }
      `}</style>
    </>
  );
}
