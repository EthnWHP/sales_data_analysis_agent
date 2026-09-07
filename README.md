# 销售数据分析 Agent

一个用于学习 LangChain / LangGraph 工具调用和会话状态的命令行 Demo。用户用中文提出问题，模型调用 Pandas 查询或 Matplotlib 绘图工具，再组织回复。仓库附带 9 条固定合成销售记录，可用于演示，不涉及真实客户数据。

本仓库是既有学习代码的整理版本。课程、上游代码来源和再分发许可仍需确认，详见 [来源说明](docs/PROVENANCE.md)。

## 功能与入口

| 入口 | 作用 | 状态保存 |
|---|---|---|
| `state_graph_agent.py` | 显式构建 Agent / ToolNode 循环，推荐先用此入口 | 进程内记忆 |
| `react.py` | `create_agent` 工具调用与命令行多轮对话 | 进程内记忆 |
| `pae.py` | 先生成步骤，再逐步执行预设销售分析问题 | 单次规划任务 |
| `redis_state_graph_agent.py` | 复用自定义图，将检查点写入 Redis | Redis 持久化 |

已实现的查询包括总销售额、总利润、各地区销售额、各月份利润、销售额或利润最高的**单条记录**；自定义图版本也支持产品总销量查询。可生成按月份的销售额 / 利润折线图及按地区的柱状图。

查询工具内部以关键词分支处理问题；没有通用 Text-to-SQL、任意 Python 执行或预测模型。“利润趋势分析”计算相邻月份的利润差额，不提供经过验证的业务因果归因。

## 本地启动

在项目根目录中操作，原项目环境使用 Python 3.11。依赖文件是原开发环境的完整版本快照，本次未从零安装验证，具体 Python / 平台兼容性仍需实测。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

若本地没有 `.env`，执行下列命令建立配置；已经存在时保留它，按 `.env.example` 补齐缺项即可。

```bash
cp -n .env.example .env
```

用编辑器填写 `.env`，再启动：

```bash
python state_graph_agent.py
```

默认模型服务地址为 OpenRouter。`OPENAI_API_KEY` 是客户端读取的变量名，应填写与 `LLM_BASE_URL` 对应的服务商密钥，不是要求使用某一家服务的密钥。模型须支持工具调用，且在自己的账户下可用。

| 变量 | 用途 |
|---|---|
| `OPENAI_API_KEY` | 模型服务密钥，必填 |
| `LLM_BASE_URL` | OpenAI 兼容接口地址，默认见示例配置 |
| `LLM_MODEL` | 模型标识，默认 `openai/gpt-4`；可改为账户可用模型 |
| `REDIS_URL` | 仅 Redis 入口使用的连接地址 |
| `LANGGRAPH_THREAD_ID` | 仅 Redis 入口使用；同一 ID 恢复同一会话 |

其他入口：

```bash
python react.py
python pae.py
```

以上是两个独立运行方式。`react.py` 输入 `exit` 退出；`pae.py` 自动执行源码中的预设任务。使用 Redis 版本前，需自行准备支持 RedisJSON / RediSearch 的 Redis 服务，并配置 `REDIS_URL`：

```bash
python redis_state_graph_agent.py
```

## 交互示例

启动交互入口后，可以逐条输入：

```text
总销售额是多少？
各地区的销售额是多少？
各月份的利润是多少？
生成按月份的利润折线图。
exit
```

随附数据的人工可核验基准：总销售额为 **12,900**，总利润为 **2,580**；按 Jan / Feb / Mar 排列的月利润为 **740 / 760 / 1,080**。这组数值来自样例数据统计，不代表本次已经验证模型回答。数据没有定义币种，因此这里不添加货币单位。

图表保存在项目目录，文件名如 `sales_profit_line.png`。现有两张历史图的月份按字符串排列为 Feb / Jan / Mar，默认被 `.gitignore` 排除，未作为公开趋势图使用。后续应在核对时间顺序并完成实际运行后，补充新的图表或终端截图。

## 文件说明

| 路径 | 内容 |
|---|---|
| `sales.csv` | 9 条合成样例记录：月份、地区、产品、销售额、利润、数量 |
| `create_data.py` | 写出同样的固定样例数据；运行会覆盖当前目录的 `sales.csv` |
| `state_graph_agent.py` / `react.py` / `pae.py` | 三种 Agent 工作流实现 |
| `redis_state_graph_agent.py` | Redis 检查点入口 |
| `requirements.txt` | 标准安装入口，引用原 `requirments.txt` |
| `.env.example` / `.gitignore` | 配置模板及本地文件排除规则 |
| `docs/` | 数据公开边界、来源与许可待办 |

## 已知限制与验证

- 最高值查询取一条记录，不是按月汇总后取最大值；旧提示词提到的最低值、平均值和按月份条件筛选并没有完整实现。
- `react.py` 和 `pae.py` 会将问题转成小写，但匹配产品名时未统一大小写，可能无法识别 `A` / `B`；自定义图版本已做一致处理。
- `react.py` / `pae.py` 使用 Pandas 默认分组排序，英文月份可能按字母排列。自定义图保留数据首次出现顺序，但仍非通用日期解析，换数据后需检查时序。
- 本项目只有命令行界面；没有 Web 上传、权限控制、指标口径管理或生产级错误恢复。模型回复可能出错，请对照工具结果核查。
- 内存检查点随进程退出丢失；Redis 中的会话需要自己管理与清理。涉及私有销售数据时，输入问题和工具结果可能发送至模型服务，详见 [数据说明](docs/DATA_POLICY.md)。

本次整理已完成 6 个 Python 文件的静态语法检查、样例 CSV 与生成脚本逐字段一致性检查，以及样例总额复核。未安装完整依赖、未调用模型 API、未验证 Redis 连接或完整对话；不把静态检查当作端到端运行通过。

## 发布前待办

1. 确认课程或上游仓库来源及许可，补充自己的具体改动说明。
2. 使用自己的模型配置完成一次真实演示，保留无凭据的终端截图。
3. 提交前检查暂存文件；只发布已经确认可公开的数据。`.gitignore` 不会移除已跟踪文件或历史中的密钥。
