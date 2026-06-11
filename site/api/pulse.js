// Pulse — live agent endpoint (Vercel Node serverless, zero deps).
//
// A judge types a question in the site chat box -> this function computes the
// LIVE Pulse signal from CoinMarketCap (server-side key) using the SAME logic as
// scripts/cmc_live.py, then has a free DeepSeek model narrate it as the agent.
// No install, no key handed out. Degrades to the cached backtest signal if CMC
// or the LLM is unavailable, so the demo never looks broken.

const BASKET = ["ETH","XRP","DOGE","ADA","LINK","BCH","LTC","AVAX","DOT","UNI",
  "ATOM","FIL","INJ","FET","CAKE","TRX","SHIB","TON","AAVE","LDO"];
const CMC_BASE = "https://pro-api.coinmarketcap.com";
const K = 5;
// 90th-pct decile of the live proxy over 21,599 historical cross-sections.
// Mirrors scripts/cmc_live.py PULSE_PANIC_THRESHOLD — keep the two in sync.
const PULSE_PANIC_THRESHOLD = 2.228;

const pstdev = (xs) => {
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / xs.length);
};

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

async function liveSignal(key) {
  const url = new URL(CMC_BASE + "/v1/cryptocurrency/quotes/latest");
  url.searchParams.set("symbol", BASKET.join(","));
  url.searchParams.set("convert", "USD");
  const r = await fetch(url, { headers: { "X-CMC_PRO_API_KEY": key, Accept: "application/json" } });
  if (!r.ok) throw new Error(`CMC quotes ${r.status}`);
  const data = (await r.json()).data || {};

  const moves = {};
  for (const sym of BASKET) {
    let d = data[sym];
    if (Array.isArray(d)) d = d[0];
    const pc1h = d?.quote?.USD?.percent_change_1h;
    if (pc1h != null) moves[sym] = pc1h / 100;
  }
  const syms = Object.keys(moves);
  if (!syms.length) throw new Error("no quote data");

  const vals = syms.map((s) => moves[s]);
  const spread = pstdev(vals) || 1e-9;
  const pulse = vals.reduce((a, v) => a + Math.abs(v), 0) / vals.length / spread;
  const direction = vals.reduce((a, b) => a + b, 0) / vals.length;

  let fg = null;
  try {
    const fr = await fetch(CMC_BASE + "/v3/fear-and-greed/latest", {
      headers: { "X-CMC_PRO_API_KEY": key, Accept: "application/json" },
    });
    if (fr.ok) fg = (await fr.json())?.data?.value ?? null;
  } catch { /* F&G is optional context */ }

  const high = pulse > PULSE_PANIC_THRESHOLD;
  const regime = !high ? "CALM" : direction < 0 ? "PANIC" : "EUPHORIA";
  const sorted = [...syms].sort((a, b) => moves[a] - moves[b]);
  let picks = [], action = "FLAT";
  if (regime === "PANIC") { picks = sorted.slice(0, K); action = "FADE_LONG"; }
  else if (regime === "EUPHORIA") { picks = sorted.slice(-K).reverse(); action = "MOMENTUM_LONG"; }

  return {
    source: "CoinMarketCap AI Agent Hub (live quotes/latest + fear-and-greed)",
    live: true,
    pulse_index: Math.round(pulse * 1000) / 1000,
    direction_1h: Math.round(direction * 100 * 1000) / 1000,
    regime, action, picks,
    fear_greed: fg, hold_hours: 3, stop_loss: -0.05, take_profit: 0.06,
    sizing: "equal-weight, market-neutral",
    conviction: conviction(regime, fg),
  };
}

// Preferred deterministic signal: the SAME live computation the dashboard card
// and EKG use (/api/heartbeat — real 30d Binance velocity + CMC Fear & Greed).
// Fetching it here means the agent narrates the exact numbers the card shows —
// one source of truth, no "card says 0.7 but chat says 1.6" mismatch.
async function heartbeatSignal(host) {
  const proto = host.startsWith("localhost") ? "http" : "https";
  const r = await fetch(`${proto}://${host}/api/heartbeat`, { signal: AbortSignal.timeout(22000) });
  if (!r.ok) throw new Error(`heartbeat ${r.status}`);
  const d = await r.json();
  const { series, ...signal } = d;   // drop the bulky series before narration
  return signal;
}

async function cachedSignal(host) {
  // Fallback: the validated backtest's last signal, served from the static site.
  const proto = host.startsWith("localhost") ? "http" : "https";
  const r = await fetch(`${proto}://${host}/data/pulse_data.json`);
  const d = await r.json();
  const s = d.latest_signal || {};
  return {
    source: "cached backtest signal (live CMC unavailable)",
    live: false,
    pulse_index: s.pulse_index, regime: s.regime, action: s.action,
    picks: s.picks || [], fear_greed: null, hold_hours: s.hold_hours,
    stop_loss: s.stop_loss, take_profit: s.take_profit, sizing: s.sizing,
    conviction: conviction(s.regime, null), note: s.note,
  };
}

const NARRATE_SYS =
  "You are the Pulse agent — a crypto-market regime analyst running the Pulse Velocity-Regime skill " +
  "(a 'crypto VIX' measuring how fast the whole market reprices). You are given a JSON signal computed " +
  "deterministically from live CoinMarketCap data. Explain it to a judge in 3-5 tight sentences: the regime, " +
  "the conviction grade and why, and the concrete action + picks.\n" +
  "CRITICAL action semantics — do not invert them:\n" +
  "- action FADE_LONG (PANIC): the market over-sold in a synchronized panic and tends to BOUNCE. " +
  "You BUY / go LONG the listed oversold picks expecting a rebound. FADE means fade the DROP, i.e. buy it — never 'sell' or 'avoid'.\n" +
  "- action MOMENTUM_LONG (EUPHORIA): BUY / go LONG the strongest picks, riding momentum.\n" +
  "- action FLAT (CALM): no trade, stand aside, hold no positions.\n" +
  "Never invent numbers outside the JSON. No markdown headers, no 'not financial advice' disclaimers.";

// Stream the narration as it generates. `onDelta(kind, text)` fires for each
// chunk: kind "reasoning" (the model thinking — shown live as a ticker so the
// demo feels instant) or "answer" (the visible reply). Returns the full answer
// text, or null if the LLM is unavailable / produced nothing.
async function narrateStream(signal, message, onDelta) {
  // Provider-agnostic: point LLM_BASE_URL at any OpenAI-compatible server
  // (self-hosted DeepSeek on a VPS via vLLM/ollama/llama.cpp/TGI, or OpenRouter).
  // Falls back to OpenRouter only if LLM_BASE_URL is unset.
  const base = (process.env.LLM_BASE_URL || "https://openrouter.ai/api/v1").replace(/\/$/, "");
  const apiKey = process.env.LLM_API_KEY || process.env.OPENROUTER_API_KEY || "";
  // self-hosted servers usually need no key; only OpenRouter strictly requires one
  if (!apiKey && base.includes("openrouter.ai")) return null;
  const model = process.env.PULSE_LLM_MODEL || "deepseek-v4-flash-free";
  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  try {
    const ctrl = AbortSignal.timeout(45000);   // reasoning-model + cold-start guard
    const r = await fetch(base + "/chat/completions", {
      method: "POST", headers, signal: ctrl,
      body: JSON.stringify({
        model, stream: true,
        messages: [
          { role: "system", content: NARRATE_SYS },
          { role: "user", content: `Judge asked: "${message}"\n\nLive signal JSON:\n${JSON.stringify(signal, null, 2)}` },
        ],
        // budget covers reasoning models (deepseek-v4-flash-free spends ~700
        // reasoning tokens before the visible answer) + the answer itself.
        temperature: 0.4, max_tokens: 1500,
      }),
    });
    if (!r.ok || !r.body) return null;

    let answer = "", buf = "";
    const dec = new TextDecoder();
    const reader = r.body.getReader();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") continue;
        let j; try { j = JSON.parse(data); } catch { continue; }
        const d = j?.choices?.[0]?.delta || {};
        if (d.reasoning_content) onDelta("reasoning", d.reasoning_content);
        if (d.content) { answer += d.content; onDelta("answer", d.content); }
      }
    }
    return answer.trim() || null;
  } catch { return null; }
}

function fallbackReply(s) {
  const r = s.regime, c = s.conviction || {};
  if (r === "PANIC") return `Regime: PANIC (Pulse ${s.pulse_index}). The basket is repricing fast and falling — capitulation. The validated edge is to FADE the overshoot: long the most oversold (${(s.picks||[]).join(", ")}), 3h hold, −5% stop / +6% take-profit. Conviction ${c.grade}: ${c.reason}.`;
  if (r === "EUPHORIA") return `Regime: EUPHORIA (Pulse ${s.pulse_index}). Fast and rising — momentum. Ride the strongest: ${(s.picks||[]).join(", ")}, 3h hold, −5% / +6%. Conviction ${c.grade}: ${c.reason}.`;
  return `Regime: CALM (Pulse ${s.pulse_index}). Cluster velocity is low — no edge, stand aside (FLAT). Pulse fires a signal only when the whole market starts moving at once. ${c.reason ? "Conviction " + c.grade + ": " + c.reason + "." : ""}`;
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") { res.status(405).json({ error: "POST only" }); return; }
  const message = (req.body?.message || "what's the regime right now?").toString().slice(0, 500);

  // Compute the deterministic signal first (fast). Errors here are returned as
  // plain JSON *before* the stream starts, so the client can detect them.
  let signal;
  const key = process.env.CMC_API_KEY;
  try {
    // Same signal as the dashboard card/EKG (real 30d velocity + CMC F&G).
    signal = await heartbeatSignal(req.headers.host);
  } catch {
    try {
      // Fallback: CMC latest-quote velocity proxy.
      if (!key) throw new Error("no CMC key");
      signal = await liveSignal(key);
    } catch {
      try { signal = await cachedSignal(req.headers.host); }
      catch { res.status(502).json({ error: "signal unavailable" }); return; }
    }
  }

  // Stream as Server-Sent Events: the signal card first, then the narration
  // token-by-token (reasoning ticker + answer). X-Accel-Buffering:no keeps
  // Vercel/proxies from buffering the stream.
  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
  });
  const send = (event, obj) => res.write(`event: ${event}\ndata: ${JSON.stringify(obj)}\n\n`);

  send("signal", signal);
  let answered = false;
  const answer = await narrateStream(signal, message, (kind, text) => {
    if (kind === "answer") answered = true;
    send("delta", { kind, text });
  });
  // No LLM (unavailable / empty): stream the deterministic fallback as the answer.
  if (!answer && !answered) send("delta", { kind: "answer", text: fallbackReply(signal) });
  send("done", {});
  res.end();
}
