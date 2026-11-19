import { buildItem, enqueue } from "./parse.js";

const get = (k) => chrome.storage.local.get(k).then((o) => o[k]);
const set = (o) => chrome.storage.local.set(o);

async function flush() {
  const cfg = (await get("cfg")) || {};
  let queue = (await get("queue")) || [];
  if (!cfg.apiUrl || !cfg.token || !queue.length) return;
  const batch = queue.slice(0, 50);
  try {
    const res = await fetch(cfg.apiUrl.replace(/\/$/, "") + "/capture/submissions", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${cfg.token}` },
      body: JSON.stringify({ platform: "leetcode", submissions: batch }) });
    if (res.status === 401) { await set({ status: { ok: false, msg: "Token rejected. Create a new one in Nexora > Settings.", at: Date.now() } }); return; }
    if (!res.ok) throw new Error("HTTP " + res.status);
    const j = await res.json();
    queue = queue.slice(batch.length);
    await set({ queue, status: { ok: true, msg: `Uploaded ${j.added} new (${j.duplicates} already known, ${j.rejected_count} rejected)`, at: Date.now() } });
    if (queue.length) flush();
  } catch (e) {
    await set({ status: { ok: false, msg: "Will retry: " + (e.message || e), at: Date.now() } });
    chrome.alarms.create("retry", { delayInMinutes: 2 });
  }
}

chrome.runtime.onMessage.addListener((m, sender) => {
  if (sender.id !== chrome.runtime.id || m?.type !== "check") return;
  (async () => {
    const item = buildItem(m.url, m.body, m.page);
    if (!item) return;
    await set({ queue: enqueue((await get("queue")) || [], item) });
    flush();
  })();
});
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "retry") flush(); });
chrome.runtime.onStartup.addListener(flush);
