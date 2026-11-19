const $ = (id) => document.getElementById(id);
chrome.storage.local.get("cfg").then(({ cfg }) => { $("u").value = cfg?.apiUrl || "http://localhost:18080"; $("t").value = cfg?.token || ""; });
$("s").onclick = async () => {
  let origin; try { origin = new URL($("u").value).origin; } catch { $("m").textContent = "Invalid URL"; return; }
  const ok = await chrome.permissions.request({ origins: [origin + "/*"] });  // only the origin the user typed
  if (!ok) { $("m").textContent = "Permission to contact that server was not granted."; return; }
  await chrome.storage.local.set({ cfg: { apiUrl: origin, token: $("t").value.trim() } });
  $("m").textContent = "Saved.";
};
