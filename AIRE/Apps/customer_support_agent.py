"""
Customer Support Agent — Layer 1 demo agent.
Handles user support tickets using Gemini + tool calls.
Instrumented with OTel to emit telemetry AIRE will analyze.
"""

import os
import time
import random
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from opentelemetry import trace

from otel_setup import setup_otel, record_llm_call

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Agent config ---
MODEL = "gemini-1.5-pro"
AGENT_NAME = "customer-support-agent"
SYSTEM_PROMPT = """You are a helpful customer support agent for a SaaS platform.
You have access to tools: search_knowledge_base, lookup_order, escalate_ticket.
Resolve issues efficiently. Always be empathetic and clear."""

SAMPLE_TICKETS = [
    "My account is locked and I can't log in.",
    "I was charged twice for my subscription this month.",
    "How do I export my data to CSV?",
    "The API is returning 429 errors on my integration.",
    "I need to add a new team member but the invite button is greyed out.",
]


def search_knowledge_base(query: str) -> str:
    """Simulated KB search tool call."""
    time.sleep(random.uniform(0.1, 0.4))
    if random.random() < 0.1:  # 10% failure rate for AIRE to catch
        raise TimeoutError("Knowledge base search timed out after 30s")
    return f"KB Article: '{query}' — Found relevant documentation in 3 articles."


def lookup_order(order_id: str) -> str:
    """Simulated order lookup tool call."""
    time.sleep(random.uniform(0.05, 0.2))
    return f"Order {order_id}: Status=COMPLETED, Amount=$49.99, Date=2024-01-15"


def escalate_ticket(reason: str) -> str:
    """Escalate to human agent."""
    return f"Ticket escalated. Reason: {reason}. ETA: 2 business hours."


def handle_ticket(ticket: str, tracer, meter) -> dict:
    """Process one support ticket end-to-end with full OTel instrumentation."""
    start = time.monotonic()
    result = {"ticket": ticket, "status": "resolved", "error": None}

    with tracer.start_as_current_span(
        "support.handle_ticket",
        attributes={
            "ticket.text": ticket[:120],
            "agent.name": AGENT_NAME,
        },
    ) as span:
        try:
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            model = genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)

            # Tool call: KB search
            with tracer.start_as_current_span("tool.search_knowledge_base"):
                kb_result = search_knowledge_base(ticket)
                span.set_attribute("tool.kb_result_length", len(kb_result))

            prompt = f"Support ticket: {ticket}\n\nKnowledge base context: {kb_result}\n\nProvide a resolution."
            prompt_tokens = len(prompt.split()) * 2  # rough estimate

            try:
                response = model.generate_content(prompt)
                res_text = response.text
                completion_tokens = len(res_text.split()) * 2
            except Exception as e:
                logger.warning("Gemini call failed, falling back to simulated resolution: %s", e)
                res_text = f"Simulated resolution for ticket: '{ticket}'. Context used: '{kb_result}'."
                completion_tokens = len(res_text.split()) * 2
                time.sleep(0.5)

            latency_ms = (time.monotonic() - start) * 1000

            record_llm_call(
                tracer,
                meter,
                model=MODEL,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                success=True,
            )

            result["response"] = res_text
            span.set_attribute("ticket.resolved", True)
            logger.info("Ticket resolved in %.0fms", latency_ms)

        except TimeoutError as e:
            latency_ms = (time.monotonic() - start) * 1000
            record_llm_call(
                tracer,
                meter,
                model=MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )
            result["status"] = "failed"
            result["error"] = str(e)
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.error("Ticket failed: %s", e)

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            record_llm_call(
                tracer,
                meter,
                model=MODEL,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )
            result["status"] = "error"
            result["error"] = str(e)
            span.set_attribute("error", True)
            logger.exception("Unexpected error processing ticket")

    return result


def run(num_tickets: int = 5):
    tracer, meter = setup_otel(AGENT_NAME)
    logger.info("Customer Support Agent started. Processing %d tickets…", num_tickets)

    for i, ticket in enumerate(SAMPLE_TICKETS[:num_tickets]):
        logger.info("--- Ticket %d/%d ---", i + 1, num_tickets)
        result = handle_ticket(ticket, tracer, meter)
        logger.info("Result: %s", result.get("status"))
        time.sleep(0.5)

    logger.info("All tickets processed.")


if __name__ == "__main__":
    run()