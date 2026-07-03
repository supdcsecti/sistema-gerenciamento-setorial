import sqlite3
from flask import Blueprint, request, jsonify, session
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
    sup_nome = body.get('sup', '')
    
    with get_db() as conn:
        sup_exists = conn.execute("SELECT 1 FROM superintendencias WHERE nome = ?", (sup_nome,)).fetchone()
        if not sup_exists:
            return jsonify({"erro": "Superintendência inválida ou inexistente."}), 400
        
        now = utc_now()
        cur = conn.execute(
            """
            INSERT INTO acoes (
                nome, descricao, superintendencia, responsavel, valor, fase,
                proxima_etapa, prazo, status, criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)
            """,
            (body.get('nome', ''), body.get('desc', ''), sup_nome, body.get('responsavel', ''),
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
    sup_nome = body.get('sup', '')
    
    with get_db() as conn:
        sup_exists = conn.execute("SELECT 1 FROM superintendencias WHERE nome = ?", (sup_nome,)).fetchone()
        if not sup_exists:
            return jsonify({"erro": "Superintendência inválida ou inexistente."}), 400
            
        now = utc_now()
        conn.execute(
            """
            UPDATE acoes SET 
                nome = ?, descricao = ?, superintendencia = ?, responsavel = ?, valor = ?, 
                fase = ?, proxima_etapa = ?, prazo = ?, atualizado_em = ?
            WHERE id = ?
            """,
            (body.get('nome', ''), body.get('desc', ''), sup_nome, body.get('responsavel', ''), body.get('valor', 0), 
             body.get('fase', 'Não iniciado'), body.get('prox', ''), body.get('prazo', ''), now, acao_id)
        )
    return jsonify({"msg": "Atualizado com sucesso"})

@acoes_bp.delete("/api/acoes/<int:acao_id>")
@admin_required
def delete_acao(acao_id):
    """Exclui uma ação existente. Apenas administradores."""
    with get_db() as conn:
        conn.execute("DELETE FROM acoes WHERE id = ?", (acao_id,))
    return "", 204

@acoes_bp.post("/api/acoes/excluir-lote")
@admin_required
def excluir_acoes_lote():
    """Remove múltiplas demandas em lote selecionadas no front-end."""
    body = request.get_json()
    ids = body.get("ids", [])
    if not ids:
        return jsonify({"erro": "Nenhum ID fornecido para exclusão."}), 400
        
    with get_db() as conn:
        placeholders = ",".join(["?"] * len(ids))
        conn.execute(f"DELETE FROM acoes WHERE id IN ({placeholders})", tuple(ids))
        
    return jsonify({"msg": f"{len(ids)} demandas excluídas com sucesso."}), 200

@acoes_bp.get("/api/acoes/<int:acao_id>/comentarios")
@login_required
def listar_comentarios(acao_id):
    """Retorna o histórico cronológico de notas/comentários de uma demanda específica."""
    with get_db() as conn:
        rows = conn.execute("SELECT username, texto, criado_em FROM comentarios WHERE acao_id = ? ORDER BY id ASC", (acao_id,)).fetchall()
    return jsonify([{"username": r["username"], "texto": r["texto"], "criado_em": r["criado_em"]} for r in rows])

@acoes_bp.post("/api/acoes/<int:acao_id>/comentarios")
@login_required
def adicionar_comentario(acao_id):
    """Permite a qualquer usuário autenticado registrar observações e comentários."""
    body = request.get_json()
    texto = body.get("texto", "").strip()
    if not texto:
        return jsonify({"erro": "O comentário não pode ser vazio"}), 400
        
    username = session['user']
    now = utc_now()
    with get_db() as conn:
        conn.execute("INSERT INTO comentarios (acao_id, username, texto, criado_em) VALUES (?, ?, ?, ?)", (acao_id, username, texto, now))
    return jsonify({"msg": "Comentário registrado com sucesso!", "username": username, "texto": texto, "criado_em": now}), 201

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
                    nome, descricao, superintendencia, responsavel, valor, fase,
                    proxima_etapa, prazo, status, criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?, ?)
                """,
                (item.get('nome', ''), item.get('desc', ''), item.get('sup', ''), item.get('responsavel', ''),
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