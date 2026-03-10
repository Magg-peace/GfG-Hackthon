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
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))

# Override individual models via env vars
OLLAMA_SQL_MODEL = os.getenv("OLLAMA_SQL_MODEL", "")
OLLAMA_VIZ_MODEL = os.getenv("OLLAMA_VIZ_MODEL", "")

_SQL_MODEL_CHAIN = [
    # DeepSeek-V3 – gold standard for Text-to-SQL in 2026
    "deepseek-v3", "deepseek-v3:latest",
    # DeepSeek Coder (any size)
    "deepseek-coder:33b", "deepseek-coder:6.7b", "deepseek-coder:latest",
    # Qwen3 MoE – fast coding / SQL
    "qwen3:235b", "qwen3:32b", "qwen3:14b", "qwen3:8b", "qwen3:latest",
    "qwen2.5-coder:32b", "qwen2.5-coder:7b", "qwen2.5-coder:latest",
    # Llama 4 / Gemma 3 (lightweight local fallback)
    "llama4:8b", "llama4:latest",
    "gemma3:12b", "gemma3:9b", "gemma3:latest",
    "llama3.2:latest", "llama3:latest",
    "mistral:latest", "codellama:latest",
]
_VIZ_MODEL_CHAIN = [
    # Qwen3 – excellent at generating clean Python/chart code
    "qwen3:235b", "qwen3:32b", "qwen3:14b", "qwen3:8b", "qwen3:latest",
    "qwen2.5-coder:32b", "qwen2.5-coder:latest",
    "deepseek-v3", "deepseek-v3:latest",
    "deepseek-coder:latest",
    "llama4:8b", "llama4:latest",
    "gemma3:12b", "gemma3:latest",
    "llama3.2:latest", "llama3:latest",
    "mistral:latest",
]

_available_models: list[str] | None = None
_models_fetched_at: float = 0.0


# ── Model discovery ────────────────────────────────────────────────────────────

def get_available_models() -> list[str]:
    """Fetch installed model names from Ollama (cached for 60s after success)."""
    global _available_models, _models_fetched_at
    import time
    now = time.time()
    # Re-fetch if cache is empty or older than 60 seconds
    if _available_models is not None and (now - _models_fetched_at) < 60:
        return _available_models
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        data = r.json()
        _available_models = [m["name"] for m in data.get("models", [])]
        _models_fetched_at = now
        return _available_models
    except Exception:
        _available_models = None  # Don't cache failures so next call retries
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

_SQL_SYSTEM = """You are an expert SQL analyst. Given a {dialect} database schema and a user question,
generate a single {dialect} SELECT query that answers the question accurately.

RULES:
- Generate ONLY a SELECT or WITH/SELECT query. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
- Use standard {dialect} syntax.
- If {dialect} is PostgreSQL, use double-quoted identifiers and TO_CHAR / DATE_TRUNC for dates.
- If {dialect} is SQLite, use double-quoted identifiers and strftime for dates. Do NOT use TO_CHAR or DATE_TRUNC.
- Always alias computed columns with descriptive names.
- Limit results to 500 rows maximum.
- If the question cannot be answered from the schema, set "error" to a clear explanation.

DATABASE SCHEMA ({dialect}):
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

_EXPLAIN_SYSTEM = """You are a data analyst. Given a database schema and sample rows from a dataset,
provide a clear, friendly explanation of what the data is about — suitable for a business user who
has just uploaded the file and wants to understand it before asking questions.

Respond ONLY with valid JSON (no markdown fences):
{{
  "title": "Short descriptive name for this dataset (e.g. 'India Life Insurance Claims 2015–2022')",
  "description": "2–4 sentence plain-English explanation of what this dataset tracks, the time period it covers, and who the main entities are.",
  "key_columns": [
    {{"column": "column_name", "meaning": "what this column represents"}}
  ],
  "suggested_questions": [
    "A concrete, specific question a business user could ask about this data (ready to use as-is)",
    "Another specific question",
    "Another specific question",
    "Another specific question"
  ],
  "error": null
}}

DATABASE SCHEMA:
{schema}

SAMPLE ROWS (first 5):
{sample}
"""

_FOLLOWUP_SYSTEM = """You are a BI assistant continuing a data conversation.

Previous query: {previous_query}
Previous SQL ({dialect}): {previous_sql}
Current user request: {followup}

DATABASE SCHEMA ({dialect}):
{schema}

Modify or extend the previous SQL to address the new request. Use {dialect} syntax.
Respond ONLY with valid JSON (no markdown fences):
{{
  "thinking": "...",
  "charts": [...],
  "summary": "...",
  "assumptions": [],
  "error": null
}}"""


# ── Public API: SQL generation ─────────────────────────────────────────────────

async def generate_sql(query: str, schema: str, dialect: str = "PostgreSQL") -> dict:
    """Generate a SELECT query for *query* given *schema*.
    
    Returns: {"thinking": ..., "sql": ..., "error": ...}
    """
    system = _SQL_SYSTEM.format(schema=schema, dialect=dialect)
    model = _pick_model(_SQL_MODEL_CHAIN, OLLAMA_SQL_MODEL)

    if model:
        try:
            raw = await _call_ollama_async(model, system, f"User question: {query}")
            try:
                result = _extract_json(raw)
                result.setdefault("error", None)
                return result
            except (json.JSONDecodeError, ValueError):
                # LLM returned non-JSON — retry once with a stricter prompt
                raw2 = await _call_ollama_async(
                    model, system,
                    f"User question: {query}\n\nIMPORTANT: You MUST respond with ONLY valid JSON. No explanations, no markdown."
                )
                try:
                    result = _extract_json(raw2)
                    result.setdefault("error", None)
                    return result
                except (json.JSONDecodeError, ValueError):
                    return {"thinking": "", "sql": "", "error": f"The local LLM ({model}) did not return valid JSON. Try a different question or run 'ollama pull qwen2.5-coder' for a better model."}
        except Exception as exc:
            # Ollama connection/timeout failure – fall back to Gemini
            print(f"[WARN] Ollama call failed ({model}): {exc}")

    # Gemini fallback
    try:
        return await _gemini_generate_sql(query, schema, dialect)
    except Exception as exc:
        return {"thinking": "", "sql": "", "error": f"No LLM available. Ollama {'returned an error' if model else 'has no matching models'} and Gemini is not configured. Please ensure Ollama is running or set GEMINI_API_KEY in backend/.env. Detail: {exc}"}


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
            try:
                result = _extract_json(raw)
            except (json.JSONDecodeError, ValueError):
                # Retry once with stricter instruction
                raw2 = await _call_ollama_async(
                    model, system,
                    user_msg + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no explanations."
                )
                result = _extract_json(raw2)
            # Patch each chart's SQL to use the actual executed SQL
            for chart in result.get("charts", []):
                if not chart.get("sql"):
                    chart["sql"] = sql
            result.setdefault("error", None)
            return result
        except (json.JSONDecodeError, ValueError):
            print(f"[WARN] Chart generation: LLM ({model}) returned non-JSON twice")
        except Exception as exc:
            print(f"[WARN] Ollama chart call failed ({model}): {exc}")

    # Gemini fallback
    try:
        return await _gemini_generate_charts(query, schema, sql, result_columns, sample_rows)
    except Exception as exc:
        return {"thinking": "", "charts": [], "summary": "", "assumptions": [], "error": f"No LLM available for chart generation. Detail: {exc}"}


# ── Public API: follow-up ──────────────────────────────────────────────────────

async def generate_followup_sql(
    followup: str,
    previous_query: str,
    previous_sql: str,
    schema: str,
    dialect: str = "PostgreSQL",
) -> dict:
    """Generate SQL for a follow-up question.

    Returns: {"thinking": ..., "charts": [...], "summary": ..., "assumptions": [...], "error": ...}
    """
    system = _FOLLOWUP_SYSTEM.format(
        previous_query=previous_query,
        previous_sql=previous_sql,
        followup=followup,
        schema=schema,
        dialect=dialect,
    )
    model = _pick_model(_SQL_MODEL_CHAIN, OLLAMA_SQL_MODEL)

    if model:
        try:
            raw = await _call_ollama_async(model, system, f"Follow-up: {followup}")
            try:
                result = _extract_json(raw)
            except (json.JSONDecodeError, ValueError):
                raw2 = await _call_ollama_async(
                    model, system,
                    f"Follow-up: {followup}\n\nIMPORTANT: Respond ONLY with valid JSON."
                )
                result = _extract_json(raw2)
            result.setdefault("error", None)
            return result
        except (json.JSONDecodeError, ValueError):
            print(f"[WARN] Followup: LLM ({model}) returned non-JSON twice")
        except Exception as exc:
            print(f"[WARN] Ollama followup call failed ({model}): {exc}")

    try:
        return await _gemini_followup(followup, previous_query, previous_sql, schema)
    except Exception as exc:
        return {"thinking": "", "charts": [], "summary": "", "assumptions": [], "error": f"No LLM available. Detail: {exc}"}


# ── Gemini fallback implementations ───────────────────────────────────────────

def _get_gemini_client():
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("Neither Ollama nor GEMINI_API_KEY is available.")
    return genai.Client(api_key=api_key)


async def _gemini_generate_sql(query: str, schema: str, dialect: str = "PostgreSQL") -> dict:
    """Use Gemini to generate SQL when Ollama is unavailable."""
    from google import genai
    client = _get_gemini_client()
    prompt = (
        f"Database schema ({dialect}):\n{schema}\n\n"
        f"Generate a {dialect} SELECT query for: {query}\n\n"
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


def _wrap_plain_text_as_explain(raw: str, schema: str) -> dict:
    """When the LLM returns plain text instead of JSON, build a valid explain response."""
    import re as _re
    table_match = _re.search(r'Table:\s*(\S+)', schema)
    title = table_match.group(1).replace('_', ' ').title() if table_match else "Uploaded Dataset"
    tbl_name = table_match.group(1) if table_match else "data"

    # Build useful suggested questions from the schema columns
    cols = _re.findall(r'Columns:\s*(.+)', schema)
    col_names = []
    if cols:
        col_names = [c.strip().split('(')[0].strip() for c in cols[0].split(',')][:10]

    suggestions = []
    readable_tbl = tbl_name.replace('_', ' ')
    if col_names:
        numeric_cols = [c for c in col_names if any(k in c.lower() for k in ('amt', 'no', 'ratio', 'count', 'total', 'amount', 'price', 'revenue', 'score'))]
        cat_cols = [c for c in col_names if any(k in c.lower() for k in ('name', 'insurer', 'category', 'region', 'type', 'dept', 'channel'))]
        time_cols = [c for c in col_names if any(k in c.lower() for k in ('date', 'year', 'month', 'time'))]

        if cat_cols and numeric_cols:
            suggestions.append(f"Show {numeric_cols[0].replace('_',' ')} by {cat_cols[0].replace('_',' ')} as a bar chart")
        if time_cols and numeric_cols:
            suggestions.append(f"Show the trend of {numeric_cols[0].replace('_',' ')} over {time_cols[0].replace('_',' ')}")
        if cat_cols:
            suggestions.append(f"Which {cat_cols[0].replace('_',' ')} has the highest values? Show top 10")
        suggestions.append(f"Show a summary overview of {readable_tbl}")
        if len(numeric_cols) >= 2:
            suggestions.append(f"Compare {numeric_cols[0].replace('_',' ')} vs {numeric_cols[1].replace('_',' ')} as a scatter chart")

    return {
        "title": title,
        "description": raw.strip()[:600],
        "key_columns": [],
        "suggested_questions": suggestions[:5],
        "error": None,
    }


async def explain_dataset(schema: str, sample_rows: list[dict]) -> dict:
    """Explain what a dataset is about using the schema and sample rows.

    Returns: {"title": ..., "description": ..., "key_columns": [...], "suggested_questions": [...], "error": ...}
    """
    sample_preview = json.dumps(sample_rows[:5], default=str, indent=2)
    system = _EXPLAIN_SYSTEM.format(schema=schema, sample=sample_preview)
    model = _pick_model(_VIZ_MODEL_CHAIN, OLLAMA_VIZ_MODEL)

    if model:
        try:
            raw = await _call_ollama_async(model, system, "Explain this dataset.")
            try:
                result = _extract_json(raw)
            except (json.JSONDecodeError, ValueError):
                # LLM returned plain text instead of JSON — wrap it
                result = _wrap_plain_text_as_explain(raw, schema)
            result.setdefault("error", None)
            return result
        except Exception:
            pass

    # Gemini fallback
    try:
        return await _gemini_explain_dataset(schema, sample_rows)
    except Exception as exc:
        # Last-resort: build a basic response from the schema itself
        return _wrap_plain_text_as_explain(
            _build_schema_summary(schema, sample_rows), schema
        )


def _build_schema_summary(schema: str, sample_rows: list[dict]) -> str:
    """Build a plain description from the schema text when all LLMs fail."""
    import re as _re
    tables = _re.findall(r'Table:\s*(\S+)\s*\((\d+) rows\)', schema)
    if not tables:
        return "A dataset has been loaded. You can ask me to visualise any aspect of it."
    parts = []
    for tname, count in tables:
        readable = tname.replace('_', ' ').title()
        parts.append(f"{readable} ({count} rows)")
    cols = _re.findall(r'Columns:\s*(.+)', schema)
    col_list = cols[0].split(',')[:6] if cols else []
    col_names = [c.strip().split('(')[0].strip().replace('_', ' ') for c in col_list]
    desc = f"This dataset contains: {', '.join(parts)}. "
    if col_names:
        desc += f"Key fields include: {', '.join(col_names)}. "
    desc += "Ask me what you'd like to visualise!"
    return desc


async def _gemini_explain_dataset(schema: str, sample_rows: list[dict]) -> dict:
    from google import genai
    client = _get_gemini_client()
    sample_preview = json.dumps(sample_rows[:5], default=str, indent=2)
    prompt = _EXPLAIN_SYSTEM.format(schema=schema, sample=sample_preview) + "\n\nExplain this dataset."
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[genai.types.Content(role="user", parts=[genai.types.Part(text=prompt)])],
        config=genai.types.GenerateContentConfig(temperature=0.1, max_output_tokens=2048),
    )
    try:
        return _extract_json(resp.text)
    except Exception:
        return {"title": "Uploaded Dataset", "description": "Dataset loaded.", "key_columns": [], "suggested_questions": [], "error": None}
