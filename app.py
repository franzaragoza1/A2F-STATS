from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlalchemy # Importamos SQLAlchemy
import json
import datetime
import os # Importamos os para leer variables de entorno

# --- Configuración Inicial ---
app = Flask(__name__, template_folder='templates')
CORS(app)

# ¡CAMBIO IMPORTANTE!
# Ya no definimos DB_FILE. En su lugar, nos conectamos a la URL de la BBDD
# que pusimos en las variables de entorno de Render.
# Si no la encuentra, usa una BBDD sqlite local (para pruebas)
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///stats.db')
engine = sqlalchemy.create_engine(DATABASE_URL)

# ---------- Crear la base de datos si no existe ----------
def init_db():
    print("Inicializando base de datos...")
    # La sintaxis de CREATE TABLE es estándar y funciona en PostgreSQL
    create_table_query = """
    CREATE TABLE IF NOT EXISTS partidos (
        id SERIAL PRIMARY KEY,
        fecha TEXT,
        rival TEXT,
        marcador_local INTEGER,
        marcador_rival INTEGER,
        boxscore_json TEXT
    )
    """
    # Usamos SQLAlchemy para conectarnos y ejecutar
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text(create_table_query)) # pyright: ignore[reportUnknownMemberType]
        print("Tabla 'partidos' verificada/creada.")
    except Exception as e:
        print(f"Error al inicializar la BBDD: {e}")

# --- Rutas de la Interfaz de Usuario (Frontend) ---

@app.route("/")
def index():
    return render_template("temporada.html")

@app.route("/boxscore")
def boxscore_page():
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

        # ¡CAMBIO! Usamos engine.connect() y :parametros
        query = sqlalchemy.text(
            "INSERT INTO partidos (fecha, rival, marcador_local, marcador_rival, boxscore_json) VALUES (:fecha, :rival, :marcador_local, :marcador_rival, :boxscore_json)"
        )
        
        with engine.connect() as conn:
            conn.execute(query, {
                "fecha": fecha, 
                "rival": rival, 
                "marcador_local": marcador_local, 
                "marcador_rival": marcador_rival, 
                "boxscore_json": boxscore_json
            })
            conn.commit() # pyright: ignore[reportUnknownMemberType]

        return jsonify({"mensaje": "Boxscore guardado correctamente", "fecha": fecha}), 200

    except Exception as e:
        print("Error al guardar:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/partidos", methods=["GET"])
def listar_partidos():
    query = sqlalchemy.text("SELECT id, fecha, rival, marcador_local, marcador_rival FROM partidos ORDER BY id DESC")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        # Convertimos el resultado a una lista de diccionarios
        partidos = [dict(row._mapping) for row in result]
        
    return jsonify(partidos)

@app.route("/partidos/<int:partido_id>", methods=["GET"])
def detalle_partido(partido_id):
    query = sqlalchemy.text("SELECT id, fecha, rival, marcador_local, marcador_rival, boxscore_json FROM partidos WHERE id = :id")
    
    with engine.connect() as conn:
        result = conn.execute(query, {"id": partido_id})
        row = result.fetchone()

    if not row:
        return jsonify({"error": "Partido no encontrado"}), 404

    # Convertir la fila a dict y parsear el JSON
    partido_dict = dict(row._mapping)
    partido_dict["boxscore"] = json.loads(partido_dict["boxscore_json"])
    del partido_dict["boxscore_json"]

    return jsonify(partido_dict)

# ---------- Inicio ----------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"Servidor Flask iniciado en http://127.0.0.1:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)
