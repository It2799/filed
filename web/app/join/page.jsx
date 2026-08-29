"use client";

import { useState } from "react";
import Nav from "../Nav";
import MkFooter from "../MkFooter";
import { SITE, SAVING, SAVING_PCT, PER_MONTH } from "../site";

const FEATURES = [
  {
    icon: "📄",
    title: "The full dashboard",
    body: "Every relevant filing, all seven days, all 30-odd categories, and Excel export on any filter you set.",
  },
  {
    icon: "💬",
    title: "The evening read-through",
    body: "The day's filings land and members pull them apart. What an order win is really worth. Whether a buyback is priced sensibly.",
  },
  {
    icon: "🤝",
    title: "Meetups across India",
    body: "Mumbai first, then wherever enough members are. Real conversations, no stage, nobody selling anything.",
  },
  {
    icon: "🔍",
    title: "Weekly deep dives",
    body: "One company or one industry, written up properly — the filings, the numbers, the history — not posted as a chart with an arrow.",
  },
  {
    icon: "❓",
    title: "Bring a filing, get it explained",
    body: "Stuck on a scheme of arrangement or a warrant issue? Post it. Someone who has read a hundred of them will walk you through it.",
  },
  {
    icon: "🚨",
    title: "Results season war room",
    body: "When 1,300 filings land in a day, members split the work and flag what actually moved. Nobody reads that alone.",
  },
  {
    icon: "👀",
    title: "Watchlist alerts",
    body: "Tell us the companies you hold. We message you when one of them files something that matters, instead of you checking.",
  },
  {
    icon: "🧹",
    title: "Moderated, properly",
    body: "No tips, no forwards, no good-morning images, no operators. One warning, then out. That rule is the whole product.",
  },
  {
    icon: "🎯",
    title: "You shape what gets built",
    body: "Members ask for a category, a filter, an alert — and it gets built. This dashboard exists because people asked for it.",
  },
];

export default function Join() {
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");

  const waLink = `https://wa.me/${SITE.phoneDigits}?text=${encodeURIComponent(
    `Hi, I'd like a founding seat in the Market Tide community at Rs ${SITE.price}/year.`
  )}`;

  async function submit(e) {
    e.preventDefault();
    if (state === "sending") return;
    setState("sending");
    setError("");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, phone, company, source: "join" }),
      });
      const d = await res.json();
      if (!res.ok) {
        setError(d.error || "Please try again.");
        setState("idle");
        return;
      }
      setState("done");
    } catch {
      setError("Couldn't reach the server. Please try again.");
      setState("idle");
    }
  }

  return (
    <>
      <Nav />

      <main className="mk">
        <section className="mk-hero">
          <div className="launch-banner">
            🚀 Launch price · first {SITE.launchSeats} members only
          </div>
          <h1 className="mk-h1">
            ₹{SITE.price} a year keeps
            <br />
            <span className="grad">the tourists out.</span>
          </h1>
          <p className="mk-sub">
            The filings stay free — they always will. What you&apos;re paying for
            is the room next door: investors and traders serious enough to put
            money on the table to be in it.{" "}
            <strong>The price isn&apos;t covering our costs. It&apos;s the filter.</strong>
          </p>
        </section>

        {/* ---------------- price + why ---------------- */}
        <section className="mk-sec" style={{ paddingTop: 8 }}>
          <div className="price-wrap">
            <div className="price-card">
              <p className="mk-kicker" style={{ marginBottom: 4 }}>
                Founding membership
              </p>

              <div className="price-tag">
                <span className="was">₹{SITE.fullPrice.toLocaleString("en-IN")}</span>
                <b>₹{SITE.price.toLocaleString("en-IN")}</b>
                <span>/ {SITE.period}</span>
              </div>
              <p className="price-note">
                Save ₹{SAVING} ({SAVING_PCT}% off) — works out to about ₹{PER_MONTH} a
                month. Goes back to ₹{SITE.fullPrice.toLocaleString("en-IN")} once
                the first {SITE.launchSeats} seats are gone.
              </p>

              <div className="seatbar">
                <div className="seatbar-track">
                  <div className="seatbar-fill" style={{ width: "18%" }} />
                </div>
                <span>Founding seats are limited to {SITE.launchSeats}.</span>
              </div>

              <ul className="tick-list">
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>Everything on the dashboard</b>, plus the members&apos; group,
                    meetups, deep dives and watchlist alerts.
                  </span>
                </li>
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>Your price is locked.</b> Founding members stay at ₹
                    {SITE.price.toLocaleString("en-IN")} on renewal, for as long as
                    you keep the membership.
                  </span>
                </li>
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>One year, paid once.</b> No monthly card charges, no
                    auto-renewal surprises.
                  </span>
                </li>
              </ul>

              {state === "done" ? (
                <div className="done">
                  <b>Your founding seat is reserved.</b>
                  <p>
                    We&apos;ll message you the moment the doors open, with joining
                    instructions and your locked price.
                  </p>
                  <a
                    className="wa-btn"
                    href={waLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ marginTop: 12 }}
                  >
                    <WaIcon /> Message us directly
                  </a>
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
                          placeholder="WhatsApp number"
                          aria-label="WhatsApp number"
                        />
                      </div>
                      <button type="submit" disabled={state === "sending"}>
                        {state === "sending" ? "Reserving…" : "Reserve my seat"}
                      </button>
                    </div>
                    {error && <p className="err">{error}</p>}
                  </form>
                  <p className="note" style={{ marginTop: 10 }}>
                    Nothing to pay today. We&apos;ll message you when the doors
                    open — your ₹{SITE.price.toLocaleString("en-IN")} price is held
                    until then.
                  </p>
                </>
              )}
            </div>

            <div>
              <div className="why-card" style={{ marginBottom: 14 }}>
                <h3>Why charge at all, if the filings are free?</h3>
                <p>
                  Because free groups fill with people who don&apos;t read. Anyone
                  joins a group that costs nothing, and within a month it&apos;s
                  tips, forwards and good-morning images.
                </p>
                <p>
                  <strong>
                    ₹{SITE.price.toLocaleString("en-IN")} a year is about ₹{PER_MONTH} a
                    month — deliberately small, deliberately not zero.
                  </strong>{" "}
                  Nobody serious is priced out. Nobody joins by accident.
                </p>
                <p>
                  The money keeps the lights on. The <em>price</em> keeps the room
                  worth being in.
                </p>
              </div>

              <div className="why-card">
                <h3>Who this is for</h3>
                <p>
                  People who already read filings, or want to and don&apos;t know
                  where to start. Investors holding twenty companies who can&apos;t
                  track them all. Traders who want to know what actually landed
                  before the noise starts.
                </p>
                <p>
                  <strong>It is not for you</strong> if you want buy-sell calls or
                  intraday tips. You will not get them here, and asking will get
                  you removed.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ---------------- what's inside ---------------- */}
        <section className="mk-sec">
          <div className="mk-sec-head">
            <p className="mk-kicker">What you get</p>
            <h2 className="mk-h2">Nine reasons it&apos;s worth ₹{PER_MONTH} a month</h2>
            <p className="mk-lead">
              The dashboard is the tool. The community is what makes it useful.
            </p>
          </div>

          <div className="feat-grid">
            {FEATURES.map((f) => (
              <div className="feat" key={f.title}>
                <div className="feat-ico" aria-hidden="true">
                  {f.icon}
                </div>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------- faq ---------------- */}
        <section className="mk-sec">
          <div className="mk-sec-head">
            <p className="mk-kicker">Straight answers</p>
            <h2 className="mk-h2">Before you join</h2>
          </div>

          <div className="mk-narrow faq">
            <details>
              <summary>Is this tips or recommendations?</summary>
              <p>
                No. We are not a SEBI-registered research analyst or investment
                adviser, and we will never tell you what to buy or sell. We
                summarise public filings and link the original. What members
                discuss between themselves is their own view, not ours.
              </p>
            </details>
            <details>
              <summary>Can I cancel? Do I get a refund?</summary>
              <p>
                You can leave the community whenever you like — there is no
                lock-in and no notice period.{" "}
                <strong>
                  The annual fee is non-refundable once you have joined.
                </strong>{" "}
                It is a one-year membership paid up front, and access continues to
                the end of the year you paid for. The two exceptions: if you are
                charged twice, or if we stop running the service during your year,
                you get your money back. Full detail is in the{" "}
                <a href="/refund">refund policy</a>.
              </p>
            </details>
            <details>
              <summary>Do I need to pay to read the filings?</summary>
              <p>
                No. The dashboard and the daily WhatsApp brief are free and stay
                free. ₹{SITE.price.toLocaleString("en-IN")} is for the community,
                the meetups, the deep dives and the watchlist alerts.
              </p>
            </details>
            <details>
              <summary>What happens after the first {SITE.launchSeats} members?</summary>
              <p>
                The price goes to ₹{SITE.fullPrice.toLocaleString("en-IN")} a year
                for everyone who joins after. If you are in the first{" "}
                {SITE.launchSeats}, you stay at ₹{SITE.price.toLocaleString("en-IN")}{" "}
                on every renewal for as long as you keep the membership.
              </p>
            </details>
            <details>
              <summary>When do the meetups start?</summary>
              <p>
                As soon as there are enough members in one city to make it worth
                everyone&apos;s evening. Mumbai is first — that is where we are.
                We will ask members before fixing anything.
              </p>
            </details>
            <details>
              <summary>What if a summary is wrong?</summary>
              <p>
                Sometimes one will be — they are written by AI. That is exactly why
                every card links to the original PDF. Tell us when you spot one and
                we fix it. Members do this, and it makes the product better for
                everyone.
              </p>
            </details>
            <details>
              <summary>How do I pay?</summary>
              <p>
                Not yet — we are opening to founding members first. Leave your
                details above and we will message you with joining instructions
                and a payment link when the doors open.
              </p>
            </details>
          </div>
        </section>

        <section className="mk-sec">
          <div className="finale">
            <h2>Read first. Decide later.</h2>
            <p>
              The dashboard is open and costs nothing. Use it for a week — if it
              earns a place in your evening, the room is next door.
            </p>
            <div className="mk-ctas">
              <a className="btn-lg btn-ghost" href="/dashboard">
                Open the dashboard
              </a>
              <a
                className="btn-lg btn-wa"
                href={waLink}
                target="_blank"
                rel="noopener noreferrer"
              >
                <WaIcon /> Ask us anything
              </a>
            </div>
          </div>
        </section>
      </main>

      <MkFooter />
    </>
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
