"""FastAPI backend for the Conversational BI Dashboard.

Data flow:
  CSV upload → PostgreSQL (or SQLite fallback) table
  User query  → LangGraph agent (Ollama/Gemini SQL gen → PG execute → results table → charts)
  Export      → PDF (fpdf2 + matplotlib) or Excel (openpyxl)
"""

import io
import re
import uuid
import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import (
    get_schema as sqlite_get_schema,
    execute_query as sqlite_execute_query,
    import_csv as sqlite_import_csv,
    seed_sample_data,
    load_insurance_dataset,
)
from agents import run_query_pipeline, run_followup_pipeline
from export import export_to_pdf, export_to_excel

try:
    from pg_database import (
        is_available as pg_available,
        import_csv_to_pg,
        get_pg_schema,
        execute_pg_query,
        store_query_results,
        get_results_tables,
        seed_pg_sample_data,
    )
    _PG_MODULE_OK = True
except ImportError:
    _PG_MODULE_OK = False


def _use_postgres() -> bool:
    return _PG_MODULE_OK and pg_available()


def get_schema(session_id: str | None = None) -> str:
    if _use_postgres():
        return get_pg_schema(session_id)
    return sqlite_get_schema(session_id)


def execute_query(sql: str, session_id: str | None = None) -> list[dict]:
    if _use_postgres():
        return execute_pg_query(sql, session_id)
    return sqlite_execute_query(sql, session_id)


from ml_serve import (
    predict_settlement_ratio,
    classify_risk_tier,
    detect_anomalies,
    get_insurer_list,
    get_all_predictions,
)

# ── App startup ────────────────────────────────────────────────────────────────
seed_sample_data()
load_insurance_dataset()

if _PG_MODULE_OK:
    try:
        seed_pg_sample_data()
    except Exception as _pg_seed_err:
        print(f"[WARN] PostgreSQL seed failed (is PG running?): {_pg_seed_err}")

app = FastAPI(title="BI Dashboard API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store (for conversation history & uploaded data sessions)
sessions: dict[str, dict] = {}


class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None


class FollowUpRequest(BaseModel):
    query: str
    session_id: str
    previous_query: str
    previous_sql: str


class ExportRequest(BaseModel):
    session_id: str | None = None
    query: str = ""
    summary: str = ""
    charts: list[dict] = []
    format: str = "pdf"   # "pdf" or "excel"


class PredictionRequest(BaseModel):
    insurer: str
    year: int = 2024
    total_claims_no: float = 1000
    total_claims_amt: float = 500.0
    claims_repudiated_no: float = 20
    claims_rejected_no: float = 5
    claims_pending_start_no: float = 10
    claims_pending_end_no: float = 15
    claims_intimated_no: float = 1000
    claims_unclaimed_no: float = 0
    claims_paid_amt: float = 450.0


@app.get("/api/health")
def health():
    postgres_ok = _use_postgres()
    try:
        from ollama_llm import is_ollama_available
        ollama_ok = is_ollama_available()
    except Exception:
        ollama_ok = False
    return {"status": "ok", "postgres": postgres_ok, "ollama": ollama_ok}


@app.get("/api/schema")
def get_db_schema(session_id: str | None = None):
    """Return the database schema for the current session."""
    try:
        schema = get_schema(session_id)
        return {"schema": schema, "postgres": _use_postgres()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _is_explain_query(query: str) -> bool:
    """Detect if the user is asking about the dataset itself rather than requesting a visualisation."""
    q = query.lower().strip()
    explain_patterns = [
        "tell me about", "describe", "what is this", "what does this",
        "explain", "what kind of data", "what data", "about the csv",
        "about the file", "about this data", "what columns", "what fields",
        "overview of", "summary of the data", "what's in",
    ]
    return any(p in q for p in explain_patterns)


@app.post("/api/query")
async def query_dashboard(req: QueryRequest):
    """Convert a natural language question into SQL → execute → store results → return charts."""
    try:
        session_id = req.session_id
        schema = get_schema(session_id)

        if not schema.strip():
            raise HTTPException(
                status_code=400,
                detail="No data available. Please upload a CSV file or use the default dataset.",
            )

        # If the user is asking *about* the data rather than asking to visualise it,
        # route to the explain flow and return a helpful text answer.
        if _is_explain_query(req.query):
            sample: list[dict] = []
            tbl_match = re.search(r'(?:Table:\s*|CREATE TABLE\s+)"?([^\s"(]+)"?', schema, re.IGNORECASE)
            if tbl_match:
                try:
                    sample = execute_query(f'SELECT * FROM "{tbl_match.group(1)}" LIMIT 5', session_id)
                except Exception:
                    pass
            from ollama_llm import explain_dataset
            explanation = await explain_dataset(schema, sample)
            if not session_id:
                session_id = str(uuid.uuid4())
            if session_id not in sessions:
                sessions[session_id] = {"history": []}
            sessions[session_id]["history"].append({"query": req.query, "response_summary": explanation.get("description", ""), "sql": ""})

            questions = explanation.get("suggested_questions", [])
            body = f"**{explanation.get('title', 'Your Dataset')}**\n\n{explanation.get('description', '')}"
            if questions:
                body += "\n\nHere are some things you can ask me to visualise:\n" + "\n".join(f"• {q}" for q in questions)
            body += "\n\nWhat would you like to visualise?"
            return {
                "success": True,
                "session_id": session_id,
                "summary": body,
                "thinking": "",
                "assumptions": [],
                "charts": [],
                "suggested_questions": questions,
            }

        history = []
        if session_id and session_id in sessions:
            history = sessions[session_id].get("history", [])

        use_pg = _use_postgres()

        # Run the LangGraph agent pipeline
        state = await run_query_pipeline(
            query=req.query,
            schema=schema,
            session_id=session_id or "",
            use_postgres=use_pg,
            conversation_history=history,
        )

        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in sessions:
            sessions[session_id] = {"history": []}

        sessions[session_id]["history"].append({
            "query": req.query,
            "response_summary": state.get("summary", ""),
            "sql": state.get("generated_sql", ""),
        })

        if state.get("error") and not state.get("charts"):
            return {
                "success": False,
                "session_id": session_id,
                "error": state["error"],
                "summary": state.get("summary", ""),
                "charts": [],
            }

        return {
            "success": True,
            "session_id": session_id,
            "summary": state.get("summary", ""),
            "thinking": state.get("thinking", ""),
            "assumptions": state.get("assumptions", []),
            "charts": state.get("charts", []),
            "results_table": state.get("results_table_name", ""),
            "postgres": use_pg,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/followup")
async def followup_query(req: FollowUpRequest):
    """Handle follow-up questions that refine previous results."""
    try:
        schema = get_schema(req.session_id)
        use_pg = _use_postgres()

        state = await run_followup_pipeline(
            followup=req.query,
            previous_query=req.previous_query,
            previous_sql=req.previous_sql,
            schema=schema,
            session_id=req.session_id,
            use_postgres=use_pg,
        )

        if req.session_id in sessions:
            sessions[req.session_id]["history"].append({
                "query": req.query,
                "response_summary": state.get("summary", ""),
                "sql": state.get("generated_sql", ""),
            })

        if state.get("error") and not state.get("charts"):
            return {
                "success": False,
                "session_id": req.session_id,
                "error": state["error"],
                "summary": state.get("summary", ""),
                "charts": [],
            }

        return {
            "success": True,
            "session_id": req.session_id,
            "summary": state.get("summary", ""),
            "thinking": state.get("thinking", ""),
            "assumptions": state.get("assumptions", []),
            "charts": state.get("charts", []),
            "results_table": state.get("results_table_name", ""),
            "postgres": use_pg,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file and store it in PostgreSQL (or SQLite fallback)."""
    fname = file.filename or ""
    if not fname.lower().endswith((".csv", ".tsv", ".txt")):
        raise HTTPException(status_code=400, detail="Only CSV/TSV files are supported.")

    if file.size and file.size > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be under 100 MB.")

    try:
        content = await file.read()
        session_id = str(uuid.uuid4())

        if _use_postgres():
            result = import_csv_to_pg(content, fname, session_id)
        else:
            result = sqlite_import_csv(content, fname, session_id)

        sessions[session_id] = {
            "history": [],
            "uploaded_file": fname,
            "table_name": result["table_name"],
            "postgres": _use_postgres(),
        }
        schema = get_schema(session_id)
        return {
            "success": True,
            "session_id": session_id,
            "filename": fname,
            "table_name": result["table_name"],
            "columns": result["columns"],
            "row_count": result["row_count"],
            "schema": schema,
            "postgres": _use_postgres(),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/suggestions")
def get_suggestions(session_id: str | None = None):
    """Return suggested queries based on the current schema."""
    try:
        schema = get_schema(session_id)
        schema_lower = schema.lower()
        if "insurance" in schema_lower or "claims" in schema_lower:
            return {
                "suggestions": [
                    "Show me the top 10 insurers by claims settlement ratio in 2021-22",
                    "Compare claims paid vs repudiated across all insurers as a bar chart",
                    "What's the yearly trend of industry claims settlement ratio?",
                    "Which insurers have the highest rejection rates?",
                    "Show total claims volume by insurer as a pie chart",
                    "Compare the pending claims at start vs end of year for top insurers",
                    "Show monthly trend of claims intimated amounts across years",
                    "Which insurer handles the most claim amount? Show top 5",
                ]
            }
        elif "sales" in schema_lower:
            return {
                "suggestions": [
                    "Show me monthly sales revenue for 2024 broken down by region",
                    "What are the top 5 products by total revenue?",
                    "Compare sales performance across different channels",
                    "Show quarterly expenses by department",
                    "Which region has the highest average order value?",
                    "Show employee performance scores by department",
                    "What's the monthly trend of customer signups?",
                    "Break down revenue by product category with a pie chart",
                ]
            }
        else:
            suggestions = [
                "Show me a summary overview of this dataset",
                "What are the top values by the main numeric column?",
                "Show the distribution of data by category",
            ]
            if any(k in schema_lower for k in ("date", "time", "year", "month")):
                suggestions.append("Show trends over time")
            return {"suggestions": suggestions}
    except Exception:
        return {"suggestions": []}


@app.get("/api/explain")
async def explain_data(session_id: str | None = None):
    """Explain what the current dataset is about using an LLM, and suggest questions."""
    try:
        schema = get_schema(session_id)
        if not schema.strip():
            raise HTTPException(status_code=400, detail="No data available. Please upload a CSV file first.")

        # Fetch a small sample of rows for context
        sample: list[dict] = []
        # Pull the first table name from the schema text (format: "Table: <name>" or CREATE TABLE "<name>")
        tbl_match = re.search(r'(?:Table:\s*|CREATE TABLE\s+)"?([^\s"(]+)"?', schema, re.IGNORECASE)
        if tbl_match:
            tbl = tbl_match.group(1)
            try:
                sample = execute_query(f'SELECT * FROM "{tbl}" LIMIT 5', session_id)
            except Exception:
                pass

        from ollama_llm import explain_dataset
        result = await explain_dataset(schema, sample)
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Export endpoints ───────────────────────────────────────────────────────────

@app.post("/api/export")
async def export_data(req: ExportRequest):
    """Export dashboard as a PDF or Excel file with charts + filtered data."""
    fmt = req.format.lower()
    if fmt not in ("pdf", "excel", "xlsx"):
        raise HTTPException(status_code=400, detail="format must be 'pdf' or 'excel'.")
    try:
        if fmt == "pdf":
            file_bytes = export_to_pdf(
                charts=req.charts,
                summary=req.summary,
                query=req.query,
                session_id=req.session_id or "",
            )
            filename = f"bi_report_{uuid.uuid4().hex[:8]}.pdf"
            media_type = "application/pdf"
        else:
            file_bytes = export_to_excel(
                charts=req.charts,
                summary=req.summary,
                query=req.query,
                session_id=req.session_id or "",
            )
            filename = f"bi_report_{uuid.uuid4().hex[:8]}.xlsx"
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Results tables ─────────────────────────────────────────────────────────────

@app.get("/api/results/{session_id}")
def list_results_tables(session_id: str):
    """List all stored results tables for a session."""
    try:
        if _use_postgres():
            tables = get_results_tables(session_id)
        else:
            from database import get_connection
            conn = get_connection(session_id)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'results_%';")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
        return {"session_id": session_id, "results_tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results/{session_id}/{table_name}")
def get_result_rows(session_id: str, table_name: str):
    """Fetch all rows from a named results table."""
    if not re.match(r"^results_[a-z0-9_]+$", table_name):
        raise HTTPException(status_code=400, detail="Invalid table name.")
    try:
        rows = execute_query(f'SELECT * FROM "{table_name}" LIMIT 1000', session_id)
        return {"table_name": table_name, "rows": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── LLM status ─────────────────────────────────────────────────────────────────

@app.get("/api/llm/status")
def llm_status():
    try:
        from ollama_llm import get_available_models, is_ollama_available, OLLAMA_BASE_URL
        return {
            "ollama_available": is_ollama_available(),
            "ollama_url": OLLAMA_BASE_URL,
            "available_models": get_available_models(),
            "gemini_configured": bool(__import__("os").getenv("GEMINI_API_KEY")),
        }
    except Exception as e:
        return {"ollama_available": False, "error": str(e)}


# ── ML Model Endpoints ──────────────────────────────────────

@app.post("/api/ml/predict")
def ml_predict(req: PredictionRequest):
    """Predict claims settlement ratio for an insurer."""
    try:
        claims_data = {
            "total_claims_no": req.total_claims_no,
            "total_claims_amt": req.total_claims_amt,
            "claims_repudiated_no": req.claims_repudiated_no,
            "claims_rejected_no": req.claims_rejected_no,
            "claims_pending_start_no": req.claims_pending_start_no,
            "claims_pending_end_no": req.claims_pending_end_no,
            "claims_intimated_no": req.claims_intimated_no,
            "claims_unclaimed_no": req.claims_unclaimed_no,
            "claims_paid_amt": req.claims_paid_amt,
        }
        prediction = predict_settlement_ratio(req.insurer, req.year, claims_data)
        risk = classify_risk_tier(req.insurer, req.year, claims_data)
        return {
            "success": True,
            **prediction,
            "risk_classification": risk,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ml/anomalies")
def ml_anomalies():
    """Get anomalous insurer patterns."""
    try:
        return {"success": True, "anomalies": detect_anomalies()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ml/insurers")
def ml_insurers():
    """Get list of known insurers."""
    try:
        return {"success": True, "insurers": get_insurer_list()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ml/overview")
def ml_overview():
    """Get predictions overview for all insurers."""
    try:
        return {"success": True, "predictions": get_all_predictions()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
