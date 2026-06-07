# AIRE Reliability Playbooks

## Overview
This document provides structured playbooks for diagnosing and resolving common reliability issues in AI agent systems.

---

## Playbook 1 — High Latency (P99 > 5s)

### Symptoms
- Agent response P99 latency exceeds 5 seconds
- Dynatrace traces show long tool-call chains
- Users report slow completions

### Diagnosis Steps
1. Check Dynatrace APM traces for the slowest spans
2. Identify whether latency is in: LLM inference, tool calls, retrieval, or network I/O
3. Check token counts — large prompts increase TTFT significantly

### Remediation
- **LLM inference**: Switch to a lighter model for simple tasks (Gemini Flash instead of Pro)
- **Tool calls**: Add caching layer for frequently called external APIs
- **Retrieval**: Reduce retrieved context chunks from 12 → 5; apply MMR re-ranking
- **Network I/O**: Move Cloud Run services closer to the model endpoint region

### Escalation Threshold
If P99 > 10s for more than 5 minutes, trigger PagerDuty alert.

---

## Playbook 2 — High Tool Call Failure Rate (> 5%)

### Symptoms
- Tool call error rate exceeds 5% in Dynatrace metrics
- Agents retrying tools repeatedly
- Final response quality degraded

### Diagnosis Steps
1. Pull tool call traces from Dynatrace — group by `tool.name`
2. Identify which specific tool is failing
3. Check error messages: timeout vs authentication vs schema mismatch

### Remediation
- **Timeout**: Increase tool timeout; add exponential backoff with jitter
- **Authentication**: Rotate API keys via Secret Manager
- **Schema mismatch**: Update tool definition; bump schema version

### Retry Policy (Standard)
```
max_retries: 3
initial_delay: 1s
multiplier: 2.0
max_delay: 30s
jitter: true
```

---

## Playbook 3 — Token Budget Overrun

### Symptoms
- `context_window_exceeded` errors
- Prompts being truncated mid-reasoning
- Agent "forgets" earlier instructions

### Diagnosis Steps
1. Log token counts per request: prompt tokens, completion tokens, total
2. Identify high-token patterns: system prompt, retrieval chunks, tool results
3. Check if multi-turn conversations are accumulating context

### Remediation
- Apply sliding window to conversation history (keep last N turns)
- Summarize older turns instead of keeping full text
- Reduce retrieval chunks: top_k 10 → 5
- Move static instructions to a cached system prompt

---

## Playbook 4 — Hallucination / Low Grounding Score

### Symptoms
- Agent produces recommendations not backed by docs
- Fact-checking fails against source documents
- Users report incorrect or fabricated information

### Diagnosis Steps
1. Check if Agent Search was queried before generating recommendation
2. Verify RAG pipeline is returning valid context (check confidence_score)
3. Review safety filter logs — was generation temperature too high?

### Remediation
- Always inject RAG context before final generation step
- Lower temperature: 0.2 → 0.0 for factual responses
- Add citation requirement to system prompt
- Implement answer verification step (G-Eval or LLM-as-judge)

---

## Playbook 5 — Cost Spike (> 2x Baseline)

### Symptoms
- Token usage per session doubles overnight
- Cloud billing alert triggered
- Cost per conversation exceeds SLA

### Diagnosis Steps
1. Pull cost_per_session metrics from Dynatrace
2. Identify agent type with highest per-session cost
3. Check if retrieval chunk count was recently increased
4. Look for prompt injection or adversarial inputs bloating context

### Remediation
- Cap max_tokens per response: 2048
- Implement context compression using summary models
- Add per-user rate limiting
- Alert on sessions with > 50K tokens
