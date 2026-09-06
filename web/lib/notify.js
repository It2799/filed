/** Transactional email (OTP, welcome, contact) through Gmail SMTP. */

import nodemailer from "nodemailer";

const SUPPORT = process.env.REPLY_TO_EMAIL || "market.tide27@gmail.com";
let transporters;

export function emailConfigured() {
  return Boolean(process.env.SMTP_USER && process.env.SMTP_PASS);
}

export async function diagnoseEmailConnection() {
  if (!emailConfigured()) return { configured: false, attempts: [] };
  const attempts = [];
  for (const client of mailers()) {
    try {
      await client.verify();
      attempts.push({ port: client.options.port, secure: client.options.secure, ok: true });
      return { configured: true, connected: true, attempts };
    } catch (error) {
      attempts.push({
        port: client.options.port,
        secure: client.options.secure,
        ok: false,
        code: error.code || null,
        responseCode: error.responseCode || null,
        command: error.command || null,
      });
    }
  }
  return { configured: true, connected: false, attempts };
}

function mailers() {
  if (!emailConfigured()) return [];
  if (transporters) return transporters;

  const host = process.env.SMTP_HOST || "smtp.gmail.com";
  const primaryPort = Number(process.env.SMTP_PORT || 465);
  const primarySecure = process.env.SMTP_SECURE == null
    ? primaryPort === 465
    : String(process.env.SMTP_SECURE) !== "false";
  const credentials = {
    user: process.env.SMTP_USER.trim(),
    // Google displays app passwords in four groups. Vercel values sometimes
    // keep those spaces, while Gmail expects the underlying 16 characters.
    pass: process.env.SMTP_PASS.replace(/\s+/g, ""),
  };
  const connections = [{ port: primaryPort, secure: primarySecure }];
  if (host === "smtp.gmail.com") {
    const fallback = primaryPort === 465
      ? { port: 587, secure: false }
      : { port: 465, secure: true };
    connections.push(fallback);
  }

  transporters = connections.map(({ port, secure }) => nodemailer.createTransport({
    host,
    port,
    secure,
    requireTLS: !secure,
    auth: credentials,
    connectionTimeout: 10000,
    greetingTimeout: 10000,
    socketTimeout: 15000,
  }));
  return transporters;
}

function from() {
  return process.env.TRANSACTIONAL_FROM || `Market Tide <${process.env.SMTP_USER}>`;
}

async function deliver(message) {
  const clients = mailers();
  if (!clients.length) return { sent: false, reason: "email not configured" };
  let lastError;
  for (const client of clients) {
    try {
      const info = await client.sendMail({ from: from(), replyTo: SUPPORT, ...message });
      return { sent: true, id: info.messageId };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

export const WELCOME_EMAIL = Object.freeze({
    subject: "Welcome to Market Tide — your member access is ready",
    text:
      "Hi there,\n\n"
      + "Welcome to Market Tide.\n\n"
      + "Your free member access is now ready. We built Market Tide to help you understand important NSE and BSE company filings without spending hours reading every document.\n\n"
      + "Here’s what you now have access to:\n\n"
      + "• Market Dashboard: Important company announcements explained in simple language, with links to the original filings.\n"
      + "• Daily Brief: A focused morning summary of the filings that matter.\n"
      + "• Member Access: Sign in securely using your email and a six-digit OTP—no password to remember.\n"
      + "• Equity Markets Club: Connect with people who take markets, businesses and research seriously.\n\n"
      + "Open your dashboard: https://markettide.in/dashboard\n"
      + "Read the Daily Brief: https://markettide.in/brief\n"
      + "Join the community: https://markettide.in/join\n\n"
      + "A quick reminder: Market Tide provides information and summaries, not investment advice. AI-generated summaries can contain mistakes, so always check the original exchange filing before making any decision.\n\n"
      + "If you have any questions, simply reply to this email. We read every response.\n\n"
      + "Welcome aboard,\nMarket Tide\nNSE & BSE filings, made easier to understand\nEmail: market.tide27@gmail.com\nContact: +91 82004 40146\nhttps://markettide.in\n\n"
      + "Don’t want to receive emails from us? Reply with Unsubscribe, and we’ll remove you.\n",
    html:
      '<div style="max-width:620px;margin:0 auto;font-family:Arial,sans-serif;color:#17191d;line-height:1.65">'
      + '<p>Hi there,</p><p><strong>Welcome to Market Tide.</strong></p>'
      + '<p>Your free member access is now ready. We built Market Tide to help you understand important NSE and BSE company filings without spending hours reading every document.</p>'
      + '<p><strong>Here’s what you now have access to:</strong></p><ul>'
      + '<li><strong>Market Dashboard:</strong> Important company announcements explained in simple language, with links to the original filings.</li>'
      + '<li><strong>Daily Brief:</strong> A focused morning summary of the filings that matter.</li>'
      + '<li><strong>Member Access:</strong> Sign in securely using your email and a six-digit OTP—no password to remember.</li>'
      + '<li><strong>Equity Markets Club:</strong> Connect with people who take markets, businesses and research seriously.</li></ul>'
      + '<p><a href="https://markettide.in/dashboard"><strong>Open your dashboard</strong></a><br>'
      + '<a href="https://markettide.in/brief"><strong>Read the Daily Brief</strong></a><br>'
      + '<a href="https://markettide.in/join"><strong>Join the community</strong></a></p>'
      + '<p><small>A quick reminder: Market Tide provides information and summaries, not investment advice. AI-generated summaries can contain mistakes, so always check the original exchange filing before making any decision.</small></p>'
      + '<p>If you have any questions, simply reply to this email. We read every response.</p>'
      + '<p>Welcome aboard,<br><strong>Market Tide</strong><br>NSE &amp; BSE filings, made easier to understand<br>Email: <a href="mailto:market.tide27@gmail.com">market.tide27@gmail.com</a><br>Contact: <a href="tel:+918200440146">+91 82004 40146</a><br><a href="https://markettide.in">markettide.in</a></p>'
      + '<p><small>Don’t want to receive emails from us? Reply with <strong>Unsubscribe</strong>, and we’ll remove you.</small></p></div>',
});

export async function sendWelcomeEmail(to) {
  return deliver({ to, ...WELCOME_EMAIL });
}

export const sendEmail = sendWelcomeEmail;

export async function sendEmailCode(to, code) {
  return deliver({
    to,
    subject: `${code} is your Market Tide sign-in code`,
    text:
      `Your sign-in code is ${code}\n\n`
      + "It works for the next 10 minutes and can be used once.\n\n"
      + "If you did not ask to sign in, ignore this email. Without this code nobody can access your account.\n",
  });
}

export async function sendContactMessage({ name, email, message }) {
  return deliver({
    to: SUPPORT,
    replyTo: email,
    subject: `Market Tide contact: ${name}`,
    text: `From: ${name} <${email}>\n\n${message}`,
  });
}
