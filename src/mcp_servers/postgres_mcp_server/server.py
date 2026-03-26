import os
import argparse
import asyncio
from typing import Optional, List

import asyncpg
from mcp.server.fastmcp import FastMCP, Context
from langchain_core.tools import tool
from langchain_mcp_adapters.tools import to_fastmcp

from src.llm.llm_factory import LLMFactory


POSTGRES_URL = os.getenv("POSTGRES_URL_HALO", "postgresql://postgres:Aap7978Po@halo-db.postgres.database.azure.com:5432/agentdb")


async def _get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(dsn=POSTGRES_URL)


async def _fetch_val(conn: asyncpg.Connection, query: str, *args):
    return await conn.fetchval(query, *args)


# -----------------------
# Internal helpers (not tools)
# -----------------------
ALLOWED_DISC_STYLES = {
    "D", "I", "S", "C",
    "DI", "ID", "CS", "SI", "SC", "CD", "IS", "DC"
}


def _normalize_disc_style(value: str) -> str:
    s = (value or "").strip().upper()
    if s not in ALLOWED_DISC_STYLES:
        raise ValueError(
            f"Invalid disc_style '{value}'. Allowed: {sorted(ALLOWED_DISC_STYLES)}"
        )
    return s


async def _describe_schema_impl(schema: Optional[str] = None) -> str:
    target_schema = schema or "public"
    conn = await _get_conn()
    try:
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_name
            """,
            target_schema,
        )
        if not tables:
            return f"Schema '{target_schema}' has no tables."
        lines = [f"Schema: {target_schema}"]
        for t in tables:
            table = t["table_name"]
            cols = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
                """,
                target_schema,
                table,
            )
            col_desc = ", ".join(
                f"{c['column_name']} ({c['data_type']}{' nullable' if c['is_nullable']=='YES' else ''})"
                for c in cols
            )
            lines.append(f"- {table}: {col_desc}")
        return "\n".join(lines)
    finally:
        await conn.close()


async def _run_sql_impl(sql: str) -> str:
    lowered = (sql or "").strip().lower()
    if not lowered.startswith("select"):
        return "Only SELECT queries are allowed."
    conn = await _get_conn()
    try:
        rows = await conn.fetch(sql)
        if not rows:
            return "No rows returned."
        headers = list(rows[0].keys())
        lines = [",".join(headers)]
        for r in rows:
            values = [str(r[h]) if r[h] is not None else "" for h in headers]
            lines.append(",".join(values))
        return "\n".join(lines)
    finally:
        await conn.close()


@tool(
    description=(
        "Provide personalized guidance to develop individual growth, flexibility, and adaptability "
        "based on the user's DiSC profile style. "
    "Parameter: disc_style: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive."
        "Returns concise, actionable tips tailored to the style."
    )
)
async def self_improvement_adaptability(disc_style: str):
    """
    name: self_improvement_adaptability
    description: Retrieves guidance on developing individual growth, flexibility, and adaptability based on the DiSC profile.
    when_to_use: When the user requests tips about self-development, resilience, or adapting to change.
    example_queries:
      - "How can I improve my adaptability at work as an S style?"
      - "What practices help a C profile handle changes?"
    cluster_keys:
      content_domain: [self_improvement]
      content_theme: [adaptability]
      content_application: [improving, learning_about]
    parameters:
      disc_style: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
    """
    # Validate and normalize style
    try:
        style = _normalize_disc_style(disc_style)
    except ValueError as e:
        return str(e)

    # Build query (read-only). Note: Using literal since _run_sql_impl executes raw SELECT text.
    query = (
        "SELECT chunk_text, self_style, other_style, source_name, source_url "
        "FROM excel_embeddings "
        "WHERE content_domain = 'self_improvement' "
        "AND content_theme = 'adaptability' "
        "AND content_application IN ('improving','learning_about') "
        f"AND self_style = '{style}' "
        "ORDER BY release_date DESC NULLS LAST, created_at DESC "
        "LIMIT 50;"
    )

    return await _run_sql_impl(query)


@tool(
    description=(
        "Provide strategies to collaborate better with colleagues of different DiSC styles, "
        "explaining typical behaviors and practical adjustments. "
        "Parameters: self_style, colleague_style (e.g., 'D','I','S','C' or full names)."
    )
)
async def collaboration_different_styles_colleague(self_style: str, colleague_style: str) -> str:
    """
    name: collaboration_different_styles_colleague
    description: Provides strategies to work better with colleagues of different DiSC styles, explaining behaviors and adjustments.
    when_to_use: When the question involves the relationship between two different styles.
    example_queries:
      - "How can a C profile collaborate better with an i profile?"
      - "Tips for a D profile to work with an S profile."
    cluster_keys:
      content_domain: [collaboration]
      content_theme: [different_styles]
      content_application: [your_colleague]
    parameters:
      self_style: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
      colleague_style: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
    """

    # Validate and normalize style
    try:
        style = _normalize_disc_style(self_style)
        colleague = _normalize_disc_style(colleague_style)
    except ValueError as e:
        return str(e)

    query = (
        "SELECT id, chunk_text, self_style, other_style, source_name, source_url"
        " FROM excel_embeddings"
        " WHERE content_domain = 'collaboration'"
        " AND content_theme  = 'different_styles'"
        " AND content_application = 'your_colleague'"
       f" AND (self_style = '{style}')"
       f" OR (other_style = '{colleague}')"
        " ORDER BY release_date DESC NULLS LAST, created_at DESC"
        " LIMIT 50;"
    )




    return await _run_sql_impl(query)

@tool(
    description=(
        "Offer insights on conflict resolution, joint decision-making, and overcoming obstacles "
        "in teams with diverse DiSC styles. Parameters: style_a, style_b, context (optional)."
    )
)
async def collaboration_relationships_problem_solving(
    style_a: str,
    style_b: str,
    context: Optional[str] = None,
) -> str:
    """
    name: collaboration_relationships_problem_solving
    description: Offers insights on conflict resolution, joint decision-making, and overcoming obstacles in diverse-style teams.
    when_to_use: When the user seeks ways to resolve disagreements or find collective solutions.
    example_queries:
      - "How to reduce friction between D and S styles in project discussions?"
      - "How to facilitate decisions when there are conflicts between i and C styles?"
    cluster_keys:
      content_domain: [collaboration]
      content_theme: [relationships]
      content_application: [problem_solving]
    parameters:
      style_a: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
      style_b: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
      context: Optional situation or decision scenario.
    """

    # Validate and normalize style
    try:
        style_a = _normalize_disc_style(style_a)
        style_b = _normalize_disc_style(style_b)
    except ValueError as e:
        return str(e)

    query = (
        "SELECT id, chunk_text, self_style, other_style, source_name, source_url"
        " FROM excel_embeddings"
        " WHERE content_domain = 'collaboration'"
        " AND content_theme  = 'relationships'"
        " AND content_application = 'problem_solving'"
        f" AND (self_style = '{style_a}')"
        f" OR (other_style = '{style_b}')"
        " ORDER BY release_date DESC NULLS LAST, created_at DESC"
        " LIMIT 50;"
    )
    return await _run_sql_impl(query)

@tool(
    description=(
        "Explain how DiSC styles impact individual and team performance, highlighting strengths and risks. "
        "Parameters: team_mix (list of styles), goals (optional)."
    )
)
async def collaboration_relationships_performance(
    style_a: str,
    goals: Optional[str] = None,
) -> str:
    """
    name: collaboration_relationships_performance
    description: Shows how DiSC styles impact individual and team performance, highlighting strengths and risks.
    when_to_use: For questions about improving performance and productivity in diverse teams.
    example_queries:
      - "How can a team with predominance of i increase results?"
      - "What are performance risks in a team with many C profiles?"
    cluster_keys:
      content_domain: [collaboration]
      content_theme: [relationships]
      content_application: [performance]
    parameters:
      style_a: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
      goals: Optional performance goals or KPIs.
    """
    # Validate and normalize style
    try:
        style_a = _normalize_disc_style(style_a)
    except ValueError as e:
        return str(e)

    query = (
        "SELECT id, chunk_text, self_style, other_style, source_name, source_url"
        " FROM excel_embeddings"
        " WHERE content_domain = 'collaboration'"
        " AND content_theme  = 'relationships'"
        " AND content_application = 'performance'"
        f" AND (self_style = '{style_a}')"
        " ORDER BY release_date DESC NULLS LAST, created_at DESC"
        " LIMIT 50;"
    )
    return await _run_sql_impl(query)

@tool(
    description=(
        "Explain sources of tension between different DiSC styles and how to reduce conflicts "
        "to improve collaboration. Parameters: style_a, style_b, scenario (optional)."
    )
)
async def collaboration_relationships_tension(
    style_a: str,
    style_b: str,
    scenario: Optional[str] = None,
) -> str:
    """
    name: collaboration_relationships_tension
    description: Explains sources of tension between different DiSC styles and ways to reduce conflicts.
    when_to_use: For questions about tension, stress, or misunderstandings between styles.
    example_queries:
      - "Why do D and C profiles clash and how to reduce it?"
      - "How to ease tensions between i and S in meetings?"
    cluster_keys:
      content_domain: [collaboration]
      content_theme: [relationships]
      content_application: [tension]
    parameters:
      style_a: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
      style_b: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
      scenario: Optional meeting or workflow context.
    """
    # Validate and normalize style
    try:
        style_a = _normalize_disc_style(style_a)
        style_b = _normalize_disc_style(style_b)
    except ValueError as e:
        return str(e)

    query = (
        "SELECT id, chunk_text, self_style, other_style, source_name, source_url"
        " FROM excel_embeddings"
        " WHERE content_domain = 'collaboration'"
        " AND content_theme  = 'relationships'"
        " AND content_application = 'tension'"
        f" AND (self_style = '{style_a}')"
        f" OR (other_style = '{style_b}')"
        " ORDER BY release_date DESC NULLS LAST, created_at DESC"
        " LIMIT 50;"
    )
    return await _run_sql_impl(query)

@tool(
    description=(
        "Retrieve detailed descriptions of characteristics, behaviors, and typical tendencies "
        "for each DiSC style or style combinations. Parameter: style_or_combo."
    )
)
async def disc_model_styles_tendencies(style_or_combo: str) -> str:
    """
    name: disc_model_styles_tendencies
    description: Retrieves detailed descriptions of characteristics, behaviors, and typical tendencies of each DiSC style.
    when_to_use: When the user asks for a direct explanation of a style or a combination of styles.
    example_queries:
      - "What are the main characteristics of the SC style?"
      - "What differentiates DI and ID styles?"
    cluster_keys:
      content_domain: [the_disc_model]
      content_theme: [styles]
      content_application: [tendencies_of_styles]
    parameters:
      style_or_combo: A single style or combination label (e.g., "SC", "DI", "ID").
    """
    # Validate and normalize style
    try:
        style = _normalize_disc_style(style_or_combo)
    except ValueError as e:
        return str(e)
    
    query = (
        "SELECT id, chunk_text, self_style, other_style, source_name, source_url"
        " FROM excel_embeddings"
        " WHERE content_domain = 'the_disc_model'"
        " AND content_theme  = 'styles'"
        " AND content_application = 'tendencies_of_styles'"
        f" AND (self_style = '{style}')"
        " ORDER BY release_date DESC NULLS LAST, created_at DESC"
        " LIMIT 50;"
    )
    return await _run_sql_impl(query)

@tool(
    description=(
        "Provide DiSC-based leadership guidance, including how to manage up, down, and across "
        "with different styles. Parameters: leader_style, target_relationship "
        "('managing_up'|'managing_down'|'managing_across'), target_style (optional), goals (optional)."
    )
)
async def leadership_managing_all_levels(
    leader_style: str,
    target_relationship: str,
    target_style: Optional[str] = None,
    goals: Optional[str] = None,
) -> str:
    """
    name: leadership_managing_all_levels
    description: Provides leadership guidance applied to DiSC, including managing bosses, peers, and reports while respecting different styles.
    when_to_use: For questions about adaptive leadership, influence, and management at multiple levels.
    example_queries:
      - "How can an i-style leader influence a C-style boss?"
      - "Management strategies for a D manager with an S team."
    cluster_keys:
      content_domain: [leadership]
      content_theme: [managing_up_down_in_between]
      content_application: [learning_about]
    parameters:
      leader_style: One of 'D','I','S','C', 'DI', 'ID','CS','SI','SC','CD','IS','DC'. Case-insensitive.
      target_relationship: One of 'managing_up','managing_down','managing_across'.
      target_style: Optional target's style.
      goals: Optional leadership or team objectives.
    """
    parts = [f"{leader_style} leading ({target_relationship})"]
    if target_style:
        parts.append(f"targeting {target_style}")
    if goals:
        parts.append(f"toward {goals}")
    return " ".join(parts) + "."



@tool(description="Describe database schemas and tables. Optional: schema (default: public). Returns a concise, human-readable summary.")
async def describe_schema(schema: Optional[str] = None) -> str:
    return await _describe_schema_impl(schema)


@tool(description="Execute a read-only SQL SELECT. Parameters: sql = SELECT query text. Returns rows as CSV-like text.")
async def run_sql(sql: str) -> str:
    return await _run_sql_impl(sql)


@tool(description="Answer a question about the database by generating and executing SQL. Parameters: question = natural language question. Optional: schema=target schema.")
async def ask_db(question: str, schema: Optional[str] = None) -> str:
    target_schema = schema or "public"
    # Build a schema snapshot to ground the LLM
    schema_summary = await _describe_schema_impl(target_schema)

    llm_factory = LLMFactory()
    foundation = "openai"
    model = "gpt-4o-mini"

    if foundation == "lmstudio":
        llm = llm_factory.get_LMStudio_llm(model)
    elif foundation == "ollama":
        llm = llm_factory.get_Ollama_llm(model)
    else:
        llm = llm_factory.get_llm_AzureOpenAI()

    prompt = (
        "You are a senior data analyst. Given the database schema and a question, "
        "write a safe, correct PostgreSQL SELECT query that answers it. "
        "- Use only the provided schema and the target schema name.\n"
        "- Never modify data.\n"
        "- Prefer explicit joins.\n"
        "- Return only the SQL between <sql> tags.\n\n"
        f"<schema>\n{schema_summary}\n</schema>\n"
        f"<question>\n{question}\n</question>\n"
        f"<target_schema>{target_schema}</target_schema>\n"
        "<format>\n<sql>SELECT ...</sql>\n</format>\n"
    )

    # Call model
    resp = await llm.ainvoke(prompt)  # type: ignore
    text = resp.content if hasattr(resp, "content") else str(resp)
    print("LLm resp:", text)
    # Extract SQL between tags
    start = text.find("<sql>")
    end = text.find("</sql>")
    if start == -1 or end == -1 or end <= start + 5:
        return f"Failed to generate SQL. Model output: {text}"
    sql = text[start + 5:end].strip()
    return await _run_sql_impl(sql)


tools = [
    to_fastmcp(describe_schema),
    to_fastmcp(run_sql),
    to_fastmcp(ask_db),
    to_fastmcp(self_improvement_adaptability),
    to_fastmcp(collaboration_different_styles_colleague),
    to_fastmcp(collaboration_relationships_problem_solving),
    to_fastmcp(collaboration_relationships_performance),
    to_fastmcp(collaboration_relationships_tension),
    to_fastmcp(disc_model_styles_tendencies),
    # to_fastmcp(leadership_managing_all_levels),
]

mcp = FastMCP("postgres-tools", host="0.0.0.0", port=8003, tools=tools)


def parse_args():
    parser = argparse.ArgumentParser(description="Run FastMCP server with selectable transport.")
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default=os.getenv("FASTMCP_TRANSPORT", "stdio"),
                        help="Transport to use (default: stdio)")
    parser.add_argument("--host", default=os.getenv("FASTMCP_HOST", "127.0.0.1"),
                        help="Host/interface for HTTP/SSE (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.getenv("FASTMCP_PORT", "8000")),
                        help="Port for HTTP/SSE (default: 8000)")
    parser.add_argument("--path", default=os.getenv("FASTMCP_PATH", "/mcp"),
                        help="HTTP path when transport=http (default: /mcp)")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return
    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http")
        return
    if args.transport == "sse":
        mcp.run(transport="sse")
        return


if __name__ == "__main__":
    main()


