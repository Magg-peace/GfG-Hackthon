"""Ollama-backed LLM integration for SQL generation and chart configuration.

Priority model chain (SQL):  deepseek-coder → qwen2.5-coder → llama3.2 → gemma3
Priority model chain (Viz):  qwen2.5-coder  → deepseek-coder → llama3.2 → gemma3

Falls back to Google Gemini when Ollama is unreachable.
"""

import json
import os
import re
import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

# Override individual models via env vars
OLLAMA_SQL_MODEL = os.getenv("OLLAMA_SQL_MODEL", "")
OLLAMA_VIZ_MODEL = os.getenv("OLLAMA_VIZ_MODEL", "")

_SQL_MODEL_CHAIN = ["deepseek-coder:latest", "qwen2.5-coder:latest",
                    "llama3.2:latest", "gemma3:latest", "llama3:latest",
                    "mistral:latest", "codellama:latest"]
_VIZ_MODEL_CHAIN = ["qwen2.5-coder:latest", "deepseek-coder:latest",
                    "llama3.2:latest", "gemma3:latest", "llama3:latest",
                    "mistral:latest"]

_available_models: list[str] | None = None


# ── Model discovery ────────────────────────────────────────────────────────────

def get_available_models() -> list[str]:
    """Fetch installed model names from Ollama (cached after first call)."""
    global _available_models
    if _available_models is not None:
        return _available_models
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
        _available_models = [m["name"] for m in data.get("models", [])]
        return _available_models
    except Exception:
        _available_models = []
        return []


def is_ollama_available() -> bool:
    return len(get_available_models()) > 0


def _pick_model(chain: list[str], override: str = "") -> str | None:
    """Return the first available model from *chain*, or None."""
    if override:
        return override  # trust user override even if not discovered
    available = get_available_models()
    # Exact match first
    for candidate in chain:
        if candidate in available:
            return candidate
    # Prefix match (e.g. "deepseek-coder" matches "deepseek-coder:6.7b")
    for candidate in chain:
        base = candidate.split(":")[0]
        for m in available:
            if m.startswith(base):
                return m
    return None


# ── Core Ollama call ───────────────────────────────────────────────────────────

def _call_ollama(model: str, system: str, user: str) -> str:
    """Call Ollama /api/chat synchronously and return the assistant message text."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 4096,
        },
    }
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        resp = client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


async def _call_ollama_async(model: str, system: str, user: str) -> str:
    """Async version of the Ollama call for use inside asyncio contexts."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 4096,
        },
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


# ── JSON extraction ────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from LLM response."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Find the first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last-resort: try to fix common issues (trailing commas)
        text = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(text)


# ── System prompts ─────────────────────────────────────────────────────────────

_SQL_SYSTEM = """You are an expert SQL analyst. Given a PostgreSQL database schema and a user question,
generate a single PostgreSQL SELECT query that answers the question accurately.

RULES:
- Generate ONLY a SELECT or WITH/SELECT query. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
- Use standard PostgreSQL syntax (double quotes for identifiers if needed).
- For date grouping use TO_CHAR(date_col, 'YYYY-MM') or DATE_TRUNC.
- Always alias computed columns with descriptive names.
- Limit results to 500 rows maximum.
- If the question cannot be answered from the schema, set "error" to a clear explanation.

DATABASE SCHEMA (PostgreSQL):
{schema}

Respond ONLY with valid JSON (no markdown fences):
{{
  "thinking": "Brief reasoning about which tables/columns to use",
  "sql": "SELECT ...",
  "error": null
}}"""

_CHART_SYSTEM = """You are a data visualization expert. Given a user question, 
data column names, and a sample of result rows, design the best chart configurations
to answer the question visually.

CHART TYPES:
- "bar"     – comparisons across categories
- "line"    – trends over time
- "pie"     – parts of a whole (use only for ≤ 8 categories)
- "area"    – volume over time
- "scatter" – correlation between two numeric variables
- "table"   – detailed row-level data
- "metric"  – single KPI number

RULES:
- Return 1–3 chart objects appropriate for the data.
- For metric charts, use: {{ "title":..., "chart_type":"metric", "sql":"...", 
  "value_column":"col", "label":"...", "prefix":"", "suffix":"", "insight":"..." }}
- Keep insight to one actionable sentence.

Respond ONLY with valid JSON (no markdown fences):
{{
  "thinking": "Why these chart types suit the data",
  "charts": [
    {{
      "title": "...",
      "chart_type": "bar|line|pie|area|scatter|table|metric",
      "sql": "...",
      "x_axis": "column_name",
      "y_axis": ["column_name"],
      "x_label": "Human Label",
      "y_label": "Human Label",
      "color_by": null,
      "highlight": null,
      "insight": "One-sentence insight."
    }}
  ],
  "summary": "2–3 sentence natural language answer to the user's question.",
  "assumptions": []
}}"""

_FOLLOWUP_SYSTEM = """You are a BI assistant continuing a data conversation.

Previous query: {previous_query}
Previous SQL (PostgreSQL): {previous_sql}
Current user request: {followup}

DATABASE SCHEMA (PostgreSQL):
{schema}

Modify or extend the previous SQL to address the new request. Keep the same JSON format.
Respond ONLY with valid JSON (no markdown fences):
{{
  "thinking": "...",
  "charts": [...],
  "summary": "...",
  "assumptions": [],
  "error": null
}}"""


# ── Public API: SQL generation ─────────────────────────────────────────────────

async def generate_sql(query: str, schema: str) -> dict:
    """Generate a PostgreSQL SELECT query for *query* given *schema*.
    
    Returns: {"thinking": ..., "sql": ..., "error": ...}
    """
    system = _SQL_SYSTEM.format(schema=schema)
    model = _pick_model(_SQL_MODEL_CHAIN, OLLAMA_SQL_MODEL)

    if model:
        try:
            raw = await _call_ollama_async(model, system, f"User question: {query}")
            result = _extract_json(raw)
            result.setdefault("error", None)
            return result
        except Exception as exc:
            # Ollama failed – fall back to Gemini
            pass

    # Gemini fallback
    return await _gemini_generate_sql(query, schema)


# ── Public API: chart config generation ───────────────────────────────────────

async def generate_charts(
    query: str,
    schema: str,
    sql: str,
    result_columns: list[str],
    sample_rows: list[dict],
    conversation_history: list[dict] | None = None,
) -> dict:
    """Generate chart configurations from SQL results.
    
    Returns: {"thinking": ..., "charts": [...], "summary": ..., "assumptions": [...], "error": ...}
    """
    sample_preview = json.dumps(sample_rows[:5], default=str, indent=2)
    user_msg = (
        f"User question: {query}\n\n"
        f"SQL executed:\n{sql}\n\n"
        f"Result columns: {result_columns}\n\n"
        f"Sample rows (first 5):\n{sample_preview}\n\n"
        f"Design the best charts to answer this question."
    )

    system = _CHART_SYSTEM
    model = _pick_model(_VIZ_MODEL_CHAIN, OLLAMA_VIZ_MODEL)

    if model:
        try:
            raw = await _call_ollama_async(model, system, user_msg)
            result = _extract_json(raw)
            # Patch each chart's SQL to use the actual executed SQL
            for chart in result.get("charts", []):
                if not chart.get("sql"):
                    chart["sql"] = sql
            result.setdefault("error", None)
            return result
        except Exception:
            pass

    # Gemini fallback
    return await _gemini_generate_charts(query, schema, sql, result_columns, sample_rows)


# ── Public API: follow-up ──────────────────────────────────────────────────────

async def generate_followup_sql(
    followup: str,
    previous_query: str,
    previous_sql: str,
    schema: str,
) -> dict:
    """Generate SQL for a follow-up question.

    Returns: {"thinking": ..., "charts": [...], "summary": ..., "assumptions": [...], "error": ...}
    """
    system = _FOLLOWUP_SYSTEM.format(
        previous_query=previous_query,
        previous_sql=previous_sql,
        followup=followup,
        schema=schema,
    )
    model = _pick_model(_SQL_MODEL_CHAIN, OLLAMA_SQL_MODEL)

    if model:
        try:
            raw = await _call_ollama_async(model, system, f"Follow-up: {followup}")
            result = _extract_json(raw)
            result.setdefault("error", None)
            return result
        except Exception:
            pass

    return await _gemini_followup(followup, previous_query, previous_sql, schema)


# ── Gemini fallback implementations ───────────────────────────────────────────

def _get_gemini_client():
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("Neither Ollama nor GEMINI_API_KEY is available.")
    return genai.Client(api_key=api_key)


async def _gemini_generate_sql(query: str, schema: str) -> dict:
    """Use Gemini to generate SQL when Ollama is unavailable."""
    from google import genai
    client = _get_gemini_client()
    prompt = (
        f"Database schema (PostgreSQL):\n{schema}\n\n"
        f"Generate a PostgreSQL SELECT query for: {query}\n\n"
        "Respond ONLY with JSON: {\"thinking\":\"...\",\"sql\":\"SELECT...\",\"error\":null}"
    )
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[genai.types.Content(role="user", parts=[genai.types.Part(text=prompt)])],
        config=genai.types.GenerateContentConfig(temperature=0.1, max_output_tokens=2048),
    )
    try:
        return _extract_json(resp.text)
    except Exception:
        return {"thinking": "", "sql": "", "error": "Failed to parse LLM response."}


async def _gemini_generate_charts(
    query: str, schema: str, sql: str,
    result_columns: list[str], sample_rows: list[dict],
) -> dict:
    """Use Gemini to generate chart configs when Ollama is unavailable.
    Delegates to the original llm.py generate_dashboard which already uses Gemini."""
    from llm import generate_dashboard
    result = await generate_dashboard(query, schema, [])
    return result


async def _gemini_followup(
    followup: str, previous_query: str, previous_sql: str, schema: str
) -> dict:
    from llm import generate_followup
    return await generate_followup(followup, previous_query, previous_sql, schema)
