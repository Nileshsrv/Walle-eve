// Assembles the static Netlify site: HTML pages, static assets, and the Python sources that the
// browser loads into Pyodide to run app.py (see static/pybridge.js).
import fs from 'fs';
import path from 'path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const out = path.resolve(root, process.env.OUT_DIR || 'dist');
const copy = (src, dst) => { fs.mkdirSync(path.dirname(path.join(out, dst)), {recursive: true}); fs.copyFileSync(path.join(root, src), path.join(out, dst)); };
const list = dir => fs.existsSync(path.join(root, dir)) ? fs.readdirSync(path.join(root, dir)).map(f => `${dir}/${f}`) : [];

fs.rmSync(out, {recursive: true, force: true});
copy('templates/landing.html', 'index.html');
copy('templates/index.html', 'mission.html');
copy('templates/guide.html', 'guide.html');
for (const f of list('static')) copy(f, f);

const py = ['app.py', ...list('walle_eve').filter(f => f.endsWith('.py')), ...list('configs'), ...list('data/runs'), 'results/LEADERBOARD.md']
  .filter(f => fs.existsSync(path.join(root, f)));
for (const f of py) copy(f, `py/${f}`);
fs.writeFileSync(path.join(out, 'py/manifest.json'), JSON.stringify(py));
console.log(`Built ${out}: ${py.length} Python-side files`);
