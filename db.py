import os
import sqlite3
from datetime import datetime, timedelta

# Determine database type
DATABASE_URL = os.environ.get('DATABASE_URL')
IS_POSTGRES = bool(DATABASE_URL)

if IS_POSTGRES:
    import psycopg2
    from psycopg2.extras import DictCursor
    IntegrityError = psycopg2.errors.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
        self.row_factory = None 

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def execute(self, sql, params=None):
        cursor = self.conn.cursor()
        if '?' in sql:
            sql = sql.replace('?', '%s')
        if 'INSERT OR REPLACE' in sql:
             sql = sql.replace('INSERT OR REPLACE', 'INSERT') 
        
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor

def get_db_connection():
    if IS_POSTGRES:
        try:
            # Add sslmode='require' for secure connection on Render
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor, sslmode='require')
        except psycopg2.OperationalError:
            # Fallback without sslmode if require fails (e.g. local postgres)
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
            
        conn.autocommit = False
        return PostgresConnectionWrapper(conn)
    else:
        basedir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(basedir, 'database.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    return conn

def execute_query(cursor, sql, params=None):
    if IS_POSTGRES:
        # Convert SQLite syntax to Postgres syntax
        sql = sql.replace('?', '%s')
        sql = sql.replace('INSERT OR REPLACE', 'INSERT') # Simple replacement, needs ON CONFLICT handling manually in specific queries
        
        # Handle AUTOINCREMENT in CREATE TABLE
        sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    return cursor

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Helper for creating tables compatible with both
    def create_table(sql):
        if IS_POSTGRES:
            sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            sql = sql.replace('DATETIME', 'TIMESTAMP')
        execute_query(cursor, sql)

    # Users
    create_table('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            game_id TEXT,
            nickname TEXT,
            elo INTEGER DEFAULT 1000,
            level INTEGER DEFAULT 4,
            matches INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        )
    ''')

    # Migration: Ensure is_admin column exists
    try:
        execute_query(cursor, "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        conn.rollback() # Reset transaction if column exists


    
    # Matches
    create_table('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'active',
            mode TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Match Players
    create_table('''
        CREATE TABLE IF NOT EXISTS match_players (
            match_id INTEGER,
            user_id BIGINT,
            accepted INTEGER DEFAULT 0,
            PRIMARY KEY (match_id, user_id)
        )
    ''')

    # Support Tickets
    create_table('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT,
            text TEXT,
            status TEXT DEFAULT 'open',
            admin_id BIGINT
        )
    ''')
    
    # Lobby Members
    create_table('''
        CREATE TABLE IF NOT EXISTS lobby_members (
            mode TEXT,
            lobby_id INTEGER,
            user_id BIGINT,
            PRIMARY KEY (mode, lobby_id, user_id)
        )
    ''')

    # Clans
    create_table('''
        CREATE TABLE IF NOT EXISTS clans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT UNIQUE,
            name TEXT,
            owner_id BIGINT,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            matches_played INTEGER DEFAULT 0,
            matches_won INTEGER DEFAULT 0,
            clan_elo INTEGER DEFAULT 1000,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            logo_url TEXT
        )
    ''')

    # Clan Members
    create_table('''
        CREATE TABLE IF NOT EXISTS clan_members (
            clan_id INTEGER,
            user_id BIGINT UNIQUE,
            role TEXT DEFAULT 'member',
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (clan_id, user_id),
            FOREIGN KEY (clan_id) REFERENCES clans(id)
        )
    ''')

    # Polls
    create_table('''
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    create_table('''
        CREATE TABLE IF NOT EXISTS poll_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER,
            option_text TEXT,
            FOREIGN KEY (poll_id) REFERENCES polls(id)
        )
    ''')

    create_table('''
        CREATE TABLE IF NOT EXISTS poll_votes (
            poll_id INTEGER,
            option_id INTEGER,
            user_id BIGINT,
            PRIMARY KEY (poll_id, user_id),
            FOREIGN KEY (poll_id) REFERENCES polls(id),
            FOREIGN KEY (option_id) REFERENCES poll_options(id)
        )
    ''')

    # Clan Matchmaking Queue
    create_table('''
        CREATE TABLE IF NOT EXISTS clan_matchmaking_queue (
            clan_id INTEGER PRIMARY KEY,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clan_id) REFERENCES clans(id)
        )
    ''')

    # Clan Matches
    create_table('''
        CREATE TABLE IF NOT EXISTS clan_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clan1_id INTEGER,
            clan2_id INTEGER,
            winner_clan_id INTEGER,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clan1_id) REFERENCES clans(id),
            FOREIGN KEY (clan2_id) REFERENCES clans(id)
        )
    ''')

    # Matchmaking Queue
    create_table('''
        CREATE TABLE IF NOT EXISTS matchmaking_queue (
            user_id BIGINT PRIMARY KEY,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Match Stats
    create_table('''
        CREATE TABLE IF NOT EXISTS match_stats (
            match_id INTEGER,
            user_id BIGINT,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            mvps INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            PRIMARY KEY (match_id, user_id)
        )
    ''')
    
    # Match Chat
    create_table('''
        CREATE TABLE IF NOT EXISTS match_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            user_id BIGINT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Friends
    create_table('''
        CREATE TABLE IF NOT EXISTS friends (
            user_id BIGINT,
            friend_id BIGINT,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, friend_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (friend_id) REFERENCES users(user_id)
        )
    ''')

    # Migration checks (moved to end to ensure tables exist)
    if not IS_POSTGRES:
        # SQLite specific migrations for existing local DB
        try:
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'level' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 4')
            if 'is_banned' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0')
            if 'ban_until' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN ban_until DATETIME')
            if 'missed_games' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN missed_games INTEGER DEFAULT 0')
            if 'is_vip' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0')
            if 'vip_until' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN vip_until DATETIME')
            if 'is_admin' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
            if 'avatar_url' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN avatar_url TEXT')
            if 'steam_url' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN steam_url TEXT')
            if 'bio' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN bio TEXT')
            if 'warnings' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0')
            if 'ban_expiration' not in columns:
                cursor.execute('ALTER TABLE users ADD COLUMN ban_expiration INTEGER DEFAULT 0')

            cursor.execute("PRAGMA table_info(support_tickets)")
            st_columns = [column[1] for column in cursor.fetchall()]
            if 'admin_id' not in st_columns:
                cursor.execute('ALTER TABLE support_tickets ADD COLUMN admin_id INTEGER')
            
            cursor.execute("PRAGMA table_info(matches)")
            m_columns = [column[1] for column in cursor.fetchall()]
            if 'mode' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN mode TEXT')
            if 'created_at' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN created_at DATETIME')
            if 'team1_score' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN team1_score INTEGER DEFAULT 0')
            if 'team2_score' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN team2_score INTEGER DEFAULT 0')
            if 'winner_team' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN winner_team INTEGER')
            if 'veto_status' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN veto_status TEXT')
            if 'current_veto_turn' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN current_veto_turn INTEGER')
            if 'map_picked' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN map_picked TEXT')
            if 'last_action_time' not in m_columns:
                cursor.execute('ALTER TABLE matches ADD COLUMN last_action_time INTEGER DEFAULT 0')

            cursor.execute('UPDATE users SET level = 4 WHERE elo = 1000')

            cursor.execute("PRAGMA table_info(match_players)")
            mp_columns = [column[1] for column in cursor.fetchall()]
            if 'team' not in mp_columns:
                cursor.execute('ALTER TABLE match_players ADD COLUMN team INTEGER DEFAULT 1')
            if 'is_annulled' not in mp_columns:
                cursor.execute('ALTER TABLE match_players ADD COLUMN is_annulled INTEGER DEFAULT 0')
            if 'has_left' not in mp_columns:
                cursor.execute('ALTER TABLE match_players ADD COLUMN has_left INTEGER DEFAULT 0')
        except Exception as e:
            print(f"SQLite Migration error: {e}")
    else:
        # Postgres migrations
        try:
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS steam_url TEXT')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 4')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_until TIMESTAMP')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS missed_games INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS is_vip INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS vip_until TIMESTAMP')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS warnings INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_expiration INTEGER DEFAULT 0')
            
            execute_query(cursor, 'ALTER TABLE matches ADD COLUMN IF NOT EXISTS team1_score INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE matches ADD COLUMN IF NOT EXISTS team2_score INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE matches ADD COLUMN IF NOT EXISTS winner_team INTEGER')
            execute_query(cursor, 'ALTER TABLE matches ADD COLUMN IF NOT EXISTS veto_status TEXT')
            execute_query(cursor, 'ALTER TABLE matches ADD COLUMN IF NOT EXISTS current_veto_turn BIGINT')
            execute_query(cursor, 'ALTER TABLE matches ADD COLUMN IF NOT EXISTS map_picked TEXT')
            execute_query(cursor, 'ALTER TABLE matches ADD COLUMN IF NOT EXISTS last_action_time INTEGER DEFAULT 0')
            
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS warnings INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_expiration INTEGER DEFAULT 0')
            
            execute_query(cursor, 'ALTER TABLE match_players ADD COLUMN IF NOT EXISTS team INTEGER DEFAULT 1')
            execute_query(cursor, 'ALTER TABLE match_players ADD COLUMN IF NOT EXISTS is_annulled INTEGER DEFAULT 0')
            execute_query(cursor, 'ALTER TABLE match_players ADD COLUMN IF NOT EXISTS has_left INTEGER DEFAULT 0')
            
            execute_query(cursor, 'ALTER TABLE clans ADD COLUMN IF NOT EXISTS logo_url TEXT')
            execute_query(cursor, 'ALTER TABLE clans ADD COLUMN IF NOT EXISTS clan_elo INTEGER DEFAULT 1000')
            
            # Commit migrations immediately to avoid transaction issues
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Postgres Migration error (harmless if fresh): {e}")
        
    conn.commit()
    conn.close()

def get_clan_by_tag(tag):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT * FROM clans WHERE tag = ?', (tag,))
    clan = cursor.fetchone()
    conn.close()
    return clan

def get_clan_by_id(clan_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT * FROM clans WHERE id = ?', (clan_id,))
    clan = cursor.fetchone()
    conn.close()
    return clan

def get_user_clan(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT c.* FROM clans c 
        JOIN clan_members cm ON c.id = cm.clan_id 
        WHERE cm.user_id = ?
    ''', (user_id,))
    clan = cursor.fetchone()
    conn.close()
    return clan

def create_clan(tag, name, owner_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if IS_POSTGRES:
            execute_query(cursor, 'INSERT INTO clans (tag, name, owner_id) VALUES (?, ?, ?) RETURNING id', (tag, name, owner_id))
            clan_id = cursor.fetchone()[0] # or ['id']
        else:
            execute_query(cursor, 'INSERT INTO clans (tag, name, owner_id) VALUES (?, ?, ?)', (tag, name, owner_id))
            clan_id = cursor.lastrowid
            
        execute_query(cursor, 'INSERT INTO clan_members (clan_id, user_id, role) VALUES (?, ?, ?)', (clan_id, owner_id, 'owner'))
        conn.commit()
        return clan_id
    except Exception:
        return None
    finally:
        conn.close()

def get_all_clans():
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT * FROM clans')
    clans = cursor.fetchall()
    conn.close()
    return clans

def get_clan_members(clan_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT u.user_id, u.nickname, u.elo, u.level, cm.role 
        FROM clan_members cm 
        JOIN users u ON cm.user_id = u.user_id 
        WHERE cm.clan_id = ?
    ''', (clan_id,))
    members = cursor.fetchall()
    conn.close()
    return members

def add_clan_member(clan_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        execute_query(cursor, 'INSERT INTO clan_members (clan_id, user_id) VALUES (?, ?)', (clan_id, user_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_clan_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT COUNT(*) FROM clans')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT user_id, game_id, nickname, elo, level, is_banned, ban_until, missed_games, is_vip, vip_until FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def increment_missed_games(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'UPDATE users SET missed_games = missed_games + 1 WHERE user_id = ?', (user_id,))
    execute_query(cursor, 'SELECT missed_games FROM users WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return count

def reset_missed_games(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'UPDATE users SET missed_games = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def set_ban_status(user_id, status, until=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        execute_query(cursor, 'UPDATE users SET is_banned = 1, ban_until = ? WHERE user_id = ?', (until, user_id))
    else:
        execute_query(cursor, 'UPDATE users SET is_banned = 0, ban_until = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def create_match(mode, players_ids):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if IS_POSTGRES:
        execute_query(cursor, 'INSERT INTO matches (status, mode) VALUES (%s, %s) RETURNING id', ('pending', mode))
        match_id = cursor.fetchone()[0]
    else:
        execute_query(cursor, 'INSERT INTO matches (status, mode) VALUES ("pending", ?)', (mode,))
        match_id = cursor.lastrowid
    
    for uid in players_ids:
        execute_query(cursor, 'INSERT INTO match_players (match_id, user_id) VALUES (?, ?)', (match_id, uid))
        
    conn.commit()
    conn.close()
    return match_id

def accept_match_player(match_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'UPDATE match_players SET accepted = 1 WHERE match_id = ? AND user_id = ?', (match_id, user_id))
    conn.commit()
    conn.close()

def get_match_players(match_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT mp.user_id, u.nickname, u.elo, u.level, mp.accepted 
        FROM match_players mp
        JOIN users u ON mp.user_id = u.user_id
        WHERE mp.match_id = ?
    ''', (match_id,))
    players = cursor.fetchall()
    conn.close()
    return players 

def cancel_match(match_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, "UPDATE matches SET status = 'cancelled' WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()

def get_pending_match(match_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, "SELECT id, mode, status FROM matches WHERE id = ? AND status = 'pending'", (match_id,))
    match = cursor.fetchone()
    conn.close()
    return match

def get_level_by_elo(elo):
    try:
        elo = int(elo)
    except (ValueError, TypeError):
        elo = 1000
    if elo <= 500: return 1
    if elo <= 750: return 2
    if elo <= 900: return 3
    if elo <= 1050: return 4
    if elo <= 1200: return 5
    if elo <= 1350: return 6
    if elo <= 1530: return 7
    if elo <= 1750: return 8
    if elo <= 2000: return 9
    return 10

def add_user(user_id, game_id, nickname):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if IS_POSTGRES:
        # Postgres ON CONFLICT syntax
        execute_query(cursor, '''
            INSERT INTO users (user_id, game_id, nickname, elo, level) 
            VALUES (?, ?, ?, 1000, 4)
            ON CONFLICT (user_id) DO UPDATE SET
            game_id = EXCLUDED.game_id,
            nickname = EXCLUDED.nickname
        ''', (user_id, game_id, nickname))
    else:
        # SQLite syntax
        execute_query(cursor, 'INSERT OR REPLACE INTO users (user_id, game_id, nickname, elo, level) VALUES (?, ?, ?, 1000, 4)', 
                       (user_id, game_id, nickname))
                       
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT user_id, game_id, nickname, elo, level, matches, wins, 
               is_banned, ban_until, missed_games, is_vip, vip_until 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_top_players(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT nickname, elo, level, is_vip FROM users ORDER BY elo DESC LIMIT ?', (limit,))
    players = cursor.fetchall()
    conn.close()
    return players

def update_elo(user_id, elo_change, is_win):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        UPDATE users 
        SET elo = elo + ?, 
            matches = matches + 1,
            wins = wins + ?
        WHERE user_id = ?
    ''', (elo_change, 1 if is_win else 0, user_id))
    
    execute_query(cursor, 'SELECT elo FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res:
        new_elo = res[0]
        new_level = get_level_by_elo(new_elo)
        execute_query(cursor, 'UPDATE users SET level = ? WHERE user_id = ?', (new_level, user_id))
    
    conn.commit()
    conn.close()

def manual_update_elo(user_id, elo_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        UPDATE users 
        SET elo = elo + ?
        WHERE user_id = ?
    ''', (elo_change, user_id))
    
    execute_query(cursor, 'SELECT elo FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res:
        new_elo = res[0]
        new_level = get_level_by_elo(new_elo)
        execute_query(cursor, 'UPDATE users SET level = ? WHERE user_id = ?', (new_level, user_id))
    
    conn.commit()
    conn.close()

def adjust_user_stats(user_id, matches_change, wins_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        UPDATE users 
        SET matches = matches + ?,
            wins = wins + ?
        WHERE user_id = ?
    ''', (matches_change, wins_change, user_id))
    conn.commit()
    conn.close()

def create_support_ticket(user_id, text):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if IS_POSTGRES:
        execute_query(cursor, 'INSERT INTO support_tickets (user_id, text) VALUES (?, ?) RETURNING id', (user_id, text))
        ticket_id = cursor.fetchone()[0]
    else:
        execute_query(cursor, 'INSERT INTO support_tickets (user_id, text) VALUES (?, ?)', (user_id, text))
        ticket_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return ticket_id

def get_support_ticket(ticket_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT user_id, text, admin_id, status FROM support_tickets WHERE id = ?', (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    return ticket

def get_all_tickets():
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT id, user_id, text, status FROM support_tickets WHERE status = "open"')
    tickets = cursor.fetchall()
    conn.close()
    return tickets

def add_lobby_member(mode, lobby_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if IS_POSTGRES:
        execute_query(cursor, '''
            INSERT INTO lobby_members (mode, lobby_id, user_id) VALUES (?, ?, ?)
            ON CONFLICT (mode, lobby_id, user_id) DO NOTHING
        ''', (mode, lobby_id, user_id))
    else:
        execute_query(cursor, 'INSERT OR REPLACE INTO lobby_members (mode, lobby_id, user_id) VALUES (?, ?, ?)', (mode, lobby_id, user_id))
        
    conn.commit()
    conn.close()

def remove_lobby_member(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'DELETE FROM lobby_members WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_all_lobby_members():
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT mode, lobby_id, user_id FROM lobby_members')
    members = cursor.fetchall()
    conn.close()
    return members

def update_support_ticket(ticket_id, admin_id=None, status=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if admin_id is not None:
        execute_query(cursor, 'UPDATE support_tickets SET admin_id = ? WHERE id = ?', (admin_id, ticket_id))
    if status is not None:
        execute_query(cursor, 'UPDATE support_tickets SET status = ? WHERE id = ?', (status, ticket_id))
    conn.commit()
    conn.close()

def close_ticket(ticket_id, admin_id):
    update_support_ticket(ticket_id, admin_id=admin_id, status='closed')

def update_user_profile(user_id, nickname=None, game_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if nickname:
        execute_query(cursor, 'UPDATE users SET nickname = ? WHERE user_id = ?', (nickname, user_id))
    if game_id:
        execute_query(cursor, 'UPDATE users SET game_id = ? WHERE user_id = ?', (game_id, user_id))
    conn.commit()
    conn.close()

def get_user_by_nickname(nickname):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT * FROM users WHERE nickname = ?', (nickname,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_friend(user_id, friend_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if already friends or pending
        execute_query(cursor, 'SELECT status FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                      (user_id, friend_id, friend_id, user_id))
        existing = cursor.fetchone()
        if existing:
            return False # Already sent/friends
            
        execute_query(cursor, 'INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'pending'))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding friend: {e}")
        return False
    finally:
        conn.close()

def accept_friend(user_id, friend_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # user_id is the one accepting (so friend_id sent the request)
    execute_query(cursor, 'UPDATE friends SET status = "accepted" WHERE user_id = ? AND friend_id = ?', (friend_id, user_id))
    if cursor.rowcount == 0:
        execute_query(cursor, 'UPDATE friends SET status = "accepted" WHERE user_id = ? AND friend_id = ?', (user_id, friend_id))
        
    conn.commit()
    conn.close()

def remove_friend(user_id, friend_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                   (user_id, friend_id, friend_id, user_id))
    conn.commit()
    conn.close()

def get_friends(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT u.user_id, u.nickname, u.avatar_url, u.elo, u.is_vip
        FROM users u
        JOIN friends f ON (f.friend_id = u.user_id AND f.user_id = ?) 
                       OR (f.user_id = u.user_id AND f.friend_id = ?)
        WHERE f.status = "accepted"
    ''', (user_id, user_id))
    friends = cursor.fetchall()
    conn.close()
    return friends

def get_friend_requests(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT u.user_id, u.nickname, u.avatar_url
        FROM users u
        JOIN friends f ON f.user_id = u.user_id
        WHERE f.friend_id = ? AND f.status = "pending"
    ''', (user_id,))
    requests = cursor.fetchall()
    conn.close()
    return requests

def get_friend_status(user_id, other_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT user_id, status FROM friends 
        WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (user_id, other_id, other_id, user_id))
    res = cursor.fetchone()
    conn.close()
    if not res: return None
    return res

def set_vip_status(user_id, status, until=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status and until:
        execute_query(cursor, 'SELECT is_vip, vip_until FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        if res and res[0] and res[1]:
            try:
                # Handle both datetime object and string (postgres returns datetime)
                current_until = res[1]
                if isinstance(current_until, str):
                    current_until = datetime.strptime(current_until, "%Y-%m-%d %H:%M:%S")
                
                if current_until > datetime.now():
                    new_until_dt = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
                    days_to_add = (new_until_dt - datetime.now()).days
                    if days_to_add < 0: days_to_add = 30
                    
                    final_until = (current_until + timedelta(days=days_to_add)).strftime("%Y-%m-%d %H:%M:%S")
                    execute_query(cursor, 'UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?', (final_until, user_id))
                    conn.commit()
                    conn.close()
                    return
            except: pass
            
    execute_query(cursor, 'UPDATE users SET is_vip = ?, vip_until = ? WHERE user_id = ?', (1 if status else 0, until, user_id))
    conn.commit()
    conn.close()

def is_user_vip(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT is_vip, vip_until FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    if not res: return False
    
    is_vip, until = res
    if not is_vip: return False
    
    if until:
        try:
            until_dt = until
            if isinstance(until, str):
                until_dt = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
            
            if datetime.now() > until_dt:
                set_vip_status(user_id, False)
                return False
        except: pass
        
    return True

def update_clan_stats(clan_id, is_win, elo_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        UPDATE clans 
        SET matches_played = matches_played + 1,
            matches_won = matches_won + ?,
            exp = exp + ?,
            clan_elo = clan_elo + ?
        WHERE id = ?
    ''', (1 if is_win else 0, 50 if is_win else 10, elo_change, clan_id))
    
    execute_query(cursor, 'SELECT exp, level FROM clans WHERE id = ?', (clan_id,))
    res = cursor.fetchone()
    if res:
        exp, level = res
        new_level = (exp // 500) + 1
        if new_level > level:
            execute_query(cursor, 'UPDATE clans SET level = ? WHERE id = ?', (new_level, clan_id))
        
    conn.commit()
    conn.close()

def get_top_clans(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, '''
        SELECT tag, name, clan_elo, matches_won, matches_played, level 
        FROM clans 
        ORDER BY clan_elo DESC, matches_won DESC 
        LIMIT ?
    ''', (limit,))
    clans = cursor.fetchall()
    conn.close()
    return clans

def remove_clan_member(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'DELETE FROM clan_members WHERE user_id = ?', (user_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_user_by_game_id(game_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    execute_query(cursor, 'SELECT user_id FROM users WHERE game_id = ?', (game_id,))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None
