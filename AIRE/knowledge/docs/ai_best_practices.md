# AI Agent Best Practices — AIRE Knowledge Base

## 1. Prompt Engineering

### System Prompt Design
- Be explicit about the agent's role, constraints, and output format
- Include a "safety contract" at the top: what the agent is/isn't allowed to do
- Use delimiters (`---`, `===`) to separate sections clearly
- Always specify output format (JSON, markdown, plain text) with an example

### Instruction Hierarchy
```
1. Safety rules (immutable)
2. Business constraints (e.g., "never delete production data")
3. Task instructions
4. Format instructions
5. Examples (few-shot)
```

### Few-Shot Examples
- Include 2–3 examples for novel or ambiguous tasks
- Ensure examples cover edge cases, not just happy paths
- Order: easy → medium → hard

---

## 2. Tool Use Best Practices

### Tool Definition
- Keep tool descriptions to ≤ 100 words
- Use snake_case for parameter names
- Mark optional vs required parameters explicitly
- Provide example values in the description

### Tool Result Handling
- Always validate tool outputs before passing to next step
- Handle null/empty results gracefully
- Log every tool call: name, inputs, output size, latency

### Avoiding Tool Abuse
- Set max_tool_calls per turn (recommended: 10)
- Implement a circuit breaker: stop after 3 consecutive failures of the same tool
- Never pass unsanitized user input directly to tool parameters

---

## 3. Retrieval-Augmented Generation (RAG)

### Chunking Strategy
- Chunk size: 512–1024 tokens for most docs
- Use semantic chunking over fixed-size for narrative documents
- Always include metadata: source, date, section title

### Retrieval Quality
- Use hybrid search: dense (embedding) + sparse (BM25)
- Re-rank with cross-encoder before injecting into context
- Set a minimum relevance threshold: discard chunks with score < 0.4

### Context Window Management
- Budget: 30% system prompt, 40% retrieved context, 30% conversation
- Prefer fewer high-quality chunks over many low-quality ones
- Always inject context BEFORE the user message

---

## 4. Observability

### What to Log
Every LLM call should emit:
- `trace_id` — unique per user session
- `span_id` — unique per model call
- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `latency_ms` — time to first token + total
- `model_id`, `temperature`, `top_p`
- `tool_calls` — list of {name, args, result_size, latency}
- `error_code` if applicable

### Alerting Thresholds
| Metric | Warning | Critical |
|---|---|---|
| P99 Latency | > 3s | > 8s |
| Tool Failure Rate | > 2% | > 10% |
| Token Usage | > 150% baseline | > 200% baseline |
| Error Rate | > 1% | > 5% |

---

## 5. Safety

### Content Filtering
- Apply input filtering: block prompt injection patterns
- Apply output filtering: detect PII leakage, harmful content
- Use model-side safety settings (Gemini: BLOCK_MEDIUM_AND_ABOVE)

### Action Validation
- Classify all agent actions: READ / WRITE / DELETE / EXECUTE
- Require explicit confirmation for WRITE and EXECUTE
- Hard-block DELETE on production resources

### Audit Logging
- Log every action with: agent_id, user_id, action_type, resource, timestamp
- Retain audit logs for 90 days minimum
- Immutable audit log: write-once storage (GCS with object lock)
