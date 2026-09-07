"""使用自定义 StateGraph 实现的销售数据分析智能体。"""

import os
from pathlib import Path

import matplotlib
import pandas as pd
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# 加载本地销售数据。使用绝对路径，避免从其他目录启动时找不到文件。
df = pd.read_csv(BASE_DIR / "sales.csv")


@tool
def query_sales_data(question: str) -> str:
    """查询销售数据，支持最高值、合计、分组统计和产品销量问题。

    Args:
        question: 用户的销售数据分析问题。
    """
    q = question.lower()

    if "最高" in q or "最大" in q:
        if "销售额" in q:
            max_row = df.loc[df["sales"].idxmax()]
            return (
                f"销售额最高的记录是{max_row['month']}月，"
                f"{max_row['region']}地区，{max_row['product']}产品，"
                f"销售额为{max_row['sales']}"
            )
        if "利润" in q:
            max_row = df.loc[df["profit"].idxmax()]
            return (
                f"利润最高的记录是{max_row['month']}月，"
                f"{max_row['region']}地区，利润为{max_row['profit']}"
            )

    if "总销售额" in q:
        return f"总销售额为{df['sales'].sum()}"
    if "总利润" in q:
        return f"总利润为{df['profit'].sum()}"

    if "各地区" in q and "销售额" in q:
        result = df.groupby("region")["sales"].sum().to_dict()
        return f"各地区销售额：{result}"
    if "各月份" in q and "利润" in q:
        result = df.groupby("month")["profit"].sum().to_dict()
        return f"各月份利润：{result}"

    if "产品" in q and "销量" in q:
        for product in df["product"].unique():
            if str(product).lower() in q:
                result = df[df["product"] == product]["quantity"].sum()
                return f"{product}产品总销量为{result}"

    return f"无法理解问题：{question}。请尝试其他表述方式。"


@tool
def plot_sales_data(chart_type: str = "line", metric: str = "sales") -> str:
    """生成销售数据图表。

    Args:
        chart_type: 图表类型，可选 line（折线图）或 bar（柱状图）。
        metric: 指标，可选 sales（销售额）或 profit（利润）。
    """
    if chart_type not in {"line", "bar"}:
        return f"不支持的图表类型：{chart_type}"
    if metric not in {"sales", "profit"}:
        return f"不支持的指标：{metric}"

    plt.figure(figsize=(10, 6))
    if chart_type == "line":
        monthly = df.groupby("month", sort=False)[metric].sum()
        monthly.plot(kind="line", marker="o")
        plt.title(f"Monthly {metric.capitalize()} Trend")
        plt.xlabel("Month")
    else:
        regional = df.groupby("region")[metric].sum()
        regional.plot(kind="bar")
        plt.title(f"{metric.capitalize()} by Region")
        plt.xlabel("Region")

    plt.ylabel(metric.capitalize())
    plt.tight_layout()
    image_path = BASE_DIR / f"sales_{metric}_{chart_type}.png"
    plt.savefig(image_path)
    plt.close()
    return f"图表已保存为{image_path}"


@tool
def analyze_sales_trend(question: str) -> str:
    """分析销售数据趋势并生成业务洞察。

    Args:
        question: 需要分析的趋势问题。
    """
    q = question.lower()
    if "利润下降" in q or "利润为什么" in q:
        monthly_profit = df.groupby("month", sort=False)["profit"].sum()
        changes = [
            f"{monthly_profit.index[index]}月相比{monthly_profit.index[index - 1]}月："
            f"{monthly_profit.iloc[index] - monthly_profit.iloc[index - 1]}"
            for index in range(1, len(monthly_profit))
        ]
        if changes:
            return "利润变化趋势：\n" + "\n".join(changes)
    return "请提供更具体的分析问题。"


TOOLS = [query_sales_data, plot_sales_data, analyze_sales_trend]
SYSTEM_MESSAGE = SystemMessage(
    content="""你是一个专业的数据分析助手。请优先调用工具获取真实数据，不要猜测。
1. 使用 query_sales_data 回答数据查询问题。
2. 使用 plot_sales_data 生成图表。
3. 使用 analyze_sales_trend 进行趋势分析。
回答要简洁、专业。"""
)

model = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "openai/gpt-4"),
    base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
    temperature=0,
)
model_with_tools = model.bind_tools(TOOLS)


def call_model(state: MessagesState) -> dict[str, list[AIMessage]]:
    """调用已绑定工具的模型，并把模型消息追加到状态。"""
    response = model_with_tools.invoke([SYSTEM_MESSAGE, *state["messages"]])
    return {"messages": [response]}


def route_after_model(state: MessagesState) -> str:
    """根据模型是否发起工具调用选择下一节点。"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "end"


def build_graph(checkpointer):
    """构建并编译自定义 StateGraph。"""
    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.set_entry_point("agent")
    builder.add_conditional_edges(
        "agent",
        route_after_model,
        {"tools": "tools", "end": END},
    )
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)


def chat(graph, thread_id: str = "data_analyzer_001") -> None:
    """启动命令行交互循环。"""
    print("=" * 50)
    print("智能数据分析助手（自定义 StateGraph 版）")
    print("输入 'exit' 退出")
    print("=" * 50)

    config = {"configurable": {"thread_id": thread_id}}
    while True:
        user_input = input("\n👤 你: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue

        result = graph.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
        )
        print(f"🤖 助手: {result['messages'][-1].content}")


def main() -> None:
    """使用内存检查点运行智能体。"""
    graph = build_graph(InMemorySaver())
    chat(graph)


if __name__ == "__main__":
    main()
