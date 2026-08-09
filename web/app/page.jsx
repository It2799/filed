"use client";

import { useState } from "react";

// Everything you'd want to rename lives here.
const SITE = {
  name: "Filed",
  // These are real figures measured from 7-8 Aug 2026. Update them when they drift.
  filedPerDay: "3,671",
  importantPerDay: "250",
  readTime: "under 10 min",

  // Contact shown at the bottom of the page.
  contactPhoneDisplay: "+91 82204 40146",
  contactPhoneDigits: "918220440146",   // wa.me needs country code, digits only
  contactEmail: "market.tide27@gmail.com",
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

function WaIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.25-.46-2.38-1.47-.88-.78-1.47-1.75-1.65-2.05-.17-.3-.02-.46.13-.6.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.6-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.47s1.06 2.86 1.21 3.06c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.72 2-1.41.25-.69.25-1.28.17-1.41-.07-.13-.27-.2-.57-.35z"/>
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm0 18.15h-.01a8.22 8.22 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23 2.2 0 4.27.86 5.83 2.42a8.18 8.18 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.24 8.23z"/>
    </svg>
  );
}

// The number people message to confirm WhatsApp. Defaults to the contact number
// above; override with NEXT_PUBLIC_WHATSAPP_NUMBER if you get a separate business
// line later. Digits only, with country code.
const WA_NUMBER = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER || SITE.contactPhoneDigits;

export default function Home() {
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [state, setState] = useState("idle"); // idle | sending | done | error
  const [error, setError] = useState("");
  const [already, setAlready] = useState(false);
  const [gaveWhatsApp, setGaveWhatsApp] = useState(false);
  const [whatsappSent, setWhatsappSent] = useState(false);

  const waLink = WA_NUMBER
    ? `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(
        "Hi, I just joined the Filed waitlist. Please send me updates on WhatsApp.")}`
    : null;

  async function submit(e) {
    e.preventDefault();
    if (state === "sending") return;
    setState("sending");
    setError("");

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, phone, company, source: "landing" }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Something went wrong. Try again?");
        setState("error");
        return;
      }
      setAlready(Boolean(data.alreadyJoined));
      setGaveWhatsApp(Boolean(data.gaveWhatsApp));
      setWhatsappSent(Boolean(data.whatsappSent));
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
              We&apos;ll message you when it opens up — and nothing else. No
              newsletter, no passing your details to anyone.
            </p>

            {gaveWhatsApp && !whatsappSent && waLink && (
              <>
                <p className="confirm-ask">
                  One last step to switch WhatsApp on — send us a message so
                  WhatsApp lets us reply. Takes a second.
                </p>
                <a className="wa-btn" href={waLink} target="_blank" rel="noopener">
                  <WaIcon /> Confirm on WhatsApp
                </a>
              </>
            )}
            {gaveWhatsApp && whatsappSent && (
              <p className="confirm-ask">
                We&apos;ve sent a confirmation to your WhatsApp.
              </p>
            )}
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
              </div>

              <div className="row phone-row">
                <div className="phone-wrap">
                  <span className="cc">+91</span>
                  <input
                    className="phone"
                    type="tel"
                    inputMode="numeric"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="WhatsApp number (optional)"
                    aria-label="WhatsApp number, optional"
                    autoComplete="tel-national"
                    maxLength={14}
                  />
                </div>
                <button type="submit" disabled={state === "sending"}>
                  {state === "sending" ? "Joining…" : "Join the waitlist"}
                </button>
              </div>

              {error && <p className="err">{error}</p>}
            </form>
            <p className="note">
              Free while we build. No card, no spam. Give us your WhatsApp and
              you&apos;ll get the alerts there instead of buried in email.
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

      <section className="section">
        <h2>Want to know more?</h2>
        <div className="contact">
          <a
            className="wa-btn"
            href={`https://wa.me/${SITE.contactPhoneDigits}?text=${encodeURIComponent(
              "Hi, I'd like to know more about Filed.")}`}
            target="_blank"
            rel="noopener"
          >
            <WaIcon /> {SITE.contactPhoneDisplay}
          </a>
          <a className="mail-btn" href={`mailto:${SITE.contactEmail}`}>
            {SITE.contactEmail}
          </a>
        </div>
        <p className="note contact-note">
          Message us on WhatsApp or drop an email — we answer both.
        </p>
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
