import { configured as usersConfigured } from "./users.js";

export function authReady() {
  return Boolean(usersConfigured() && process.env.AUTH_SECRET);
}
