import { useState, useEffect } from "react";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer
} from "recharts";
import {
  Activity, AlertTriangle, DollarSign, Brain,
  CheckCircle, Play, RefreshCw, ChevronDown, ChevronUp, Zap
} from "lucide-react";

// Chart colors — hardcoded because canvas cannot read CSS variables
const C = {
  teal: "#1D9E75", tealLight: "#9FE1CB",
  red: "#E24B4A", amber: "#EF9F27",
  blue: "#378ADD", green: "#639922", gray: "#888780",
};

// ── Data ──────────────────────────────────────────────────────────────────────

const trendBefore = [
  { t: "-6h", score: 82 }, { t: "-5h", score: 78 }, { t: "-4h", score: 69 },
  { t: "-3h", score: 71 }, { t: "-2h", score: 74 }, { t: "-1h", score: 85 },
  { t: "now", score: 69 },
];
const trendAfter = [
  { t: "-6h", score: 82 }, { t: "-5h", score: 78 }, { t: "-4h", score: 69 },
  { t: "-3h", score: 71 }, { t: "-2h", score: 74 }, { t: "-1h", score: 85 },
  { t: "now", score: 93 },
];

const rootCauses = [
  { name: "Shipping API timeout",   pct: 67, color: C.red,   spanId: "span_8f2a3c" },
  { name: "Speculative tool calls", pct: 23, color: C.amber, spanId: "span_3c7b1d" },
  { name: "Context overflow",       pct: 7,  color: "#f97316", spanId: "span_1e9d4a" },
  { name: "Retry exhaustion",       pct: 3,  color: "#8b5cf6", spanId: "span_5a4f2e" },
];

const agentDefs = [
  { name: "Reliability Agent",    Icon: Activity,      color: C.teal,
    outputBefore: "Score: 69/100",              outputAfter: "Score: 93/100",
    detail: "Trend: declining → recovering",    latency: "1.2s" },
  { name: "Root Cause Agent",     Icon: AlertTriangle, color: C.red,
    outputBefore: "Shipping API → 67% failures", outputAfter: "Shipping API → 67% failures",
    detail: "Span: span_8f2a3c",                latency: "2.1s" },
  { name: "Cost Agent",           Icon: DollarSign,    color: C.amber,
    outputBefore: "−38% tokens possible",        outputAfter: "−38% tokens removed",
    detail: "$1,640/day saving identified",      latency: "1.8s" },
  { name: "Recommendation Agent", Icon: Brain,         color: "#7c3aed",
    outputBefore: "3 fixes ranked",              outputAfter: "3 fixes ranked",
    detail: "RAG-grounded · safety cleared",     latency: "3.4s" },
];

const recs = [
  { rank: 1, color: C.teal,
    title: "Implement lazy tool-calling",
    impact: "Reliability: 69 → 93", effort: "Low (2h)", saving: "$1,640/day",
    source: "ShopFast Reliability Guide v3 §4.2",
    before: { failures: "31%", latency: "8.4s", cost: "$2,100/day" },
    after:  { failures: "4%",  latency: "2.1s", cost: "$460/day"  } },
  { rank: 2, color: C.green,
    title: "Add 1s timeout + 2 retries on Shipping API",
    impact: "Failure rate: 31% → 4%", effort: "Low (1h)", saving: "$640/day",
    source: "Reliability Playbook §7.1",
    before: { failures: "67%", latency: "3.2s", cost: "—" },
    after:  { failures: "8%",  latency: "1.1s", cost: "—" } },
  { rank: 3, color: C.amber,
    title: "Reduce retrieval k from 12 → 3",
    impact: "Token reduction: −38%", effort: "Medium (4h)", saving: "$420/day",
    source: "Prompt Engineering Guide §2.3",
    before: { failures: "—", latency: "4.1s", cost: "$1,080/day" },
    after:  { failures: "—", latency: "1.8s", cost: "$660/day"  } },
];

const tokenData = [
  { day: "Mon", prompt: 42, completion: 28, speculative: 18 },
  { day: "Tue", prompt: 45, completion: 30, speculative: 21 },
  { day: "Wed", prompt: 51, completion: 34, speculative: 24 },
  { day: "Thu", prompt: 48, completion: 31, speculative: 22 },
  { day: "Fri", prompt: 55, completion: 37, speculative: 26 },
  { day: "Sat", prompt: 38, completion: 25, speculative: 17 },
  { day: "Sun", prompt: 41, completion: 27, speculative: 19 },
];

const spans = [
  { id: "agent.request",    time: "12:04:27", latency: 8400, status: "error",   tokens: 1840, indent: 0 },
  { id: "tool.orders_api",  time: "12:04:28", latency: 340,  status: "success", tokens: 0,    indent: 1 },
  { id: "tool.shipping_api",time: "12:04:29", latency: 3200, status: "timeout", tokens: 0,    indent: 1, note: "Root cause" },
  { id: "tool.returns_api", time: "12:04:33", latency: 820,  status: "success", tokens: 0,    indent: 1, speculative: true },
];

const initFeed = [
  { time: "12:04:33", msg: "tool.returns_api → OK (820ms) [SPECULATIVE]",  type: "warn"  },
  { time: "12:04:29", msg: "tool.shipping_api → TIMEOUT (3200ms)",          type: "error" },
  { time: "12:04:28", msg: "tool.orders_api → OK (340ms)",                  type: "ok"    },
  { time: "12:04:27", msg: "agent.request started — session 7f3a9c",         type: "info"  },
];
const feedPool = [
  { msg: "tool.shipping_api → TIMEOUT (3100ms)",          type: "error" },
  { msg: "agent.request started — session 8a2b1f",         type: "info"  },
  { msg: "tool.orders_api → OK (290ms)",                   type: "ok"    },
  { msg: "Root Cause Agent: timeout pattern confirmed",    type: "info"  },
  { msg: "tool.returns_api → OK (910ms) [SPECULATIVE]",   type: "warn"  },
  { msg: "Reliability Agent: score recalculated",          type: "info"  },
];

// ── Shared style tokens ────────────────────────────────────────────────────────

const card = {
  background: "var(--color-background-primary)",
  border: "0.5px solid var(--color-border-tertiary)",
  borderRadius: "var(--border-radius-lg)",
  padding: "1rem 1.25rem",
};
const metCard = {
  background: "var(--color-background-secondary)",
  borderRadius: "var(--border-radius-md)",
  padding: "1rem",
};
const mono = { fontFamily: "var(--font-mono)" };

// ── Sub-components ─────────────────────────────────────────────────────────────

function Gauge({ score }) {
  const r = 54, circ = 2 * Math.PI * r;
  const color = score >= 80 ? C.teal : score >= 60 ? C.amber : C.red;
  const dash = (score / 100) * circ;
  return (
    <svg width={140} height={140} viewBox="0 0 140 140" style={{ display: "block", margin: "0 auto" }}>
      <circle cx={70} cy={70} r={r} fill="none" stroke="var(--color-border-tertiary)" strokeWidth={10} />
      <circle cx={70} cy={70} r={r} fill="none" stroke={color} strokeWidth={10}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        transform="rotate(-90 70 70)" style={{ transition: "stroke-dasharray 0.8s ease, stroke 0.5s ease" }} />
      <text x={70} y={64} textAnchor="middle" fill={color} fontSize={26} fontWeight={500}
        fontFamily="var(--font-mono)" style={{ transition: "fill 0.5s" }}>{score}</text>
      <text x={70} y={79} textAnchor="middle" fill="var(--color-text-secondary)" fontSize={10}
        fontFamily="var(--font-sans)">/100</text>
      <text x={70} y={94} textAnchor="middle" fill="var(--color-text-secondary)" fontSize={9}
        fontFamily="var(--font-sans)">reliability score</text>
    </svg>
  );
}

function CTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "var(--color-background-primary)", border: "0.5px solid var(--color-border-secondary)",
      borderRadius: 6, padding: "8px 12px", fontSize: 12 }}>
      <div style={{ color: "var(--color-text-secondary)", marginBottom: 4 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color || "var(--color-text-primary)" }}>
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  );
}

function LiveDot() {
  return <span style={{ width: 7, height: 7, borderRadius: "50%", background: C.teal,
    display: "inline-block", animation: "aire-pulse 1.5s infinite" }} />;
}

function ScoreBar({ label, val }) {
  const color = val >= 80 ? C.teal : val >= 60 ? C.amber : C.red;
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11,
        color: "var(--color-text-secondary)", marginBottom: 3 }}>
        <span>{label}</span>
        <span style={{ color, ...mono }}>{val}</span>
      </div>
      <div style={{ height: 4, background: "var(--color-border-tertiary)", borderRadius: 2 }}>
        <div style={{ height: "100%", width: `${val}%`, background: color,
          borderRadius: 2, transition: "width 0.8s ease" }} />
      </div>
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────

export default function AIREDashboard() {
  const [tab, setTab]           = useState("overview");
  const [showFix, setShowFix]   = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedRec, setSelRec]  = useState(null);
  const [liveEvents, setFeed]   = useState(initFeed);

  // derived state
  const score      = showFix ? 93 : 69;
  const failRate   = showFix ? "4%"   : "31%";
  const dailyCost  = showFix ? "$460" : "$2,100";
  const tokenDelta = showFix ? "−38%" : "—";
  const trendData  = showFix ? trendAfter : trendBefore;
  const scoreColor = score >= 80 ? C.teal : score >= 60 ? C.amber : C.red;

  const scoreBreakdown = [
    { label: "Success rate",   val: showFix ? 96 : 69 },
    { label: "P95 latency",    val: showFix ? 90 : 52 },
    { label: "Error rate",     val: showFix ? 94 : 61 },
    { label: "Tool stability", val: showFix ? 88 : 74 },
  ];

  useEffect(() => {
    let i = 0;
    const iv = setInterval(() => {
      const n = new Date();
      const time = [n.getHours(), n.getMinutes(), n.getSeconds()]
        .map(v => String(v).padStart(2, "0")).join(":");
      const ev = feedPool[i % feedPool.length];
      setFeed(prev => [{ time, msg: ev.msg, type: ev.type }, ...prev.slice(0, 9)]);
      i++;
    }, 3200);
    return () => clearInterval(iv);
  }, []);

  const runAIRE = () => {
    setAnalyzing(true);
    setTimeout(() => { setAnalyzing(false); setShowFix(true); }, 2200);
  };

  const feedColor = t => t === "error" ? C.red : t === "warn" ? C.amber : t === "ok" ? C.teal : "var(--color-text-secondary)";
  const spanColor = s => s === "timeout" || s === "error" ? C.red : C.teal;

  const TABS = ["overview", "agents", "costs", "traces", "recommendations"];

  // ── Metric strip (always visible) ──────────────────────────────────────────
  const MetricStrip = () => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 16 }}>
      {[
        { label: "Reliability score", value: `${score}/100`,  delta: showFix ? "↑ +24 after fix" : "↓ Declining",            color: scoreColor },
        { label: "Failure rate",      value: failRate,         delta: showFix ? "↓ was 31%" : "67% from Shipping API",        color: showFix ? C.teal : C.red },
        { label: "Daily cost",        value: dailyCost,        delta: showFix ? "↓ saving $1,640/day" : "$1,640/day waste",   color: showFix ? C.teal : C.amber },
        { label: "Token delta",       value: tokenDelta,       delta: showFix ? "speculative calls removed" : "optimization available", color: showFix ? C.teal : "var(--color-text-secondary)" },
      ].map(m => (
        <div key={m.label} style={metCard}>
          <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 6 }}>{m.label}</div>
          <div style={{ fontSize: 24, fontWeight: 500, color: m.color, marginBottom: 3, transition: "color 0.5s", ...mono }}>{m.value}</div>
          <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{m.delta}</div>
        </div>
      ))}
    </div>
  );

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: "0 0 2rem" }}>
      <h2 className="aire-sr">AIRE — AI Reliability Engineer dashboard: reliability scoring, root cause analysis, cost optimization, agent status</h2>

      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 0", marginBottom: 8, borderBottom: "0.5px solid var(--color-border-tertiary)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 500, color: "var(--color-text-primary)" }}>AIRE</span>
          <span style={{ fontSize: 11, background: "var(--color-background-info)", color: "var(--color-text-info)",
            padding: "2px 8px", borderRadius: "var(--border-radius-md)", border: "0.5px solid var(--color-border-info)" }}>
            v0.1-hackathon
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--color-text-secondary)" }}>
            <LiveDot /> LIVE
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <select style={{ fontSize: 12, padding: "4px 8px", borderRadius: "var(--border-radius-md)",
            border: "0.5px solid var(--color-border-secondary)", background: "var(--color-background-secondary)",
            color: "var(--color-text-primary)" }}>
            <option>customer_support_bot_v2</option>
            <option>coding_assistant_prod</option>
            <option>research_agent_v1</option>
            <option>ops_agent_internal</option>
          </select>

          {/* Simulate Fix toggle */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12,
            color: "var(--color-text-secondary)", cursor: "pointer", userSelect: "none" }}
            onClick={() => !analyzing && setShowFix(f => !f)}>
            Simulate fix
            <div style={{ width: 34, height: 18, borderRadius: 9, position: "relative",
              background: showFix ? C.teal : "var(--color-border-secondary)", transition: "background 0.3s",
              border: "0.5px solid var(--color-border-secondary)" }}>
              <div style={{ width: 12, height: 12, borderRadius: "50%", background: "white",
                position: "absolute", top: 2, left: showFix ? 18 : 2, transition: "left 0.3s" }} />
            </div>
            {showFix && (
              <span style={{ fontSize: 10, color: "var(--color-text-success)",
                background: "var(--color-background-success)", padding: "1px 6px",
                borderRadius: "var(--border-radius-md)" }}>SIM</span>
            )}
          </div>

          <button onClick={runAIRE} disabled={analyzing}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, padding: "6px 14px",
              borderRadius: "var(--border-radius-md)", cursor: analyzing ? "wait" : "pointer",
              background: "var(--color-background-info)", color: "var(--color-text-info)",
              border: "0.5px solid var(--color-border-info)", opacity: analyzing ? 0.6 : 1 }}>
            {analyzing
              ? <><RefreshCw size={13} style={{ animation: "aire-spin 0.8s linear infinite" }} /> Analyzing…</>
              : <><Play size={13} /> Run AIRE</>}
          </button>
        </div>
      </div>

      {/* Analyzing banner */}
      {analyzing && (
        <div style={{ background: "var(--color-background-info)", border: "0.5px solid var(--color-border-info)",
          borderRadius: "var(--border-radius-md)", padding: "10px 14px", marginBottom: 12,
          display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: "var(--color-text-info)" }}>
          <RefreshCw size={14} style={{ animation: "aire-spin 0.8s linear infinite", flexShrink: 0 }} />
          <span><strong>AIRE is analyzing</strong> — 4 Gemini agents running in parallel across Reliability · Root Cause · Cost · Recommendation</span>
        </div>
      )}

      {/* ── Tabs ── */}
      <div style={{ display: "flex", borderBottom: "0.5px solid var(--color-border-tertiary)", marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: "8px 16px", fontSize: 12, background: "none", border: "none",
              borderBottom: tab === t ? `2px solid ${C.teal}` : "2px solid transparent",
              color: tab === t ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              cursor: "pointer", textTransform: "capitalize", fontWeight: tab === t ? 500 : 400 }}>
            {t}
          </button>
        ))}
      </div>

      <MetricStrip />

      {/* ════════════════════════════════════════════════════════════
          OVERVIEW TAB
      ════════════════════════════════════════════════════════════ */}
      {tab === "overview" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 12, marginBottom: 12 }}>
            {/* Score card */}
            <div style={card}>
              <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 12 }}>Reliability score</div>
              <Gauge score={score} />
              <div style={{ marginTop: 16 }}>
                {scoreBreakdown.map(s => <ScoreBar key={s.label} {...s} />)}
              </div>
            </div>

            {/* Trend + root cause */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ ...card, flex: 1 }}>
                <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 8 }}>Score trend — last 6h</div>
                <ResponsiveContainer width="100%" height={120}>
                  <AreaChart data={trendData}>
                    <XAxis dataKey="t" tick={{ fontSize: 10, fill: C.gray }} axisLine={false} tickLine={false} />
                    <YAxis domain={[50, 100]} tick={{ fontSize: 10, fill: C.gray }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CTooltip />} />
                    <Area type="monotone" dataKey="score" stroke={C.teal} strokeWidth={2}
                      fill={C.tealLight} fillOpacity={0.15} dot={false} name="Score" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div style={{ ...card, flex: 1 }}>
                <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 12 }}>Root cause breakdown</div>
                {rootCauses.map(rc => (
                  <div key={rc.name} style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
                      <span style={{ color: "var(--color-text-primary)" }}>{rc.name}</span>
                      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                        <span style={{ color: rc.color, fontWeight: 500, ...mono }}>{rc.pct}%</span>
                        <span style={{ fontSize: 10, color: "var(--color-text-secondary)", ...mono }}>{rc.spanId}</span>
                      </div>
                    </div>
                    <div style={{ height: 5, background: "var(--color-border-tertiary)", borderRadius: 2 }}>
                      <div style={{ height: "100%", width: `${rc.pct}%`, background: rc.color, borderRadius: 2 }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Agents + Live Feed */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 260px", gap: 12 }}>
            <div style={card}>
              <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 12 }}>Four Gemini agents</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {agentDefs.map(a => {
                  const Icon = a.Icon;
                  return (
                    <div key={a.name} style={{ background: "var(--color-background-secondary)",
                      borderRadius: "var(--border-radius-md)", padding: 12, borderLeft: `3px solid ${a.color}` }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <Icon size={13} color={a.color} />
                          <span style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)" }}>{a.name}</span>
                        </div>
                        <span style={{ fontSize: 10, color: a.color, background: `${a.color}18`,
                          padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>done</span>
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: a.color, marginBottom: 2 }}>
                        {showFix ? a.outputAfter : a.outputBefore}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{a.detail}</div>
                      <div style={{ fontSize: 10, color: "var(--color-text-secondary)", ...mono, marginTop: 4 }}>
                        latency: {a.latency}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={card}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 10 }}>
                <span>Live span feed</span>
                <LiveDot />
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {liveEvents.map((ev, i) => (
                  <div key={i} style={{ display: "flex", gap: 8, padding: "4px 0",
                    borderBottom: "0.5px solid var(--color-border-tertiary)", fontSize: 11 }}>
                    <span style={{ color: "var(--color-text-secondary)", ...mono, flexShrink: 0 }}>{ev.time}</span>
                    <span style={{ color: feedColor(ev.type) }}>{ev.msg}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ════════════════════════════════════════════════════════════
          AGENTS TAB
      ════════════════════════════════════════════════════════════ */}
      {tab === "agents" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {agentDefs.map(a => {
            const Icon = a.Icon;
            const rows = [
              { label: "RAG-grounded",     val: a.name === "Recommendation Agent" ? "✓ yes"    : "—", ok: a.name === "Recommendation Agent" },
              { label: "Safety filter",    val: a.name === "Recommendation Agent" ? "✓ passed" : "—", ok: a.name === "Recommendation Agent" },
              { label: "Dynatrace trace",  val: "span_7f3a9c", ok: false },
              { label: "Execution latency",val: a.latency,      ok: false },
            ];
            return (
              <div key={a.name} style={{ ...card, borderTop: `3px solid ${a.color}` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                  <Icon size={20} color={a.color} />
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-primary)" }}>{a.name}</div>
                    <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>Gemini Enterprise · {a.latency}</div>
                  </div>
                  <span style={{ marginLeft: "auto", fontSize: 10, color: a.color,
                    background: `${a.color}18`, padding: "2px 8px", borderRadius: "var(--border-radius-md)",
                    border: `0.5px solid ${a.color}40` }}>COMPLETE</span>
                </div>

                <div style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)",
                  padding: 12, marginBottom: 12 }}>
                  <div style={{ fontSize: 10, color: "var(--color-text-secondary)", marginBottom: 6,
                    textTransform: "uppercase", letterSpacing: 0.5 }}>Output</div>
                  <div style={{ fontSize: 15, fontWeight: 500, color: a.color, marginBottom: 3 }}>
                    {showFix ? a.outputAfter : a.outputBefore}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>{a.detail}</div>
                </div>

                {rows.map(row => (
                  <div key={row.label} style={{ display: "flex", justifyContent: "space-between",
                    fontSize: 12, padding: "4px 0", borderBottom: "0.5px solid var(--color-border-tertiary)",
                    color: "var(--color-text-secondary)" }}>
                    <span>{row.label}</span>
                    <span style={{ ...mono, color: row.ok ? C.teal : "var(--color-text-primary)" }}>{row.val}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          COSTS TAB
      ════════════════════════════════════════════════════════════ */}
      {tab === "costs" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginBottom: 12 }}>
            {[
              { label: "Current daily cost",   val: "$2,100", sub: "before optimization",  color: C.red   },
              { label: "Optimized daily cost",  val: "$460",   sub: "after applying fixes", color: C.teal  },
              { label: "Daily saving",          val: "$1,640", sub: "78% cost reduction",   color: C.green },
            ].map(m => (
              <div key={m.label} style={{ ...metCard, textAlign: "center" }}>
                <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 6 }}>{m.label}</div>
                <div style={{ fontSize: 30, fontWeight: 500, color: m.color, ...mono, marginBottom: 3 }}>{m.val}</div>
                <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{m.sub}</div>
              </div>
            ))}
          </div>

          <div style={card}>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 6 }}>
              Token usage by type — 7 days (thousands)
            </div>

            {/* Legend */}
            <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 12 }}>
              {[{ c: C.blue, l: "Prompt" }, { c: C.teal, l: "Completion" }, { c: C.red, l: "Speculative (waste)" }].map(({ c, l }) => (
                <span key={l} style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--color-text-secondary)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: c, display: "inline-block" }} />{l}
                </span>
              ))}
            </div>

            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={tokenData}>
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: C.gray }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: C.gray }} axisLine={false} tickLine={false} />
                <Tooltip content={<CTooltip />} />
                <Bar dataKey="prompt"     stackId="a" fill={C.blue}  name="Prompt" />
                <Bar dataKey="completion" stackId="a" fill={C.teal}  name="Completion" />
                <Bar dataKey="speculative" stackId="a" fill={C.red}  name="Speculative" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>

            <div style={{ marginTop: 12, padding: "10px 12px", background: "var(--color-background-secondary)",
              borderRadius: "var(--border-radius-md)", fontSize: 12, color: "var(--color-text-secondary)",
              display: "flex", alignItems: "center", gap: 8 }}>
              <Zap size={14} color={C.amber} style={{ flexShrink: 0 }} />
              Returns API called on 98% of requests — only relevant 11% of the time.
              Removing speculative calls saves <strong style={{ color: "var(--color-text-primary)" }}>&nbsp;$1,640/day</strong> and reduces tokens by 38%.
            </div>
          </div>
        </>
      )}

      {/* ════════════════════════════════════════════════════════════
          TRACES TAB
      ════════════════════════════════════════════════════════════ */}
      {tab === "traces" && (
        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
              Agent trace waterfall — session 7f3a9c
            </div>
            <span style={{ fontSize: 11, color: "var(--color-text-secondary)", ...mono }}>
              12:04:27 → 12:04:35 · 8400ms total
            </span>
          </div>

          {spans.map(s => {
            const barW = Math.round((s.latency / 8400) * 100);
            const sc = spanColor(s.status);
            return (
              <div key={s.id} style={{ marginBottom: 14, paddingLeft: s.indent * 18 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                  {s.indent > 0 && <span style={{ color: "var(--color-text-secondary)", fontSize: 12 }}>└</span>}
                  <span style={{ ...mono, fontSize: 12, color: "var(--color-text-primary)", minWidth: 168 }}>{s.id}</span>
                  {s.speculative && (
                    <span style={{ fontSize: 10, color: C.amber, background: `${C.amber}18`,
                      padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>SPECULATIVE</span>
                  )}
                  {s.note && (
                    <span style={{ fontSize: 10, color: C.red, background: `${C.red}15`,
                      padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>{s.note}</span>
                  )}
                  <span style={{ marginLeft: "auto", fontSize: 11, ...mono, color: sc, fontWeight: 500 }}>
                    {s.status.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 11, ...mono, color: "var(--color-text-secondary)", minWidth: 62, textAlign: "right" }}>
                    {s.latency}ms
                  </span>
                </div>
                <div style={{ height: 6, background: "var(--color-border-tertiary)", borderRadius: 3 }}>
                  <div style={{ height: "100%", width: `${barW}%`, background: sc, borderRadius: 3, opacity: 0.85 }} />
                </div>
                {s.tokens > 0 && (
                  <div style={{ fontSize: 10, color: "var(--color-text-secondary)", ...mono, marginTop: 3 }}>
                    tokens: {s.tokens}
                  </div>
                )}
              </div>
            );
          })}

          <div style={{ marginTop: 16, padding: 12, background: "var(--color-background-secondary)",
            borderRadius: "var(--border-radius-md)", fontSize: 12 }}>
            <div style={{ color: C.red, marginBottom: 6, display: "flex", gap: 8 }}>
              <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              Shipping API timeout (3200ms) is the root cause — 67% of failures trace back to this span
            </div>
            <div style={{ color: C.amber, display: "flex", gap: 8 }}>
              <Zap size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              Returns API called speculatively — not required for "Where is my order?" queries
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════════
          RECOMMENDATIONS TAB
      ════════════════════════════════════════════════════════════ */}
      {tab === "recommendations" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)", marginBottom: 12 }}>
              Top-3 recommendations
            </div>
            {recs.map(rec => (
              <div key={rec.rank}
                onClick={() => setSelRec(selectedRec === rec.rank ? null : rec.rank)}
                style={{ ...card, marginBottom: 10, cursor: "pointer",
                  borderLeft: `3px solid ${rec.color}`, borderRadius: `0 var(--border-radius-lg) var(--border-radius-lg) 0`,
                  outline: selectedRec === rec.rank ? `1.5px solid ${rec.color}` : "none", outlineOffset: 1 }}>
                <div style={{ display: "flex", alignItems: "start", justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)" }}>
                    <span style={{ ...mono, color: rec.color, marginRight: 8 }}>#{rec.rank}</span>
                    {rec.title}
                  </div>
                  {selectedRec === rec.rank
                    ? <ChevronUp size={14} color="var(--color-text-secondary)" />
                    : <ChevronDown size={14} color="var(--color-text-secondary)" />}
                </div>
                <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 6 }}>
                  <span>Impact: {rec.impact}</span>
                  <span>Effort: {rec.effort}</span>
                  <span style={{ color: C.teal }}>Save: {rec.saving}</span>
                </div>
                <div style={{ fontSize: 10, color: "var(--color-text-secondary)", ...mono }}>
                  Source: {rec.source}
                </div>

                {selectedRec === rec.rank && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8,
                    marginTop: 12, paddingTop: 12, borderTop: "0.5px solid var(--color-border-tertiary)" }}>
                    {[
                      { label: "Before", data: rec.before, color: C.red,  bg: "var(--color-background-danger)"  },
                      { label: "After",  data: rec.after,  color: C.teal, bg: "var(--color-background-success)" },
                    ].map(({ label, data, color, bg }) => (
                      <div key={label} style={{ background: bg, borderRadius: "var(--border-radius-md)",
                        padding: 10, border: `0.5px solid ${color}40` }}>
                        <div style={{ fontSize: 10, color, marginBottom: 5, fontWeight: 500 }}>{label.toUpperCase()}</div>
                        {Object.entries(data).map(([k, v]) => (
                          <div key={k} style={{ fontSize: 11, color: "var(--color-text-primary)",
                            display: "flex", justifyContent: "space-between" }}>
                            <span style={{ color: "var(--color-text-secondary)", textTransform: "capitalize" }}>{k}:</span>
                            <span style={mono}>{v}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* RAG sources */}
            <div style={card}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 12 }}>
                <span>Agent Search — RAG sources</span>
                <span style={{ fontSize: 10, color: C.teal }}>3 cited</span>
              </div>
              {[
                { doc: "ShopFast Reliability Guide v3", section: "§4.2 Lazy Tool-Calling Patterns", rel: "98%" },
                { doc: "Reliability Playbook",          section: "§7.1 API Timeout Handling",       rel: "94%" },
                { doc: "Prompt Engineering Guide",      section: "§2.3 Retrieval k-value Tuning",   rel: "87%" },
              ].map(s => (
                <div key={s.doc} style={{ background: "var(--color-background-secondary)",
                  borderRadius: "var(--border-radius-md)", padding: 10, marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                    <div>
                      <div style={{ fontSize: 12, color: "var(--color-text-primary)", marginBottom: 2 }}>{s.doc}</div>
                      <div style={{ fontSize: 11, color: C.teal }}>{s.section}</div>
                    </div>
                    <span style={{ fontSize: 10, color: C.teal, background: `${C.teal}15`,
                      padding: "1px 5px", borderRadius: "var(--border-radius-md)", flexShrink: 0, marginLeft: 6 }}>
                      {s.rel}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Safety filter */}
            <div style={card}>
              <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 10 }}>Gemini safety filter</div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                <CheckCircle size={14} color={C.teal} />
                <span style={{ fontSize: 12, color: "var(--color-text-primary)", fontWeight: 500 }}>All recommendations cleared</span>
              </div>
              {["No destructive actions", "No monitoring disablement", "No irreversible changes", "Human approval required"].map(item => (
                <div key={item} style={{ fontSize: 11, color: "var(--color-text-secondary)", padding: "4px 0",
                  borderBottom: "0.5px solid var(--color-border-tertiary)", display: "flex", alignItems: "center", gap: 6 }}>
                  <CheckCircle size={11} color={C.teal} /> {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .aire-sr { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); border:0; }
        @keyframes aire-pulse { 0%,100%{opacity:1}  50%{opacity:0.3} }
        @keyframes aire-spin  { to{transform:rotate(360deg)} }
        button:focus-visible, select:focus-visible { outline:2px solid ${C.teal}; outline-offset:2px; }
      `}</style>
    </div>
  );
}
