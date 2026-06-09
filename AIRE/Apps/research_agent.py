"""
Research Agent — Layer 1 demo agent.
Performs multi-step web research using Gemini with search grounding.
Heavy tool usage generates rich telemetry for AIRE cost analysis.
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

MODEL = os.environ.get("GEMINI_PRO_MODEL", "gemini-2.5-pro")
AGENT_NAME = "research-agent"
SYSTEM_PROMPT = """You are a deep research analyst. Given a topic, you:
1. Break it into sub-questions
2. Search each sub-question
3. Synthesize findings into a structured report
Always cite sources and acknowledge uncertainty."""

RESEARCH_TOPICS = [
    "Impact of AI agents on enterprise software development productivity",
    "Best practices for LLM observability in production systems",
    "Cost optimization strategies for large language model deployments",
    "Reliability patterns for multi-agent AI orchestration systems",
]


def web_search(query: str) -> str:
    """Simulated web search — high latency, occasional failures."""
    delay = random.uniform(0.5, 2.5)
    time.sleep(delay)
    q_lower = query.lower()
    if "timeout" in q_lower or "slow" in q_lower:
        time.sleep(1.5)
        raise TimeoutError("Web search timed out")
    if "rate limit" in q_lower or "429" in q_lower:
        raise ConnectionError(f"Search API rate limit exceeded for query: '{query}'")
    if random.random() < 0.15:  # 15% failure — creates root cause patterns
        raise ConnectionError(f"Search API rate limit exceeded for query: '{query}'")
    return (
        f"Search results for '{query}': [Article 1: Comprehensive overview...] "
        f"[Article 2: Case study from Fortune 500...] [Article 3: Academic paper 2024...]"
    )


def fetch_article(url: str) -> str:
    """Simulated article fetcher."""
    time.sleep(random.uniform(0.3, 1.0))
    return f"Article content from {url}: [Full text with data, statistics, expert quotes...]"


def synthesize_report(findings: list[str], topic: str) -> str:
    """Combine all research into final report via Gemini."""
    combined = "\n\n".join(findings)
    return f"# Research Report: {topic}\n\n## Key Findings\n{combined}\n\n## Conclusion\n[AI-generated synthesis]"


def research_topic(topic: str, tracer, meter) -> dict:
    start = time.monotonic()
    result = {"topic": topic, "status": "completed", "findings": [], "error": None}

    with tracer.start_as_current_span(
        "research.full_pipeline",
        attributes={"research.topic": topic[:100], "agent.name": AGENT_NAME},
    ) as span:
        sub_questions = [
            f"What are the key challenges in {topic}?",
            f"What are the best solutions for {topic}?",
            f"What do experts say about {topic}?",
        ]

        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for q in sub_questions:
            with tracer.start_as_current_span(
                "research.sub_question",
                attributes={"research.question": q},
            ):
                try:
                    search_result = web_search(q)
                    prompt = f"Question: {q}\nSearch results: {search_result}\nSummarize the key insight in 2-3 sentences."
                    pt = len(prompt.split()) * 2

                    try:
                        response = model.generate_content(prompt)
                        res_text = response.text
                        ct = len(res_text.split()) * 2
                    except Exception as e:
                        logger.warning("Gemini call failed in research agent, simulating findings: %s", e)
                        res_text = f"Simulated key insight for question '{q}' based on search results."
                        ct = len(res_text.split()) * 2
                        time.sleep(0.3)

                    total_prompt_tokens += pt
                    total_completion_tokens += ct
                    result["findings"].append(res_text)

                except ConnectionError as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", "search_rate_limit")
                    result["findings"].append(f"[Search failed for: {q}]")
                    logger.warning("Search failed: %s", e)

        latency_ms = (time.monotonic() - start) * 1000
        record_llm_call(
            tracer,
            meter,
            model=MODEL,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            latency_ms=latency_ms,
            success=True,
        )

        span.set_attribute("research.findings_count", len(result["findings"]))
        span.set_attribute("research.total_tokens", total_prompt_tokens + total_completion_tokens)
        logger.info("Research completed in %.0fms | tokens: %d", latency_ms, total_prompt_tokens + total_completion_tokens)

    return result


def run(num_topics: int = 2):
    tracer, meter = setup_otel(AGENT_NAME)
    logger.info("Research Agent started. Topics: %d", num_topics)

    for topic in RESEARCH_TOPICS[:num_topics]:
        logger.info("Researching: %s", topic)
        result = research_topic(topic, tracer, meter)
        logger.info("Status: %s | Findings: %d", result["status"], len(result["findings"]))
        time.sleep(1)


if __name__ == "__main__":
    run()