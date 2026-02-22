import sqlite3
import os
import sys

# Add current directory to path so we can import db if needed, 
# but we'll try to use sqlite3 directly for robustness on local dev environment
sys.path.append(os.getcwd())

def fix_schema():
    print("Checking database schema...")
    
    # Check if we are using SQLite
    db_path = 'database.db'
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found in current directory.")
        # Try to find it in web folder or parent
        if os.path.exists(os.path.join('web', 'database.db')):
            db_path = os.path.join('web', 'database.db')
        elif os.path.exists(os.path.join('..', 'database.db')):
            db_path = os.path.join('..', 'database.db')
        else:
            print("Could not locate database.db. Creating new one...")
            db_path = 'database.db'

    print(f"Using database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Check matches table columns
        print("Checking 'matches' table...")
        cursor.execute("PRAGMA table_info(matches)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        needed_columns = {
            'mode': 'TEXT',
            'created_at': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
            'team1_score': 'INTEGER DEFAULT 0',
            'team2_score': 'INTEGER DEFAULT 0',
            'winner_team': 'INTEGER',
            'veto_status': 'TEXT',
            'current_veto_turn': 'INTEGER',
            'map_picked': 'TEXT'
        }
        
        for col_name, col_type in needed_columns.items():
            if col_name not in columns:
                print(f"Adding missing column: {col_name}")
                try:
                    cursor.execute(f'ALTER TABLE matches ADD COLUMN {col_name} {col_type}')
                except Exception as e:
                    print(f"Error adding {col_name}: {e}")
            else:
                print(f"Column {col_name} exists.")

        # 2. Check match_players table
        print("\nChecking 'match_players' table...")
        cursor.execute("PRAGMA table_info(match_players)")
        mp_columns = [col[1] for col in cursor.fetchall()]
        if 'team' not in mp_columns:
            print("Adding 'team' column to match_players")
            try:
                cursor.execute('ALTER TABLE match_players ADD COLUMN team INTEGER DEFAULT 1')
            except Exception as e:
                print(f"Error adding team column: {e}")

        # 3. Check matchmaking_queue table
        print("\nChecking 'matchmaking_queue' table...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matchmaking_queue'")
        if not cursor.fetchone():
            print("Creating matchmaking_queue table...")
            cursor.execute('''
                CREATE TABLE matchmaking_queue (
                    user_id BIGINT PRIMARY KEY,
                    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            print("matchmaking_queue table exists.")

        # 4. Check match_chat table
        print("\nChecking 'match_chat' table...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='match_chat'")
        if not cursor.fetchone():
            print("Creating match_chat table...")
            cursor.execute('''
                CREATE TABLE match_chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    user_id BIGINT,
                    message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            print("match_chat table exists.")

        conn.commit()
        conn.close()
        print("\nSchema check/fix completed successfully.")
        
    except Exception as e:
        print(f"\nCritical error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_schema()
