// Pure functions (no browser APIs) so they can be unit-tested with `node --test`.
// FIELD NAMES BELOW COME FROM THE AUTHOR'S KNOWLEDGE OF LEETCODE'S PRIVATE WEB API AND HAVE NOT BEEN CHECKED AGAINST THE LIVE SITE.
// The parser is deliberately strict: if anything needed is missing it returns null and nothing is sent.

export const CHECK_URL = /\/submissions\/detail\/([^/]+)\/check\/?(?:\?|$)/;

/** "https://leetcode.com/problems/two-sum/description/" -> "two-sum" (or null) */
export function slugFromLocation(href) {
  const m = /^https:\/\/leetcode\.com\/problems\/([a-z0-9-]+)(?:[/?#]|$)/.exec(href || "");
  return m ? m[1] : null;
}

/** id from the polled URL. "runcode_..." ids are the "Run" button (not a real submission) and are rejected. */
export function submissionIdFromUrl(url) {
  const m = CHECK_URL.exec(url || "");
  return m && /^\d{1,20}$/.test(m[1]) ? m[1] : null;
}

/** LeetCode's poll returns many intermediate states; only a finished SUCCESS state has a final verdict. */
export function buildItem(url, body, pageHref, now = Date.now()) {
  const id = submissionIdFromUrl(url);
  const slug = slugFromLocation(pageHref);
  if (!id || !slug || !body || typeof body !== "object") return null;
  if (body.state !== "SUCCESS" || typeof body.status_msg !== "string" || !body.status_msg) return null;
  const finished = Number(body.task_finish_time);
  const at = Number.isFinite(finished) && finished > 1e12 && finished <= now + 300000 ? finished : now;
  const m = /^(\d+)\s*ms$/.exec(String(body.status_runtime || ""));
  return {
    id,
    problem_url: `https://leetcode.com/problems/${slug}/`,
    verdict: body.status_msg,
    submitted_at: new Date(at).toISOString(),
    language: typeof body.lang === "string" ? body.lang.slice(0, 40) : null,
    time_ms: m ? Number(m[1]) : null,
  };
}

/** Queue helper: merge by id (a retry or a double poll must not duplicate). */
export function enqueue(queue, item, max = 500) {
  if (!item || queue.some((q) => q.id === item.id && q.problem_url === item.problem_url)) return queue;
  return [...queue, item].slice(-max);
}
