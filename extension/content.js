// Isolated-world relay: page -> extension. Only forwards messages that originate from our own injected script on this origin.
window.addEventListener("message", (e) => {
  if (e.source !== window || e.origin !== window.location.origin || !e.data || e.data.source !== "nexora-capture") return;
  try { chrome.runtime.sendMessage({ type: "check", url: String(e.data.url), body: e.data.body, page: window.location.href }); } catch (err) {}
});
