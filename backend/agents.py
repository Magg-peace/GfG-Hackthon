"""LangGraph agent pipeline for the BI Dashboard.

Workflow:
  START
    └─► sql_generator      (Ollama/Gemini → SQL)
          └─► sql_executor  (PostgreSQL / SQLite)
                ├─(success)─► results_storer  (saves rows to results table)
                │                └─► chart_generator  (Ollama/Gemini → chart configs)
                │                        └─► END
                └─(error, retry < 3)─► sql_generator  (retry with error context)
                └─(error, retry ≥ 3)─► END  (return error state)
"""

from __future__ import annotations

import json
from typing import Any, TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, END

import ollama_llm as llm


# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # ---- inputs ---------------------------------------------------------
    query: str
    schema: str
    session_id: str
    conversation_history: list[dict]
    use_postgres: bool          # True if PostgreSQL is available
    previous_sql: str           # For follow-up support

    # ---- working state --------------------------------------------------
    generated_sql: str
    sql_errors: Annotated[list[str], operator.add]   # accumulated across retries
    retry_count: int

    # ---- results --------------------------------------------------------
    query_results: list[dict]
    results_table_name: str     # PostgreSQL results table

    # ---- output ---------------------------------------------------------
    charts: list[dict]
    summary: str
    thinking: str
    assumptions: list[str]
    error: str | None


# ── Helper: run postgres or sqlite ────────────────────────────────────────────

def _execute_query(sql: str, session_id: str | None, use_postgres: bool) -> list[dict]:
    """Try PostgreSQL first; fall back to SQLite."""
    if use_postgres:
        from pg_database import execute_pg_query
        return execute_pg_query(sql, session_id)
    else:
        from database import execute_query
        return execute_query(sql, session_id)


def _store_results(data: list[dict], session_id: str, idx: int, use_postgres: bool) -> str:
    """Persist results and return the table name."""
    if not data:
        return ""
    if use_postgres:
        from pg_database import store_query_results
        return store_query_results(data, session_id, idx)
    # SQLite – lightweight inline storage
    from database import get_connection
    import re
    table_name = f"results_{session_id.replace('-','')[:12]}_{idx}"
    conn = get_connection(session_id)
    cursor = conn.cursor()
    columns = list(data[0].keys())
    safe_cols = [re.sub(r"[^a-z0-9_]", "_", c.lower()) for c in columns]
    col_defs = ", ".join(f'"{sc}" TEXT' for sc in safe_cols)
    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}";')
    cursor.execute(f'CREATE TABLE "{table_name}" ({col_defs});')
    for row in data:
        ph = ", ".join(["?"] * len(safe_cols))
        vals = [str(row.get(c, "")) if row.get(c) is not None else None for c in columns]
        cursor.execute(f'INSERT INTO "{table_name}" VALUES ({ph})', vals)
    conn.commit()
    conn.close()
    return table_name


# ── Node implementations ───────────────────────────────────────────────────────

async def sql_generator_node(state: AgentState) -> dict:
    """Generate (or regenerate) SQL from the user query and schema."""
    query = state["query"]
    schema = state["schema"]
    retry_count = state.get("retry_count", 0)
    past_errors = state.get("sql_errors", [])

    # Augment query with retry context
    if past_errors:
        error_context = "\n".join(f"- Attempt {i+1} error: {e}" for i, e in enumerate(past_errors))
        augmented_query = (
            f"{query}\n\n"
            f"IMPORTANT: Previous SQL attempts failed. Fix the SQL to avoid these errors:\n"
            f"{error_context}"
        )
    else:
        augmented_query = query

    result = await llm.generate_sql(
        augmented_query, schema,
        dialect="PostgreSQL" if state.get("use_postgres") else "SQLite",
    )

    return {
        "generated_sql": result.get("sql", ""),
        "thinking": result.get("thinking", ""),
        "error": result.get("error"),
    }


async def sql_executor_node(state: AgentState) -> dict:
    """Execute the generated SQL against the database."""
    sql = state.get("generated_sql", "")
    if not sql or state.get("error"):
        return {"error": state.get("error") or "No SQL was generated."}

    session_id = state.get("session_id")
    use_postgres = state.get("use_postgres", False)

    try:
        rows = _execute_query(sql, session_id, use_postgres)
        return {
            "query_results": rows,
            "error": None,
        }
    except Exception as exc:
        return {
            "query_results": [],
            "sql_errors": [str(exc)],
            "retry_count": state.get("retry_count", 0) + 1,
            "error": str(exc),
        }


async def results_storer_node(state: AgentState) -> dict:
    """Save the query results to a dedicated results table."""
    data = state.get("query_results", [])
    session_id = state.get("session_id", "default")
    use_postgres = state.get("use_postgres", False)

    # Use the number of past errors as a unique index
    idx = len(state.get("sql_errors", []))

    try:
        table_name = _store_results(data, session_id, idx, use_postgres)
        return {"results_table_name": table_name}
    except Exception:
        return {"results_table_name": ""}


async def chart_generator_node(state: AgentState) -> dict:
    """Generate chart configurations + summary from query results."""
    query = state["query"]
    schema = state["schema"]
    sql = state.get("generated_sql", "")
    rows = state.get("query_results", [])

    if not rows:
        return {
            "charts": [],
            "summary": "The query returned no results.",
            "assumptions": [],
        }

    columns = list(rows[0].keys()) if rows else []
    sample = rows[:10]

    result = await llm.generate_charts(query, schema, sql, columns, sample,
                                       state.get("conversation_history", []))

    charts = result.get("charts", [])
    # Attach actual data to every chart so the frontend can render it immediately
    for chart in charts:
        chart.setdefault("data", rows)
        chart.setdefault("sql_executed", sql)
        chart.setdefault("row_count", len(rows))

    llm_error = result.get("error") if not charts else None

    return {
        "charts": charts,
        "summary": result.get("summary", ""),
        "assumptions": result.get("assumptions", []),
        "thinking": state.get("thinking", "") + "\n" + result.get("thinking", ""),
        "error": llm_error,
    }


# ── Routing ────────────────────────────────────────────────────────────────────

def route_after_executor(state: AgentState) -> str:
    """Decide whether to retry SQL generation or proceed to results storage."""
    if state.get("error") and state.get("retry_count", 0) < 3:
        return "sql_generator"
    elif state.get("error"):
        return END
    else:
        return "results_storer"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("results_storer", results_storer_node)
    graph.add_node("chart_generator", chart_generator_node)

    graph.set_entry_point("sql_generator")
    graph.add_edge("sql_generator", "sql_executor")
    graph.add_conditional_edges(
        "sql_executor",
        route_after_executor,
        {
            "sql_generator": "sql_generator",
            "results_storer": "results_storer",
            END: END,
        },
    )
    graph.add_edge("results_storer", "chart_generator")
    graph.add_edge("chart_generator", END)

    return graph.compile()


# Build the compiled graph once at import time
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ── Public entry-points ────────────────────────────────────────────────────────

async def run_query_pipeline(
    query: str,
    schema: str,
    session_id: str,
    use_postgres: bool = False,
    conversation_history: list[dict] | None = None,
) -> AgentState:
    """Run the full query → SQL → execute → store → chart pipeline.

    Returns the final AgentState dict.
    """
    initial: AgentState = {
        "query": query,
        "schema": schema,
        "session_id": session_id,
        "conversation_history": conversation_history or [],
        "use_postgres": use_postgres,
        "previous_sql": "",
        "generated_sql": "",
        "sql_errors": [],
        "retry_count": 0,
        "query_results": [],
        "results_table_name": "",
        "charts": [],
        "summary": "",
        "thinking": "",
        "assumptions": [],
        "error": None,
    }
    graph = get_graph()
    final: AgentState = await graph.ainvoke(initial)
    return final


async def run_followup_pipeline(
    followup: str,
    previous_query: str,
    previous_sql: str,
    schema: str,
    session_id: str,
    use_postgres: bool = False,
) -> AgentState:
    """Run a follow-up query through the pipeline."""
    # Generate modified SQL via the LLM
    dialect = "PostgreSQL" if use_postgres else "SQLite"
    result = await llm.generate_followup_sql(followup, previous_query, previous_sql, schema, dialect=dialect)

    if result.get("error"):
        empty: AgentState = {
            "query": followup,
            "schema": schema,
            "session_id": session_id,
            "conversation_history": [],
            "use_postgres": use_postgres,
            "previous_sql": previous_sql,
            "generated_sql": "",
            "sql_errors": [],
            "retry_count": 0,
            "query_results": [],
            "results_table_name": "",
            "charts": result.get("charts", []),
            "summary": result.get("summary", ""),
            "thinking": result.get("thinking", ""),
            "assumptions": result.get("assumptions", []),
            "error": result.get("error"),
        }
        return empty

    # Follow-up returns charts directly (from Gemini) or SQL that needs executing
    if result.get("charts"):
        # Gemini-style: charts already include SQL; we need to execute each one
        charts_with_data = []
        for chart in result.get("charts", []):
            chart_sql = chart.get("sql", "")
            if chart_sql:
                try:
                    rows = _execute_query(chart_sql, session_id, use_postgres)
                    chart["data"] = rows
                    chart["sql_executed"] = chart_sql
                    chart["row_count"] = len(rows)
                except Exception as e:
                    chart["data"] = []
                    chart["error"] = str(e)
            charts_with_data.append(chart)

        final: AgentState = {
            "query": followup,
            "schema": schema,
            "session_id": session_id,
            "conversation_history": [],
            "use_postgres": use_postgres,
            "previous_sql": previous_sql,
            "generated_sql": result.get("charts", [{}])[0].get("sql", "") if result.get("charts") else "",
            "sql_errors": [],
            "retry_count": 0,
            "query_results": charts_with_data[0].get("data", []) if charts_with_data else [],
            "results_table_name": "",
            "charts": charts_with_data,
            "summary": result.get("summary", ""),
            "thinking": result.get("thinking", ""),
            "assumptions": result.get("assumptions", []),
            "error": None,
        }
        return final

    # Ollama-style: follow-up returned SQL; run it through the normal pipeline
    return await run_query_pipeline(
        followup, schema, session_id, use_postgres,
        conversation_history=[{"query": previous_query, "sql": previous_sql}],
    )
