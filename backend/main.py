"""FastAPI backend for the Conversational BI Dashboard."""

import uuid
import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    get_schema,
    execute_query,
    import_csv,
    seed_sample_data,
)
from llm import generate_dashboard, generate_followup

# Seed sample data on startup
seed_sample_data()

app = FastAPI(title="BI Dashboard API", version="1.0.0")

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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/schema")
def get_db_schema(session_id: str | None = None):
    """Return the database schema for the current session."""
    try:
        schema = get_schema(session_id)
        return {"schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query")
async def query_dashboard(req: QueryRequest):
    """Convert natural language to a dashboard with charts."""
    try:
        session_id = req.session_id
        schema = get_schema(session_id)

        if not schema.strip():
            raise HTTPException(
                status_code=400,
                detail="No data available. Please upload a CSV file or use the default dataset.",
            )

        # Get conversation history for context
        history = []
        if session_id and session_id in sessions:
            history = sessions[session_id].get("history", [])

        # Generate dashboard config from LLM
        llm_result = await generate_dashboard(req.query, schema, history)

        if llm_result.get("error"):
            return {
                "success": False,
                "error": llm_result["error"],
                "summary": llm_result.get("summary", ""),
                "charts": [],
            }

        # Execute each chart's SQL and attach data
        charts_with_data = []
        for chart_config in llm_result.get("charts", []):
            sql = chart_config.get("sql", "")
            try:
                data = execute_query(sql, session_id)
                chart_config["data"] = data
                chart_config["sql_executed"] = sql
                chart_config["row_count"] = len(data)
                charts_with_data.append(chart_config)
            except Exception as e:
                chart_config["data"] = []
                chart_config["error"] = f"SQL Error: {str(e)}"
                chart_config["sql_executed"] = sql
                charts_with_data.append(chart_config)

        # Store in conversation history
        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in sessions:
            sessions[session_id] = {"history": []}

        sessions[session_id]["history"].append({
            "query": req.query,
            "response_summary": llm_result.get("summary", ""),
            "sql": [c.get("sql", "") for c in charts_with_data],
        })

        return {
            "success": True,
            "session_id": session_id,
            "summary": llm_result.get("summary", ""),
            "thinking": llm_result.get("thinking", ""),
            "assumptions": llm_result.get("assumptions", []),
            "charts": charts_with_data,
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
        llm_result = await generate_followup(
            req.query, req.previous_query, req.previous_sql, schema
        )

        if llm_result.get("error"):
            return {
                "success": False,
                "error": llm_result["error"],
                "summary": llm_result.get("summary", ""),
                "charts": [],
            }

        charts_with_data = []
        for chart_config in llm_result.get("charts", []):
            sql = chart_config.get("sql", "")
            try:
                data = execute_query(sql, req.session_id)
                chart_config["data"] = data
                chart_config["sql_executed"] = sql
                chart_config["row_count"] = len(data)
                charts_with_data.append(chart_config)
            except Exception as e:
                chart_config["data"] = []
                chart_config["error"] = f"SQL Error: {str(e)}"
                chart_config["sql_executed"] = sql
                charts_with_data.append(chart_config)

        # Update conversation history
        if req.session_id in sessions:
            sessions[req.session_id]["history"].append({
                "query": req.query,
                "response_summary": llm_result.get("summary", ""),
                "sql": [c.get("sql", "") for c in charts_with_data],
            })

        return {
            "success": True,
            "session_id": req.session_id,
            "summary": llm_result.get("summary", ""),
            "thinking": llm_result.get("thinking", ""),
            "assumptions": llm_result.get("assumptions", []),
            "charts": charts_with_data,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file and create a new session database."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be under 50MB.")

    try:
        content = await file.read()
        session_id = str(uuid.uuid4())
        result = import_csv(content, file.filename, session_id)

        sessions[session_id] = {"history": [], "uploaded_file": file.filename}

        schema = get_schema(session_id)

        return {
            "success": True,
            "session_id": session_id,
            "filename": file.filename,
            "table_name": result["table_name"],
            "columns": result["columns"],
            "row_count": result["row_count"],
            "schema": schema,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/suggestions")
def get_suggestions(session_id: str | None = None):
    """Return suggested queries based on the current schema."""
    try:
        schema = get_schema(session_id)
        if "sales" in schema.lower():
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
            return {
                "suggestions": [
                    "Show me an overview of the data",
                    "What are the top values in each column?",
                    "Show the distribution of numeric values",
                    "Show trends over time if there are date columns",
                ]
            }
    except Exception:
        return {"suggestions": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
