import os
from flask import Flask, send_from_directory
from database.connection import init_db
from routes.auth import auth_bp
from routes.acoes import acoes_bp

APP_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=APP_DIR, static_url_path="")
app.secret_key = "chave_secreta_para_sessoes"

# Registrando os Blueprints modulares
app.register_blueprint(auth_bp)
app.register_blueprint(acoes_bp)

@app.get("/")
def index():
    """Serve a interface front-end principal."""
    return send_from_directory(APP_DIR, "seaf_monitor_acoes.html")

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)