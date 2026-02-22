import sqlite3
import os

db_path = 'database.db'

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add ban_expiration column to users table
        cursor.execute("ALTER TABLE users ADD COLUMN ban_expiration INTEGER DEFAULT 0")
        print("Added ban_expiration column to users table.")
    except sqlite3.OperationalError as e:
        print(f"Column ban_expiration might already exist: {e}")

    try:
        # Add warnings column to users table
        cursor.execute("ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0")
        print("Added warnings column to users table.")
    except sqlite3.OperationalError as e:
        print(f"Column warnings might already exist: {e}")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
