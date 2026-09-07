"""Optional Redis checkpoint CLI; no Redis connection at import time."""

import argparse
import os
from dotenv import load_dotenv
from agent_runtime import chat
from sales_tools import BASE_DIR
from state_graph_agent import build_graph


def main():
    parser = argparse.ArgumentParser(description="Redis 持久化销售分析助手")
    parser.add_argument("--question")
    parser.add_argument("--thread-id", help="复用相同标识恢复历史；不要跨用户共享")
    args = parser.parse_args()
    load_dotenv(BASE_DIR / ".env", override=False)
    try:
        from langgraph.checkpoint.redis import RedisSaver
        with RedisSaver.from_conn_string(os.getenv("REDIS_URL", "redis://localhost:6379")) as store:
            store.setup()
            chat(build_graph(checkpointer=store),
                 args.thread_id or os.getenv("LANGGRAPH_THREAD_ID", "data_analyzer_redis_001"), args.question)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"执行失败（{type(exc).__name__}）。请检查模型配置、Redis 扩展和连接；未输出连接地址或密钥。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
