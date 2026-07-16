"""Base agent class with common functionality for all 6 agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from sentinel_swarm.models.agents import AgentReport
from sentinel_swarm.models.case import CaseState

logger = structlog.get_logger("agents.base")


class BaseAgent(ABC):
    """Base class for all Sentinel Swarm agents."""

    agent_id: str = "base"
    description: str = ""

    def __init__(self, llm: BaseChatModel, tools: list[BaseTool] | None = None) -> None:
        self.llm = llm
        self.tools = tools or []
        if self.tools:
            self.llm_with_tools = llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = llm

    async def run(self, state: CaseState) -> CaseState:
        """Execute the agent's logic and return updated state."""
        start = time.monotonic()
        log = logger.bind(agent=self.agent_id, case_id=state.case_id)
        log.info("agent_started")

        try:
            updated_state = await self._execute(state)
            latency = int((time.monotonic() - start) * 1000)
            log.info("agent_completed", latency_ms=latency)
            return updated_state
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            log.error("agent_failed", error=str(e), latency_ms=latency, exc_info=True)
            state.error_log.append(f"{self.agent_id}: {str(e)}")
            return state

    @abstractmethod
    async def _execute(self, state: CaseState) -> CaseState:
        """Agent-specific execution logic. Subclasses must implement this."""
        ...

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        return f"You are {self.description}"

    async def _invoke_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Invoke the LLM with system and user prompts."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def _invoke_with_tools(self, system_prompt: str, user_prompt: str) -> Any:
        """Invoke the LLM with tools bound."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await self.llm_with_tools.ainvoke(messages)
        return response
