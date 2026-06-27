"""Servidor SEAF Monitor — API REST + SQLite."""
import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data", "seaf.db")

app = Flask(__name__, static_folder=APP_DIR, static_url_path="")
# Defina uma chave secreta real e segura em ambiente de produção
app.secret_key = "chave_secreta_para_sessoes" 

def utc_now():
    """Retorna o horário atual em formato ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_db():
    """Conecta ao banco de dados SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# --- Decoradores de Permissão ---
def admin_required(f):
    """Garante que apenas administradores acessem a rota."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({"erro": "Acesso negado: Administradores apenas"}), 403
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Garante que apenas usuários autenticados acessem a rota."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"erro": "Não autenticado"}), 401
        return f(*args, **kwargs)
    return decorated_function

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

# --- Rotas de Autenticação e Usuários ---
@app.post("/api/login")
def login():
    """Autentica um usuário e cria uma sessão."""
    body = request.get_json()
    username = body.get("username")
    password = body.get("password")
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            session['role'] = user['role']
            return jsonify({"username": user['username'], "role": user['role']})
            
    return jsonify({"erro": "Usuário ou senha inválidos"}), 401

@app.post("/api/logout")
def logout():
    """Limpa a sessão atual."""
    session.clear()
    return jsonify({"msg": "Logout efetuado com sucesso"})

@app.get("/api/me")
def get_me():
    """Retorna os dados do usuário atualmente logado."""
    if 'user' not in session:
         return jsonify({"erro": "Não autenticado"}), 401
    return jsonify({"username": session.get('user'), "role": session.get('role')})

@app.post("/api/users")
@admin_required
def create_user():
    """Rota para o admin criar novos acessos no sistema."""
    body = request.get_json()
    username = body.get("username")
    password = body.get("password")
    role = body.get("role", "usuario")
    
    if not username or not password:
        return jsonify({"erro": "Usuário e senha são obrigatórios"}), 400
        
    pwd_hash = generate_password_hash(password)
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, pwd_hash, role))
        return jsonify({"msg": "Usuário criado com sucesso!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"erro": "Este nome de usuário já existe."}), 400

# --- Rotas da Aplicação ---
@app.get("/")
def index():
    """Serve a interface front-end."""
    return send_from_directory(APP_DIR, "seaf_monitor_acoes.html")

@app.get("/api/acoes")
@login_required
def list_acoes():
    """Lista todas as ações cadastradas. Permite visualizadores."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM acoes ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@app.post("/api/acoes")
@admin_required
def create_acao():
    """Cria uma nova ação. Apenas administradores."""
    body = request.get_json()
    now = utc_now()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO acoes (
                nome, descricao, superintendencia, valor, fase,
                proxima_etapa, prazo, status, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)
            """,
            (body.get('nome', ''), body.get('desc', ''), body.get('sup', ''), 
             body.get('valor', 0), body.get('fase', 'Não iniciado'), 
             body.get('prox', ''), body.get('prazo', ''), now, now),
        )
        row = conn.execute("SELECT * FROM acoes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201

@app.put("/api/acoes/<int:acao_id>")
@admin_required
def update_acao(acao_id):
    """Atualiza uma ação existente. Apenas administradores."""
    body = request.get_json()
    now = utc_now()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE acoes SET 
                nome = ?, descricao = ?, superintendencia = ?, valor = ?, 
                fase = ?, proxima_etapa = ?, prazo = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (body.get('nome', ''), body.get('desc', ''), body.get('sup', ''), 
             body.get('valor', 0), body.get('fase', 'Não iniciado'), 
             body.get('prox', ''), body.get('prazo', ''), now, acao_id)
        )
    return jsonify({"msg": "Atualizado com sucesso"})

@app.patch("/api/acoes/aprovar/<int:acao_id>")
@admin_required
def approve_acao(acao_id):
    """Aprova o status de uma ação."""
    with get_db() as conn:
        conn.execute("UPDATE acoes SET status = 'aprovado' WHERE id = ?", (acao_id,))
    return jsonify({"msg": "Aprovado com sucesso"})

@app.delete("/api/acoes/<int:acao_id>")
@admin_required
def delete_acao(acao_id):
    """Exclui uma ação existente. Apenas administradores."""
    with get_db() as conn:
        conn.execute("DELETE FROM acoes WHERE id = ?", (acao_id,))
    return "", 204

@app.post("/api/acoes/importar")
@admin_required
def importar_acoes():
    """Importa múltiplas ações em lote via JSON/CSV."""
    payload = request.get_json()
    now = utc_now()
    if not isinstance(payload, list):
        return jsonify({"erro": "Formato inválido"}), 400
    
    count = 0
    with get_db() as conn:
        for item in payload:
            conn.execute(
                """
                INSERT INTO acoes (
                    nome, descricao, superintendencia, valor, fase,
                    proxima_etapa, prazo, status, criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)
                """,
                (item.get('nome', ''), item.get('desc', ''), item.get('sup', ''), 
                 item.get('valor', 0), item.get('fase', 'Não iniciado'), 
                 item.get('prox', ''), item.get('prazo', ''), now, now)
            )
            count += 1
            
            # Adiciona automaticamente as superintendências encontradas no CSV que ainda não existam
            sup_name = item.get('sup')
            if sup_name:
                conn.execute("INSERT OR IGNORE INTO superintendencias (nome, criado_em) VALUES (?, ?)", (sup_name, now))
                
        rows = conn.execute("SELECT * FROM acoes ORDER BY id DESC").fetchall()
                
    return jsonify({"msg": "Importação concluída", "importados": count, "acoes": [row_to_dict(r) for r in rows]}), 201

@app.get("/api/superintendencias")
@login_required
def list_superintendencias():
    """Lista todas as superintendências. Permite visualizadores."""
    with get_db() as conn:
        rows = conn.execute("SELECT id, nome FROM superintendencias").fetchall()
    return jsonify([{"id": r["id"], "nome": r["nome"]} for r in rows])

@app.post("/api/superintendencias")
@admin_required
def create_superintendencia():
    """Cria uma nova superintendência. Apenas administradores."""
    body = request.get_json()
    now = utc_now()
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO superintendencias (nome, criado_em) VALUES (?, ?)", (body['nome'], now))
        return jsonify({"msg": "Superintendência criada"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"erro": "Esta superintendência já existe."}), 400

@app.put("/api/superintendencias/<int:sup_id>")
@admin_required
def rename_superintendencia(sup_id):
    """Renomeia uma superintendência existente. Apenas administradores."""
    body = request.get_json()
    with get_db() as conn:
        conn.execute("UPDATE superintendencias SET nome = ? WHERE id = ?", (body['nome'], sup_id))
    return jsonify({"msg": "Superintendência renomeada com sucesso"}), 200

@app.delete("/api/superintendencias/<int:sup_id>")
@admin_required
def delete_superintendencia(sup_id):
    """Exclui uma superintendência. Apenas administradores."""
    with get_db() as conn:
        conn.execute("DELETE FROM superintendencias WHERE id = ?", (sup_id,))
    return "", 204

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)