import { SITE } from "./site";

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-in">
        <a className="nav-brand" href="/">
          <span className="dot" /> {SITE.name}
        </a>
        <div className="nav-links">
          <a href="/dashboard">Dashboard</a>
          <a href={SITE.newsletterLink} target="_blank" rel="noopener noreferrer">
            Free brief
          </a>
          <a className="nav-cta" href="/join">
            Join · ₹{SITE.price.toLocaleString("en-IN")}
          </a>
        </div>
      </div>
    </nav>
  );
}
