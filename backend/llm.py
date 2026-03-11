"""Google Gemini LLM integration for natural language to SQL and chart configuration."""

import json
import os
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()

_client = None
MODEL_NAME = "gemini-2.0-flash"


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Create a backend/.env file with your key."
            )
        _client = genai.Client(api_key=api_key)
    return _client

SYSTEM_PROMPT = """You are an expert Business Intelligence assistant that converts natural language questions into SQL queries and chart configurations.

You have access to a SQLite database. The user will ask business questions in plain English. Your job is to:
1. Write a correct SQLite SQL query to answer the question.
2. Choose the most appropriate chart type(s) based on the data.
3. Configure the chart axes, labels, and visual properties.

CRITICAL RULES:
- You may ONLY query tables and columns that exist in the DATABASE SCHEMA below. NEVER invent tables or columns.
- ONLY generate SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP, or any data-modifying statement.
- Use proper SQLite syntax (e.g., strftime for date functions).
- For date grouping by month, use strftime('%Y-%m', date_column) and alias it clearly.
- Always alias computed columns with readable names.
- NEVER use hardcoded/fabricated values in SELECT that are not derived from actual table data.
- NEVER hallucinate or assume data patterns — base your insights and summaries strictly on actual query results.
- If the question is about topics NOT present in the database (e.g. weather, general knowledge, coding, personal questions, politics, sports, entertainment, or anything unrelated to the schema), set "error" to: "This question is not related to the available dataset. Please ask a question related to the data shown in the database."
- Choose chart types wisely:
  - "bar" for comparisons across categories
  - "line" for time-series / trends
  - "pie" for parts of a whole (max 8 slices)
  - "area" for volume over time
  - "scatter" for correlation between two variables
  - "table" for detailed data listings
  - "metric" for single KPI values (e.g., total revenue)
- You may return MULTIPLE charts for a single query if the question warrants it.
- If the question is ambiguous, make reasonable assumptions and note them.
- If the question CANNOT be answered from the available tables, set "error" field explaining what data is missing.

DATABASE SCHEMA:
{schema}

Respond ONLY with valid JSON in this exact format (no markdown, no code fences):
{{
  "thinking": "Brief explanation of your interpretation and approach",
  "charts": [
    {{
      "title": "Chart Title",
      "chart_type": "bar|line|pie|area|scatter|table|metric",
      "sql": "SELECT ... FROM ...",
      "x_axis": "column_name_for_x",
      "y_axis": ["column_name_for_y"],
      "x_label": "Human Readable X Label",
      "y_label": "Human Readable Y Label",
      "color_by": "optional_column_for_color_grouping_or_null",
      "highlight": "optional_description_of_what_to_highlight_or_null",
      "insight": "A one-sentence business insight about what this chart shows"
    }}
  ],
  "summary": "A brief natural language summary answering the user's question",
  "assumptions": ["Any assumptions made if query was ambiguous"],
  "error": null
}}

For "metric" type charts, use this format:
{{
  "title": "Metric Title",
  "chart_type": "metric",
  "sql": "SELECT value as metric_value, label as metric_label FROM ...",
  "value_column": "metric_value",
  "label": "Total Revenue",
  "prefix": "$",
  "suffix": "",
  "insight": "Insight text"
}}
"""

FOLLOWUP_PROMPT = """You are continuing a conversation about a business dashboard. The user wants to modify or refine the previous analysis.

Previous query: {previous_query}
Previous SQL: {previous_sql}

The user now says: {followup}

CRITICAL RULES:
- You may ONLY query tables and columns that exist in the DATABASE SCHEMA below. NEVER invent tables or columns.
- NEVER hallucinate data or trends — base everything on actual query results.
- If the follow-up question is about topics NOT present in the database, set "error" to: "This question is not related to the available dataset. Please ask a question related to the data."
- Generate new chart configurations based on this follow-up request. Apply filters, change groupings, or modify the visualization as requested.

DATABASE SCHEMA:
{schema}

Respond ONLY with valid JSON (no markdown, no code fences) in the same format as before.
"""


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences and extract JSON from LLM response."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ``
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


async def generate_dashboard(query: str, schema: str, conversation_history: list[dict] | None = None) -> dict:
    """Use Gemini to convert a natural language query into SQL + chart configs."""
    system = SYSTEM_PROMPT.format(schema=schema.replace('{', '{{').replace('}', '}}'))

    # Build conversation contents
    contents = []

    if conversation_history:
        for entry in conversation_history[-3:]:
            if entry.get("query"):
                contents.append(genai.types.Content(role="user", parts=[genai.types.Part(text=entry["query"])]))
            if entry.get("response_summary"):
                contents.append(genai.types.Content(role="model", parts=[genai.types.Part(text=entry["response_summary"])]))

    contents.append(genai.types.Content(role="user", parts=[genai.types.Part(text="User question: " + query)]))

    response = _get_client().models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.1,
            max_output_tokens=4096,
        ),
    )

    raw = response.text
    cleaned = _clean_json_response(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                result = {
                    "error": "Failed to parse LLM response. Please try rephrasing your question.",
                    "raw_response": raw[:500],
                    "charts": [],
                    "summary": "",
                }
        else:
            result = {
                "error": "Failed to parse LLM response. Please try rephrasing your question.",
                "raw_response": raw[:500],
                "charts": [],
                "summary": "",
            }

    return result


async def generate_followup(
    followup: str, previous_query: str, previous_sql: str, schema: str
) -> dict:
    """Handle follow-up questions that refine or filter previous results."""
    prompt = FOLLOWUP_PROMPT.format(
        previous_query=previous_query.replace('{', '{{').replace('}', '}}'),
        previous_sql=previous_sql.replace('{', '{{').replace('}', '}}'),
        followup=followup.replace('{', '{{').replace('}', '}}'),
        schema=schema.replace('{', '{{').replace('}', '}}'),
    )

    response = _get_client().models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4096,
        ),
    )

    raw = response.text
    cleaned = _clean_json_response(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                result = {
                    "error": "Failed to parse follow-up response.",
                    "charts": [],
                    "summary": "",
                }
        else:
            result = {
                "error": "Failed to parse follow-up response.",
                "charts": [],
                "summary": "",
            }

    return result
