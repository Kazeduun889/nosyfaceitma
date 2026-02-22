
import sqlite3
import os

def run_migration():
    # Connect to the database
    db_path = 'database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Promote user 8565678796 to admin
    user_id_to_promote = "8565678796"
    print(f"Promoting user {user_id_to_promote} to admin...")
    cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id_to_promote,))
    if cursor.rowcount > 0:
        print("User promoted successfully.")
    else:
        print("User not found or already admin.")

    # 2. Add is_annulled column to match_players table
    print("Checking for is_annulled column in match_players...")
    cursor.execute("PRAGMA table_info(match_players)")
    columns = [info[1] for info in cursor.fetchall()]

    if 'is_annulled' not in columns:
        print("Adding is_annulled column...")
        cursor.execute("ALTER TABLE match_players ADD COLUMN is_annulled INTEGER DEFAULT 0")
        print("Column added.")
    else:
        print("Column is_annulled already exists.")

    # 3. Add status column to matches table if not exists (for full cancellation)
    print("Checking for status column in matches...")
    cursor.execute("PRAGMA table_info(matches)")
    match_columns = [info[1] for info in cursor.fetchall()]

    if 'status' not in match_columns:
        print("Adding status column to matches...")
        cursor.execute("ALTER TABLE matches ADD COLUMN status TEXT DEFAULT 'ongoing'") # ongoing, completed, cancelled
        print("Column added.")
    else:
        print("Column status already exists.")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    run_migration()
