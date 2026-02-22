import sqlite3

def check_bans():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1')
    banned_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT user_id, nickname, is_banned, ban_until, wins FROM users WHERE is_banned = 1 LIMIT 5')
    sample_banned = cursor.fetchall()
    
    conn.close()
    print(f"Total users: {total_count}")
    print(f"Banned users: {banned_count}")
    print(f"Sample banned users (uid, nick, is_banned, until, wins): {sample_banned}")

if __name__ == "__main__":
    check_bans()
