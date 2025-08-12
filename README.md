# Agent Trader — Portfolio Assistant (PT-BR)

Agente que ajuda a gerenciar portfólio de investimentos em português, integrando LLM local (LM Studio) com duas integrações via MCP (Model Context Protocol): pesquisa na web (DuckDuckGo) e dados financeiros (Yahoo Finance).

## Como o agente funciona

O agente é orquestrado com LangGraph (estilo ReAct) e usa ferramentas MCP para obter dados confiáveis. O fluxo é:

1) Entrada do usuário
   - Você faz uma pergunta em PT-BR (ex.: “Analise meu portfólio com PETR4 e VALE3”).
   - O agente captura a data/hora atual (contexto temporal) para análises consistentes.

2) Planejamento e raciocínio (ReAct)
   - O agente decide quais ferramentas MCP precisa chamar e em qual ordem.
   - Ele só usa ferramentas disponíveis, evitando “adivinhações”.

3) Ferramentas MCP usadas pelo agente
   - Memória do usuário:
     - get_user_memory / save_user_memory / update_user_memory
     - Lê e persiste preferências e o portfólio do usuário.
   - Descoberta de tickers:
     - find_ticker_tool para mapear nomes de empresas para tickers corretos.
   - Preços e históricos:
     - get_stock_price_tool (cotação atual)
     - get_stock_price_on_date_tool (cotação em uma data específica)
   - Indicadores fundamentalistas:
     - get_company_indicators_tool para métricas da empresa.
   - Sentimento e notícias (MCP DuckDuckGo):
     - search para encontrar notícias e referências recentes.
     - fetch_content para ler e resumir o conteúdo das páginas encontradas.

4) Cálculos do portfólio
   - Monta uma tabela Markdown com as colunas:
     - Empresa | Ticker | Quantidade | Valor Total Investido (R$) | Cotação Atual (R$) | Valor Atual (R$) | Variação (R$) | Variação (%)
   - Regras de cálculo:
     - Valor Total Investido = soma de (preço de compra × quantidade).
     - Valor Atual = soma de (cotação atual × quantidade).
     - Variação (R$) = Valor Atual − Valor Total Investido.
     - Variação (%) = (Variação (R$) / Valor Total Investido) × 100.
   - Formatação monetária em R$ com 2 casas decimais.
   - Totaliza Quantidade, Valor Total Investido e Valor Atual ao final da tabela.

5) Persistência de alterações
   - Se o portfólio for alterado (ex.: compra/venda simulada), o agente chama update_user_memory para salvar o novo estado.

6) Saída
   - Retorna a tabela Markdown e comentários objetivos:
     - Interpreta os números, compara variações e destaca riscos/oportunidades.
     - Informa brevemente quais ferramentas/fonte de dados foram usadas (preços, indicadores, notícias).

Observações importantes:
- O agente considera sempre a data/hora atual.
- Não inventa dados: só responde com base no que obteve via ferramentas MCP e memória do usuário.
- Em análises qualitativas, combina indicadores com sentimento extraído de notícias recentes.


## Arquitetura

Componentes principais:

- LLM local: configurado via `LLMFactory` (padrão LM Studio).
- Agente: `src/agents/trader_agent.py` (LangGraph `create_react_agent`) + ferramentas MCP.
- MCP Servers (HTTP streamable):
  - DuckDuckGo Search: busca web e coleta de conteúdo.
  - YFinance Tools: cotações e indicadores.
- API FastAPI: `src/api/api.py` (endpoints para o frontend/serviços).
- UI (opcional): `src/web/chat.py` com Streamlit.

Fluxo típico:
1) UI/cliente → API (FastAPI) → Agente
2) Agente → LLM + Ferramentas MCP (DDG/YFinance via HTTP)
3) Resposta agregada ao cliente

## Requisitos

- Linux (Dev Container: Debian 12)
- Python 3.10+ (projeto usa venv)
- LM Studio (ou outro backend suportado por `LLMFactory`)
- Portas padrão:
  - API: 8000
  - MCP DDG: 8001 (path /mcp/)
  - MCP YFinance: 8002 (path /mcp/)
  - Streamlit: 8585

## Instalação

```bash
# Dentro do dev container
python -m venv .venv
source .venv/bin/activate

# Dependências (ajuste se houver requirements.txt)
pip install -U pip
pip install fastapi uvicorn[standard] streamlit httpx beautifulsoup4 yfinance \
            langchain langgraph langchain-core langchain-mcp-adapters mcp
```

## Execução rápida (terminais separados)

1) Iniciar MCP DuckDuckGo (HTTP):
```bash
python -m src.mcp_servers.duckduckgo_mcp_server.server --transport http --host 0.0.0.0 --port 8001 --path /mcp
```

2) Iniciar MCP YFinance (HTTP):
```bash
python -m src.mcp_servers.yfinance_mcp_server.server --transport http --host 0.0.0.0 --port 8002 --path /mcp
```

3) Iniciar API FastAPI:
```bash
uvicorn src.api.api:app --reload --host 0.0.0.0 --port 8000
```

4) Iniciar UI Streamlit (opcional):
```bash
python -m streamlit run src/web/chat.py --server.port 8585 --server.address 0.0.0.0
```

Abra no host:
```bash
"$BROWSER" http://localhost:8000/docs
"$BROWSER" http://localhost:8585
```

Observação:
- Se seu repositório usa caminhos alternativos (ex.: `src/duckduckgo_mcp_server/server.py`), ajuste os comandos de módulo/caminho.
- Caso o transporte HTTP do MCP não aceite host/port/path via `FastMCP.run`, use um wrapper ASGI/uvicorn conforme implementado no servidor HTTP.

## Uso do agente

O agente é criado em `get_trader_agent()`:
```python
# src/agents/trader_agent.py
client = MultiServerMCPClient(
  {
    "ddg-search": {
      "transport": "streamable_http",
      "url": "http://localhost:8001/mcp/"
    },
    "yfinance-tools": {
      "transport": "streamable_http",
      "url": "http://localhost:8002/mcp/"
    },
  }
)
mcp_tools = await client.get_tools()

trader_agent = create_react_agent(
  model=user_model,      # LLM vindo do LM Studio por padrão
  tools=mcp_tools,       # Ferramentas expostas pelos MCP servers
  prompt=system_prompt,  # Prompt descrito acima
)
```

Isso permite ao agente:
- Pesquisar/ler notícias (DuckDuckGo: `search`, `fetch_content`).
- Obter cotações, indicadores, datas e memória do usuário (YFinance + memória).

## Endpoints principais (API)

- GET `/health` → status
- POST `/query/streaming` → consulta ao agente
  - Body (exemplo):
    ```json
    {
      "question": "Quero analisar meu portfólio com PETR4 e VALE3",
      "user_id": "usuario@example.com",
      "thread_id": "session-123"
    }
    ```

Testes rápidos:
```bash
curl -s http://localhost:8000/health | jq

curl -s -X POST http://localhost:8000/query/streaming \
  -H "Content-Type: application/json" \
  -d '{"question":"Liste meu portfólio","user_id":"u@e.com","thread_id":"t-1"}' | jq
```

## VS Code — Run and Debug

O projeto inclui `.vscode/launch.json` com alvos típicos:
- API FastAPI (Uvicorn)
- Streamlit Chat
- MCP Server – DuckDuckGo
- MCP Server – YFinance

Abra a aba “Run and Debug”, selecione a configuração e inicie.

## Integração com LM Studio

- O LLM padrão é servido pelo LM Studio. Inicie o servidor do modelo no LM Studio (ex.: Qwen 30B).
- Ajuste o modelo padrão em `get_trader_agent(foundation="lmstudio", model="...")` conforme necessário.
- Caso use outro backend (Ollama, OpenAI, etc.), adapte `LLMFactory`.

Exemplo de preset simples (LM Studio) para usar o modelo local (sem MCP externo, pois o agente já consome MCP via HTTP internamente):
```json
{
  "preset_name": "Agent Trader",
  "model_settings": {
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 4096
  },
  "system_message": "Você é um agente Trader em PT-BR...",
  "prompt_template": "{system_message}\n\nUsuário: {prompt}\nAssistente:"
}
```

## Variáveis de ambiente

- `API_URL` (opcional): usada pelo Streamlit `src/web/chat.py`. Padrão: `http://localhost:8000`.

```bash
export API_URL="http://localhost:8000"
```

## Testes dos MCP Servers

Teste via script assíncrono:
```bash
python src/test_mcp.py
```

Teste via HTTP (se exposto com FastAPI/uvicorn):
```bash
# Ajuste portas conforme seus servidores MCP
curl -s http://localhost:8001/health | jq
curl -s http://localhost:8002/health | jq
```

## Solução de problemas

- Uvicorn “Attribute not found”: confirme o objeto `app` em `src/api/api.py` e use o caminho correto:
  ```bash
  uvicorn src.api.api:app --reload
  ```
- Imports de pacotes: garanta `src/__init__.py` e `src/api/__init__.py` existam.
- Transporte HTTP do MCP:
  - Se `FastMCP.run()` não aceitar `host/port/path`, rode via `uvicorn` com a app ASGI do servidor MCP (wrapper).
- Portas ocupadas: mude as portas ou finalize processos antigos:
  ```bash
  lsof -i :8000 :8001 :8002 :8585
  ```

## Roadmap

- Memória persistente do usuário (armazenamento real).
- Novas integrações MCP (ex.: calendários, notícias setoriais).
- Métricas e tracing.
- Testes automatizados e exemplos de portfólio.

---
Sinta-se à vontade para abrir issues/PRs com melhorias.