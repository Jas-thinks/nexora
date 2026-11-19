chrome.storage.local.get(["status", "queue", "cfg"]).then(({ status, queue, cfg }) => {
  document.getElementById("s").textContent = !cfg?.token ? "Not set up yet." : status ? `${status.ok ? "✓" : "⚠"} ${status.msg}` : "Waiting for a submission.";
  document.getElementById("q").textContent = `${(queue || []).length} waiting to upload`;
});
document.getElementById("o").onclick = () => chrome.runtime.openOptionsPage();
