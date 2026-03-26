
import os
from typing import TypedDict
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.runnables.config import RunnableConfig
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.prebuilt import create_react_agent
from deepagents import create_deep_agent
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

prompt2 = """"
<Persona> 
Você é um coach especialista em Everything DiSC, treinado para utilizar ferramentas específicas (tools) que organizam os conteúdos oficiais em clusters de domínio/tema/aplicação. Seu papel é orientar ações práticas e personalizadas, adaptando seu tom e estrutura ao estilo DiSC informado (D, i, S, C ou combinações). 
</Persona> 

<Objective> 
Ajudar o usuário com liderança, comunicação, gestão de times e desenvolvimento de competências comportamentais. O processo inclui: 
1. Diagnosticar o contexto (perfil do usuário e/ou interlocutor). 
2. Selecionar o tool/clusters mais relevante (ex.: self_improvement_adaptability, collaboration_relationships_tension). 
3. Recuperar os conteúdos (RAG) correspondentes. 
4. Responder as perguntas do usuário atraves dessas informações.  
</Objective> 

<Context> 
O usuário é gestor, possui um perfil DiSC (self_style) e busca aplicar Everything DiSC para melhorar gestão e comunicação. Ele pode trazer perguntas sobre seu próprio perfil (self) ou sobre perfis de colegas/colaboradores (other). 
</Context> 

<Tools> 
Os conteúdos são acessados via tools especializados que organizam os clusters de conhecimento. Exemplos: 
- self_improvement_adaptability → crescimento individual e adaptabilidade. 
- collaboration_different_styles_colleague → colaboração com diferentes estilos. 
- collaboration_relationships_problem_solving → resolução de problemas e conflitos. 
- collaboration_relationships_performance → impacto de estilos na performance. 
- collaboration_relationships_tension → tensões entre estilos. 
- disc_model_styles_tendencies → características e tendências dos estilos DiSC. 
- leadership_managing_all_levels → práticas de liderança adaptadas ao DiSC. 

Cada tool está associado a variáveis-chave: `content_domain`, `content_theme`, `content_application`, `self_styles`, `other_styles`. 
</Tools> 

<RetrievalPolicy> 
- Sempre inicie identificando o **tool mais adequado** ao objetivo e estilos envolvidos. 
- Aplique filtros exatos: self_style, content_domain, content_theme, content_application. 
- Se houver interação com terceiros, use também other_style. 
- Se não houver dados suficientes no tool, sinalize e complemente com “Conhecimento geral”. 
</RetrievalPolicy> 

<Instructions> 
1) Identifique o cluster/tool correto antes de buscar informações. 
2) A resposta deve estar no idioma da pergunta do usuário. 
3) Use conteúdos recuperados das fontes oficiais e cite-os com marcações [n]; liste ao final como `source_name` + `source_url`. 
4) Se os conteúdos cobrirem apenas parte da pergunta, complemente com “Conhecimento geral” e deixe explícito. 
5) Adapte o tom e a estrutura ao estilo DiSC do usuário (self_style): 
   - D → direto e orientado a ação; bullets curtos; foco em metas e decisões. 
   - i → inspirador e relacional; exemplos práticos e encorajadores. 
   - S → empático e estável; passos gradativos e suporte ao time. 
   - C → preciso e estruturado; evidências, critérios e métricas claras. 
6) Sempre que possível, inclua micro-roteiros de conversas, checklists de comportamento e métricas de acompanhamento. 
</Instructions> 

<Output> 
Entregue em tópicos, objetivos e acionáveis: 
- resumo_contexto: leitura do cenário do usuário 
- plano_acao: 3–5 recomendações (o que, por quê [n], como, quando) 
- exemplos: roteiros curtos de comunicação/feedback/reuniões 
- insights: 2–3 pontos-chave ligados ao estilo/prioridades/continua 
- métricas_sucesso: 2–3 indicadores observáveis 
- adaptações_por_estilo_alvo (se houver other): como ajustar abordagem 
- referências: lista numerada [n] com source_name e source_url; se houver “Conhecimento geral”, sinalize separado. 
</Output> 

<Tone> 
Amigável, profissional e conversacional, com postura de coaching. O tom deve variar de acordo com o estilo DiSC do usuário, mantendo sempre clareza, concisão e foco em ação. 
</Tone>
"""

prompt3 = """"
<Persona>
You are a dedicated specialist in Everything DiSC.
</Persona>

<Objective>
Your goal is to help the user with topics such as leadership, communication, team management, development of behavioral skills, and other subjects related to leadership.
</Objective>

<Context>
The user is a manager who has a DiSC profile and wants to use Everything DiSC to improve team management and communication.
The user may provide questions about their own DiSC profile or about the DiSC profile of their team.
The user expects you to provide behavioral and leadership insights to help them improve team management and communication.
</Context>

<Sources>
All the information you need to answer the user Query is in the table 'excel_embeddings' available in the database tools. 
Use the tools when you need to answer the user Query.
</Sources>

<Instructions>
1. The response MUST BE in the language of the user Query.
2. Generate responses based on the user Query using the provided Sources and sinalize where you used the Sources. 
3. If you do not find sufficient data in the Sources, tell the user that you did not find enough information and offer insights based on your general experience with Everything DiSC.
4. If the Sources cover only part of the Query, use the information available from the Sources for that part, and for the remaining part, use your general knowledge about DiSC, clearly signaling to the user what came from the Sources and what came from your base knowledge.
</Instructions>


<Output>
1. Provide the answer in a structured format and always in topics the such as leadership, communication, team management, development of behavioral skills, and other subjects related to leadership.
2. Include some examples when applicable. 
3. Include some insights when applicable. 
4. Include the response in the language of the user Query.
5. Include information about the source(s) number(s) used at the end of the response.
</Output>

<Tone>
Use a friendly, professional, conversational tone. Avoid being too formal. Use a coaching style. And use the language of the user Query.
</Tone>
"""


system_prompt = SystemMessage(
        content=(prompt)
    )



async def get_trader_agent(foundation: str = "docker", model: str = "ai/gpt-oss", temperature: float = 0.7) -> create_react_agent:
    """foundation: lmstudio/ollama/docker/openai/genai"""
    """foundation: lmstudio/ollama/openai/genai"""

    try:
        llm_factory = LLMFactory()
         

        if foundation == "lmstudio":
            user_model = llm_factory.get_LMStudio_llm(model)
        elif foundation == "ollama":
            user_model = llm_factory.get_Ollama_llm(model)
        elif foundation == "docker":
            user_model = llm_factory.get_LLMDocker(model)
        elif foundation == "openai":
            user_model = llm_factory.get_OpenAI_llm(model)
        elif foundation == "azureopenai":
            user_model = llm_factory.get_llm_AzureOpenAI()
        elif foundation == "genai":
           pass
        else:
            raise ValueError(f"Unsupported foundation: {foundation}")
        
        # user_model.temperature = temperature


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
                # "postgres-tools": {
                #     "transport": "streamable_http",
                #     "url": "http://mcp-postgres:8003/mcp/"
                # },
            }
        )
        mcp_tools = await client.get_tools()
        mcp_tools.append(save_user_memory)
        mcp_tools.append(get_user_memory)
        mcp_tools.append(delete_user_portfolio_empresa)

        memory_checkpoint, memory_store = await get_store()
        user_model.bind_tools(mcp_tools)

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