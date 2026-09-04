"use client";

import { useEffect, useMemo, useState } from "react";
import Nav from "../Nav";
import AuthGate from "../AuthGate";
import { mcapLabel, mcapTier } from "../fmt";

const PAGE = 40;

const impactClass = (i) =>
  i === "Positive" ? "pos" : i === "Negative" ? "neg" : "neu";

function dayLabel(iso) {
  if (!iso) return { d: "", w: "" };
  const dt = new Date(iso + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - dt) / 86400000);
  const w = diff === 0 ? "Today" : diff === 1 ? "Yesterday"
    : dt.toLocaleDateString("en-IN", { weekday: "short" });
  return { d: dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short" }), w };
}

// Company size bands, matching the ones the API filters on. Labelled the way
// an Indian investor says them out loud rather than in raw rupees.
const BANDS = [
  ["mega", "Above Rs 1 lakh cr"],
  ["large", "Rs 50,000 cr - 1 lakh cr"],
  ["mid", "Rs 10,000 - 50,000 cr"],
  ["small", "Rs 1,000 - 10,000 cr"],
  ["micro", "Below Rs 1,000 cr"],
];

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [scope, setScope] = useState("important");
  const [tag, setTag] = useState(null);
  const [day, setDay] = useState(null);
  const [band, setBand] = useState(null);
  const [q, setQ] = useState("");
  const [catQ, setCatQ] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const [railOpen, setRailOpen] = useState(false);

  // Filtering happens on the server. Doing it in the browser meant a small
  // category was searched inside an already-truncated list, so picking
  // "Pref" or "Warrants" came back nearly empty even though the filings existed.
  const [debouncedQ, setDebouncedQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    let dead = false;
    setLoading(true);
    const p = new URLSearchParams({ scope });
    if (tag) p.set("tag", tag);
    if (day) p.set("day", day);
    if (band) p.set("band", band);
    if (debouncedQ) p.set("q", debouncedQ);

    fetch(`/api/announcements?${p}`, { cache: "no-store" })
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
    return () => { dead = true; };
  }, [scope, tag, day, band, debouncedQ]);

  // `band` too: without it, paging deep and then changing size rendered the
  // whole result set at once and the "Show more" button vanished.
  useEffect(() => { setLimit(PAGE); }, [scope, tag, day, band, debouncedQ]);

  const items = data?.items || [];

  const tags = useMemo(
    () => Object.entries(data?.tagCounts || {}).sort((a, b) => b[1] - a[1]),
    [data]
  );

  // Filings across every category, not the number of categories. The row read
  // "All categories 25" above "Results 412", which made the total look like a
  // subset of its own children - 25 was how many categories there were.
  const tagTotal = useMemo(
    () => tags.reduce((sum, [, n]) => sum + n, 0),
    [tags]
  );

  const visibleTags = useMemo(() => {
    const n = catQ.toLowerCase().trim();
    return n ? tags.filter(([t]) => t.toLowerCase().includes(n)) : tags;
  }, [tags, catQ]);

  // Day counts come from a separate unfiltered read, so selecting a category
  // doesn't make every other day look empty.
  // Counted by the server, not from the rows it sent back.
  //
  // This used to tally `d.items`, which the API caps - 1,500 under Worth
  // reading, 600 under Everything - and sorts newest first. So on a busy week
  // the older days had no rows left to count and the sidebar showed them as 0,
  // while clicking one filled the feed: the API applies the day filter BEFORE
  // the cap. The sidebar contradicted the page.
  //
  // The guard matters too. Without it a slow response for a scope you have
  // since navigated away from lands last and overwrites the right answer - the
  // feed's own fetch has always had one.
  const [dayCounts, setDayCounts] = useState({});
  useEffect(() => {
    let dead = false;
    fetch(`/api/announcements?scope=${scope}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (dead) return;
        setDayCounts(d.dayCounts || {});
      })
      .catch(() => {});
    return () => { dead = true; };
  }, [scope]);

  const shown = items;

  // Everything the screen is filtered by, so the file matches what you can see.
  // Band and search used to be left out.
  const exportUrl = () => {
    const p = new URLSearchParams();
    if (tag) p.set("tag", tag);
    if (day) p.set("day", day);
    if (band) p.set("band", band);
    if (debouncedQ) p.set("q", debouncedQ);
    if (scope === "all") p.set("scope", "all");
    const qs = p.toString();
    return "/api/announcements/export" + (qs ? `?${qs}` : "");
  };

  // `band` belongs here. Without it, choosing a company size showed no pill,
  // no "Filters" badge and no "clear all" - and the empty state gates its
  // escape hatch on this count, so a reader who narrowed to a size with no
  // matches got "Nothing matches that." with no way back.
  const activeCount =
    (tag ? 1 : 0) + (day ? 1 : 0) + (band ? 1 : 0) + (q ? 1 : 0);
  const clearAll = () => {
    setTag(null); setDay(null); setBand(null); setQ(""); setCatQ("");
  };

  // Stop the page scrolling behind the filter sheet on a phone.
  useEffect(() => {
    document.body.classList.toggle("sheet-open", railOpen);
    return () => document.body.classList.remove("sheet-open");
  }, [railOpen]);

  return (
    <AuthGate>
      <Nav />
      <div className="dash-shell">
        <header className="dash-top">
          <h1>Corporate announcements</h1>
          <p className="dash-meta">
            {data?.meta?.updated
              ? `Last 7 days · updated ${new Date(data.meta.updated).toLocaleString(
                  "en-IN",
                  { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }
                )}`
              : "Loading…"}
          </p>

          {data?.meta ? (
            <div className="funnel">
              <div className="fstep">
                <b>{Number(data.meta.scanned || 0).toLocaleString("en-IN")}</b>
                <span>filed on NSE &amp; BSE</span>
              </div>
              <div className="fstep hi">
                <b>{Number(data.total || 0).toLocaleString("en-IN")}</b>
                <span>worth reading</span>
              </div>
              <div className="fstep hi">
                <b>{Number(data.summarised || 0).toLocaleString("en-IN")}</b>
                <span>summarised</span>
              </div>
            </div>
          ) : null}

          {data?.meta?.promoted > 0 && (
            <p className="rescued">
              In the latest scan, <b>{Number(data.meta.promoted).toLocaleString("en-IN")}</b>{" "}
              important announcements were discovered only after examining their
              attached documents.
            </p>
          )}
        </header>

        <div className="dash-grid">
          {/* ---------------- filter rail ---------------- */}
          <div
            className={`sheet-backdrop ${railOpen ? "open" : ""}`}
            onClick={() => setRailOpen(false)}
            aria-hidden="true"
          />

          <aside className={`rail ${railOpen ? "open" : ""}`}>
            <div className="rail-group">
              <p className="rail-title">Show</p>
              <div className="seg">
                <button
                  className={scope === "important" ? "on" : ""}
                  onClick={() => { setScope("important"); setTag(null); }}
                >
                  Worth reading
                </button>
                <button
                  className={scope === "all" ? "on" : ""}
                  onClick={() => { setScope("all"); setTag(null); }}
                >
                  Everything
                </button>
              </div>
            </div>

            <div className="rail-group">
              <p className="rail-title">
                Day
                {day && (
                  <button className="rail-clear" onClick={() => setDay(null)}>
                    clear
                  </button>
                )}
              </p>
              <div className="daylist">
                <button
                  className={`dayrow ${!day ? "on" : ""}`}
                  onClick={() => setDay(null)}
                >
                  <span>All days</span>
                  <span className="cnt">
                    {(Object.values(dayCounts).reduce((a, b) => a + b, 0)
                      || items.length).toLocaleString("en-IN")}
                  </span>
                </button>
                {(data?.days || []).map((d) => {
                  const { d: dd, w } = dayLabel(d);
                  return (
                    <button
                      key={d}
                      className={`dayrow ${day === d ? "on" : ""}`}
                      onClick={() => setDay(day === d ? null : d)}
                    >
                      <span>
                        {dd} <span className="dw">{w}</span>
                      </span>
                      <span className="cnt">{dayCounts[d] || 0}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rail-group">
              <p className="rail-title">
                Company size
                {band && (
                  <button className="rail-clear" onClick={() => setBand(null)}>
                    clear
                  </button>
                )}
              </p>
              <div className="catlist">
                <button
                  className={`catrow ${!band ? "on" : ""}`}
                  onClick={() => setBand(null)}
                >
                  <span>Any size</span>
                  <span className="cnt">{tagTotal.toLocaleString("en-IN")}</span>
                </button>
                {BANDS.map(([key, label]) => (
                  <button
                    key={key}
                    className={`catrow ${band === key ? "on" : ""}`}
                    onClick={() => setBand(band === key ? null : key)}
                  >
                    <span>{label}</span>
                    <span className="cnt">
                      {(data?.bandCounts?.[key] ?? 0).toLocaleString("en-IN")}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="rail-group">
              <p className="rail-title">
                Category
                {tag && (
                  <button className="rail-clear" onClick={() => setTag(null)}>
                    clear
                  </button>
                )}
              </p>
              {tags.length > 8 && (
                <input
                  className="catsearch"
                  value={catQ}
                  onChange={(e) => setCatQ(e.target.value)}
                  placeholder="Filter categories…"
                  aria-label="Filter the category list"
                />
              )}
              <div className="catlist">
                <button
                  className={`catrow ${!tag ? "on" : ""}`}
                  onClick={() => setTag(null)}
                >
                  <span>All categories</span>
                  <span className="cnt">{tagTotal.toLocaleString("en-IN")}</span>
                </button>
                {visibleTags.map(([t, n]) => (
                  <button
                    key={t}
                    className={`catrow ${tag === t ? "on" : ""}`}
                    onClick={() => setTag(tag === t ? null : t)}
                  >
                    <span>{t}</span>
                    <span className="cnt">{n.toLocaleString("en-IN")}</span>
                  </button>
                ))}
                {visibleTags.length === 0 && (
                  <p className="note" style={{ padding: "8px 10px" }}>
                    No category matches that.
                  </p>
                )}
              </div>
            </div>

            {/* Only shows on a phone, where the rail is a sheet that has to
                be dismissed. On desktop the rail is always visible and the
                filters apply as you click them. */}
            <div className="sheet-done">
              {activeCount > 0 && (
                <button className="done-reset" onClick={clearAll}>
                  Reset
                </button>
              )}
              <button className="done-ok" onClick={() => setRailOpen(false)}>
                Show {shown.length.toLocaleString("en-IN")}
                {shown.length === 1 ? " filing" : " filings"}
              </button>
            </div>
          </aside>

          {/* ---------------- feed ---------------- */}
          <section>
            <div className="feedbar">
              <div className="feedbar-row">
                <button
                  className="filter-toggle"
                  onClick={() => setRailOpen(!railOpen)}
                  aria-expanded={railOpen}
                >
                  Filters
                  {activeCount > 0 && <span className="badge">{activeCount}</span>}
                </button>
                <input
                  type="search"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search company…"
                  aria-label="Search filings"
                />
                <a className="dl-btn" href={exportUrl()} download>
                  <XlsIcon /> Excel
                </a>
              </div>

              {/* The filing count used to sit here. It was removed because it
                  was not the number of filings: the API caps what it returns
                  (1,500 under Worth reading, 600 under Everything), so a busy
                  week always read exactly "1,500 filings" whatever was really
                  there, and it contradicted the larger figure in the funnel
                  three lines above. A wrong number is worse than none. */}
              <div className="active-row">
                {day && (
                  <button className="pill-x" onClick={() => setDay(null)}>
                    {dayLabel(day).d} <span>×</span>
                  </button>
                )}
                {tag && (
                  <button className="pill-x" onClick={() => setTag(null)}>
                    {tag} <span>×</span>
                  </button>
                )}
                {band && (
                  <button className="pill-x" onClick={() => setBand(null)}>
                    {(BANDS.find(([k]) => k === band) || [, band])[1]}{" "}
                    <span>×</span>
                  </button>
                )}
                {q && (
                  <button className="pill-x" onClick={() => setQ("")}>
                    &ldquo;{q}&rdquo; <span>×</span>
                  </button>
                )}
                {activeCount > 1 && (
                  <button className="rail-clear" onClick={clearAll}>
                    clear all
                  </button>
                )}
                {loading && <span className="tab-loading">loading…</span>}
              </div>
            </div>

            {error ? (
              <div className="empty">{error}</div>
            ) : loading && !data ? (
              [0, 1, 2, 3].map((i) => (
                <div className="sk" key={i}>
                  <div className="sk-line w40" />
                  <div className="sk-line w90" />
                  <div className="sk-line w70" />
                  <div className="sk-line w55" />
                </div>
              ))
            ) : shown.length === 0 ? (
              <div className="empty">
                <p>Nothing matches that.</p>
                {activeCount > 0 && (
                  <button className="more" style={{ maxWidth: 220, margin: "12px auto 0" }}
                          onClick={clearAll}>
                    Clear the filters
                  </button>
                )}
              </div>
            ) : (
              <>
                {shown.slice(0, limit).map((it) => {
                  const nums = Array.isArray(it.key_numbers) ? it.key_numbers : [];
                  return (
                    <article
                      className={`card imp-${it.impact || "Neutral"}`}
                      key={it.id}
                    >
                      <div className="card-head">
                        <div className="co-line">
                          <span className="co">{it.company}</span>
                          {mcapLabel(it.mcap) && (
                            <span className={`mcap ${mcapTier(it.mcap)}`}>
                              {mcapLabel(it.mcap)}
                            </span>
                          )}
                        </div>
                        <div className="meta-line">
                          <span className="b tag">{it.tag}</span>
                          {it.impact && (
                            <span className={`b ${impactClass(it.impact)}`}>
                              {it.impact}
                            </span>
                          )}
                          <span className="meta">{it.time}</span>
                          <span className="meta hide-sm">· {it.exchange}</span>
                        </div>
                      </div>

                      {it.summary ? (
                        <p className="summary">{it.summary}</p>
                      ) : (
                        <>
                          <div className="head">{it.headline}</div>
                          <span className="no-summary">
                            Routine filing — not summarised
                          </span>
                        </>
                      )}

                      {nums.length > 0 && (
                        <div className="nums">
                          {nums.map((n, i) => (
                            <span className="num" key={i}>{n}</span>
                          ))}
                        </div>
                      )}

                      {it.why_it_matters && (
                        <div className="why">{it.why_it_matters}</div>
                      )}

                      {/* Two shapes here. Filed under DIFFERENT headings, so
                          the other headings are worth naming; or filed more
                          than once under the SAME heading, where there is no
                          other heading to name and the count is the whole
                          story. The second case used to render "Also filed
                          as" followed by nothing. */}
                      {it.also_filed > 0 && (
                        <div className="also">
                          {(it.also_tags || []).length > 0 ? (
                            <>
                              <span>Also filed as</span>
                              {it.also_tags.map((t) => (
                                <span className="also-tag" key={t}>{t}</span>
                              ))}
                            </>
                          ) : (
                            <span>
                              Filed {it.also_filed + 1} times
                            </span>
                          )}
                        </div>
                      )}

                      <div className="card-links">
                        {it.pdf_url && (
                          <a href={it.pdf_url} target="_blank" rel="noopener noreferrer">
                            Open filing
                          </a>
                        )}
                        {!it.pdf_url && it.page_url && (
                          <a href={it.page_url} target="_blank" rel="noopener noreferrer">
                            View company on {it.exchange?.includes("BSE") ? "BSE" : "NSE"}
                          </a>
                        )}
                        {!it.pdf_url && !it.page_url && (
                          <span className="verify">Filing link unavailable</span>
                        )}
                      </div>
                    </article>
                  );
                })}

                {shown.length > limit && (
                  <button className="more" onClick={() => setLimit(limit + PAGE)}>
                    Show {Math.min(PAGE, shown.length - limit)} more{" "}
                    <span className="meta">({shown.length - limit} left)</span>
                  </button>
                )}
              </>
            )}
          </section>
        </div>

        <footer>
          <div className="footer-links">
            <a href="/">Home</a>
            <a href="/join">Join</a>
            <a href="/terms">Terms</a>
            <a href="/refund">Refunds</a>
            <a href="/privacy">Privacy</a>
            <a href="/contact">Contact</a>
          </div>
          <p>
            Market Tide summarises public filings made with NSE and BSE. It is not
            investment advice, and we are not a registered research analyst.
            Always read the original filing before acting on anything.
          </p>
          <p>Summaries are generated by AI and can contain mistakes.</p>
        </footer>
      </div>
    </AuthGate>
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
