import sqlite3
from flask import Blueprint, request, jsonify
from database.connection import get_db, row_to_dict, utc_now
from utils.decorators import admin_required, login_required

acoes_bp = Blueprint('acoes', __name__)

@acoes_bp.get("/api/acoes")
@login_required
def list_acoes():
    """Lista todas as ações cadastradas. Permite visualizadores."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM acoes ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@acoes_bp.post("/api/acoes")
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

@acoes_bp.put("/api/acoes/<int:acao_id>")
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

@acoes_bp.delete("/api/acoes/<int:acao_id>")
@admin_required
def delete_acao(acao_id):
    """Exclui uma ação existente. Apenas administradores."""
    with get_db() as conn:
        conn.execute("DELETE FROM acoes WHERE id = ?", (acao_id,))
    return "", 204

@acoes_bp.post("/api/acoes/importar")
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
                    proxima_etapa, prazo, status, criado_em, updated_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)
                """,
                (item.get('nome', ''), item.get('desc', ''), item.get('sup', ''), 
                 item.get('valor', 0), item.get('fase', 'Não iniciado'), 
                 item.get('prox', ''), item.get('prazo', ''), now, now)
            )
            count += 1
            
            sup_name = item.get('sup')
            if sup_name:
                conn.execute("INSERT OR IGNORE INTO superintendencias (nome, criado_em) VALUES (?, ?)", (sup_name, now))
                
        rows = conn.execute("SELECT * FROM acoes ORDER BY id DESC").fetchall()
                
    return jsonify({"msg": "Importação concluída", "importados": count, "acoes": [row_to_dict(r) for r in rows]}), 201

@acoes_bp.get("/api/superintendencias")
@login_required
def list_superintendencias():
    """Lista todas as superintendências. Permite visualizadores."""
    with get_db() as conn:
        rows = conn.execute("SELECT id, nome FROM superintendencias").fetchall()
    return jsonify([{"id": r["id"], "nome": r["nome"]} for r in rows])

@acoes_bp.post("/api/superintendencias")
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

@acoes_bp.put("/api/superintendencias/<int:sup_id>")
@admin_required
def rename_superintendencia(sup_id):
    """Renomeia uma superintendência existente. Apenas administradores."""
    body = request.get_json()
    with get_db() as conn:
        conn.execute("UPDATE superintendencias SET nome = ? WHERE id = ?", (body['nome'], sup_id))
    return jsonify({"msg": "Superintendência renomeada com sucesso"}), 200

@acoes_bp.delete("/api/superintendencias/<int:sup_id>")
@admin_required
def delete_superintendencia(sup_id):
    """Exclui uma superintendência. Apenas administradores."""
    with get_db() as conn:
        conn.execute("DELETE FROM superintendencias WHERE id = ?", (sup_id,))
    return "", 204