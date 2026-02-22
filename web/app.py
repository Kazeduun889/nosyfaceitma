from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_file, jsonify
import os
import sys
import json
import random
import logging
from datetime import datetime
import sqlite3

# Add parent directory to path to import db.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'error.log')
logging.basicConfig(filename=log_file, level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s: %(message)s')

# Constants
MAP_POOL = ['Cabbleway', 'Pipeline', 'Bridge', 'Pool', 'Temple', 'Yard', 'Desert']
DATABASE_URL = os.environ.get('DATABASE_URL')
# Ensure IS_POSTGRES is consistent with db.py
try:
    import db
    IS_POSTGRES = db.IS_POSTGRES
except ImportError:
    IS_POSTGRES = bool(DATABASE_URL)

try:
    import db
    # Initialize DB on startup (auto-migrate)
    print("Initializing database...")
    db.init_db()
except ImportError as e:
    print(f"Warning: Could not import db module: {e}")
    logging.error(f"Could not import db module: {e}")
except Exception as e:
    print(f"Error initializing database: {e}")
    logging.error(f"Error initializing database: {e}")

# Explicitly set template and static folders relative to this file
basedir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(basedir, 'templates')
static_dir = os.path.join(basedir, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-key-change-me')

def get_db_connection():
    try:
        import db as database_module
        return database_module.get_db_connection()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        logging.error(f"Error connecting to database: {e}")
        g.db_connect_error = str(e)
        return None

def log_error(e, context=""):
    msg = f"Error in {context}: {e}"
    print(msg)
    logging.error(msg)
    import traceback
    logging.error(traceback.format_exc())


@app.before_request
def check_ban():
    if not request.endpoint or 'static' in request.endpoint:
        return
    
    if 'user_id' in session:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Select is_admin instead of role, as role column does not exist
            db.execute_query(cursor, 'SELECT is_banned, is_admin, ban_expiration FROM users WHERE user_id = ?', (session['user_id'],))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                # Update session admin status (for immediate admin grant effect)
                session['is_admin'] = bool(user['is_admin'])
                
                # Check ban expiration
                if user['is_banned']:
                    import time
                    current_time = int(time.time())
                    ban_expiration = user.get('ban_expiration', 0)
                    
                    if ban_expiration and ban_expiration > 0 and current_time > ban_expiration:
                         # Ban expired
                         conn = get_db_connection()
                         cursor = conn.cursor()
                         db.execute_query(cursor, 'UPDATE users SET is_banned = 0, ban_expiration = 0 WHERE user_id = ?', (session['user_id'],))
                         conn.commit()
                         conn.close()
                         # User is unbanned, continue
                    else:
                        # Allow logout to clear session
                        if request.endpoint == 'logout':
                            return
                            
                        # For API requests, return 403 so frontend can handle it
                        if request.path.startswith('/api/'):
                            return jsonify({'error': 'User is banned', 'is_banned': True}), 403
                            
                        return render_template('banned.html', ban_expiration=ban_expiration)

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    try:
        user = None
        if 'user_id' in session:
            conn = get_db_connection()
            if conn:
                import db  # Ensure db module is available
                cursor = conn.cursor()
                db.execute_query(cursor, 'SELECT * FROM users WHERE user_id = ?', (session['user_id'],))
                user = cursor.fetchone()
                conn.close()
            
            if user is None and 'user_id' in session:
                session.clear()
                return redirect(url_for('index'))
                
        return render_template('index.html', user=user)
    except Exception as e:
        log_error(e, "/")
        return f"<h1>Internal Server Error (Debug)</h1><p>{str(e)}</p>"

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    import db
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Ошибка подключения к базе данных. Попробуйте позже.', 'error')
        return redirect(url_for('index'))

    cursor = conn.cursor()
    
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        avatar_url = request.form.get('avatar_url')
        bio = request.form.get('bio')
        game_id = request.form.get('game_id')
        
        # Validation
        if avatar_url and len(avatar_url) > 500: avatar_url = avatar_url[:500]
        if bio and len(bio) > 1000: bio = bio[:1000]
        if nickname and len(nickname) > 20: nickname = nickname[:20]
        if game_id and len(game_id) > 50: game_id = game_id[:50]
        
        try:
            if nickname:
                # Check uniqueness if changed
                db.execute_query(cursor, 'SELECT nickname FROM users WHERE user_id = ?', (session['user_id'],))
                current_nick_row = cursor.fetchone()
                current_nick = current_nick_row[0] if current_nick_row else None
                
                if nickname != current_nick:
                    db.execute_query(cursor, 'SELECT 1 FROM users WHERE nickname = ?', (nickname,))
                    exists = cursor.fetchone()
                    if exists:
                        flash('Этот никнейм уже занят!', 'error')
                        conn.close()
                        return redirect(url_for('settings'))
                    session['nickname'] = nickname # Update session

            db.execute_query(cursor, 'UPDATE users SET nickname = ?, avatar_url = ?, bio = ?, game_id = ? WHERE user_id = ?',
                         (nickname, avatar_url, bio, game_id, session['user_id']))
            conn.commit()
            flash('Настройки сохранены!', 'success')
        except Exception as e:
            log_error(e, "/settings")
            flash(f'Ошибка: {e}', 'error')
            
    db.execute_query(cursor, 'SELECT * FROM users WHERE user_id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    return render_template('settings.html', user=user)

@app.route('/health')
def health_check():
    return "OK", 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    import db
    if request.method == 'POST':
        user_id = request.form['user_id']
        conn = get_db_connection()
        if not conn:
            error_msg = getattr(g, 'db_connect_error', 'Unknown error')
            flash(f'Database connection failed: {error_msg}', 'error')
            return render_template('login.html')
            
        cursor = conn.cursor()
        db.execute_query(cursor, 'SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user:
            session['user_id'] = user['user_id']
            session['nickname'] = user['nickname']
            
            # Check if profile setup is needed
            if not user.get('game_id'):
                conn.close()
                return redirect(url_for('setup_profile'))
            
            # HARDCODED ADMIN GRANT FOR USER 1562788488
            is_admin = 0
            try:
                is_admin = user['is_admin']
            except (IndexError, KeyError):
                is_admin = 0
                
            if str(user['user_id']) == '1562788488':
                is_admin = 1
                try:
                    # Update DB to make permanent
                    db.execute_query(cursor, "UPDATE users SET is_admin = 1 WHERE user_id = ?", (user['user_id'],))
                    conn.commit()
                except Exception as e:
                    log_error(e, "admin_grant_login")
            
            session['is_admin'] = is_admin
                
            flash('Вы успешно вошли!', 'success')
            conn.close()
            return redirect(url_for('index'))
        else:
            # Auto-register if user not found (for testing/easy access)
            try:
                # Default nickname based on ID
                nickname = f"User_{user_id}"
                
                # Check if this is the admin user
                is_admin = 1 if str(user_id) == '1562788488' else 0
                
                db.execute_query(cursor, 'INSERT INTO users (user_id, nickname, elo, is_admin) VALUES (?, ?, ?, ?)', 
                             (user_id, nickname, 1000, is_admin))
                conn.commit()
                
                # Login immediately
                session['user_id'] = int(user_id)
                session['nickname'] = nickname
                session['is_admin'] = is_admin
                
                flash(f'Аккаунт создан! Пожалуйста, настройте профиль.', 'success')
                conn.close()
                return redirect(url_for('setup_profile'))
            except Exception as e:
                log_error(e, "/login register")
                flash(f'Ошибка регистрации: {e}', 'error')
                conn.close()
            
    return render_template('login.html')

@app.route('/setup_profile', methods=['GET', 'POST'])
def setup_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn: return "DB Error", 500
    
    if request.method == 'POST':
        game_id = request.form['game_id']
        nickname = request.form['nickname']
        
        try:
            cursor = conn.cursor()
            # Update user
            db.execute_query(cursor, 'UPDATE users SET game_id = ?, nickname = ? WHERE user_id = ?', 
                           (game_id, nickname, session['user_id']))
            conn.commit()
            
            # Update session
            session['nickname'] = nickname
            
            flash('Профиль успешно настроен!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            log_error(e, "/setup_profile")
            flash(f'Ошибка сохранения: {e}', 'error')
        finally:
            conn.close()
            
    conn.close()
    return render_template('setup_profile.html')

@app.route('/debug/update_db')
def update_db():
    try:
        # Re-import db to ensure we have latest version
        import sys
        if 'db' in sys.modules:
            import importlib
            importlib.reload(sys.modules['db'])
        else:
            import db
            
        db.init_db()
        return "Database updated successfully! <a href='/'>Go Home</a>"
    except Exception as e:
        return f"Error updating database: {e}"

@app.route('/debug/reset_all')
def reset_all_data():
    if not session.get('is_admin'):
        return "Access denied. Only admins can reset the database."
        
    try:
        conn = get_db_connection()
        if not conn: return "DB Connection Error"
        
        cursor = conn.cursor()
        # Wipe all data but keep tables
        tables = [
            'users', 'matches', 'match_players', 'support_tickets', 'lobby_members',
            'clans', 'clan_members', 'polls', 'poll_options', 'poll_votes',
            'clan_matchmaking_queue', 'clan_matches', 'matchmaking_queue', 
            'match_stats', 'match_chat'
        ]
        
        for table in tables:
            try:
                db.execute_query(cursor, f'DELETE FROM {table}')
                # Reset auto-increment
                if not IS_POSTGRES:
                    try:
                        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                    except Exception: pass
            except (sqlite3.OperationalError, Exception):
                pass # Table might not exist yet
                
        conn.commit()
        conn.close()
        
        session.clear() # Logout everyone
        return "ALL DATA WIPED! Site is fresh. <a href='/'>Go Home</a>"
    except Exception as e:
        log_error(e, "/debug/reset_all")
        return f"Error resetting database: {e}"

@app.route('/debug/make_me_admin/<secret_key>')
def make_me_admin_route(secret_key):
    import db
    if secret_key != 'super-admin-secret':
        return "Invalid secret key"
        
    if 'user_id' not in session:
        return "Please login first"
        
    conn = get_db_connection()
    if not conn: return "DB Connection Error"
    
    try:
        cursor = conn.cursor()
        # Use execute_query to handle placeholders correctly
        db.execute_query(cursor, 'UPDATE users SET is_admin = 1 WHERE user_id = ?', (session['user_id'],))
        conn.commit()
        session['is_admin'] = 1
        return "You are now an admin! <a href='/'>Go Home</a>"
    except Exception as e:
        log_error(e, "/debug/make_me_admin")
        return f"Error: {e}"
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

@app.route('/matches')
def matches():
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    cursor = conn.cursor()
    
    if session.get('is_admin'):
        # Admin: Show all matches
        db.execute_query(cursor, '''
            SELECT m.*, 
            (SELECT COUNT(*) FROM match_players WHERE match_id = m.id) as player_count
            FROM matches m 
            ORDER BY m.created_at DESC LIMIT 50
        ''')
    elif 'user_id' in session:
        # User: Show only their matches
        db.execute_query(cursor, '''
            SELECT m.*, mp.has_left, mp.is_annulled,
            (SELECT COUNT(*) FROM match_players WHERE match_id = m.id) as player_count
            FROM matches m 
            JOIN match_players mp ON m.id = mp.match_id
            WHERE mp.user_id = ?
            ORDER BY m.created_at DESC LIMIT 50
        ''', (session['user_id'],))
    else:
        # Guest: Redirect or empty
        conn.close()
        flash('Пожалуйста, войдите в систему для просмотра истории матчей.', 'warning')
        return redirect(url_for('login'))
        
    matches = cursor.fetchall()
    conn.close()
    return render_template('matches.html', matches=matches)

@app.route('/matches/<int:match_id>')
def match_detail(match_id):
    conn = get_db_connection()
    if not conn:
        return "DB Error", 500
        
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
    match = cursor.fetchone()
    
    if not match:
        conn.close()
        return "Match not found", 404
        
    # Get players with team info (if available)
    db.execute_query(cursor, '''
        SELECT mp.*, u.nickname, u.elo, u.avatar_url, ms.kills, ms.deaths, c.tag as clan_tag
        FROM match_players mp
        JOIN users u ON mp.user_id = u.user_id
        LEFT JOIN match_stats ms ON ms.match_id = mp.match_id AND ms.user_id = mp.user_id
        LEFT JOIN clan_members cm ON cm.user_id = u.user_id
        LEFT JOIN clans c ON c.id = cm.clan_id
        WHERE mp.match_id = ?
    ''', (match_id,))
    players = cursor.fetchall()
    
    conn.close()
    return render_template('match_detail.html', match=match, players=players)

@app.route('/u/<nickname>')
def user_profile(nickname):
    import db
    conn = get_db_connection()
    if not conn: return "DB Error", 500
    
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT * FROM users WHERE nickname = ?', (nickname,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return "User not found", 404
        
    friend_status = None
    if 'user_id' in session and session['user_id'] != user['user_id']:
        # Check friend status
        db.execute_query(cursor, '''
            SELECT user_id, status FROM friends 
            WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
        ''', (session['user_id'], user['user_id'], user['user_id'], session['user_id']))
        res = cursor.fetchone()
        if res:
            friend_status = (res['user_id'], res['status']) # (requester_id, status)
            
    # Get user's recent matches
    db.execute_query(cursor, '''
        SELECT m.*, mp.team, mp.is_annulled, mp.accepted, mp.has_left,
               (CASE WHEN m.winner_team = mp.team THEN 1 ELSE 0 END) as is_win
        FROM matches m
        JOIN match_players mp ON m.id = mp.match_id
        WHERE mp.user_id = ?
        ORDER BY m.created_at DESC
        LIMIT 10
    ''', (user['user_id'],))
    recent_matches = cursor.fetchall()
            
    conn.close()
    return render_template('user_profile.html', user=user, friend_status=friend_status, recent_matches=recent_matches)

@app.route('/friends')
def friends_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    cursor = conn.cursor()
    user_id = session['user_id']
    
    # Get accepted friends
    db.execute_query(cursor, '''
        SELECT u.user_id, u.nickname, u.avatar_url, u.elo, u.is_vip
        FROM users u
        JOIN friends f ON (f.friend_id = u.user_id AND f.user_id = ?) 
                       OR (f.user_id = u.user_id AND f.friend_id = ?)
        WHERE f.status = 'accepted'
    ''', (user_id, user_id))
    friends = cursor.fetchall()
    
    # Get pending requests (incoming)
    db.execute_query(cursor, '''
        SELECT u.user_id, u.nickname, u.avatar_url
        FROM users u
        JOIN friends f ON f.user_id = u.user_id
        WHERE f.friend_id = ? AND f.status = 'pending'
    ''', (user_id,))
    requests = cursor.fetchall()
    
    conn.close()
    return render_template('friends.html', friends=friends, requests=requests)

@app.route('/friends/add/<int:friend_id>', methods=['POST'])
def add_friend(friend_id):
    import db
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    try:
        cursor = conn.cursor()
        # Check if already friends
        db.execute_query(cursor, 'SELECT 1 FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                                (session['user_id'], friend_id, friend_id, session['user_id']))
        existing = cursor.fetchone()
        
        if not existing:
            db.execute_query(cursor, 'INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (session['user_id'], friend_id, 'pending'))
            conn.commit()
            flash('Запрос отправлен!', 'success')
        else:
            flash('Запрос уже отправлен или вы уже друзья', 'info')
    except Exception as e:
        log_error(e, "/friends/add")
        flash(f'Error: {e}', 'error')
    finally:
        conn.close()
        
    return redirect(request.referrer or url_for('friends_list'))

@app.route('/friends/accept/<int:friend_id>', methods=['POST'])
def accept_friend(friend_id):
    import db
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    try:
        cursor = conn.cursor()
        db.execute_query(cursor, "UPDATE friends SET status = 'accepted' WHERE user_id = ? AND friend_id = ?", (friend_id, session['user_id']))
        conn.commit()
        flash('Запрос принят!', 'success')
    except Exception as e:
        log_error(e, "/friends/accept")
        flash(f'Error: {e}', 'error')
    finally:
        conn.close()
        
    return redirect(request.referrer or url_for('friends_list'))

@app.route('/friends/remove/<int:friend_id>', methods=['POST'])
def remove_friend(friend_id):
    import db
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    try:
        cursor = conn.cursor()
        db.execute_query(cursor, 'DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                     (session['user_id'], friend_id, friend_id, session['user_id']))
        conn.commit()
        flash('Пользователь удален из друзей', 'info')
    except Exception as e:
        log_error(e, "/friends/remove")
        flash(f'Error: {e}', 'error')
    finally:
        conn.close()
        
    return redirect(request.referrer or url_for('friends_list'))

@app.route('/leaderboard')
def leaderboard():
    import db
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    cursor = conn.cursor()
    # Join with clans to get tags
    db.execute_query(cursor, '''
        SELECT u.*, c.tag as clan_tag 
        FROM users u 
        LEFT JOIN clan_members cm ON u.user_id = cm.user_id 
        LEFT JOIN clans c ON cm.clan_id = c.id 
        ORDER BY u.elo DESC LIMIT 50
    ''')
    users = cursor.fetchall()
    conn.close()
    return render_template('leaderboard.html', users=users)

# === CLAN SYSTEM ===

@app.route('/clans')
def clans():
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT * FROM clans ORDER BY clan_elo DESC')
    clans = cursor.fetchall()
    
    user_clan = None
    if 'user_id' in session:
        db.execute_query(cursor, '''
            SELECT c.* FROM clans c 
            JOIN clan_members cm ON c.id = cm.clan_id 
            WHERE cm.user_id = ?
        ''', (session['user_id'],))
        user_clan = cursor.fetchone()
        
    conn.close()
    return render_template('clans.html', clans=clans, user_clan=user_clan)

@app.route('/clans/create', methods=['GET', 'POST'])
def create_clan():
    import db
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('clans'))
    
    cursor = conn.cursor()
    
    # Check if user is already in a clan
    db.execute_query(cursor, 'SELECT * FROM clan_members WHERE user_id = ?', (session['user_id'],))
    existing_clan = cursor.fetchone()
    
    if existing_clan:
        conn.close()
        flash('Вы уже состоите в клане', 'error')
        return redirect(url_for('clans'))

    if request.method == 'POST':
        tag = request.form['tag'].upper()
        name = request.form['name']
        
        if not tag or not name:
            flash('Заполните все поля', 'error')
        elif len(tag) > 5:
            flash('Тег не может быть длиннее 5 символов', 'error')
        else:
            try:
                if IS_POSTGRES:
                    db.execute_query(cursor, 'INSERT INTO clans (tag, name, owner_id) VALUES (?, ?, ?) RETURNING id', (tag, name, session['user_id']))
                    clan_id = cursor.fetchone()[0]
                else:
                    db.execute_query(cursor, 'INSERT INTO clans (tag, name, owner_id) VALUES (?, ?, ?)', (tag, name, session['user_id']))
                    clan_id = cursor.lastrowid
                
                db.execute_query(cursor, 'INSERT INTO clan_members (clan_id, user_id, role) VALUES (?, ?, ?)', (clan_id, session['user_id'], 'owner'))
                
                conn.commit()
                flash('Клан успешно создан!', 'success')
                return redirect(url_for('clan_detail', clan_id=clan_id))
            except (sqlite3.IntegrityError, db.IntegrityError):
                flash('Клан с таким тегом уже существует', 'error')
            except Exception as e:
                log_error(e, "/clans/create")
                flash(f'Ошибка создания клана: {e}', 'error')
                
    conn.close()
    return render_template('create_clan.html')

@app.route('/clans/<int:clan_id>')
def clan_detail(clan_id):
    import db
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('clans'))
        
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT * FROM clans WHERE id = ?', (clan_id,))
    clan = cursor.fetchone()
    
    if not clan:
        conn.close()
        flash('Клан не найден', 'error')
        return redirect(url_for('clans'))
        
    db.execute_query(cursor, '''
        SELECT u.nickname, u.elo, cm.role, u.user_id
        FROM clan_members cm
        JOIN users u ON cm.user_id = u.user_id
        WHERE cm.clan_id = ?
    ''', (clan_id,))
    members = cursor.fetchall()
    
    is_member = False
    is_owner = False
    if 'user_id' in session:
        db.execute_query(cursor, 'SELECT * FROM clan_members WHERE clan_id = ? AND user_id = ?', (clan_id, session['user_id']))
        member_record = cursor.fetchone()
        if member_record:
            is_member = True
            if member_record['role'] == 'owner':
                is_owner = True
                
    conn.close()
    return render_template('clan_detail.html', clan=clan, members=members, is_member=is_member, is_owner=is_owner)

@app.route('/clans/<int:clan_id>/join', methods=['POST'])
def join_clan(clan_id):
    import db
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('clans'))
        
    cursor = conn.cursor()
    
    # Check if user is already in ANY clan
    db.execute_query(cursor, 'SELECT * FROM clan_members WHERE user_id = ?', (session['user_id'],))
    existing_clan = cursor.fetchone()
    if existing_clan:
        conn.close()
        flash('Вы уже состоите в клане', 'error')
        return redirect(url_for('clans'))
        
    try:
        db.execute_query(cursor, 'INSERT INTO clan_members (clan_id, user_id) VALUES (?, ?)', (clan_id, session['user_id']))
        conn.commit()
        flash('Вы вступили в клан!', 'success')
    except Exception as e:
        log_error(e, "/clans/join")
        flash(f'Ошибка вступления: {e}', 'error')
        
    conn.close()
    return redirect(url_for('clan_detail', clan_id=clan_id))

@app.route('/clans/<int:clan_id>/leave', methods=['POST'])
def leave_clan(clan_id):
    import db
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('clans'))
        
    cursor = conn.cursor()
    
    # Check if user is owner
    db.execute_query(cursor, 'SELECT * FROM clan_members WHERE clan_id = ? AND user_id = ?', (clan_id, session['user_id']))
    member = cursor.fetchone()
    
    if member and member['role'] == 'owner':
        conn.close()
        flash('Владелец не может покинуть клан. Удалите клан или передайте права.', 'error')
        return redirect(url_for('clan_detail', clan_id=clan_id))
        
    try:
        db.execute_query(cursor, 'DELETE FROM clan_members WHERE clan_id = ? AND user_id = ?', (clan_id, session['user_id']))
        conn.commit()
        flash('Вы покинули клан', 'info')
    except Exception as e:
        log_error(e, "/clans/leave")
        flash(f'Error: {e}', 'error')
        
    conn.close()
    return redirect(url_for('clans'))

@app.route('/clans/matchmaking')
def clan_matchmaking():
    import db
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('clans'))
        
    cursor = conn.cursor()
    
    # Get user's clan and role
    db.execute_query(cursor, '''
        SELECT c.id, c.name, cm.role 
        FROM clan_members cm
        JOIN clans c ON cm.clan_id = c.id
        WHERE cm.user_id = ?
    ''', (session['user_id'],))
    user_clan_info = cursor.fetchone()
    
    if not user_clan_info:
        conn.close()
        flash('Вы должны состоять в клане', 'error')
        return redirect(url_for('clans'))
        
    if user_clan_info['role'] != 'owner':
        conn.close()
        flash('Только лидер клана может искать матчи', 'error')
        return redirect(url_for('clan_detail', clan_id=user_clan_info['id']))
        
    # Check queue status
    db.execute_query(cursor, 'SELECT * FROM clan_matchmaking_queue WHERE clan_id = ?', (user_clan_info['id'],))
    in_queue = cursor.fetchone()
    
    # Find active matches
    db.execute_query(cursor, '''
        SELECT * FROM clan_matches 
        WHERE (clan1_id = ? OR clan2_id = ?) AND status = 'active'
    ''', (user_clan_info['id'], user_clan_info['id']))
    active_match = cursor.fetchone()
    
    opponent = None
    if active_match:
        opponent_id = active_match['clan2_id'] if active_match['clan1_id'] == user_clan_info['id'] else active_match['clan1_id']
        db.execute_query(cursor, 'SELECT * FROM clans WHERE id = ?', (opponent_id,))
        opponent = cursor.fetchone()
        
    conn.close()
    return render_template('clan_matchmaking.html', clan=user_clan_info, in_queue=bool(in_queue), active_match=active_match, opponent=opponent)

@app.route('/clans/matchmaking/join', methods=['POST'])
def join_clan_queue():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('clans'))
        
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT clan_id, role FROM clan_members WHERE user_id = ?', (session['user_id'],))
    user_clan_info = cursor.fetchone()
    
    if not user_clan_info or user_clan_info['role'] != 'owner':
        conn.close()
        return redirect(url_for('clans'))
        
    # Check if user is in an active 1v1 match
    db.execute_query(cursor, '''
        SELECT m.id FROM matches m
        JOIN match_players mp ON m.id = mp.match_id
        WHERE mp.user_id = ? AND m.status = 'active'
    ''', (session['user_id'],))
    active_match_1v1 = cursor.fetchone()
    
    if active_match_1v1:
        conn.close()
        flash("Вы не можете искать клановый матч, пока находитесь в активном 1v1 матче!", "error")
        return redirect(url_for('match_room', match_id=active_match_1v1['id']))

    # Check if clan is already in an active clan match
    db.execute_query(cursor, '''
        SELECT id FROM clan_matches 
        WHERE (clan1_id = ? OR clan2_id = ?) AND status = 'active'
    ''', (user_clan_info['clan_id'], user_clan_info['clan_id']))
    active_clan_match = cursor.fetchone()
    
    if active_clan_match:
        conn.close()
        flash("Ваш клан уже находится в активном матче!", "error")
        return redirect(url_for('clan_matchmaking'))
        
    clan_id = user_clan_info['clan_id']
    
    # Check if anyone else is in queue
    db.execute_query(cursor, 'SELECT * FROM clan_matchmaking_queue WHERE clan_id != ? ORDER BY joined_at ASC LIMIT 1', (clan_id,))
    opponent_entry = cursor.fetchone()
    
    if opponent_entry:
        # Match found!
        opponent_id = opponent_entry['clan_id']
        
        # Remove opponent from queue
        db.execute_query(cursor, 'DELETE FROM clan_matchmaking_queue WHERE clan_id = ?', (opponent_id,))
        
        # Create match
        db.execute_query(cursor, 'INSERT INTO clan_matches (clan1_id, clan2_id) VALUES (?, ?)', (clan_id, opponent_id))
        conn.commit()
        flash('Матч найден!', 'success')
    else:
        # Add to queue
        try:
            db.execute_query(cursor, 'INSERT INTO clan_matchmaking_queue (clan_id) VALUES (?)', (clan_id,))
            conn.commit()
            flash('Вы добавлены в очередь поиска', 'info')
        except (sqlite3.IntegrityError, db.IntegrityError):
            pass # Already in queue
        except Exception as e:
            log_error(e, "/clans/matchmaking/join")
            flash(f'Error: {e}', 'error')
            
    conn.close()
    return redirect(url_for('clan_matchmaking'))

@app.route('/clans/matchmaking/leave', methods=['POST'])
def leave_clan_queue():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('clans'))
        
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT clan_id, role FROM clan_members WHERE user_id = ?', (session['user_id'],))
    user_clan_info = cursor.fetchone()
    
    if user_clan_info and user_clan_info['role'] == 'owner':
        try:
            db.execute_query(cursor, 'DELETE FROM clan_matchmaking_queue WHERE clan_id = ?', (user_clan_info['clan_id'],))
            conn.commit()
            flash('Вы покинули очередь', 'info')
        except Exception as e:
            log_error(e, "/clans/matchmaking/leave")
            flash(f'Error: {e}', 'error')
        
    conn.close()
    return redirect(url_for('clan_matchmaking'))

# === ADMIN PANEL ===

@app.route('/admin')
def admin_dashboard():
    import db
    if not session.get('is_admin'):
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('index'))
        
    cursor = conn.cursor()
    
    # Stats for dashboard
    db.execute_query(cursor, 'SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    
    db.execute_query(cursor, 'SELECT COUNT(*) FROM clans')
    clans_count = cursor.fetchone()[0]
    
    db.execute_query(cursor, 'SELECT COUNT(*) FROM matches')
    matches_count_1 = cursor.fetchone()[0]
    
    db.execute_query(cursor, 'SELECT COUNT(*) FROM clan_matches')
    matches_count_2 = cursor.fetchone()[0]
    
    stats = {
        'users_count': users_count,
        'clans_count': clans_count,
        'matches_count': matches_count_1 + matches_count_2,
    }
    
    # Recent items
    db.execute_query(cursor, 'SELECT * FROM users ORDER BY user_id DESC LIMIT 5')
    recent_users = cursor.fetchall()
    
    db.execute_query(cursor, 'SELECT * FROM clans ORDER BY created_at DESC LIMIT 5')
    recent_clans = cursor.fetchall()
    
    conn.close()
    return render_template('admin/dashboard.html', stats=stats, users=recent_users, clans=recent_clans)

@app.route('/admin/download_db')
def download_db():
    if not session.get('is_admin'): return redirect(url_for('index'))
    try:
        return send_file(os.path.join(app.root_path, '..', 'database.db'), as_attachment=True)
    except Exception as e:
        # Fallback for different path structure
        try:
            return send_file('database.db', as_attachment=True)
        except Exception as e2:
            return f"Error downloading database: {e}, {e2}"

@app.route('/admin/users')
def admin_users():
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn: return redirect(url_for('index'))
    
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT * FROM users ORDER BY elo DESC')
    users = cursor.fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/ban', methods=['POST'])
def admin_ban_user(user_id):
    import db
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        flash(f'Пользователь {user_id} заблокирован', 'success')
    except Exception as e:
        log_error(e, "/admin/ban")
        flash(f'Error: {e}', 'error')
        
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/unban', methods=['POST'])
def admin_unban_user(user_id):
    import db
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        flash(f'Пользователь {user_id} разблокирован', 'success')
    except Exception as e:
        log_error(e, "/admin/unban")
        flash(f'Error: {e}', 'error')
        
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/make_admin', methods=['POST'])
def admin_make_admin(user_id):
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'UPDATE users SET is_admin = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        flash(f'Пользователь {user_id} теперь АДМИНИСТРАТОР', 'success')
    except Exception as e:
        log_error(e, "/admin/make_admin")
        flash(f'Error: {e}', 'error')
        
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/revoke_admin', methods=['POST'])
def admin_revoke_admin(user_id):
    import db
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    # Prevent removing admin from self (optional safety)
    if user_id == session['user_id']:
        flash('Вы не можете снять админку с самого себя!', 'error')
        return redirect(url_for('admin_users'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'UPDATE users SET is_admin = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        flash(f'Пользователь {user_id} больше не администратор', 'info')
    except Exception as e:
        log_error(e, "/admin/revoke_admin")
        flash(f'Error: {e}', 'error')
        
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
def admin_edit_user(user_id):
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    nickname = request.form.get('nickname')
    elo = request.form.get('elo')
    
    conn = get_db_connection()
    if not conn: return redirect(url_for('index'))
    
    try:
        cursor = conn.cursor()
        if nickname:
            db.execute_query(cursor, 'UPDATE users SET nickname = ? WHERE user_id = ?', (nickname, user_id))
        if elo:
            db.execute_query(cursor, 'UPDATE users SET elo = ? WHERE user_id = ?', (elo, user_id))
        conn.commit()
        flash(f'Данные пользователя {user_id} обновлены', 'success')
    except Exception as e:
        log_error(e, "/admin/edit_user")
        flash(f'Ошибка обновления: {e}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('admin_users'))

@app.route('/admin/clans')
def admin_clans():
    import db
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn: return redirect(url_for('index'))
    
    cursor = conn.cursor()
    db.execute_query(cursor, 'SELECT * FROM clans ORDER BY created_at DESC')
    clans = cursor.fetchall()
    conn.close()
    return render_template('admin/clans.html', clans=clans)

@app.route('/admin/clans/<int:clan_id>/delete', methods=['POST'])
def admin_delete_clan(clan_id):
    import db
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'DELETE FROM clan_members WHERE clan_id = ?', (clan_id,))
        db.execute_query(cursor, 'DELETE FROM clans WHERE id = ?', (clan_id,))
        conn.commit()
        conn.close()
        flash(f'Клан удален', 'success')
    except Exception as e:
        log_error(e, "/admin/delete_clan")
        flash(f'Error: {e}', 'error')
        
    return redirect(url_for('admin_clans'))

# === PLAYER MATCHMAKING ===

@app.route('/play')
def play():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed", "error")
            return redirect(url_for('index'))
            
        cursor = conn.cursor()
        
        # Check if already in match
        db.execute_query(cursor, '''
            SELECT m.* FROM matches m
            JOIN match_players mp ON m.id = mp.match_id
            WHERE mp.user_id = ? AND m.status = 'active'
        ''', (session['user_id'],))
        active_match = cursor.fetchone()
        
        if active_match:
            conn.close()
            return redirect(url_for('match_room', match_id=active_match['id']))
        
        # Check queue
        db.execute_query(cursor, 'SELECT * FROM matchmaking_queue WHERE user_id = ?', (session['user_id'],))
        in_queue = cursor.fetchone()
        
        db.execute_query(cursor, 'SELECT COUNT(*) FROM matchmaking_queue')
        queue_count_row = cursor.fetchone()
        queue_count = queue_count_row[0] if queue_count_row else 0
        
        conn.close()
        return render_template('play.html', in_queue=bool(in_queue), queue_count=queue_count)
    except Exception as e:
        log_error(e, "/play")
        flash(f"Error loading play page: {e}", "error")
        return redirect(url_for('index'))

@app.route('/play/join_queue', methods=['POST'])
def join_queue():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if not conn: 
            flash("Database connection failed", "error")
            return redirect(url_for('play'))
        
        cursor = conn.cursor()
        
        # CRITICAL FIX: Check if already in an active match BEFORE joining queue
        db.execute_query(cursor, '''
            SELECT m.id FROM matches m
            JOIN match_players mp ON m.id = mp.match_id
            WHERE mp.user_id = ? AND m.status = 'active'
        ''', (session['user_id'],))
        active_match = cursor.fetchone()
        
        if active_match:
            conn.close()
            flash("Вы уже находитесь в активном матче!", "warning")
            return redirect(url_for('match_room', match_id=active_match['id']))
            
        # Check if user's clan is in an active match (if they are in a clan) - DISABLED TEMPORARILY AS CLAN WARS IS IN DEV
        # db.execute_query(cursor, 'SELECT clan_id FROM clan_members WHERE user_id = ?', (session['user_id'],))
        # clan_member = cursor.fetchone()
        
        # if clan_member:
        #      db.execute_query(cursor, "SELECT id FROM clan_matches WHERE (clan1_id = ? OR clan2_id = ?) AND status = 'active'", (clan_member['clan_id'], clan_member['clan_id']))
        #      active_clan_match = cursor.fetchone()
        #      if active_clan_match:
        #          conn.close()
        #          flash("Ваш клан находится в активном матче! Вы не можете искать 1v1.", "warning")
        #          return redirect(url_for('clan_matchmaking'))
        
        # Check if already in queue
        db.execute_query(cursor, 'SELECT * FROM matchmaking_queue WHERE user_id = ?', (session['user_id'],))
        existing_queue = cursor.fetchone()
        if existing_queue:
            conn.close()
            return redirect(url_for('play'))

        # Check if opponent exists
        db.execute_query(cursor, 'SELECT * FROM matchmaking_queue WHERE user_id != ? ORDER BY joined_at ASC LIMIT 1', (session['user_id'],))
        opponent = cursor.fetchone()
        
        if opponent:
            # Match found!
            opponent_id = opponent['user_id']
            db.execute_query(cursor, 'DELETE FROM matchmaking_queue WHERE user_id = ?', (opponent_id,))
            
            # Create match
            match_id = None
            import time
            current_time = int(time.time())
            try:
                if IS_POSTGRES:
                    db.execute_query(cursor, "INSERT INTO matches (mode, status, last_action_time) VALUES ('1x1', 'active', ?) RETURNING id", (current_time,))
                    match_id = cursor.fetchone()[0]
                else:
                    db.execute_query(cursor, "INSERT INTO matches (mode, status, last_action_time) VALUES ('1x1', 'active', ?)", (current_time,))
                    match_id = cursor.lastrowid
            except Exception as e:
                log_error(e, "create_match_failed")
                conn.rollback()
                flash(f"Failed to create match: {e}", "error")
                return redirect(url_for('play'))

            if not match_id:
                flash("Failed to create match ID", "error")
                conn.rollback()
                return redirect(url_for('play'))
            
            # Add players
            # execute_query handles placeholder conversion for us (using ? is fine)
            # Assign teams: User=1, Opponent=2
            db.execute_query(cursor, "INSERT INTO match_players (match_id, user_id, accepted, team) VALUES (?, ?, 1, 1)", (match_id, session['user_id']))
            db.execute_query(cursor, "INSERT INTO match_players (match_id, user_id, accepted, team) VALUES (?, ?, 1, 2)", (match_id, opponent_id))
            
            conn.commit()
            flash('Матч найден! Переход в комнату...', 'success')
            conn.close()
            return redirect(url_for('match_room', match_id=match_id))
            
        else:
            # Add to queue
            try:
                if IS_POSTGRES:
                     db.execute_query(cursor, 'INSERT INTO matchmaking_queue (user_id) VALUES (?) ON CONFLICT (user_id) DO NOTHING', (session['user_id'],))
                else:
                     db.execute_query(cursor, 'INSERT OR IGNORE INTO matchmaking_queue (user_id) VALUES (?)', (session['user_id'],))
                conn.commit()
            except Exception as e:
                # Fallback for generic insert error
                log_error(e, "/play/join_queue insert")
                pass
                
        conn.close()
        return redirect(url_for('play'))
    except Exception as e:
        log_error(e, "/play/join_queue")
        flash(f"Error joining queue: {e}", "error")
        return redirect(url_for('play'))

@app.route('/play/leave_queue', methods=['POST'])
def leave_queue():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if not conn: 
            flash("Database connection failed", "error")
            return redirect(url_for('play'))
        
        cursor = conn.cursor()
        db.execute_query(cursor, 'DELETE FROM matchmaking_queue WHERE user_id = ?', (session['user_id'],))
        conn.commit()
        conn.close()
    except Exception as e:
        log_error(e, "/play/leave_queue")
        flash(f"Error leaving queue: {e}", "error")
        
    return redirect(url_for('play'))




@app.route('/api/match/<int:match_id>/winner', methods=['POST'])
def api_match_set_winner(match_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        data = request.json
        winner_id = data.get('winner_id')
        
        conn = get_db_connection()
        if not conn: return jsonify({'error': 'Database error'}), 500
        
        cursor = conn.cursor()
        
        # Verify match exists and is active
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        
        if not match or match['status'] != 'active':
            conn.close()
            return jsonify({'error': 'Match not active or not found'}), 400
            
        # Verify winner is in match
        db.execute_query(cursor, 'SELECT team FROM match_players WHERE match_id = ? AND user_id = ?', (match_id, winner_id))
        winner_player = cursor.fetchone()
        
        if not winner_player:
            conn.close()
            return jsonify({'error': 'Winner not in match'}), 400
            
        winner_team = winner_player['team']
        
        # Update match status
        db.execute_query(cursor, "UPDATE matches SET status = 'finished', winner_team = ? WHERE id = ?", (winner_id, match_id))
        
        # Update ELO (simplified)
        db.execute_query(cursor, 'SELECT user_id, team, is_annulled FROM match_players WHERE match_id = ?', (match_id,))
        players = cursor.fetchall()
        
        for p in players:
            if p['is_annulled']:
                continue
                
            change = 25 if p['user_id'] == int(winner_id) else -25
            db.execute_query(cursor, 'UPDATE users SET elo = elo + ? WHERE user_id = ?', (change, p['user_id']))
            
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        log_error(e, "/api/match/winner")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/clan/<int:clan_id>/delete', methods=['POST'])
def api_admin_delete_clan(clan_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        db.execute_query(cursor, 'DELETE FROM clan_members WHERE clan_id = ?', (clan_id,))
        db.execute_query(cursor, 'DELETE FROM clans WHERE id = ?', (clan_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        log_error(e, "/api/admin/clan/delete")
        return jsonify({'error': str(e)}), 500

@app.route('/match/<int:match_id>')
def match_room(match_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed", "error")
            return redirect(url_for('play'))
            
        cursor = conn.cursor()
        
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        
        if not match:
            conn.close()
            flash('Match not found', 'error')
            return redirect(url_for('play'))

        db.execute_query(cursor, '''
            SELECT u.*, mp.accepted, mp.team, mp.is_annulled, mp.has_left, c.tag as clan_tag
            FROM match_players mp 
            JOIN users u ON mp.user_id = u.user_id 
            LEFT JOIN clan_members cm ON cm.user_id = u.user_id
            LEFT JOIN clans c ON c.id = cm.clan_id
            WHERE mp.match_id = ?
            ORDER BY mp.team ASC
        ''', (match_id,))
        players = cursor.fetchall()
        
        # Initialize Veto if not started and match is active
        # Check if veto_status is None or empty
        veto_status_raw = match['veto_status']
        if match['status'] == 'active' and not veto_status_raw:
            veto_status = {m: 'available' for m in MAP_POOL}
            # Random first turn
            first_turn = players[0]['user_id'] if players else session['user_id']
            
            # Use json.dumps for the dict
            veto_json = json.dumps(veto_status)
            
            db.execute_query(cursor, 'UPDATE matches SET veto_status = ?, current_veto_turn = ? WHERE id = ?',
                         (veto_json, first_turn, match_id))
            conn.commit()
            # Refresh match data
            db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
            match = cursor.fetchone()
            
        # Parse veto status
        veto_data = {}
        if match['veto_status']:
            if isinstance(match['veto_status'], str):
                try:
                    veto_data = json.loads(match['veto_status'])
                except:
                    veto_data = {}
            else:
                # If it's already a dict (some drivers might do this, though unlikely with sqlite/psycopg2 unless configured)
                veto_data = match['veto_status']
        
        # Get chat messages
        db.execute_query(cursor, '''
            SELECT mc.*, u.nickname, u.avatar_url 
            FROM match_chat mc
            JOIN users u ON mc.user_id = u.user_id
            WHERE mc.match_id = ?
            ORDER BY mc.created_at ASC
        ''', (match_id,))
        chat_messages = cursor.fetchall()
        
        conn.close()
        return render_template('match_room.html', match=match, players=players, veto_data=veto_data, map_pool=MAP_POOL, chat_messages=chat_messages)

    except Exception as e:
        log_error(e, "/match_room")
        flash(f"Error loading match room: {e}", "error")
        return redirect(url_for('play'))




@app.route('/match/<int:match_id>/chat', methods=['POST'])
def match_chat(match_id):
    import db
    if 'user_id' not in session: return redirect(url_for('login'))
    
    try:
        message = request.form.get('message')
        if message and len(message.strip()) > 0:
            conn = get_db_connection()
            if not conn: 
                flash("Database connection failed", "error")
                return redirect(url_for('match_room', match_id=match_id))
            
            cursor = conn.cursor()
            db.execute_query(cursor, 'INSERT INTO match_chat (match_id, user_id, message) VALUES (?, ?, ?)',
                         (match_id, session['user_id'], message.strip()))
            conn.commit()
            conn.close()
    except Exception as e:
        log_error(e, "/match_chat")
        flash(f"Error sending message: {e}", "error")
        
    return redirect(url_for('match_room', match_id=match_id))

@app.route('/match/<int:match_id>/veto', methods=['POST'])
def match_veto(match_id):
    import db
    if 'user_id' not in session: return redirect(url_for('login'))
    
    try:
        map_name = request.form.get('map_name')
        conn = get_db_connection()
        if not conn: 
            flash("Database connection failed", "error")
            return redirect(url_for('match_room', match_id=match_id))
        
        cursor = conn.cursor()
        
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        
        if not match or match['status'] != 'active':
            conn.close()
            return redirect(url_for('match_room', match_id=match_id))
            
        # Check turn
        if str(match['current_veto_turn']) != str(session['user_id']):
            flash('Сейчас не ваш ход!', 'error')
            conn.close()
            return redirect(url_for('match_room', match_id=match_id))
            
        veto_data = {}
        if match['veto_status']:
             if isinstance(match['veto_status'], str):
                 veto_data = json.loads(match['veto_status'])
             else:
                 veto_data = match['veto_status']
        
        if veto_data.get(map_name) == 'available':
            # Ban map
            veto_data[map_name] = 'banned'
            
            # Check remaining maps
            available_maps = [m for m, s in veto_data.items() if s == 'available']
            
            veto_json = json.dumps(veto_data)
            
            if len(available_maps) == 1:
                # Last map picked!
                last_map = available_maps[0]
                veto_data[last_map] = 'picked'
                veto_json = json.dumps(veto_data) # Update json with picked status
                
                import time
                current_time = int(time.time())
                db.execute_query(cursor, 'UPDATE matches SET veto_status = ?, map_picked = ?, last_action_time = ? WHERE id = ?',
                             (veto_json, last_map, current_time, match_id))
            else:
                # Switch turn
                db.execute_query(cursor, 'SELECT user_id FROM match_players WHERE match_id = ?', (match_id,))
                players = cursor.fetchall()
                next_turn = None
                for p in players:
                    if str(p['user_id']) != str(session['user_id']):
                        next_turn = p['user_id']
                        break
                
                if next_turn:
                    import time
                    current_time = int(time.time())
                    db.execute_query(cursor, 'UPDATE matches SET veto_status = ?, current_veto_turn = ?, last_action_time = ? WHERE id = ?',
                                 (veto_json, next_turn, current_time, match_id))
                         
            conn.commit()
            
        conn.close()
    except Exception as e:
        log_error(e, "/match_veto")
        flash(f"Error processing veto: {e}", "error")
        
    return redirect(url_for('match_room', match_id=match_id))

@app.route('/match/<int:match_id>/submit_result', methods=['POST'])
def submit_match_result(match_id):
    import db
    if 'user_id' not in session: return redirect(url_for('login'))
    
    try:
        winner_id = request.form.get('winner_id') # user_id of winner
        if not winner_id:
            flash('No winner selected', 'error')
            return redirect(url_for('match_room', match_id=match_id))
            
        conn = get_db_connection()
        if not conn: 
            flash("Database connection failed", "error")
            return redirect(url_for('match_room', match_id=match_id))
        
        cursor = conn.cursor()
        
        # Verify match exists and is active
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        if not match or match['status'] != 'active':
             conn.close()
             flash('Match not active or not found', 'error')
             return redirect(url_for('match_room', match_id=match_id))

        # Verify user is admin
        if not session.get('is_admin'):
             conn.close()
             flash('Только администраторы могут подтверждать результаты', 'error')
             return redirect(url_for('match_room', match_id=match_id))

        db.execute_query(cursor, "UPDATE matches SET status = 'finished', winner_team = ? WHERE id = ?", (winner_id, match_id))
        
        # Update ELO (simplified)
        # Winner +25, Loser -25
        # Check for annulled players
        db.execute_query(cursor, 'SELECT user_id, is_annulled FROM match_players WHERE match_id = ?', (match_id,))
        players = cursor.fetchall()
        
        for p in players:
            if p['is_annulled']:
                continue # Skip ELO update for annulled players
                
            if str(p['user_id']) == str(winner_id):
                db.execute_query(cursor, 'UPDATE users SET elo = elo + 25, wins = wins + 1, matches = matches + 1 WHERE user_id = ?', (p['user_id'],))
            else:
                db.execute_query(cursor, 'UPDATE users SET elo = elo - 25, matches = matches + 1 WHERE user_id = ?', (p['user_id'],))
                
        conn.commit()
        conn.close()
        
        flash('Результат матча подтвержден!', 'success')
    except Exception as e:
        log_error(e, "/submit_match_result")
        flash(f"Ошибка при подтверждении результата: {e}", "error")
        
    return redirect(url_for('match_room', match_id=match_id))

@app.route('/match/<int:match_id>/cancel', methods=['POST'])
def cancel_match(match_id):
    import db
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Set match status to cancelled
        db.execute_query(cursor, "UPDATE matches SET status = 'cancelled' WHERE id = ?", (match_id,))
        
        conn.commit()
        conn.close()
        
        flash('Матч был отменен. ELO не изменено.', 'success')
    except Exception as e:
        log_error(e, "/cancel_match")
        flash(f"Ошибка при отмене матча: {e}", 'error')
        
    return redirect(url_for('match_room', match_id=match_id))

@app.route('/match/<int:match_id>/leave', methods=['POST'])
def leave_match(match_id):
    import db
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user is in match and match is active
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        
        if not match or match['status'] != 'active':
            conn.close()
            flash('Матч не активен', 'error')
            return redirect(url_for('play'))
            
        db.execute_query(cursor, 'SELECT * FROM match_players WHERE match_id = ? AND user_id = ?', (match_id, session['user_id']))
        player = cursor.fetchone()
        
        if not player:
            conn.close()
            flash('Вы не участвуете в этом матче', 'error')
            return redirect(url_for('play'))
            
        # Mark match as disputed and user as left
        db.execute_query(cursor, "UPDATE matches SET status = 'disputed' WHERE id = ?", (match_id,))
        db.execute_query(cursor, "UPDATE match_players SET has_left = 1 WHERE match_id = ? AND user_id = ?", (match_id, session['user_id']))
        
        flash('Вы покинули матч. Матч помечен как СПОРНЫЙ. Администратор проверит ситуацию.', 'info')
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('play'))
    except Exception as e:
        log_error(e, "/leave_match")
        flash(f"Ошибка при выходе из матча: {e}", 'error')
        return redirect(url_for('match_room', match_id=match_id))

@app.route('/api/match/<int:match_id>/annul_player', methods=['POST'])
def api_annul_player(match_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    player_id = data.get('user_id')
    
    if not player_id:
        return jsonify({'error': 'Missing user_id'}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Toggle is_annulled
        db.execute_query(cursor, 'SELECT is_annulled FROM match_players WHERE match_id = ? AND user_id = ?', (match_id, player_id))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'Player not found in match'}), 404
            
        new_status = 0 if row['is_annulled'] else 1
        db.execute_query(cursor, 'UPDATE match_players SET is_annulled = ? WHERE match_id = ? AND user_id = ?', (new_status, match_id, player_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'is_annulled': new_status})
    except Exception as e:
        log_error(e, "/api/annul_player")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match/<int:match_id>')
def api_match_status(match_id):
    if 'user_id' not in session: 
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database error'}), 500
            
        cursor = conn.cursor()
        
        # Get match info
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        
        if not match:
            conn.close()
            return jsonify({'error': 'Match not found'}), 404
            
        # Parse veto status
        veto_data = {}
        if match['veto_status']:
            if isinstance(match['veto_status'], str):
                try:
                    veto_data = json.loads(match['veto_status'])
                except:
                    veto_data = {}
            else:
                veto_data = match['veto_status']
        
        # Check for timeout (30 seconds)
        remaining_time = 30
        if match['status'] == 'active' and not match['map_picked']:
            import time
            current_time = int(time.time())
            last_action_time = match['last_action_time']
            
            # If last_action_time is missing (for old matches), set it to now
            if not last_action_time:
                last_action_time = current_time
                db.execute_query(cursor, 'UPDATE matches SET last_action_time = ? WHERE id = ?', (current_time, match_id))
                conn.commit()
            
            remaining_time = 30 - (current_time - last_action_time)
            
            if remaining_time <= 0:
                # Timeout! Perform random action
                if not veto_data:
                    # Initialize if empty
                    veto_data = {m: 'available' for m in MAP_POOL}
                
                available_maps = [m for m, s in veto_data.items() if s == 'available']
                if available_maps:
                    import random
                    map_to_ban = random.choice(available_maps)
                    veto_data[map_to_ban] = 'banned'
                    
                    # Check remaining
                    available_maps = [m for m, s in veto_data.items() if s == 'available']
                    veto_json = json.dumps(veto_data)
                    
                    if len(available_maps) == 1:
                        # Last map picked
                        last_map = available_maps[0]
                        veto_data[last_map] = 'picked'
                        veto_json = json.dumps(veto_data)
                        db.execute_query(cursor, 'UPDATE matches SET veto_status = ?, map_picked = ?, last_action_time = ? WHERE id = ?', (veto_json, last_map, current_time, match_id))
                        match['map_picked'] = last_map
                        # match['veto_status'] updated implicitly for response via veto_data
                    else:
                        # Switch turn
                        current_turn = match['current_veto_turn']
                        db.execute_query(cursor, 'SELECT user_id FROM match_players WHERE match_id = ?', (match_id,))
                        players = cursor.fetchall()
                        next_turn = None
                        
                        # If current_turn is not set, pick first player
                        if not current_turn and players:
                             current_turn = players[0]['user_id']
                             
                        for p in players:
                            if str(p['user_id']) != str(current_turn):
                                next_turn = p['user_id']
                                break
                        
                        if next_turn:
                            db.execute_query(cursor, 'UPDATE matches SET veto_status = ?, current_veto_turn = ?, last_action_time = ? WHERE id = ?', (veto_json, next_turn, current_time, match_id))
                            match['current_veto_turn'] = next_turn
                    
                    conn.commit()
                    remaining_time = 30 # Reset timer for next turn

        # Get chat messages
        db.execute_query(cursor, '''
            SELECT mc.id, mc.message, mc.created_at, mc.user_id, u.nickname, u.avatar_url 
            FROM match_chat mc
            JOIN users u ON mc.user_id = u.user_id
            WHERE mc.match_id = ?
            ORDER BY mc.created_at ASC
        ''', (match_id,))
        chat_rows = cursor.fetchall()
        
        chat_messages = []
        for row in chat_rows:
            chat_messages.append({
                'id': row['id'],
                'user_id': row['user_id'],
                'nickname': row['nickname'],
                'avatar_url': row['avatar_url'],
                'message': row['message'],
                'created_at': str(row['created_at'])
            })
            
        conn.close()
        
        return jsonify({
            'status': match['status'],
            'veto_status': veto_data,
            'current_veto_turn': match['current_veto_turn'],
            'map_picked': match['map_picked'],
            'winner_team': match['winner_team'],
            'chat_messages': chat_messages,
            'current_user_id': session['user_id'],
            'remaining_time': remaining_time
        })
        
    except Exception as e:
        log_error(e, "/api/match")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match/<int:match_id>/veto', methods=['POST'])
def api_match_veto(match_id):
    if 'user_id' not in session: 
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        map_name = data.get('map_name')
        
        conn = get_db_connection()
        if not conn: 
            return jsonify({'error': 'Database error'}), 500
        
        cursor = conn.cursor()
        
        db.execute_query(cursor, 'SELECT * FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        
        if not match or match['status'] != 'active':
            conn.close()
            return jsonify({'error': 'Match not active'}), 400
            
        # Check turn
        if str(match['current_veto_turn']) != str(session['user_id']):
            conn.close()
            return jsonify({'error': 'Not your turn'}), 400
            
        veto_data = {}
        if match['veto_status']:
             if isinstance(match['veto_status'], str):
                 try:
                     veto_data = json.loads(match['veto_status'])
                 except:
                     veto_data = {}
             else:
                 veto_data = match['veto_status']
        
        if veto_data.get(map_name) == 'available':
            # Ban map
            veto_data[map_name] = 'banned'
            
            # Check remaining maps
            available_maps = [m for m, s in veto_data.items() if s == 'available']
            
            veto_json = json.dumps(veto_data)
            
            if len(available_maps) == 1:
                # Last map picked!
                import time
                current_time = int(time.time())
                last_map = available_maps[0]
                veto_data[last_map] = 'picked'
                veto_json = json.dumps(veto_data) # Update json with picked status
                
                db.execute_query(cursor, 'UPDATE matches SET veto_status = ?, map_picked = ?, last_action_time = ? WHERE id = ?',
                             (veto_json, last_map, current_time, match_id))
            else:
                # Switch turn
                db.execute_query(cursor, 'SELECT user_id FROM match_players WHERE match_id = ?', (match_id,))
                players = cursor.fetchall()
                next_turn = None
                for p in players:
                    if str(p['user_id']) != str(session['user_id']):
                        next_turn = p['user_id']
                        break
                
                if next_turn:
                    import time
                    current_time = int(time.time())
                    db.execute_query(cursor, 'UPDATE matches SET veto_status = ?, current_veto_turn = ?, last_action_time = ? WHERE id = ?',
                                 (veto_json, next_turn, current_time, match_id))
                         
            conn.commit()
            
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        log_error(e, "/api/match/veto")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match/<int:match_id>/chat', methods=['POST'])
def api_match_chat(match_id):
    if 'user_id' not in session: 
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Empty message'}), 400
            
        conn = get_db_connection()
        if not conn: 
            return jsonify({'error': 'Database error'}), 500
        
        cursor = conn.cursor()
        
        # Verify match exists
        db.execute_query(cursor, 'SELECT 1 FROM matches WHERE id = ?', (match_id,))
        match = cursor.fetchone()
        if not match:
            conn.close()
            return jsonify({'error': 'Match not found'}), 404
            
        # Verify user is participant or admin
        is_participant = False
        db.execute_query(cursor, 'SELECT 1 FROM match_players WHERE match_id = ? AND user_id = ?', (match_id, session['user_id']))
        if cursor.fetchone():
            is_participant = True
            
        if not is_participant and not session.get('is_admin'):
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
            
        db.execute_query(cursor, 'INSERT INTO match_chat (match_id, user_id, message) VALUES (?, ?, ?)',
                     (match_id, session['user_id'], message.strip()))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        log_error(e, "/api/match/chat")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/ban_user_v2', methods=['POST'])
def api_admin_ban_user_v2():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    user_id = data.get('user_id')
    # Support both old format (action='ban'/'unban') and new format (is_banned=True/False)
    action = data.get('action') 
    is_banned = data.get('is_banned')
    duration = data.get('duration', 0) # in minutes
    
    if is_banned is None and action:
        is_banned = (action == 'ban')
        
    if not user_id or is_banned is None:
        return jsonify({'error': 'Invalid data'}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        ban_expiration = 0
        if is_banned and duration > 0:
            import time
            ban_expiration = int(time.time()) + (duration * 60)
            
        db.execute_query(cursor, 'UPDATE users SET is_banned = ?, ban_expiration = ? WHERE user_id = ?', 
                         (1 if is_banned else 0, ban_expiration, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'is_banned': is_banned})
    except Exception as e:
        log_error(e, "/api/admin/ban_user_v2")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/warn_user_v2', methods=['POST'])
def api_warn_user_v2():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    if not user_id: return jsonify({'error': 'Missing user_id'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current warnings
        db.execute_query(cursor, 'SELECT warnings FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
        if not row:
             conn.close()
             return jsonify({'error': 'User not found'}), 404
             
        current_warnings = (row['warnings'] or 0) + 1
        message = f"Предупреждение выдано ({current_warnings}/3)"
        
        # Check if limit reached
        if current_warnings >= 3:
            # Reset warnings and ban for 1 hour
            import time
            ban_expiration = int(time.time()) + 3600
            db.execute_query(cursor, 'UPDATE users SET warnings = 0, is_banned = 1, ban_expiration = ? WHERE user_id = ?', (ban_expiration, user_id))
            message = "Игрок получил 3-е предупреждение и был забанен на 1 час!"
        else:
            db.execute_query(cursor, 'UPDATE users SET warnings = ? WHERE user_id = ?', (current_warnings, user_id))
            
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': message, 'warnings': current_warnings})
    except Exception as e:
        log_error(e, "/api/admin/warn_user_v2")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/set_role_v2', methods=['POST'])
def api_admin_set_role_v2():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    user_id = data.get('user_id')
    role = data.get('role') # 'admin' or 'user'
    
    if not user_id or role not in ['admin', 'user']:
        return jsonify({'error': 'Invalid data'}), 400
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_admin = 1 if role == 'admin' else 0
        db.execute_query(cursor, 'UPDATE users SET is_admin = ? WHERE user_id = ?', (is_admin, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'is_admin': is_admin})
    except Exception as e:
        log_error(e, "/api/admin/set_role_v2")
        return jsonify({'error': str(e)}), 500

# force deploy check
if __name__ == '__main__':
    app.run(debug=True, port=5000)