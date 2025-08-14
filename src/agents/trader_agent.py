
import os
from typing import TypedDict
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.runnables.config import RunnableConfig
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
import asyncio
import datetime
from zoneinfo import ZoneInfo

from src.llm.llm_factory import LLMFactory  

from src.agents.memory_agent import UserMemory, get_store

DATABASE_URL = os.getenv(
    "POSTGRES_URL"
)
print(f"Using DATABASE_URL: {DATABASE_URL}")

@tool(description="""Salva a memória completa do usuário incluindo informações pessoais e portfólio.
Parameters: 
- user_memory: Dicionário contendo:
  - user_info: {'name': 'Nome do usuário'}
  - user_portfolio: Lista de posições [{'empresa': 'Nome da empresa', 'ticker': 'CÓDIGO.SA', 'quantity': quantidade_ações, 'total_value_invested': valor_em_reais}]
""")
async def save_user_memory(user_memory: UserMemory, config: RunnableConfig) -> str:
    user_id = config.get("configurable", {}).get("user_id", "default_user")
    namespace = ("users", user_id)
    key = "user_memory"
    try:
        async with AsyncPostgresStore.from_conn_string(DATABASE_URL) as store:
            await store.aput(namespace, key, dict(user_memory))
        return "User memory saved"
    except Exception as e:
        print(f"Error saving user memory: {e}")
        return "Error saving user memory"

@tool(description="""Recupera a memória completa do usuário com informações pessoais e portfólio.
Retorna um dicionário com:
- user_info: informações básicas (nome)
- user_portfolio: lista de posições com empresa, ticker, quantidade e valor investido
""")
async def get_user_memory(config: RunnableConfig) -> UserMemory:

    user_id = config.get("configurable", {}).get("user_id", "default_user")
    namespace = ("users", user_id)
    key = "user_memory"
    try:
        async with AsyncPostgresStore.from_conn_string(DATABASE_URL) as store:
            existing_memory = await store.aget(("users", user_id), "user_memory")
            if existing_memory and existing_memory.value:
                return existing_memory.value  # type: ignore
            else:
                # Return default empty memory structure
                return {"user_info": {"name": ""}, "user_portfolio": []}
    except Exception as e:
        print(f"Error getting user memory: {e}")
        return {"user_info": {"name": ""}, "user_portfolio": []}


@tool(description="Remove uma empresa do portfólio do usuário. Parameters: empresa = nome da empresa a ser removida do portfólio.")
async def delete_user_portfolio_empresa(empresa: str, config: RunnableConfig) -> str:
    user_id = config.get("configurable", {}).get("user_id", "default_user")
    namespace = ("users", user_id)
    key = "user_memory"
    try:
        async with AsyncPostgresStore.from_conn_string(DATABASE_URL) as store:
            existing_memory = await store.aget(namespace, key)
            if not existing_memory or not getattr(existing_memory, "value", None):
                return "Não há memória de usuário para atualizar"

            memory_value = existing_memory.value  # type: ignore
            portfolio = memory_value.get("user_portfolio", [])
            if not isinstance(portfolio, list):
                return "Estrutura de memória inválida: user_portfolio não é uma lista"

            empresa_normalized = empresa.strip().casefold()
            updated_portfolio = [
                position for position in portfolio
                if str(position.get("empresa", "")).strip().casefold() != empresa_normalized
            ]

            if len(updated_portfolio) == len(portfolio):
                return "Empresa não encontrada no portfólio"

            memory_value["user_portfolio"] = updated_portfolio
            await store.aput(namespace, key, dict(memory_value))
            return "Empresa removida do portfólio"
    except Exception as e:
        print(f"Error deleting company from user portfolio: {e}")
        return "Error deleting company from user portfolio"



tz = "America/Sao_Paulo"
now = datetime.datetime.now(ZoneInfo(tz))
date_time_today = now.strftime("%Y-%m-%d %H:%M:%S")

prompt = """
<persona>
Você é um agente Trader que ajuda o usuário em PT-BR a gerenciar seu portfólio de investimentos.
</persona>

<objectives>
Gerenciar o portfólio, sugerir investimentos, analisar indicadores de empresas e o sentimento do mercado.
</objectives>

<regras>
- Hoje é {date_time_today} formato: Ano-Mes-Dia Hora:Min:Seg
- Use apenas os tools disponíveis; não invente tools.
- Ao iniciar, recupere a memória do usuário com get_user_memory.
- Se não houver portfólio, pergunte se deseja criar um. Em caso afirmativo, salve com save_user_memory.
- Sempre atualize a data com get_current_datetime_tool e exiba “Atualizado em”.
- Se o usuário citar empresas sem ticker, use find_ticker_tool para obter o ticker.
- Para cada posição do portfólio, atualize a cotação com get_stock_price_tool. Se for sobre uma data específica, use get_stock_price_on_date_tool.
- Para comentários, use get_company_indicators_tool (indicadores) e search (para analise de sentimento sentimento). Quando útil, complemente com fetch_content.
- Sempre que o portfólio for alterado (inclusão/remoção/quantidade/valor investido), persista com update_user_memory.
</regras>

<cálculos>
- Valor Atual (R$) = Quantidade x Cotação Atual
- Variação (R$) = Valor Atual - Valor Total Investido
- Variação (%) = (Variação (R$) / Valor Total Investido) x 100
</cálculos>

<output>
- Apresente uma tabela Markdown com as colunas: Empresa | Ticker | Quantidade | Valor Total Investido (R$) | Cotação Atual (R$) | Valor Atual (R$) | Variação (R$) | Variação (%).
- Totalize Quantidade, Valor Total Investido e Valor Atual. Formate valores em R$ com 2 casas decimais.
- Inclua comentários objetivos dos indicadores e do sentimento, citando brevemente as ferramentas usadas.
- Se não houver portfólio, não gere a tabela; apenas faça a pergunta para criação.
</output>
""".format(date_time_today=date_time_today)

system_prompt = SystemMessage(
        content=(prompt)
    )

async def get_trader_agent(foundation: str = "lmstudio", model: str = "qwen/qwen3-30b-a3b-2507", temperature: float = 0.7) -> create_react_agent:
    """foundation: lmstudio/ollama/openai/genai"""

    try:
        llm_factory = LLMFactory()

        if foundation == "lmstudio":
            user_model = llm_factory.get_LMStudio_llm(model)
        elif foundation == "ollama":
            user_model = llm_factory.get_ollama_llm(model)
        elif foundation == "openai":
            user_model = llm_factory.get_openai_llm(model)
        elif foundation == "genai":
            user_model = llm_factory.get_genai_llm(model)
        else:
            raise ValueError(f"Unsupported foundation: {foundation}")
        
        user_model.temperature = temperature

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
        mcp_tools.append(save_user_memory)
        mcp_tools.append(get_user_memory)
        mcp_tools.append(delete_user_portfolio_empresa)

        memory_checkpoint, memory_store = await get_store()

        trader_agent = create_react_agent(
            model=user_model,
            tools=mcp_tools,
            prompt=system_prompt,
            checkpointer=memory_checkpoint,
            store=memory_store,
        )

    except Exception as e:
        print(f"Error creating trader agent: {e}")
        raise

    return trader_agent