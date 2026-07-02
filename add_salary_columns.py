"""
Add salary columns to employees table
Run the Flask app first to create tables, then run this script.
"""
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = "instance/hr_employee_management.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if employees table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees'")
    if not cursor.fetchone():
        print("[ERROR] 'employees' table not found!")
        print("Please run the Flask application first to create the database tables.")
        print("Then run this migration script.")
        conn.close()
        return

    print("Adding salary columns to employees table...")

    columns_to_add = [
        ("basic_salary", "NUMERIC(12, 2)"),
        ("hra", "NUMERIC(12, 2)"),
        ("allowances", "NUMERIC(12, 2)"),
        ("gross_salary", "NUMERIC(12, 2)"),
        ("ctc", "NUMERIC(12, 2)"),
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}")
            print(f"[OK] Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"[SKIP] Column '{col_name}' already exists")
            else:
                print(f"[FAIL] Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("\n✅ Salary columns migration complete!")
    print("You can now use HR dashboard to manage employee salaries.")

if __name__ == "__main__":
    main()
