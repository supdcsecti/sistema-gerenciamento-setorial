from functools import wraps
from flask import jsonify, session

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