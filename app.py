from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import datetime
import os

# --- Configuración Inicial ---
app = Flask(__name__, template_folder='templates')
CORS(app) # pyright: ignore[reportUnknownMemberType]
DB_FILE = "stats.db"

# ---------- Crear la base de datos si no existe ----------
def init_db():
    print("Inicializando base de datos...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS partidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            rival TEXT,
            marcador_local INTEGER,
            marcador_rival INTEGER,
            boxscore_json TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Base de datos '{DB_FILE}' lista.")

# --- Rutas de la Interfaz de Usuario (Frontend) ---

@app.route("/")
def index():
    """ Sirve la página principal de estadísticas de temporada. """
    return render_template("temporada.html")

@app.route("/boxscore")
def boxscore_page():
    """ Sirve la página para registrar un nuevo partido. """
    return render_template("boxscore.html")

# --- Rutas de la API (Backend) ---

@app.route("/guardar_boxscore", methods=["POST"])
def guardar_boxscore():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON vacío"}), 400

        rival = data.get("rival", "Desconocido")
        marcador_local = data.get("marcador_local", 0)
        marcador_rival = data.get("marcador_rival", 0)
        boxscore_json = json.dumps(data.get("boxscore", {}))
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO partidos (fecha, rival, marcador_local, marcador_rival, boxscore_json) VALUES (?,?,?,?,?)",
            (fecha, rival, marcador_local, marcador_rival, boxscore_json)
        )
        conn.commit()
        conn.close()

        return jsonify({"mensaje": "Boxscore guardado correctamente", "fecha": fecha}), 200

    except Exception as e:
        print("Error al guardar:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/partidos", methods=["GET"])
def listar_partidos():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row # Devuelve diccionarios en lugar de tuplas
    c = conn.cursor()
    c.execute("SELECT id, fecha, rival, marcador_local, marcador_rival FROM partidos ORDER BY id DESC")
    partidos = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(partidos)

@app.route("/partidos/<int:partido_id>", methods=["GET"])
def detalle_partido(partido_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, fecha, rival, marcador_local, marcador_rival, boxscore_json FROM partidos WHERE id = ?", (partido_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Partido no encontrado"}), 404

    # Convertir la fila a dict y parsear el JSON
    partido_dict = dict(row)
    partido_dict["boxscore"] = json.loads(partido_dict["boxscore_json"]) # pyright: ignore[reportUnknownArgumentType]
    del partido_dict["boxscore_json"] # No enviar el string JSON duplicado

    return jsonify(partido_dict)

# ---------- Inicio ----------
if __name__ == "__main__":
    init_db()
    print("Servidor Flask iniciado en http://127.0.0.1:5000")
    print("Abre http://127.0.0.1:5000 para ver las estadísticas")
    print("Abre http://127.0.0.1:5000/boxscore para registrar un partido")
    app.run(debug=True, port=5000)