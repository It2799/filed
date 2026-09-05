import assert from "node:assert/strict";
import test from "node:test";

const { GET } = await import("../app/api/cron/brief/route.js");

test("brief cron is hidden when CRON_SECRET is absent", async () => {
  delete process.env.CRON_SECRET;
  const response = await GET(new Request("https://example.test/api/cron/brief"));
  assert.equal(response.status, 404);
});

test("brief cron rejects a request without Vercel's bearer token", async () => {
  process.env.CRON_SECRET = "cron-test-secret";
  const response = await GET(new Request("https://example.test/api/cron/brief"));
  assert.equal(response.status, 404);
});

test("brief cron reports a missing GitHub worker token", async () => {
  process.env.CRON_SECRET = "cron-test-secret";
  delete process.env.GITHUB_DISPATCH_TOKEN;
  const response = await GET(new Request("https://example.test/api/cron/brief", {
    headers: { Authorization: "Bearer cron-test-secret" },
  }));
  assert.equal(response.status, 503);
});
