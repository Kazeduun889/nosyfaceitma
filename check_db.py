import sqlite3
try:
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA table_info(users)')
    columns = cursor.fetchall()
    print("Columns in users table:")
    for col in columns:
        print(col)
    conn.close()
except Exception as e:
    print(e)
