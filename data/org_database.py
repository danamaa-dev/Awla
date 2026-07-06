import os
import random
import sqlite3
from datetime import date, timedelta

ORG_DB_PATH = os.path.join(os.path.dirname(__file__), "org_data.db")


def init_org_db():
    """This is a synthetic analytics dataset regenerated from scratch
    whenever it's empty -- there is no real user-submitted data here to
    preserve, so unlike data/database.py this doesn't need a versioned
    migration path; the constraints below (audit finding M15) just apply
    directly to CREATE TABLE."""
    conn = sqlite3.connect(ORG_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        product TEXT NOT NULL,
        department TEXT NOT NULL,
        revenue REAL NOT NULL CHECK (revenue >= 0),
        units_sold INTEGER NOT NULL CHECK (units_sold >= 0),
        region TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        attendance_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late')),
        hours_worked REAL NOT NULL CHECK (hours_worked >= 0)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS budget (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department TEXT NOT NULL,
        category TEXT NOT NULL,
        allocated_budget REAL NOT NULL CHECK (allocated_budget >= 0),
        spent_amount REAL NOT NULL CHECK (spent_amount >= 0),
        month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
        year INTEGER NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT NOT NULL UNIQUE,
        acquisition_date TEXT NOT NULL,
        segment TEXT NOT NULL,
        total_purchases REAL NOT NULL CHECK (total_purchases >= 0),
        satisfaction_score REAL NOT NULL CHECK (satisfaction_score BETWEEN 1.0 AND 5.0)
    )""")

    if c.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0:
        _seed_data(c)

    conn.commit()
    conn.close()


def _seed_data(c):
    products = ["Laptop", "Monitor", "Keyboard", "Mouse", "Headset"]
    regions = ["North", "South", "East", "West"]
    departments = ["Sales", "Marketing", "Operations", "Finance", "HR"]
    segments = ["Enterprise", "SMB", "Individual"]
    categories = ["Salaries", "Operations", "Marketing", "IT", "Training"]

    start = date(2025, 1, 1)
    for i in range(200):
        d = start + timedelta(days=random.randint(0, 530))
        c.execute("INSERT INTO sales VALUES (NULL,?,?,?,?,?,?)", (
            str(d), random.choice(products), random.choice(departments[:3]),
            round(random.uniform(500, 50000), 2), random.randint(1, 200),
            random.choice(regions)
        ))

    names = ["Ahmed Al-Rashid", "Sara Al-Mutairi", "Khalid Al-Dosari",
             "Fatima Al-Ghamdi", "Omar Al-Shehri", "Nora Al-Qahtani",
             "Abdullah Al-Harbi", "Maha Al-Zahrani", "Yousef Al-Otaibi", "Reem Al-Anazi"]
    start_emp = date(2025, 12, 1)
    for emp_num in range(1, 51):
        dept = random.choice(departments)
        name = random.choice(names)
        for day_offset in range(random.randint(8, 12)):
            d = start_emp + timedelta(days=random.randint(0, 196))
            status = random.choices(["present", "absent", "late"], weights=[75, 10, 15])[0]
            hours = round(random.uniform(6, 9), 1) if status == "present" else (
                round(random.uniform(1, 4), 1) if status == "late" else 0
            )
            c.execute("INSERT INTO employees VALUES (NULL,?,?,?,?,?,?)", (
                f"EMP{emp_num:03d}", name, dept, str(d), status, hours
            ))

    for dept in departments:
        for cat in categories:
            for month in range(1, 13):
                allocated = round(random.uniform(50000, 500000), 2)
                spent = round(allocated * random.uniform(0.6, 1.2), 2)
                year = random.choice([2025, 2026])
                c.execute("INSERT INTO budget VALUES (NULL,?,?,?,?,?,?)", (
                    dept, cat, allocated, spent, month, year
                ))

    for i in range(1, 301):
        acq = date(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        c.execute("INSERT INTO customers VALUES (NULL,?,?,?,?,?)", (
            f"CUST{i:04d}", str(acq), random.choice(segments),
            round(random.uniform(100, 100000), 2),
            round(random.uniform(1.0, 5.0), 1)
        ))
