import os
import sqlite3
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(APP_DIR, "data", "seaf.db")

def utc_now():
    """Retorna o horário atual em formato ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_db():
    """Conecta ao banco de dados SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Inicializa as tabelas do banco de dados, incluindo usuários e senhas."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS acoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL DEFAULT '',
                descricao TEXT NOT NULL DEFAULT '',
                superintendencia TEXT NOT NULL DEFAULT '',
                valor REAL NOT NULL DEFAULT 0,
                fase TEXT NOT NULL DEFAULT 'Não iniciado',
                proxima_etapa TEXT NOT NULL DEFAULT '',
                prazo TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pendente',
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'usuario'
            );

            CREATE TABLE IF NOT EXISTS superintendencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                criado_em TEXT NOT NULL
            );
            """
        )
        
        # Inserção do administrador padrão (se não existir)
        # O login padrão será: admin / admin123
        admin_pass = generate_password_hash("admin123")
        conn.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', admin_pass, 'admin'))

def row_to_dict(row):
    """Converte uma linha do banco de dados SQLite para um dicionário Python."""
    return {
        "id": row["id"],
        "nome": row["nome"],
        "desc": row["descricao"],
        "sup": row["superintendencia"],
        "valor": row["valor"],
        "fase": row["fase"],
        "prox": row["proxima_etapa"],
        "prazo": row["prazo"],
        "status": row["status"],
        "criado_em": row["criado_em"],
        "atualizado_em": row["atualizado_em"],
    }