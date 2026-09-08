"use client";

// The SME dashboard.
//
// Same component as the main board, one parameter different. The two boards
// are genuinely different products - an SME company is a Rs 40 crore business
// with three analysts following it, sitting in the same feed as Reliance - but
// everything about how you read a filing is identical, so the page is not.
//
// Copying 580 lines to change a query parameter is how two pages drift until
// only one of them gets the next fix.

import Dashboard from "../dashboard/page";

export default function SmeDashboard() {
  return (
    <Dashboard
      board="SME"
      title="SME announcements"
      blurb="Companies listed on the BSE SME and NSE Emerge platforms. Smaller, less covered, and filed under the same rules as the main board."
    />
  );
}
