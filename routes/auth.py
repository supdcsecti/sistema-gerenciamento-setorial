import sqlite3
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db, utc_now
from utils.decorators import admin_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.post("/api/login")
def login():
    """Autentica um usuário e gerencia sessões e bloqueios de redefinição."""
    body = request.get_json()
    username = body.get("username")
    password = body.get("password")
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            session['role'] = user['role']
            return jsonify({
                "username": user['username'], 
                "role": user['role'],
                "requer_reset": bool(user['requer_reset'])
            })
            
    return jsonify({"erro": "Usuário ou senha inválidos"}), 401

@auth_bp.post("/api/logout")
def logout():
    """Limpa a sessão atual."""
    session.clear()
    return jsonify({"msg": "Logout efetuado com sucesso"})

@auth_bp.get("/api/me")
def get_me():
    """Retorna os dados do usuário atualmente logado."""
    if 'user' not in session:
         return jsonify({"erro": "Não autenticado"}), 401
    with get_db() as conn:
        user = conn.execute("SELECT username, role, requer_reset FROM users WHERE username = ?", (session['user'],)).fetchone()
    if not user:
        return jsonify({"erro": "Usuário inválido"}), 401
    return jsonify({
        "username": user['username'], 
        "role": user['role'], 
        "requer_reset": bool(user['requer_reset'])
    })

@auth_bp.get("/api/users")
def list_users():
    """Lista todos os usuários para popular dropdowns estruturais. Retorna vazio amigavelmente se não for admin."""
    if session.get('role') != 'admin':
        return jsonify([]) # Fallback seguro contra travamentos de interface de visualizadores comuns
    with get_db() as conn:
        rows = conn.execute("SELECT username, role, setor, email, requer_reset FROM users WHERE username != 'administrator' ORDER BY username ASC").fetchall()
    return jsonify([
        {
            "username": r["username"], 
            "role": r["role"],
            "setor": r["setor"],
            "email": r["email"],
            "requer_reset": bool(r["requer_reset"])
        } for r in rows
    ])

@auth_bp.post("/api/users")
@admin_required
def create_or_update_user():
    """Cria ou edita as propriedades completas de um usuário do sistema."""
    body = request.get_json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    role = body.get("role", "usuario")
    setor = body.get("setor", "").strip()
    email = body.get("email", "").strip()
    is_edit = body.get("is_edit", False)
    
    if not username:
        return jsonify({"erro": "O nome de usuário é obrigatório"}), 400
        
    with get_db() as conn:
        if is_edit:
            if password:
                pwd_hash = generate_password_hash(password)
                conn.execute(
                    "UPDATE users SET role = ?, setor = ?, email = ?, password = ? WHERE username = ?",
                    (role, setor, email, pwd_hash, username)
                )
            else:
                conn.execute(
                    "UPDATE users SET role = ?, setor = ?, email = ? WHERE username = ?",
                    (role, setor, email, username)
                )
            return jsonify({"msg": "Usuário atualizado com sucesso!"})
        else:
            if not password:
                return jsonify({"erro": "A senha é obrigatória para novos cadastros"}), 400
            pwd_hash = generate_password_hash(password)
            try:
                conn.execute(
                    "INSERT INTO users (username, password, role, setor, email, requer_reset) VALUES (?, ?, ?, ?, ?, 0)",
                    (username, pwd_hash, role, setor, email)
                )
                return jsonify({"msg": "Usuário criado com sucesso!"}), 201
            except sqlite3.IntegrityError:
                return jsonify({"erro": "Este nome de usuário já existe no sistema."}), 400

@auth_bp.delete("/api/users/<string:username>")
@admin_required
def delete_user(username):
    """Exclui um usuário do sistema."""
    if username == "administrator":
        return jsonify({"erro": "Não é possível remover o administrador mestre do sistema"}), 400
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
    return "", 204

@auth_bp.post("/api/solicitar-reset")
def solicitar_reset():
    """Permite a um usuário solicitar a redefinição de sua senha validando o e-mail cadastrado."""
    body = request.get_json()
    username = body.get("username", "").strip()
    email = body.get("email", "").strip()
    
    if not username or not email:
        return jsonify({"erro": "Informe o nome de usuário e o e-mail cadastrado para solicitar o reset"}), 400
        
    with get_db() as conn:
        user = conn.execute("SELECT email FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            return jsonify({"erro": "Nome de usuário não encontrado no sistema"}), 404
            
        if user["email"].lower() != email.lower():
            return jsonify({"erro": "O e-mail informado não condiz com o cadastrado para este usuário"}), 400
            
        conn.execute("INSERT INTO solicitacoes_reset (username, criado_em) VALUES (?, ?)", (username, utc_now()))
    return jsonify({"msg": "Alerta de redefinição validado e enviado com sucesso para o painel do administrador!"})

@auth_bp.get("/api/alertas-reset")
@admin_required
def listar_alertas():
    """Lista todos os pedidos de reset de senha pendentes."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM solicitacoes_reset WHERE status = 'pendente' ORDER BY id DESC").fetchall()
    return jsonify([{"id": r["id"], "username": r["username"], "criado_em": r["criado_em"]} for r in rows])

@auth_bp.post("/api/alertas-reset/processar")
@admin_required
def processar_redefinicao():
    """O Administrador define uma nova senha temporária para o usuário e força a redefinição futura."""
    body = request.get_json()
    alerta_id = body.get("id")
    username = body.get("username")
    nova_senha = body.get("password", "").strip()
    
    if not nova_senha:
        return jsonify({"erro": "Defina uma senha temporária válida"}), 400
        
    pwd_hash = generate_password_hash(nova_senha)
    with get_db() as conn:
        conn.execute("UPDATE users SET password = ?, requer_reset = 1 WHERE username = ?", (pwd_hash, username))
        conn.execute("DELETE FROM solicitacoes_reset WHERE id = ?", (alerta_id,))
    return jsonify({"msg": f"Senha de {username} redefinida! Próximo login exigirá alteração obrigatória."})

@auth_bp.post("/api/users/forcar-mudar-senha")
def alterar_senha_obrigatoria():
    """Gatilho acionado pelo usuário para trocar sua senha provisória e desbloquear sua conta."""
    if 'user' not in session:
        return jsonify({"erro": "Sessão inválida ou expirada"}), 401
    body = request.get_json()
    nova_senha = body.get("password", "").strip()
    if not nova_senha:
        return jsonify({"erro": "A nova senha não pode ser vazia"}), 400
        
    pwd_hash = generate_password_hash(nova_senha)
    with get_db() as conn:
        conn.execute("UPDATE users SET password = ?, requer_reset = 0 WHERE username = ?", (pwd_hash, session['user']))
    return jsonify({"msg": "Sua senha definitiva foi salva! O sistema foi liberado."})