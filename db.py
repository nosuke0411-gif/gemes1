import os
import psycopg2
from psycopg2 import pool
from flask_login import UserMixin

db_pool = pool.SimpleConnectionPool(
    1, 15,
    host=os.getenv("DB_HOST", "aws-0-ap-northeast-1.pooler.supabase.com"),
    database=os.getenv("DB_NAME", "postgres"),
    user=os.getenv("DB_USER", "postgres.txfrrpxosbhytshmwzkq"),
    password=os.getenv("DB_PASSWORD", ""),
    port=int(os.getenv("DB_PORT", 5432))
)

def get_conn():
    return db_pool.getconn()

def put_conn(conn):
    db_pool.putconn(conn)

class User(UserMixin):
    def __init__(self, id, username, password_hash, coins):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.coins = coins

def get_user_by_username(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, coins FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    put_conn(conn)
    if row:
        return User(row[0], row[1], row[2], row[3])
    return None

def get_user_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, coins FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    put_conn(conn)
    if row:
        return User(row[0], row[1], row[2], row[3])
    return None
