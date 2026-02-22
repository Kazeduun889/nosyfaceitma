import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            game_id TEXT,
            nickname TEXT,
            elo INTEGER DEFAULT 1000,
            level INTEGER DEFAULT 4,
            matches INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица для хранения матчей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT DEFAULT 'active',
            mode TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица для участников матчей (в том числе ожидающих подтверждения)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_players (
            match_id INTEGER,
            user_id INTEGER,
            accepted INTEGER DEFAULT 0,
            PRIMARY KEY (match_id, user_id)
        )
    ''')

    # Таблица для хранения обращений в поддержку
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'open',
            admin_id INTEGER
        )
    ''')
    
    # Таблица для лобби (синхронизация участников)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lobby_members (
            mode TEXT,
            lobby_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (mode, lobby_id, user_id)
        )
    ''')

    # Миграция: проверяем наличие колонки level
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
        
    # Миграция: проверяем наличие колонки admin_id в support_tickets
    cursor.execute("PRAGMA table_info(support_tickets)")
    st_columns = [column[1] for column in cursor.fetchall()]
    if 'admin_id' not in st_columns:
        cursor.execute('ALTER TABLE support_tickets ADD COLUMN admin_id INTEGER')
    
    # Миграция для matches
    cursor.execute("PRAGMA table_info(matches)")
    m_columns = [column[1] for column in cursor.fetchall()]
    if 'mode' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN mode TEXT')
    if 'created_at' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN created_at DATETIME')

    # Принудительное обновление всех игроков на 4 уровень, если ELO 1000
    cursor.execute('UPDATE users SET level = 4 WHERE elo = 1000')
        
    # Таблица кланов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT UNIQUE,
            name TEXT,
            owner_id INTEGER,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            matches_played INTEGER DEFAULT 0,
            matches_won INTEGER DEFAULT 0,
            clan_elo INTEGER DEFAULT 1000,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица участников кланов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clan_members (
            clan_id INTEGER,
            user_id INTEGER UNIQUE,
            role TEXT DEFAULT 'member',
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (clan_id, user_id),
            FOREIGN KEY (clan_id) REFERENCES clans(id)
        )
    ''')

    # Миграция для clans
    cursor.execute("PRAGMA table_info(clans)")
    c_columns = [column[1] for column in cursor.fetchall()]
    if 'clan_elo' not in c_columns:
        cursor.execute('ALTER TABLE clans ADD COLUMN clan_elo INTEGER DEFAULT 1000')

    # Таблица опросов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица вариантов ответов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS poll_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER,
            option_text TEXT,
            FOREIGN KEY (poll_id) REFERENCES polls(id)
        )
    ''')

    # Таблица голосов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS poll_votes (
            poll_id INTEGER,
            option_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (poll_id, user_id),
            FOREIGN KEY (poll_id) REFERENCES polls(id),
            FOREIGN KEY (option_id) REFERENCES poll_options(id)
        )
    ''')

    # Таблица для поиска клановых войн (очередь)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clan_matchmaking_queue (
            clan_id INTEGER PRIMARY KEY,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clan_id) REFERENCES clans(id)
        )
    ''')

    # Таблица клановых матчей
    cursor.execute('''
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

    # === НОВЫЕ ТАБЛИЦЫ ДЛЯ РЕАЛИЗМА ===

    # Очередь поиска матча (игроки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matchmaking_queue (
            user_id INTEGER PRIMARY KEY,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Расширенная статистика матча
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_stats (
            match_id INTEGER,
            user_id INTEGER,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            headshots INTEGER DEFAULT 0,
            mvps INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            PRIMARY KEY (match_id, user_id)
        )
    ''')
    
    # Миграция: логотип клана
    cursor.execute("PRAGMA table_info(clans)")
    c_columns = [column[1] for column in cursor.fetchall()]
    if 'logo_url' not in c_columns:
        cursor.execute('ALTER TABLE clans ADD COLUMN logo_url TEXT')

    # Миграция: таблица матчей (для истории)
    cursor.execute("PRAGMA table_info(matches)")
    m_columns = [column[1] for column in cursor.fetchall()]
    if 'team1_score' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN team1_score INTEGER DEFAULT 0')
    if 'team2_score' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN team2_score INTEGER DEFAULT 0')
    if 'winner_team' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN winner_team INTEGER') # 1 or 2
        
    # Миграция: админ
    cursor.execute("PRAGMA table_info(users)")
    u_columns = [column[1] for column in cursor.fetchall()]
    if 'is_admin' not in u_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
    if 'avatar_url' not in u_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN avatar_url TEXT')
    if 'steam_url' not in u_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN steam_url TEXT')
    if 'bio' not in u_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN bio TEXT')

    # Миграция: матчи (Veto)
    cursor.execute("PRAGMA table_info(matches)")
    m_columns = [column[1] for column in cursor.fetchall()]
    if 'veto_status' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN veto_status TEXT') # JSON {"Mirage": "banned", ...}
    if 'current_veto_turn' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN current_veto_turn INTEGER') # user_id
    if 'map_picked' not in m_columns:
        cursor.execute('ALTER TABLE matches ADD COLUMN map_picked TEXT')
        
    # Чат матча
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            user_id INTEGER,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица друзей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            user_id INTEGER,
            friend_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, friend_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (friend_id) REFERENCES users(user_id)
        )
    ''')

    # Миграция: команда игрока в матче
    cursor.execute("PRAGMA table_info(match_players)")
    mp_columns = [column[1] for column in cursor.fetchall()]
    if 'team' not in mp_columns:
        cursor.execute('ALTER TABLE match_players ADD COLUMN team INTEGER DEFAULT 1') # 1 or 2
        
    conn.commit()
    conn.close()

def get_clan_by_tag(tag):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clans WHERE tag = ?', (tag,))
    clan = cursor.fetchone()
    conn.close()
    return clan

def get_clan_by_id(clan_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clans WHERE id = ?', (clan_id,))
    clan = cursor.fetchone()
    conn.close()
    return clan

def get_user_clan(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.* FROM clans c 
        JOIN clan_members cm ON c.id = cm.clan_id 
        WHERE cm.user_id = ?
    ''', (user_id,))
    clan = cursor.fetchone()
    conn.close()
    return clan

def create_clan(tag, name, owner_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO clans (tag, name, owner_id) VALUES (?, ?, ?)', (tag, name, owner_id))
        clan_id = cursor.lastrowid
        cursor.execute('INSERT INTO clan_members (clan_id, user_id, role) VALUES (?, ?, ?)', (clan_id, owner_id, 'owner'))
        conn.commit()
        return clan_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_all_clans():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clans')
    clans = cursor.fetchall()
    conn.close()
    return clans

def get_clan_members(clan_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.user_id, u.nickname, u.elo, u.level, cm.role 
        FROM clan_members cm 
        JOIN users u ON cm.user_id = u.user_id 
        WHERE cm.clan_id = ?
    ''', (clan_id,))
    members = cursor.fetchall()
    conn.close()
    return members

def add_clan_member(clan_id, user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO clan_members (clan_id, user_id) VALUES (?, ?)', (clan_id, user_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_clan_count():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM clans')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, game_id, nickname, elo, level, is_banned, ban_until, missed_games, is_vip, vip_until FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def increment_missed_games(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET missed_games = missed_games + 1 WHERE user_id = ?', (user_id,))
    cursor.execute('SELECT missed_games FROM users WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return count

def reset_missed_games(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET missed_games = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def set_ban_status(user_id, status, until=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if status:
        cursor.execute('UPDATE users SET is_banned = 1, ban_until = ? WHERE user_id = ?', (until, user_id))
    else:
        cursor.execute('UPDATE users SET is_banned = 0, ban_until = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def create_match(mode, players_ids):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO matches (status, mode) VALUES ("pending", ?)', (mode,))
    match_id = cursor.lastrowid
    
    for uid in players_ids:
        cursor.execute('INSERT INTO match_players (match_id, user_id) VALUES (?, ?)', (match_id, uid))
        
    conn.commit()
    conn.close()
    return match_id

def accept_match_player(match_id, user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE match_players SET accepted = 1 WHERE match_id = ? AND user_id = ?', (match_id, user_id))
    conn.commit()
    conn.close()

def get_match_players(match_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT mp.user_id, u.nickname, u.elo, u.level, mp.accepted 
        FROM match_players mp
        JOIN users u ON mp.user_id = u.user_id
        WHERE mp.match_id = ?
    ''', (match_id,))
    players = cursor.fetchall()
    conn.close()
    return players # [(user_id, nickname, elo, level, accepted), ...]

def cancel_match(match_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE matches SET status = "cancelled" WHERE id = ?', (match_id,))
    conn.commit()
    conn.close()

def get_pending_match(match_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, mode, status FROM matches WHERE id = ? AND status = "pending"', (match_id,))
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
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Убеждаемся, что при добавлении ставим elo 1000 и level 4 (хотя DEFAULT в БД есть, INSERT OR REPLACE может затирать)
    cursor.execute('INSERT OR REPLACE INTO users (user_id, game_id, nickname, elo, level) VALUES (?, ?, ?, 1000, 4)', 
                   (user_id, game_id, nickname))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, game_id, nickname, elo, level, matches, wins, 
               is_banned, ban_until, missed_games, is_vip, vip_until 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_top_players(limit=10):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nickname, elo, level, is_vip FROM users ORDER BY elo DESC LIMIT ?', (limit,))
    players = cursor.fetchall()
    conn.close()
    return players

def update_elo(user_id, elo_change, is_win):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET elo = elo + ?, 
            matches = matches + 1,
            wins = wins + ?
        WHERE user_id = ?
    ''', (elo_change, 1 if is_win else 0, user_id))
    
    # Также обновляем уровень на основе нового ELO
    cursor.execute('SELECT elo FROM users WHERE user_id = ?', (user_id,))
    new_elo = cursor.fetchone()[0]
    new_level = get_level_by_elo(new_elo)
    cursor.execute('UPDATE users SET level = ? WHERE user_id = ?', (new_level, user_id))
    
    conn.commit()
    conn.close()

def manual_update_elo(user_id, elo_change):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET elo = elo + ?
        WHERE user_id = ?
    ''', (elo_change, user_id))
    
    # Also update level based on new ELO
    cursor.execute('SELECT elo FROM users WHERE user_id = ?', (user_id,))
    new_elo = cursor.fetchone()[0]
    new_level = get_level_by_elo(new_elo)
    cursor.execute('UPDATE users SET level = ? WHERE user_id = ?', (new_level, user_id))
    
    conn.commit()
    conn.close()

def adjust_user_stats(user_id, matches_change, wins_change):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET matches = matches + ?,
            wins = wins + ?
        WHERE user_id = ?
    ''', (matches_change, wins_change, user_id))
    conn.commit()
    conn.close()

def create_support_ticket(user_id, text):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO support_tickets (user_id, text) VALUES (?, ?)', (user_id, text))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

def get_support_ticket(ticket_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, text, admin_id, status FROM support_tickets WHERE id = ?', (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    return ticket

def get_all_tickets():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, text, status FROM support_tickets WHERE status = "open"')
    tickets = cursor.fetchall()
    conn.close()
    return tickets

def add_lobby_member(mode, lobby_id, user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO lobby_members (mode, lobby_id, user_id) VALUES (?, ?, ?)', (mode, lobby_id, user_id))
    conn.commit()
    conn.close()

def remove_lobby_member(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM lobby_members WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_all_lobby_members():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT mode, lobby_id, user_id FROM lobby_members')
    members = cursor.fetchall()
    conn.close()
    return members

def update_support_ticket(ticket_id, admin_id=None, status=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if admin_id is not None:
        cursor.execute('UPDATE support_tickets SET admin_id = ? WHERE id = ?', (admin_id, ticket_id))
    if status is not None:
        cursor.execute('UPDATE support_tickets SET status = ? WHERE id = ?', (status, ticket_id))
    conn.commit()
    conn.close()

def close_ticket(ticket_id, admin_id):
    update_support_ticket(ticket_id, admin_id=admin_id, status='closed')

def update_user_profile(user_id, nickname=None, game_id=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if nickname:
        cursor.execute('UPDATE users SET nickname = ? WHERE user_id = ?', (nickname, user_id))
    if game_id:
        cursor.execute('UPDATE users SET game_id = ? WHERE user_id = ?', (game_id, user_id))
    conn.commit()
    conn.close()

def get_user_by_nickname(nickname):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE nickname = ?', (nickname,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_friend(user_id, friend_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        # Check if already friends or pending
        existing = cursor.execute('SELECT status FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                                  (user_id, friend_id, friend_id, user_id)).fetchone()
        if existing:
            return False # Already sent/friends
            
        cursor.execute('INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'pending'))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding friend: {e}")
        return False
    finally:
        conn.close()

def accept_friend(user_id, friend_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # user_id is the one accepting (so friend_id sent the request)
    # The request is stored as (friend_id, user_id, 'pending')
    cursor.execute('UPDATE friends SET status = "accepted" WHERE user_id = ? AND friend_id = ?', (friend_id, user_id))
    if cursor.rowcount == 0:
        # Maybe stored the other way around? Or not found
        cursor.execute('UPDATE friends SET status = "accepted" WHERE user_id = ? AND friend_id = ?', (user_id, friend_id))
        
    conn.commit()
    conn.close()

def remove_friend(user_id, friend_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                   (user_id, friend_id, friend_id, user_id))
    conn.commit()
    conn.close()

def get_friends(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Get all accepted friends
    # Case 1: user_id is requester (user_id, friend_id)
    # Case 2: user_id is receiver (friend_id, user_id)
    cursor.execute('''
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
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Get incoming pending requests (where friend_id is user_id)
    cursor.execute('''
        SELECT u.user_id, u.nickname, u.avatar_url
        FROM users u
        JOIN friends f ON f.user_id = u.user_id
        WHERE f.friend_id = ? AND f.status = "pending"
    ''', (user_id,))
    requests = cursor.fetchall()
    conn.close()
    return requests

def get_friend_status(user_id, other_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, status FROM friends 
        WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (user_id, other_id, other_id, user_id))
    res = cursor.fetchone()
    conn.close()
    if not res: return None
    # Returns (requester_id, status)
    return res

def set_vip_status(user_id, status, until=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if status and until:
        # Проверяем текущий статус для продления
        cursor.execute('SELECT is_vip, vip_until FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        if res and res[0] and res[1]:
            try:
                current_until = datetime.strptime(res[1], "%Y-%m-%d %H:%M:%S")
                if current_until > datetime.now():
                    # Продлеваем: добавляем время к текущему сроку
                    new_until_dt = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
                    # Вычисляем сколько дней добавляем (упрощенно считаем разницу от 'now' до 'until')
                    days_to_add = (new_until_dt - datetime.now()).days
                    if days_to_add < 0: days_to_add = 30 # fallback
                    
                    final_until = (current_until + timedelta(days=days_to_add)).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute('UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?', (final_until, user_id))
                    conn.commit()
                    conn.close()
                    return
            except: pass
            
    cursor.execute('UPDATE users SET is_vip = ?, vip_until = ? WHERE user_id = ?', (1 if status else 0, until, user_id))
    conn.commit()
    conn.close()

def is_user_vip(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_vip, vip_until FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    if not res: return False
    
    is_vip, until = res
    if not is_vip: return False
    
    if until:
        try:
            until_dt = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > until_dt:
                # VIP expired
                set_vip_status(user_id, False)
                return False
        except: pass
        
    return True

def update_clan_stats(clan_id, is_win, elo_change):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE clans 
        SET matches_played = matches_played + 1,
            matches_won = matches_won + ?,
            exp = exp + ?,
            clan_elo = clan_elo + ?
        WHERE id = ?
    ''', (1 if is_win else 0, 50 if is_win else 10, elo_change, clan_id))
    
    # Simple level up logic
    cursor.execute('SELECT exp, level FROM clans WHERE id = ?', (clan_id,))
    exp, level = cursor.fetchone()
    new_level = (exp // 500) + 1
    if new_level > level:
        cursor.execute('UPDATE clans SET level = ? WHERE id = ?', (new_level, clan_id))
        
    conn.commit()
    conn.close()

def get_top_clans(limit=10):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT tag, name, clan_elo, matches_won, matches_played, level 
        FROM clans 
        ORDER BY clan_elo DESC, matches_won DESC 
        LIMIT ?
    ''', (limit,))
    clans = cursor.fetchall()
    conn.close()
    return clans # [(tag, name, elo, won, played, level), ...]

def remove_clan_member(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clan_members WHERE user_id = ?', (user_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_user_by_nickname(nickname):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE nickname = ?', (nickname,))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

def get_user_by_game_id(game_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE game_id = ?', (game_id,))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None
