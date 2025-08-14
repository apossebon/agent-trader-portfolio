# Building an Investment Agent with LangChain + LangGraph, MCP Servers, Postgres Memory, and Multi‑Container Cloud Deploy

I recently evolved the Agent Trader: a Portuguese-first portfolio assistant that combines LangChain and LangGraph (ReAct‑style orchestration) with MCP integrations (DuckDuckGo and Yahoo Finance), medium/long‑term memory in Postgres, and end‑to‑end streaming. This post shows how the pieces fit together, with real code snippets and an architecture diagram, plus how to package everything into multiple cloud‑ready containers.

## Why LangChain and LangGraph together?

- LangChain: LLM, messages, tools, and client abstractions (including `langchain-openai`) and a rich ecosystem of integrations (e.g., MCP adapters).
- LangGraph: reactive orchestration (ReAct‑style), state and memory via checkpointers/stores, enabling persistent conversations by `thread_id` and robust control flow.

In this project, the agent is built with `create_react_agent`, receives MCP tools dynamically, and connects two types of Postgres memory (checkpoint and store).

## Integrating with MCP Servers (Model Context Protocol)

The agent consumes tools from multiple MCP servers over HTTP (streamable). Client configuration:

```python
# src/agents/trader_agent.py (excerpt)
client = MultiServerMCPClient(
    {
        "ddg-search": {
            "transport": "streamable_http",
            "url": "http://mcp-duckduckgo:8001/mcp/"
        },
        "yfinance-tools": {
            "transport": "streamable_http",
            "url": "http://mcp-yfinance:8002/mcp/"
        },
    }
)
mcp_tools = await client.get_tools()
```

On the server side, each MCP exposes a set of tools. DuckDuckGo for search and page fetching:

```python
# src/mcp_servers/duckduckgo_mcp_server/server.py (excerpt)
mcp = FastMCP("ddg-search", host="0.0.0.0", port=8001)

@mcp.tool()
async def search(query: str, ctx: Context, max_results: int = 10) -> str:
    ...

@mcp.tool()
async def fetch_content(url: str, ctx: Context) -> str:
    ...
```

And YFinance for financial data:

```python
# src/mcp_servers/yfinance_mcp_server/server.py (excerpt)
tools_trader = [
    to_fastmcp(find_ticker_tool),
    to_fastmcp(get_stock_price_tool),
    to_fastmcp(get_stock_price_on_date_tool),
    to_fastmcp(get_current_datetime_tool),
    to_fastmcp(get_company_indicators_tool),
]

mcp = FastMCP("yfinance-tools", host="0.0.0.0", port=8002, tools=tools_trader)
```

This separation allows scaling, versioning, and auditing each capability independently.

## Postgres Memory: medium and long term

- Checkpoint (medium‑term): keeps graph state and reasoning by `thread_id` via `AsyncPostgresSaver`.
- Store (long‑term): holds user “semantic” memory (e.g., portfolio) via `AsyncPostgresStore`, with namespaced keys.

```python
# src/agents/memory_agent.py (excerpt)
pool = psycopg_pool.AsyncConnectionPool(POSTGRES_URL, kwargs={"autocommit": True}, open=False)
await pool.open()
memory_checkpoint = AsyncPostgresSaver(pool)
await memory_checkpoint.setup()

async with AsyncPostgresStore.from_conn_string(POSTGRES_URL) as store:
    await store.setup()
```

Both components are wired into the agent:

```python
# src/agents/trader_agent.py (excerpt)
trader_agent = create_react_agent(
    model=user_model,
    tools=mcp_tools,
    prompt=system_prompt,
    checkpointer=memory_checkpoint,
    store=memory_store,
)
```

And the agent exposes tools to persist user portfolio:

```python
# src/agents/trader_agent.py (excerpt)
@tool
async def save_user_memory(user_memory: UserMemory, config: RunnableConfig) -> str:
    user_id = config.get("configurable", {}).get("user_id", "default_user")
    namespace = ("users", user_id)
    async with AsyncPostgresStore.from_conn_string(POSTGRES_URL) as store:
        await store.aput(namespace, "user_memory", dict(user_memory))
    return "User memory saved"
```

## End‑to‑end streaming

The LLM is instantiated with streaming enabled, and the API exposes an endpoint that streams tokens as the graph progresses (great UX and transparency):

```python
# src/llm/llm_factory.py (excerpt)
llm = ChatOpenAI(base_url=os.getenv("base_url_LMStudio"), model=model,
                 api_key=SecretStr("lm-studio"), streaming=True, max_retries=5)
```

```python
# src/api/api.py (excerpt)
async def token_streamer():
    async for step, metadata in agent.astream(langchain_input, config=session_cfg, stream_mode="messages"):
        if metadata.get("langgraph_node") == "agent" and (text := step.text()):
            yield text

return StreamingResponse(
    token_streamer(),
    media_type="text/plain",
    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
)
```

## Multi‑container deploy (cloud‑ready)

The repo includes a multi‑container composition (a good base for Swarm, ECS, ACI, etc.):

```yaml
# .devcontainer/docker-compose.yaml (simplified excerpt)
services:
  pgvector:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: agent_db
      POSTGRES_USER: user_agent
      POSTGRES_PASSWORD: pass_agent
    ports: ["5432:5432"]

  app:
    build:
      context: ../
      dockerfile: .devcontainer/Dockerfile
      target: base
    ports: ["8000:8000", "8585:8585"]
    depends_on: { pgvector: { condition: service_healthy } }

  mcp-duckduckgo:
    build: { context: ../, dockerfile: .devcontainer/Dockerfile, target: mcp_servers }
    ports: ["8001:8001"]
    command: python -m src.mcp_servers.duckduckgo_mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8001

  mcp-yfinance:
    build: { context: ../, dockerfile: .devcontainer/Dockerfile, target: mcp_servers }
    ports: ["8002:8002"]
    command: python -m src.mcp_servers.yfinance_mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8002
```

Production notes:
- Healthchecks and observability (logs/metrics/traces) per service.
- Secrets via secure ENV (Vault/Secrets Manager) and least‑privilege DB roles.
- Scale MCP servers independently.

## Block diagram (Agent, MCPs, Postgres)

```mermaid
graph LR
  U[User / UI (Streamlit)] -->|HTTP POST (/query/streaming)| API[FastAPI]
  API -->|astream (tokens)| AG[Agent (LangChain + LangGraph)]
  AG -->|MCP Tools| MCP1[ddg-search]
  AG -->|MCP Tools| MCP2[yfinance-tools]
  MCP1 -->|HTTP| WEB[Web/News]
  MCP2 -->|Financial APIs| YF[Yahoo Finance]
  AG -->|Checkpoint (medium term)| PG1[(Postgres - Checkpointer)]
  AG -->|Store (long term)| PG2[(Postgres - Store)]
```

## Best practices and lessons learned

- Decouple capabilities into MCP servers for reuse and evolution.
- Treat memory as first‑class: checkpoint (medium term) and store (long term) solve different needs.
- Stream whenever possible: improves perceived performance.
- Standardize prompts: persona, objectives, tool rules, and output format.

## Getting started

1) Bring up services (MCPs, API, Postgres) via compose or an orchestrator.
2) Set `POSTGRES_URL` and your LLM backend URL (e.g., LM Studio).
3) Call `POST /query/streaming` with `question`, `user_id`, and `thread_id`.

If you want to chat about extensions (new MCPs, embeddings/vectors, tracing) or cloud deployment (ECS/K8s), ping me!


