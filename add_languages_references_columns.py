"""
Add languages_known and reference columns to employee_profiles and employees tables
Run this after starting the Flask app.
"""
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = "instance/hr_employee_management.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('employee_profiles', 'employees')")
    tables = [row[0] for row in cursor.fetchall()]

    if 'employee_profiles' not in tables or 'employees' not in tables:
        print("[ERROR] Required tables not found!")
        print("Please run the Flask application first to create the database tables.")
        conn.close()
        return

    print("Adding languages and reference columns to employee_profiles and employees tables...")

    columns_to_add = [
        ("languages_known", "VARCHAR(500)"),
        ("ref1_name", "VARCHAR(100)"),
        ("ref1_email", "VARCHAR(120)"),
        ("ref1_phone", "VARCHAR(20)"),
        ("ref1_relationship", "VARCHAR(100)"),
        ("ref2_name", "VARCHAR(100)"),
        ("ref2_email", "VARCHAR(120)"),
        ("ref2_phone", "VARCHAR(20)"),
        ("ref2_relationship", "VARCHAR(100)"),
        ("ref3_name", "VARCHAR(100)"),
        ("ref3_email", "VARCHAR(120)"),
        ("ref3_phone", "VARCHAR(20)"),
        ("ref3_relationship", "VARCHAR(100)"),
    ]

    # Add to employee_profiles table
    print("\n[employee_profiles]")
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE employee_profiles ADD COLUMN {col_name} {col_type}")
            print(f"  [OK] Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"  [SKIP] Column '{col_name}' already exists")
            else:
                print(f"  [FAIL] Error adding {col_name}: {e}")

    # Add to employees table
    print("\n[employees]")
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}")
            print(f"  [OK] Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"  [SKIP] Column '{col_name}' already exists")
            else:
                print(f"  [FAIL] Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("\n✅ Languages and references columns migration complete!")
    print("Employees can now add languages known and 3 references in Step 1.")

if __name__ == "__main__":
    main()
