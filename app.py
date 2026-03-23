from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime, timedelta
import sqlite3
import urllib.parse
import os


app = Flask(__name__)
app.secret_key = "minha_chave_secreta_123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def gerar_horarios(inicio, fim, intervalo_minutos=60):
    horarios = []
    hora_atual = datetime.strptime(inicio, "%H:%M")
    hora_fim = datetime.strptime(fim, "%H:%M")

    while hora_atual <= hora_fim:
        horarios.append(hora_atual.strftime("%H:%M"))
        hora_atual += timedelta(minutes=intervalo_minutos)

    return horarios

def obter_horarios_por_data(data_str):
    data_obj = datetime.strptime(data_str, "%Y-%m-%d")
    dia_semana = data_obj.weekday()

    # Segunda a sexta = 0 a 4
    if 0 <= dia_semana <= 4:
        return gerar_horarios("17:00", "19:00", 30)

    # Sábado = 5
    elif dia_semana == 5:
        return gerar_horarios("08:00", "17:00")

    # Domingo = 6
    else:
        return []
    
def obter_limite_agendamentos_por_data(data_str):
    data_obj = datetime.strptime(data_str, "%Y-%m-%d")
    dia_semana = data_obj.weekday()

    # Segunda a sexta
    if 0 <= dia_semana <= 4:
        return 5

    # Sábado
    elif dia_semana == 5:
        return 10

    # Domingo
    else:
        return 0

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            motivo TEXT
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

        data_obj = datetime.strptime(data, "%Y-%m-%d")

        if data_obj.weekday() == 6:
            return render_template("agendamento.html", erro="Domingo não há atendimento.")

        horarios_validos = obter_horarios_por_data(data)

        if not horarios_validos:
            return render_template("agendamento.html", erro="Não há atendimento nessa data.")

        if horario not in horarios_validos:
            return render_template("agendamento.html", erro="Esse horário não está disponível para essa data.")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM bloqueios WHERE data = ?", (data,))
        bloqueado = cursor.fetchone()

        if bloqueado:
            conn.close()
            return render_template("agendamento.html", erro="Essa data está bloqueada para atendimento.")

        cursor.execute("SELECT COUNT(*) FROM agendamentos WHERE data = ?", (data,))
        total_dia = cursor.fetchone()[0]

        limite_dia = obter_limite_agendamentos_por_data(data)

        if total_dia >= limite_dia:
            conn.close()
            return render_template("agendamento.html", erro="Esse dia já atingiu o limite de agendamentos.")

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

        mensagem = f"""*NOVO AGENDAMENTO*

        Nome: {nome}
        Telefone: {telefone}
        Serviço: {servico}
        Data: {data}
        Horário: {horario}
        Observação: {obs if obs else "Nenhuma"}
        """

        mensagem_codificada = urllib.parse.quote(mensagem, safe='')
        numero_whatsapp = "5516999621509"
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

    cursor.execute("""
        SELECT id, data, motivo
        FROM bloqueios
        ORDER BY data
    """)
    bloqueios = cursor.fetchall()

    conn.close()

    return render_template("admin.html", agendamentos=agendamentos, bloqueios=bloqueios)

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

        horarios_validos = obter_horarios_por_data(data)

        if not horarios_validos:
            conn.close()
            return render_template(
                "editar.html",
                agendamento=(id, nome, telefone, servico, data, horario),
                erro="Não há atendimento nessa data."
            )

        if horario not in horarios_validos:
            conn.close()
            return render_template(
                "editar.html",
                agendamento=(id, nome, telefone, servico, data, horario),
                erro="Esse horário não está disponível para essa data."
            )

        cursor.execute("""
            SELECT id FROM agendamentos
            WHERE data = ? AND horario = ? AND id != ?
        """, (data, horario, id))
        conflito = cursor.fetchone()

        if conflito:
            conn.close()
            return render_template(
                "editar.html",
                agendamento=(id, nome, telefone, servico, data, horario),
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

    if not data:
        return jsonify([])

    data_obj = datetime.strptime(data, "%Y-%m-%d")

    # Bloqueia domingos
    if data_obj.weekday() == 6:
        return jsonify([])

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verifica se a data está bloqueada manualmente
    cursor.execute("SELECT id FROM bloqueios WHERE data = ?", (data,))
    bloqueado = cursor.fetchone()

    if bloqueado:
        conn.close()
        return jsonify([])

    # Conta quantos agendamentos já existem no dia
    cursor.execute("SELECT COUNT(*) FROM agendamentos WHERE data = ?", (data,))
    total_dia = cursor.fetchone()[0]

    limite_dia = obter_limite_agendamentos_por_data(data)

    if total_dia >= limite_dia:
        conn.close()
        return jsonify([])

    # Busca horários ocupados
    cursor.execute("SELECT horario FROM agendamentos WHERE data = ?", (data,))
    ocupados = [row[0] for row in cursor.fetchall()]

    conn.close()

    horarios_base = obter_horarios_por_data(data)

    livres = [h for h in horarios_base if h not in ocupados]

    return jsonify(livres)  

@app.route("/bloquear-data", methods=["GET", "POST"])
def bloquear_data():
    if not session.get("admin_logado"):
        return redirect(url_for("login"))

    erro = None

    if request.method == "POST":
        data = request.form["data"]
        motivo = request.form.get("motivo", "")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO bloqueios (data, motivo) VALUES (?, ?)",
                (data, motivo)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            erro = "Essa data já está bloqueada."

        conn.close()

        if not erro:
            return redirect(url_for("admin"))

    return render_template("bloquear_data.html", erro=erro)

@app.route("/desbloquear-data/<int:id>")
def desbloquear_data(id):
    if not session.get("admin_logado"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bloqueios WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)