import { useState, useEffect, useRef } from "react";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer
} from "recharts";
import {
  Activity, AlertTriangle, DollarSign, Brain,
  CheckCircle, Play, RefreshCw, ChevronDown, ChevronUp, Zap
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";

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
  { rank: 1, color: C.teal, confidence: "98%",
    title: "Implement lazy tool-calling",
    impact: "Reliability: 69 → 93", effort: "Low (2h)", saving: "$1,640/day",
    source: "ShopFast Reliability Guide v3 §4.2",
    before: { failures: "31%", latency: "8.4s", cost: "$2,100/day" },
    after:  { failures: "4%",  latency: "2.1s", cost: "$460/day"  } },
  { rank: 2, color: "#6366f1", confidence: "94%",
    title: "Add 1s timeout + 2 retries on Shipping API",
    impact: "Failure rate: 31% → 4%", effort: "Low (1h)", saving: "$640/day",
    source: "Reliability Playbook §7.1",
    before: { failures: "67%", latency: "3.2s", cost: "—" },
    after:  { failures: "8%",  latency: "1.1s", cost: "—" } },
  { rank: 3, color: C.amber, confidence: "87%",
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
        fontFamily="var(--font-mono)" style={{ transition: "fill 0.5s" }}>
        <AnimatedNumber value={score} />
      </text>
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
  return <span className="live-dot-pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: C.teal,
    display: "inline-block" }} />;
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

// ── Markdown Parser Helpers ────────────────────────────────────────────────────

function renderMarkdown(text) {
  return text.split("\n\n").map((para, i) => {
    para = para.trim();
    if (para.startsWith("### ")) {
      return (
        <h3 key={i} style={{ fontSize: "13.5px", color: "#fff", margin: "14px 0 6px", borderBottom: "0.5px solid var(--color-border-tertiary)", paddingBottom: "3px" }}>
          {para.replace("### ", "")}
        </h3>
      );
    }
    if (para.startsWith("#### ")) {
      return (
        <h4 key={i} style={{ fontSize: "12px", color: "#fff", margin: "10px 0 4px" }}>
          {para.replace("#### ", "")}
        </h4>
      );
    }
    if (para.startsWith("* ") || para.startsWith("- ")) {
      return (
        <ul key={i} style={{ margin: "0 0 8px", paddingLeft: "16px" }}>
          {para.split("\n").map((li, j) => (
            <li key={j} style={{ marginBottom: "4px" }}>{parseBold(li.replace(/^[*-\s]+/, ""))}</li>
          ))}
        </ul>
      );
    }
    if (para.match(/^\d+\.\s/)) {
      return (
        <ol key={i} style={{ margin: "0 0 8px", paddingLeft: "16px" }}>
          {para.split("\n").map((li, j) => (
            <li key={j} style={{ marginBottom: "4px" }}>{parseBold(li.replace(/^\d+\.\s+/, ""))}</li>
          ))}
        </ol>
      );
    }
    return <p key={i} style={{ margin: "0 0 8px" }}>{parseBold(para)}</p>;
  });
}

function parseBold(str) {
  const parts = str.split(/\*\*([^*]+)\*\*/g);
  return parts.map((part, i) => i % 2 === 1 ? <strong key={i} style={{ color: "#fff" }}>{part}</strong> : part);
}

function AnimatedNumber({ value, duration = 1000 }) {
  const [displayVal, setDisplayVal] = useState(value);
  const lastValue = useRef(value);

  useEffect(() => {
    const cleanValue = (val) => {
      if (typeof val === 'number') return { num: val, prefix: '', suffix: '', decimals: 0 };
      const clean = String(val).replace(/,/g, '').replace(/\u2212/g, '-');
      const numMatch = clean.match(/-?[-\u2212]?\d+(\.\d+)?/);
      if (!numMatch) return { num: null, raw: val };
      const num = parseFloat(numMatch[0]);
      const idx = clean.indexOf(numMatch[0]);
      const prefix = clean.substring(0, idx);
      const suffix = clean.substring(idx + numMatch[0].length);
      const decimals = numMatch[1] ? numMatch[1].length - 1 : 0;
      return { num, prefix, suffix, decimals };
    };

    const startInfo = cleanValue(lastValue.current);
    const endInfo = cleanValue(value);

    if (startInfo.num === null || endInfo.num === null) {
      setDisplayVal(value);
      lastValue.current = value;
      return;
    }

    let start = performance.now();
    let from = startInfo.num;
    let to = endInfo.num;

    let animationFrameId;
    const animate = (time) => {
      let progress = (time - start) / duration;
      if (progress > 1) progress = 1;
      
      const ease = 1 - Math.pow(1 - progress, 3); // cubicOut
      const current = from + (to - from) * ease;
      
      const formattedNum = current.toLocaleString(undefined, {
        minimumFractionDigits: endInfo.decimals,
        maximumFractionDigits: endInfo.decimals,
      });
      
      let finalVal = `${endInfo.prefix}${formattedNum}${endInfo.suffix}`;
      if (String(value).includes('\u2212') && current < 0) {
        finalVal = finalVal.replace('-', '\u2212');
      }
      setDisplayVal(finalVal);

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(animate);
      } else {
        lastValue.current = value;
      }
    };

    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, [value, duration]);

  return <>{displayVal}</>;
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────

export default function AIREDashboard() {
  // tab states
  const [tab, setTab]           = useState("overview");
  const [showFix, setShowFix]   = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedRec, setSelRec]  = useState(null);
  const [liveEvents, setFeed]   = useState(initFeed);

  // visual energy states
  const [scanningAgentIdx, setScanningAgentIdx] = useState(-1);
  const [completedAgents, setCompletedAgents] = useState([true, true, true, true]);
  const [btnSuccess, setBtnSuccess] = useState(false);

  // conversational copilot states
  const [chatOpen, setChatOpen] = useState(true);
  const [messages, setMessages] = useState([
    { role: "assistant", parts: "### 👋 Hello! I'm AIRE, your AI Reliability Engineer.\n\nI can help you monitor, debug, and optimize your Generative AI applications using live Dynatrace telemetry. Ask me anything about failures, latency, or token costs!" }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // dynamic telemetry states
  const [score, setScore] = useState(0);
  const [failRate, setFailRate] = useState("0%");
  const [dailyCost, setDailyCost] = useState("$0");
  const [tokenDelta, setTokenDelta] = useState("—");
  const [trendData, setTrendData] = useState(trendBefore);
  const [spansState, setSpansState] = useState(spans);
  const [tokenDataState, setTokenDataState] = useState(tokenData);

  // derived state
  const scoreValue      = showFix ? 93 : score;
  const failRateValue   = showFix ? "4%"   : failRate;
  const dailyCostValue  = showFix ? "$460" : dailyCost;
  const tokenDeltaValue = showFix ? "−38%" : tokenDelta;
  const trendDataValue  = showFix ? trendAfter : trendData;
  const scoreColor = scoreValue >= 80 ? C.teal : scoreValue >= 60 ? C.amber : C.red;

  const scoreBreakdown = [
    { label: "Success rate",   val: showFix ? 96 : (scoreValue === 69 || scoreValue === 0 ? 69 : 88) },
    { label: "P95 latency",    val: showFix ? 90 : (scoreValue === 69 || scoreValue === 0 ? 52 : 78) },
    { label: "Error rate",     val: showFix ? 94 : (scoreValue === 69 || scoreValue === 0 ? 61 : 84) },
    { label: "Tool stability", val: showFix ? 88 : (scoreValue === 69 || scoreValue === 0 ? 74 : 86) },
  ];

  // Auto scroll to chat bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  // Trigger animations on load
  useEffect(() => {
    const t = setTimeout(() => {
      setScore(69);
      setFailRate("31%");
      setDailyCost("$2,100");
      setTokenDelta("—");
    }, 150);
    return () => clearTimeout(t);
  }, []);

  // Particle mesh canvas animation
  useEffect(() => {
    const canvas = document.getElementById("particle-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let animationFrameId;
    
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", resize);
    resize();
    
    const particles = [];
    const particleCount = 45;
    const maxDistance = 120;
    
    const colors = [
      "rgba(29, 158, 117, 0.45)",  // teal
      "rgba(99, 102, 241, 0.45)",  // indigo
      "rgba(239, 159, 39, 0.45)",  // amber
      "rgba(6, 182, 212, 0.45)"    // cyan
    ];
    
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 2 + 1.5,
        color: colors[Math.floor(Math.random() * colors.length)]
      });
    }
    
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      particles.forEach((p, idx) => {
        p.x += p.vx;
        p.y += p.vy;
        
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
        
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.fill();
        
        for (let j = idx + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dist = Math.hypot(p.x - p2.x, p.y - p2.y);
          if (dist < maxDistance) {
            const alpha = (1 - dist / maxDistance) * 0.12;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      });
      
      animationFrameId = requestAnimationFrame(draw);
    };
    
    draw();
    
    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  // Feed simulation
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
    setScanningAgentIdx(0);
    setCompletedAgents([false, false, false, false]);

    // Agent 1 starts scanning
    setTimeout(() => {
      setScanningAgentIdx(1);
      setCompletedAgents([true, false, false, false]);
    }, 450);

    // Agent 2 starts scanning
    setTimeout(() => {
      setScanningAgentIdx(2);
      setCompletedAgents([true, true, false, false]);
    }, 900);

    // Agent 3 starts scanning
    setTimeout(() => {
      setScanningAgentIdx(3);
      setCompletedAgents([true, true, true, false]);
    }, 1350);

    // Finish scanning
    setTimeout(() => {
      setScanningAgentIdx(-1);
      setCompletedAgents([true, true, true, true]);
    }, 1800);

    // Trigger success and complete analysis
    setTimeout(() => {
      setAnalyzing(false);
      setShowFix(true);
      setBtnSuccess(true);
      setTimeout(() => setBtnSuccess(false), 1200);
    }, 2200);
  };

  const sendQuery = async (queryText) => {
    if (!queryText.trim()) return;
    setMessages(prev => [...prev, { role: "user", parts: queryText }]);
    setInputValue("");
    setChatLoading(true);

    // Dynamic routing to agent logic depending on query keywords
    let selectedAgent = "customer-support-agent";
    const qLower = queryText.toLowerCase();
    if (qLower.includes("vpn") || qLower.includes("hr") || qLower.includes("policy") || qLower.includes("enterprise") || qLower.includes("parental")) {
      selectedAgent = "enterprise-agent";
    } else if (qLower.includes("code") || qLower.includes("linter") || qLower.includes("test") || qLower.includes("coding") || qLower.includes("git") || qLower.includes("refactor")) {
      selectedAgent = "coding-agent";
    } else if (qLower.includes("search") || qLower.includes("research") || qLower.includes("web")) {
      selectedAgent = "research-agent";
    }

    try {
      const response = await fetch(`${API_URL}/api/v1/dashboard/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryText, agent_name: selectedAgent })
      });
      const data = await response.json();

      // Typewriter word-by-word streaming effect
      const typewriteMessage = (text) => {
        return new Promise((resolve) => {
          const words = text.split(" ");
          let currentText = "";
          let wordIdx = 0;
          setMessages(prev => [...prev, { role: "assistant", parts: "" }]);

          const interval = setInterval(() => {
            if (wordIdx < words.length) {
              currentText += (wordIdx === 0 ? "" : " ") + words[wordIdx];
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { role: "assistant", parts: currentText };
                return copy;
              });
              wordIdx++;
            } else {
              clearInterval(interval);
              resolve();
            }
          }, 30);
        });
      };

      await typewriteMessage(data.chat_response);

      if (data.dashboard_data) {
        setScore(data.dashboard_data.score);
        setFailRate(data.dashboard_data.failRate);
        setDailyCost(data.dashboard_data.dailyCost);
        setTokenDelta(data.dashboard_data.tokenDelta);
        setTrendData(data.dashboard_data.trendData);
        setSpansState(data.dashboard_data.spans);
        setTokenDataState(data.dashboard_data.tokenData);
      }

      // Auto-switch tabs to focus user's attention
      if (qLower.includes("cost") || qLower.includes("token") || qLower.includes("spend") || qLower.includes("waste") || qLower.includes("saving")) {
        setTab("costs");
      } else if (qLower.includes("trace") || qLower.includes("waterfall") || qLower.includes("timeout") || qLower.includes("run") || qLower.includes("vpn") || qLower.includes("code")) {
        setTab("traces");
      } else if (qLower.includes("recommend") || qLower.includes("fix") || qLower.includes("playbook")) {
        setTab("recommendations");
      } else {
        setTab("overview");
      }

    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: "assistant", parts: "⚠️ Connection error: Failed to reach AIRE analysis backend." }]);
    } finally {
      setChatLoading(false);
    }
  };

  const feedColor = t => t === "error" ? C.red : t === "warn" ? C.amber : t === "ok" ? C.teal : "var(--color-text-secondary)";
  const spanColor = s => s === "timeout" || s === "error" ? C.red : C.teal;

  const TABS = ["overview", "agents", "costs", "traces", "recommendations"];

  // ── Metric strip (always visible) ──────────────────────────────────────────
  const MetricStrip = () => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 16 }}>
      {[
        { label: "Reliability score", value: `${scoreValue}/100`,  delta: showFix ? "↑ +24 after fix" : (scoreValue === 69 ? "↓ Declining" : "→ Stable"), color: scoreColor },
        { label: "Failure rate",      value: failRateValue,         delta: showFix ? "↓ was 31%" : (scoreValue === 69 ? "67% from Shipping API" : "4% healthy"), color: showFix ? C.teal : (scoreValue === 69 ? C.red : C.teal) },
        { label: "Daily cost",        value: dailyCostValue,        delta: showFix ? "↓ saving $1,640/day" : (scoreValue === 69 ? "$1,640/day waste" : "$410 optimized"), color: showFix ? C.teal : (scoreValue === 69 ? C.amber : C.teal) },
        { label: "Token delta",       value: tokenDeltaValue,       delta: showFix ? "speculative calls removed" : (scoreValue === 69 ? "optimization available" : "standard usage"), color: showFix ? C.teal : "var(--color-text-secondary)" },
      ].map(m => (
        <div key={m.label} style={metCard}>
          <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 6 }}>{m.label}</div>
          <div style={{ fontSize: 24, fontWeight: 500, color: m.color, marginBottom: 3, transition: "color 0.5s", ...mono }}>
            <AnimatedNumber value={m.value} />
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{m.delta}</div>
        </div>
      ))}
    </div>
  );

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={{ padding: "0 0 2rem" }}>
      <canvas id="particle-canvas" stroke="none" />
      <h2 className="aire-sr">AIRE — AI Reliability Engineer dashboard: reliability scoring, root cause analysis, cost optimization, agent status</h2>

      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 0", marginBottom: 8, borderBottom: "0.5px solid var(--color-border-tertiary)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 500, color: "var(--color-text-primary)" }}>AIRE</span>
          <span style={{ fontSize: 11, background: "var(--color-background-info)", color: "var(--color-text-info)",
            padding: "2px 8px", borderRadius: "var(--border-radius-md)", border: "0.5px solid var(--color-border-info)" }}>
            v2.0-conversational
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
            className={analyzing ? "btn-analyzing" : btnSuccess ? "btn-success-flash" : ""}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, padding: "6px 14px",
              borderRadius: "var(--border-radius-md)", cursor: analyzing ? "wait" : "pointer",
              background: "var(--color-background-info)", color: "var(--color-text-info)",
              border: "0.5px solid var(--color-border-info)", opacity: analyzing ? 0.6 : 1 }}>
            {analyzing
              ? <><RefreshCw size={13} style={{ animation: "aire-spin 0.8s linear infinite" }} /> Analyzing…</>
              : btnSuccess
                ? <><CheckCircle size={13} /> Fixed!</>
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

      {/* ── Split Layout ── */}
      <div className="aire-split-layout">
        
        {/* ── Chat/Copilot Sidebar ── */}
        <div className={`aire-chat-sidebar ${chatOpen ? "" : "collapsed"}`}>
          <div className="aire-chat-header">
            <span className="aire-chat-title">
              <Brain size={14} color="#7c3aed" /> AIRE Copilot
              <span style={{ fontSize: 9, padding: "1px 5px", background: "var(--color-background-success)", color: C.teal, border: `0.5px solid ${C.teal}40`, borderRadius: 4, marginLeft: 6 }}>live telemetry</span>
            </span>
            <button className="aire-chat-toggle-btn" onClick={() => setChatOpen(false)}>
              &laquo;
            </button>
          </div>

          <div className="aire-chat-messages">
            {messages.map((m, idx) => (
              <div key={idx} className={`aire-chat-msg ${m.role}`}>
                {m.role === "assistant" ? renderMarkdown(m.parts) : <p>{m.parts}</p>}
              </div>
            ))}
            {chatLoading && (
              <div className="aire-chat-msg assistant" style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <RefreshCw size={12} style={{ animation: "aire-spin 0.8s linear infinite" }} /> AIRE is analyzing telemetry...
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="aire-chat-input-area">
            <div className="aire-chat-input-wrapper">
              <textarea
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendQuery(inputValue);
                  }
                }}
                placeholder="Ask AIRE a question..."
                className="aire-chat-input"
                disabled={chatLoading}
              />
              <button
                className="aire-chat-send-btn"
                onClick={() => sendQuery(inputValue)}
                disabled={chatLoading || !inputValue.trim()}
              >
                <Play size={14} fill="white" />
              </button>
            </div>

            <div className="aire-chip-list">
              <span className="aire-chip" onClick={() => sendQuery("Why did reliability drop today?")}>
                🔍 Why did reliability drop?
              </span>
              <span className="aire-chip" onClick={() => sendQuery("How can we optimize our API spend?")}>
                💰 How can we optimize costs?
              </span>
              <span className="aire-chip" onClick={() => sendQuery("Run the parental leave query on HR agent")}>
                🏢 Run live RAG HR policy check
              </span>
              <span className="aire-chip" onClick={() => sendQuery("Run standard test suite on coding agent")}>
                💻 Run live code syntax check
              </span>
            </div>
          </div>
        </div>

        {/* ── Dashboard Content (Right Panel) ── */}
        <div className="aire-dashboard-content">
          
          {/* Re-open Sidebar trigger */}
          {!chatOpen && (
            <button
              onClick={() => setChatOpen(true)}
              style={{
                position: "fixed",
                bottom: 24,
                left: 24,
                zIndex: 100,
                background: "var(--gemini-gradient)",
                border: "none",
                borderRadius: "50%",
                width: 48,
                height: 48,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "white",
                boxShadow: "0 4px 15px rgba(139, 92, 246, 0.3)",
                cursor: "pointer",
                transition: "transform 0.2s"
              }}
              onMouseOver={e => e.currentTarget.style.transform = "scale(1.05)"}
              onMouseOut={e => e.currentTarget.style.transform = "scale(1)"}
            >
              <Brain size={20} />
            </button>
          )}

          {/* ── Tabs ── */}
          <div style={{ display: "flex", borderBottom: "0.5px solid var(--color-border-tertiary)", marginBottom: 16 }}>
            {TABS.map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`tab-btn ${tab === t ? "active" : ""}`}
                style={{ padding: "8px 16px", fontSize: 12, background: "none", border: "none",
                  color: tab === t ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                  cursor: "pointer", textTransform: "capitalize", fontWeight: tab === t ? 500 : 400,
                  "--tab-indicator-color": C.teal }}>
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
                  <Gauge score={scoreValue} />
                  <div style={{ marginTop: 16 }}>
                    {scoreBreakdown.map(s => <ScoreBar key={s.label} {...s} />)}
                  </div>
                </div>

                {/* Trend + root cause */}
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ ...card, flex: 1 }} className="chart-draw-on">
                    <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 8 }}>Score trend — last 6h</div>
                    <ResponsiveContainer width="100%" height={120}>
                      <AreaChart data={trendDataValue}>
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
                    {rootCauses.map((rc, idx) => (
                      <div key={rc.name} style={{ marginBottom: 10 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
                          <span style={{ color: "var(--color-text-primary)" }}>{rc.name}</span>
                          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                            <span style={{ color: rc.color, fontWeight: 500, ...mono }}>{rc.pct}%</span>
                            <span style={{ fontSize: 10, color: "var(--color-text-secondary)", ...mono }}>{rc.spanId}</span>
                          </div>
                        </div>
                        <div style={{ height: 5, background: "var(--color-border-tertiary)", borderRadius: 2 }}>
                          <div className="root-cause-bar-anim" style={{ height: "100%", background: rc.color, borderRadius: 2,
                            "--target-width": `${rc.pct}%`, animationDelay: `${idx * 120}ms` }} />
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
                    {agentDefs.map((a, idx) => {
                      const isScanning = analyzing && scanningAgentIdx === idx;
                      const isComplete = !analyzing || completedAgents[idx];
                      const isWaiting = analyzing && !isScanning && !isComplete;

                      let cardClass = "agent-card-hover";
                      if (isScanning) cardClass += " agent-card-scanning";

                      const glowStyles = {
                        background: "var(--color-background-secondary)",
                        borderRadius: "var(--border-radius-md)",
                        padding: 12,
                        borderLeft: `3px solid ${a.color}`,
                        "--hover-border-color": a.color,
                        "--hover-glow-color": `${a.color}25`,
                        "--agent-glow-color": `${a.color}25`,
                        "--agent-glow-color-soft": `${a.color}05`,
                        "--agent-glow-color-bright": a.color,
                        "--agent-glow-color-glow": `${a.color}35`,
                        opacity: isWaiting ? 0.45 : 1,
                        transition: "opacity 0.3s ease",
                      };

                      return (
                        <div key={a.name} className={cardClass} style={glowStyles}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              {a.Icon === "Activity" ? <Activity size={13} color={a.color} /> :
                               a.Icon === "AlertTriangle" ? <AlertTriangle size={13} color={a.color} /> :
                               a.Icon === "DollarSign" ? <DollarSign size={13} color={a.color} /> :
                               <Brain size={13} color={a.color} />}
                              <span style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-primary)" }}>{a.name}</span>
                            </div>
                            {isScanning ? (
                              <span className="pulse-badge" style={{ fontSize: 10, color: C.amber, background: `${C.amber}18`,
                                padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>scanning</span>
                            ) : isComplete ? (
                              <span style={{ fontSize: 10, color: C.teal, background: `${C.teal}18`,
                                padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>done</span>
                            ) : (
                              <span style={{ fontSize: 10, color: "var(--color-text-secondary)", background: "rgba(255,255,255,0.05)",
                                padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>waiting</span>
                            )}
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
                  <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                    {liveEvents.map((ev, i) => (
                      <div key={ev.time + ev.msg} className="feed-item-anim" style={{ display: "flex", gap: 8, padding: "4px 0",
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
              {agentDefs.map((a, idx) => {
                const isScanning = analyzing && scanningAgentIdx === idx;
                const isComplete = !analyzing || completedAgents[idx];
                const isWaiting = analyzing && !isScanning && !isComplete;

                let cardClass = "agent-card-hover";
                if (isScanning) cardClass += " agent-card-scanning";

                const glowStyles = {
                  ...card,
                  borderTop: `3px solid ${a.color}`,
                  "--hover-border-color": a.color,
                  "--hover-glow-color": `${a.color}25`,
                  "--agent-glow-color": `${a.color}25`,
                  "--agent-glow-color-soft": `${a.color}05`,
                  "--agent-glow-color-bright": a.color,
                  "--agent-glow-color-glow": `${a.color}35`,
                  opacity: isWaiting ? 0.45 : 1,
                  transition: "opacity 0.3s ease",
                };

                const rows = [
                  { label: "RAG-grounded",     val: a.name === "Recommendation Agent" ? "✓ yes"    : "—", ok: a.name === "Recommendation Agent" },
                  { label: "Safety filter",    val: a.name === "Recommendation Agent" ? "✓ passed" : "—", ok: a.name === "Recommendation Agent" },
                  { label: "Dynatrace trace",  val: "span_7f3a9c", ok: false },
                  { label: "Execution latency",val: a.latency,      ok: false },
                ];

                return (
                  <div key={a.name} className={cardClass} style={glowStyles}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                      {a.Icon === "Activity" ? <Activity size={20} color={a.color} /> :
                       a.Icon === "AlertTriangle" ? <AlertTriangle size={20} color={a.color} /> :
                       a.Icon === "DollarSign" ? <DollarSign size={20} color={a.color} /> :
                       <Brain size={20} color={a.color} />}
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-primary)" }}>{a.name}</div>
                        <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>Gemini Enterprise · {a.latency}</div>
                      </div>
                      {isScanning ? (
                        <span className="pulse-badge" style={{ marginLeft: "auto", fontSize: 10, color: C.amber,
                          background: `${C.amber}18`, padding: "2px 8px", borderRadius: "var(--border-radius-md)",
                          border: `0.5px solid ${C.amber}40` }}>SCANNING</span>
                      ) : isComplete ? (
                        <span style={{ marginLeft: "auto", fontSize: 10, color: a.color,
                          background: `${a.color}18`, padding: "2px 8px", borderRadius: "var(--border-radius-md)",
                          border: `0.5px solid ${a.color}40` }}>COMPLETE</span>
                      ) : (
                        <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--color-text-secondary)",
                          background: "rgba(255,255,255,0.05)", padding: "2px 8px", borderRadius: "var(--border-radius-md)",
                          border: "0.5px solid rgba(255,255,255,0.1)" }}>WAITING</span>
                      )}
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
                  { label: "Current daily cost",   val: dailyCostValue, sub: "before optimization",  color: C.red   },
                  { label: "Optimized daily cost",  val: showFix ? "$460" : (scoreValue === 88 ? "$410" : (scoreValue === 94 ? "$620" : "$460")), sub: "after applying fixes", color: C.teal  },
                  { label: "Daily saving",          val: showFix ? "$1,640" : (scoreValue === 88 ? "$1,690" : (scoreValue === 94 ? "$1,480" : "$1,640")), sub: "78% cost reduction",   color: C.green },
                ].map(m => (
                  <div key={m.label} style={{ ...metCard, textAlign: "center" }}>
                    <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 6 }}>{m.label}</div>
                    <div style={{ fontSize: 30, fontWeight: 500, color: m.color, ...mono, marginBottom: 3 }}>
                      <AnimatedNumber value={m.val} />
                    </div>
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
                  <BarChart data={tokenDataState}>
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
                  Agent trace waterfall — execution span list
                </div>
                <span style={{ fontSize: 11, color: "var(--color-text-secondary)", ...mono }}>
                  Captured live via OpenTelemetry capture instrumentation
                </span>
              </div>

              {spansState.map((s, idx) => {
                const maxLat = Math.max(...spansState.map(x => x.latency), 10);
                const barW = Math.round((s.latency / maxLat) * 100);
                const sc = spanColor(s.status);
                const isTimeout = s.status === "timeout" || s.id === "tool.shipping_api";
                const barClass = isTimeout ? "trace-bar-slow trace-bar-flash-red" : "trace-bar-fill";
                
                return (
                  <div key={idx} style={{ marginBottom: 14, paddingLeft: s.indent * 18 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                      {s.indent > 0 && <span style={{ color: "var(--color-text-secondary)", fontSize: 12 }}>└</span>}
                      
                      {/* Tooltip wrapping span id */}
                      <div className="span-tooltip-wrapper">
                        <span style={{ ...mono, fontSize: 12, color: "var(--color-text-primary)", minWidth: 168, borderBottom: "0.5px dashed rgba(255,255,255,0.2)" }}>{s.id}</span>
                        <div className="span-tooltip-content">
                          <strong style={{ color: "#c084fc" }}>Span details:</strong><br />
                          <strong>ID</strong>: {s.id}<br />
                          <strong>Time</strong>: {s.time}<br />
                          <strong>Latency</strong>: {s.latency}ms<br />
                          <strong>Status</strong>: <span style={{ color: sc }}>{s.status.toUpperCase()}</span><br />
                          {s.tokens > 0 && <><strong>Tokens</strong>: {s.tokens}<br /></>}
                          {s.speculative && <span style={{ color: C.amber }}>Speculative execution</span>}
                        </div>
                      </div>

                      {s.speculative && (
                        <span className="pulse-badge" style={{ fontSize: 10, color: C.amber, background: `${C.amber}18`,
                          padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>SPECULATIVE</span>
                      )}
                      {s.note && (
                        <span className="pulse-badge" style={{ fontSize: 10, color: sc, background: `${sc}15`,
                          padding: "1px 6px", borderRadius: "var(--border-radius-md)" }}>{s.note}</span>
                      )}
                      <span style={{ marginLeft: "auto", fontSize: 11, ...mono, color: sc, fontWeight: 500 }}>
                        {s.status.toUpperCase()}
                      </span>
                      <span style={{ fontSize: 11, ...mono, color: "var(--color-text-secondary)", minWidth: 62, textAlign: "right" }}>
                        {s.latency}ms
                      </span>
                    </div>
                    <div style={{ height: 6, background: "var(--color-border-tertiary)", borderRadius: 3, overflow: "hidden" }}>
                      <div className={barClass} style={{ height: "100%", width: `${barW}%`, background: sc, borderRadius: 3, opacity: 0.85,
                        animationDelay: `${idx * 250}ms` }} />
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
                  Timeout anomalies and rate limit errors are highlighted in red above.
                </div>
                <div style={{ color: C.amber, display: "flex", gap: 8 }}>
                  <Zap size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  Speculative tool calls and RAG context blocks are flagged with warning tags.
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
                {recs.map((rec, rIdx) => {
                  const accentStyles = {
                    ...card,
                    "--rec-accent-color": rec.color,
                    "--rec-glow-color": `${rec.color}18`,
                    animationDelay: `${rIdx * 150}ms`,
                    marginBottom: 10,
                    cursor: "pointer",
                    borderRadius: `0 var(--border-radius-lg) var(--border-radius-lg) 0`,
                    outline: selectedRec === rec.rank ? `1.5px solid ${rec.color}` : "none",
                    outlineOffset: 1
                  };
                  
                  return (
                    <div key={rec.rank}
                      onClick={() => setSelRec(selectedRec === rec.rank ? null : rec.rank)}
                      className="rec-card-anim rec-card-theme"
                      style={accentStyles}>
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
                        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "0.5px solid var(--color-border-tertiary)" }}>
                          {/* RAG Reference Source with animated confidence bar */}
                          <div style={{ marginBottom: 12, background: "rgba(255, 255, 255, 0.01)", padding: "10px 12px", borderRadius: "var(--border-radius-md)", border: "0.5px solid rgba(255,255,255,0.03)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 4 }}>
                              <span>RAG Reference Citation</span>
                              <span style={{ color: rec.color, fontWeight: 600 }}>{rec.confidence} Match</span>
                            </div>
                            <div style={{ fontSize: 11.5, color: "var(--color-text-primary)", fontWeight: 500, marginBottom: 6 }}>
                              {rec.source}
                            </div>
                            {/* Confidence bar */}
                            <div style={{ height: 4, background: "var(--color-border-tertiary)", borderRadius: 2 }}>
                              <div className="root-cause-bar-anim" style={{ height: "100%", width: rec.confidence, background: rec.color, borderRadius: 2,
                                "--target-width": rec.confidence }} />
                            </div>
                          </div>

                          {/* Before/After Table */}
                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
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
                        </div>
                      )}
                    </div>
                  );
                })}
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

        </div>
      </div>

      <style>{`
        .aire-sr { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); border:0; }
        @keyframes aire-pulse { 0%,100%{opacity:1}  50%{opacity:0.3} }
        @keyframes aire-spin  { to{transform:rotate(360deg)} }
        button:focus-visible, select:focus-visible { outline:2px solid ${C.teal}; outline-offset:2px; }
      `}</style>
    </div>
  );
}
