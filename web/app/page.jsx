"use client";

import { useState } from "react";

// Everything you'd want to rename lives here.
const SITE = {
  name: "Filed",
  // These are real figures measured from 7-8 Aug 2026. Update them when they drift.
  filedPerDay: "3,671",
  importantPerDay: "250",
  readTime: "under 10 min",
};

// A real summary the pipeline produced, not a mock-up.
const SAMPLES = [
  {
    company: "Aptus Pharma Ltd",
    meta: "BSE · Company Update / Buyback · 08 Aug, 18:42",
    tag: "Buyback",
    impact: "Positive",
    summary:
      "The board approved a buy-back of up to 1.394 million shares (about 1.24% of "
      + "equity) at a maximum price of Rs 500 per share, totalling no more than "
      + "Rs 697 million. It also approved buying the remaining 4.28% of JC Biotech "
      + "to make it wholly owned.",
    numbers: [
      "Max price Rs 500/share",
      "Max size Rs 697 million",
      "1,394,000 shares (1.24%)",
    ],
    why: "Returns cash to shareholders and can lift earnings per share.",
  },
  {
    company: "Mayank Cattle Food Ltd",
    meta: "BSE · Corp. Action / Bonus Issue · 08 Aug, 16:05",
    tag: "Bonus/Split",
    impact: "Positive",
    summary:
      "Announced the record date of 24 Aug 2026 for a 1:1 bonus issue of up to "
      + "5.4 lakh shares. Bonus shares are deemed allotted on 25 Aug and tradable "
      + "from 26 Aug.",
    numbers: ["1:1 bonus", "Record date 24 Aug 2026", "Trading from 26 Aug"],
    why: "Existing shareholders receive extra shares at no cost.",
  },
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [state, setState] = useState("idle"); // idle | sending | done | error
  const [error, setError] = useState("");
  const [already, setAlready] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (state === "sending") return;
    setState("sending");
    setError("");

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, company, source: "landing" }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Something went wrong. Try again?");
        setState("error");
        return;
      }
      setAlready(Boolean(data.alreadyJoined));
      setState("done");
    } catch {
      setError("Couldn't reach the server. Check your connection and try again.");
      setState("error");
    }
  }

  return (
    <div className="wrap">
      <div className="brand">
        <span className="dot" /> {SITE.name}
      </div>

      <section className="hero">
        <h1>
          {SITE.filedPerDay} filings were made yesterday.
          <br />
          <span className="fade">{SITE.importantPerDay} of them mattered.</span>
        </h1>

        <p className="lede">
          Every trading day, NSE and BSE publish thousands of corporate
          announcements. Almost all of it is paperwork — trading window notices,
          newspaper clippings, duplicate share certificates.{" "}
          <strong>
            {SITE.name} throws that away, reads the PDFs that are left, and tells
            you what each one actually says.
          </strong>{" "}
          In plain English, {SITE.readTime} to get through.
        </p>

        <div className="counts">
          <div className="count">
            <b>{SITE.filedPerDay}</b>
            <span>Filed daily</span>
          </div>
          <div className="count">
            <b>{SITE.importantPerDay}</b>
            <span>Actually matter</span>
          </div>
          <div className="count">
            <b>93%</b>
            <span>Filtered out</span>
          </div>
        </div>

        {state === "done" ? (
          <div className="done">
            <b>{already ? "You're already on the list." : "You're on the list."}</b>
            <p>
              We&apos;ll email you when it opens up — and nothing else. No
              newsletter, no forwarding your address to anyone.
            </p>
          </div>
        ) : (
          <>
            <form onSubmit={submit}>
              <div className="row">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@email.com"
                  aria-label="Email address"
                  required
                  autoComplete="email"
                />
                <input
                  className="hp"
                  type="text"
                  tabIndex={-1}
                  autoComplete="off"
                  aria-hidden="true"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Leave this empty"
                />
                <button type="submit" disabled={state === "sending"}>
                  {state === "sending" ? "Joining…" : "Join the waitlist"}
                </button>
              </div>
              {error && <p className="err">{error}</p>}
            </form>
            <p className="note">
              Free while we build. No card, no spam, one email when it launches.
            </p>
          </>
        )}
      </section>

      <section className="section">
        <h2>What you&apos;ll actually get</h2>
        {SAMPLES.map((s) => (
          <div className="card" key={s.company}>
            <div className="card-top">
              <div>
                <div className="co">{s.company}</div>
                <div className="meta">{s.meta}</div>
              </div>
              <div className="badges">
                <span className="b tag">{s.tag}</span>
                <span className="b pos">{s.impact}</span>
              </div>
            </div>
            <p className="summary">{s.summary}</p>
            <div className="nums">
              {s.numbers.map((n) => (
                <span className="num" key={n}>{n}</span>
              ))}
            </div>
            <div className="why">{s.why}</div>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>How it works</h2>
        <ul className="points">
          <li>
            <b>Everything gets pulled.</b> Every announcement filed with NSE and
            BSE, both exchanges, every trading day.
          </li>
          <li>
            <b>The noise gets cut.</b> Routine compliance filings are dropped.
            What survives is scored and sorted, so results, order wins, buybacks
            and takeovers rise to the top.
          </li>
          <li>
            <b>The PDF gets read.</b> Including the scanned ones that are just a
            photo of a signed letter — those get read visually.
          </li>
          <li>
            <b>You get the point.</b> Two or three sentences, the numbers that
            matter, and a link to the original filing.
          </li>
        </ul>
      </section>

      <footer>
        <p>
          {SITE.name} summarises public filings made with NSE and BSE. It is not
          investment advice, and we are not a registered research analyst. Always
          read the original filing before acting on anything.
        </p>
        <p>Summaries are generated by AI and can contain mistakes.</p>
      </footer>
    </div>
  );
}
