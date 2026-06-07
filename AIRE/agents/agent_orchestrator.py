"""
Agent Orchestrator — Layer 4.
Chains all four AIRE agents (Reliability → Root Cause → Cost → Recommendation)
into a single analysis pipeline. This is the main entry point for AIRE analysis.
"""

import os
import json
import time
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from gemini_client import GeminiClient
from reliability_agent import ReliabilityAgent, ReliabilityScore
from root_cause_agent import RootCauseAgent, RCAReport
from cost_agent import CostAgent, CostReport
from recommendation_agent import RecommendationAgent, RecommendationReport

logger = logging.getLogger(__name__)


@dataclass
class AIREAnalysis:
    """Complete AIRE analysis output for one agent."""
    agent_name: str
    analyzed_at: str
    reliability: dict
    root_cause: dict
    cost: dict
    recommendations: dict
    pipeline_duration_ms: float
    gemini_tokens_used: int

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


class AgentOrchestrator:
    """
    Orchestrates the full AIRE analysis pipeline.
    Supports both sequential and parallel agent execution.
    """

    def __init__(
        self,
        rag_client=None,
        shared_gemini_client: GeminiClient | None = None,
    ):
        # Share one Gemini client across agents to unify token tracking
        gemini = shared_gemini_client or GeminiClient(
            model_name="gemini-1.5-pro",
            force_json=True,
        )

        self.reliability_agent = ReliabilityAgent(gemini_client=gemini)
        self.root_cause_agent = RootCauseAgent(gemini_client=gemini)
        self.cost_agent = CostAgent(
            gemini_client=GeminiClient(model_name="gemini-1.5-flash", force_json=True)
        )
        self.recommendation_agent = RecommendationAgent(gemini_client=gemini)
        self.rag_client = rag_client

        logger.info("AgentOrchestrator initialized with 4 agents")

    def _get_rag_context(self, topic: str) -> str:
        """Fetch relevant context from Agent Search (RAG)."""
        if not self.rag_client:
            return ""
        try:
            results = self.rag_client.search(topic, top_k=3)
            return "\n\n".join([r.get("content", "") for r in results])
        except Exception as e:
            logger.warning("RAG context fetch failed: %s", e)
            return ""

    def analyze_agent(
        self,
        agent_name: str,
        traces: list[dict],
        metrics: dict,
        token_breakdown: list[dict] | None = None,
    ) -> AIREAnalysis:
        """
        Run the full AIRE pipeline for one agent.
        Pipeline: Reliability → Root Cause → Cost → Recommendation (sequential)
        """
        pipeline_start = time.monotonic()
        logger.info("=" * 60)
        logger.info("AIRE Pipeline started for: %s", agent_name)
        logger.info("=" * 60)

        error_traces = [t for t in traces if not t.get("llm.success", True)]

        # ── Step 1: Reliability Analysis ─────────────────────────────────────
        logger.info("[1/4] Running Reliability Analysis…")
        rag_reliability = self._get_rag_context("AI agent reliability scoring best practices")
        reliability: ReliabilityScore = self.reliability_agent.analyze(
            agent_name, traces, metrics, rag_context=rag_reliability
        )

        # ── Step 2: Root Cause Analysis ──────────────────────────────────────
        logger.info("[2/4] Running Root Cause Analysis…")
        rag_rca = self._get_rag_context("root cause analysis AI agent failures timeout retry")
        rca: RCAReport = self.root_cause_agent.analyze(
            agent_name, error_traces, traces, rag_context=rag_rca
        )

        # ── Step 3: Cost Optimization ─────────────────────────────────────────
        logger.info("[3/4] Running Cost Analysis…")
        rag_cost = self._get_rag_context("LLM cost optimization token reduction strategies")
        cost: CostReport = self.cost_agent.analyze(
            agent_name, metrics, token_breakdown or [], rag_context=rag_cost
        )

        # ── Step 4: Recommendation Synthesis ─────────────────────────────────
        logger.info("[4/4] Synthesizing Recommendations…")
        rag_rec = self._get_rag_context("AI agent improvement recommendations engineering best practices")
        recommendations: RecommendationReport = self.recommendation_agent.synthesize(
            agent_name,
            reliability_result=reliability.to_dict(),
            rca_result=rca.to_dict(),
            cost_result=cost.to_dict(),
            rag_context=rag_rec,
        )

        pipeline_ms = (time.monotonic() - pipeline_start) * 1000

        analysis = AIREAnalysis(
            agent_name=agent_name,
            analyzed_at=datetime.utcnow().isoformat() + "Z",
            reliability=reliability.to_dict(),
            root_cause=rca.to_dict(),
            cost=cost.to_dict(),
            recommendations=recommendations.to_dict(),
            pipeline_duration_ms=round(pipeline_ms, 1),
            gemini_tokens_used=self.reliability_agent.gemini.stats["total_tokens"],
        )

        logger.info("=" * 60)
        logger.info("AIRE Pipeline complete for: %s", agent_name)
        logger.info("  Reliability Score: %.1f (%s)", reliability.score, reliability.grade)
        logger.info("  Root Cause: %s", rca.root_cause.title)
        logger.info("  Est. Monthly Cost: $%.2f",
                    cost.current_cost_analysis.get("estimated_monthly_usd", 0))
        logger.info("  P0 Recommendations: %d", len(recommendations.p0_items))
        logger.info("  Pipeline Duration: %.0fms", pipeline_ms)
        logger.info("=" * 60)

        return analysis

    def analyze_all_agents(
        self,
        agent_datasets: list[tuple[str, list[dict], dict]],
        parallel: bool = False,
    ) -> list[AIREAnalysis]:
        """
        Analyze multiple agents.
        Set parallel=True to run agents concurrently (faster but more API calls).
        """
        if parallel:
            return self._analyze_parallel(agent_datasets)
        else:
            return [
                self.analyze_agent(name, traces, metrics)
                for name, traces, metrics in agent_datasets
            ]

    def _analyze_parallel(
        self,
        agent_datasets: list[tuple[str, list[dict], dict]],
    ) -> list[AIREAnalysis]:
        """Parallel execution — each agent runs concurrently."""
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.analyze_agent, name, traces, metrics): name
                for name, traces, metrics in agent_datasets
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error("Parallel analysis failed for '%s': %s", agent, e)

        return sorted(results, key=lambda a: a.reliability["score"])


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    from dotenv import load_dotenv
    load_dotenv()

    # Demo run with simulated data
    from scripts.seed_demo_data import generate_demo_dataset
    dataset = generate_demo_dataset()

    orchestrator = AgentOrchestrator()
    analyses = orchestrator.analyze_all_agents(dataset)

    output_path = "/tmp/aire_analysis.json"
    with open(output_path, "w") as f:
        json.dump([a.to_dict() for a in analyses], f, indent=2, default=str)

    print(f"\n✅ Analysis complete. Results saved to {output_path}")
    print(f"   Agents analyzed: {len(analyses)}")
    print(f"   Lowest score: {min(a.reliability['score'] for a in analyses):.1f}")