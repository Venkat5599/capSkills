// Pulse — LIVE heartbeat endpoint (Vercel Node serverless, zero deps).
//
// Computes the REAL Pulse velocity series from the last 30 days of hourly
// klines (free Binance public API, no key) using the exact same math as
// scripts/velocity.py — so the dashboard EKG is live, not a frozen file, and
// every number on the card (pulse, threshold, regime, picks) is internally
// consistent because they all come from this one computation.
//
//   speed_i(t) = |logret_i(t)| / rolling_std(logret_i, 168)
//   Pulse(t)   = mean_i speed_i(t)
//   threshold  = 90th percentile of Pulse over the window
//   regime     = CALM | PANIC (fast+falling) | EUPHORIA (fast+rising)

const BASKET = ["ETH","XRP","DOGE","ADA","LINK","BCH","LTC","AVAX","DOT","UNI",
  "ATOM","FIL","INJ","FET","CAKE","TRX","SHIB","TON","AAVE","LDO"];
const BINANCE = "https://api.binance.com/api/v3/klines";
const CMC_BASE = "https://pro-api.coinmarketcap.com";
const LIMIT = 720;          // 30 days of hourly bars (<= Binance 1000 max/call)
const VOL_WINDOW = 168;     // 1-week rolling vol baseline (matches velocity.py)
const MIN_PERIODS = VOL_WINDOW / 2;
const PANIC_Q = 0.90;
const K = 5;

// Conviction = velocity regime + CMC Fear & Greed agreement (matches api/pulse.js).
function conviction(regime, fg) {
  if (fg == null) return { grade: "MEDIUM", reason: "price signal only; F&G unavailable", fear_greed: null };
  fg = Number(fg);
  const label = fg <= 25 ? "extreme fear" : fg <= 45 ? "fear" : fg <= 55 ? "neutral" : fg < 75 ? "greed" : "extreme greed";
  let grade, reason;
  if (regime === "PANIC" && fg <= 25) { grade = "HIGH"; reason = "velocity panic + extreme fear agree (capitulation)"; }
  else if (regime === "EUPHORIA" && fg >= 75) { grade = "HIGH"; reason = "velocity euphoria + extreme greed agree (momentum)"; }
  else if (regime === "PANIC" && fg <= 45) { grade = "MEDIUM"; reason = "velocity panic + fearful crowd"; }
  else if (regime === "EUPHORIA" && fg >= 55) { grade = "MEDIUM"; reason = "velocity euphoria + greedy crowd"; }
  else if (regime === "CALM") { grade = "LOW"; reason = "calm regime — no trade"; }
  else { grade = "LOW"; reason = "velocity and sentiment disagree; size down or wait"; }
  return { grade, reason, fear_greed: fg, fg_label: label };
}

// Sample standard deviation (ddof=1) to match pandas .std().
function sampleStd(xs) {
  const n = xs.length;
  if (n < 2) return NaN;
  const m = xs.reduce((a, b) => a + b, 0) / n;
  const v = xs.reduce((a, b) => a + (b - m) ** 2, 0) / (n - 1);
  return Math.sqrt(v);
}

// Linear-interpolation quantile (matches numpy/pandas default).
function quantile(sorted, q) {
  const n = sorted.length;
  if (!n) return NaN;
  const pos = (n - 1) * q;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

async function fetchCloses(sym, signal) {
  const url = `${BINANCE}?symbol=${sym}USDT&interval=1h&limit=${LIMIT}`;
  const r = await fetch(url, { signal });
  if (!r.ok) throw new Error(`${sym} ${r.status}`);
  const rows = await r.json();
  // [openTime, open, high, low, close, ...] — key close by bar open time.
  const out = new Map();
  for (const row of rows) out.set(row[0], Number(row[4]));
  return out;
}

async function fearGreed(key, signal) {
  if (!key) return null;
  try {
    const r = await fetch(CMC_BASE + "/v3/fear-and-greed/latest", {
      headers: { "X-CMC_PRO_API_KEY": key, Accept: "application/json" }, signal,
    });
    if (r.ok) return (await r.json())?.data?.value ?? null;
  } catch { /* optional */ }
  return null;
}

module.exports = async function handler(req, res) {
  const ctrl = AbortSignal.timeout(20000);
  let maps;
  try {
    maps = await Promise.all(BASKET.map((s) => fetchCloses(s, ctrl).catch(() => null)));
  } catch {
    res.status(502).json({ error: "klines unavailable" });
    return;
  }

  // Build the union of bar timestamps (sorted) from whichever symbols returned.
  const tset = new Set();
  const closesBySym = {};
  BASKET.forEach((s, i) => {
    if (maps[i] && maps[i].size) { closesBySym[s] = maps[i]; for (const t of maps[i].keys()) tset.add(t); }
  });
  const times = [...tset].sort((a, b) => a - b);
  const syms = Object.keys(closesBySym);
  if (syms.length < 3 || times.length < VOL_WINDOW) {
    res.status(502).json({ error: "insufficient kline data" });
    return;
  }

  // Per-symbol log-return series aligned to `times`, then rolling-std speed.
  // speed[symIdx][tIdx], logret[symIdx][tIdx] (NaN where undefined).
  const T = times.length;
  const logret = {}, speed = {};
  for (const s of syms) {
    const closes = closesBySym[s];
    const lr = new Array(T).fill(NaN);
    let prev = null;
    for (let i = 0; i < T; i++) {
      const c = closes.get(times[i]);
      if (c != null && prev != null && prev > 0 && c > 0) lr[i] = Math.log(c / prev);
      prev = c != null ? c : prev;
    }
    logret[s] = lr;
    const sp = new Array(T).fill(NaN);
    for (let i = 0; i < T; i++) {
      if (Number.isNaN(lr[i])) continue;
      const start = Math.max(0, i - VOL_WINDOW + 1);
      const win = [];
      for (let j = start; j <= i; j++) if (!Number.isNaN(lr[j])) win.push(lr[j]);
      if (win.length < MIN_PERIODS) continue;
      const sd = sampleStd(win);
      if (sd && Number.isFinite(sd)) sp[i] = Math.abs(lr[i]) / sd;
    }
    speed[s] = sp;
  }

  // Aggregate across the basket per timestamp: Pulse = mean speed, dir = mean logret.
  const series = [];
  for (let i = 0; i < T; i++) {
    let ssum = 0, scount = 0, lsum = 0, lcount = 0;
    for (const s of syms) {
      if (!Number.isNaN(speed[s][i])) { ssum += speed[s][i]; scount++; }
      if (!Number.isNaN(logret[s][i])) { lsum += logret[s][i]; lcount++; }
    }
    if (scount > 0) series.push({ t: times[i], pulse: ssum / scount, dir: lcount ? lsum / lcount : 0 });
  }
  if (series.length < 10) { res.status(502).json({ error: "no pulse series" }); return; }

  const threshold = quantile(series.map((p) => p.pulse).sort((a, b) => a - b), PANIC_Q);
  for (const p of series) p.regime = p.pulse <= threshold ? "CALM" : (p.dir < 0 ? "PANIC" : "EUPHORIA");

  const last = series[series.length - 1];
  const lastIdx = T - 1;
  // Picks from the latest bar's per-token returns.
  const ranked = syms
    .map((s) => ({ s, r: logret[s][lastIdx] }))
    .filter((o) => !Number.isNaN(o.r))
    .sort((a, b) => a.r - b.r);
  let picks = [], action = "FLAT";
  if (last.regime === "PANIC") { picks = ranked.slice(0, K).map((o) => o.s); action = "FADE_LONG"; }
  else if (last.regime === "EUPHORIA") { picks = ranked.slice(-K).reverse().map((o) => o.s); action = "MOMENTUM_LONG"; }

  const fg = await fearGreed(process.env.CMC_API_KEY, ctrl);

  res.setHeader("Cache-Control", "s-maxage=300, stale-while-revalidate=600");
  res.status(200).json({
    source: "Binance public klines (live, 30d hourly) — same math as the skill",
    live: true,
    generated_at: new Date().toISOString(),
    window_days: 30,
    bars: series.length,
    symbols: syms.length,
    threshold: Math.round(threshold * 1000) / 1000,
    pulse_index: Math.round(last.pulse * 1000) / 1000,
    direction_1h: Math.round(last.dir * 100 * 1000) / 1000,
    regime: last.regime,
    action, picks,
    fear_greed: fg,
    conviction: conviction(last.regime, fg),
    // Compact series for the EKG (drop NaN, round).
    series: series.map((p) => ({
      t: new Date(p.t).toISOString(),
      pulse: Math.round(p.pulse * 1000) / 1000,
      regime: p.regime,
    })),
  });
};
