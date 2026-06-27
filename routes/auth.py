import sqlite3
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db
from utils.decorators import admin_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.post("/api/login")
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
    return jsonify({"username": session.get('user'), "role": session.get('role')})

@auth_bp.post("/api/users")
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