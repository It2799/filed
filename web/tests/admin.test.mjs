import assert from "node:assert/strict";

process.env.NODE_ENV = "production";
process.env.ADMIN_PASSWORD = "test-password";
process.env.ADMIN_SESSION_SECRET = "test-admin-secret-with-enough-entropy";

const admin = await import("../lib/admin-auth.js");

assert.equal(admin.adminConfigured(), true);
assert.equal(admin.correctAdminPassword("wrong"), false);
assert.equal(admin.correctAdminPassword("test-password"), true);

const token = admin.createAdminSession();
const header = admin.adminCookie(token);
assert.match(header, /HttpOnly/);
assert.match(header, /SameSite=Strict/);
assert.match(header, /Secure/);

const request = new Request("https://example.test/api/admin/stats", {
  headers: { cookie: header.split(";")[0] },
});
assert.equal(admin.isAdmin(request), true);

const tampered = new Request("https://example.test/api/admin/stats", {
  headers: { cookie: `mt_admin_session=${token.slice(0, -1)}x` },
});
assert.equal(admin.isAdmin(tampered), false);

process.env.NODE_ENV = "development";
assert.doesNotMatch(admin.adminCookie(token), /Secure/);

delete process.env.ADMIN_PASSWORD;
assert.equal(admin.adminConfigured(), false);
assert.equal(admin.isAdmin(request), false);

console.log("Admin authentication: all checks pass");
