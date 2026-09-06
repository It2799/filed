"use client";

import { usePathname } from "next/navigation";
import { SITE, PRICE_LABEL } from "./site";
import { useSiteAuth } from "./SiteAuth";

export default function Nav() {
  const pathname = usePathname();
  const { user, openAuth, logout } = useSiteAuth();

  async function signOut() {
    await logout();
    window.location.href = "/";
  }

  return (
    <nav className="nav">
      <div className="nav-in">
        <a className="nav-brand" href="/">
          <span className="dot" /> {SITE.name}
        </a>
        <div className="nav-links">
          <a href="/dashboard">Dashboard</a>
          <a href="/brief">Daily brief</a>
          {user ? (
            <button type="button" className="nav-account" onClick={signOut}>Log out</button>
          ) : (
            <button
              type="button"
              className="nav-account"
              onClick={() => openAuth({ clear: true, returnTo: pathname === "/" ? "/dashboard" : null })}
            >
              Sign in
            </button>
          )}
          <a className="nav-cta" href="/join">
            {SITE.free ? "Join free" : `Join · ${PRICE_LABEL}`}
          </a>
        </div>
      </div>
    </nav>
  );
}
