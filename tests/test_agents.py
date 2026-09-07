import importlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent_runtime import create_model
from pae import build_plan_graph, parse_plan
from react import build_agent
from sales_tools import build_tools
from state_graph_agent import build_graph


class ToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tools = build_tools(output_dir=self.temp.name)

    def test_tools_use_shared_calculations(self):
        result = self.tools[0].invoke({"metric": "profit", "group_by": "month", "rank": "highest"})
        self.assertEqual(result["results"], [{"month": "Mar", "value": 1080}])
        self.assertEqual(len(self.tools[2].invoke({"metric": "profit"})["changes"]), 2)

    def test_custom_and_react_tool_roundtrip(self):
        for factory in [build_graph, build_agent]:
            with self.subTest(factory=factory.__name__):
                model = ToolModel(responses=[
                    AIMessage(content="", tool_calls=[{"name": "query_sales_data", "args": {"metric": "sales"},
                                                       "id": "query-1", "type": "tool_call"}]),
                    AIMessage(content="12900")])
                graph = factory(model=model, tools=self.tools)
                config = {"configurable": {"thread_id": "test"}, "recursion_limit": 10}
                result = graph.invoke({"messages": [{"role": "user", "content": "总销售额？"}]}, config)
                self.assertEqual(result["messages"][-1].content, "12900")
                tool_message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
                self.assertEqual(json.loads(tool_message.content)["results"][0]["value"], 12900)
                self.assertTrue(graph.get_state(config).values)
                self.assertFalse(graph.get_state({"configurable": {"thread_id": "other"}}).values)

    def test_recursion_limit_stops_tool_loop(self):
        model = ToolModel(responses=[AIMessage(content="", tool_calls=[
            {"name": "query_sales_data", "args": {}, "id": "loop", "type": "tool_call"}])])
        graph = build_graph(model=model, tools=self.tools)
        with self.assertRaises(GraphRecursionError):
            graph.invoke({"messages": [{"role": "user", "content": "test"}]},
                         {"configurable": {"thread_id": "loop"}, "recursion_limit": 3})

    def test_plan_validation(self):
        self.assertEqual(parse_plan('```json\n["查询", "绘图"]\n```'), ["查询", "绘图"])
        for value in ["bad", "[]", "{}", "[1]", '[""]', json.dumps(["x"] * 6)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_plan(value)

    def test_plan_executes_each_step_once(self):
        model = ToolModel(responses=[AIMessage(content='["查询总额", "总结"]')])

        class Executor:
            count = 0

            def invoke(self, state, config):
                self.count += 1
                return {"messages": [AIMessage(content=f"结果{self.count}")]}

        executor = Executor()
        result = build_plan_graph(model, executor).invoke({"input": "分析"}, {"recursion_limit": 10})
        self.assertEqual(executor.count, 2)
        self.assertEqual(result["plan"], [])
        self.assertIn("结果1", result["final_answer"])
        self.assertIn("结果2", result["final_answer"])

    def test_missing_key_has_clear_error(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch("agent_runtime.load_dotenv"):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                create_model()

    def test_imports_do_not_initialize_model_or_connect(self):
        with patch("langchain_openai.ChatOpenAI", side_effect=AssertionError("model created")), \
             patch("socket.socket.connect", side_effect=AssertionError("network attempted")):
            for name in ["state_graph_agent", "react", "pae", "redis_state_graph_agent", "demo", "create_data"]:
                importlib.reload(importlib.import_module(name))


if __name__ == "__main__":
    unittest.main()
