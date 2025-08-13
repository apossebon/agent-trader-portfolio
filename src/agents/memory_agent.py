
import os
from typing import TypedDict
import psycopg_pool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore



class UserInfo(TypedDict):
    """Informações básicas do usuário como Nome completo."""
    name: str  # Nome completo do usuário


class UserPortfolio(TypedDict):

    """Representa uma posição de ação/ativo no portfólio do usuário."""
    empresa: str  # Nome da empresa (ex: "Petrobras", "JBS")
    ticker: str  # Código da ação na bolsa (ex: "PETR4.SA", "JBSS3.SA")
    quantity: int  # Quantidade de ações que o usuário possui
    total_value_invested: float  # Valor total investido em reais (R$)

class UserMemory(TypedDict):
    """Memória completa do usuário contendo informações pessoais e portfólio."""
    user_info: UserInfo  # Informações básicas do usuário (nome)
    user_portfolio: list[UserPortfolio]  # Lista de todas as posições no portfólio

# DATABASE_URL = {
#     "POSTGRES_URL": os.getenv("DATABASE_URL")
# }
DATABASE_URL = os.getenv(
    "POSTGRES_URL",
)

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

    return memory_checkpoint, store