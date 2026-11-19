// Runs in the PAGE's JS context so it can observe the site's own polling requests. It reads responses only; it never modifies them
// and never reads the code editor. Results are handed to content.js via window.postMessage.
(() => {
  if (window.__nexoraCapture) return;
  window.__nexoraCapture = true;
  const RE = /\/submissions\/detail\/\d+\/check\/?(\?|$)/;
  const emit = (url, body) => window.postMessage({ source: "nexora-capture", url, body }, window.location.origin);
  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    const res = await origFetch.apply(this, args);
    try { const url = typeof args[0] === "string" ? args[0] : args[0]?.url; if (RE.test(url || "")) res.clone().json().then((b) => emit(url, b)).catch(() => {}); } catch (e) {}
    return res;
  };
  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    if (RE.test(String(url))) this.addEventListener("load", () => { try { emit(String(url), JSON.parse(this.responseText)); } catch (e) {} });
    return open.call(this, method, url, ...rest);
  };
})();
