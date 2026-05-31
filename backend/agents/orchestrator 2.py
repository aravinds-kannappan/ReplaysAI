"""
Orchestrator: runs all 3 agents in parallel via asyncio.gather().
Agent 3 (LLM) receives Agent 1 + 2 outputs as context.
"""
import asyncio

from backend.agents.event_extraction import event_extraction_agent
from backend.agents.cv_classification import cv_classification_agent
from backend.agents.llm_summarization import llm_summarization_agent


async def generate_game_recap(game_id: int) -> dict:
    print(f"[Orchestrator] Starting parallel agents for game {game_id}...")

    # Agents 1 and 2 run fully in parallel
    features, cv_results = await asyncio.gather(
        event_extraction_agent(game_id),
        cv_classification_agent(game_id),
    )

    print(f"[Orchestrator] Agents 1+2 done. Features: {bool(features)}, CV: {len(cv_results)} classifications")

    # Agent 3 uses the outputs from 1 and 2
    recap = await llm_summarization_agent(game_id, features=features, cv_results=cv_results)

    return {
        "game_id": game_id,
        "features": features,
        "cv_classifications": len(cv_results),
        "recap_length": len(recap),
        "recap": recap,
    }
