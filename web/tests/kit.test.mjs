import assert from "node:assert/strict";

const requests = [];
global.fetch = async (url, init) => {
  requests.push({ url, init });
  return Response.json({ subscriber: { id: 42 } });
};

const kit = await import("../lib/kit.js");
delete process.env.KIT_API_KEY;
assert.equal((await kit.upsertSubscriber("reader@example.com")).skipped, true);
assert.equal(requests.length, 0);

process.env.KIT_API_KEY = "test-kit-key";
const result = await kit.upsertSubscriber("reader@example.com");
assert.equal(result.ok, true);
assert.equal(requests[0].url, "https://api.kit.com/v4/subscribers");
assert.equal(requests[0].init.headers["X-Kit-Api-Key"], "test-kit-key");
assert.deepEqual(JSON.parse(requests[0].init.body), {
  email_address: "reader@example.com",
  state: "active",
});
console.log("Kit subscriber sync: all checks pass");
