const $ = id => document.getElementById(id), $$ = s => [...document.querySelectorAll(s)];
const CY = '0,243,255', MG = '255,0,85';
const S = {meta:null, frames:[], idx:0, live:true, sum:null, timer:null, hover:null, pin:null, pulse:0, raf:null,
  tab:'reason', view:'post', numbers:false, on:{belief:1, plan:1, decoys:1, clues:1, cred:0, pf:0, eve:0}};
const cur = () => S.frames[S.idx];
const head = () => S.frames.length - 1;

async function call(path, body) {
  const r = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  return r.json();
}
function fit(cv, h) {
  const d = window.devicePixelRatio || 1, w = cv.clientWidth, hh = h || cv.clientHeight;
  if (cv.width !== Math.round(w * d) || cv.height !== Math.round(hh * d)) { cv.width = Math.round(w * d); cv.height = Math.round(hh * d); }
  const g = cv.getContext('2d'); g.setTransform(d, 0, 0, d, 0, 0); g.clearRect(0, 0, w, hh); return [g, w, hh];
}
const obsAt = (r, c) => S.meta.obstacles.some(o => o[0] === r && o[1] === c);

/* ---------- mission control ---------- */
function formBody() {
  return {seed:+$('seed').value, eve_seed:$('eveSeed').value, agent:$('agent').value,
          threat:document.querySelector('input[name=th]:checked').value, stress:$('hard').checked ? 'hard' : 'none'};
}
function ingest(d, live) {
  S.meta = d.meta; S.frames = d.frames; S.sum = d.summary; S.live = live; S.idx = head(); S.pin = null;
  const m = S.meta; $('seed').value = m.seed; $('eveSeed').value = m.eve_seed ?? ''; if ([...$('agent').options].some(o => o.value === m.agent)) $('agent').value = m.agent;
  document.querySelector(`input[name=th][value=${m.threat}]`).checked = true; $('hard').checked = !!(m.stress && m.stress.dropout);
  render();
}
async function launch(body) { stop(); ingest(await call('/api/reset', body || formBody()), true); }
async function reroll() { const b = formBody(); b.eve_seed = Math.floor(Math.random() * 9000) + 1; $('eveSeed').value = b.eve_seed; launch(b); }
async function stepOnce() {
  if (S.idx < head()) { S.idx++; return render(); }
  if (!S.live || S.sum.done) return stop();
  const d = await call('/api/step', {n:1}); S.frames.push(...d.frames); S.sum = d.summary; S.idx = head(); S.pulse = 1; render();
}
async function toEnd() {
  stop();
  if (S.live && !S.sum.done) { const d = await call('/api/step', {n:400}); S.frames.push(...d.frames); S.sum = d.summary; }
  S.idx = head(); render();
}
function stop() { clearInterval(S.timer); S.timer = null; $('bPlay').textContent = 'Run'; }
function play() {
  if (S.timer) return stop();
  $('bPlay').textContent = 'Pause';
  const tick = async () => { if (S.idx >= head() && (!S.live || S.sum.done)) return stop(); await stepOnce(); };
  S.timer = setInterval(tick, 1050 - $('speed').value * 100);
}

/* ---------- drawing: map ---------- */
const peakOf = b => { let m = -1, p = [0, 0]; b.forEach((row, r) => row.forEach((v, c) => { if (v > m) { m = v; p = [r, c]; } })); return p; };
function drawMap() {
  const cv = $('map'), wrap = cv.parentElement, side = Math.max(240, Math.min(wrap.clientWidth, window.innerWidth > 1100 ? (wrap.clientHeight || 560) : 760, 760));
  cv.style.width = cv.style.height = side + 'px';
  const [g, W] = fit(cv, side), f = cur(), n = S.meta.size, cs = W / n, cx = c => (c + .5) * cs;
  g.strokeStyle = '#161b25'; g.lineWidth = 1;
  for (let i = 0; i <= n; i++) { g.beginPath(); g.moveTo(i * cs, 0); g.lineTo(i * cs, W); g.moveTo(0, i * cs); g.lineTo(W, i * cs); g.stroke(); }
  g.fillStyle = '#232a38'; S.meta.obstacles.forEach(([r, c]) => g.fillRect(c * cs + 1, r * cs + 1, cs - 2, cs - 2));
  if (S.on.belief) { const mx = Math.max(...f.belief.flat());
    f.belief.forEach((row, r) => row.forEach((p, c) => { if (p > 0) { g.fillStyle = `rgba(${CY},${Math.min(.92, Math.sqrt(p / mx) * .85)})`; g.fillRect(c * cs + 1, r * cs + 1, cs - 2, cs - 2); } })); }
  if (S.on.pf && f.pf) { const mx = Math.max(...f.pf.flat(), 1);
    g.fillStyle = '#fff'; f.pf.forEach((row, r) => row.forEach((k, c) => { if (k) { g.globalAlpha = .35 + .6 * k / mx; g.beginPath(); g.arc(cx(c), cx(r), 1.5 + 2.5 * Math.sqrt(k / mx), 0, 7); g.fill(); } })); g.globalAlpha = 1; }
  if (S.on.cred) { g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 1; g.setLineDash([2, 2]); f.cred90.forEach(([r, c]) => g.strokeRect(c * cs + 2.5, r * cs + 2.5, cs - 5, cs - 5)); g.setLineDash([]); }
  S.meta.pads.forEach(([r, c]) => { g.strokeStyle = '#ffb454'; g.lineWidth = 2; g.strokeRect(c * cs + 4, r * cs + 4, cs - 8, cs - 8);
    g.fillStyle = '#ffb454'; g.font = `${cs * .42}px Inter`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('⚡', cx(c), cx(r) + 1); });
  if (S.on.decoys) S.meta.decoys.forEach(({pos:[r, c], amp}) => { g.strokeStyle = `rgba(${MG},.7)`; g.lineWidth = 1.4;
    [.28, .5, .72].forEach(k => { g.beginPath(); g.setLineDash(k > .4 ? [3, 4] : []); g.arc(cx(c), cx(r), cs * k * (1 + amp / 6), 0, 7); g.stroke(); });
    g.setLineDash([]); g.fillStyle = `rgb(${MG})`; g.beginPath(); g.arc(cx(c), cx(r), cs * .08, 0, 7); g.fill(); });
  if (S.on.clues) f.clues.forEach(([r, c]) => { g.save(); g.translate(cx(c), cx(r)); g.rotate(Math.PI / 4); g.strokeStyle = '#5ce1a0'; g.lineWidth = 2;
    g.strokeRect(-cs * .17, -cs * .17, cs * .34, cs * .34); g.restore(); });
  if (S.on.plan) {
    g.strokeStyle = 'rgba(255,255,255,.3)'; g.lineWidth = 2; g.beginPath();
    S.frames.slice(0, S.idx + 1).forEach((fr, i) => i ? g.lineTo(cx(fr.walle[1]), cx(fr.walle[0])) : g.moveTo(cx(fr.walle[1]), cx(fr.walle[0]))); g.stroke();
    if (f.plan.length > 1) { g.strokeStyle = `rgb(${CY})`; g.setLineDash([5, 5]); g.beginPath(); f.plan.forEach(([r, c], i) => i ? g.lineTo(cx(c), cx(r)) : g.moveTo(cx(c), cx(r))); g.stroke(); g.setLineDash([]); } }
  const pk = peakOf(f.belief); g.strokeStyle = '#fff'; g.lineWidth = 1.5; g.setLineDash([2, 3]); g.beginPath(); g.arc(cx(pk[1]), cx(pk[0]), cs * .42, 0, 7); g.stroke(); g.setLineDash([]);
  [[S.hover, 'rgba(255,255,255,.55)'], [S.pin, `rgb(${CY})`]].forEach(([h, col]) => { if (h) { g.strokeStyle = col; g.lineWidth = 2; g.strokeRect(h[1] * cs + 1, h[0] * cs + 1, cs - 2, cs - 2); } });
  if (S.pulse > 0 && f.mode === 'scan') { g.strokeStyle = `rgba(${CY},${S.pulse * .7})`; g.lineWidth = 2; g.beginPath(); g.arc(cx(f.walle[1]), cx(f.walle[0]), cs * (1.2 + (1 - S.pulse) * n * .35), 0, 7); g.stroke(); }
  if (S.on.eve || f.captured) { const [r, c] = f.eve; g.fillStyle = `rgb(${MG})`; g.shadowColor = `rgb(${MG})`; g.shadowBlur = 14; g.beginPath(); g.arc(cx(c), cx(r), cs * .3, 0, 7); g.fill(); g.shadowBlur = 0; }
  const [r, c] = f.walle; g.fillStyle = '#0b0d12'; g.strokeStyle = `rgb(${CY})`; g.lineWidth = 2.5; g.shadowColor = `rgb(${CY})`; g.shadowBlur = 12;
  g.beginPath(); g.rect(cx(c) - cs * .3, cx(r) - cs * .22, cs * .6, cs * .44); g.fill(); g.stroke(); g.shadowBlur = 0;
  g.fillStyle = `rgb(${CY})`; g.fillRect(cx(c) - cs * .17, cx(r) - cs * .06, cs * .1, cs * .12); g.fillRect(cx(c) + cs * .07, cx(r) - cs * .06, cs * .1, cs * .12);
}
function describe(rc) {
  const [r, c] = rc, f = cur(), has = a => a.some(o => o[0] === r && o[1] === c);
  const kind = obsAt(r, c) ? 'obstacle' : has(S.meta.pads) ? 'recharge pad' : S.meta.decoys.some(d => d.pos[0] === r && d.pos[1] === c) ? 'decoy beacon'
    : has(f.clues) ? 'clue token' : (f.walle[0] === r && f.walle[1] === c) ? 'WALL-E' : 'free';
  const p = f.belief[r][c], rank = f.belief.flat().filter(v => v > p).length + 1, d = Math.hypot(r - f.walle[0], c - f.walle[1]);
  const truth = (S.on.eve || f.captured) && f.eve[0] === r && f.eve[1] === c ? ' · <b>EVE is here</b>' : '';
  const o = kind === 'obstacle';
  return `(${r},${c}) ${kind}${truth}<br>p(EVE) <b>${o ? '–' : (p * 100).toFixed(2) + '%'}</b> · rank ${o ? '–' : '#' + rank} · dist ${d.toFixed(1)} · expected signal ${Math.exp(-d / 5).toFixed(3)}`;
}
function info() {
  if (!S.meta) return; const t = $('tip'), sel = S.pin || S.hover;
  if (S.hover) { t.hidden = false; t.innerHTML = describe(S.hover); } else t.hidden = true;
  $('cellInfo').innerHTML = sel ? (S.pin ? 'Pinned ' : '') + describe(sel) : 'Hover a cell to inspect it. Click to pin.';
}
function cellAt(ev) { const b = $('map').getBoundingClientRect(), n = S.meta.size;
  const c = Math.floor((ev.clientX - b.left) / b.width * n), r = Math.floor((ev.clientY - b.top) / b.height * n); return r >= 0 && c >= 0 && r < n && c < n ? [r, c] : null; }
function mapEvents() { const cv = $('map');
  cv.addEventListener('mousemove', ev => { if (!S.meta) return; S.hover = cellAt(ev); info();
    const t = $('tip'), pb = cv.parentElement.getBoundingClientRect(), x = ev.clientX - pb.left, y = ev.clientY - pb.top, w = t.offsetWidth, h = t.offsetHeight;
    t.style.left = Math.max(0, Math.min(x + 12, pb.width - w)) + 'px'; t.style.top = (y + h + 24 > pb.height ? y - h - 12 : y + 12) + 'px'; drawMap(); });
  cv.addEventListener('mouseleave', () => { S.hover = null; info(); S.meta && drawMap(); });
  cv.addEventListener('click', ev => { const c = cellAt(ev); S.pin = S.pin && c && S.pin[0] === c[0] && S.pin[1] === c[1] ? null : c; info(); drawMap(); }); }
function pulse() { cancelAnimationFrame(S.raf); const t0 = performance.now();
  const f = t => { S.pulse = Math.max(0, 1 - (t - t0) / 800); drawMap(); if (S.pulse > 0) S.raf = requestAnimationFrame(f); }; S.raf = requestAnimationFrame(f); }

/* ---------- rail ---------- */
function drawRail() {
  const f = cur(), m = S.meta, sp = f.spend, st = $('status'), pct = Math.max(0, f.battery / m.battery_max * 100);
  $('batNum').textContent = f.battery; $('batMax').textContent = m.battery_max;
  $('gFill').style.height = pct + '%'; $('gFill').classList.toggle('low', f.battery <= f.reserve);
  $('gReserve').style.bottom = Math.min(100, f.reserve / m.battery_max * 100) + '%'; $('resNote').textContent = 'reserve ' + f.reserve;
  const row = (k, v) => `<dt>${k}</dt><dd>${v}</dd>`, ex = S.sum.metrics && S.sum.metrics.baseline_log_loss;
  $('vitals').innerHTML = row('entropy', `${f.entropy.toFixed(2)} / ${Math.log(m.nfree).toFixed(2)}`) + row('info gain', (f.info_gain >= 0 ? '+' : '') + f.info_gain.toFixed(2) + ' nats')
    + row('90% set', f.cred90.length + ' cells') + row('steps left', m.max_steps - f.step) + row('moves / scans', `${sp.moves} / ${sp.scans}`)
    + row('blocked', sp.blocked) + row('move cost', sp.move_cost) + row('scan cost', sp.scan_cost) + row('charges used', sp.charges) + row('clues taken', sp.clues)
    + (f.pf ? row('grid↔particles KL', f.kl.toFixed(2)) : '');
  const multi = m.qs.length > 1; $('qSec').hidden = false;
  $('qTrue').textContent = `true q ${m.true_q}` + (multi ? '' : ` · assumes ${m.qs[0]}`);
  $('qBars').innerHTML = m.qs.map((q, i) => `<div class="qrow ${Math.abs(q - m.true_q) < .021 ? 'true' : ''}"><span>${q.toFixed(2)}</span><div class="b"><i style="width:${f.q[i] * 100}%"></i></div><span>${(f.q[i] * 100).toFixed(0)}%</span></div>`).join('');
  st.className = 'status mono ' + (f.captured ? 'win' : f.dead ? 'dead' : '');
  st.textContent = f.captured ? `EVE captured · step ${f.step}` : f.dead ? 'battery depleted' : `mode · ${f.mode}`;
  $('runLabel').textContent = `${m.agent_label} · ${m.threat}${m.stress && m.stress.dropout ? ' · hard sensors' : ''} · map ${m.seed}${m.eve_seed != null ? ' · eve ' + m.eve_seed : ''}${S.live ? '' : ' · recording'}`;
  $('pos').textContent = `step ${f.step} / ${S.frames[head()].step}  ·  ${S.idx === head() ? (S.live ? 'live' : 'end') : 'replay'}`;
}

/* ---------- dock ---------- */
function drawLog() {
  const el = $('log'), stick = el.scrollTop + el.clientHeight >= el.scrollHeight - 40;
  el.innerHTML = S.frames.slice(0, S.idx + 1).map((l, i) => `<div data-i="${i}" class="${/captured/.test(l.reason) ? 'win' : l.mode} ${i === S.idx ? 'cur' : ''}"><span class="t">${String(l.step).padStart(3, '0')}</span> <b>${l.action}</b> · bat ${l.battery} · H ${l.entropy.toFixed(2)}<br>${l.reason}${l.options.length ? `<span class="opt">options: ${l.options.join('  ')}</span>` : ''}</div>`).join('');
  if (stick) el.scrollTop = el.scrollHeight;
}
function heat(cv, M, flat, numbers, scale) {
  const [g, W] = fit(cv, cv.clientWidth), n = M.length, cs = W / n, mx = Math.max(...M.flat()) || 1;
  M.forEach((row, r) => row.forEach((v, c) => { const o = obsAt(r, c);
    g.fillStyle = o ? '#1a1f2b' : `rgba(${CY},${flat ? .1 : Math.sqrt(v / mx) * .95})`; g.fillRect(c * cs, r * cs, cs, cs);
    if (numbers && !o) { g.fillStyle = v / mx > .5 ? '#001417' : '#aab3c4'; g.font = `${Math.max(7, cs * .36)}px "JetBrains Mono",monospace`; g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(Math.round(v * scale) || '·', c * cs + cs / 2, r * cs + cs / 2); } }));
  const [wr, wc] = cur().walle; g.strokeStyle = '#fff'; g.lineWidth = 1; g.strokeRect(wc * cs, wr * cs, cs, cs);
}
function drawUpdate() {
  const f = cur(), noScan = f.mode !== 'scan' && f.step > 0 && !f.lik.flat().some(v => v < .999);
  heat($('tPrior'), f.prior); heat($('tLik'), f.lik, noScan); heat($('tPost'), f.belief);
  $('likCap').textContent = noScan ? 'Likelihood (none)' : 'Likelihood';
  $$('#thumbs button').forEach(b => b.classList.toggle('on', b.dataset.v === S.view));
  const M = {prior:f.prior, lik:f.lik, post:f.belief}[S.view];
  heat($('big'), M, S.view === 'lik' && noScan, S.numbers, S.view === 'lik' ? 100 : 1000);
  $('vHint').textContent = S.numbers ? (S.view === 'lik' ? 'likelihood ×100 (relative to max)' : 'probability in ‰') : '';
  $('vHeat').setAttribute('aria-pressed', !S.numbers); $('vNum').setAttribute('aria-pressed', S.numbers);
}
function axesChart(cv, draw) { const [g, W, H] = fit(cv); const pad = {l:26, r:6, t:8, b:16};
  const X = (v, a, b) => pad.l + (v - a) / ((b - a) || 1) * (W - pad.l - pad.r), Y = (v, a, b) => H - pad.b - (v - a) / ((b - a) || 1) * (H - pad.t - pad.b);
  g.strokeStyle = '#1c212c'; g.fillStyle = '#7a8395'; g.font = '9px "JetBrains Mono",monospace'; g.lineWidth = 1;
  g.beginPath(); g.moveTo(pad.l, pad.t); g.lineTo(pad.l, H - pad.b); g.lineTo(W - pad.r, H - pad.b); g.stroke(); draw(g, X, Y, W, H, pad); }
function drawScores() {
  const f = cur(), m = (S.sum.metrics || {}), sc = f.m || {}, fm = S.frames.slice(0, S.idx + 1);
  const card = (k, v, s) => `<div class="card"><span>${k}</span><b>${v}</b><small>${s}</small></div>`;
  $('cards').innerHTML = card('ROC-AUC', (sc.roc_auc ?? 0).toFixed(3), 'cell ranking, mean per step') + card('Log loss', (sc.log_loss ?? 0).toFixed(2), `nats · ignorant ${m.baseline_log_loss?.toFixed(2) ?? '–'}`)
    + card('Brier', (sc.brier ?? 0).toFixed(3), `${(sc.brier_cell ?? 0).toFixed(4)} per cell`) + card('Top-1 / Top-3', `${((sc.top1 ?? 0) * 100).toFixed(0)}% · ${((sc.top3 ?? 0) * 100).toFixed(0)}%`, 'running hit rate')
    + card('90% set', (sc.cred90_size ?? 0).toFixed(1), 'cells, running mean') + card('Calibration', (sc.ece ?? 0).toFixed(4), 'ECE · lower is better')
    + card('Info gained', (m.total_info_gain ?? 0).toFixed(1), 'nats over the run') + card('Pooled AUC', (m.roc_auc_pooled ?? 0).toFixed(3), 'all cells, all steps');
  const N = Math.max(fm.length - 1, 1), Hm = Math.log(S.meta.nfree);
  axesChart($('chUnc'), (g, X, Y, W, H, pd) => {
    [[fm.map(x => x.entropy / Hm), `rgb(${CY})`], [fm.map(x => x.cred90.length / S.meta.nfree), '#ffb454']].forEach(([s, col]) => { g.strokeStyle = col; g.lineWidth = 1.6; g.beginPath(); s.forEach((v, i) => i ? g.lineTo(X(i, 0, N), Y(v, 0, 1)) : g.moveTo(X(i, 0, N), Y(v, 0, 1))); g.stroke(); });
    g.fillText('1', 14, pd.t + 6); g.fillText('0', 14, H - pd.b); g.fillText('step ' + N, W - 52, H - 4); });
  const gm = Math.max(0.5, ...fm.map(x => Math.abs(x.info_gain)));
  axesChart($('chGain'), (g, X, Y, W, H, pd) => { const z = Y(0, -gm, gm), bw = Math.max(2, (W - pd.l - pd.r) / (N + 1) - 1);
    fm.forEach((x, i) => { g.fillStyle = x.info_gain >= 0 ? `rgb(${CY})` : `rgb(${MG})`; const y = Y(x.info_gain, -gm, gm); g.fillRect(X(i, 0, N) - bw / 2, Math.min(y, z), bw, Math.abs(y - z)); });
    g.fillText('+' + gm.toFixed(1), 2, pd.t + 6); g.fillText('-' + gm.toFixed(1), 2, H - pd.b); });
  const sq = Math.sqrt;
  axesChart($('chCal'), (g, X, Y, W, H, pd) => { g.strokeStyle = '#2a3140'; g.beginPath(); g.moveTo(X(0, 0, 1), Y(0, 0, 1)); g.lineTo(X(1, 0, 1), Y(1, 0, 1)); g.stroke();
    (m.calibration || []).filter(b => b.n).forEach(b => { g.fillStyle = `rgba(${CY},.85)`; g.beginPath(); g.arc(X(sq(b.pred), 0, 1), Y(sq(b.obs), 0, 1), 2 + Math.log10(b.n + 1), 0, 7); g.fill(); });
    g.fillText('observed', 2, pd.t + 6); g.fillText('claimed (√ scale)', W - 90, H - 4); });
  axesChart($('chRoc'), (g, X, Y, W, H, pd) => { g.strokeStyle = '#2a3140'; g.beginPath(); g.moveTo(X(0, 0, 1), Y(0, 0, 1)); g.lineTo(X(1, 0, 1), Y(1, 0, 1)); g.stroke();
    g.strokeStyle = `rgb(${CY})`; g.lineWidth = 1.8; g.beginPath(); (m.roc || []).forEach(([x, y], i) => i ? g.lineTo(X(x, 0, 1), Y(y, 0, 1)) : g.moveTo(X(x, 0, 1), Y(y, 0, 1))); g.stroke();
    g.fillText('TPR', 2, pd.t + 6); g.fillText('FPR', W - 24, H - 4); });
  $('rocCap').innerHTML = `ROC, pooled <em>AUC ${(m.roc_auc_pooled ?? 0).toFixed(3)}</em>`;
  const d = m.detection || {}, pc = v => v == null ? '–' : (v * 100).toFixed(0) + '%';
  $('detect').innerHTML = `Detection claim: “my best 3×3 holds ≥ half my belief”, scored against EVE within one cell.<br>TP <b>${d.tp ?? 0}</b> · FP <b>${d.fp ?? 0}</b> · FN <b>${d.fn ?? 0}</b> · TN <b>${d.tn ?? 0}</b> &nbsp; precision <b>${pc(d.precision)}</b> · recall <b>${pc(d.recall)}</b>`
    + `<br>Charts show the run up to the playhead; ROC, calibration and detection cover the whole run so far.`;
}

/* ---------- timeline / transport ---------- */
function drawTimeline() {
  const [g, W, H] = fit($('timeline')), F = S.frames, N = Math.max(F.length, 24), x = i => 6 + i / (N - 1) * (W - 12), Hm = Math.log(S.meta.nfree);
  F.forEach((f, i) => { const w = Math.max(3, (W - 12) / N - 1);
    if (f.mode === 'return' || f.mode === 'recharge') { g.fillStyle = 'rgba(255,180,84,.16)'; g.fillRect(x(i) - w / 2, 0, w, H); }
    if (f.info_gain > 0) { g.fillStyle = `rgba(${CY},.22)`; g.fillRect(x(i) - w / 2, H - 4 - Math.min(f.info_gain / 1.5, 1) * H * .45, w, Math.min(f.info_gain / 1.5, 1) * H * .45); } });
  g.beginPath(); g.moveTo(x(0), H); F.forEach((f, i) => g.lineTo(x(i), H - 4 - f.entropy / Hm * (H - 16))); g.lineTo(x(F.length - 1), H); g.closePath();
  g.fillStyle = `rgba(${CY},.12)`; g.fill(); g.strokeStyle = `rgb(${CY})`; g.lineWidth = 1.5; g.beginPath(); F.forEach((f, i) => i ? g.lineTo(x(i), H - 4 - f.entropy / Hm * (H - 16)) : g.moveTo(x(i), H - 4 - f.entropy / Hm * (H - 16))); g.stroke();
  F.forEach((f, i) => { if (f.mode === 'scan' || f.mode === 'clue') { g.fillStyle = f.mode === 'clue' ? '#5ce1a0' : `rgb(${CY})`; g.beginPath(); g.arc(x(i), 7, 2.4, 0, 7); g.fill(); } });
  const last = F[F.length - 1]; if (last.captured) { g.fillStyle = `rgb(${MG})`; g.beginPath(); g.arc(x(F.length - 1), 7, 4, 0, 7); g.fill(); }
  g.strokeStyle = '#fff'; g.lineWidth = 1.5; g.beginPath(); g.moveTo(x(S.idx), 0); g.lineTo(x(S.idx), H); g.stroke();
  g.fillStyle = '#7a8395'; g.font = '9px "JetBrains Mono",monospace'; g.fillText('entropy · ● scan  ▮ info gain  ▒ recharge', 8, H - 6);
}
function seek(ev) { const b = $('timeline').getBoundingClientRect(), N = Math.max(S.frames.length, 24); S.idx = Math.max(0, Math.min(head(), Math.round((ev.clientX - b.left - 6) / (b.width - 12) * (N - 1)))); render(); }

/* ---------- render ---------- */
function render() {
  if (!S.meta) return;
  drawRail(); drawMap(); info(); drawTimeline();
  if (S.tab === 'reason') drawLog(); else if (S.tab === 'update') drawUpdate(); else drawScores();
  if (S.pulse > 0 && cur().mode === 'scan' && S.idx === head() && !matchMedia('(prefers-reduced-motion: reduce)').matches) pulse();
}
function setTab(t) { S.tab = t; $$('.tabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.t === t)); ['reason', 'update', 'scores'].forEach(k => $('pane-' + k).hidden = k !== t); render(); }

/* ---------- wiring ---------- */
$('btnLaunch').onclick = () => launch(); $('btnReroll').onclick = reroll;
$('bPlay').onclick = play; $('bNext').onclick = () => { stop(); stepOnce(); }; $('bBack').onclick = () => { stop(); S.idx = Math.max(0, S.idx - 1); render(); };
$('bFirst').onclick = () => { stop(); S.idx = 0; render(); }; $('bLast').onclick = toEnd;
$('speed').oninput = () => { if (S.timer) { stop(); play(); } };
$$('.tabs button').forEach(b => b.onclick = () => setTab(b.dataset.t));
$$('#chips .chip').forEach(b => b.onclick = () => { const k = b.dataset.k; S.on[k] = S.on[k] ? 0 : 1; b.setAttribute('aria-pressed', !!S.on[k]); S.meta && (drawMap(), info()); });
$$('#thumbs button').forEach(b => b.onclick = () => { S.view = b.dataset.v; drawUpdate(); });
$('vHeat').onclick = () => { S.numbers = false; drawUpdate(); }; $('vNum').onclick = () => { S.numbers = true; drawUpdate(); };
$('log').addEventListener('click', e => { const d = e.target.closest('[data-i]'); if (d) { stop(); S.idx = +d.dataset.i; render(); } });
let drag = false; $('timeline').addEventListener('mousedown', e => { drag = true; stop(); seek(e); });
window.addEventListener('mousemove', e => drag && seek(e)); window.addEventListener('mouseup', () => drag = false);
$('btnSave').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify({meta:S.meta, frames:S.frames, summary:S.sum})], {type:'application/json'}));
  a.download = `recording_seed${S.meta.seed}_${S.meta.agent}.json`; a.click(); };
$('openFile').onchange = async e => { const f = e.target.files[0]; if (!f) return; stop(); const d = JSON.parse(await f.text()); ingest(d, false); S.idx = 0; render(); };
$('recSel').onchange = async e => { if (!e.target.value) return; stop(); ingest(await call('/api/runs/' + e.target.value), false); S.idx = 0; render(); e.target.value = ''; };
document.addEventListener('keydown', e => { if (/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
  if (e.code === 'Space') { e.preventDefault(); play(); } else if (e.key === 'ArrowRight') { stop(); stepOnce(); } else if (e.key === 'ArrowLeft') { stop(); S.idx = Math.max(0, S.idx - 1); render(); }
  else if (e.key === 'Home') { stop(); S.idx = 0; render(); } else if (e.key === 'End') toEnd(); else if (e.key.toLowerCase() === 'r') launch(); });
window.addEventListener('resize', () => S.meta && render());
(async () => {
  mapEvents();
  const [ags, runs] = await Promise.all([call('/api/agents'), call('/api/runs')]);
  $('agent').innerHTML = ags.map(a => `<option value="${a.id}">${a.label}</option>`).join(''); $('agent').value = 'v2';
  $('recSel').innerHTML += runs.map(r => `<option>${r}</option>`).join('');
  ingest(await call('/api/state'), true);
})();
