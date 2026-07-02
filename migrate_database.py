"""
Database Migration Script
Adds new columns to existing tables for employee management enhancements
"""

import sqlite3
import os
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app import app

def migrate_database():
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'hr_employee_management.db')

    print("Starting database migration...")
    print(f"Database path: {db_path}")

    if not os.path.exists(db_path):
        print("Database doesn't exist. Creating new database with all tables...")
        with app.app_context():
            from sql import db
            db.create_all()
        print("✓ New database created successfully!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check existing columns in employees table
        cursor.execute("PRAGMA table_info(employees)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        print(f"\nExisting columns in 'employees' table: {len(existing_columns)} columns")

        # Add missing columns to employees table
        columns_to_add = [
            ("whatsapp_number", "VARCHAR(20) DEFAULT ''"),
            ("esi_number", "VARCHAR(100) DEFAULT ''"),
            ("manager_id", "INTEGER")
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}"
                    cursor.execute(sql)
                    print(f"✓ Added column: employees.{col_name}")
                except sqlite3.OperationalError as e:
                    print(f"✗ Failed to add employees.{col_name}: {e}")
            else:
                print(f"  Column employees.{col_name} already exists")

        # Check employee_profiles table
        cursor.execute("PRAGMA table_info(employee_profiles)")
        profile_columns = {row[1] for row in cursor.fetchall()}
        print(f"\nExisting columns in 'employee_profiles' table: {len(profile_columns)} columns")

        # Add missing columns to employee_profiles table
        profile_cols_to_add = [
            ("whatsapp_number", "VARCHAR(20)"),
            ("esi_number", "VARCHAR(100)"),
            ("family_info_json", "TEXT")
        ]

        for col_name, col_type in profile_cols_to_add:
            if col_name not in profile_columns:
                try:
                    sql = f"ALTER TABLE employee_profiles ADD COLUMN {col_name} {col_type}"
                    cursor.execute(sql)
                    print(f"✓ Added column: employee_profiles.{col_name}")
                except sqlite3.OperationalError as e:
                    print(f"✗ Failed to add employee_profiles.{col_name}: {e}")
            else:
                print(f"  Column employee_profiles.{col_name} already exists")

        conn.commit()
        print("\n✓ Column migration completed successfully!")

        # Now create new tables using SQLAlchemy
        print("\nCreating new tables...")
        with app.app_context():
            from sql import db
            db.create_all()
        print("✓ All new tables created!")

        # Verify the migration
        print("\nVerifying migration...")
        cursor.execute("PRAGMA table_info(employees)")
        new_columns = {row[1] for row in cursor.fetchall()}

        required_cols = {'whatsapp_number', 'esi_number', 'manager_id'}
        if required_cols.issubset(new_columns):
            print("✓ All required columns present in employees table")
        else:
            missing = required_cols - new_columns
            print(f"✗ Missing columns: {missing}")

        # Check if new tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {'employee_family', 'employee_asset', 'employee_contract'}
        if required_tables.issubset(tables):
            print("✓ All new tables created successfully")
        else:
            missing = required_tables - tables
            print(f"✗ Missing tables: {missing}")

        print("\n" + "="*60)
        print("MIGRATION COMPLETE!")
        print("="*60)
        print("You can now restart your Flask application.")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
