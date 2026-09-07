"""LangChain create_agent implementation using the shared sales tools."""

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from agent_runtime import SYSTEM_PROMPT, create_model, run_cli
from sales_tools import build_tools


def build_agent(model=None, tools=None, checkpointer=None):
    return create_agent(model=model if model is not None else create_model(),
                        tools=tools if tools is not None else build_tools(),
                        system_prompt=SYSTEM_PROMPT,
                        checkpointer=checkpointer if checkpointer is not None else InMemorySaver())


if __name__ == "__main__":
    raise SystemExit(run_cli(build_agent))
