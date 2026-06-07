"""
Coding Agent — Layer 1 demo agent.
AI-assisted code generation, review, and debugging.
Uses large context windows — ideal for cost optimization analysis by AIRE.
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

MODEL = "gemini-1.5-pro"
AGENT_NAME = "coding-agent"
SYSTEM_PROMPT = """You are an expert software engineer. You write clean, well-tested,
production-ready code. You explain your reasoning, follow best practices,
and always consider edge cases and error handling."""

CODING_TASKS = [
    {
        "type": "generate",
        "description": "Write a Python async REST API client with retry logic and rate limiting",
        "context_size": "medium",
    },
    {
        "type": "review",
        "description": "Review this Python code for bugs and security issues",
        "code": "def get_user(id): return db.execute(f'SELECT * FROM users WHERE id={id}')",
        "context_size": "small",
    },
    {
        "type": "debug",
        "description": "Debug: KeyError in dict access during batch processing of 10k records",
        "stack_trace": "KeyError: 'user_id' at line 47 in process_batch()",
        "context_size": "large",
    },
    {
        "type": "refactor",
        "description": "Refactor this 500-line monolithic function into clean modular services",
        "context_size": "xlarge",
    },
]

# Context sizes in approximate tokens — for cost analysis
CONTEXT_TOKEN_MAP = {"small": 500, "medium": 2000, "large": 5000, "xlarge": 12000}


def run_linter(code: str) -> dict:
    """Simulated linter tool — fast, rarely fails."""
    time.sleep(random.uniform(0.05, 0.15))
    issues = random.randint(0, 5)
    return {"issues": issues, "warnings": random.randint(0, 10), "passed": issues == 0}


def run_tests(code: str) -> dict:
    """Simulated test runner — medium latency, occasional failures."""
    time.sleep(random.uniform(0.3, 1.2))
    if random.random() < 0.2:
        raise RuntimeError("Test runner OOMkilled — container exceeded 512MB memory limit")
    passed = random.randint(8, 12)
    total = 12
    return {"passed": passed, "total": total, "coverage": f"{random.randint(70,95)}%"}


def process_coding_task(task: dict, tracer, meter) -> dict:
    start = time.monotonic()
    ctx_tokens = CONTEXT_TOKEN_MAP.get(task.get("context_size", "medium"), 2000)
    result = {"task": task["type"], "status": "completed"}

    with tracer.start_as_current_span(
        "coding.task",
        attributes={
            "coding.task_type": task["type"],
            "coding.context_size": task.get("context_size", "medium"),
            "coding.estimated_context_tokens": ctx_tokens,
            "agent.name": AGENT_NAME,
        },
    ) as span:
        try:
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            model = genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)

            prompt = f"Task: {task['description']}"
            if "code" in task:
                prompt += f"\n\nCode to review:\n```python\n{task['code']}\n```"
            if "stack_trace" in task:
                prompt += f"\n\nStack trace:\n{task['stack_trace']}"

            # Simulate large context padding (realistic for coding agents)
            context_padding = "# existing codebase context\n" * (ctx_tokens // 10)
            full_prompt = f"{context_padding}\n\n{prompt}"
            prompt_tokens = ctx_tokens + len(prompt.split()) * 2

            response = model.generate_content(full_prompt)
            completion_tokens = len(response.text.split()) * 2

            # Tool: linter
            with tracer.start_as_current_span("tool.linter"):
                lint_result = run_linter(response.text)
                span.set_attribute("coding.lint_issues", lint_result["issues"])

            # Tool: test runner
            with tracer.start_as_current_span("tool.test_runner"):
                try:
                    test_result = run_tests(response.text)
                    span.set_attribute("coding.test_pass_rate",
                                       test_result["passed"] / test_result["total"])
                except RuntimeError as e:
                    span.set_attribute("tool.test_runner.error", str(e))
                    test_result = {"passed": 0, "total": 0, "error": str(e)}

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

            result["code"] = response.text[:200]
            result["lint"] = lint_result
            result["tests"] = test_result
            span.set_attribute("coding.total_tokens", prompt_tokens + completion_tokens)
            logger.info(
                "[%s] Done in %.0fms | tokens: %d | lint issues: %d",
                task["type"], latency_ms, prompt_tokens + completion_tokens, lint_result["issues"]
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            record_llm_call(
                tracer, meter, model=MODEL,
                prompt_tokens=ctx_tokens, completion_tokens=0,
                latency_ms=latency_ms, success=False, error=str(e)
            )
            result["status"] = "error"
            result["error"] = str(e)
            span.set_attribute("error", True)
            logger.exception("Coding task failed")

    return result


def run():
    tracer, meter = setup_otel(AGENT_NAME)
    logger.info("Coding Agent started.")

    for task in CODING_TASKS:
        logger.info("Processing %s task…", task["type"])
        result = process_coding_task(task, tracer, meter)
        logger.info("Result: %s", result["status"])
        time.sleep(0.3)


if __name__ == "__main__":
    run()