"""Explicit Agent → Tools → Agent loop with thread-scoped checkpoints."""

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from agent_runtime import SYSTEM_PROMPT, create_model, run_cli
from sales_tools import build_tools


def route_after_model(state):
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else "end"


def build_graph(checkpointer=None, model=None, tools=None):
    tools = tools if tools is not None else build_tools()
    bound_model = (model if model is not None else create_model()).bind_tools(tools)

    def call_model(state):
        response = bound_model.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", route_after_model, {"tools": "tools", "end": END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer if checkpointer is not None else InMemorySaver())


if __name__ == "__main__":
    raise SystemExit(run_cli(build_graph))
