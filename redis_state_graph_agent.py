"""使用 Redis 持久化检查点的自定义 StateGraph 销售分析智能体。"""

import os

from dotenv import load_dotenv
from langgraph.checkpoint.redis import RedisSaver

from state_graph_agent import BASE_DIR, build_graph, chat


load_dotenv(BASE_DIR / ".env")

# 本地 Docker 默认地址；如有密码或使用其他端口，请在 .env 中覆盖。
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
THREAD_ID = os.getenv("LANGGRAPH_THREAD_ID", "data_analyzer_redis_001")


def main() -> None:
    """连接 Redis、初始化索引并运行交互式智能体。"""
    try:
        with RedisSaver.from_conn_string(REDIS_URL) as checkpointer:
            # 首次运行时创建 RedisJSON/RediSearch 索引；重复调用是安全的。
            checkpointer.setup()
            graph = build_graph(checkpointer)
            print("已连接 Redis 检查点存储。")
            chat(graph, thread_id=THREAD_ID)
    except Exception as exc:
        raise RuntimeError(
            "无法初始化 Redis 检查点。请确认 Docker 中的 Redis 8+ "
            "或 Redis Stack 已启动，且 REDIS_URL 配置正确。"
        ) from exc


if __name__ == "__main__":
    main()
