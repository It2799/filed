import Nav from "../Nav";
import MkFooter from "../MkFooter";
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
          <h1 className="mk-h1">The morning brief</h1>
          <p className="mk-sub">
            One PDF, every morning at 7. The fifty filings from yesterday that
            were actually worth knowing about — what was announced, the numbers,
            and why it matters. Concall invitations and slide decks are left
            out; this is for things that happened.
          </p>

          {latest ? (
            <div className="brief-latest">
              <div>
                <span className="brief-kicker">Latest issue</span>
                <b>{pretty(latest)}</b>
                <span className="brief-day">{weekday(latest)}</span>
              </div>
              <a className="brief-cta" href={`/brief/${latest}`}>
                Read the brief →
              </a>
            </div>
          ) : (
            <p className="brief-empty">
              The first issue goes out tomorrow morning. In the meantime the
              full archive is on the <a href="/dashboard">dashboard</a>.
            </p>
          )}
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
