import { SITE, PRICE_LABEL } from "./site";

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-in">
        <a className="nav-brand" href="/">
          <span className="dot" /> {SITE.name}
        </a>
        <div className="nav-links">
          <a href="/dashboard">Dashboard</a>
          <a href="/brief">Daily brief</a>
          <a className="nav-cta" href="/join">
            {SITE.free ? "Join free" : `Join · ${PRICE_LABEL}`}
          </a>
        </div>
      </div>
    </nav>
  );
}
