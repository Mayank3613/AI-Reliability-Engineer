"""
Enterprise Agent — Layer 1 demo agent.
Internal enterprise assistant: HR queries, policy lookup, procurement, IT.
Uses RAG heavily — designed to show retrieval cost patterns to AIRE.
"""

import os
import time
import random
import logging
from dotenv import load_dotenv
import google.generativeai as genai

from otel_setup import setup_otel, record_llm_call

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")  # Flash model for enterprise — cost-conscious
AGENT_NAME = "enterprise-agent"
SYSTEM_PROMPT = """You are an internal enterprise assistant with access to company policies,
HR documents, IT runbooks, and procurement systems. Always cite the policy source.
Never share confidential data. Escalate ambiguous requests to the relevant department."""

ENTERPRISE_QUERIES = [
    {"dept": "HR", "query": "What is the parental leave policy for contractors?"},
    {"dept": "IT", "query": "How do I request VPN access for a new team member?"},
    {"dept": "Finance", "query": "What is the approval process for software purchases over $5000?"},
    {"dept": "Legal", "query": "Can I share a customer's data with a third-party integration partner?"},
    {"dept": "IT", "query": "My laptop won't connect to the company Wi-Fi after the OS update."},
    {"dept": "HR", "query": "How do I submit a reimbursement for home office equipment?"},
]


def retrieve_policy_docs(dept: str, query: str) -> list[dict]:
    """Simulated RAG retrieval — returns policy chunks with scores."""
    time.sleep(random.uniform(0.1, 0.6))
    q_lower = query.lower()
    if "timeout" in q_lower or "slow" in q_lower:
        time.sleep(1.5)
        raise TimeoutError("Vector search timed out — index overloaded")
    if "quota" in q_lower or "limit" in q_lower:
        # We can trigger quota limit issue directly
        raise RuntimeError("ServiceUnavailable: Vertex AI prediction quota exhausted")
    num_chunks = random.randint(3, 12)  # Variable retrieval — cost analysis target
    if num_chunks > 8 and random.random() < 0.3:
        raise TimeoutError("Vector search timed out — index overloaded")
    return [
        {
            "source": f"{dept.lower()}_policy_v{random.randint(1,3)}.pdf",
            "chunk": f"Policy excerpt {i}: [Relevant {dept} policy text...]",
            "score": round(random.uniform(0.6, 0.99), 3),
        }
        for i in range(num_chunks)
    ]


def lookup_employee_directory(name: str) -> dict:
    """Simulated employee directory lookup."""
    time.sleep(0.05)
    return {
        "name": name,
        "department": "Engineering",
        "manager": "Jane Smith",
        "location": "Remote",
    }


def create_it_ticket(summary: str, priority: str) -> str:
    """Create IT support ticket."""
    ticket_id = f"IT-{random.randint(10000, 99999)}"
    return f"Ticket {ticket_id} created. Priority: {priority}. ETA: 4 hours."


def handle_enterprise_query(query_obj: dict, tracer, meter) -> dict:
    dept = query_obj["dept"]
    query = query_obj["query"]
    start = time.monotonic()
    result = {"dept": dept, "query": query, "status": "resolved"}

    with tracer.start_as_current_span(
        "enterprise.query",
        attributes={
            "enterprise.dept": dept,
            "enterprise.query_preview": query[:80],
            "agent.name": AGENT_NAME,
        },
    ) as span:
        try:
            # RAG retrieval
            with tracer.start_as_current_span("tool.policy_retrieval") as tool_span:
                try:
                    docs = retrieve_policy_docs(dept, query)
                    tool_span.set_attribute("rag.chunks_retrieved", len(docs))
                    tool_span.set_attribute(
                        "rag.avg_score",
                        round(sum(d["score"] for d in docs) / len(docs), 3),
                    )
                    context = "\n".join(
                        [f"[{d['source']}] {d['chunk']}" for d in docs]
                    )
                    span.set_attribute("rag.chunks_retrieved", len(docs))
                except TimeoutError as e:
                    tool_span.set_attribute("error", True)
                    context = "Policy retrieval unavailable — using general knowledge."
                    span.set_attribute("rag.fallback", True)
                    logger.warning("RAG timeout: %s", e)

            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            model = genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)

            prompt = (
                f"Department: {dept}\n"
                f"Employee question: {query}\n\n"
                f"Relevant policy documents:\n{context}\n\n"
                f"Provide a clear, cited answer."
            )
            prompt_tokens = len(prompt.split()) * 2

            response = model.generate_content(prompt)
            latency_ms = (time.monotonic() - start) * 1000
            completion_tokens = len(response.text.split()) * 2

            # IT escalation check
            if dept == "IT" and "ticket" in response.text.lower():
                with tracer.start_as_current_span("tool.create_it_ticket"):
                    ticket = create_it_ticket(query, "medium")
                    span.set_attribute("enterprise.it_ticket", ticket)

            record_llm_call(
                tracer, meter,
                model=MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                success=True,
            )

            result["answer"] = response.text[:300]
            span.set_attribute("enterprise.answered", True)
            logger.info("[%s] Resolved in %.0fms | chunks: %s", dept, latency_ms,
                        span.attributes.get("rag.chunks_retrieved", "?"))

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            record_llm_call(
                tracer, meter, model=MODEL,
                prompt_tokens=0, completion_tokens=0,
                latency_ms=latency_ms, success=False, error=str(e)
            )
            result["status"] = "error"
            result["error"] = str(e)
            span.set_attribute("error", True)
            logger.exception("Enterprise query failed")

    return result


def run(num_queries: int = 4):
    tracer, meter = setup_otel(AGENT_NAME)
    logger.info("Enterprise Agent started. Queries: %d", num_queries)

    for q in ENTERPRISE_QUERIES[:num_queries]:
        logger.info("[%s] %s", q["dept"], q["query"])
        result = handle_enterprise_query(q, tracer, meter)
        logger.info("Status: %s", result["status"])
        time.sleep(0.5)


if __name__ == "__main__":
    run()