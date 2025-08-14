# Agent Trader — Portfolio Assistant (EN)

English overview for international readers. The original PT‑BR section follows below.

## Overview

- LLM via `LLMFactory` (default: LM Studio) with `streaming=True`.
- ReAct agent (`LangGraph`) + MCP tools consumed over HTTP.
- Postgres memory:
  - Short‑term: `AsyncPostgresSaver` (checkpoint by `thread_id`).
  - Long‑term: `AsyncPostgresStore` (user memory by namespace).
- FastAPI with a streaming endpoint.
- Streamlit UI consuming the stream.

## Architecture (high level)

1) UI/client → API (`FastAPI`) → Agent (`LangGraph`)
2) Agent → LLM + MCP tools (DDG/YFinance over HTTP)
3) Agent aggregates results + memory and streams the response back

Exposed MCP servers:
- `ddg-search`: web search + page fetching (`search`, `fetch_content`).
- `yfinance-tools`: tickers, quotes, history, indicators (`find_ticker_tool`, `get_stock_price_tool`, `get_stock_price_on_date_tool`, `get_current_datetime_tool`, `get_company_indicators_tool`).

User memory (e.g., portfolio):
- Internal tools: `save_user_memory`, `get_user_memory`, `delete_user_portfolio_empresa`.

## Requirements

- Python 3.10+
- Reachable Postgres and `POSTGRES_URL` set
- LM Studio (or Ollama/OpenAI) if you prefer another LLM backend
- Default ports:
  - API: 8000
  - MCP DDG: 8001 (path `/mcp/`)
  - MCP YFinance: 8002 (path `/mcp/`)
  - Streamlit: 8585

## Installation

```bash
python -m venv .venv
source .venv/bin/activate

# Minimal deps (repo also ships pyproject/uv.lock)
pip install -U pip
pip install fastapi uvicorn[standard] streamlit httpx beautifulsoup4 yfinance \
            langchain langgraph langchain-core langchain-mcp-adapters mcp \
            langchain-openai psycopg-binary pydantic
```

Set relevant environment variables (examples):

```bash
export POSTGRES_URL="postgresql://user:pass@localhost:5432/agent_trader"
export base_url_LMStudio="http://localhost:1234/v1"
# export base_url_Ollama="http://localhost:11434/v1"
# export OPENAI_API_KEY="sk-..."
```

## Quickstart (4 processes)

1) MCP DuckDuckGo (streamable HTTP):
```bash
python -m src.mcp_servers.duckduckgo_mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8001 --path /mcp
```

2) MCP YFinance (streamable HTTP):
```bash
python -m src.mcp_servers.yfinance_mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8002 --path /mcp
```

3) FastAPI:
```bash
uvicorn src.api.api:app --reload --host 0.0.0.0 --port 8000
```

4) Optional UI (Streamlit):
```bash
python -m streamlit run src/web/chat.py --server.port 8585 --server.address 0.0.0.0
```

Open in browser:
```bash
http://localhost:8000/docs
http://localhost:8585
```

Note: when running under Docker networking, the agent uses hosts `mcp-duckduckgo` and `mcp-yfinance` (see `src/agents/trader_agent.py`). Locally, keep MCPs at `localhost` or adjust URLs.

## Agent and MCP (key code)

Multiple MCP servers integration:

```160:171:src/agents/trader_agent.py
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
```

Postgres memory (checkpoint + store):

```35:49:src/agents/memory_agent.py
async def get_store()->tuple[AsyncPostgresSaver, AsyncPostgresStore]:

    pool = psycopg_pool.AsyncConnectionPool(
        DATABASE_URL,
        kwargs={"autocommit": True},
        open=False,
    )
    await pool.open()
    memory_checkpoint = AsyncPostgresSaver(pool)  # type: ignore
    await memory_checkpoint.setup()

    # Criar store sem context manager para manter ativo
    async with AsyncPostgresStore.from_conn_string(DATABASE_URL) as store:
        await store.setup()  # Run migrations. Done once
        namespaces = await store.alist_namespaces()
        print(namespaces)
```

Streaming in the API (tokens emitted as the graph progresses):

```75:85:src/api/api.py
    async def token_streamer():
        try:
            async for step, metadata in agent.astream(langchain_input,config=session_cfg, stream_mode="messages"):
                try:
                    if metadata["langgraph_node"] == "agent" and (text := step.text()):
                        yield text
                    elif metadata["langgraph_node"] == "tools" and (text := step.text()):
                        print(text, end="")
```

## Endpoints (API)

- GET `/health` → status
- POST `/query/streaming` → query with streamed response

Example:

```bash
curl -s -X POST http://localhost:8000/query/streaming \
  -H "Content-Type: application/json" \
  -d '{"question":"List my portfolio","user_id":"u@e.com","thread_id":"t-1"}'
```

## Prompt engineering (summary)

The prompt defines persona, objectives, tool usage rules, and output format, including:
- call `get_user_memory` at the start;
- normalize tickers with `find_ticker_tool`;
- update quotes/indicators and complement with sentiment via `search`/`fetch_content`;
- persist changes with memory tools;
- produce a Markdown table with totals and concise comments.

## Environment variables

- `POSTGRES_URL` (required): Postgres connection (e.g., `postgresql://user:pass@host:5432/db`).
- `base_url_LMStudio` (optional): LM Studio local endpoint.
- `base_url_Ollama` (optional) / `OPENAI_API_KEY` (optional): other backends.
- `API_URL` (optional, UI): base for `src/web/chat.py` (default `http://localhost:8000`).

## Quick tests

```bash
python src/test_mcp.py
```

## Tips & troubleshooting

- Uvicorn: ensure `app` in `src/api/api.py` and run `uvicorn src.api.api:app --reload`.
- Ensure `POSTGRES_URL` is valid; first run applies LangGraph migrations.
- Busy ports? Adjust or kill processes (`lsof -i :8000 :8001 :8002 :8585`).

## Roadmap

- Enrich user memory and UI/UX
- New MCP integrations (e.g., calendars, sector data)
- Metrics, tracing, automated tests

—
Contributions welcome via issues/PRs.

# Agent Trader — Portfolio Assistant (PT-BR)
# Agent Trader — Portfolio Assistant (PT-BR)

Agente em PT‑BR para gerenciar portfólio de investimentos, orquestrado com LangGraph (ReAct), integrações via MCP (DuckDuckGo e Yahoo Finance), memória persistente em Postgres (curto e longo prazo) e streaming ponta‑a‑ponta até a UI.

## Visão geral

- LLM via `LLMFactory` (padrão: LM Studio) com `streaming=True`.
- Agente ReAct (`LangGraph`) + ferramentas MCP consumidas via HTTP.
- Memória em Postgres:
  - Curto prazo: `AsyncPostgresSaver` (checkpoint por `thread_id`).
  - Longo prazo: `AsyncPostgresStore` (memória de usuário por namespace).
- API FastAPI com endpoint de streaming.
- UI em Streamlit consumindo o stream.

## Arquitetura (alto nível)

1) UI/cliente → API (`FastAPI`) → Agente (`LangGraph`)
2) Agente → LLM + Ferramentas MCP (DDG/YFinance via HTTP)
3) Agente agrega resultados + memória e streama a resposta ao cliente

MCP Servers expostos:
- `ddg-search`: busca web + leitura de páginas (`search`, `fetch_content`).
- `yfinance-tools`: tickers, cotações, históricos e indicadores (`find_ticker_tool`, `get_stock_price_tool`, `get_stock_price_on_date_tool`, `get_current_datetime_tool`, `get_company_indicators_tool`).

Memória do usuário (ex.: portfólio):
- Ferramentas internas do agente: `save_user_memory`, `get_user_memory`, `delete_user_portfolio_empresa`.

## Requisitos

- Python 3.10+
- Postgres acessível e variável `POSTGRES_URL` definida
- LM Studio (ou Ollama/OpenAI) se desejar outro backend para o LLM
- Portas padrão:
  - API: 8000
  - MCP DDG: 8001 (path `/mcp/`)
  - MCP YFinance: 8002 (path `/mcp/`)
  - Streamlit: 8585

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate

# Dependências mínimas (o projeto também contém pyproject/uv.lock)
pip install -U pip
pip install fastapi uvicorn[standard] streamlit httpx beautifulsoup4 yfinance \
            langchain langgraph langchain-core langchain-mcp-adapters mcp \
            langchain-openai psycopg-binary pydantic
```

Defina variáveis de ambiente relevantes (exemplos):

```bash
export POSTGRES_URL="postgresql://user:pass@localhost:5432/agent_trader"
export base_url_LMStudio="http://localhost:1234/v1"
# export base_url_Ollama="http://localhost:11434/v1"
# export OPENAI_API_KEY="sk-..."
```

## Execução rápida (4 processos)

1) MCP DuckDuckGo (HTTP streamable):
```bash
python -m src.mcp_servers.duckduckgo_mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8001 --path /mcp
```

2) MCP YFinance (HTTP streamable):
```bash
python -m src.mcp_servers.yfinance_mcp_server.server --transport streamable-http --host 0.0.0.0 --port 8002 --path /mcp
```

3) API FastAPI:
```bash
uvicorn src.api.api:app --reload --host 0.0.0.0 --port 8000
```

4) UI (opcional) em Streamlit:
```bash
python -m streamlit run src/web/chat.py --server.port 8585 --server.address 0.0.0.0
```

Abrir no navegador:
```bash
http://localhost:8000/docs
http://localhost:8585
```

Observação: se rodar em rede Docker, o agente usa hosts `mcp-duckduckgo` e `mcp-yfinance` (vide `src/agents/trader_agent.py`). Localmente, mantenha os MCP em `localhost` ou ajuste URLs.

## Agente e MCP (código‑chave)

Integração com múltiplos MCP Servers:

```160:171:src/agents/trader_agent.py
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
```

Memória Postgres (checkpoint + store):

```35:49:src/agents/memory_agent.py
async def get_store()->tuple[AsyncPostgresSaver, AsyncPostgresStore]:

    pool = psycopg_pool.AsyncConnectionPool(
        DATABASE_URL,
        kwargs={"autocommit": True},
        open=False,
    )
    await pool.open()
    memory_checkpoint = AsyncPostgresSaver(pool)  # type: ignore
    await memory_checkpoint.setup()

    # Criar store sem context manager para manter ativo
    async with AsyncPostgresStore.from_conn_string(DATABASE_URL) as store:
        await store.setup()  # Run migrations. Done once
        namespaces = await store.alist_namespaces()
        print(namespaces)
```

Streaming na API (tokens conforme progresso do grafo):

```75:85:src/api/api.py
    async def token_streamer():
        try:
            async for step, metadata in agent.astream(langchain_input,config=session_cfg, stream_mode="messages"):
                try:
                    if metadata["langgraph_node"] == "agent" and (text := step.text()):
                        yield text
                    elif metadata["langgraph_node"] == "tools" and (text := step.text()):
                        print(text, end="")
```

## Endpoints (API)

- GET `/health` → status
- POST `/query/streaming` → consulta com resposta streamada

Exemplo:

```bash
curl -s -X POST http://localhost:8000/query/streaming \
  -H "Content-Type: application/json" \
  -d '{"question":"Liste meu portfólio","user_id":"u@e.com","thread_id":"t-1"}'
```

## Prompt engineering (resumo)

O prompt define persona, objetivos, regras de uso das ferramentas e formato de saída, incluindo:
- recuperar `get_user_memory` no início;
- normalizar tickers com `find_ticker_tool`;
- atualizar cotações/indicadores e complementar com sentimento via `search`/`fetch_content`;
- persistir alterações com ferramentas de memória;
- produzir tabela Markdown com totais e comentários objetivos.

## Variáveis de ambiente

- `POSTGRES_URL` (obrigatório): conexão Postgres (ex.: `postgresql://user:pass@host:5432/db`).
- `base_url_LMStudio` (opcional): endpoint local do LM Studio.
- `base_url_Ollama` (opcional) / `OPENAI_API_KEY` (opcional): outros backends.
- `API_URL` (opcional, UI): base para `src/web/chat.py` (padrão `http://localhost:8000`).

## Testes rápidos

```bash
python src/test_mcp.py
```

## Dicas e solução de problemas

- Uvicorn: garanta `app` em `src/api/api.py` e rode com `uvicorn src.api.api:app --reload`.
- Certifique‑se de que `POSTGRES_URL` é válido; a primeira execução aplica migrações do LangGraph.
- Portas ocupadas? Ajuste ou finalize processos (`lsof -i :8000 :8001 :8002 :8585`).

## Roadmap

- Enriquecer memória do usuário e UX na UI
- Novas integrações MCP (ex.: calendários, fontes setoriais)
- Métricas, tracing e testes automatizados

—
Contribuições são bem‑vindas via issues/PRs.