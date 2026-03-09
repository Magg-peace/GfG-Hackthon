"""Database management: SQLite connection, schema introspection, and sample data generation."""

import sqlite3
import os
import csv
import io
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_DIR = Path(__file__).parent / "data"
DEFAULT_DB = DB_DIR / "business_data.db"


def get_db_path(session_id: str | None = None) -> Path:
    """Get database path for a session (uploaded CSV) or the default DB."""
    DB_DIR.mkdir(exist_ok=True)
    if session_id:
        return DB_DIR / f"session_{session_id}.db"
    return DEFAULT_DB


def get_connection(session_id: str | None = None) -> sqlite3.Connection:
    db_path = get_db_path(session_id)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_schema(session_id: str | None = None) -> str:
    """Return a text description of all tables and their columns for the LLM."""
    conn = get_connection(session_id)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]

    schema_parts = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}');")
        columns = cursor.fetchall()
        col_defs = ", ".join(f"{col['name']} ({col['type']})" for col in columns)
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM '{table}';")
        count = cursor.fetchone()[0]
        # Get sample values for each column (first 3 distinct)
        sample_parts = []
        for col in columns:
            col_name = col["name"]
            try:
                cursor.execute(
                    f"SELECT DISTINCT \"{col_name}\" FROM '{table}' WHERE \"{col_name}\" IS NOT NULL LIMIT 5;"
                )
                vals = [str(r[0]) for r in cursor.fetchall()]
                if vals:
                    sample_parts.append(f"  {col_name}: [{', '.join(vals)}]")
            except Exception:
                pass
        samples_str = "\n".join(sample_parts)
        schema_parts.append(
            f"Table: {table} ({count} rows)\n  Columns: {col_defs}\n  Sample values:\n{samples_str}"
        )

    conn.close()
    return "\n\n".join(schema_parts)


def execute_query(sql: str, session_id: str | None = None) -> list[dict]:
    """Execute a read-only SQL query and return results as list of dicts."""
    conn = get_connection(session_id)
    cursor = conn.cursor()

    # Safety: only allow SELECT statements
    sql_stripped = sql.strip().upper()
    if not sql_stripped.startswith("SELECT") and not sql_stripped.startswith("WITH"):
        raise ValueError("Only SELECT queries are allowed for security reasons.")

    # Block dangerous keywords
    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "EXEC", "ATTACH", "DETACH"]
    for kw in dangerous:
        if kw in sql_stripped.split("--")[0].split("/*")[0]:
            raise ValueError(f"Query contains forbidden keyword: {kw}")

    cursor.execute(sql)
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description] if cursor.description else []
    result = [dict(zip(columns, row)) for row in rows]
    conn.close()
    return result


def import_csv(file_content: bytes, filename: str, session_id: str) -> dict:
    """Import a CSV file into a new SQLite table for the given session."""
    table_name = Path(filename).stem.replace(" ", "_").replace("-", "_").lower()
    # Remove non-alphanumeric characters except underscores
    table_name = "".join(c for c in table_name if c.isalnum() or c == "_")
    if not table_name or table_name[0].isdigit():
        table_name = "data_" + table_name

    # Try multiple encodings to handle non-UTF-8 files (e.g. Windows-1252)
    decoded = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            decoded = file_content.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if decoded is None:
        decoded = file_content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(decoded))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty or has no valid rows.")

    columns = list(rows[0].keys())
    conn = get_connection(session_id)
    cursor = conn.cursor()

    # Infer column types from data
    col_types = {}
    for col in columns:
        sample_values = [r[col] for r in rows[:100] if r[col] and r[col].strip()]
        col_type = _infer_type(sample_values)
        safe_col = col.replace('"', '""')
        col_types[col] = (safe_col, col_type)

    col_defs = ", ".join(f'"{safe}" {ctype}' for safe, ctype in col_types.values())
    cursor.execute(f"DROP TABLE IF EXISTS \"{table_name}\";")
    cursor.execute(f"CREATE TABLE \"{table_name}\" ({col_defs});")

    placeholders = ", ".join(["?"] * len(columns))
    for row in rows:
        values = []
        for col in columns:
            val = row[col]
            ctype = col_types[col][1]
            if val is None or val.strip() == "":
                values.append(None)
            elif ctype == "REAL":
                try:
                    values.append(float(val.replace(",", "")))
                except ValueError:
                    values.append(val)
            elif ctype == "INTEGER":
                try:
                    values.append(int(float(val.replace(",", ""))))
                except ValueError:
                    values.append(val)
            else:
                values.append(val)
        cursor.execute(f"INSERT INTO \"{table_name}\" VALUES ({placeholders});", values)

    conn.commit()
    conn.close()
    return {"table_name": table_name, "columns": columns, "row_count": len(rows)}


def _infer_type(values: list[str]) -> str:
    """Infer SQLite column type from sample string values."""
    if not values:
        return "TEXT"
    int_count = 0
    float_count = 0
    for v in values:
        v = v.strip().replace(",", "")
        try:
            int(v)
            int_count += 1
            continue
        except ValueError:
            pass
        try:
            float(v)
            float_count += 1
        except ValueError:
            pass
    total = len(values)
    if int_count > total * 0.8:
        return "INTEGER"
    if (int_count + float_count) > total * 0.8:
        return "REAL"
    return "TEXT"


def seed_sample_data():
    """Generate realistic sample business data if the default DB doesn't exist or is empty."""
    db_path = get_db_path()
    DB_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check if tables already exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing = [r[0] for r in cursor.fetchall()]
    if "sales" in existing:
        conn.close()
        return

    random.seed(42)

    # --- Regions & Products ---
    regions = ["North", "South", "East", "West"]
    categories = ["Electronics", "Clothing", "Home & Garden", "Sports", "Books"]
    products = {
        "Electronics": ["Laptop", "Smartphone", "Tablet", "Headphones", "Smart Watch"],
        "Clothing": ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Dress"],
        "Home & Garden": ["Sofa", "Lamp", "Plant Pot", "Cookware Set", "Rug"],
        "Sports": ["Yoga Mat", "Dumbbells", "Running Shoes", "Bicycle", "Tennis Racket"],
        "Books": ["Fiction Novel", "Tech Manual", "Cookbook", "Biography", "Self-Help"],
    }

    # --- Customers ---
    cursor.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            region TEXT,
            signup_date TEXT,
            customer_segment TEXT
        );
    """)

    first_names = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry", "Ivy", "Jack",
                   "Karen", "Leo", "Mia", "Noah", "Olivia", "Peter", "Quinn", "Rachel", "Sam", "Tina",
                   "Uma", "Victor", "Wendy", "Xander", "Yara", "Zach"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                  "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson"]
    segments = ["Enterprise", "SMB", "Startup", "Individual"]

    customers = []
    for i in range(1, 201):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
        region = random.choice(regions)
        signup = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 730))
        segment = random.choice(segments)
        customers.append((i, name, email, region, signup.strftime("%Y-%m-%d"), segment))
    cursor.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?);", customers)

    # --- Products table ---
    cursor.execute("""
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT,
            category TEXT,
            unit_price REAL,
            cost_price REAL
        );
    """)

    product_rows = []
    pid = 1
    for cat, prods in products.items():
        for pname in prods:
            price = round(random.uniform(15, 1500), 2)
            cost = round(price * random.uniform(0.4, 0.75), 2)
            product_rows.append((pid, pname, cat, price, cost))
            pid += 1
    cursor.executemany("INSERT INTO products VALUES (?,?,?,?,?);", product_rows)

    # --- Sales ---
    cursor.execute("""
        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            sale_date TEXT,
            customer_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            revenue REAL,
            region TEXT,
            sales_channel TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)

    channels = ["Online", "Retail", "Partner"]
    sales_rows = []
    for i in range(1, 2001):
        sale_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 364))
        cust = random.choice(customers)
        prod = random.choice(product_rows)
        qty = random.randint(1, 20)
        revenue = round(prod[3] * qty * random.uniform(0.85, 1.15), 2)
        region = cust[3]
        channel = random.choice(channels)
        sales_rows.append((i, sale_date.strftime("%Y-%m-%d"), cust[0], prod[0], qty, revenue, region, channel))
    cursor.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?,?);", sales_rows)

    # --- Expenses ---
    cursor.execute("""
        CREATE TABLE expenses (
            expense_id INTEGER PRIMARY KEY,
            expense_date TEXT,
            category TEXT,
            amount REAL,
            department TEXT,
            description TEXT
        );
    """)

    departments = ["Marketing", "Engineering", "Sales", "HR", "Operations"]
    expense_categories = ["Salaries", "Marketing", "Infrastructure", "Travel", "Software Licenses", "Office Supplies"]
    expense_rows = []
    for i in range(1, 501):
        edate = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 364))
        ecat = random.choice(expense_categories)
        amount = round(random.uniform(100, 50000), 2)
        dept = random.choice(departments)
        desc = f"{ecat} expense for {dept}"
        expense_rows.append((i, edate.strftime("%Y-%m-%d"), ecat, amount, dept, desc))
    cursor.executemany("INSERT INTO expenses VALUES (?,?,?,?,?,?);", expense_rows)

    # --- Employee Performance ---
    cursor.execute("""
        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY,
            name TEXT,
            department TEXT,
            role TEXT,
            hire_date TEXT,
            performance_score REAL,
            quarterly_target REAL,
            quarterly_achieved REAL
        );
    """)

    roles = {"Marketing": ["Marketing Manager", "Content Writer", "SEO Analyst"],
             "Engineering": ["Software Engineer", "DevOps Engineer", "QA Engineer"],
             "Sales": ["Sales Rep", "Account Manager", "Sales Director"],
             "HR": ["HR Manager", "Recruiter", "Training Lead"],
             "Operations": ["Operations Manager", "Logistics Coordinator", "Supply Chain Analyst"]}

    emp_rows = []
    for i in range(1, 76):
        dept = random.choice(departments)
        role = random.choice(roles[dept])
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        hire = datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1800))
        perf = round(random.uniform(2.5, 5.0), 1)
        target = round(random.uniform(50000, 200000), 2)
        achieved = round(target * random.uniform(0.6, 1.3), 2)
        emp_rows.append((i, f"{fn} {ln}", dept, role, hire.strftime("%Y-%m-%d"), perf, target, achieved))
    cursor.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?);", emp_rows)

    conn.commit()
    conn.close()
    print("Sample business data seeded successfully.")


def load_insurance_dataset():
    """Load the India Life Insurance Claims CSV into the default SQLite database."""
    import pandas as pd

    csv_path = Path(__file__).parent.parent / "Dataset" / "1. India Life Insurance Claims" / "India Life Insurance Claims.csv"
    if not csv_path.exists():
        print("Insurance dataset not found, skipping.")
        return

    conn = sqlite3.connect(str(get_db_path()))
    cursor = conn.cursor()

    # Check if already loaded
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='insurance_claims';")
    if cursor.fetchone():
        conn.close()
        return

    df = pd.read_csv(str(csv_path), encoding="latin-1")
    df = df.dropna(subset=["life_insurer", "year"])

    # Clean column names for SQL friendliness
    df.columns = [c.strip().replace(" ", "_") for c in df.columns]

    df.to_sql("insurance_claims", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print(f"Insurance claims dataset loaded: {len(df)} rows.")
