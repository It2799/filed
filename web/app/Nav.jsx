"use client";

import { useEffect, useState } from "react";
import { SITE, PRICE_LABEL } from "./site";

export default function Nav() {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    let active = true;
    const syncAuthentication = (event) => {
      if (active) setSignedIn(Boolean(event.detail?.signedIn));
    };
    window.addEventListener("market-tide-auth", syncAuthentication);
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => response.json())
      .then((data) => active && setSignedIn(Boolean(data.user)))
      .catch(() => {});
    return () => {
      active = false;
      window.removeEventListener("market-tide-auth", syncAuthentication);
    };
  }, []);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
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
          {signedIn ? (
            <button type="button" className="nav-account" onClick={logout}>Log out</button>
          ) : (
            <a href="/login">Sign in</a>
          )}
          <a className="nav-cta" href="/join">
            {SITE.free ? "Join free" : `Join · ${PRICE_LABEL}`}
          </a>
        </div>
      </div>
    </nav>
  );
}
