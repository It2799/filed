import Nav from "../Nav";
import MkFooter from "../MkFooter";
import { SITE } from "../site";
import { briefDays } from "../../lib/brief";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "The morning brief — Market Tide",
  description:
    "One PDF every morning: the fifty NSE and BSE filings from yesterday that "
    + "were worth knowing about, in plain English. Free to read and to forward.",
};

function pretty(iso) {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-IN", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
}

function weekday(iso) {
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-IN", {
    weekday: "long", timeZone: "UTC",
  });
}

export default async function BriefIndex() {
  const days = await briefDays();
  const [latest, ...rest] = days;

  return (
    <>
      <Nav />
      <main className="mk">
        <section className="brief-hero">
          <p className="mk-kicker">Daily free brief · morning newsletter</p>
          <h1 className="mk-h1">The morning brief</h1>
          <p className="mk-sub">
            One PDF, free, every morning at 7:30. The fifty filings that were
            actually worth knowing about — what happened, the key numbers, and
            why it matters. Concall invitations, slide decks, dividends and
            splits are left out; this is for things that happened.
          </p>

          {latest ? (
            <div className="brief-latest">
              <div>
                <span className="brief-kicker">Latest issue</span>
                <b>{pretty(latest)}</b>
                <span className="brief-day">{weekday(latest)}</span>
              </div>
              <div className="brief-actions">
                <a className="brief-cta" href={`/brief/${latest}`}>
                  Read the brief →
                </a>
                <a
                  className="brief-dl"
                  href={`/brief/${latest}?download=1`}
                  aria-label={`Download the brief for ${pretty(latest)} as a PDF`}
                >
                  Download PDF
                </a>
              </div>
            </div>
          ) : (
            <p className="brief-empty">
              The first issue goes out tomorrow morning. In the meantime the
              full archive is on the <a href="/dashboard">dashboard</a>.
            </p>
          )}

          <div className="brief-get">
            <a className="btn-lg btn-grad" href="/subscribe">
              Get it every morning
            </a>
            <a
              className="btn-lg btn-wa"
              href={SITE.newsletterLink}
              target="_blank"
              rel="noopener noreferrer"
            >
              Join the WhatsApp community
            </a>
          </div>
          <p className="mk-ctanote">
            Free either way. One email a day, or the same brief posted in the
            group.
          </p>
        </section>

        {rest.length > 0 && (
          <section className="section">
            <h2>Earlier issues</h2>
            <ul className="brief-list">
              {rest.map((d) => (
                <li key={d}>
                  <a href={`/brief/${d}`}>
                    <b>{pretty(d)}</b>
                    <span>{weekday(d)}</span>
                  </a>
                  <a className="brief-dl sm" href={`/brief/${d}?download=1`}>
                    Download
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
      <MkFooter />
    </>
  );
}
