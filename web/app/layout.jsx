import "./globals.css";

export const metadata = {
  title: "Filed — the NSE & BSE filings that actually matter",
  description:
    "Around 3,600 corporate announcements are filed with NSE and BSE every day. "
    + "About 250 matter. Filed reads all of them and sends you the ones that do, "
    + "in plain English.",
  openGraph: {
    title: "Filed — the NSE & BSE filings that actually matter",
    description:
      "3,600 filings a day. 250 matter. We read all of them so you don't have to.",
    type: "website",
  },
};

export const viewport = { themeColor: "#0e1116" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
