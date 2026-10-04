// Applies the saved light/dark choice before first paint. A separate file (not inline)
// so the Content-Security-Policy can be script-src 'self' with no inline exceptions.
try {
  const t = JSON.parse(localStorage.getItem("ts:v1:theme"));
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
} catch (_e) {}
