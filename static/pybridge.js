/* Runs app.py (Flask) inside the browser via Pyodide and routes /api/* fetches to it.
   Netlify serves static files only, so the Flask app is executed client-side with app.test_client(). */
(() => {
  const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
  const banner = document.createElement('div');
  banner.style.cssText = 'position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:9999;padding:8px 14px;border-radius:8px;' +
    'background:rgba(10,16,24,.92);border:1px solid rgba(0,212,232,.4);color:#cfe;font:500 12px Inter,system-ui,sans-serif';
  banner.textContent = 'Booting Python runtime…';
  const show = () => document.body && document.body.appendChild(banner);
  document.body ? show() : document.addEventListener('DOMContentLoaded', show);

  const ready = (async () => {
    await new Promise((ok, err) => { const s = document.createElement('script'); s.src = PYODIDE + 'pyodide.js'; s.onload = ok; s.onerror = err; document.head.appendChild(s); });
    const py = await loadPyodide({indexURL: PYODIDE});
    banner.textContent = 'Loading numpy + Flask…';
    await py.loadPackage(['numpy', 'micropip']);
    await py.runPythonAsync('import micropip\nawait micropip.install("flask")');
    banner.textContent = 'Loading app.py…';
    const files = await (await nativeFetch('/py/manifest.json')).json();
    await Promise.all(files.map(async f => {
      const buf = new Uint8Array(await (await nativeFetch('/py/' + f)).arrayBuffer());
      py.FS.mkdirTree('/app/' + f.split('/').slice(0, -1).join('/'));
      py.FS.writeFile('/app/' + f, buf);
    }));
    py.runPython('import sys, os\nsys.path.insert(0, "/app"); os.chdir("/app")\nimport app as _app\n_client = _app.app.test_client()');
    banner.remove();
    return py;
  })().catch(e => { banner.textContent = 'Python runtime failed to load: ' + e; throw e; });

  const nativeFetch = window.fetch.bind(window);
  async function request(path, init = {}) {
    const py = await ready;
    py.globals.set('_req', py.toPy({path, method: (init.method || 'GET').toUpperCase(), body: init.body || ''}));
    const res = py.runPython(`_r = _client.open(_req["path"], method=_req["method"], data=_req["body"], content_type="application/json")
(_r.status_code, _r.get_data(as_text=True), _r.mimetype, _r.headers.get("Content-Disposition", ""))`).toJs();
    const [status, text, type, disposition] = res;
    return new Response(text, {status, headers: {'Content-Type': type, 'Content-Disposition': disposition}});
  }
  window.fetch = (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    return url.origin === location.origin && url.pathname.startsWith('/api/') ? request(url.pathname + url.search, init) : nativeFetch(input, init);
  };

  // Download links that point at the API (e.g. Briefing) must go through the in-browser server too.
  document.addEventListener('click', async e => {
    const a = e.target.closest && e.target.closest('a[href^="/api/"]');
    if (!a) return;
    e.preventDefault();
    const r = await window.fetch(a.getAttribute('href'));
    const name = (/filename=([^;]+)/.exec(r.headers.get('Content-Disposition') || '') || [])[1] || 'download';
    const link = document.createElement('a');
    link.href = URL.createObjectURL(await r.blob()); link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });
})();
