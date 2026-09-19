import sqlite3
from datetime import datetime

DB_PATH = "site.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                bio TEXT DEFAULT '',
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                score INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)


# ---------- Пользователи ----------
def create_user(username, email, password_hash, is_admin=0):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, is_admin, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, email, password_hash, is_admin,
             datetime.now().strftime("%d.%m.%Y %H:%M")),
        )


def get_user_by_username(username):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


def get_user_by_id(user_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def user_exists(username, email):
    with get_db() as conn:
        return conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone() is not None


def count_users():
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
        return row["cnt"] if row else 0


def get_all_users():
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users ORDER BY id DESC"
        ).fetchall()


def update_user(user_id, email=None, bio=None, password_hash=None, is_admin=None):
    with get_db() as conn:
        if email is not None:
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
        if bio is not None:
            conn.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, user_id))
        if password_hash is not None:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id)
            )
        if is_admin is not None:
            conn.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?",
                (1 if is_admin else 0, user_id)
            )


def delete_user(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------- Сообщения ----------
def create_message(name, email, text):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (name, email, text, created_at) VALUES (?, ?, ?, ?)",
            (name, email, text, datetime.now().strftime("%d.%m.%Y %H:%M")),
        )


def get_all_messages():
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM messages ORDER BY id DESC"
        ).fetchall()


def delete_message(message_id):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))


# ---------- Рекорды игр ----------
def save_score(user_id, game, score):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO scores (user_id, game, score, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, game, score,
             datetime.now().strftime("%d.%m.%Y %H:%M")),
        )


def get_leaderboard(game, limit=10):
    """Топ-10 рекордов для игры (по убыванию счёта)."""
    with get_db() as conn:
        return conn.execute("""
            SELECT s.score, s.created_at, u.username
            FROM scores s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.game = ?
            ORDER BY s.score DESC
            LIMIT ?
        """, (game, limit)).fetchall()


def get_user_best(user_id, game):
    with get_db() as conn:
        row = conn.execute("""
            SELECT MAX(score) AS best FROM scores
            WHERE user_id = ? AND game = ?
        """, (user_id, game)).fetchone()
        return row["best"] if row and row["best"] else 0