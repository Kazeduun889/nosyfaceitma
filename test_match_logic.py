import sqlite3
import os
import sys
import json

# Add parent directory
sys.path.append(os.getcwd())
try:
    import db
except ImportError:
    # Try web/..
    sys.path.append(os.path.join(os.getcwd(), '..'))
    import db

def test_logic():
    print("Testing match logic...")
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create dummy users
    print("Creating users...")
    try:
        cursor.execute("INSERT OR REPLACE INTO users (user_id, nickname) VALUES (999, 'TestUser1')")
        cursor.execute("INSERT OR REPLACE INTO users (user_id, nickname) VALUES (888, 'TestUser2')")
        conn.commit()
    except Exception as e:
        print(f"Error creating users: {e}")

    # 2. Add TestUser2 to queue
    print("Adding user to queue...")
    try:
        cursor.execute("DELETE FROM matchmaking_queue WHERE user_id IN (999, 888)")
        cursor.execute("INSERT INTO matchmaking_queue (user_id) VALUES (888)")
        conn.commit()
    except Exception as e:
        print(f"Error adding to queue: {e}")

    # 3. Simulate join_queue for TestUser1
    print("Simulating join_queue...")
    try:
        session_user_id = 999
        opponent = cursor.execute('SELECT * FROM matchmaking_queue WHERE user_id != ? ORDER BY joined_at ASC LIMIT 1', (session_user_id,)).fetchone()
        
        if opponent:
            print(f"Opponent found: {opponent['user_id']}")
            opponent_id = opponent['user_id']
            cursor.execute('DELETE FROM matchmaking_queue WHERE user_id = ?', (opponent_id,))
            
            # Create match
            print("Creating match...")
            if db.IS_POSTGRES:
                cursor.execute("INSERT INTO matches (mode, status) VALUES ('1x1', 'active') RETURNING id")
                match_id = cursor.fetchone()[0]
            else:
                cursor.execute("INSERT INTO matches (mode, status) VALUES ('1x1', 'active')")
                match_id = cursor.lastrowid
            
            print(f"Match created with ID: {match_id}")
            
            # Add players
            print("Adding players...")
            if db.IS_POSTGRES:
                cursor.execute("INSERT INTO match_players (match_id, user_id, accepted) VALUES (%s, %s, 1)", (match_id, session_user_id))
                cursor.execute("INSERT INTO match_players (match_id, user_id, accepted) VALUES (%s, %s, 1)", (match_id, opponent_id))
            else:
                cursor.execute("INSERT INTO match_players (match_id, user_id, accepted) VALUES (?, ?, 1)", (match_id, session_user_id))
                cursor.execute("INSERT INTO match_players (match_id, user_id, accepted) VALUES (?, ?, 1)", (match_id, opponent_id))
            
            conn.commit()
            print("Match creation committed.")
            
            # 4. Simulate match_room
            print("Simulating match_room...")
            match = cursor.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
            print(f"Match status: {match['status']}")
            
            if match['status'] == 'active' and not match['veto_status']:
                print("Initializing veto...")
                veto_status = {'Map1': 'available'}
                first_turn = session_user_id
                
                cursor.execute('UPDATE matches SET veto_status = ?, current_veto_turn = ? WHERE id = ?',
                             (json.dumps(veto_status), first_turn, match_id))
                conn.commit()
                print("Veto initialized.")
                
            # Verify update
            match = cursor.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
            print(f"Veto status in DB: {match['veto_status']}")
            
            # 5. Simulate veto
            print("Simulating veto...")
            veto_data = json.loads(match['veto_status'])
            # ... veto logic ...
            
        else:
            print("No opponent found (unexpected)")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        conn.close()

if __name__ == "__main__":
    test_logic()
