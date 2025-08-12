from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
import asyncio
import datetime
from zoneinfo import ZoneInfo

from llm.llm_factory import LLMFactory   

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
"""

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
            pass
        elif foundation == "openai":
            pass
        elif foundation == "genai":
            pass
        else:
            raise ValueError(f"Unsupported foundation: {foundation}")
        
        user_model.temperature = temperature

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
            model=user_model,
            tools=mcp_tools,
            prompt=system_prompt,
        )

    except Exception as e:
        print(f"Error creating trader agent: {e}")
        raise

    return trader_agent