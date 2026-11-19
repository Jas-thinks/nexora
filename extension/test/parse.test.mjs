import test from "node:test";
import assert from "node:assert/strict";
import { buildItem, enqueue, slugFromLocation, submissionIdFromUrl } from "../parse.js";

const PAGE = "https://leetcode.com/problems/two-sum/description/";
const URL_OK = "/submissions/detail/1234567890/check/";
const NOW = Date.parse("2026-11-19T10:00:00Z");
const ok = { state: "SUCCESS", status_msg: "Accepted", lang: "python3", status_runtime: "45 ms", task_finish_time: NOW - 5000 };

test("slug and id extraction", () => {
  assert.equal(slugFromLocation(PAGE), "two-sum");
  assert.equal(slugFromLocation("https://leetcode.com/problemset/all/"), null);
  assert.equal(slugFromLocation("https://evil.com/problems/two-sum/"), null);
  assert.equal(submissionIdFromUrl(URL_OK), "1234567890");
  assert.equal(submissionIdFromUrl("/submissions/detail/runcode_abc123/check/"), null); // the Run button is not a submission
});
test("final accepted result becomes an item without any code", () => {
  const it = buildItem(URL_OK, ok, PAGE, NOW);
  assert.deepEqual(it, { id: "1234567890", problem_url: "https://leetcode.com/problems/two-sum/", verdict: "Accepted", submitted_at: new Date(NOW - 5000).toISOString(), language: "python3", time_ms: 45 });
  assert.deepEqual(Object.keys(it).sort(), ["id", "language", "problem_url", "submitted_at", "time_ms", "verdict"]); // no code field at all
});
test("intermediate polls, runcode, other pages and malformed bodies produce nothing", () => {
  assert.equal(buildItem(URL_OK, { state: "PENDING" }, PAGE, NOW), null);
  assert.equal(buildItem(URL_OK, { state: "STARTED", status_msg: "Accepted" }, PAGE, NOW), null);
  assert.equal(buildItem("/submissions/detail/runcode_1/check/", ok, PAGE, NOW), null);
  assert.equal(buildItem(URL_OK, ok, "https://leetcode.com/contest/", NOW), null);
  assert.equal(buildItem(URL_OK, null, PAGE, NOW), null);
  assert.equal(buildItem(URL_OK, { state: "SUCCESS" }, PAGE, NOW), null);
});
test("implausible finish times fall back to now; runtime is optional", () => {
  assert.equal(buildItem(URL_OK, { ...ok, task_finish_time: NOW + 9e9 }, PAGE, NOW).submitted_at, new Date(NOW).toISOString());
  assert.equal(buildItem(URL_OK, { ...ok, status_runtime: "N/A" }, PAGE, NOW).time_ms, null);
});
test("queue dedupes by submission id and is bounded", () => {
  const a = buildItem(URL_OK, ok, PAGE, NOW);
  assert.equal(enqueue(enqueue([], a), a).length, 1);
  let q = []; for (let i = 0; i < 600; i++) q = enqueue(q, { ...a, id: String(i) });
  assert.equal(q.length, 500); assert.equal(q[499].id, "599");
});
