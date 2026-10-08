import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

def data_dir():
    p = Path(os.getenv('FINPATH_DATA', './data')).resolve()
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p

def secret(name):
    p = data_dir() / name
    if not p.exists():
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(Fernet.generate_key())
        except FileExistsError:
            pass
    return p.read_bytes().strip()

def cipher():
    return Fernet(secret('statements.key'))

@contextmanager
def db():
    con = sqlite3.connect(data_dir() / 'finpath.sqlite3', timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def init_db():
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
          expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS statements (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          filename TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL,
          start_date TEXT NOT NULL, end_date TEXT NOT NULL, confirmed INTEGER DEFAULT 0,
          UNIQUE(user_id, sha256));
        CREATE TABLE IF NOT EXISTS transactions (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          statement_id INTEGER NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
          date TEXT NOT NULL, description TEXT NOT NULL, amount_cents INTEGER NOT NULL,
          category TEXT NOT NULL, essential INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS goals (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          name TEXT NOT NULL, target_cents INTEGER NOT NULL, saved_cents INTEGER NOT NULL,
          deadline TEXT NOT NULL);
        ''')
