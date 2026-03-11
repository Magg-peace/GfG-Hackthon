"""PostgreSQL database management: connection pooling, schema inspection, CSV import,
query execution, and results storage for the BI Dashboard."""

import csv
import io
import os
import re
import random
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
PG_DB = os.getenv("POSTGRES_DB", "bi_dashboard")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
            connect_timeout=5,
        )
    return _pool


def _get_conn() -> psycopg2.extensions.connection:
    return _get_pool().getconn()


def _release_conn(conn: psycopg2.extensions.connection) -> None:
    _get_pool().putconn(conn)


def is_available() -> bool:
    """Check whether PostgreSQL is reachable."""
    try:
        conn = _get_conn()
        _release_conn(conn)
        return True
    except Exception:
        return False


# ── Naming helpers ─────────────────────────────────────────────────────────────

def _session_prefix(session_id: str) -> str:
    return session_id.replace("-", "")[:12]


def _safe_identifier(name: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())
    if not safe or safe[0].isdigit():
        safe = "t_" + safe
    return safe[:48]


def make_upload_table(session_id: str, base_name: str) -> str:
    return f"upload_{_session_prefix(session_id)}_{_safe_identifier(base_name)}"


def make_results_table(session_id: str, query_index: int) -> str:
    return f"results_{_session_prefix(session_id)}_{query_index}"


# ── Type inference ─────────────────────────────────────────────────────────────

def _infer_pg_type(values: list[str]) -> str:
    if not values:
        return "TEXT"
    int_ok = float_ok = 0
    for v in values:
        v = v.strip().replace(",", "")
        try:
            int(v)
            int_ok += 1
            continue
        except ValueError:
            pass
        try:
            float(v)
            float_ok += 1
        except ValueError:
            pass
    total = len(values)
    if int_ok > total * 0.8:
        return "BIGINT"
    if (int_ok + float_ok) > total * 0.8:
        return "NUMERIC"
    return "TEXT"


# ── CSV import ─────────────────────────────────────────────────────────────────

def import_csv_to_pg(content: bytes, filename: str, session_id: str) -> dict:
    """Parse a CSV and store it as a PostgreSQL table. Returns metadata dict."""
    base = Path(filename).stem
    table_name = make_upload_table(session_id, base)

    # Try multiple encodings to handle non-UTF-8 files (e.g. Windows-1252)
    decoded = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            decoded = content.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if decoded is None:
        decoded = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(decoded))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty or invalid.")

    raw_columns = list(rows[0].keys())
    safe_columns = [_safe_identifier(c) for c in raw_columns]

    # Detect types from first 200 rows
    col_types: dict[str, str] = {}
    for i, col in enumerate(raw_columns):
        samples = [r[col] for r in rows[:200] if r.get(col) and r[col].strip()]
        col_types[safe_columns[i]] = _infer_pg_type(samples)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{table_name}";')
            col_defs = ", ".join(f'"{sc}" {ct}' for sc, ct in col_types.items())
            cur.execute(f'CREATE TABLE "{table_name}" ({col_defs});')

            for row in rows:
                safe_cols_quoted = [f'"{sc}"' for sc in safe_columns]
                placeholders = ", ".join(["%s"] * len(safe_columns))
                values = []
                for i, raw_col in enumerate(raw_columns):
                    sc = safe_columns[i]
                    ct = col_types[sc]
                    val = row.get(raw_col, "")
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        values.append(None)
                    elif ct in ("BIGINT", "NUMERIC"):
                        try:
                            clean = str(val).replace(",", "").strip()
                            values.append(int(clean) if ct == "BIGINT" else float(clean))
                        except (ValueError, TypeError):
                            values.append(None)
                    else:
                        values.append(str(val))
                cur.execute(
                    f'INSERT INTO "{table_name}" ({", ".join(safe_cols_quoted)}) VALUES ({placeholders})',
                    values,
                )

        conn.commit()
        return {
            "table_name": table_name,
            "columns": safe_columns,
            "row_count": len(rows),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_conn(conn)


# ── Schema introspection ───────────────────────────────────────────────────────

def get_pg_schema(session_id: str | None = None) -> str:
    """Return a human-readable schema string for the given session (or default tables)."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if session_id:
                prefix = _session_prefix(session_id)
                cur.execute(
                    """SELECT table_name FROM information_schema.tables
                       WHERE table_schema = 'public'
                         AND (table_name LIKE %s OR table_name LIKE %s)
                       ORDER BY table_name;""",
                    (f"upload_{prefix}%", f"results_{prefix}%"),
                )
            else:
                cur.execute(
                    """SELECT table_name FROM information_schema.tables
                       WHERE table_schema = 'public'
                         AND table_name NOT LIKE 'upload_%'
                         AND table_name NOT LIKE 'results_%'
                       ORDER BY table_name;"""
                )
            tables = [row["table_name"] for row in cur.fetchall()]
            if not tables:
                return ""

            parts = []
            for table in tables:
                cur.execute(
                    """SELECT column_name, data_type
                       FROM information_schema.columns
                       WHERE table_name = %s AND table_schema = 'public'
                       ORDER BY ordinal_position;""",
                    (table,),
                )
                cols = cur.fetchall()
                cur.execute(f'SELECT COUNT(*) AS cnt FROM "{table}";')
                count = cur.fetchone()["cnt"]

                col_str = ", ".join(f'{c["column_name"]} ({c["data_type"]})' for c in cols)

                samples = []
                for c in cols[:6]:
                    try:
                        cur.execute(
                            f'SELECT DISTINCT "{c["column_name"]}" FROM "{table}"'
                            f' WHERE "{c["column_name"]}" IS NOT NULL LIMIT 5;'
                        )
                        vals = [str(r[c["column_name"]]) for r in cur.fetchall()]
                        if vals:
                            samples.append(f'  {c["column_name"]}: [{", ".join(vals)}]')
                    except Exception:
                        pass

                parts.append(
                    f'Table: {table} ({count} rows)\n  Columns: {col_str}\n  Sample values:\n'
                    + "\n".join(samples)
                )
            return "\n\n".join(parts)
    finally:
        _release_conn(conn)


# ── Query execution ────────────────────────────────────────────────────────────

def execute_pg_query(sql: str, session_id: str | None = None) -> list[dict]:
    """Execute a read-only SQL query against PostgreSQL and return rows as dicts."""
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()

    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        raise ValueError("Only SELECT / WITH queries are allowed.")

    # Block dangerous DDL/DML keywords (check before -- comments)
    check_part = re.sub(r"--[^\n]*", "", sql_upper, flags=re.MULTILINE)
    check_part = re.sub(r"/\*.*?\*/", "", check_part, flags=re.DOTALL)
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
                 "TRUNCATE", "EXECUTE", "PERFORM", "COPY"]
    for kw in forbidden:
        if re.search(r"\b" + re.escape(kw) + r"\b", check_part):
            raise ValueError(f"Forbidden keyword in query: {kw}")

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql_stripped)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        _release_conn(conn)


# ── Results storage ────────────────────────────────────────────────────────────

def store_query_results(data: list[dict], session_id: str, query_index: int) -> str:
    """Persist query result rows into a dedicated PostgreSQL table. Returns table name."""
    if not data:
        return ""

    table_name = make_results_table(session_id, query_index)
    columns = list(data[0].keys())

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{table_name}";')
            col_defs = ", ".join(f'"{_safe_identifier(c)}" TEXT' for c in columns)
            cur.execute(f'CREATE TABLE "{table_name}" ({col_defs});')

            safe_cols = [_safe_identifier(c) for c in columns]
            quoted = [f'"{sc}"' for sc in safe_cols]
            ph = ", ".join(["%s"] * len(safe_cols))
            for row in data:
                vals = [str(row.get(c, "")) if row.get(c) is not None else None for c in columns]
                cur.execute(
                    f'INSERT INTO "{table_name}" ({", ".join(quoted)}) VALUES ({ph})',
                    vals,
                )
        conn.commit()
        return table_name
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_conn(conn)


def get_results_tables(session_id: str) -> list[str]:
    """List all results tables for a session."""
    prefix = _session_prefix(session_id)
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT table_name FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name LIKE %s
                   ORDER BY table_name;""",
                (f"results_{prefix}%",),
            )
            return [row["table_name"] for row in cur.fetchall()]
    finally:
        _release_conn(conn)


# ── Default sample data seeding ────────────────────────────────────────────────

def seed_pg_sample_data() -> None:
    """Seed default sales/insurance sample data into PostgreSQL if not present."""
    if not is_available():
        return

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='sales';"
            )
            if cur.fetchone():
                return  # Already seeded

        _seed_sales(conn)
        _seed_insurance(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_conn(conn)


def _seed_sales(conn) -> None:
    random.seed(42)
    regions = ["North", "South", "East", "West"]
    categories = {
        "Electronics": ["Laptop", "Smartphone", "Tablet", "Headphones", "Smart Watch"],
        "Clothing": ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Dress"],
        "Home & Garden": ["Sofa", "Lamp", "Plant Pot", "Cookware Set", "Rug"],
        "Sports": ["Yoga Mat", "Dumbbells", "Running Shoes", "Bicycle", "Tennis Racket"],
        "Books": ["Fiction Novel", "Tech Manual", "Cookbook", "Biography", "Self-Help"],
    }
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id BIGINT PRIMARY KEY, name TEXT, email TEXT,
                region TEXT, signup_date TEXT, customer_segment TEXT
            );""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id BIGINT PRIMARY KEY, product_name TEXT, category TEXT,
                unit_price NUMERIC, cost_price NUMERIC
            );""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                sale_id BIGINT PRIMARY KEY, sale_date TEXT, customer_id BIGINT,
                product_id BIGINT, quantity BIGINT, revenue NUMERIC,
                region TEXT, sales_channel TEXT
            );""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                expense_id BIGINT PRIMARY KEY, expense_date TEXT, category TEXT,
                amount NUMERIC, department TEXT, description TEXT
            );""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                employee_id BIGINT PRIMARY KEY, name TEXT, department TEXT,
                role TEXT, hire_date TEXT, salary NUMERIC, performance_score NUMERIC,
                region TEXT
            );""")

        first_names = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace",
                       "Henry", "Ivy", "Jack", "Karen", "Leo", "Mia", "Noah", "Olivia"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                      "Miller", "Davis", "Rodriguez", "Martinez"]
        segments = ["Enterprise", "SMB", "Startup", "Individual"]

        customers = []
        for i in range(1, 201):
            fn = random.choice(first_names)
            ln = random.choice(last_names)
            signup = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 730))
            customers.append((i, f"{fn} {ln}", f"{fn.lower()}.{ln.lower()}{i}@example.com",
                               random.choice(regions), signup.strftime("%Y-%m-%d"),
                               random.choice(segments)))
        cur.executemany("INSERT INTO customers VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;", customers)

        products = []
        pid = 1
        for cat, items in categories.items():
            for name in items:
                price = round(random.uniform(15, 1500), 2)
                products.append((pid, name, cat, price, round(price * random.uniform(0.4, 0.75), 2)))
                pid += 1
        cur.executemany("INSERT INTO products VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;", products)

        channels = ["Online", "Retail", "Partner"]
        sales = []
        for i in range(1, 2001):
            d = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 364))
            cust = random.choice(customers)
            prod = random.choice(products)
            qty = random.randint(1, 20)
            rev = round(prod[3] * qty * random.uniform(0.85, 1.15), 2)
            sales.append((i, d.strftime("%Y-%m-%d"), cust[0], prod[0], qty, rev, cust[3], random.choice(channels)))
        cur.executemany("INSERT INTO sales VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;", sales)

        depts = ["Marketing", "Engineering", "Sales", "HR", "Operations"]
        ecats = ["Salaries", "Marketing", "Infrastructure", "Travel", "Software Licenses"]
        expenses = []
        for i in range(1, 501):
            d = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 364))
            expenses.append((i, d.strftime("%Y-%m-%d"), random.choice(ecats),
                             round(random.uniform(100, 50000), 2),
                             random.choice(depts), "Business expense"))
        cur.executemany("INSERT INTO expenses VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;", expenses)

        roles_map = {
            "Marketing": ["Marketing Manager", "Content Strategist"],
            "Engineering": ["Software Engineer", "DevOps Engineer", "QA Engineer"],
            "Sales": ["Sales Rep", "Account Executive"],
            "HR": ["HR Manager", "Recruiter"],
            "Operations": ["Operations Manager", "Analyst"],
        }
        emps = []
        for i in range(1, 101):
            dept = random.choice(depts)
            role = random.choice(roles_map[dept])
            hire = datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1460))
            emps.append((i, f"{random.choice(first_names)} {random.choice(last_names)}",
                         dept, role, hire.strftime("%Y-%m-%d"),
                         round(random.uniform(40000, 150000), 2),
                         round(random.uniform(2.5, 5.0), 1),
                         random.choice(regions)))
        cur.executemany(
            "INSERT INTO employees VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;", emps
        )


def _seed_insurance(conn) -> None:
    """Seed a minimal insurance_claims table so the default suggestions work."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS insurance_claims (
                id BIGINT PRIMARY KEY,
                insurer TEXT, year TEXT,
                total_claims_no BIGINT, total_claims_amt NUMERIC,
                claims_paid_no BIGINT, claims_paid_amt NUMERIC,
                claims_repudiated_no BIGINT, claims_rejected_no BIGINT,
                settlement_ratio NUMERIC
            );""")
        cur.execute("SELECT COUNT(*) FROM insurance_claims;")
        if cur.fetchone()[0] > 0:
            return
        insurers = ["LIC", "SBI Life", "HDFC Life", "ICICI Prudential",
                    "Max Life", "Bajaj Allianz", "Tata AIA", "Kotak Life"]
        random.seed(99)
        rows = []
        rid = 1
        for year in ["2019-20", "2020-21", "2021-22", "2022-23"]:
            for ins in insurers:
                total_no = random.randint(5000, 50000)
                total_amt = round(random.uniform(100, 5000), 2)
                paid_no = int(total_no * random.uniform(0.85, 0.98))
                paid_amt = round(total_amt * random.uniform(0.80, 0.95), 2)
                rep_no = int(total_no * random.uniform(0.01, 0.05))
                rej_no = int(total_no * random.uniform(0.01, 0.04))
                ratio = round(paid_no / total_no * 100, 2)
                rows.append((rid, ins, year, total_no, total_amt,
                             paid_no, paid_amt, rep_no, rej_no, ratio))
                rid += 1
        cur.executemany(
            "INSERT INTO insurance_claims VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT DO NOTHING;",
            rows,
        )
