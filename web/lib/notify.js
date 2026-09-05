/** Transactional email (OTP, welcome, contact) through Gmail SMTP. */

import nodemailer from "nodemailer";

const SUPPORT = process.env.REPLY_TO_EMAIL || "market.tide27@gmail.com";
let transporter;

export function emailConfigured() {
  return Boolean(process.env.SMTP_USER && process.env.SMTP_PASS);
}

function mailer() {
  if (!emailConfigured()) return null;
  if (!transporter) {
    transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || "smtp.gmail.com",
      port: Number(process.env.SMTP_PORT || 465),
      secure: String(process.env.SMTP_SECURE || "true") !== "false",
      auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS },
      connectionTimeout: 6000,
      greetingTimeout: 6000,
      socketTimeout: 10000,
    });
  }
  return transporter;
}

function from() {
  return process.env.TRANSACTIONAL_FROM || `Market Tide <${process.env.SMTP_USER}>`;
}

async function deliver(message) {
  const client = mailer();
  if (!client) return { sent: false, reason: "email not configured" };
  const info = await client.sendMail({ from: from(), replyTo: SUPPORT, ...message });
  return { sent: true, id: info.messageId };
}

export async function sendWelcomeEmail(to) {
  return deliver({
    to,
    subject: "Welcome to Market Tide",
    text:
      "Welcome to Market Tide.\n\n"
      + "Your account is ready. You can now open the Dashboard and Daily Brief using your email. "
      + "On future sign-ins we will remember your mobile number, so you only need your email and the six-digit code.\n\n"
      + "Market Tide summarises public exchange filings. It is not investment advice.\n",
  });
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

/** Best-effort welcome notification; saving a signup must not depend on SMTP. */
export async function confirm({ email }) {
  try {
    return { email: await sendWelcomeEmail(email) };
  } catch (error) {
    console.error("[notify] email failed:", error.message || error);
    return { email: { sent: false, error: String(error.message || error) } };
  }
}
