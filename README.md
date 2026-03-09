# InsightAI — Conversational BI Dashboard

> Generate interactive business intelligence dashboards using plain English. No SQL or technical skills required.

![InsightAI](https://img.shields.io/badge/Powered_by-Google_Gemini-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## Overview

InsightAI is a conversational AI system that allows non-technical users (CXOs, managers, analysts) to generate fully functional, interactive data dashboards using only natural language prompts. Simply type a question like *"Show me monthly sales revenue for Q3 broken down by region"* and get charts instantly.

### Key Features

- **Natural Language to Dashboard**: Type any business question and get interactive charts in real-time
- **Smart Chart Selection**: Automatically picks the best visualization (bar, line, pie, area, scatter, table, KPI metric)
- **Follow-up Conversations**: Refine your dashboards by chatting — "Now filter to East region only"
- **CSV Upload**: Upload your own CSV file and start querying immediately — no setup required
- **Interactive Charts**: Hover tooltips, sortable tables, pagination, zoom
- **SQL Transparency**: View the generated SQL for every chart (expandable)
- **Hallucination Handling**: Reports when it can't answer rather than fabricating data
- **Error Recovery**: Gracefully handles ambiguous or complex prompts with assumptions shown

### Architecture

```
User (Natural Language) → Next.js Frontend → FastAPI Backend → Gemini LLM
                                                    ↓
                                              SQLite Database
                                                    ↓
                                            JSON Chart Config
                                                    ↓
                                         Recharts Interactive Dashboard
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Backend | Python FastAPI |
| LLM | Google Gemini 2.0 Flash |
| Database | SQLite |
| File Upload | react-dropzone |

## Getting Started

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **Google Gemini API Key** — get one free at [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd GfG-Hackthon
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the `backend/` folder:

```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

Start the backend server:

```bash
python main.py
```

The API will be available at `http://localhost:8000`.

### 3. Frontend Setup

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:3000`.

## Usage

### Default Dataset

The app comes with a pre-loaded business dataset containing:
- **Sales** (2,000 records): dates, products, customers, regions, channels, revenue
- **Customers** (200 records): names, regions, segments, signup dates
- **Products** (25 items): categories, prices, costs
- **Expenses** (500 records): departments, categories, amounts
- **Employees** (75 records): departments, roles, performance scores, targets

### Example Queries

**Simple:**
> "What is the total revenue for 2024?"

**Medium:**
> "Show me monthly sales revenue broken down by region as a line chart"

**Complex:**
> "Compare the top 5 product categories by revenue, show the sales channel mix for each, and highlight which category has the highest profit margin"

**Follow-up:**
> "Now filter this to only show the North and East regions"

### Upload Your Own Data

1. Click the upload area in the sidebar
2. Drag & drop (or browse) any CSV file up to 50MB
3. Start asking questions immediately — the system auto-detects columns and types

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | Get database schema |
| GET | `/api/suggestions` | Get query suggestions |
| POST | `/api/query` | Convert NL to dashboard |
| POST | `/api/followup` | Refine previous query |
| POST | `/api/upload` | Upload CSV file |

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI application & routes
│   ├── database.py          # SQLite operations, schema, CSV import
│   ├── llm.py               # Gemini integration & prompt engineering
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # API key template
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx   # Root layout
│   │   │   ├── page.tsx     # Main page (orchestrator)
│   │   │   └── globals.css  # Global styles & animations
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx   # Chat UI with messages
│   │   │   ├── ChartRenderer.tsx   # All chart types (Recharts)
│   │   │   ├── Dashboard.tsx       # Dashboard grid layout
│   │   │   └── FileUpload.tsx      # CSV drag-and-drop upload
│   │   └── lib/
│   │       └── api.ts       # API client functions
│   ├── package.json
│   ├── tailwind.config.js
│   └── next.config.js       # Proxy /api to backend
│
└── README.md
```

## Evaluation Criteria Addressed

### Accuracy (40 pts)
- **Data Retrieval**: Gemini generates precise SQLite queries with proper joins, aggregation, and date functions
- **Chart Selection**: System prompt instructs contextual chart type selection (line for trends, pie for proportions, etc.)
- **Error Handling**: Validates SQL before execution, catches ambiguous queries, shows assumptions

### Aesthetics & UX (30 pts)
- **Design**: Dark theme, modern glassmorphism, smooth animations, consistent typography
- **Interactivity**: Hover tooltips on all charts, sortable/paginated tables, expandable SQL
- **User Flow**: Intuitive split-panel layout, loading states with skeleton animations, suggestion chips

### Approach & Innovation (30 pts)
- **Architecture**: Clean pipeline from text → LLM → SQL → Data → Charts with session management
- **Prompt Engineering**: Detailed system prompt with schema injection (RAG-like), chart type rules, output format enforcement
- **Hallucination Handling**: Read-only SQL enforcement, data-not-found reporting, assumption transparency

### Bonus Points
- **Follow-up Questions** (+10): Chat with the dashboard to filter and refine charts
- **Data Format Agnostic** (+20): Upload any CSV file and query it instantly with auto type inference

## License

MIT
