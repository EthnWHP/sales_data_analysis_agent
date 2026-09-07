"""Bounded plan-and-execute demo. Importing never runs the workflow."""

import argparse
import json
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph
from agent_runtime import SYSTEM_PROMPT, create_model
from react import build_agent


class PlanState(TypedDict):
    input: str
    plan: list[str]
    past_steps: list[tuple[str, str]]
    final_answer: str


def parse_plan(content):
    if not isinstance(content, str):
        raise ValueError("计划必须是 JSON 字符串数组。")
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    try:
        plan = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValueError("规划器没有返回有效 JSON 数组。") from exc
    if not isinstance(plan, list) or not 1 <= len(plan) <= 5:
        raise ValueError("计划必须包含 1–5 个步骤。")
    if any(not isinstance(step, str) or not step.strip() or len(step) > 500 for step in plan):
        raise ValueError("每步必须为 1–500 字符的非空字符串。")
    return [step.strip() for step in plan]


def build_plan_graph(model=None, agent=None):
    model = model if model is not None else create_model()
    agent = agent if agent is not None else build_agent(model=model)

    def planner(state):
        response = model.invoke([{"role": "system", "content": SYSTEM_PROMPT +
                                  "只规划，不执行。返回 1–5 个步骤的 JSON 字符串数组，不输出其他文字。"},
                                 {"role": "user", "content": state["input"]}])
        return {"plan": parse_plan(response.content), "past_steps": [], "final_answer": ""}

    def executor(state):
        step = state["plan"][0]
        result = agent.invoke({"messages": [{"role": "user", "content":
                              f"原始任务：{state['input']}\n已完成：{state['past_steps']}\n本步：{step}"}]},
                              config={"configurable": {"thread_id": uuid4().hex}, "recursion_limit": 30})
        past = [*state["past_steps"], (step, str(result["messages"][-1].content))]
        remaining = state["plan"][1:]
        return {"plan": remaining, "past_steps": past,
                "final_answer": "\n\n".join(f"{s}\n{r}" for s, r in past) if not remaining else ""}

    builder = StateGraph(PlanState)
    builder.add_node("planner", planner)
    builder.add_node("executor", executor)
    builder.set_entry_point("planner")
    builder.add_edge("planner", "executor")
    builder.add_conditional_edges("executor", lambda state: "executor" if state["plan"] else END)
    return builder.compile()


def main():
    parser = argparse.ArgumentParser(description="最多 5 步的计划执行演示；调用模型可能产生费用")
    parser.add_argument("--question", default="统计总销售额、最高利润月份，并画利润趋势图")
    args = parser.parse_args()
    try:
        result = build_plan_graph().invoke({"input": args.question}, config={"recursion_limit": 10})
        print(result["final_answer"])
        return 0
    except Exception as exc:
        print(f"计划执行失败（{type(exc).__name__}）。请检查配置、网络或规划格式；未输出请求详情。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
