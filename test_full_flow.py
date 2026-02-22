
import os
import sys
import unittest
import tempfile
import sqlite3
import json

# Add web directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'web')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Mock db module before importing app
import db
from web.app import app

class FacevosaitTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Monkeypatch db.get_db_connection to use our temp db
        self.original_get_db = db.get_db_connection
        self.original_is_postgres = db.IS_POSTGRES
        
        db.IS_POSTGRES = False # Force SQLite for testing
        
        def mock_get_db():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
            
        db.get_db_connection = mock_get_db
        
        # Initialize schema
        with app.app_context():
            db.init_db()
            
        self.app = app.test_client()
        self.app.testing = True

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)
        # Restore original functions
        db.get_db_connection = self.original_get_db
        db.IS_POSTGRES = self.original_is_postgres

    def login(self, user_id, nickname):
        with self.app.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['nickname'] = nickname
            sess['is_admin'] = 0
            
    def test_play_flow(self):
        print("Testing full play flow...")
        
        # 1. Login User 1
        self.login(1, 'PlayerOne')
        
        # 2. Access Play Page
        response = self.app.get('/play')
        self.assertEqual(response.status_code, 200)
        print("User 1 accessed play page.")
        
        # 3. Join Queue
        response = self.app.post('/play/join_queue', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'play', response.data) # Should stay on play page or redirect to it
        print("User 1 joined queue.")
        
        # Verify in queue
        conn = db.get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'SELECT * FROM matchmaking_queue WHERE user_id = 1')
        self.assertIsNotNone(cursor.fetchone())
        conn.close()
        
        # 4. Login User 2
        self.login(2, 'PlayerTwo')
        
        # 5. Join Queue (Should trigger match)
        response = self.app.post('/play/join_queue', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Should be redirected to match room
        # We need to find the match ID
        conn = db.get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'SELECT * FROM matches ORDER BY id DESC LIMIT 1')
        match = cursor.fetchone()
        self.assertIsNotNone(match)
        match_id = match['id']
        print(f"Match created: ID {match_id}")
        
        # Verify both players in match
        db.execute_query(cursor, 'SELECT COUNT(*) FROM match_players WHERE match_id = ?', (match_id,))
        count = cursor.fetchone()[0]
        self.assertEqual(count, 2)
        conn.close()
        
        # 6. Access Match Room as User 2
        response = self.app.get(f'/match/{match_id}')
        self.assertEqual(response.status_code, 200)
        print("User 2 accessed match room.")
        
        # 7. Check Veto Initialization
        conn = db.get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        self.assertIsNotNone(match['veto_status'])
        print("Veto initialized.")
        
        veto_data = json.loads(match['veto_status'])
        current_turn = match['current_veto_turn']
        print(f"Current turn: {current_turn}")
        
        # 8. Perform Veto (Ban a map)
        # Login as the user whose turn it is
        self.login(current_turn, 'CurrentTurnPlayer')
        
        map_to_ban = 'Desert' # Ensure this is in MAP_POOL
        response = self.app.post(f'/match/{match_id}/veto', data={'map_name': map_to_ban}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify ban
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        veto_data = json.loads(match['veto_status'])
        self.assertEqual(veto_data[map_to_ban], 'banned')
        print(f"Map {map_to_ban} banned.")
        conn.close()
        
        # 9. Send Chat Message
        response = self.app.post(f'/match/{match_id}/chat', data={'message': 'Hello world'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        conn = db.get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'SELECT * FROM match_chat WHERE match_id = ?', (match_id,))
        msg = cursor.fetchone()
        self.assertEqual(msg['message'], 'Hello world')
        print("Chat message sent.")
        conn.close()
        
        # 10. Submit Result
        winner_id = 1
        response = self.app.post(f'/match/{match_id}/submit_result', data={'winner_id': winner_id}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        conn = db.get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        self.assertEqual(match['status'], 'finished')
        self.assertEqual(match['winner_team'], winner_id)
        print("Match result submitted.")
        conn.close()
        
        print("FULL FLOW TEST PASSED SUCCESSFULLY")

if __name__ == '__main__':
    unittest.main()
