from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import urllib.parse
import os
from flask import jsonify

HORARIOS_DISPONIVEIS = [
    "08:00", "09:00", "10:00", "11:00",
    "13:00", "14:00", "15:00", "16:00", "17:00"
]
app = Flask(__name__)
app.secret_key = "minha_chave_secreta_123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            servico TEXT NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        if usuario == "admin" and senha == "1234":
            session["admin_logado"] = True
            return redirect(url_for("admin"))
        else:
            erro = "Usuário ou senha inválidos."

    return render_template("login.html", erro=erro)

@app.route("/agendamento", methods=["GET", "POST"])
def agendamento():
    if request.method == "POST":
        nome = request.form["nome"]
        telefone = request.form["telefone"]
        servico = request.form["servico"]
        data = request.form["data"]
        horario = request.form["horario"]
        obs = request.form.get("obs", "")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM agendamentos
            WHERE data = ? AND horario = ?
        """, (data, horario))
        agendamento_existente = cursor.fetchone()

        if agendamento_existente:
            conn.close()
            return render_template("agendamento.html", erro="Este horário já está ocupado. Escolha outro.")

        cursor.execute("""
            INSERT INTO agendamentos (nome, telefone, servico, data, horario)
            VALUES (?, ?, ?, ?, ?)
        """, (nome, telefone, servico, data, horario))
        conn.commit()
        conn.close()

        mensagem = f"""📅 *NOVO AGENDAMENTO*

👤 Nome: {nome}
📞 Telefone: {telefone}
🩺 Serviço: {servico}
📆 Data: {data}
⏰ Horário: {horario}
📝 Observação: {obs if obs else "Nenhuma"}
"""

        mensagem_codificada = urllib.parse.quote(mensagem)

        numero_whatsapp = "5516982202029"
        link_whatsapp = f"https://wa.me/{numero_whatsapp}?text={mensagem_codificada}"

        return redirect(link_whatsapp)

    return render_template("agendamento.html")

@app.route("/admin")
def admin():
    if not session.get("admin_logado"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, servico, data, horario
        FROM agendamentos
        ORDER BY data, horario
    """)
    agendamentos = cursor.fetchall()

    conn.close()

    return render_template("admin.html", agendamentos=agendamentos)

@app.route("/excluir/<int:id>")
def excluir(id):
    if not session.get("admin_logado"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM agendamentos WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin"))

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if not session.get("admin_logado"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        telefone = request.form["telefone"]
        servico = request.form["servico"]
        data = request.form["data"]
        horario = request.form["horario"]

        cursor.execute("""
            SELECT id FROM agendamentos
            WHERE data = ? AND horario = ? AND id != ?
        """, (data, horario, id))
        conflito = cursor.fetchone()

        if conflito:
            cursor.execute("""
                SELECT id, nome, telefone, servico, data, horario
                FROM agendamentos
                WHERE id = ?
            """, (id,))
            agendamento = cursor.fetchone()
            conn.close()
            return render_template(
                "editar.html",
                agendamento=agendamento,
                erro="Esse horário já está ocupado por outro agendamento."
            )

        cursor.execute("""
            UPDATE agendamentos
            SET nome = ?, telefone = ?, servico = ?, data = ?, horario = ?
            WHERE id = ?
        """, (nome, telefone, servico, data, horario, id))

        conn.commit()
        conn.close()
        return redirect(url_for("admin"))

    cursor.execute("""
        SELECT id, nome, telefone, servico, data, horario
        FROM agendamentos
        WHERE id = ?
    """, (id,))
    agendamento = cursor.fetchone()

    conn.close()

    return render_template("editar.html", agendamento=agendamento)

@app.route("/logout")
def logout():
    session.pop("admin_logado", None)
    return redirect(url_for("login"))

@app.route("/horarios")
def horarios():
    data = request.args.get("data")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT horario FROM agendamentos WHERE data = ?
    """, (data,))
    ocupados = [row[0] for row in cursor.fetchall()]

    conn.close()

    livres = [h for h in HORARIOS_DISPONIVEIS if h not in ocupados]

    return jsonify(livres)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)